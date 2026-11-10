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

print("[+] Conectando à API do Zabbix para Pré-Configuração...")
auth_token = api_request("user.login", {"username": "Admin", "password": "zabbix"})

if not auth_token:
    print("[-] Falha na autenticação.")
    sys.exit(1)

# 1. Configurar Mídia de E-mail (Gmail SMTP)
email_addr = "matheus.ziravello@gmail.com"
email_pass = "<REMOVIDA>"

print("[+] Pré-configurando Gateway SMTP Gmail...")
media_types = api_request("mediatype.get", {"filter": {"name": ["Gmail Alertas SENAI"]}}, auth_token)

if media_types:
    mediatype_id = media_types[0]['mediatypeid']
else:
    res_mt = api_request("mediatype.create", {
        "name": "Gmail Alertas SENAI",
        "type": 0,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_helo": "gmail.com",
        "smtp_email": email_addr,
        "smtp_security": 1,
        "smtp_verify_peer": 0,
        "smtp_verify_host": 0,
        "smtp_authentication": 1,
        "username": email_addr,
        "passwd": email_pass,
        "message_format": 1,
        "status": 0
    }, auth_token)
    mediatype_id = res_mt['mediatypeids'][0]

# 2. Vincular E-mail de Destino ao Usuário Admin
users = api_request("user.get", {"filter": {"username": ["Admin"]}}, auth_token)
admin_id = users[0]['userid']

api_request("user.update", {
    "userid": admin_id,
    "medias": [
        {
            "mediatypeid": mediatype_id,
            "sendto": [email_addr],
            "active": 0,
            "severity": 63,
            "period": "1-7,00:00-24:00"
        }
    ]
}, auth_token)
print(f"[+] Destinatário {email_addr} vinculado com sucesso!")

# 3. Obter Grupo do SENAI
groups = api_request("hostgroup.get", {"filter": {"name": ["Rede SENAI - Equipamentos"]}}, auth_token)
if not groups:
    print("[-] Grupo de Hosts não encontrado. Execute a etapa anterior primeiro.")
    sys.exit(1)
group_id = groups[0]['groupid']

# 4. Criar Ação de Alerta Global para o Grupo de Equipamentos
actions = api_request("action.get", {"filter": {"name": ["Notificação NOC - Redundância e Enlaces"]}}, auth_token)

if not actions:
    act_payload = {
        "name": "Notificação NOC - Redundância e Enlaces",
        "eventsource": 0,
        "status": 0,
        "filter": {
            "evaltype": 0,
            "conditions": [
                {
                    "conditiontype": 0, # Host Group
                    "operator": 0,
                    "value": group_id
                }
            ]
        },
        "operations": [
            {
                "operationtype": 0,
                "opmessage_usr": [{"userid": admin_id}],
                "opmessage": {
                    "default_msg": 0,
                    "subject": "🚨 [ALERTA NOC SENAI] Falha / Mudança de Link em {HOST.NAME}",
                    "message": """<h2>Alerta de Conectividade - NOC SENAI</h2>
<p><b>Equipamento:</b> {HOST.NAME} ({HOST.IP})</p>
<p><b>Evento Identificado:</b> {EVENT.NAME}</p>
<p><b>Severidade:</b> {EVENT.SEVERITY}</p>
<p><b>Data/Hora do Disparo:</b> {EVENT.DATE} às {EVENT.TIME}</p>
<hr>
<p><i>Este é um disparo automático predeterminado do Zabbix Server.</i></p>""",
                    "mediatypeid": mediatype_id
                }
            }
        ],
        "recovery_operations": [
            {
                "operationtype": 11,
                "opmessage": {
                    "default_msg": 0,
                    "subject": "✅ [NORMALIZADO NOC SENAI] Restabelecimento em {HOST.NAME}",
                    "message": """<h2>Enlace Restabelecido - NOC SENAI</h2>
<p><b>Equipamento:</b> {HOST.NAME}</p>
<p><b>Evento Resolvido:</b> {EVENT.NAME}</p>
<p><b>Horário da Normalização:</b> {EVENT.RECOVERY.DATE} às {EVENT.RECOVERY.TIME}</p>"""
                }
            }
        ]
    }
    api_request("action.create", act_payload, auth_token)
    print("[+] Regras de disparo de e-mail atreladas ao grupo de hosts com sucesso!")

# 5. Criar Dashboard Dinâmico (Sem IDs fixos de Itens)
dashboards = api_request("dashboard.get", {"filter": {"name": ["NOC - Monitoramento Dinâmico de Redundância"]}}, auth_token)

if not dashboards:
    dash_payload = {
        "name": "NOC - Monitoramento Dinâmico de Redundância",
        "display_period": 10,
        "auto_start": 1,
        "pages": [
            {
                "name": "Painel Principal de Links",
                "widgets": [
                    {
                        "type": "hostavail",
                        "name": "STATUS DOS ROTEADORES E ENLACES",
                        "x": 0, "y": 0, "width": 12, "height": 3,
                        "fields": [
                            {"type": 2, "name": "groupids.0", "value": group_id}
                        ]
                    },
                    {
                        "type": "problems",
                        "name": "ALERTAS EM TEMPO REAL (QUEDAS DE LINK / FAILOVER)",
                        "x": 0, "y": 3, "width": 12, "height": 5,
                        "fields": [
                            {"type": 2, "name": "groupids.0", "value": group_id}
                        ]
                    },
                    {
                        "type": "actionlog",
                        "name": "HISTÓRICO DE NOTIFICAÇÕES ENVIADAS POR E-MAIL",
                        "x": 0, "y": 8, "width": 12, "height": 4
                    }
                ]
            }
        ]
    }
    api_request("dashboard.create", dash_payload, auth_token)
    print("[+] Dashboard NOC Dinâmico criado com sucesso!")

print("\n========================================================")
print(" PRÉ-CONFIGURAÇÃO CONCLUÍDA! O ZABBIX ESTÁ PRONTO.")
print("========================================================")
