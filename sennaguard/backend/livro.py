"""Leitura e verificação do livro de chamados (mesmo formato de noc/chamados.py do noc-senai-tcc).

Cada linha guarda o hash SHA-256 dela somado ao hash da linha anterior; alterar, apagar ou reordenar
qualquer linha quebra a cadeia, e a verificação aponta onde.
"""
import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

LIVRO = Path(os.environ.get("NOC_LIVRO", Path(__file__).parent / "dados" / "chamados.jsonl"))


def _hash(anterior, registro):
    corpo = json.dumps(registro, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((anterior + corpo).encode()).hexdigest()


def linhas():
    try:
        if not LIVRO.exists():
            return []
        return [json.loads(l) for l in LIVRO.read_text(encoding="utf-8").splitlines() if l.strip()]
    except PermissionError:  # o instalador dá leitura ao grupo sennaguard; sem isso, a lista fica vazia
        return []


def verificar():
    """Devolve {"ok": bool, "registros": n, "quebra": seq|None, "motivo": str}."""
    anterior = "0" * 64
    regs = linhas()
    for r in regs:
        if r.get("hash_anterior") != anterior:
            return {"ok": False, "registros": len(regs), "quebra": r.get("seq"), "motivo": "registro fora de ordem ou apagado"}
        if _hash(anterior, {k: v for k, v in r.items() if k != "hash"}) != r.get("hash"):
            return {"ok": False, "registros": len(regs), "quebra": r.get("seq"), "motivo": "conteúdo alterado depois de gravado"}
        anterior = r["hash"]
    return {"ok": True, "registros": len(regs), "quebra": None, "motivo": ""}


def chamados():
    """Junta abertura e encerramento de cada chamado num item só, do mais novo para o mais velho."""
    por_num = {}
    for r in linhas():
        c = por_num.setdefault(r["chamado"], {"numero": r["chamado"], "eventid": r["eventid"], "host": r["host"],
                                              "nome": r["nome"], "severidade": r["severidade"], "inicio": r["inicio"],
                                              "status": "aberto", "fim": "", "duracao": "", "registros": []})
        c["registros"].append({"seq": r["seq"], "acao": r["acao"], "em": r["registrado_em"], "hash": r["hash"]})
        if r["acao"] == "encerramento":
            c.update(status="encerrado", fim=r.get("fim", ""), duracao=r.get("duracao", ""))
    return sorted(por_num.values(), key=lambda c: c["inicio"], reverse=True)


def semear_exemplo():
    """Cria um livro de exemplo, com cadeia válida, para o modo simulação.
    Regravado a cada início para casar com os horários dos alertas simulados."""
    LIVRO.parent.mkdir(parents=True, exist_ok=True)
    agora = datetime.now().astimezone().replace(microsecond=0)
    casos = [
        (31207, "Link FIBRA caiu: failover para RÁDIO ativo", "Alta", 52, 1, "1h 12m 40s"),
        (30988, "FILIAL ISOLADA: Fibra e Rádio indisponíveis", "Desastre", 74, 3, "1h 41m 05s"),
        (30512, "Link RÁDIO (backup) caiu: rede sem redundância", "Média", 140, 6, "2h 03m 18s"),
        (31415, "Link RÁDIO (backup) caiu: rede sem redundância", "Média", 80 / 60, 0, None),
    ]
    anterior, seq, saida = "0" * 64, 0, []
    eventos = []
    for eid, nome, sev, horas_atras, _, dur in casos:
        inicio = agora - timedelta(hours=horas_atras)
        eventos.append((inicio + timedelta(hours=1), "abertura", eid, nome, sev, inicio, "", ""))
        if dur:
            h, m, s = [int(x[:-1]) for x in dur.split()]
            fim = inicio + timedelta(hours=h, minutes=m, seconds=s)
            eventos.append((fim, "encerramento", eid, nome, sev, inicio, dur, fim))
    for em, acao, eid, nome, sev, inicio, dur, fim in sorted(eventos, key=lambda e: e[0]):
        seq += 1
        r = {"seq": seq, "acao": acao, "chamado": f"NOC-{eid}", "registrado_em": em.isoformat(),
             "eventid": str(eid), "host": "R-FILIAL", "nome": nome, "severidade": sev,
             "inicio": inicio.isoformat(), "duracao": dur, "fim": fim.isoformat() if fim else "",
             "hash_anterior": anterior}
        r["hash"] = anterior = _hash(anterior, r)
        saida.append(json.dumps(r, ensure_ascii=False))
    LIVRO.write_text("\n".join(saida) + "\n", encoding="utf-8")
