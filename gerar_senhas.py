import getpass, hashlib, secrets
print("Gerador local de senhas - Gran'Art")
print("Nao compartilhe as senhas nem as credenciais.")
print("[usuarios]")
for nome in ("administrador","socio1","socio2"):
    while True:
        s=getpass.getpass(f"Senha para {nome} (minimo 12 caracteres): ")
        c=getpass.getpass("Repita: ")
        if s==c and len(s)>=12: break
        print("Senhas diferentes ou curtas.")
    sal=secrets.token_bytes(16)
    h=hashlib.pbkdf2_hmac("sha256",s.encode(),sal,600000)
    print(f'{nome} = "pbkdf2_sha256${sal.hex()}${h.hex()}"')
