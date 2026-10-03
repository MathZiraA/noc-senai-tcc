"""Configura o Grafana do NOC por provisionamento (idempotente). Rodar como root na VM.

- Usuário só leitura "grafana-leitura" no Zabbix, com token gravado direto no arquivo da fonte de dados
- Plugin Zabbix habilitado + fonte de dados "Zabbix NOC" (uid zabbix-noc)
- Dashboard "NOC - Redundância Fibra x Rádio" como página inicial
- Acesso de visitante somente leitura (TV do NOC) e senha de admin aleatória em /root/.grafana_admin
"""
import json
import os
import pwd
import secrets
from pathlib import Path

from zbx import call

GRUPO = "Rede SENAI - Equipamentos"
GRUPO_USUARIOS = "NOC Automação"
USUARIO = "grafana-leitura"
HOST = "R-FILIAL"  # o plugin filtra pelo nome visível ("R-FILIAL (RouterOS ...)"), por isso vira regex
DS ={"type": "alexanderzobnin-zabbix-datasource", "uid": "zabbix-noc"}
PROV = Path("/etc/grafana/provisioning")
DIR_DASH = Path("/var/lib/grafana/dashboards")
ARQ_DASH = DIR_DASH / "noc-redundancia.json"
SENHA_ADMIN = Path("/etc/grafana/admin_password")
GRAFANA_GID = pwd.getpwnam("grafana").pw_gid


def gravar(caminho, conteudo, modo=0o644, grupo_grafana=False):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo)
    os.chmod(caminho, modo)
    if grupo_grafana:
        os.chown(caminho, 0, GRAFANA_GID)


# 1. Usuário de leitura no Zabbix + token (nunca impresso)
ugid = call("usergroup.get", {"filter": {"name": [GRUPO_USUARIOS]}, "output": ["usrgrpid"]})[0]["usrgrpid"]
u = call("user.get", {"filter": {"username": [USUARIO]}, "output": ["userid"]})
uid = u[0]["userid"] if u else call("user.create", {
    "username": USUARIO, "name": "Grafana (somente leitura)", "roleid": "1",
    "passwd": secrets.token_urlsafe(32), "usrgrps": [{"usrgrpid": ugid}]})["userids"][0]
arq_ds = PROV / "datasources" / "zabbix.yaml"
if not arq_ds.exists():
    for t in call("token.get", {"userids": [uid], "filter": {"name": ["grafana"]}, "output": ["tokenid"]}):
        call("token.delete", [t["tokenid"]])
    tid = call("token.create", {"name": "grafana", "userid": uid})["tokenids"][0]
    token = call("token.generate", [tid])[0]["token"]
    gravar(arq_ds, f"""apiVersion: 1
datasources:
  - name: Zabbix NOC
    type: {DS['type']}
    uid: {DS['uid']}
    access: proxy
    url: http://localhost/zabbix/api_jsonrpc.php
    isDefault: true
    editable: false
    jsonData:
      authType: token
      trends: true
      trendsFrom: 7d
      trendsRange: 4d
      cacheTTL: 30s
    secureJsonData:
      apiToken: {token}
""", 0o640, grupo_grafana=True)
print(f"[ok] usuário '{USUARIO}' e fonte de dados Zabbix NOC")

# 2. Plugin habilitado + provedor de dashboards
gravar(PROV / "plugins" / "zabbix.yaml",
       "apiVersion: 1\napps:\n  - type: alexanderzobnin-zabbix-app\n    org_id: 1\n    disabled: false\n")
gravar(PROV / "dashboards" / "noc.yaml", f"""apiVersion: 1
providers:
  - name: NOC
    folder: NOC SENAI
    type: file
    allowUiUpdates: false
    options:
      path: {DIR_DASH}
""")


# 3. Dashboard
def alvo(ref, item_regex):
    return {"refId": ref, "datasource": DS, "queryType": "0", "group": {"filter": GRUPO},
            "host": {"filter": f"/^{HOST}/"}, "itemTag": {"filter": ""}, "item": {"filter": item_regex},
            "functions": [], "options": {"showDisabledItems": False}}


