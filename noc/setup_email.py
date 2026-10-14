"""E-mail de alertas do NOC (idempotente): mídia SMTP do Gmail, e-mail do Admin e a ação de alerta/normalização.

A senha de app do Gmail é lida de /root/.gmail_app (gravada pelo instalador) e apagada depois de enviada
ao Zabbix: a partir daí ela só existe dentro do Zabbix. Sem o arquivo, a mídia existente é mantida.
"""
from pathlib import Path

import config
from config import C
from zbx import call

MIDIA = "Gmail Alertas SENAI"
ACAO = "Notificação NOC - Redundância e Enlaces"
SENHA_APP = Path("/root/.gmail_app")

ALERTA_ASSUNTO = "🚨 [ALERTA NOC SENAI] Falha / Mudança de Link em {HOST.NAME}"
ALERTA_CORPO = """<h2>Alerta de Conectividade - NOC SENAI</h2>
<p><b>Equipamento:</b> {HOST.NAME} ({HOST.IP})</p>
<p><b>Evento Identificado:</b> {EVENT.NAME}</p>
<p><b>Severidade:</b> {EVENT.SEVERITY}</p>
<p><b>Data/Hora do Disparo:</b> {EVENT.DATE} às {EVENT.TIME}</p>
<hr>
<p><i>Este é um disparo automático predeterminado do Zabbix Server.</i></p>"""
NORMAL_ASSUNTO = "✅ [NORMALIZADO NOC SENAI] Restabelecimento em {HOST.NAME}"
NORMAL_CORPO = """<h2>Enlace Restabelecido - NOC SENAI</h2>
<p><b>Equipamento:</b> {HOST.NAME}</p>
<p><b>Evento Resolvido:</b> {EVENT.NAME}</p>
<p><b>Horário da Normalização:</b> {EVENT.RECOVERY.DATE} às {EVENT.RECOVERY.TIME}</p>"""

# 1. Mídia SMTP
campos = {"name": MIDIA, "type": 0, "status": 0, "smtp_server": C["SMTP_SERVIDOR"], "smtp_port": C["SMTP_PORTA"],
          "smtp_helo": C["EMAIL"].split("@")[1], "smtp_email": C["EMAIL"], "smtp_security": 1,
          "smtp_verify_peer": 1, "smtp_verify_host": 1, "smtp_authentication": 1, "username": C["EMAIL"],
          "message_format": 1}
if SENHA_APP.exists():
    campos["passwd"] = SENHA_APP.read_text().strip().replace(" ", "")
m = call("mediatype.get", {"filter": {"name": [MIDIA]}, "output": ["mediatypeid"]})
if m:
    midia_id = m[0]["mediatypeid"]
    call("mediatype.update", {"mediatypeid": midia_id, **campos})
elif "passwd" in campos:
    midia_id = call("mediatype.create", campos)["mediatypeids"][0]
else:
    raise SystemExit("[erro] grave a senha de app do Gmail em /root/.gmail_app antes de criar a mídia")
if SENHA_APP.exists():
    SENHA_APP.unlink()
print(f"[ok] mídia '{MIDIA}' ({C['EMAIL']} via {C['SMTP_SERVIDOR']})")

# 2. E-mail no usuário Admin (preserva as outras mídias, como o webhook do analista)
admin = call("user.get", {"filter": {"username": ["Admin"]}, "selectMedias": "extend", "output": ["userid"]})[0]
if not any(md["mediatypeid"] == midia_id for md in admin["medias"]):
    medias = [{k: md[k] for k in ("mediatypeid", "sendto", "active", "severity", "period")} for md in admin["medias"]]
    medias.append({"mediatypeid": midia_id, "sendto": [C["EMAIL"]], "active": 0, "severity": 63,
                   "period": "1-7,00:00-24:00"})
    call("user.update", {"userid": admin["userid"], "medias": medias})
print(f"[ok] Admin recebe em {C['EMAIL']}")

# 3. Ação: alerta na abertura e normalização na recuperação, para o grupo da rede
grupo_id = call("hostgroup.get", {"filter": {"name": [config.GRUPO]}, "output": ["groupid"]})[0]["groupid"]
if not call("action.get", {"filter": {"name": [ACAO]}, "output": ["actionid"]}):
    call("action.create", {
        "name": ACAO, "eventsource": 0, "status": 0, "esc_period": "1h", "pause_suppressed": 1,
        "filter": {"evaltype": 0, "conditions": [{"conditiontype": 0, "operator": 0, "value": grupo_id}]},
        "operations": [{"operationtype": 0, "esc_step_from": 1, "esc_step_to": 1,
                        "opmessage_usr": [{"userid": admin["userid"]}],
                        "opmessage": {"default_msg": 0, "mediatypeid": midia_id, "subject": ALERTA_ASSUNTO,
                                      "message": ALERTA_CORPO}}],
        "recovery_operations": [{"operationtype": 11,
                                 "opmessage": {"default_msg": 0, "subject": NORMAL_ASSUNTO,
                                               "message": NORMAL_CORPO}}],
    })
print(f"[ok] ação '{ACAO}'")
