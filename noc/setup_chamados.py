"""Chamado automático quando um enlace fica fora por mais de CHAMADO_APOS (padrão 1 h) — idempotente.

Pedido da CTI (reunião de 10/2026): o Zabbix confirma que a queda continua, abre um chamado numerado e envia
e-mail formal ao cliente, que serve de registro (segurança jurídica). Na volta do enlace, e-mail de encerramento.
- Macro global {$NOC_CHAMADO_APOS}: prazo do escalonamento (mudar no Zabbix vale na hora)
- Usuário "cliente-noc" (sem acesso ao site) com o e-mail do cliente
- Webhook "Chamado NOC": registra abertura/encerramento no livro encadeado (chamados.py)
- Ação "Chamado - enlace fora por mais de 1h": só para triggers com a tag chamado=sim
"""
import secrets

import config
from config import C
from zbx import call

MACRO = "{$NOC_CHAMADO_APOS}"
MIDIA_EMAIL = "Gmail Alertas SENAI"
MIDIA_CHAMADO = "Chamado NOC"
GRUPO_CLIENTES = "Clientes NOC"
USUARIO_CLIENTE = "cliente-noc"
ACAO = "Chamado - enlace fora por mais do prazo"

SCRIPT = """var p = JSON.parse(value);
var req = new HttpRequest();
req.addHeader('Content-Type: application/json');
req.post('http://127.0.0.1:8765/chamado', JSON.stringify(p));
if (req.getStatus() != 202) {
    throw 'Livro de chamados respondeu HTTP ' + req.getStatus();
}
return 'OK';"""
PARAMETROS = {"eventid": "{EVENT.ID}", "host": "{HOST.NAME}", "nome": "{EVENT.NAME}", "status": "{EVENT.STATUS}",
              "severidade": "{EVENT.SEVERITY}", "inicio": "{EVENT.DATE} {EVENT.TIME}", "duracao": "{EVENT.AGE}",
              "fim": "{EVENT.RECOVERY.DATE} {EVENT.RECOVERY.TIME}"}

ESTILO = 'style="border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;font-size:14px"'
CELULA = 'style="padding:6px 12px;border:1px solid #d0d7de"'
ABRE_ASSUNTO = "[CHAMADO NOC-{EVENT.ID}] Enlace indisponível há mais de {$NOC_CHAMADO_APOS} - {HOST.NAME}"
ABRE_CORPO = f"""<h2>Abertura de chamado - NOC SENAI</h2>
<p>Prezado(a) {C['CLIENTE_NOME']},</p>
<p>O monitoramento do NOC confirmou que o enlace abaixo continua indisponível após o prazo de
{{$NOC_CHAMADO_APOS}}. Foi aberto o chamado a seguir:</p>
<table {ESTILO}>
<tr><td {CELULA}><b>Chamado</b></td><td {CELULA}>NOC-{{EVENT.ID}}</td></tr>
<tr><td {CELULA}><b>Equipamento</b></td><td {CELULA}>{{HOST.NAME}}</td></tr>
<tr><td {CELULA}><b>Ocorrência</b></td><td {CELULA}>{{EVENT.NAME}}</td></tr>
<tr><td {CELULA}><b>Severidade</b></td><td {CELULA}>{{EVENT.SEVERITY}}</td></tr>
<tr><td {CELULA}><b>Início da indisponibilidade</b></td><td {CELULA}>{{EVENT.DATE}} às {{EVENT.TIME}}</td></tr>
<tr><td {CELULA}><b>Duração até este aviso</b></td><td {CELULA}>{{EVENT.AGE}}</td></tr>
<tr><td {CELULA}><b>Chamado aberto em</b></td><td {CELULA}>{{DATE}} às {{TIME}}</td></tr>
</table>
<p>Você receberá outro e-mail quando o serviço for normalizado.</p>
<hr><p style="font-size:12px;color:#57606a">Registro automático do sistema de monitoramento (Zabbix) do NOC SENAI,
gerado no momento indicado acima. Este e-mail documenta formalmente a indisponibilidade do enlace e a abertura do
chamado. O mesmo registro é mantido no servidor do NOC em livro encadeado por SHA-256, que permite comprovar que
não foi alterado depois de gravado.</p>"""
FECHA_ASSUNTO = "[CHAMADO NOC-{EVENT.ID}] Encerrado - serviço normalizado - {HOST.NAME}"
FECHA_CORPO = f"""<h2>Encerramento de chamado - NOC SENAI</h2>
<p>Prezado(a) {C['CLIENTE_NOME']}, o enlace foi normalizado e o chamado abaixo foi encerrado.</p>
<table {ESTILO}>
<tr><td {CELULA}><b>Chamado</b></td><td {CELULA}>NOC-{{EVENT.ID}}</td></tr>
<tr><td {CELULA}><b>Equipamento</b></td><td {CELULA}>{{HOST.NAME}}</td></tr>
<tr><td {CELULA}><b>Ocorrência</b></td><td {CELULA}>{{EVENT.NAME}}</td></tr>
<tr><td {CELULA}><b>Início</b></td><td {CELULA}>{{EVENT.DATE}} às {{EVENT.TIME}}</td></tr>
<tr><td {CELULA}><b>Normalização</b></td><td {CELULA}>{{EVENT.RECOVERY.DATE}} às {{EVENT.RECOVERY.TIME}}</td></tr>
<tr><td {CELULA}><b>Duração total da indisponibilidade</b></td><td {CELULA}>{{EVENT.DURATION}}</td></tr>
</table>
<hr><p style="font-size:12px;color:#57606a">Registro automático do sistema de monitoramento do NOC SENAI.</p>"""

