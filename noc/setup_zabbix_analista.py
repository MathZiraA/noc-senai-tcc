"""Configura no Zabbix a integração com o Analista NOC (idempotente).

- Tipo de mídia webhook "Analista IA (Claude)" -> POST no serviço local
- Mídia desse tipo no usuário Admin
- Ação "Analista IA - Investigação de incidentes": em cada problema do grupo, chama o webhook;
  quando o problema recebe o comentário da IA, envia esse comentário por e-mail.
"""
import secrets

import config
from zbx import TOKEN_ANALISTA, call

GRUPO = config.GRUPO
GRUPO_USUARIOS = "NOC Automação"
USUARIO = "noc-analista"
MIDIA_WEBHOOK = "Analista IA"
MIDIA_EMAIL = "Gmail Alertas SENAI"
ACAO = "Analista IA - Investigação de incidentes"

SCRIPT = """var p = JSON.parse(value);
var req = new HttpRequest();
req.addHeader('Content-Type: application/json');
req.post('http://127.0.0.1:8765/evento', JSON.stringify(p));
if (req.getStatus() != 202) {
    throw 'Analista IA respondeu HTTP ' + req.getStatus();
}
return 'OK';"""

PARAMETROS = {
    "eventid": "{EVENT.ID}",
    "host": "{HOST.HOST}",
    "nome": "{EVENT.NAME}",
    "status": "{EVENT.STATUS}",
    "atualizacao": "{EVENT.UPDATE.STATUS}",
    "severidade": "{EVENT.SEVERITY}",
    "severidade_num": "{EVENT.NSEVERITY}",
    "horario": "{EVENT.DATE} {EVENT.TIME}",
}

EMAIL_ASSUNTO = "[ANÁLISE IA] {EVENT.NAME} - {HOST.NAME}"
EMAIL_CORPO = """<h2>Análise do Analista NOC (IA)</h2>
<p><b>Incidente:</b> {EVENT.NAME}<br>
<b>Severidade:</b> {EVENT.SEVERITY}<br>
<b>Início:</b> {EVENT.DATE} {EVENT.TIME}<br>
<b>Status atual:</b> {EVENT.STATUS}</p>
<pre style="white-space:pre-wrap;font-family:Segoe UI,Arial,sans-serif;font-size:14px">{EVENT.UPDATE.MESSAGE}</pre>
<hr><p><i>Relatório gerado pelo Claude a partir dos dados do Zabbix. Confirme antes de agir.</i></p>"""

# 1. Tipo de mídia webhook
mt = call("mediatype.get", {"filter": {"name": [MIDIA_WEBHOOK]}, "output": ["mediatypeid"]})
if mt:
    webhook_id = mt[0]["mediatypeid"]
else:
    webhook_id = call("mediatype.create", {
        "name": MIDIA_WEBHOOK, "type": 4, "status": 0, "timeout": "10s", "script": SCRIPT,
        "parameters": [{"name": k, "value": v} for k, v in PARAMETROS.items()],
        "description": "Entrega o evento ao serviço noc-analista (127.0.0.1:8765), que investiga com IA.",
    })["mediatypeids"][0]
print(f"[ok] tipo de mídia webhook (id {webhook_id})")
email_id = call("mediatype.get", {"filter": {"name": [MIDIA_EMAIL]}, "output": ["mediatypeid"]})[0]["mediatypeid"]

# 2. Mídia no usuário Admin (preservando as existentes)
admin = call("user.get", {"filter": {"username": ["Admin"]}, "selectMedias": "extend", "output": ["userid"]})[0]
if not any(m["mediatypeid"] == webhook_id for m in admin["medias"]):
    medias = [{k: m[k] for k in ("mediatypeid", "sendto", "active", "severity", "period")} for m in admin["medias"]]
    medias.append({"mediatypeid": webhook_id, "sendto": "analista", "active": 0, "severity": 63,
                   "period": "1-7,00:00-24:00"})
    call("user.update", {"userid": admin["userid"], "medias": medias})
print("[ok] mídia do analista vinculada ao Admin")

# 3. Ação
grupo_id = call("hostgroup.get", {"filter": {"name": [GRUPO]}, "output": ["groupid"]})[0]["groupid"]
if not call("action.get", {"filter": {"name": [ACAO]}, "output": ["actionid"]}):
    call("action.create", {
        "name": ACAO, "eventsource": 0, "status": 0, "esc_period": "1h", "pause_suppressed": 1,
        "filter": {"evaltype": 0, "conditions": [{"conditiontype": 0, "operator": 0, "value": grupo_id}]},
        "operations": [{
            "operationtype": 0, "esc_step_from": 1, "esc_step_to": 1,
            "opmessage_usr": [{"userid": admin["userid"]}],
            "opmessage": {"default_msg": 0, "mediatypeid": webhook_id, "subject": "IA", "message": "IA"},
        }],
        "update_operations": [{
            "operationtype": 0,
            "opmessage_usr": [{"userid": admin["userid"]}],
            "opmessage": {"default_msg": 0, "mediatypeid": email_id, "subject": EMAIL_ASSUNTO,
                          "message": EMAIL_CORPO},
        }],
    })
print(f"[ok] ação '{ACAO}'")

# 4. Usuário próprio do analista (só leitura + comentar), com token gravado direto em arquivo
ug = call("usergroup.get", {"filter": {"name": [GRUPO_USUARIOS]}, "output": ["usrgrpid"]})
ugid = ug[0]["usrgrpid"] if ug else call("usergroup.create", {
    "name": GRUPO_USUARIOS, "gui_access": 3,  # sem acesso ao frontend, só API
    "hostgroup_rights": [{"id": grupo_id, "permission": 2}]})["usrgrpids"][0]
u = call("user.get", {"filter": {"username": [USUARIO]}, "output": ["userid"]})
uid = u[0]["userid"] if u else call("user.create", {
    "username": USUARIO, "name": "Analista IA", "roleid": "1",  # User role: ler e comentar problemas
    "passwd": secrets.token_urlsafe(32),  # nunca usada: o acesso é só por token
    "usrgrps": [{"usrgrpid": ugid}]})["userids"][0]
if not TOKEN_ANALISTA.exists():
    for t in call("token.get", {"userids": [uid], "filter": {"name": ["noc-analista"]}, "output": ["tokenid"]}):
        call("token.delete", [t["tokenid"]])
    tid = call("token.create", {"name": "noc-analista", "userid": uid})["tokenids"][0]
    TOKEN_ANALISTA.write_text(call("token.generate", [tid])[0]["token"])
    TOKEN_ANALISTA.chmod(0o600)
print(f"[ok] usuário '{USUARIO}' com token em {TOKEN_ANALISTA}")
