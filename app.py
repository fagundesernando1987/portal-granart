import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import re
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='Gran’Art | Portal Executivo',page_icon='🏛️',layout='wide')
st.markdown('''<style>
.stApp{background:#f8f7f4;color:#302e2d}[data-testid="stSidebar"]{background:#f0ede7;border-right:1px solid #e2ddd3}
.block-container{padding-top:1.1rem;max-width:1650px}h1,h2,h3{color:#302e2d;letter-spacing:-.02em}
[data-testid="stSidebar"] [data-testid="stRadio"] label p{font-size:1.08rem!important;line-height:1.7!important}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]{gap:.5rem}
[data-testid="stMetric"]{background:white;border:1px solid #eae5dc;border-radius:13px;padding:14px 15px;min-width:0}
[data-testid="stMetricValue"]{font-size:clamp(1.03rem,1.7vw,1.65rem)!important;white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
.period{background:white;border-left:4px solid #aa987a;padding:12px 16px;border-radius:8px;margin:8px 0 16px}
.stButton button{border-radius:9px!important}
</style>''',unsafe_allow_html=True)

import hashlib as _hashlib
import hmac as _hmac
import time as _time

def _autenticar_granart():
    try:
        usuarios = dict(st.secrets["usuarios"])
    except Exception:
        usuarios = {}
    if not usuarios:
        st.error("Portal bloqueado: configure [usuarios] nos Secrets do Streamlit.")
        st.stop()
    atual = st.session_state.get("_granart_usuario")
    if atual in usuarios:
        with st.sidebar:
            st.caption("Usuário: " + atual)
            if st.button("Sair da conta", key="granart_sair"):
                del st.session_state["_granart_usuario"]
                st.rerun()
        return
    st.title("Portal Executivo Gran’Art")
    st.subheader("Acesso restrito aos sócios")
    with st.form("granart_login", clear_on_submit=True):
        usuario = st.text_input("Usuário").strip().lower()
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")
    if entrar:
        agora = _time.monotonic()
        n = st.session_state.get("_granart_erros", 0)
        t = st.session_state.get("_granart_erro_tempo", 0)
        if n >= 5 and agora - t < 120:
            st.error("Muitas tentativas. Aguarde 2 minutos.")
        else:
            ok = False
            try:
                tipo, sal, hash_hex = str(usuarios.get(usuario, "")).split("$")
                if tipo == "pbkdf2_sha256":
                    calculado = _hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), 600000)
                    ok = _hmac.compare_digest(calculado, bytes.fromhex(hash_hex))
            except (ValueError, TypeError):
                pass
            if ok:
                st.session_state["_granart_usuario"] = usuario
                st.session_state["_granart_erros"] = 0
                st.rerun()
            else:
                st.session_state["_granart_erros"] = n + 1
                st.session_state["_granart_erro_tempo"] = agora
                st.error("Usuário ou senha incorretos.")
    st.stop()

_autenticar_granart()