# 1. Prazo do chamado (macro global)
m = call("usermacro.get", {"globalmacro": True, "filter": {"macro": MACRO}, "output": ["globalmacroid", "value"]})
if not m:
    call("usermacro.createglobal", {"macro": MACRO, "value": C["CHAMADO_APOS"],
                                    "description": "Tempo de queda contínua até abrir chamado e avisar o cliente"})
elif m[0]["value"] != C["CHAMADO_APOS"]:
    call("usermacro.updateglobal", {"globalmacroid": m[0]["globalmacroid"], "value": C["CHAMADO_APOS"]})
print(f"[ok] prazo do chamado: {C['CHAMADO_APOS']} (macro {MACRO})")

# 2. Webhook de registro
mt = call("mediatype.get", {"filter": {"name": [MIDIA_CHAMADO]}, "output": ["mediatypeid"]})
webhook_id = mt[0]["mediatypeid"] if mt else call("mediatype.create", {
    "name": MIDIA_CHAMADO, "type": 4, "status": 0, "timeout": "10s", "script": SCRIPT,
    "parameters": [{"name": k, "value": v} for k, v in PARAMETROS.items()],
    "description": "Registra abertura/encerramento de chamados no livro do NOC (127.0.0.1:8765/chamado)."})["mediatypeids"][0]
email_id = call("mediatype.get", {"filter": {"name": [MIDIA_EMAIL]}, "output": ["mediatypeid"]})[0]["mediatypeid"]

admin = call("user.get", {"filter": {"username": ["Admin"]}, "selectMedias": "extend", "output": ["userid"]})[0]
if not any(md["mediatypeid"] == webhook_id for md in admin["medias"]):
    medias = [{k: md[k] for k in ("mediatypeid", "sendto", "active", "severity", "period")} for md in admin["medias"]]
    medias.append({"mediatypeid": webhook_id, "sendto": "livro", "active": 0, "severity": 63,
                   "period": "1-7,00:00-24:00"})
    call("user.update", {"userid": admin["userid"], "medias": medias})
print(f"[ok] webhook '{MIDIA_CHAMADO}' ligado ao livro de chamados")

# 3. Usuário do cliente (só recebe e-mail, sem acesso ao site)
grupo_id = call("hostgroup.get", {"filter": {"name": [config.GRUPO]}, "output": ["groupid"]})[0]["groupid"]
ug = call("usergroup.get", {"filter": {"name": [GRUPO_CLIENTES]}, "output": ["usrgrpid"]})
ugid = ug[0]["usrgrpid"] if ug else call("usergroup.create", {
    "name": GRUPO_CLIENTES, "gui_access": 3, "hostgroup_rights": [{"id": grupo_id, "permission": 2}]})["usrgrpids"][0]
cli = call("user.get", {"filter": {"username": [USUARIO_CLIENTE]}, "selectMedias": "extend", "output": ["userid"]})
midia_cliente = [{"mediatypeid": email_id, "sendto": [config.CLIENTE_EMAIL], "active": 0, "severity": 63,
                  "period": "1-7,00:00-24:00"}]
if not cli:
    cliente_id = call("user.create", {"username": USUARIO_CLIENTE, "name": C["CLIENTE_NOME"], "roleid": "1",
                                      "passwd": secrets.token_urlsafe(32), "usrgrps": [{"usrgrpid": ugid}],
                                      "medias": midia_cliente})["userids"][0]
else:
    cliente_id = cli[0]["userid"]
    if [md["sendto"] for md in cli[0]["medias"]] != [[config.CLIENTE_EMAIL]]:
        call("user.update", {"userid": cliente_id, "name": C["CLIENTE_NOME"], "medias": midia_cliente})
print(f"[ok] cliente '{C['CLIENTE_NOME']}' recebe chamados em {config.CLIENTE_EMAIL}")

# 4. Ação com escalonamento: passo 1 (na hora) não faz nada; passo 2 (depois do prazo) abre o chamado
if not call("action.get", {"filter": {"name": [ACAO]}, "output": ["actionid"]}):
    call("action.create", {
        "name": ACAO, "eventsource": 0, "status": 0, "esc_period": MACRO, "pause_suppressed": 1,
        "filter": {"evaltype": 1, "conditions": [
            {"conditiontype": 0, "operator": 0, "value": grupo_id},
            {"conditiontype": 26, "operator": 0, "value2": "chamado", "value": "sim"}]},
        "operations": [
            {"operationtype": 0, "esc_step_from": 2, "esc_step_to": 2,
             "opmessage_usr": [{"userid": cliente_id}, {"userid": admin["userid"]}],
             "opmessage": {"default_msg": 0, "mediatypeid": email_id, "subject": ABRE_ASSUNTO, "message": ABRE_CORPO}},
            {"operationtype": 0, "esc_step_from": 2, "esc_step_to": 2,
             "opmessage_usr": [{"userid": admin["userid"]}],
             "opmessage": {"default_msg": 0, "mediatypeid": webhook_id, "subject": "chamado", "message": "abertura"}},
        ],
        # "Notificar todos os envolvidos" só alcança quem recebeu a abertura (passo 2): queda resolvida antes do
        # prazo não gera e-mail de encerramento. Usa todas as mídias deles: e-mail do cliente/Admin e o webhook do livro.
        "recovery_operations": [
            {"operationtype": 11,
             "opmessage": {"default_msg": 0, "subject": FECHA_ASSUNTO, "message": FECHA_CORPO}},
        ],
    })
print(f"[ok] ação '{ACAO}' (só quedas com tag chamado=sim)")
