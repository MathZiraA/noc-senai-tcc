"""Cliente mínimo da API do Zabbix — lê o token de /root/.zabbix_token."""
import json
import urllib.request
from pathlib import Path

URL = "http://localhost/zabbix/api_jsonrpc.php"
TOKEN = Path("/root/.zabbix_token").read_text().strip()
# Usuário próprio do Analista IA: o Zabbix não notifica o autor de um comentário sobre o próprio comentário
TOKEN_ANALISTA = Path("/root/.zabbix_token_analista")


class ZbxError(Exception):
    pass


def call(method, params, token=None):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json-rpc",
        "Authorization": f"Bearer {token or TOKEN}",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        res = json.loads(r.read())
    if "error" in res:
        raise ZbxError(f"{method}: {res['error']['message']} {res['error'].get('data', '')}")
    return res["result"]