MONTHS=['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
FULL=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
FIELDS=[('Receita Bruta','receita_bruta'),('(-) Reserva Técnica dos Arquitetos','reserva_tecnica'),('(-) Simples Nacional','simples'),('(=) RECEITA LÍQUIDA','receita_liquida'),('(-) CPV','cpv'),('(=) LUCRO BRUTO','lucro_bruto'),('(-) Despesas Operacionais','despesas'),('(-) Salários e Encargos','salarios_encargos'),('(-) Pró-labore','pro_labore'),('(-) Depreciação','depreciacao'),('(+/-) Resultado Financeiro','resultado_financeiro'),('(+/-) Baixa de Clientes','baixa_clientes'),('(=) LUCRO LÍQUIDO','lucro_liquido')]
TABS=['Indicadores','DRE_Mensal','DRE_Gerencial','BI_Caixa','BI_Resumo_Producao','BI_Carteira_Producao','BI_Detalhe_Materiais','BI_Estoque_Materiais','BI_Orcamentos_Comercial','BI_Orcamentos_Itens']

def num(x,dec=1):
    try:return f'{float(x):,.{dec}f}'.replace(',','@').replace('.',',').replace('@','.')
    except:return '—'
def money(x):
    if pd.isna(x) or str(x).strip()=='':return 'Pendente de lançamento no controle'
    try:return ('−' if float(x)<0 else '')+'R$ '+num(abs(float(x)),2)
    except:return '—'
def compact(x):
    try:
        x=float(x);sign='−' if x<0 else '';x=abs(x)
        return sign+'R$ '+(num(x/1e6,2)+' mi' if x>=1e6 else num(x/1e3,1)+' mil' if x>=1e3 else num(x,2))
    except:return '—'
def pct(x):return num(x,1)+'%'
def val(df,k):return pd.to_numeric(df[k],errors='coerce').fillna(0) if k in df else pd.Series(0.0,index=df.index)
def moeda_editavel(rotulo, valor, chave):
    # Texto em pt-BR com separador de milhares. Atualiza no Enter ou ao sair do campo.
    original=num(valor,2)
    texto=st.text_input(rotulo,value=original,key=chave)
    limpo=str(texto).strip().replace('R$','').replace(' ','')
    try:
        if ',' in limpo:numero=float(limpo.replace('.','').replace(',','.'))
        else:numero=float(limpo.replace('.','')) if limpo.count('.')>1 else float(limpo)
        if not __import__('math').isfinite(numero):raise ValueError()
        return numero
    except (ValueError,TypeError):
        st.warning(f'Valor inválido em {rotulo}. Use, por exemplo, 100.000,00.')
        return float(valor)

def cards(data):
    for c,(name,v) in zip(st.columns(len(data)),data):c.metric(name,v)
def show(df,cols,rename=None,height=420,links=None,extra_config=None):
    x=df[[c for c in cols if c in df]].copy().rename(columns=rename or {})
    config={}
    for c in (links or []):
        label=(rename or {}).get(c,c)
        if label in x:config[label]=st.column_config.LinkColumn(label,display_text='Abrir')
    config.update(extra_config or {})
    st.dataframe(x,hide_index=True,width='stretch',height=height,column_config=config)

def config():
    try:return dict(st.secrets)
    except:return {}
CFG=config();LIVE=bool(CFG.get('google_sheets_id')) and (bool(CFG.get('gcp_service_account')) or bool(CFG.get('automacao_dir')))
@st.cache_data(ttl=300,show_spinner=False)
def load_sheet(name,live):
    if live:
        import gspread
        if CFG.get('gcp_service_account'):
            from google.oauth2.service_account import Credentials
            creds=Credentials.from_service_account_info(dict(CFG['gcp_service_account']),scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        else:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            pasta=Path(str(CFG['automacao_dir']))
            token=pasta/'token_google.json'
            if not token.is_file():raise RuntimeError('Token OAuth não encontrado na pasta da automação. Execute a publicação normal uma vez.')
            creds=Credentials.from_authorized_user_file(str(token),scopes=['https://www.googleapis.com/auth/spreadsheets'])
            if not creds.valid and creds.expired and creds.refresh_token:creds.refresh(Request())
            if not creds.valid:raise RuntimeError('Autenticação Google expirada; execute a publicação normal para renovar o acesso.')
        ws=gspread.authorize(creds).open_by_key(str(CFG['google_sheets_id'])).worksheet(name)
        records=ws.get_all_records(default_blank='',numericise_ignore=['all'],value_render_option='UNFORMATTED_VALUE' if name in {'BI_Planejamento','BI_Parametros_Planejamento','BI_Tickets_Anuais'} else 'FORMATTED_VALUE')
        frame=pd.DataFrame(records)
        # Planilhas: conversão de números em formatos pt-BR e internacionais
        for col in frame.columns:
            if col in {'orcamento','venda','codigo_venda','linha_excel','ordem','pedidos','dias_prazo','qtd_itens','qtd_selecionados','qtd_alternativas','m2_previsto','m2_realizado','m2_pendente','estoque_material_m2','demanda_pendente_m2','necessidade_teorica_m2','saldo_material_m2','valor_venda','valor_orcado_oficial','valor_final_controle','valor_vendido','valor_recebido','saldo_receber','m2_sem_quebra','m2_com_quebra','valor_item'} or (col in [k for _,k in FIELDS]):
                def parse(v):
                    s=str(v).strip().replace('R$','').replace(' ','')
                    if not s:return None
                    if ',' in s:s=s.replace('.','').replace(',','.')
                    try:return float(s)
                    except:return None
                frame[col]=frame[col].map(parse)
        return frame
    if name in {'DRE_Mensal','DRE_Gerencial'} and (ROOT/'dados_conciliados'/f'{name}.csv').exists():
        return pd.read_csv(ROOT/'dados_conciliados'/f'{name}.csv',encoding='utf-8-sig')
    return pd.read_excel(ROOT/'GranArt_BI_snapshot.xlsx',sheet_name=name)

def sheet(name):
    try:return load_sheet(name,LIVE)
    except Exception as e:
        if LIVE:
            st.error(f'Falha ao consultar Google Sheets ({name}): {e}. Não foi usada uma cópia antiga silenciosamente.')
            st.stop()
        raise

def updated():
    try:
        d=sheet('BI_Caixa')
        t=pd.to_datetime(d['data_extracao'],errors='coerce',utc=True).max()
        return t.tz_convert('America/Sao_Paulo').strftime('%d/%m/%Y às %H:%M') if pd.notna(t) else 'não informada'
    except:return 'não informada'

def dre():
    d=sheet('DRE_Gerencial').copy()
    d['mes']=pd.to_datetime(d['mes'],errors='coerce')
    d['ano']=d.mes.dt.year;d['nmes']=d.mes.dt.month
    d['situacao']=d.situacao.fillna('').astype(str)
    return d

def realized(d):return d[d.situacao.str.strip().str.casefold().eq('realizado')].copy()
def total(d):return {k:float(val(d,k).sum()) for _,k in FIELDS}
def period(d,y):
    a=d[d.ano==y].copy()
    if y==2021:
        dez2020=d[(d.ano==2020)&(d.nmes==12)]
        if not dez2020.empty:a=pd.concat([dez2020,a],ignore_index=True)
    return a

def period_name(d,y):
    months=sorted(d.loc[d.ano==y,'nmes'].dropna().astype(int).unique())
    return (f'Dez/2020–Dez/2021' if y==2021 and (d.ano==2020).any() else f'Jan–{MONTHS[max(months)-1]}/{y}') if months else str(y)
def chart(fig):
    fig.update_layout(height=310,margin=dict(l=12,r=15,t=20,b=45),paper_bgcolor='#fff',plot_bgcolor='#fff',legend=dict(orientation='h',y=-.32),font=dict(color='#353432'))
    st.plotly_chart(fig,width='stretch')

with st.sidebar:
    st.image(str(ROOT/'logo_granart.png'),width='stretch')
    st.caption('PORTAL EXECUTIVO · V3.5')
    if '_pending_nav' in st.session_state:st.session_state['nav']=st.session_state.pop('_pending_nav')
    nav=st.radio('Menu',['Visão Geral','DRE — Resultados','Financeiro','Comercial','Romaneios','Produção','Materiais e Estoque','Margem e Planejamento'],label_visibility='collapsed',key='nav')
    st.divider()
    if st.button('Atualizar dados agora',width='stretch'):
        load_sheet.clear();st.rerun()
    st.caption('Últimos dados do BI: '+updated())
    st.caption('Horário registrado na extração do Excel; o botão acima atualiza apenas a consulta do portal.' if LIVE else 'Base local de demonstração')
D=dre();R=realized(D)
YEARS=sorted([int(x) for x in R.ano.dropna().unique() if x>=2021],reverse=True)

if nav=='Visão Geral':
    st.title('Visão Geral')
    y=st.selectbox('Período',YEARS)
    p=period(R,y);t=total(p)
    st.markdown(f'<div class="period"><b>ACUMULADO {y}</b> · {period_name(p,y)} · {len(p)} meses fechados</div>',unsafe_allow_html=True)
    cards([('Receita bruta',compact(t['receita_bruta'])),('Receita líquida',compact(t['receita_liquida'])),('CPV',compact(abs(t['cpv'])))])
    cards([('Lucro bruto',compact(t['lucro_bruto'])),('Margem bruta',pct(100*t['lucro_bruto']/t['receita_liquida']) if t['receita_liquida'] else '—'),('Lucro líquido',compact(t['lucro_liquido'])),('Margem líquida',pct(100*t['lucro_liquido']/t['receita_liquida']) if t['receita_liquida'] else '—')])

    st.subheader('Acesso rápido')
    for c,label,dest in zip(st.columns(3),['DRE — Resultados','Financeiro','Comercial'],['DRE — Resultados','Financeiro','Comercial']):
        if c.button(label,width='stretch',key='quick_'+dest):st.session_state['_pending_nav']=dest;st.rerun()
    c1,c2=st.columns(2)
    for c,label,dest in [(c1,'Produção','Produção'),(c2,'Materiais e Estoque','Materiais e Estoque')]:
        if c.button(label,width='stretch',key='quick_'+dest):st.session_state['_pending_nav']=dest;st.rerun()

elif nav=='DRE — Resultados':
    st.title('DRE — Resultados')
    a,b=st.columns([3,1])
    with a:mode=st.segmented_control('Visualização',['Mês atual — Previsão','Último mês fechado','Acumulado','Comparar'],default='Acumulado') or 'Acumulado'
    with b:y=st.selectbox('Exercício',YEARS,disabled=mode=='Mês atual — Previsão')
    if mode=='Mês atual — Previsão':
        p=D[~D.situacao.str.strip().str.casefold().eq('realizado')].sort_values('mes').tail(1);period_label=(p.mes.dt.strftime('%m/%Y').iloc[0]+' · Previsão do mês') if len(p) else 'Previsão';y=int(p.ano.iloc[0]) if len(p) else y
    elif mode=='Último mês fechado':
        p=R[R.ano==y].sort_values('mes').tail(1);period_label=FULL[int(p.nmes.iloc[0])-1]+'/'+str(y)+' · FECHADO' if len(p) else str(y)
    else:p=period(R,y);period_label=period_name(p,y)+' · '+str(len(p))+' meses fechados'
    st.markdown(f'<div class="period"><b>{period_label}</b></div>',unsafe_allow_html=True)
    if p.empty:st.warning('Sem dados neste período.');st.stop()

    t=total(p)
    estimated=mode=='Mês atual — Previsão'
    cards([(label+(' estimada' if estimated and label not in ('CPV','Lucro bruto','Lucro líquido') else ' estimado' if estimated else ''),value) for label,value in [('Receita líquida',compact(t['receita_liquida'])),('CPV',compact(t['cpv'])),('Lucro bruto',compact(t['lucro_bruto'])),('Lucro líquido',compact(t['lucro_liquido'])),('Margem líquida',pct(100*t['lucro_liquido']/t['receita_liquida']) if t['receita_liquida'] else '—')]])
    previous=None;prev_t=None;prev_label=None
    if mode=='Comparar' and y>2021:
        months=sorted(p.nmes.dropna().astype(int).unique())
        previous=R[(R.ano==y-1)&R.nmes.isin(months)]
        prev_label=period_name(previous,y-1)
        st.caption(f'Valores completos disponíveis na DRE abaixo — comparação {period_name(p,y)} versus {prev_label} ({len(p)} e {len(previous)} meses fechados).')
        prev_t=total(previous)
    else:st.caption('Valores completos disponíveis na DRE abaixo.')
    st.subheader('Demonstração do Resultado')
    rows=[]
    for label,k in FIELDS:
        row={'Conta':label,period_name(p,y) if mode in ('Acumulado','Comparar') else period_label:money(t[k]),'% receita líquida':pct(100*t[k]/t['receita_liquida']) if t['receita_liquida'] else '—'}
        if prev_t is not None:row[prev_label]=money(prev_t[k]);row['Diferença']=money(t[k]-prev_t[k])
        rows.append(row)
    st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch',height=490)
    with st.expander('Dividendos e lucro reinvestido'):
        dividendos=abs(float(val(p,'dividendos').sum()))
        reinvestido=t['lucro_liquido']-dividendos
        cards([('Lucro líquido',money(t['lucro_liquido'])),('Dividendos distribuídos',money(dividendos)),('Lucro reinvestido',money(reinvestido))])
        st.caption('Lucro reinvestido = lucro líquido menos dividendos distribuídos no período selecionado. Não altera os lançamentos da planilha.')
    l,r=st.columns(2)
    with l:
        st.subheader('Margens bruta e líquida')
        labels=[period_name(p,y)];groups=[t]
        if prev_t is not None:labels.append(prev_label);groups.append(prev_t)
        fig=go.Figure()
        for k,name,color in [('lucro_bruto','Margem bruta','#ad946a'),('lucro_liquido','Margem líquida','#305d6b')]:
            values=[100*z[k]/z['receita_liquida'] if z['receita_liquida'] else 0 for z in groups]
            fig.add_bar(name=name,x=labels,y=values,marker_color=color,text=[pct(v) for v in values],textposition='outside')
        fig.update_layout(barmode='group',yaxis_title='%');chart(fig)
    with r:
        st.subheader('Receita, CPV e resultados mensais')
        monthly=p.sort_values('mes') if mode=='Mês atual — Previsão' else R[R.ano==y].sort_values('mes')
        fig=go.Figure()
        for k,name,color in [('receita_liquida','Receita líquida','#b08b43'),('cpv','CPV (magnitude)','#b34b4b'),('lucro_bruto','Lucro bruto','#288678'),('lucro_liquido','Lucro líquido','#3a548e')]:
            values=val(monthly,k).abs() if k=='cpv' else val(monthly,k)
            fig.add_scatter(x=monthly.mes.dt.strftime('%m/%Y'),y=values,mode='lines+markers',name=name,line=dict(color=color,width=2.5))
        chart(fig)

elif nav=='Financeiro':
    st.title('Financeiro');c=sheet('BI_Caixa');summary=c[c.tipo.astype(str).str.casefold()=='resumo']
    def lookup(s):
        a=summary[summary.indicador.astype(str).str.casefold()==s.casefold()]
        return float(a.valor.iloc[0]) if len(a) else 0.0
    st.subheader('Posição financeira')
    available=lookup('Disponível');cheques=float(c.loc[c.indicador.astype(str).str.casefold()=='cheques e cartão','valor'].sum());total_cash=lookup('Saldo financeiro total')
    cards([('Saldo disponível',compact(available)),('Cheques e cartão a receber',compact(cheques)),('Instalados a receber',compact(lookup('Instalados a receber')))])
    st.subheader('Capital de giro')
    cards([(k,compact(lookup(k))) for k in ['Sem investimentos e sem adiantamentos','Sem investimentos','Com investimentos']])
    st.subheader('Disponibilidade e saldos')
    acc=c[c.tipo.astype(str).str.casefold()=='conta'].copy();acc=acc[acc.indicador.notna() & acc.indicador.astype(str).str.strip().ne('')];acc=acc[acc.valor.notna()];acc=acc[~acc.indicador.astype(str).str.strip().str.casefold().isin(['nan','none','—','-'])];acc['valor']=acc.valor.map(money)
    show(acc,['indicador','valor'],{'indicador':'Fonte','valor':'Valor'},height=min(390,38+len(acc)*36))

elif nav=='Comercial':
    st.title('Comercial · Orçamentos')
    st.subheader('Evolução anual dos tickets médios')
    tickets=sheet('BI_Tickets_Anuais').copy()
    if not tickets.empty:
        tickets['ano']=pd.to_numeric(tickets['ano'],errors='coerce')
        tickets=tickets.dropna(subset=['ano']).sort_values('ano')
        if len(tickets):
            anos_tickets=sorted(tickets.ano.astype(int).unique().tolist(),reverse=True)
            ano_ticket=st.selectbox('Ano dos tickets médios',anos_tickets,key='ano_ticket')
            selecionado=tickets[tickets.ano.eq(ano_ticket)].iloc[0]
            cards([('Ticket orçado · '+str(ano_ticket),money(selecionado['ticket_orcado'])),('Ticket vendido · '+str(ano_ticket),money(selecionado['ticket_vendido'])),('Ticket instalado · '+str(ano_ticket),money(selecionado['ticket_instalado']))])
            if ano_ticket==max(anos_tickets):st.caption('O ano mais recente pode estar parcial.')
            fig=go.Figure()
            for key,label,color in [('ticket_orcado','Orçado','#ad946a'),('ticket_vendido','Vendido','#305d6b'),('ticket_instalado','Instalado','#42776c')]:
                fig.add_scatter(x=tickets.ano.astype(int).astype(str),y=pd.to_numeric(tickets[key],errors='coerce'),mode='lines+markers',name=label,line=dict(color=color,width=2.5))
            chart(fig)
            st.caption('Evolução histórica completa. Tickets calculados a partir das abas Orçam. e Receitas; ano corrente parcial.')
            with st.expander('Valores e quantidades por ano'):
                colunas=['ano','quantidade_orcado','valor_orcado','ticket_orcado','quantidade_vendido','valor_vendido','ticket_vendido','quantidade_instalado','valor_instalado','ticket_instalado']
                view=tickets[colunas].copy()
                for k in colunas:
                    if k.startswith('valor_') or k.startswith('ticket_'):view[k]=view[k].map(money)
                    elif k.startswith('quantidade_'):view[k]=pd.to_numeric(view[k],errors='coerce').map(lambda x:num(x,0))
                show(view,colunas,{'ano':'Ano','quantidade_orcado':'Qtd. orçada','valor_orcado':'Valor orçado','ticket_orcado':'Ticket orçado','quantidade_vendido':'Qtd. vendida','valor_vendido':'Valor vendido','ticket_vendido':'Ticket vendido','quantidade_instalado':'Qtd. instalada','valor_instalado':'Valor instalado','ticket_instalado':'Ticket instalado'},height=270)
    st.divider()
    df=sheet('BI_Orcamentos_Comercial').copy()
    st.subheader('Desempenho comercial')
    scope=st.segmented_control('Período comercial',['Mês','Ano','Histórico total'],default='Histórico total') or 'Histórico total'
    # Indicadores gerenciais: somente orçamentos cadastrados no Controle oficial.
    # Arquivos extraídos sem cadastro continuam disponíveis na consulta/auditoria.
    integracao=df.get('situacao_integracao',pd.Series('',index=df.index)).fillna('').astype(str).str.strip().str.casefold()
    oficial=integracao.eq('vinculado_controle')
    df_oficial=df.loc[oficial].copy()
    filtered=df_oficial.copy()
    if scope=='Ano':
        years=sorted(pd.to_numeric(df_oficial.get('ano_orcamento'),errors='coerce').dropna().astype(int).unique().tolist(),reverse=True)
        yy=st.selectbox('Ano do orçamento',years)
        filtered=filtered[pd.to_numeric(filtered.ano_orcamento,errors='coerce')==yy]
    elif scope=='Mês':
        periods=pd.to_datetime(df_oficial.get('data_orcamento_iso'),errors='coerce')
        period_options=sorted(periods.dropna().dt.to_period('M').astype(str).unique().tolist(),reverse=True)
        selected_period=st.selectbox('Mês do orçamento',period_options,format_func=lambda x:x[5:7]+'/'+x[:4])
        filtered=filtered[periods.dt.to_period('M').astype(str)==selected_period]
    status_raw=filtered.status_controle.fillna('').astype(str).str.strip().str.casefold()
    sold=status_raw.eq('vendido')
    issued=len(filtered);nsold=int(sold.sum())
    budget=pd.to_numeric(filtered.valor_orcado_oficial,errors='coerce')
    sold_value=pd.to_numeric(filtered.get('valor_vendido',pd.Series(index=filtered.index,dtype=float)),errors='coerce')
    # Valores oficiais apenas: sem substituir faltantes pelos extraídos dos arquivos de orçamento.
    sum_budget=float(budget.sum());sum_sold=float(sold_value[sold].sum())
    cards([('Orçamentos emitidos',num(issued,0)),('Orçamentos vendidos',num(nsold,0)),('Conversão de orçamentos',pct(100*nsold/issued) if issued else '—')])
    cards([('Valor total orçado',compact(sum_budget)),('Valor total vendido',compact(sum_sold)),('Conversão financeira',pct(100*sum_sold/sum_budget) if sum_budget else '—')])
    if budget.isna().any():st.caption(f'{int(budget.isna().sum())} orçamento(s) cadastrados no controle sem valor oficial; os totais financeiros refletem somente valores disponíveis.')
    pendentes=int((~oficial).sum())
    if pendentes:st.caption(f'{pendentes} arquivo(s) de orçamento ainda sem cadastro no Controle, excluído(s) dos indicadores oficiais; permanecem na consulta abaixo.')
    groups=status_raw.map(lambda x:'Vendido' if x=='vendido' else 'Recusado' if x=='recusado' else 'Em análise')
    amounts=budget.groupby(groups).sum().reindex(['Vendido','Recusado','Em análise'],fill_value=0)
    with st.expander('Distribuição dos orçamentos por situação',expanded=True):
        fig=go.Figure(go.Bar(x=amounts.index.tolist(),y=amounts.values.tolist(),text=[compact(v) for v in amounts.values],textposition='outside',marker_color=['#42776c','#9e8773','#b6a27b']))
        fig.update_layout(yaxis_title='Valor orçado oficial (R$)');chart(fig)
    st.divider()
    a,b=st.columns([2,1])
    with a:q=st.text_input('Buscar por código ou cliente')
    with b:status=st.selectbox('Situação',['Todos','Em análise','Vendido','Recusado'])
    raw=df.status_controle.fillna('').astype(str).str.strip().str.casefold()
    df['Situação']=raw.map(lambda x:'Vendido' if x=='vendido' else 'Recusado' if x=='recusado' else 'Em análise')
    # Cliente oficial: coluna C da aba Orçam. do Controle, publicada como cliente_controle.
    # Apenas se estiver vazia, utiliza o nome preenchido no Excel do orçamento.
    cliente_oficial=df.get('cliente_controle',pd.Series('',index=df.index)).fillna('').astype(str).str.strip()
    cliente_excel=df.get('cliente_excel',pd.Series('',index=df.index)).fillna('').astype(str).str.strip()
    df['Cliente']=cliente_oficial.where(cliente_oficial.ne(''),cliente_excel)
    df['Cliente']=df['Cliente'].where(df['Cliente'].ne(''),'Cliente não informado')
    if q:
        query=q.strip()
        df=df[df.orcamento.astype(str).str.replace(r'\.0$','',regex=True).str.contains(re.escape(query),case=False,na=False)|df['Cliente'].str.contains(re.escape(query),case=False,na=False)]
    if status!='Todos':df=df[df['Situação']==status]
    df['_sort']=pd.to_numeric(df.orcamento,errors='coerce');df=df.sort_values('_sort',ascending=False,na_position='last')
    cards([('Orçamentos encontrados',num(len(df),0))])
    st.subheader('Consulta de orçamentos')
    df['valor_orcado_oficial']=df.valor_orcado_oficial.map(money)
    # Links comerciais publicados pelo indexador do Drive, incluindo todos os status.
    if 'link_pdf' in df.columns:
        df['PDF']=df['link_pdf'].fillna('').astype(str)
    else:
        df['PDF']=''
    show(df,['orcamento','Cliente','Situação','valor_orcado_oficial','PDF'],{'orcamento':'Código do orçamento','valor_orcado_oficial':'Valor orçado'},height=470,links=['PDF'],extra_config={'Código do orçamento':st.column_config.NumberColumn('Código do orçamento',width='small',format='%d'),'Cliente':st.column_config.TextColumn('Cliente',width='medium'),'Valor orçado':st.column_config.TextColumn('Valor orçado',width='medium')})
    sem_pdf=int(df['PDF'].eq('').sum())
    if sem_pdf:st.caption(f'{sem_pdf} orçamento(s) da consulta ainda sem PDF correspondente na pasta do Drive.')
    st.subheader('Materiais dos orçamentos')
    code=st.text_input('Código do orçamento para consultar os itens')
    if code:
        items=sheet('BI_Orcamentos_Itens')
        selected=items[items.orcamento.astype(str).str.replace(r'\.0$','',regex=True)==code.strip()].copy()
        if selected.empty:st.info('Nenhum item encontrado.')
        else:
            for k in ['m2_sem_quebra','m2_com_quebra']:selected[k]=pd.to_numeric(selected[k],errors='coerce').map(lambda x:num(x,1) if pd.notna(x) else '—')
            selected['valor_item']=val(selected,'valor_item').map(money)
            show(selected,['ambiente','descricao','material_original','m2_sem_quebra','m2_com_quebra','somar_no_total','valor_item'],{'ambiente':'Ambiente','descricao':'Descrição','material_original':'Material','m2_sem_quebra':'Área sem quebra (m²)','m2_com_quebra':'Área com quebra (m²)','somar_no_total':'Considerar no total','valor_item':'Valor do item (R$)'},height=390,extra_config={'Descrição':st.column_config.TextColumn('Descrição',width='medium'),'Ambiente':st.column_config.TextColumn('Ambiente',width='small'),'Material':st.column_config.TextColumn('Material',width='medium')})
            st.caption('Área não informada na origem aparece como —, sem transformar ausência de dados em zero.')

elif nav=='Margem e Planejamento':
    st.title('Margem e Planejamento')
    st.caption('Simulação gerencial independente das abas Metas, Margem e Margem (2) do Excel. Os percentuais de Simples, reserva técnica e CPV têm como base a receita líquida (100%).')
    params=sheet('BI_Parametros_Planejamento').copy()
    plan=sheet('BI_Planejamento').copy()
    if params.empty or plan.empty:
        st.error('Bases de planejamento indisponíveis. Execute a nova automação antes de abrir esta área.')
        st.stop()
    def prm(key,default=0.):
        match=params[params.indicador.astype(str)==key]
        try:return float(match.valor.iloc[0]) if len(match) else default
        except:return default
    latest=params.loc[params.indicador.astype(str).eq('mes_ultimo_fechado'),'valor']
    st.caption('Base de custos até '+(str(latest.iloc[0]) if len(latest) else 'último fechamento')+' · Sazonalidade aprovada preservada no plano original.')
    historical=R.sort_values('mes').tail(12)
    latest_row=historical.iloc[-1]
    base_net=float(val(historical,'receita_liquida').sum())
    base_month_net=float(val(historical.tail(1),'receita_liquida').iloc[0])
    if base_net<=0:st.error('Receita líquida histórica inválida.');st.stop()
    st.subheader('Simulador mensal de margem e lucro')
    st.caption('Valores em reais, com separador de milhares. Para alterar, digite o valor e pressione Enter.')
    c1,c2,c3,c4=st.columns(4)
    with c1: gross=moeda_editavel('Receita bruta simulada (R$)',float(max(0,round(base_month_net*(1+prm('simples_sobre_liquida')+prm('reserva_tecnica_sobre_liquida')),2))),'sim_bruto')
    with c2:tax=st.number_input('Simples (% da líquida)',min_value=0.,max_value=100.,value=round(prm('simples_sobre_liquida')*100,3),step=.1,format='%.3f')/100
    with c3:rt=st.number_input('Reserva técnica (% da líquida)',min_value=0.,max_value=100.,value=round(prm('reserva_tecnica_sobre_liquida')*100,3),step=.1,format='%.3f')/100
    with c4:cpvr=st.number_input('CPV de materiais (% da líquida)',min_value=0.,max_value=100.,value=round(prm('cpv_sobre_liquida')*100,3),step=.1,format='%.3f')/100
    a,b,c,d=st.columns(4)
    with a:salary=moeda_editavel('Salários e encargos mensais (R$)',prm('salarios_encargos_media_12m'),'sim_salarios')
    with b:pro=moeda_editavel('Pró-labore mensal (R$)',prm('pro_labore_media_12m'),'sim_pro')
    with c:opex=moeda_editavel('Despesas operacionais mensais (R$)',prm('despesas_media_12m'),'sim_desp')
    with d:dep=moeda_editavel('Depreciação mensal (R$)',prm('depreciacao_base_mensal'),'sim_dep')
    a,b,c=st.columns(3)
    with a:fin=moeda_editavel('Resultado financeiro mensal assinado (R$)',prm('resultado_financeiro_base_mensal'),'sim_fin')
    with b:bad=moeda_editavel('Baixa de clientes mensal assinada (R$)',prm('baixa_clientes_base_mensal'),'sim_baixa')
    with c:desired=moeda_editavel('Lucro líquido mensal desejado (R$)',100000.,'sim_desejado')
    net=gross/(1+tax+rt);simples=net*tax;reserve=net*rt;material=net*cpvr
    contrib=net-material
    operating=contrib-salary-pro-opex-dep
    profit=operating+fin+bad
    margin_contrib=1-cpvr
    fixed_oper=salary+pro+opex+dep
    breakeven_oper=(fixed_oper/margin_contrib)*(1+tax+rt) if margin_contrib>0 else None
    breakeven_full=((fixed_oper-fin-bad)/margin_contrib)*(1+tax+rt) if margin_contrib>0 else None
    required=((desired+fixed_oper-fin-bad)/margin_contrib)*(1+tax+rt) if margin_contrib>0 else None
    cards([('Receita líquida',money(net)),('Margem de contribuição',money(contrib)),('Lucro operacional',money(operating)),('Lucro líquido simulado',money(profit))])
    cards([('Equilíbrio operacional (bruto)',money(max(0,breakeven_oper)) if breakeven_oper is not None else 'Inviável'),('Equilíbrio com financeiro (bruto)',money(max(0,breakeven_full)) if breakeven_full is not None else 'Inviável'),('Bruto para lucro desejado',money(max(0,required)) if required is not None else 'Inviável')])
    with st.expander('DRE completa da simulação',expanded=False):
        details=[('Receita bruta',gross),('(-) Simples Nacional',-simples),('(-) Reserva técnica',-reserve),('Receita líquida',net),('(-) CPV / materiais',-material),('Margem de contribuição',contrib),('(-) Salários e encargos',-salary),('(-) Pró-labore',-pro),('(-) Despesas operacionais',-opex),('(-) Depreciação',-dep),('Resultado financeiro',fin),('Baixa de clientes',bad),('Lucro líquido',profit)]
        show(pd.DataFrame([{'Conta':name,'Valor':money(v),'% da receita líquida':pct(v/net*100) if net else '—'} for name,v in details]),['Conta','Valor','% da receita líquida'],height=490)
    st.divider()
    st.subheader('Planejamento anual e próximos 12 meses')
    def parse_plan_month(v):
        t=str(v).strip()
        if not t or t.lower() in ('nan','none'):return pd.NaT
        if re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?',t):return pd.to_datetime(t[:7],format='%Y-%m',errors='coerce')
        try:
            n=float(t)
            if 30000<n<80000:return pd.Timestamp('1899-12-30')+pd.to_timedelta(n,unit='D')
        except (ValueError,TypeError):pass
        return pd.to_datetime(t,dayfirst=True,errors='coerce')
    plan['mes']=plan['mes'].map(parse_plan_month).dt.to_period('M').dt.to_timestamp()
    plan['ano']=plan['mes'].dt.year.astype('Int64')
    for col in ('meta_lucro_anual','meta_receita_bruta_anual','peso_sazonal','receita_bruta_planejada'):
        plan[col]=pd.to_numeric(plan[col],errors='coerce')
    years_plan=sorted(plan.ano.dropna().astype(int).unique().tolist())
    if not years_plan:
        st.error('Nenhum exercício válido encontrado na base BI_Planejamento.');st.stop()
    year=st.selectbox('Exercício do planejamento',years_plan,index=0)
    annual=plan[plan.ano.eq(year)].sort_values('mes').copy()
    if annual.empty:st.error('Planejamento do exercício indisponível.');st.stop()
    goal=float(annual.meta_lucro_anual.iloc[0]);gross_target=float(annual.meta_receita_bruta_anual.iloc[0])
    # Preserva os pesos trimestrais aprovados, mas distribui igualmente entre os 3 meses.
    pesos=pd.to_numeric(annual.peso_sazonal,errors='coerce').fillna(0).to_numpy()
    if len(pesos)!=12 or pesos.sum()<=0:st.error('Pesos sazonais inválidos.');st.stop()
    pesos=pesos/pesos.sum()
    pesos_trimestrais=[sum(pesos[q:q+3]) for q in (0,3,6,9)]
    pesos_iguais=[pesos_trimestrais[q//3]/3 for q in range(12)]
    annual['peso_igual']=pesos_iguais
    annual['meta_mensal']=gross_target*annual.peso_igual
    annual['trimestre']=((annual.mes.dt.month-1)//3+1)
    # Fonte de realizado: somente meses efetivamente fechados na DRE.
    fechados=R[R.mes.dt.year.eq(year)].copy()
    bruto_real=dict(zip(fechados.mes.dt.to_period('M'),val(fechados,'receita_bruta')))
    lucro_real=dict(zip(fechados.mes.dt.to_period('M'),val(fechados,'lucro_liquido')))
    annual['realizado']=annual.mes.dt.to_period('M').map(bruto_real)
    annual['lucro_realizado']=annual.mes.dt.to_period('M').map(lucro_real)
    fechado=annual.realizado.notna()
    bruto_acumulado=float(annual.loc[fechado,'realizado'].sum())
    lucro_acumulado=float(annual.loc[fechado,'lucro_realizado'].sum())
    peso_fechado=float(annual.loc[fechado,'peso_igual'].sum())
    tendencia_bruta=(bruto_acumulado/peso_fechado) if peso_fechado>0 else None
    # Meta reprogramada para os meses abertos; não modifica o plano original.
    peso_aberto=float(annual.loc[~fechado,'peso_igual'].sum())
    falta_bruto=max(0,gross_target-bruto_acumulado)
    annual['meta_recalculada']=annual['meta_mensal']
    if peso_aberto>0:
        annual.loc[~fechado,'meta_recalculada']=annual.loc[~fechado,'peso_igual']*falta_bruto/peso_aberto
    annual.loc[fechado,'meta_recalculada']=float('nan')
    annual['pct_meta']=annual.realizado/annual.meta_mensal*100
    # DRE projetada usa as premissas financeiras atuais e custo extra de 50% em nov/dez.
    annual_salary=prm('salarios_encargos_base_mensal')
    annual_pro=prm('pro_labore_base_mensal')
    annual_opex=prm('despesas_base_mensal')
    annual_dep=prm('depreciacao_base_mensal')
    annual_fin=prm('resultado_financeiro_base_mensal')
    annual_bad=prm('baixa_clientes_base_mensal')
    # As taxas são baseadas na receita líquida (100%).
    def dre_projetada(bruto,mes):
        liquida=bruto/(1+tax+rt)
        fator=1.5 if mes in (11,12) else 1.
        return {'receita_bruta':bruto,'simples':-liquida*tax,'reserva_tecnica':-liquida*rt,'receita_liquida':liquida,'cpv':-liquida*cpvr,'lucro_bruto':liquida*(1-cpvr),'despesas':-annual_opex,'salarios_encargos':-annual_salary*fator,'pro_labore':-annual_pro*fator,'depreciacao':-annual_dep,'resultado_financeiro':annual_fin,'baixa_clientes':annual_bad,'lucro_liquido':liquida*(1-cpvr)-annual_opex-(annual_salary+annual_pro)*fator-annual_dep+annual_fin+annual_bad}
    previsto=[dre_projetada(float(r.meta_mensal),int(r.mes.month)) for r in annual.itertuples()]
    futuro=[dre_projetada(float(r.meta_mensal),int(r.mes.month)) for r in annual.itertuples()]
    annual['lucro_meta']= [r['lucro_liquido'] for r in previsto]
    annual['lucro_tendencia']=annual['lucro_realizado'].where(fechado,pd.Series([r['lucro_liquido'] for r in futuro],index=annual.index))
    st.markdown('**Resumo do exercício**')
    cards([('Meta de lucro anual',money(goal)),('Faturamento bruto planejado',money(gross_target)),('Receita bruta realizada',money(bruto_acumulado)),('Falta faturar para a meta',money(falta_bruto))])
    cards([('Lucro realizado',money(lucro_acumulado)),('Tendência de faturamento pela sazonalidade',money(tendencia_bruta) if tendencia_bruta is not None else 'Sem meses fechados'),('Tendência de lucro (realizado + previsto)',money(annual.lucro_tendencia.sum())),('Sazonalidade de referência',str(int(annual.sazonalidade_ano.iloc[0])))])
    st.caption('O plano anual permanece fixo. A tendência de faturamento usa o peso sazonal dos meses fechados; a tendência de lucro soma a DRE realizada aos meses futuros projetados.')
    st.subheader('Acompanhamento mensal')
    st.caption('Metas iguais nos três meses de cada trimestre. A meta recalculada redistribui o saldo anual somente entre os meses abertos, conforme os pesos dos trimestres restantes.')
    tabela=pd.DataFrame({'Mês':annual.mes.dt.strftime('%m/%Y'),'Meta bruta':annual.meta_mensal,'Realizado':annual.realizado,'% realizado':annual.pct_meta,'Meta recalculada':annual.meta_recalculada,'Lucro meta projetado':annual.lucro_meta,'Lucro realizado':annual.lucro_realizado,'Diferença do lucro':annual.lucro_realizado-annual.lucro_meta})
    for c in ['Meta bruta','Realizado','Meta recalculada','Lucro meta projetado','Lucro realizado','Diferença do lucro']:
        tabela[c]=tabela[c].map(lambda v:money(v) if pd.notna(v) else '—')
    tabela['% realizado']=tabela['% realizado'].map(lambda v:pct(v) if pd.notna(v) else '—')
    st.dataframe(tabela,hide_index=True,width='stretch',height=465)
    fig=go.Figure()
    fig.add_scatter(x=annual.mes.dt.strftime('%m/%Y'),y=annual.meta_mensal,mode='lines+markers',name='Meta original',line=dict(color='#ad946a'))
    fig.add_scatter(x=annual.mes.dt.strftime('%m/%Y'),y=annual.realizado,mode='lines+markers',name='Realizado',line=dict(color='#305d6b'))
    fig.add_scatter(x=annual.mes.dt.strftime('%m/%Y'),y=annual.meta_recalculada,mode='lines+markers',name='Meta recalculada',line=dict(color='#42776c',dash='dash'))
    chart(fig)
    st.subheader('DRE anual — previsto, realizado e tendência')
    dre_linhas=[('Receita bruta','receita_bruta'),('(-) Simples Nacional','simples'),('(-) Reserva técnica','reserva_tecnica'),('Receita líquida','receita_liquida'),('(-) CPV de materiais','cpv'),('Margem de contribuição','lucro_bruto'),('(-) Despesas operacionais','despesas'),('(-) Salários e encargos','salarios_encargos'),('(-) Pró-labore','pro_labore'),('(-) Depreciação','depreciacao'),('Resultado financeiro','resultado_financeiro'),('Baixa de clientes','baixa_clientes'),('Lucro líquido','lucro_liquido')]
    tabela_dre=[]
    for nome,k in dre_linhas:
        prev=sum(m[k] for m in previsto)
        real=float(val(fechados,k).sum())
        tend=real+sum(futuro[i][k] for i in range(len(futuro)) if not bool(fechado.iloc[i]))
        tabela_dre.append({'Conta':nome,'Previsto anual':money(prev),'Realizado fechado':money(real),'Tendência de fechamento':money(tend)})
    st.dataframe(pd.DataFrame(tabela_dre),hide_index=True,width='stretch',height=500)
    st.caption('Previsto: premissas atuais aplicadas ao plano anual. Realizado: DRE dos meses fechados. Tendência: realizado + meses futuros com sazonalidade e custos previstos.')
    with st.expander('Simular outro cenário (não altera o plano)',expanded=False):
        st.caption('Este teste não grava alterações nas metas anuais aprovadas.')
        c1,c2=st.columns(2)
        with c1:goal_scenario=moeda_editavel('Meta de lucro para simular (R$)',goal,'cenario_lucro_'+str(year))
        with c2:salary_growth=st.number_input('Reajuste dos custos fixos (%)',value=0.,min_value=-50.,max_value=200.,step=1.,key='cenario_reajuste_'+str(year))/100
        fixo=14*(annual_salary+annual_pro)*(1+salary_growth)+12*(annual_opex*(1+salary_growth)+annual_dep-annual_fin-annual_bad)
        if 1-cpvr>0:
            scenario_gross=max(0,(goal_scenario+fixo)/(1-cpvr)*(1+tax+rt))
            cards([('Faturamento bruto necessário',money(scenario_gross)),('Diferença para o plano original',money(scenario_gross-gross_target))])
        else:st.error('CPV impede margem de contribuição positiva.')
    st.subheader('Próximos 12 meses')
    available=plan[plan.mes.notna()].sort_values('mes').copy()
    # Também na janela móvel, distribuir os pesos trimestrais igualmente.
    available['peso_igual']=0.
    for ano_group,group in available.groupby('ano'):
        if len(group)!=12:continue
        weights=pd.to_numeric(group.peso_sazonal,errors='coerce').fillna(0).to_numpy()
        if weights.sum()<=0:continue
        weights=weights/weights.sum()
        w=[sum(weights[q:q+3])/3 for q in (0,3,6,9) for _ in range(3)]
        available.loc[group.index,'peso_igual']=w
    available['meta_corrigida']=available.meta_receita_bruta_anual*available.peso_igual
    last_close=R.mes.max()
    next_month=(last_close.to_period('M')+1).to_timestamp()
    rolling=available[(available.mes>=next_month)&(available.mes<next_month+pd.DateOffset(months=12))].copy()
    if len(rolling):
        rolling['Mês']=rolling.mes.dt.strftime('%m/%Y')
        rolling['Plano do exercício']=rolling.meta_corrigida.map(money)
        show(rolling,['Mês','ano','Plano do exercício'],{'ano':'Exercício'},height=460)
        st.metric('Total bruto dos próximos 12 meses',money(rolling.meta_corrigida.sum()))
        st.caption('Cada mês pertence ao plano anual do respectivo exercício; a meta de 2027 não é antecipada para 2026.')
    else:st.info('Janela móvel fora dos anos disponíveis no planejamento.')

elif nav=='Romaneios':
    st.title('Romaneio de Produção e Entrega')
    base=sheet('BI_Orcamentos_Comercial').copy()
    status_base=base.get('status_controle',pd.Series('',index=base.index)).fillna('').astype(str).str.strip().str.casefold()
    integracao_base=base.get('situacao_integracao',pd.Series('',index=base.index)).fillna('').astype(str).str.strip().str.casefold()
    elegiveis=base[status_base.eq('vendido') & integracao_base.eq('vinculado_controle')].copy()
    # Filtro principal: somente pedidos presentes na carteira e AGUARDANDO PRODUÇÃO.
    # Não tratar a ausência na carteira como pedido em aberto.
    carteira_rom=sheet('BI_Carteira_Producao').copy()
    def codigo_rom(v):
        try:return str(int(float(v))) if pd.notna(v) and str(v).strip() else ''
        except:return str(v).strip()
    carteira_rom['_codigo']=carteira_rom['orcamento'].map(codigo_rom)
    carteira_rom['_status_normalizado']=carteira_rom['status'].fillna('').astype(str).str.strip().str.casefold()
    codigos_producao=set(carteira_rom.loc[carteira_rom['_status_normalizado'].eq('aguardando produção'),'_codigo'])
    elegiveis['_codigo']=elegiveis['orcamento'].map(codigo_rom)
    filtro_rom=st.selectbox('Filtrar pedidos',[
        'Aguardando produção','Todos os vendidos'
    ],key='rom_filtro')
    if filtro_rom=='Aguardando produção':
        elegiveis=elegiveis[elegiveis['_codigo'].isin(codigos_producao)].copy()
    if filtro_rom=='Aguardando produção':
        st.caption(f'{len(codigos_producao)} pedido(s) na carteira com status Aguardando produção. A lista considera apenas os que também constam como vendidos no Controle.')

    if elegiveis.empty:
        st.warning('Não há pedidos que atendam ao filtro selecionado. Confira a situação na carteira de produção e no Controle comercial.')
    else:
        elegiveis['_codigo']=elegiveis['orcamento'].map(lambda v: str(int(float(v))) if pd.notna(v) and str(v).strip() else '')
        elegiveis=elegiveis[elegiveis['_codigo'].ne('')].sort_values('orcamento',ascending=False)
        nomes_oficiais=elegiveis.get('cliente_controle',pd.Series('',index=elegiveis.index)).fillna('').astype(str).str.strip()
        nomes_excel=elegiveis.get('cliente_excel',pd.Series('',index=elegiveis.index)).fillna('').astype(str).str.strip()
        elegiveis['_cliente_busca']=nomes_oficiais.where(nomes_oficiais.ne(''),nomes_excel).replace('','Cliente não informado')
        busca=st.text_input('Buscar orçamento por número ou nome do cliente',placeholder='Digite o número ou o nome',key='rom_busca')
        encontrados=elegiveis
        if busca.strip():
            termo=busca.strip()
            encontrados=elegiveis[elegiveis['_codigo'].str.contains(re.escape(termo),case=False,na=False)|elegiveis['_cliente_busca'].str.contains(re.escape(termo),case=False,na=False)]
        codigos=encontrados['_codigo'].drop_duplicates().tolist()
        if not codigos:
            st.info('Nenhum orçamento vendido encontrado para esta busca.')
            st.stop()
        codigo=st.selectbox('Orçamento',codigos,format_func=lambda c: f'{c} — '+elegiveis.loc[elegiveis['_codigo'].eq(c),'_cliente_busca'].iloc[0],key='rom_codigo')
        registro=elegiveis[elegiveis['_codigo'].eq(codigo)].iloc[0]
        def texto_romaneio(v):
            return '' if pd.isna(v) or str(v).strip().lower() in ('nan','none') else str(v).strip()
        cliente=texto_romaneio(registro.get('cliente_controle')) or texto_romaneio(registro.get('cliente_excel')) or 'Cliente não informado'
        itens=sheet('BI_Orcamentos_Itens').copy()
        itens['_codigo']=itens['orcamento'].map(lambda v: str(int(float(v))) if pd.notna(v) and str(v).strip() else '')
        todos=itens[itens['_codigo'].eq(codigo)].copy()
        if todos.empty:
            st.error('Nenhum item foi encontrado para este orçamento. A emissão está bloqueada.')
        elif 'somar_no_total' not in todos.columns:
            st.error('Campo de seleção de itens ausente. A emissão está bloqueada.')
        else:
            flag=todos['somar_no_total'].fillna('').astype(str).str.strip().str.casefold()
            selecionados=todos[flag.eq('sim')].copy()
            if selecionados.empty:
                st.error('Nenhum item marcado como SIM. A emissão está bloqueada para evitar um romaneio incorreto.')
            else:
                colunas=['ambiente','descricao','material_original']
                st.subheader('Itens que serão impressos')
                show(selecionados,colunas,{'ambiente':'Ambiente','descricao':'Descrição técnica completa','material_original':'Material'},height=420)
                # O endereço só é importado quando a base publicada contém um campo explícito.
                campos_endereco=('endereco_entrega','endereco_cliente','endereco')
                endereco_base=next((texto_romaneio(registro.get(c)) for c in campos_endereco if texto_romaneio(registro.get(c))), '')
                # Montagem somente com campos efetivamente publicados (sem criar rua ou número).
                if not endereco_base:
                    partes=[]
                    for nomes in (('rua','logradouro'),('numero_endereco','numero'),('complemento','compl'),('bairro',),('cidade','municipio'),('uf','estado')):
                        v=next((texto_romaneio(registro.get(c)) for c in nomes if texto_romaneio(registro.get(c))), '')
                        if v:partes.append(v)
                    endereco_base=', '.join(partes)
                endereco=st.text_input('Endereço de entrega',value=endereco_base,key='rom_endereco_'+codigo)
                if not endereco.strip():st.warning('Sem endereço informado. Preencha o endereço de entrega, se disponível.')
                elif not any(c in registro.index and texto_romaneio(registro.get(c)) for c in ('endereco_entrega','endereco_cliente','endereco','rua','logradouro')):
                    st.info('A base pode conter apenas cidade ou outros dados parciais. Confira e complete o endereço antes da entrega.')
                observacoes=st.text_area('Observações para produção e entrega (opcional)',height=85,key='rom_obs')
                if True:
                    try:
                        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, KeepTogether, Image
                        from reportlab.lib import colors
                        from reportlab.lib.styles import ParagraphStyle
                        from reportlab.lib.enums import TA_CENTER, TA_LEFT
                        from reportlab.lib.pagesizes import A4
                        from reportlab.pdfbase import pdfmetrics
                        from reportlab.pdfbase.ttfonts import TTFont
                        import os
                        font='Helvetica'
                        for fonte in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',r'C:\Windows\Fonts\arial.ttf'):
                            if os.path.isfile(fonte):
                                pdfmetrics.registerFont(TTFont('GranArtRomaneio',fonte));font='GranArtRomaneio';break
                        def esc(v):return xml_escape(texto_romaneio(v)).replace('\n','<br/>')
                        normal=ParagraphStyle('rom_normal',fontName=font,fontSize=8.3,leading=12,textColor=colors.HexColor('#262626'))
                        pequeno=ParagraphStyle('rom_small',parent=normal,fontSize=7.5,leading=10.5)
                        rotulo=ParagraphStyle('rom_label',parent=pequeno,fontSize=7.8,leading=11,textColor=colors.white)
                        branco=ParagraphStyle('rom_white',parent=normal,textColor=colors.white)
                        branco_pequeno=ParagraphStyle('rom_white_small',parent=pequeno,textColor=colors.white)
                        def esc(v):return xml_escape(texto_romaneio(v)).replace('\n','<br/>')
                        buffer=BytesIO()
                        doc=SimpleDocTemplate(buffer,pagesize=A4,rightMargin=31,leftMargin=31,topMargin=31,bottomMargin=36,title='Romaneio GranArt - '+codigo)
                        story=[]
                        # Logo oficial do portal, adaptada para fundo preto sem alterar o arquivo original.
                        logo_path=ROOT/'logo_granart.png'
                        logo_element=None
                        if logo_path.is_file():
                            try:
                                from PIL import Image as PILImage
                                from io import BytesIO as IOBytes
                                im=PILImage.open(logo_path).convert('RGB')
                                import numpy as np
                                arr=np.asarray(im).copy()
                                # Original: fundo branco, letras escuras e detalhes dourados.
                                lum=arr.mean(axis=2)
                                gold=(arr[:,:,0]>130)&(arr[:,:,1]>110)&(arr[:,:,2]<195)&(arr[:,:,0]>arr[:,:,2]+12)
                                dark=(lum<155)&(~gold)
                                bg=(lum>220)&(~gold)
                                arr[bg]=[35,35,35]
                                arr[dark]=[245,243,237]
                                # Mantém a linha e a palavra Revestimentos em dourado.
                                im=PILImage.fromarray(arr)
                                logo_bytes=IOBytes();im.save(logo_bytes,format='PNG');logo_bytes.seek(0)
                                logo_element=Image(logo_bytes,width=182,height=62)
                            except Exception:logo_element=None
                        if logo_element is None:
                            logo_element=Paragraph('<font color="#d0b58a"><b>GRAN’ART</b></font><br/><font color="#d0b58a">Revestimentos</font>',ParagraphStyle('rom_logo_fallback',parent=normal,fontSize=17,leading=19))
                        header_title=Paragraph('<b>ROMANEIO DE<br/>PRODUÇÃO E ENTREGA</b>',ParagraphStyle('rom_header_title',parent=branco,fontSize=12,leading=17,alignment=TA_CENTER))
                        cab=Table([[logo_element,header_title]],colWidths=[222,311],rowHeights=[78])
                        cab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#232323')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(0,0),12),('RIGHTPADDING',(1,0),(1,0),12)]))
                        story.extend([cab,Spacer(1,10)])
                        # Cabeçalho uniforme, com rótulos pretos e texto alinhado.
                        meta=[[
                            Paragraph('<b>ORÇAMENTO</b>',rotulo),Paragraph('<b>'+esc(codigo)+'</b>',normal),
                            Paragraph('<b>CLIENTE</b>',rotulo),Paragraph('<b>'+esc(cliente).upper()+'</b>',normal)
                        ]]
                        if endereco.strip():
                            meta.append([Paragraph('<b>ENDEREÇO</b>',rotulo),Paragraph(esc(endereco),normal),'',''])
                        mt=Table(meta,colWidths=[82,75,68,308],hAlign='LEFT')
                        estilos=[('BOX',(0,0),(-1,-1),.6,colors.HexColor('#292929')),
                                 ('INNERGRID',(0,0),(-1,-1),.45,colors.HexColor('#b9b9b9')),
                                 ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#232323')),
                                 ('BACKGROUND',(2,0),(2,0),colors.HexColor('#232323')),
                                 ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                 ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]
                        if endereco.strip():estilos.append(('SPAN',(1,1),(3,1)))
                        mt.setStyle(TableStyle(estilos))
                        story.extend([mt,Spacer(1,12)])
                        linhas=[[Paragraph('<b>OK</b>',branco_pequeno),Paragraph('<b>AMBIENTE</b>',branco_pequeno),Paragraph('<b>DESCRIÇÃO TÉCNICA</b>',branco_pequeno),Paragraph('<b>MATERIAL</b>',branco_pequeno)]]
                        for _,item in selecionados.iterrows():
                            linhas.append([Paragraph('☐' if font!='Helvetica' else '[ ]',normal),Paragraph(esc(item.get('ambiente')),normal),Paragraph(esc(item.get('descricao')),normal),Paragraph(esc(item.get('material_original')),normal)])
                        tabela=Table(linhas,colWidths=[28,83,292,130],repeatRows=1,hAlign='LEFT')
                        tabela.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#252525')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b9b9b9')),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f6f3')])]))
                        story.append(tabela)
                        if observacoes.strip():story.extend([Spacer(1,13),Paragraph('<b>OBSERVAÇÕES:</b> '+esc(observacoes),normal)])
                        story.extend([Spacer(1,24),Paragraph('PRODUÇÃO: _____________________   EXPEDIÇÃO: _____________________',normal),Spacer(1,16),Paragraph('DATA DE ENTREGA: ____/____/______   RECEBIDO POR: _____________________',normal)])
                        def rodape(canvas,documento):
                            canvas.setFont(font,7);canvas.setFillColor(colors.HexColor('#777777'))
                            canvas.drawString(31,22,'GRAN’ART · Documento operacional sem informações financeiras')
                            canvas.drawRightString(A4[0]-31,22,f'Página {documento.page}')
                        doc.build(story,onFirstPage=rodape,onLaterPages=rodape)
                        st.download_button('Baixar romaneio em PDF',data=buffer.getvalue(),file_name=f'GranArt_Romaneio_{codigo}.pdf',mime='application/pdf',type='primary')
                    except ImportError:
                        st.error('A biblioteca reportlab não está instalada neste computador. No CMD, execute: python -m pip install reportlab')
                    except Exception as exc:
                        st.error(f'Não foi possível gerar o PDF: {exc}')

elif nav=='Produção':
    st.title('Produção e pedidos')
    summary=sheet('BI_Resumo_Producao');s=dict(zip(summary.situacao,summary.pedidos))
    cards([(k,num(s.get(k,0),0)) for k in ['Total em aberto','Aguardando liberação','Aguardando medição','Aguardando produção','Atrasados','Entregues no mês']])
    st.subheader('Situação dos pedidos')
    x=summary.copy();x['pedidos']=val(x,'pedidos').map(lambda z:num(z,0));x['m2_previsto']=val(x,'m2_previsto').map(lambda z:num(z,1));x['valor_venda']=val(x,'valor_venda').map(money)
    show(x,['situacao','pedidos','m2_previsto','valor_venda'],{'situacao':'Situação','pedidos':'Número de pedidos','m2_previsto':'Metragem prevista (m²)','valor_venda':'Valor da venda'},height=260)
    cart=sheet('BI_Carteira_Producao').copy();a,b=st.columns(2)
    with a:q=st.text_input('Buscar orçamento ou cliente')
    with b:status=st.selectbox('Situação',['Todas']+sorted(cart.status.dropna().astype(str).unique().tolist()))
    if q:cart=cart[cart.orcamento.astype(str).str.contains(re.escape(q),case=False,na=False)|cart.cliente.astype(str).str.contains(re.escape(q),case=False,na=False)]
    if status!='Todas':cart=cart[cart.status==status]
    cart['_prazo']=pd.to_numeric(cart.dias_prazo,errors='coerce');cart=cart.sort_values('_prazo',na_position='last')
    cart['m2_previsto']=val(cart,'m2_previsto').map(lambda z:num(z,1));cart['valor_venda']=val(cart,'valor_venda').map(money)
    st.subheader('Acompanhamento dos pedidos')
    table=cart[['orcamento','cliente','status','dias_prazo','m2_previsto','valor_venda','link_pdf']].rename(columns={'orcamento':'Orçamento','cliente':'Cliente','status':'Situação','dias_prazo':'Dias de prazo','m2_previsto':'Metragem prevista (m²)','valor_venda':'Valor da venda','link_pdf':'PDF'})
    def prazo_color(v):
        try:
            n=float(v)
            if pd.isna(n):return ''
            if n<0:return 'background-color:#f9d6d4;color:#7e2020'
            if n==0:return 'background-color:#fbe3c7;color:#8d4514'
            if n<=7:return 'background-color:#fff1c6;color:#755a14'
            if n<=15:return 'background-color:#eff1c7;color:#4e5e20'
            return 'background-color:#dff0dc;color:#235d3d'
        except:return ''
    styled=table.style.map(prazo_color,subset=['Dias de prazo'])
    st.dataframe(styled,hide_index=True,width='stretch',height=540,column_config={'PDF':st.column_config.LinkColumn('PDF',display_text='Abrir')})

elif nav=='Materiais e Estoque':
    st.title('Materiais e Estoque')
    stock=sheet('BI_Estoque_Materiais');a,b=st.columns(2)
    with a:
        scenarios=stock.cenario.dropna().astype(str).unique().tolist();scenario=st.selectbox('Estágio',['Todos os pedidos','Aguardando liberação','Aguardando medição','Aguardando produção'],index=0)
    with b:q=st.text_input('Buscar material',placeholder='Ex.: Granito Preto São Gabriel')
    material_filter=q.strip()
    st.subheader('Consulta de pedidos e materiais')
    items=sheet('BI_Detalhe_Materiais').copy()
    # Corte concluído é filtro de exclusão. Somente pedidos vendidos presentes na carteira produtiva.
    items=items[~items.status_corte.fillna('').astype(str).str.strip().str.casefold().isin(['concluído','concluido'])]
    items=items[~items.status_pedido.fillna('').astype(str).str.casefold().str.contains('instalação concluída|instalacao concluida',regex=True)]
    if scenario!='Todos os pedidos':items=items[items.status_pedido.astype(str).str.strip()==scenario]
    if material_filter:items=items[items.material.fillna('').astype(str).str.contains(re.escape(material_filter),case=False,na=False)]
    query=st.text_input('Buscar orçamento ou cliente',key='material_order_query')
    if query:items=items[items.orcamento.astype(str).str.contains(re.escape(query),case=False,na=False)|items.cliente.astype(str).str.contains(re.escape(query),case=False,na=False)]
    items=items.sort_values('orcamento',ascending=False)
    materiais_pedidos=set(items.loc[pd.to_numeric(items['m2_pendente'],errors='coerce').fillna(0)>0,'material'].dropna().astype(str).str.strip().str.casefold())
    for k in ['m2_previsto','m2_realizado','m2_pendente']:items[k]=val(items,k).map(lambda z:num(z,1))
    show(items,['orcamento','cliente','material','status_pedido','m2_previsto','m2_realizado','m2_pendente'],{'orcamento':'Orçamento','cliente':'Cliente','material':'Material','status_pedido':'Situação do pedido','m2_previsto':'Previsto (m²)','m2_realizado':'Realizado (m²)','m2_pendente':'Pendente (m²)'},height=440)
    st.subheader('Planejamento de compras')
    f=stock[stock.cenario==scenario].copy()
    f=f[pd.to_numeric(f['demanda_pendente_m2'],errors='coerce').fillna(0)>0]
    f=f[f.material.fillna('').astype(str).str.strip().str.casefold().isin(materiais_pedidos)]
    if material_filter:f=f[f.material.astype(str).str.contains(re.escape(material_filter),case=False,na=False)]
    cards([('Demanda pendente',num(val(f,'demanda_pendente_m2').sum(),1)+' m²'),('Necessidade de compra',num(val(f,'necessidade_teorica_m2').sum(),1)+' m²')])
    if f.empty:st.info('Não há demanda pendente de materiais para os filtros selecionados.')
    for k in ['demanda_pendente_m2','estoque_material_m2','necessidade_teorica_m2','saldo_material_m2']:f[k]=val(f,k).map(lambda z:num(z,1))
    show(f,['material','demanda_pendente_m2','estoque_material_m2','necessidade_teorica_m2','saldo_material_m2'],{'material':'Material','demanda_pendente_m2':'Demanda pendente (m²)','estoque_material_m2':'Estoque de material (m²)','necessidade_teorica_m2':'Necessidade de compra (m²)','saldo_material_m2':'Saldo de material (m²)'},height=470)
