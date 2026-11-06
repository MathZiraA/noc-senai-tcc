"""Modo TV: link fixo e revogável para a tela do NOC, sem login.

O link dá acesso só ao que a TV mostra (enlace, latência e alertas ativos), nunca a usuários ou chamados.
Só o hash do segredo fica no banco; o link completo aparece uma única vez, ao ser criado.
"""
import hashlib
import secrets
import time

from fastapi import Header, APIRouter, HTTPException
from pydantic import BaseModel, Field

import auth
import fonte
from banco import db

router = APIRouter()


def criar_tabelas(con):
    con.execute("""create table if not exists tv_links (id integer primary key, nome text not null, token_hash text unique,
                   criado_em integer, criado_por text, ultimo_uso integer, revogado_em integer)""")


def _h(k):
    return hashlib.sha256(k.encode()).hexdigest()


class NovaTv(BaseModel):
    nome: str = Field(min_length=2, max_length=60)


@router.get("/api/tv-links")
def listar(_=auth.exigir("usuarios")):
    with db() as con:
        return [dict(r) for r in con.execute(
            "select id, nome, criado_em, criado_por, ultimo_uso from tv_links where revogado_em is null order by id desc")]


@router.post("/api/tv-links", status_code=201)
def criar(t: NovaTv, u=auth.exigir("usuarios")):
    k = secrets.token_urlsafe(24)
    with db() as con:
        con.execute("insert into tv_links (nome, token_hash, criado_em, criado_por) values (?,?,?,?)",
                    (t.nome, _h(k), int(time.time()), u["nome"]))
    return {"chave": k}  # o front monta https://<servidor>/sennaguard/tv#k=<chave>


@router.delete("/api/tv-links/{tid}", status_code=204)
def revogar(tid: int, _=auth.exigir("usuarios")):
    with db() as con:
        con.execute("update tv_links set revogado_em=? where id=?", (int(time.time()), tid))


@router.get("/api/tv")
def tela(x_tv_chave: str | None = Header(default=None)):
    # A chave vem no cabeçalho (o link usa #k=, que o navegador nunca envia): não fica no log de acesso do Apache
    k = x_tv_chave or ""
    with db() as con:
        r = con.execute("select id from tv_links where token_hash=? and revogado_em is null", (_h(k),)).fetchone()
        if not r:
            raise HTTPException(403, "Link de TV inválido ou revogado.")
        con.execute("update tv_links set ultimo_uso=? where id=?", (int(time.time()), r[0]))
    alertas = [a for a in fonte.alertas(24) if a["ativo"]]
    campos = ("id", "severidade", "nivel", "nome", "inicio")
    return {"visao": fonte.visao(), "latencia": fonte.serie("latencia", 6),
            "alertas": [{c: a[c] for c in campos} for a in alertas][:6]}