def nome(padrao, texto):
    return {"matcher": {"id": "byRegexp", "options": padrao},
            "properties": [{"id": "displayName", "value": texto}]}


UP_DOWN = [{"type": "range", "options": {"from": 0.5, "to": 1.5, "result": {"text": "UP", "color": "green", "index": 0}}},
           {"type": "range", "options": {"from": -0.5, "to": 0.5, "result": {"text": "DOWN", "color": "red", "index": 1}}}]
SEM_RESPOSTA = [{"type": "value", "options": {"0": {"text": "sem resposta", "color": "text", "index": 0}}}]
FIBRA, RADIO = "/^Enlace FIBRA - estado/", "/^Enlace RÁDIO - estado/"


def estado(pid, titulo, item, x):
    return {"id": pid, "type": "stat", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": 0, "w": 5, "h": 5}, "targets": [alvo("A", item)],
            "fieldConfig": {"defaults": {"mappings": UP_DOWN, "color": {"mode": "thresholds"},
                                         "thresholds": {"mode": "absolute", "steps": [
                                             {"color": "red", "value": None}, {"color": "green", "value": 1}]}},
                            "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def latencia(pid, titulo, item, x):
    return {"id": pid, "type": "stat", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": 0, "w": 4, "h": 5}, "targets": [alvo("A", item)],
            "fieldConfig": {"defaults": {"unit": "s", "decimals": 1, "mappings": SEM_RESPOSTA, "color": {"mode": "thresholds"},
                                         "thresholds": {"mode": "absolute", "steps": [
                                             {"color": "green", "value": None}, {"color": "yellow", "value": 0.02},
                                             {"color": "red", "value": 0.05}]}}, "overrides": []},
            "options": {"colorMode": "value", "graphMode": "area", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


caminho = {
    "id": 1, "type": "stat", "title": "CAMINHO ATIVO MATRIZ ↔ FILIAL", "datasource": DS,
    "gridPos": {"x": 0, "y": 0, "w": 6, "h": 5}, "targets": [alvo("A", "/^Caminho ativo/")],
    "fieldConfig": {"defaults": {"mappings": [
        {"type": "range", "options": {"from": 1.5, "to": 3.5, "result": {"text": "FIBRA", "color": "green", "index": 0}}},
        {"type": "range", "options": {"from": 0.5, "to": 1.5, "result": {"text": "RÁDIO (failover)", "color": "orange", "index": 1}}},
        {"type": "range", "options": {"from": -0.5, "to": 0.5, "result": {"text": "FILIAL ISOLADA", "color": "red", "index": 2}}}],
        "color": {"mode": "thresholds"},
        "thresholds": {"mode": "absolute", "steps": [{"color": "red", "value": None}, {"color": "orange", "value": 0.5},
                                                     {"color": "green", "value": 1.5}]}}, "overrides": []},
    "options": {"colorMode": "background", "graphMode": "none", "textMode": "value",
                "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
}

painéis = [
    caminho,
    estado(2, "FIBRA (principal)", FIBRA, 6),
    estado(3, "RÁDIO (backup)", RADIO, 11),
    latencia(4, "Latência FIBRA", "/^Enlace FIBRA - latência/", 16),
    latencia(5, "Latência RÁDIO", "/^Enlace RÁDIO - latência/", 20),
    {"id": 6, "type": "state-timeline", "title": "LINHA DO TEMPO DOS ENLACES — cada troca de cor é uma queda ou retorno",
     "datasource": DS, "gridPos": {"x": 0, "y": 5, "w": 24, "h": 6},
     "targets": [alvo("A", FIBRA), alvo("B", RADIO)],
     "fieldConfig": {"defaults": {"mappings": UP_DOWN, "color": {"mode": "fixed", "fixedColor": "text"}},
                     "overrides": [nome(".*FIBRA.*", "Fibra"), nome(".*RÁDIO.*", "Rádio")]},
     "options": {"showValue": "auto", "mergeValues": True, "rowHeight": 0.8, "legend": {"showLegend": False}}},
    {"id": 7, "type": "timeseries", "title": "Latência Fibra x Rádio", "datasource": DS,
     "gridPos": {"x": 0, "y": 11, "w": 12, "h": 8},
     "targets": [alvo("A", "/^Enlace FIBRA - latência/"), alvo("B", "/^Enlace RÁDIO - latência/")],
     "fieldConfig": {"defaults": {"unit": "s", "min": 0, "custom": {"fillOpacity": 10, "lineWidth": 2, "axisSoftMax": 0.05}},
                     "overrides": [nome(".*FIBRA.*", "Fibra"), nome(".*RÁDIO.*", "Rádio")]},
     "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}},
    {"id": 8, "type": "timeseries", "title": "Tráfego: no failover ele sai da Fibra (ether2) e vai para o Rádio (ether3)",
     "datasource": DS, "gridPos": {"x": 12, "y": 11, "w": 12, "h": 8},
     "targets": [alvo("A", "/ether2.*Bits/"), alvo("B", "/ether3.*Bits/")],
     "fieldConfig": {"defaults": {"unit": "bps", "custom": {"fillOpacity": 15, "lineWidth": 2}}, "overrides": []},
     "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}},
    {"id": 9, "type": "alexanderzobnin-zabbix-triggers-panel", "title": "PROBLEMAS (com comentários da IA)",
     "datasource": DS, "gridPos": {"x": 0, "y": 19, "w": 24, "h": 9},
     "targets": [{"refId": "A", "datasource": DS, "queryType": "5", "group": {"filter": GRUPO},
                  "host": {"filter": "/.*/"}, "proxy": {"filter": ""}, "application": {"filter": ""},
                  "trigger": {"filter": ""}, "tags": {"filter": ""},
                  "options": {"minSeverity": 0, "acknowledged": 2, "sortProblems": "default",
                              "hostsInMaintenance": True, "showProblems": "problems", "limit": 100}}],
     "options": {"layout": "table", "showTags": True, "hostField": True, "severityField": True,
                 "ackField": True, "ageField": True, "descriptionField": True}},
]

dashboard = {"uid": "noc-redundancia", "title": "NOC - Redundância Fibra x Rádio", "tags": ["NOC", "TCC"],
             "timezone": "browser", "refresh": "10s", "time": {"from": "now-6h", "to": "now"},
             "schemaVersion": 39, "editable": False, "graphTooltip": 1, "panels": painéis}
gravar(ARQ_DASH, json.dumps(dashboard, ensure_ascii=False, indent=1))
os.chown(DIR_DASH, 0, GRAFANA_GID)
print(f"[ok] dashboard em {ARQ_DASH}")

# 4. Servidor: senha de admin aleatória, visitante somente leitura, página inicial = NOC
if not SENHA_ADMIN.exists():
    senha = secrets.token_urlsafe(18)
    gravar(SENHA_ADMIN, senha, 0o640, grupo_grafana=True)
    gravar(Path("/root/.grafana_admin"), f"usuario: admin\nsenha: {senha}\n", 0o600)
ambiente = Path("/etc/default/grafana-server")
linhas = [l for l in ambiente.read_text().splitlines() if not l.startswith("GF_")]
linhas += [f"GF_SECURITY_ADMIN_PASSWORD__FILE={SENHA_ADMIN}",
           "GF_AUTH_ANONYMOUS_ENABLED=true",
           "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer",
           f"GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH={ARQ_DASH}",
           "GF_USERS_DEFAULT_LANGUAGE=pt-BR",
           "GF_ANALYTICS_REPORTING_ENABLED=false",
           "GF_NEWS_NEWS_FEED_ENABLED=false"]
ambiente.write_text("\n".join(linhas) + "\n")
print("[ok] servidor: visitante só leitura, página inicial NOC, senha admin em /root/.grafana_admin")
