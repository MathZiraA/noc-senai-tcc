"""Confere o Grafana: saúde da fonte de dados Zabbix e se cada painel do NOC devolve dados."""
import base64
import json
import urllib.error
import urllib.request

import ssl

URL = "https://localhost:3000"
TLS = ssl.create_default_context(cafile="/root/noc-ca/ca.crt")
SENHA = open("/etc/grafana/admin_password").read().strip()
AUTH = "Basic " + base64.b64encode(f"admin:{SENHA}".encode()).decode()


def api(caminho, corpo=None):
    req = urllib.request.Request(URL + caminho,
                                 data=json.dumps(corpo).encode() if corpo else None,
                                 headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=TLS) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


print("fonte de dados:", api("/api/datasources/uid/zabbix-noc/health"))
print("plugin habilitado:", api("/api/plugins/alexanderzobnin-zabbix-app/settings")[1].get("enabled"))
print("página inicial:", api("/api/dashboards/home")[1].get("dashboard", {}).get("title"))
painel_json = json.load(open("/var/lib/grafana/dashboards/noc-redundancia.json"))
for p in painel_json["panels"]:
    corpo = {"queries": [dict(t, intervalMs=10000, maxDataPoints=200) for t in p["targets"]],
             "from": "now-1h", "to": "now"}
    status, r = api("/api/ds/query", corpo)
    if status != 200:
        print(f"PAINEL {p['title'][:45]} -> HTTP {status} {r}")
        continue
    partes = []
    for ref, v in r["results"].items():
        frames = v.get("frames", [])
        pontos = sum(len(f["data"]["values"][0]) for f in frames if f.get("data", {}).get("values"))
        erro = f" ERRO {v['error'][:100]}" if v.get("error") else ""
        partes.append(f"{ref}: {len(frames)} séries/{pontos} pontos{erro}")
    print(f"PAINEL {p['title'][:45]} -> {', '.join(partes)}")
