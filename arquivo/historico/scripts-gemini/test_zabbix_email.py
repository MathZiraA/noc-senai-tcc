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

media_types = api_request("mediatype.get", {"filter": {"name": ["Gmail Alertas SENAI"]}}, auth_token)

if not media_types:
    print("[-] Tipo de mídia 'Gmail Alertas SENAI' não encontrado.")
    sys.exit(1)

mediatype_id = media_types[0]['mediatypeid']

print("[+] Enviando e-mail de teste...")
test_res = api_request("mediatype.test", {
    "mediatypeid": mediatype_id,
    "sendto": "matheus.ziravello@gmail.com",
    "subject": "TESTE NOC SENAI - Validação de Notificação Zabbix",
    "message": "Olá Matheus,\n\nEste é um e-mail de teste para confirmar que o Zabbix Server está configurado e pronto para enviar alertas de redundância dos links de Fibra e Rádio.\n\nAtenciosamente,\nEquipe NOC SENAI"
}, auth_token)

if test_res and test_res.get("result"):
    print("\n[✔] E-mail enviado com sucesso pelo servidor Zabbix!")
else:
    print("\n[-] Resultado do teste:", test_res)
