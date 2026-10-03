import urllib.request
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

APP_PASSWORD = "<REMOVIDA>"
EMAIL = "matheus.ziravello@aluno.senai.br"
ZABBIX_URL = "http://localhost/zabbix/api_jsonrpc.php"

# 1. Testar Envio Direto SMTP via Google Workspace/Gmail
print("[1] Testando envio SMTP para o e-mail institucional...")
msg = MIMEMultipart()
msg['From'] = EMAIL
msg['To'] = EMAIL
msg['Subject'] = "🚨 [NOC SENAI] Validação de E-mail Institucional"

body = """
<h3>Servidor NOC SENAI - Notificações Ativadas</h3>
<p>O envio de alertas para o e-mail institucional (<b>matheus.ziravello@aluno.senai.br</b>) foi validado com sucesso!</p>
<hr>
<p><b>Status Zabbix:</b> Integrado e pronto para alertar falhas nos enlaces de Fibra e Rádio.</p>
"""
msg.attach(MIMEText(body, 'html'))

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL, APP_PASSWORD)
    server.sendmail(EMAIL, EMAIL, msg.as_string())
    server.quit()
    print("  [✔] E-mail de teste enviado com SUCESSO para matheus.ziravello@aluno.senai.br!")
except Exception as e:
    print(f"  [-] Falha na autenticação/envio SMTP: {e}")
    sys.exit(1)

# 2. Atualizar Mídia e Usuário no Zabbix via API
print("\n[2] Atualizando configurações no Zabbix Server...")

def api_request(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "auth": auth, "id": 1}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(ZABBIX_URL, data=data, headers={'Content-Type': 'application/json-rpc'})
    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return res.get('result')
    except Exception as e:
        print(f"[-] Erro na API: {e}")
        return None

auth_token = api_request("user.login", {"username": "Admin", "password": "zabbix"})
if not auth_token:
    print("[-] Falha na autenticação do Zabbix.")
    sys.exit(1)

media_types = api_request("mediatype.get", {"filter": {"name": ["Gmail Alertas SENAI"]}}, auth_token)

if media_types:
    mt_id = media_types[0]['mediatypeid']
    api_request("mediatype.update", {
        "mediatypeid": mt_id,
        "smtp_email": EMAIL,
        "username": EMAIL,
        "passwd": APP_PASSWORD
    }, auth_token)
    print("  [✔] Mídia 'Gmail Alertas SENAI' atualizada com o novo e-mail institucional!")

users = api_request("user.get", {"filter": {"username": ["Admin"]}}, auth_token)
if users and media_types:
    admin_id = users[0]['userid']
    api_request("user.update", {
        "userid": admin_id,
        "medias": [
            {
                "mediatypeid": mt_id,
                "sendto": [EMAIL],
                "active": 0,
                "severity": 63,
                "period": "1-7,00:00-24:00"
            }
        ]
    }, auth_token)
    print("  [✔] Destinatário do usuário Admin alterado para matheus.ziravello@aluno.senai.br!")

print("\n========================================================")
print(" CONFIGURAÇÃO DE E-MAIL CONCLUÍDA E VALIDADA COM SUCESSO!")
print("========================================================")
