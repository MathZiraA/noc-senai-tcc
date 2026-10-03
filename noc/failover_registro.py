"""Registra no item "Tempo de failover medido" cada nova queda da fibra (cron a cada minuto).
Espera a janela de medição fechar (3 min) antes de gravar, e nunca grava a mesma queda duas vezes."""
import json
import time
from pathlib import Path

import ferramentas
from zbx import call

HOST = "R-FILIAL"
ESTADO = Path("/var/lib/noc-analista/failover_registrado.json")

ultimo = json.loads(ESTADO.read_text())["ultimo"] if ESTADO.exists() else 0
agora = int(time.time())
novos = [f for f in ferramentas.failovers(HOST, 2)
         if f["evento"] == "queda" and f["voltou"] and ultimo < f["inicio"] < agora - 200]
for f in novos:
    call("history.push", [{"host": HOST, "key": "noc.failover.segundos", "value": f["segundos"], "clock": f["inicio"]}])
    print(f"failover de {f['segundos']} s registrado ({ferramentas._hora(f['inicio'])})")
if novos:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps({"ultimo": max(f["inicio"] for f in novos)}))
