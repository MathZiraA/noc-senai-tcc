"""Avisos pelo Telegram: bot próprio do NOC (criado no @BotFather), token em TELEGRAM_TOKEN.

Cada pessoa liga a própria conta pelo botão "Conectar Telegram": o link abre o bot com um código de uso
único, e a mensagem /start <código> grava o chat dela. Sem token, todas as funções viram no-op.
"""
import json
import logging
import os
import secrets
import threading
import time
import urllib.request
import uuid

from fastapi import APIRouter, HTTPException

import auth
from banco import coluna, db

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
# O que cada pessoa quer receber (perfil). "silencio" = não perturbe das 22 h às 7 h, menos Desastre.
NOTIFICACOES = {"desastre": True, "alta": True, "media": True, "caminho": True, "chamados": True,
                "manutencao": True, "relatorio": True, "silencio": False}
log = logging.getLogger("sennaguard.telegram")
router = APIRouter()
_bot = {"nome": os.environ.get("TELEGRAM_BOT", ""), "offset": 0}


def ativo():
    return bool(TOKEN)


def criar_tabelas(con):
    coluna(con, "usuarios", "telegram_chat_id", "text")
    coluna(con, "usuarios", "notificacoes", "text")
    con.execute("create table if not exists telegram_codigos (codigo text primary key, usuario_id integer, expira integer)")


def _api(metodo, dados=None, corpo=None, tipo="application/json", timeout=15):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{metodo}",
                                 data=corpo if corpo is not None else json.dumps(dados or {}).encode(),
                                 headers={"Content-Type": tipo})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["result"]


def _em_segundo_plano(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


def _enviar(chat_id, texto):
    try:
        _api("sendMessage", {"chat_id": chat_id, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})
    except Exception as e:  # Telegram fora do ar não pode derrubar a ação de quem está usando o painel
        log.warning("falha ao enviar Telegram para %s: %s", chat_id, e)


def enviar_documento(chat_id, nome, conteudo: bytes, legenda=""):
    if not ativo():
        return
    limite = uuid.uuid4().hex
    partes = []
    for campo, valor in (("chat_id", str(chat_id)), ("caption", legenda)):
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"\r\n\r\n{valor}\r\n'.encode())
    partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="document"; filename="{nome}"\r\n'
                  f'Content-Type: application/pdf\r\n\r\n'.encode() + conteudo + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    try:
        _api("sendDocument", corpo=b"".join(partes), tipo=f"multipart/form-data; boundary={limite}", timeout=60)
    except Exception as e:
        log.warning("falha ao enviar documento para %s: %s", chat_id, e)


def preferencias(guardado):
    try:
        return NOTIFICACOES | (json.loads(guardado) if guardado else {})
    except ValueError:
        return dict(NOTIFICACOES)


def aceita(guardado, tipo=None, urgente=False):
    """A pessoa quer este aviso agora? `tipo` é uma chave de NOTIFICACOES; urgente fura o não perturbe."""
    p = preferencias(guardado)
    if tipo and not p.get(tipo, True):
        return False
    hora = time.localtime().tm_hour
    return urgente or not (p["silencio"] and (hora >= 22 or hora < 7))


def para_usuarios(ids, texto, tipo=None, urgente=False):
    """Manda para os usuários indicados que têm Telegram ligado, acesso ativo e querem esse tipo de aviso."""
    if not ativo() or not ids:
        return
    with db() as con:
        linhas = con.execute(f"""select telegram_chat_id, notificacoes from usuarios
                                 where ativo=1 and telegram_chat_id is not null and id in ({','.join('?' * len(ids))})""", list(ids)).fetchall()
    for chat, prefs in linhas:
        if aceita(prefs, tipo, urgente):
            _em_segundo_plano(_enviar, chat, texto)


def para_equipe(texto, preferencia="chamado_email", papeis=("Administrador", "Analista", "Operador"), tipo=None, urgente=False, exceto=None):
    """Manda para a equipe que marcou a preferência (alerta_email = alertas, chamado_email = chamados)."""
    if not ativo():
        return
    with db() as con:
        ids = [r[0] for r in con.execute(
            f"select id from usuarios where {preferencia}=1 and papel in ({','.join('?' * len(papeis))})", list(papeis)) if r[0] != exceto]
    para_usuarios(ids, texto, tipo, urgente)


def ler_mensagens():
    """Chamado pela agenda: liga o chat de quem mandou /start <código>."""
    if not ativo():
        return
    try:
        if not _bot["nome"]:
            _bot["nome"] = _api("getMe")["username"]
        for u in _api("getUpdates", {"offset": _bot["offset"], "timeout": 0}):
            _bot["offset"] = u["update_id"] + 1
            msg = u.get("message") or {}
            texto, chat = msg.get("text", ""), msg.get("chat", {}).get("id")
            if not texto.startswith("/start") or not chat:
                continue
            codigo = texto.split(maxsplit=1)[1].strip() if " " in texto else ""
            with db() as con:
                r = con.execute("select usuario_id from telegram_codigos where codigo=? and expira>?", (codigo, int(time.time()))).fetchone()
                if r:
                    con.execute("update usuarios set telegram_chat_id=? where id=?", (str(chat), r[0]))
                    con.execute("delete from telegram_codigos where codigo=?", (codigo,))
                    nome = con.execute("select nome from usuarios where id=?", (r[0],)).fetchone()[0]
            _enviar(chat, f"✅ Pronto, {nome}! Você vai receber os avisos do SennaGuard aqui." if r
                    else "Código inválido ou expirado. Gere um novo em SennaGuard → seu nome → Conectar Telegram.")
    except Exception as e:
        log.warning("falha ao ler o Telegram: %s", e)


@router.post("/api/eu/telegram")
def gerar_link(u=auth.exigir("visao")):
    if not ativo():
        raise HTTPException(503, "O Telegram ainda não foi configurado no servidor (TELEGRAM_TOKEN).")
    if not _bot["nome"]:
        _bot["nome"] = _api("getMe")["username"]
    codigo = secrets.token_urlsafe(9)
    with db() as con:
        con.execute("delete from telegram_codigos where usuario_id=? or expira<?", (u["id"], int(time.time())))
        con.execute("insert into telegram_codigos values (?,?,?)", (codigo, u["id"], int(time.time()) + 900))
    return {"link": f"https://t.me/{_bot['nome']}?start={codigo}", "bot": _bot["nome"]}


@router.delete("/api/eu/telegram", status_code=204)
def desligar(u=auth.exigir("visao")):
    with db() as con:
        con.execute("update usuarios set telegram_chat_id=null where id=?", (u["id"],))
