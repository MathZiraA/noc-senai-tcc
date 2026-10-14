"""Livro de chamados do NOC: registro só de acréscimo, encadeado por SHA-256 (segurança jurídica).

Cada linha de /var/lib/noc-analista/chamados.jsonl guarda o evento (abertura ou encerramento) e o hash
dela calculado junto com o hash da linha anterior. Alterar, apagar ou reordenar qualquer linha quebra a
cadeia, e a verificação aponta exatamente onde.

Uso:  python chamados.py --listar      mostra os chamados
      python chamados.py --verificar   confere a integridade de todo o livro
"""
import argparse
import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path

LIVRO = Path("/var/lib/noc-analista/chamados.jsonl")
_trava = threading.Lock()


def numero(eventid):
    """Mesmo formato do e-mail (NOC-{EVENT.ID}): o número tem de bater entre e-mail e livro."""
    return f"NOC-{int(eventid)}"


def _hash(anterior, registro):
    corpo = json.dumps(registro, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((anterior + corpo).encode()).hexdigest()


def _linhas():
    if not LIVRO.exists():
        return []
    return [json.loads(l) for l in LIVRO.read_text(encoding="utf-8").splitlines() if l.strip()]


def registrar(acao, dados):
    """Acrescenta um registro ('abertura' ou 'encerramento') e devolve ele com o hash."""
    with _trava:
        linhas = _linhas()
        anterior = linhas[-1]["hash"] if linhas else "0" * 64
        registro = {"seq": len(linhas) + 1, "acao": acao, "chamado": numero(dados["eventid"]),
                    "registrado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                    **{k: dados.get(k, "") for k in ("eventid", "host", "nome", "severidade", "inicio", "duracao", "fim")},
                    "hash_anterior": anterior}
        registro["hash"] = _hash(anterior, {k: v for k, v in registro.items() if k != "hash"})
        LIVRO.parent.mkdir(parents=True, exist_ok=True)
        with LIVRO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        LIVRO.chmod(0o640)
        return registro


def aberto(eventid):
    """True se o evento tem abertura e ainda não tem encerramento."""
    acoes = [r["acao"] for r in _linhas() if r["eventid"] == str(eventid)]
    return "abertura" in acoes and "encerramento" not in acoes


def verificar():
    """Devolve (ok, mensagem). Recalcula a cadeia inteira."""
    anterior = "0" * 64
    for i, r in enumerate(_linhas(), 1):
        if r.get("seq") != i or r.get("hash_anterior") != anterior:
            return False, f"registro {i}: sequência ou encadeamento quebrado (linha removida ou reordenada)"
        if _hash(anterior, {k: v for k, v in r.items() if k != "hash"}) != r.get("hash"):
            return False, f"registro {i} ({r.get('chamado')}): conteúdo alterado depois de gravado"
        anterior = r["hash"]
    return True, f"livro íntegro: {len(_linhas())} registros, último hash {anterior[:16]}..."


def listar(dias=None):
    """Chamados (um por evento) com abertura, encerramento e duração."""
    por_evento = {}
    for r in _linhas():
        c = por_evento.setdefault(r["eventid"], {"chamado": r["chamado"], "host": r["host"], "nome": r["nome"]})
        if r["acao"] == "abertura":
            c.update(aberto_em=r["registrado_em"], inicio=r["inicio"], duracao_na_abertura=r["duracao"])
        else:
            c.update(encerrado_em=r["registrado_em"], fim=r["fim"], duracao_total=r["duracao"])
    return list(por_evento.values())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listar", action="store_true")
    p.add_argument("--verificar", action="store_true")
    a = p.parse_args()
    if a.verificar or not a.listar:
        ok, msg = verificar()
        print(("[ok] " if ok else "[ALERTA] ") + msg)
    if a.listar:
        for c in listar():
            print(f"{c['chamado']} | {c['host']} | {c['nome']} | aberto {c.get('aberto_em', '-')} | "
                  f"encerrado {c.get('encerrado_em', 'EM ABERTO')} | duração {c.get('duracao_total', '-')}")
