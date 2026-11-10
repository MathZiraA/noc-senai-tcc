import urllib.request
import json
import sys

ZABBIX_URL = "http://localhost/zabbix/api_jsonrpc.php"

def api_request(method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "auth": auth, "id": 1}
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
        print(f"[-] Erro de Conexão: {e}")
        return None

print("[+] Conectando à API do Zabbix...")
auth_token = api_request("user.login", {"username": "Admin", "password": "zabbix"})

if not auth_token:
    print("[-] Falha na autenticação.")
    sys.exit(1)

# 1. Remover dashboards antigos com erros de ID
old_dashboards = api_request("dashboard.get", {"output": ["dashboardid", "name"]}, auth_token)
if old_dashboards:
    for dash in old_dashboards:
        if "NOC" in dash['name'] or "Redundância" in dash['name']:
            api_request("dashboard.delete", [dash['dashboardid']], auth_token)
            print(f"[+] Dashboard antigo removido: {dash['name']}")

# 2. Obter ID do Grupo de Equipamentos SENAI
groups = api_request("hostgroup.get", {"filter": {"name": ["Rede SENAI - Equipamentos"]}}, auth_token)
group_id = groups[0]['groupid'] if groups else None

dash_fields = []
if group_id:
    dash_fields = [{"type": 2, "name": "groupids.0", "value": group_id}]

# 3. Criar Dashboard NOC Oficial Ajustado
new_dashboard = {
    "name": "NOC - Monitoramento de Redundância (OFICIAL)",
    "display_period": 30,
    "auto_start": 1,
    "pages": [
        {
            "name": "Visão Geral dos Enlaces",
            "widgets": [
                {
                    "type": "hostavail",
                    "name": "DISPONIBILIDADE DOS ROTEADORES E ENLACES",
                    "x": 0, "y": 0, "width": 12, "height": 3,
                    "fields": dash_fields
                },
                {
                    "type": "problems",
                    "name": "ALERTAS EM TEMPO REAL (QUEDAS / FAILOVER DE LINK)",
                    "x": 0, "y": 3, "width": 12, "height": 5,
                    "fields": dash_fields
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

res = api_request("dashboard.create", new_dashboard, auth_token)
if res:
    print("\n[✔] Novo Dashboard NOC Oficial criado com sucesso!")
