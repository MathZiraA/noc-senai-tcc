"""Backup diário das configurações do R-MATRIZ e do R-FILIAL (às 3 h), com histórico e diferença entre versões.

Usa o mesmo acesso do Analista IA: SSH com chave, usuário zabbix-ia (grupo read), comando `/export terse`
(sem senhas). Uma versão nova só é gravada quando a configuração muda; aí os administradores são avisados.
"""
import difflib
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

import agenda
import auth
import fonte
import ia
import telegram
import tempo_real
from banco import BANCO, db
from html import escape as _e  # texto de usuário nas mensagens HTML do Telegram

router = APIRouter()
PASTA = Path(os.environ.get("SENNAGUARD_BACKUPS", BANCO.parent / "backups"))
CHAVE = Path(os.environ.get("SENNAGUARD_MIKROTIK_KEY", "/etc/sennaguard/mikrotik_key"))
USUARIO = os.environ.get("SENNAGUARD_MIKROTIK_USER", "zabbix-ia")
ROTEADORES = {"R-MATRIZ": os.environ.get("NOC_LOOPBACK_MATRIZ", "10.255.255.1"),
              "R-FILIAL": os.environ.get("NOC_LOOPBACK_FILIAL", "10.255.255.2")}


def _limpo(texto):
    """Tira a linha de data que o RouterOS põe no topo: senão toda exportação pareceria diferente."""
    return "\n".join(l for l in texto.strip().splitlines() if not re.match(r"^# (\d{4}-\d{2}-\d{2}|\w{3}/\d{2}/\d{4}) ", l)) + "\n"


def _exportar(host):
    if fonte.SIMULACAO:
        return _sim_export(host)
    if not CHAVE.exists():
        raise RuntimeError(f"chave SSH ausente em {CHAVE}")
    r = subprocess.run(["ssh", "-i", str(CHAVE), "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new",
                        "-o", f"UserKnownHostsFile={PASTA / 'known_hosts'}", f"{USUARIO}@{ROTEADORES[host]}", "/export terse"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300] or f"ssh saiu com código {r.returncode}")
    return r.stdout


def versoes(host):
    pasta = PASTA / host
    return sorted(pasta.glob("*.rsc"), reverse=True) if pasta.exists() else []


def fazer_backup(host):
    """Devolve (gravou, linhas_adicionadas, linhas_removidas)."""
    texto = _limpo(_exportar(host))
    anteriores = versoes(host)
    antigo = anteriores[0].read_text(encoding="utf-8") if anteriores else ""
    if texto == antigo:
        return False, 0, 0
    (PASTA / host).mkdir(parents=True, exist_ok=True)
    (PASTA / host / f"{datetime.now():%Y%m%d-%H%M%S}.rsc").write_text(texto, encoding="utf-8")
    d = list(difflib.unified_diff(antigo.splitlines(), texto.splitlines(), lineterm="", n=0))
    mais = sum(1 for l in d if l.startswith("+") and not l.startswith("+++"))
    menos = sum(1 for l in d if l.startswith("-") and not l.startswith("---"))
    tempo_real.avisar("backups")
    if anteriores:
        telegram.para_equipe(f"📝 A configuração do <b>{host}</b> mudou: +{mais} / −{menos} linhas. Veja em SennaGuard → Backups.",
                             papeis=("Administrador", "Analista"))
    return True, mais, menos


@agenda.tarefa(300)
def backup_diario():
    agora = datetime.now()
    if agora.hour != 3:
        return
    with db() as con:
        con.execute("create table if not exists marcas (chave text primary key, em integer)")
        chave = f"backup_{agora:%Y%m%d}"
        if con.execute("select 1 from marcas where chave=?", (chave,)).fetchone():
            return
        con.execute("insert into marcas values (?,?)", (chave, int(time.time())))
    for host in ROTEADORES:
        try:
            fazer_backup(host)
        except Exception as e:
            telegram.para_equipe(f"⚠️ Backup do {host} falhou: {_e(str(e))}", papeis=("Administrador",))


def _arquivo(host, nome):
    if host not in ROTEADORES or not re.fullmatch(r"\d{8}-\d{6}\.rsc", nome):
        raise HTTPException(404, "Versão não encontrada.")
    p = PASTA / host / nome
    if not p.exists():
        raise HTTPException(404, "Versão não encontrada.")
    return p


def _diferenca(host, a, b):
    va, vb = _arquivo(host, a).read_text(encoding="utf-8"), _arquivo(host, b).read_text(encoding="utf-8")
    return list(difflib.unified_diff(va.splitlines(), vb.splitlines(), fromfile=a, tofile=b, lineterm="", n=2))


