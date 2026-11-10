"""Gera o painel "NOC - Servidor (segurança)" no Grafana, a partir do host NOC-SERVIDOR do Zabbix.

Escreve um dashboard provisionado próprio (/var/lib/grafana/dashboards/noc-servidor.json), ao lado do
painel de redundância. Mostra os sinais de ataque (estados TCP, conexões no site, workers do Apache,
descartes do firewall) e a saúde (CPU, carga, RAM), para acompanhar e mitigar ataques ao servidor.

Uso, no servidor:  python3 grafana_servidor.py && systemctl restart grafana-server
"""
import json

ARQ = "/var/lib/grafana/dashboards/noc-servidor.json"
GRUPO = "Rede SENAI - Equipamentos"
DS = {"type": "alexanderzobnin-zabbix-datasource", "uid": "zabbix-noc"}
_id = 0


def novo_id():
    global _id
    _id += 1
    return _id


def alvo(ref, item):
    return {"refId": ref, "datasource": DS, "queryType": "0", "group": {"filter": GRUPO},
            "host": {"filter": "/^NOC-SERVIDOR/"}, "itemTag": {"filter": ""}, "item": {"filter": item},
            "functions": [], "options": {"showDisabledItems": False}}


def limiares(*passos):
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for v, c in passos]}


def stat(titulo, x, w, item, passos, unit=""):
    return {"id": novo_id(), "type": "stat", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": 0, "w": w, "h": 4},
            "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "thresholds"},
                                         "thresholds": limiares(*passos)}, "overrides": []},
            "targets": [alvo("A", item)],
            "options": {"colorMode": "background", "graphMode": "area", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def ip_stat(titulo, x, w, item):
    return {"id": novo_id(), "type": "stat", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": 0, "w": w, "h": 4},
            "fieldConfig": {"defaults": {"color": {"mode": "fixed", "fixedColor": "text"}}, "overrides": []},
            "targets": [alvo("A", item)],
            "options": {"colorMode": "none", "graphMode": "none", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def serie(titulo, x, y, w, h, alvos, unit=""):
    return {"id": novo_id(), "type": "timeseries", "title": titulo, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "fieldConfig": {"defaults": {"unit": unit, "custom": {"fillOpacity": 12, "lineWidth": 2,
                            "showPoints": "never"}}, "overrides": []},
            "targets": [alvo(chr(65 + i), it) for i, it in enumerate(alvos)],
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}


paines = [
    # Linha de indicadores (y=0)
    stat("SYN_RECV", 0, 4, "/^Conexões SYN_RECV/", ((None, "green"), (100, "orange"), (200, "red"))),
    stat("Conexões no site", 4, 4, "/^Conexões no site/", ((None, "green"), (300, "orange"), (500, "red"))),
    stat("Apache ocupados", 8, 4, "/^Apache: workers ocupados/", ((None, "green"), (100, "orange"), (135, "red"))),
    stat("IP mais frequente", 12, 4, "/^Conexões do IP mais frequente/", ((None, "green"), (60, "orange"), (100, "red"))),
    stat("fail2ban banidos", 16, 4, "/^fail2ban/", ((None, "green"), (1, "orange"), (10, "red"))),
    stat("SSH falhas/min", 20, 4, "/^SSH: falhas/", ((None, "green"), (10, "orange"), (20, "red"))),
    # Rede / web
    serie("Estados de conexão TCP", 0, 4, 12, 8,
          ["/^Conexões estabelecidas/", "/^Conexões SYN_RECV/", "/^Conexões TIME_WAIT/"]),
    serie("Conexões no site (80/443)", 12, 4, 12, 8, ["/^Conexões no site/"]),
    serie("Apache: workers ocupados x livres", 0, 12, 12, 8,
          ["/^Apache: workers ocupados/", "/^Apache: workers livres/"]),
    serie("Firewall: pacotes descartados por segundo", 12, 12, 12, 8,
          ["/^Firewall: pacotes descartados/"], unit="pps"),
    # Saúde
    serie("CPU e carga", 0, 20, 8, 7, ["/^CPU utilizada/", "/^Carga média/"]),
    serie("Memória", 8, 20, 8, 7, ["/^RAM usada/", "/^Swap usada/"], unit="percent"),
    serie("SSH falhas x fail2ban banidos", 16, 20, 8, 7, ["/^SSH: falhas/", "/^fail2ban/"]),
]
paines.append(ip_stat("IP de origem com mais conexões", 0, 24, "/^IP mais frequente/"))
paines[-1]["gridPos"]["y"] = 27

dash = {
    "uid": "noc-servidor", "title": "NOC - Servidor (segurança)", "tags": ["NOC", "seguranca"],
    "timezone": "browser", "schemaVersion": 39, "version": 1, "editable": True,
    "refresh": "30s", "time": {"from": "now-3h", "to": "now"},
    "templating": {"list": []}, "annotations": {"list": []}, "panels": paines,
}
json.dump(dash, open(ARQ, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"painel do servidor gerado: {len(paines)} painéis em {ARQ}")
