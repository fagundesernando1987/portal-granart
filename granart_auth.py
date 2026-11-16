"""Autenticacao Supabase para piloto; sem permissao de acesso por sessao Streamlit."""
from pathlib import Path
import urllib.request
import urllib.error
import json
import streamlit as st
import importlib

def _componente():
    # Importacao adiada: se o piloto estiver desligado, nao inicializa o componente.
    frontend = Path(__file__).resolve().parent / 'components' / 'granart_auth' / 'frontend'
    if not (frontend / 'index.html').is_file():
        st.error('Arquivos da autenticacao incompletos: falta components/granart_auth/frontend/index.html')
        st.stop()
    v1 = importlib.import_module('streamlit.components.v1')
    return v1.declare_component('granart_passkeys', path=str(frontend))


def _cfg():
    try:
        return dict(st.secrets.get('auth_passkeys', {}))
    except Exception:
        return {}


def piloto_ativo():
    return bool(_cfg().get('enabled', False))


def _validar_token(url, publishable_key, token):
    """Consulta Supabase Auth no servidor a CADA execucao. Nunca confia no email do browser."""
    if not isinstance(token, str) or not token or len(token) > 8192:
        return None
    req = urllib.request.Request(
        url.rstrip('/') + '/auth/v1/user',
        headers={'apikey': publishable_key, 'Authorization': 'Bearer ' + token,
                 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status != 200:
                return None
            obj = json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None
    return obj if isinstance(obj, dict) and obj.get('id') and obj.get('email_confirmed_at') else None


def exigir_acesso():
    """Bloqueia todo o BI se a autenticacao do piloto nao for validada."""
    cfg = _cfg()
    # Estes dois valores são públicos; não são credenciais administrativas.
    url = 'https://tgmlwxtchtlorbzgsfod.supabase.co'
    pub = 'sb_publishable_kjSwJJVulLRN3SnX4N0Y8A_fKvDoRDp'
    permitidos = {str(e).strip().casefold() for e in cfg.get('allowed_emails', []) if str(e).strip()}
    if not (permitidos):
        st.error('Acesso bloqueado: configure a lista allowed_emails em [auth_passkeys] nos Secrets.')
        st.stop()
    st.sidebar.caption('ACESSO SEGURO · HOMOLOGAÇÃO')
    # Token recebido de um componente de navegador; somente o Supabase valida a identidade.
    resultado = _componente()(url=url, publishableKey=pub, key='granart_passkeys_component', default=None)
    token = resultado.get('access_token') if isinstance(resultado, dict) else None
    usuario = _validar_token(url, pub, token)
    if usuario is None:
        st.title('Portal Executivo Gran’Art')
        st.info('Use o painel de acesso acima para entrar. O BI permanece bloqueado até a validação da sua conta.')
        st.stop()
    email = str(usuario.get('email', '')).strip().casefold()
    if email not in permitidos:
        st.error('Esta conta não está autorizada a acessar o Portal Gran’Art.')
        st.stop()
    st.sidebar.caption('Conectado: ' + email)
    return email
