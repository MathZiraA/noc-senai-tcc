"""Sonda própria de 1 s nos dois enlaces, para a tela reagir na hora (o Zabbix coleta a cada 5 s).

Pinga o IP da Filial na fibra e no rádio a cada segundo, guarda os últimos 30 min em memória e avisa o canal
"visao" assim que um enlace cai ou volta. A queda só conta depois de 2 pings perdidos seguidos (~2 s), para um
pacote perdido não virar alarme; a volta conta no primeiro ping respondido.
"""
import re
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import tempo_real

QUEDA_APOS = 2           # pings perdidos seguidos para considerar o enlace fora
VALIDADE = 5             # s sem leitura nova = sonda parada, a tela volta a usar o Zabbix
HISTORICO = deque(maxlen=1800)  # 30 min, 1 ponto por segundo: {"t", "fibra", "radio"} em ms (None = sem resposta)
ESTADO: dict[str, dict] = {}
_iniciada = threading.Event()
_tempo = re.compile(r"time[=<]([\d.]+)")


def _pingar(ip: str):
    """Latência em ms, ou None sem resposta em 1 s."""
    try:
        r = subprocess.run(["ping", "-n", "-c", "1", "-W", "1", ip], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = _tempo.search(r.stdout) if r.returncode == 0 else None
    return round(float(m.group(1)), 2) if m else None


def _laco(alvos: dict[str, str]):
    falhas = {nome: 0 for nome in alvos}
    with ThreadPoolExecutor(len(alvos)) as pool:
        while True:
            inicio = time.time()
            leituras = dict(zip(alvos, pool.map(_pingar, alvos.values())))
            agora = int(inicio)
            mudou = False
            for nome, ms in leituras.items():
                falhas[nome] = 0 if ms is not None else falhas[nome] + 1
                up = falhas[nome] < QUEDA_APOS
                antes = ESTADO.get(nome, {}).get("up")
                ESTADO[nome] = {"up": up, "latencia": ms, "t": agora}
                mudou |= antes is not None and antes != up
            HISTORICO.append({"t": agora, **leituras})
            if mudou:
                tempo_real.avisar("visao")
            time.sleep(max(0.0, 1 - (time.time() - inicio)))


def iniciar(fibra_ip: str, radio_ip: str):
    if not _iniciada.is_set():
        _iniciada.set()
        threading.Thread(target=_laco, args=({"fibra": fibra_ip, "radio": radio_ip},), name="sonda", daemon=True).start()


def ativa() -> bool:
    return all(time.time() - ESTADO.get(n, {}).get("t", 0) <= VALIDADE for n in ("fibra", "radio"))


def serie(desde: int, ate: int) -> list[dict]:
    return [p for p in HISTORICO if desde <= p["t"] <= ate]
