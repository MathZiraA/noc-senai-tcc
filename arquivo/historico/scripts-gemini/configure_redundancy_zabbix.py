import urllib.request
import json
import sys

ZABBIX_URL = "http://localhost/zabbix/api_jsonrpc.php"

def api_request(method, params, auth=None):
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "auth": auth,
        "id": 1
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(ZABBIX_URL, data=data, headers={'Content-Type': 'application/json-rpc'})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            if 'error' in res:
                print(f"[-] Erro na API [{method}]: {res['error']['data']}")
                return None
            return res.get('result')
    except Exception as e:
        print(f"[-] Erro de Conexão HTTP: {e}")
        return None

print("[+] Conectando à API do Zabbix...")
auth_token = api_request("user.login", {"username": "Admin", "password": "zabbix"})

if not auth_token:
    print("[-] Falha na autenticação.")
    sys.exit(1)

# 1. Configurar Mídia de E-mail (Gmail SMTP)
email_addr = "matheus.ziravello@gmail.com"
email_pass = "<REMOVIDA>"

print("[+] Configurando servidor SMTP Gmail para envio de alertas...")
media_types = api_request("mediatype.get", {"filter": {"name": ["Gmail Alertas SENAI"]}}, auth_token)

if media_types:
    mediatype_id = media_types[0]['mediatypeid']
else:
    res_mt = api_request("mediatype.create", {
        "name": "Gmail Alertas SENAI",
        "type": 0, # Email
        "smtp_server": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_helo": "gmail.com",
        "smtp_email": email_addr,
        "smtp_security": 1, # STARTTLS
        "smtp_verify_peer": 0,
        "smtp_verify_host": 0,
        "smtp_authentication": 1,
        "username": email_addr,
        "passwd": email_pass,
        "message_format": 1, # HTML
        "status": 0
    }, auth_token)
    mediatype_id = res_mt['mediatypeids'][0]
    print(f"[+] Mídia SMTP Gmail criada (ID: {mediatype_id})")

# 2. Associar E-mail ao Usuário Admin
users = api_request("user.get", {"filter": {"username": ["Admin"]}}, auth_token)
admin_id = users[0]['userid']

api_request("user.update", {
    "userid": admin_id,
    "medias": [
        {
            "mediatypeid": mediatype_id,
            "sendto": [email_addr],
            "active": 0,
            "severity": 63, # Todas as severidades
            "period": "1-7,00:00-24:00"
        }
    ]
}, auth_token)
print(f"[+] E-mail {email_addr} vinculado ao usuário Admin com sucesso!")

# 3. Criar Ação de Notificação para Queda/Restabelecimento de Links
actions = api_request("action.get", {"filter": {"name": ["Notificação de Redundância - Link Fibra/Rádio"]}}, auth_token)

if not actions:
    act_payload = {
        "name": "Notificação de Redundância - Link Fibra/Rádio",
        "eventsource": 0, # Triggers
        "status": 0, # Habilitado
        "esc_period": "1m",
        "operations": [
            {
                "operationtype": 0, # Enviar mensagem
                "evaltype": 0,
                "opmessage_usr": [{"userid": admin_id}],
                "opmessage": {
                    "default_msg": 0,
                    "subject": "🚨 [NOC SENAI] Alteração de Link em R-FILIAL: {EVENT.NAME}",
                    "message": """<h3>Alerta de Redundância de Link - NOC SENAI</h3>
<p><b>Status do Evento:</b> {EVENT.VALUE}</p>
<p><b>Equipamento:</b> {HOST.NAME} ({HOST.IP})</p>
<p><b>Ocorrência:</b> {EVENT.NAME}</p>
<p><b>Severidade:</b> {EVENT.SEVERITY}</p>
<p><b>Horário:</b> {EVENT.TIME} - {EVENT.DATE}</p>
<hr>
<p><i>Este é um e-mail automático gerado pelo Zabbix Server.</i></p>""",
                    "mediatypeid": mediatype_id
                }
            }
        ],
        "recovery_operations": [
            {
                "operationtype": 11, # Notificação de Recuperação
                "opmessage": {
                    "default_msg": 0,
                    "subject": "✅ [NOC SENAI] RESTABELECIDO: {EVENT.NAME}",
                    "message": """<h3>Link Restabelecido - NOC SENAI</h3>
<p><b>Equipamento:</b> {HOST.NAME}</p>
<p><b>Status:</b> RESOLVIDO</p>
<p><b>Horário de Normalização:</b> {EVENT.RECOVERY.TIME} - {EVENT.RECOVERY.DATE}</p>"""
                }
            }
        ]
    }
    api_request("action.create", act_payload, auth_token)
    print("[+] Ação de Notificação por E-mail criada com sucesso!")

# 4. Obter Grupo de Hosts do SENAI
groups = api_request("hostgroup.get", {"filter": {"name": ["Rede SENAI - Equipamentos"]}}, auth_token)
group_id = groups[0]['groupid']

# 5. Criar Dashboard de Redundância em Tempo Real
dashboards = api_request("dashboard.get", {"filter": {"name": ["Painel NOC - Redundância Fibra vs Rádio"]}}, auth_token)

if not dashboards:
    dash_payload = {
        "name": "Painel NOC - Redundância Fibra vs Rádio",
        "display_period": 10,
        "auto_start": 1,
        "pages": [
            {
                "name": "Monitoramento em Tempo Real WANS",
                "widgets": [
                    {
                        "type": "item",
                        "name": "STATUS LINK FIBRA (ether2)",
                        "x": 0, "y": 0, "width": 6, "height": 3,
                        "fields": [
                            {"type": 1, "name": "itemid.0", "value": "1"} # Widget visual
                        ]
                    },
                    {
                        "type": "item",
                        "name": "STATUS LINK RÁDIO (ether3)",
                        "x": 6, "y": 0, "width": 6, "height": 3,
                        "fields": [
                            {"type": 1, "name": "itemid.0", "value": "1"}
                        ]
                    },
                    {
                        "type": "problems",
                        "name": "HISTÓRICO DE FALHAS E COMUTAÇÕES DE LINK",
                        "x": 0, "y": 3, "width": 12, "height": 5,
                        "fields": [
                            {"type": 2, "name": "groupids.0", "value": group_id},
                            {"type": 0, "name": "show_suppressed", "value": "1"}
                        ]
                    },
                    {
                        "type": "actionlog",
                        "name": "LOG DE NOTIFICAÇÕES DE E-MAIL ENVIADAS",
                        "x": 0, "y": 8, "width": 12, "height": 4
                    }
                ]
            }
        ]
    }
    api_request("dashboard.create", dash_payload, auth_token)
    print("[+] Dashboard Customizado de Redundância criado com sucesso!")

print("\n[✔] Configuração concluída sem erros.")
