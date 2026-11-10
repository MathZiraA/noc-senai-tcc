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
    print("[-] Falha ao autenticar. Verifique se o Zabbix está rodando e a senha padrão é 'zabbix'.")
    sys.exit(1)

print("[+] Autenticado com sucesso!")

# 1. Obter ou Criar Grupo de Hosts
group_name = "Rede SENAI - Equipamentos"
groups = api_request("hostgroup.get", {"filter": {"name": [group_name]}}, auth_token)

if groups:
    group_id = groups[0]['groupid']
    print(f"[+] Grupo '{group_name}' já existe (ID: {group_id}).")
else:
    res_group = api_request("hostgroup.create", {"name": group_name}, auth_token)
    group_id = res_group['groupids'][0]
    print(f"[+] Grupo '{group_name}' criado com sucesso (ID: {group_id}).")

# 2. Localizar IDs dos Templates Padrão
templates_target = ["MikroTik RouterOS by SNMP", "ICMP Ping"]
templates = api_request("template.get", {"filter": {"host": templates_target}}, auth_token)

template_ids = [{"templateid": t['templateid']} for t in templates]
print(f"[+] Templates vinculados: {[t['host'] for t in templates]}")

# 3. Criar ou Atualizar Host R-FILIAL
host_name = "R-FILIAL"
existing_hosts = api_request("host.get", {"filter": {"host": [host_name]}}, auth_token)

if existing_hosts:
    host_id = existing_hosts[0]['hostid']
    print(f"[+] Host '{host_name}' já cadastrado (ID: {host_id}).")
else:
    host_payload = {
        "host": host_name,
        "name": "R-FILIAL (RouterOS Filial SENAI)",
        "interfaces": [
            {
                "type": 2, # SNMP
                "main": 1,
                "useip": 1,
                "ip": "10.0.1.2", # IP da WAN Fibra da Filial conforme a topologia
                "dns": "",
                "port": "161",
                "details": {
                    "version": 2,
                    "bulk": 1,
                    "community": "{$SNMP_COMMUNITY}"
                }
            }
        ],
        "groups": [{"groupid": group_id}],
        "templates": template_ids,
        "macros": [
            {
                "macro": "{$SNMP_COMMUNITY}",
                "value": "public_senai"
            }
        ]
    }
    res_host = api_request("host.create", host_payload, auth_token)
    if res_host:
        host_id = res_host['hostids'][0]
        print(f"[+] Host '{host_name}' cadastrado com sucesso (ID: {host_id})!")

# 4. Criar Dashboard NOC Profissional
dashboards = api_request("dashboard.get", {"filter": {"name": ["NOC - Monitoramento Filial SENAI"]}}, auth_token)

if not dashboards:
    dash_payload = {
        "name": "NOC - Monitoramento Filial SENAI",
        "display_period": 30,
        "auto_start": 1,
        "pages": [
            {
                "name": "Visão Geral R-FILIAL",
                "widgets": [
                    {
                        "type": "hostavail",
                        "name": "Status de Disponibilidade (SNMP/ICMP)",
                        "x": 0, "y": 0, "width": 8, "height": 4,
                        "fields": [
                            {"type": 2, "name": "groupids.0", "value": group_id}
                        ]
                    },
                    {
                        "type": "clock",
                        "name": "Horário do Sistema NOC",
                        "x": 8, "y": 0, "width": 4, "height": 4
                    },
                    {
                        "type": "problems",
                        "name": "Central de Alertas e Incidentes",
                        "x": 0, "y": 4, "width": 12, "height": 6,
                        "fields": [
                            {"type": 2, "name": "groupids.0", "value": group_id}
                        ]
                    }
                ]
            }
        ]
    }
    res_dash = api_request("dashboard.create", dash_payload, auth_token)
    if res_dash:
        print("[+] Dashboard NOC criado com sucesso!")
else:
    print("[+] Dashboard NOC já existente.")

print("\n========================================================")
print(" CONFIGURAÇÃO CONCLUÍDA COM SUCESSO!")
print("========================================================")
