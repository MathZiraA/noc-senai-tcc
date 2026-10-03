import urllib.request
import json
import sys

URLS = [
    "http://localhost/zabbix/api_jsonrpc.php",
    "http://127.0.0.1/zabbix/api_jsonrpc.php",
    "http://localhost/api_jsonrpc.php"
]

def test_api_endpoint(url):
    payload = {"jsonrpc": "2.0", "method": "apiinfo.version", "params": [], "id": 1}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json-rpc'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return True, res.get('result', 'OK')
    except Exception as e:
        return False, str(e)

print("[1] Testando endpoints da API do Zabbix...")
valid_url = None
for url in URLS:
    ok, detail = test_api_endpoint(url)
    if ok:
        print(f"  [✔] Conectado em: {url} (Versão API: {detail})")
        valid_url = url
        break
    else:
        print(f"  [-] Inacessível em {url}: {detail}")

if not valid_url:
    print("\n[-] Nenhuma URL respondeu. Verifique se o Apache/Nginx está rodando: 'systemctl status apache2'")
    sys.exit(1)

def api_request(url, method, params, auth=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "auth": auth, "id": 1}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json-rpc'})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res = json.loads(response.read().decode('utf-8'))
            if 'error' in res:
                print(f"[-] Erro na API [{method}]: {res['error']['message']} - {res['error'].get('data','')}")
                return None
            return res.get('result')
    except Exception as e:
        print(f"[-] Erro HTTP/Conexão: {e}")
        return None

print("\n[2] Testando Autenticação...")
auth_token = api_request(valid_url, "user.login", {"username": "Admin", "password": "zabbix"})
if not auth_token:
    auth_token = api_request(valid_url, "user.login", {"user": "Admin", "password": "zabbix"})

if not auth_token:
    print("\n[-] Falha de autenticação. Se a senha do 'Admin' foi alterada na Web, informe a nova senha.")
    sys.exit(1)

print("  [✔] Autenticado com sucesso!")

print("\n[3] Enviando E-mail de Teste...")
media_types = api_request(valid_url, "mediatype.get", {"filter": {"name": ["Gmail Alertas SENAI"]}}, auth_token)

if not media_types:
    print("[-] Tipo de mídia 'Gmail Alertas SENAI' não encontrado. Recrie a mídia de e-mail.")
    sys.exit(1)

mediatype_id = media_types[0]['mediatypeid']

test_res = api_request(valid_url, "mediatype.test", {
    "mediatypeid": mediatype_id,
    "sendto": "matheus.ziravello@gmail.com",
    "subject": "TESTE NOC SENAI - Validação de Notificação Zabbix",
    "message": "Olá Matheus,\n\nEste é um e-mail de teste para confirmar que o Zabbix Server está configurado e pronto para enviar alertas de redundância dos links de Fibra e Rádio.\n\nAtenciosamente,\nEquipe NOC SENAI"
}, auth_token)

if test_res and test_res.get("result"):
    print("\n========================================================")
    print(" [✔] E-MAIL ENVIADO COM SUCESSO PELO SERVIDO ZABBIX!")
    print("========================================================")
else:
    print("\n[-] Falha no disparo do e-mail de teste.")
