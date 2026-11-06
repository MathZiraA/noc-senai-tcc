"""Janelas de manutenção: agendadas no SennaGuard e criadas também no Zabbix (o Zabbix continua coletando,
mas os avisos ficam suspensos). O cliente é avisado no Telegram ao agendar e 1 h antes, e vê uma faixa no painel.
"""
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import agenda
import auth
import fonte
import telegram
import tempo_real
from banco import db
from html import escape as _e  # texto de usuário nas mensagens HTML do Telegram

router = APIRouter()


def criar_tabelas(con):
    con.execute("""create table if not exists manutencoes (id integer primary key, titulo text not null, descricao text,
                   inicio integer not null, fim integer not null, criado_por text, criado_em integer, zabbix_id text,
                   avisado_1h integer default 0, cancelada_em integer)""")


def _hm(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")


def em_andamento():
    agora = int(time.time())
    with db() as con:
        return bool(con.execute("select 1 from manutencoes where cancelada_em is null and inicio<=? and fim>?", (agora, agora)).fetchone())


agenda.SILENCIOS.append(em_andamento)  # sem avisos de alerta no Telegram durante a janela


def _todos_com_telegram():
    with db() as con:
        return [r[0] for r in con.execute("select id from usuarios where ativo=1 and telegram_chat_id is not null")]


class NovaManutencao(BaseModel):
    titulo: str = Field(min_length=4, max_length=120)
    descricao: str = Field("", max_length=1000)
    inicio: int
    fim: int


@router.get("/api/manutencoes")
def listar(_=auth.exigir("visao")):
    """Em andamento, próximas e as dos últimos 30 dias (o cliente usa para a faixa do painel)."""
    with db() as con:
        return [dict(r) for r in con.execute(
            "select id, titulo, descricao, inicio, fim, criado_por, cancelada_em from manutencoes where fim>? order by inicio",
            (int(time.time()) - 30 * 86400,))]


@router.post("/api/manutencoes", status_code=201)
def agendar(m: NovaManutencao, u=auth.exigir("manutencao")):
    if m.fim <= m.inicio:
        raise HTTPException(422, "O fim precisa ser depois do início.")
    if m.fim < time.time():
        raise HTTPException(422, "Essa janela já terminou.")
    zid = None
    if not fonte.SIMULACAO:
        h = fonte.call("host.get", {"filter": {"host": [fonte.HOST]}, "output": ["hostid"]})[0]
        zid = fonte.call("maintenance.create", {
            "name": f"SennaGuard: {m.titulo} ({_hm(m.inicio)})", "active_since": m.inicio, "active_till": m.fim,
            "hostids": [h["hostid"]], "maintenance_type": 0,
            "timeperiods": [{"timeperiod_type": 0, "start_date": m.inicio, "period": m.fim - m.inicio}]})["maintenanceids"][0]
    with db() as con:
        mid = con.execute("insert into manutencoes (titulo, descricao, inicio, fim, criado_por, criado_em, zabbix_id) values (?,?,?,?,?,?,?)",
                          (m.titulo, m.descricao, m.inicio, m.fim, u["nome"], int(time.time()), zid)).lastrowid
    tempo_real.avisar("manutencao")
    telegram.para_usuarios(_todos_com_telegram(), f"🛠 <b>Manutenção programada</b>\n{_e(m.titulo)}\n{_hm(m.inicio)} até {_hm(m.fim)}"
                           + (f"\n{_e(m.descricao)}" if m.descricao else ""), tipo="manutencao")
    return {"id": mid}


@router.delete("/api/manutencoes/{mid}", status_code=204)
def cancelar(mid: int, _=auth.exigir("manutencao")):
    with db() as con:
        r = con.execute("select titulo, zabbix_id, inicio from manutencoes where id=? and cancelada_em is null", (mid,)).fetchone()
        if not r:
            raise HTTPException(404, "Manutenção não encontrada.")
        con.execute("update manutencoes set cancelada_em=? where id=?", (int(time.time()), mid))
    if r["zabbix_id"] and not fonte.SIMULACAO:
        fonte.call("maintenance.delete", [r["zabbix_id"]])
    tempo_real.avisar("manutencao")
    telegram.para_usuarios(_todos_com_telegram(), f"✖️ Manutenção cancelada: {_e(r['titulo'])} ({_hm(r['inicio'])})", tipo="manutencao")


@agenda.tarefa(60)
def avisar_uma_hora_antes():
    agora = int(time.time())
    with db() as con:
        proximas = con.execute("select id, titulo, inicio, fim from manutencoes where cancelada_em is null and avisado_1h=0 and inicio>? and inicio<=?",
                               (agora, agora + 3600)).fetchall()
        for p in proximas:
            con.execute("update manutencoes set avisado_1h=1 where id=?", (p["id"],))
    for p in proximas:
        telegram.para_usuarios(_todos_com_telegram(), f"⏰ Em 1 hora: manutenção <b>{_e(p['titulo'])}</b>, das {_hm(p['inicio'])} às {_hm(p['fim'])}.", tipo="manutencao")
    tempo_real.avisar("manutencao")  # a faixa do painel muda sozinha quando a janela começa ou termina