@router.get("/api/backups")
def listar(_=auth.exigir("backups")):
    out = {}
    for host in ROTEADORES:
        vs = versoes(host)
        out[host] = [{"arquivo": v.name, "em": int(datetime.strptime(v.stem, "%Y%m%d-%H%M%S").timestamp()),
                      "linhas": v.read_text(encoding="utf-8").count("\n")} for v in vs[:60]]
    return out


@router.get("/api/backups/{host}/diferenca")
def diferenca(host: str, a: str, b: str, _=auth.exigir("backups")):
    return {"linhas": _diferenca(host, a, b)}


@router.get("/api/backups/{host}/{arquivo}")
def conteudo(host: str, arquivo: str, _=auth.exigir("backups")):
    return {"texto": _arquivo(host, arquivo).read_text(encoding="utf-8")}


@router.post("/api/backups/agora")
def agora(_=auth.exigir("backups")):
    out = {}
    for host in ROTEADORES:
        try:
            gravou, mais, menos = fazer_backup(host)
            out[host] = {"ok": True, "mudou": gravou, "mais": mais, "menos": menos}
        except Exception as e:
            out[host] = {"ok": False, "erro": str(e)}
    return out


@router.post("/api/backups/{host}/explicar")
def explicar(host: str, a: str, b: str, _=auth.exigir("backups")):
    linhas = _diferenca(host, a, b)
    if not linhas:
        return {"texto": "As duas versões são iguais."}
    try:
        texto = ia.gerar(
            "Você é analista de redes MikroTik (RouterOS 7). Explique em português, em até 6 tópicos curtos, o que a mudança "
            "de configuração faz na prática e se há risco para a redundância fibra/rádio (OSPF, netwatch, firewall). Seja objetivo.",
            f"Roteador {host}. Diferença (unified diff):\n" + "\n".join(linhas[:400]))
    except ia.IaIndisponivel as e:
        raise HTTPException(503, str(e))
    return {"texto": texto}


# ---------------------------------------------------------------- simulação
_BASE = """# software id = DEMO-0000
/interface bridge
add name=bridge-LAN
/interface ethernet
set [ find default-name=sfp1 ] name=sfp1-WAN-FIBRA mtu=2000
set [ find default-name=ether1 ] name=ether1-WAN-RADIO mtu=2000
/routing ospf instance
add name=ospf-1 router-id={rid}
/routing ospf interface-template
add area=backbone cost=10 interfaces=sfp1-WAN-FIBRA type=ptp
add area=backbone cost=100 interfaces=ether1-WAN-RADIO type=ptp
/ip firewall filter
add action=accept chain=input connection-state=established,related
add action=accept chain=input protocol=icmp
add action=drop chain=input
/system identity
set name={host}
"""


def _sim_export(host):
    rid = "1.1.1.1" if host == "R-MATRIZ" else "2.2.2.2"
    texto = _BASE.format(rid=rid, host=host)
    if host == "R-FILIAL":  # duas mudanças de exemplo: custo da fibra e regra de SSH
        texto = texto.replace("cost=10 interfaces=sfp1", "cost=60 interfaces=sfp1").replace("cost=100 interfaces=ether1", "cost=62 interfaces=ether1")
        texto = texto.replace("add action=drop chain=input", "add action=accept chain=input dst-port=22 protocol=tcp src-address=192.168.10.0/24\nadd action=drop chain=input")
    return f"# {datetime.now():%Y-%m-%d %H:%M:%S} by RouterOS 7.24.5\n" + texto


def semear_simulacao():
    """Cria o histórico de exemplo: R-FILIAL com 3 versões (a última mudou custo OSPF e SSH)."""
    if versoes("R-FILIAL"):
        return
    for host in ROTEADORES:
        (PASTA / host).mkdir(parents=True, exist_ok=True)
        base = _limpo(_BASE.format(rid="1.1.1.1" if host == "R-MATRIZ" else "2.2.2.2", host=host))
        (PASTA / host / f"{datetime.fromtimestamp(time.time() - 9 * 86400):%Y%m%d-%H%M%S}.rsc").write_text(base, encoding="utf-8")
    meio = base.replace("add action=accept chain=input protocol=icmp", "add action=accept chain=input protocol=icmp\nadd action=accept chain=input protocol=ospf")
    (PASTA / "R-FILIAL" / f"{datetime.fromtimestamp(time.time() - 4 * 86400):%Y%m%d-%H%M%S}.rsc").write_text(meio, encoding="utf-8")
    fazer_backup("R-FILIAL")
