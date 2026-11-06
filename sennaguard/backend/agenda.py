"""Tarefas em segundo plano do SennaGuard numa única thread: vigiar o enlace e os alertas, ler o Telegram,
relatório mensal, avisos de manutenção, backups e testes agendados (cada módulo registra a sua).
"""
import json
import logging
import threading
import time

import fonte
import telegram
import tempo_real
from html import escape as _e  # texto de usuário nas mensagens HTML do Telegram

log = logging.getLogger("sennaguard.agenda")
TAREFAS: list[list] = []  # [intervalo em s, função, última execução]
SILENCIOS = []            # funções que dizem se os avisos estão suspensos agora (ex.: janela de manutenção)
_iniciada = threading.Event()


def tarefa(intervalo):
    def registrar(fn):
        TAREFAS.append([intervalo, fn, 0.0])
        return fn
    return registrar


def silenciado():
    return any(f() for f in SILENCIOS)


def _laco():
    while True:
        for t in TAREFAS:
            if time.time() - t[2] >= t[0]:
                t[2] = time.time()
                try:
                    t[1]()
                except Exception:
                    log.exception("tarefa %s falhou", t[1].__name__)
        time.sleep(1)


def iniciar():
    if not _iniciada.is_set():
        _iniciada.set()
        threading.Thread(target=_laco, name="agenda", daemon=True).start()


# ---------------------------------------------------------------- vigias de sempre
_estado = {"visao": None, "alertas": None, "caminho": None}
TIPO_ALERTA = {5: "desastre", 4: "alta", 3: "media"}


@tarefa(5)
def vigiar_enlace():
    v = fonte.visao()
    assinatura = json.dumps([v["caminho"], v["enlaces"]["fibra"]["up"], v["enlaces"]["radio"]["up"]])
    if assinatura != _estado["visao"]:
        _estado["visao"] = assinatura
        tempo_real.avisar("visao")
    antes, _estado["caminho"] = _estado["caminho"], v["caminho"]
    if antes and antes != v["caminho"] and not silenciado():
        texto = ("📡 A Filial passou para o <b>rádio</b>: a fibra parou de responder." if v["caminho"] == "radio"
                 else "🟢 A Filial voltou para a <b>fibra</b>.")
        telegram.para_equipe(texto, preferencia="alerta_email", tipo="caminho")


@tarefa(5)
def vigiar_alertas():
    ativos = {a["id"]: a for a in fonte.alertas(24) if a["ativo"]}
    anteriores = _estado["alertas"]
    _estado["alertas"] = set(ativos)
    if anteriores is None or set(ativos) == anteriores:
        return
    tempo_real.avisar("alertas")
    if silenciado():
        return
    for eid in set(ativos) - anteriores:
        a = ativos[eid]
        if a["nivel"] >= 3:  # Média ou mais grave
            icone = "🔴" if a["nivel"] >= 4 else "🟣"
            telegram.para_equipe(f"{icone} <b>{a['severidade']}</b> · {_e(a['host'])}\n{_e(a['nome'])}", preferencia="alerta_email",
                                 tipo=TIPO_ALERTA[min(a["nivel"], 5)], urgente=a["nivel"] >= 5)


@tarefa(3)
def ler_telegram():
    telegram.ler_mensagens()
