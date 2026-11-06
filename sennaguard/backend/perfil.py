"""Perfil de quem está logado: foto, e-mail, avisos no Telegram, montagem da Visão geral e o tour do 1º acesso."""
import json
import sqlite3
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

import anexos
import auth
import telegram
from banco import ARQUIVOS, coluna, db

FOTOS = ARQUIVOS / "fotos"
router = APIRouter()


def criar_tabelas(con):
    coluna(con, "usuarios", "foto_em", "integer")
    coluna(con, "usuarios", "painel", "text")
    coluna(con, "usuarios", "tour_visto", "integer default 0")


def do_usuario(u):
    """Campos do perfil que vão junto com /api/eu."""
    return {"foto": u.get("foto_em"), "tour_visto": bool(u.get("tour_visto")),
            "painel": json.loads(u["painel"]) if u.get("painel") else None,
            "notificacoes": telegram.preferencias(u.get("notificacoes")) | {
                "alertas": bool(u.get("alerta_email")), "chamados_equipe": bool(u.get("chamado_email"))}}


class TrocaEmail(BaseModel):
    email: EmailStr
    senha: str


@router.put("/api/eu/email", status_code=204)
def trocar_email(d: TrocaEmail, req: Request, u=auth.exigir("visao")):
    if not auth.confere_senha(d.senha, u["senha_hash"]):
        raise HTTPException(400, "Senha atual incorreta.")
    try:
        with db() as con:
            con.execute("update usuarios set email=? where id=?", (d.email.strip().lower(), u["id"]))
            auth.derrubar_outras_sessoes(con, req, u["id"])
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Já existe um usuário com esse e-mail.")


class Notificacoes(BaseModel):
    alertas: bool = True           # coluna alerta_email: liga/desliga todos os alertas (só equipe)
    chamados_equipe: bool = False  # coluna chamado_email: chamados novos de qualquer pessoa (só equipe)
    desastre: bool = True
    alta: bool = True
    media: bool = True
    caminho: bool = True
    chamados: bool = True          # respostas nos chamados em que a pessoa está
    manutencao: bool = True
    relatorio: bool = True
    silencio: bool = False


@router.put("/api/eu/notificacoes", status_code=204)
def salvar_notificacoes(n: Notificacoes, u=auth.exigir("visao")):
    prefs = n.model_dump(exclude={"alertas", "chamados_equipe"})
    with db() as con:
        con.execute("update usuarios set notificacoes=?, alerta_email=?, chamado_email=? where id=?",
                    (json.dumps(prefs), n.alertas, n.chamados_equipe, u["id"]))


class Painel(BaseModel):
    ordem: list[str] = Field(max_length=20)
    ocultos: list[str] = Field(default_factory=list, max_length=20)


@router.put("/api/eu/painel", status_code=204)
def salvar_painel(p: Painel, u=auth.exigir("visao")):
    if any(len(x) > 30 or not x.replace("_", "").isalnum() for x in p.ordem + p.ocultos):
        raise HTTPException(422, "Cartão inválido.")
    with db() as con:
        con.execute("update usuarios set painel=? where id=?", (json.dumps(p.model_dump()), u["id"]))


@router.delete("/api/eu/painel", status_code=204)
def restaurar_painel(u=auth.exigir("visao")):
    with db() as con:
        con.execute("update usuarios set painel=null where id=?", (u["id"],))


@router.post("/api/eu/tour", status_code=204)
def tour_visto(u=auth.exigir("visao")):
    with db() as con:
        con.execute("update usuarios set tour_visto=1 where id=?", (u["id"],))


@router.put("/api/eu/foto")
async def enviar_foto(req: Request, u=auth.exigir("visao")):
    """O navegador já manda a foto recortada em 256 px; aqui só conferimos tipo e tamanho."""
    corpo = await anexos.ler_corpo(req, 2 * 1024 * 1024)
    if not (anexos.tipo_real(corpo) or "").startswith("image/"):
        raise HTTPException(415, "Envie uma imagem PNG, JPG ou WEBP.")
    FOTOS.mkdir(parents=True, exist_ok=True)
    (FOTOS / str(u["id"])).write_bytes(corpo)
    em = int(time.time())
    with db() as con:
        con.execute("update usuarios set foto_em=? where id=?", (em, u["id"]))
    return {"foto": em}


@router.delete("/api/eu/foto", status_code=204)
def remover_foto(u=auth.exigir("visao")):
    (FOTOS / str(u["id"])).unlink(missing_ok=True)
    with db() as con:
        con.execute("update usuarios set foto_em=null where id=?", (u["id"],))


@router.get("/api/usuarios/{uid}/foto")
def foto(uid: int, _=auth.exigir("visao")):
    arquivo = FOTOS / str(uid)
    if not arquivo.is_file():
        raise HTTPException(404, "Sem foto.")
    tipo = anexos.tipo_real(arquivo.read_bytes()[:16]) or "application/octet-stream"
    # O endereço muda a cada foto nova (?v=…), então pode ficar em cache por bastante tempo
    return FileResponse(arquivo, media_type=tipo, headers={"Cache-Control": "private, max-age=604800",
                                                           "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})
