"""Gera a página de status para os usuários da Filial (cron a cada minuto).
Publicada pelo Apache em https://<servidor>/status."""
import html
import time
from datetime import datetime, timedelta
from pathlib import Path

import chamados
import config
from zbx import call

HOST = config.HOST
SAIDA = Path("/var/www/html/status/index.html")
DIAS = 7
# Só ocorrências que o usuário sente, em linguagem simples
OCORRENCIAS = {
    "FILIAL ISOLADA": ("Filial sem conexão com a Matriz", "critico"),
    "Link FIBRA caiu": ("Link principal interrompido — serviço mantido pelo link reserva", "aviso"),
    "Filial sem comunicação": ("Interrupção na conexão com a Matriz", "aviso"),
    "Link RÁDIO (backup) caiu": ("Link reserva indisponível — sem impacto para os usuários", "info"),
}
SITUACOES = {
    0: ("critico", "Sem conexão com a Matriz",
        "Sistemas da Matriz estão inacessíveis a partir da Filial. A equipe de rede já foi alertada."),
    1: ("aviso", "Funcionando pelo link reserva",
        "O link principal está fora e a Filial opera pelo link de rádio. Tudo continua acessível, "
        "mas pode ficar um pouco mais lento."),
    2: ("ok", "Funcionando normalmente", "A conexão entre a Filial e a Matriz está estável pelo link principal."),
}


def item(chave, campos=("itemid", "lastvalue", "lastclock", "value_type")):
    return call("item.get", {"host": HOST, "filter": {"key_": chave}, "output": list(campos)})[0]


def duracao(segundos):
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min"
    return f"{segundos // 3600} h {segundos % 3600 // 60:02d} min"


agora = int(time.time())
host = call("host.get", {"filter": {"host": [HOST]}, "output": ["hostid", "maintenance_status"]})[0]
caminho = item("noc.caminho_ativo")
classe, titulo, texto = SITUACOES[min(int(caminho["lastvalue"] or 0), 2)]
atualizado = int(caminho["lastclock"])
if agora - atualizado > 120:
    classe, titulo, texto = ("info", "Sem dados recentes", "O monitoramento não recebe medições há mais de 2 minutos.")

# Disponibilidade = parcela das medições com algum caminho até a Filial
hist = call("history.get", {"itemids": caminho["itemid"], "history": 3, "time_from": agora - DIAS * 86400,
                            "sortfield": "clock", "sortorder": "ASC", "limit": 200000, "output": ["clock", "value"]})


def disponibilidade(desde, ate):
    amostras = [int(v["value"]) for v in hist if desde <= int(v["clock"]) < ate]
    return None if not amostras else 100 * sum(1 for v in amostras if v > 0) / len(amostras)


hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
barras = []
for d in range(DIAS - 1, -1, -1):
    dia = hoje - timedelta(days=d)
    pct = disponibilidade(int(dia.timestamp()), int((dia + timedelta(days=1)).timestamp()))
    cor = "vazio" if pct is None else "ok" if pct >= 99.9 else "aviso" if pct >= 95 else "critico"
    rotulo = f"{dia:%d/%m}: " + ("sem dados" if pct is None else f"{pct:.2f}% disponível".replace(".", ","))
    barras.append(f'<div class="dia {cor}" title="{rotulo}"><span>{dia:%d/%m}</span></div>')
d24, d7 = disponibilidade(agora - 86400, agora), disponibilidade(agora - DIAS * 86400, agora)

# Ocorrências dos últimos 7 dias
trgs = call("trigger.get", {"hostids": host["hostid"], "inherited": False, "output": ["triggerid", "description"]})
mapa = {t["triggerid"]: next(((n, c) for p, (n, c) in OCORRENCIAS.items() if t["description"].startswith(p)), None)
        for t in trgs}
alvo = [tid for tid, v in mapa.items() if v]
eventos = call("event.get", {"objectids": alvo, "source": 0, "object": 0, "value": 1, "sortfield": ["clock"],
                             "sortorder": "DESC", "time_from": agora - DIAS * 86400, "limit": 30,
                             "output": ["clock", "objectid", "r_eventid"]}) if alvo else []
rec_ids = [e["r_eventid"] for e in eventos if e["r_eventid"] != "0"]
recs = {r["eventid"]: int(r["clock"]) for r in
        (call("event.get", {"eventids": rec_ids, "output": ["eventid", "clock"]}) if rec_ids else [])}
# Uma queda total gera "FILIAL ISOLADA" e "sem comunicação" juntos: mostra só a mais grave
isoladas = [(int(e["clock"]) - 120, recs.get(e["r_eventid"], agora)) for e in eventos
            if mapa[e["objectid"]][1] == "critico"]
linhas = []
for e in eventos:
    nome, cor = mapa[e["objectid"]]
    if nome.startswith("Interrupção") and any(ini <= int(e["clock"]) <= fim for ini, fim in isoladas):
        continue
    inicio = int(e["clock"])
    fim = recs.get(e["r_eventid"])
    estado = f"Resolvido em {duracao(fim - inicio)}" if fim else "Em andamento"
    linhas.append(f'<li class="{cor}"><div><strong>{html.escape(nome)}</strong>'
                  f'<small>{datetime.fromtimestamp(inicio):%d/%m às %H:%M}</small></div>'
                  f'<span class="{"resolvido" if fim else "andamento"}">{estado}</span></li>')

failover = item("noc.failover.segundos")
extra = (f'<p class="nota">Última troca automática para o link reserva: os usuários ficaram '
         f'{failover["lastvalue"]} s sem conexão ({datetime.fromtimestamp(int(failover["lastclock"])):%d/%m às %H:%M}).</p>'
         if failover["lastclock"] != "0" else "")
implantacao = ('<div class="faixa">Ambiente em implantação: a rede da Filial ainda está sendo montada, '
               'então os dados abaixo não refletem a operação real.</div>' if host["maintenance_status"] == "1" else "")
fmt = lambda p: "—" if p is None else f"{p:.2f}%".replace(".", ",")

# Chamados (quedas acima do prazo), do livro encadeado por SHA-256; simulações de teste ficam de fora
limite_chamados = (datetime.now() - timedelta(days=DIAS)).astimezone().isoformat()
lista_chamados = [c for c in reversed(chamados.listar()) if not c["host"].startswith("SIMULA")
                  and c.get("aberto_em", "") >= limite_chamados]
livro_ok, _ = chamados.verificar()
linhas_chamados = "".join(
    f'<li class="{"info" if c.get("encerrado_em") else "critico"}"><div><strong>{html.escape(c["chamado"])} · '
    f'{html.escape(c["nome"])}</strong><small>aberto em {c["aberto_em"][:16].replace("T", " ")}</small></div>'
    f'<span class="{"resolvido" if c.get("encerrado_em") else "andamento"}">'
    f'{"Encerrado: " + c["duracao_total"] if c.get("encerrado_em") else "Em aberto"}</span></li>'
    for c in lista_chamados)
secao_chamados = (f'<section><h3>Chamados dos últimos {DIAS} dias</h3>'
                  + (f"<ul>{linhas_chamados}</ul>" if linhas_chamados else '<p class="vazia">Nenhum chamado aberto no período.</p>')
                  + f'<p class="nota">Chamado é aberto quando uma queda dura mais que {config.C["CHAMADO_APOS"]}. '
                  + ("Registro íntegro (SHA-256)." if livro_ok else "ATENÇÃO: o livro de chamados não passou na verificação de integridade.")
                  + "</p></section>")

pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Status da Rede — Filial</title>
<style>
:root {{ --fundo:#f5f7fa; --cartao:#ffffff; --texto:#1f2933; --suave:#616e7c; --borda:#e4e7eb;
        --ok:#2e7d32; --aviso:#ed6c02; --critico:#d32f2f; --info:#546e7a; --vazio:#cbd2d9; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --fundo:#111418; --cartao:#1b1f24; --texto:#e4e7eb; --suave:#9aa5b1; --borda:#2c333a; --vazio:#3e4c59; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--fundo); color:var(--texto);
       font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
main {{ max-width:760px; margin:0 auto; padding:32px 16px 48px; }}
header h1 {{ font-size:22px; margin:0; }} header p {{ color:var(--suave); margin:4px 0 24px; }}
.faixa {{ background:var(--info); color:#fff; padding:10px 14px; border-radius:8px; margin-bottom:16px; font-size:14px; }}
.situacao {{ border-radius:12px; padding:22px; color:#fff; margin-bottom:24px; }}
.situacao h2 {{ margin:0 0 6px; font-size:24px; }} .situacao p {{ margin:0; opacity:.95; }}
.situacao.ok {{ background:var(--ok); }} .situacao.aviso {{ background:var(--aviso); }}
.situacao.critico {{ background:var(--critico); }} .situacao.info {{ background:var(--info); }}
section {{ background:var(--cartao); border:1px solid var(--borda); border-radius:12px; padding:20px; margin-bottom:20px; }}
section h3 {{ margin:0 0 14px; font-size:16px; }}
.numeros {{ display:flex; gap:32px; margin-bottom:16px; flex-wrap:wrap; }}
.numeros b {{ display:block; font-size:28px; }} .numeros span {{ color:var(--suave); font-size:14px; }}
.barras {{ display:grid; grid-template-columns:repeat({DIAS},1fr); gap:6px; }}
.dia {{ height:40px; border-radius:6px; position:relative; }}
.dia span {{ position:absolute; bottom:-22px; left:0; right:0; text-align:center; font-size:12px; color:var(--suave); }}
.dia.ok {{ background:var(--ok); }} .dia.aviso {{ background:var(--aviso); }}
.dia.critico {{ background:var(--critico); }} .dia.vazio {{ background:var(--vazio); }}
.legenda {{ margin-top:30px; font-size:13px; color:var(--suave); }}
ul {{ list-style:none; margin:0; padding:0; }}
li {{ display:flex; justify-content:space-between; gap:12px; align-items:center; padding:12px 0 12px 12px;
      border-bottom:1px solid var(--borda); border-left:4px solid var(--info); }}
li:last-child {{ border-bottom:0; }} li.critico {{ border-left-color:var(--critico); }}
li.aviso {{ border-left-color:var(--aviso); }} li small {{ display:block; color:var(--suave); }}
.resolvido {{ color:var(--ok); font-size:14px; white-space:nowrap; }}
.andamento {{ color:var(--critico); font-weight:600; font-size:14px; white-space:nowrap; }}
.nota, .vazia {{ color:var(--suave); font-size:14px; }}
footer {{ color:var(--suave); font-size:13px; text-align:center; }}
</style>
</head>
<body>
<main>
<header><h1>Status da conexão Filial ↔ Matriz</h1>
<p>Página informativa da equipe de rede. Atualiza sozinha a cada minuto.</p></header>
{implantacao}
<div class="situacao {classe}"><h2>{titulo}</h2><p>{texto}</p></div>
<section><h3>Disponibilidade</h3>
<div class="numeros"><div><b>{fmt(d24)}</b><span>últimas 24 horas</span></div>
<div><b>{fmt(d7)}</b><span>últimos {DIAS} dias</span></div></div>
<div class="barras">{"".join(barras)}</div>
<p class="legenda">Verde: 99,9% ou mais · Laranja: 95% a 99,9% · Vermelho: abaixo de 95% · Cinza: sem dados</p>
{extra}</section>
<section><h3>Ocorrências dos últimos {DIAS} dias</h3>
{"<ul>" + "".join(linhas) + "</ul>" if linhas else '<p class="vazia">Nenhuma ocorrência no período.</p>'}
</section>
{secao_chamados}
<footer>Atualizado em {datetime.fromtimestamp(agora):%d/%m/%Y às %H:%M:%S} · Monitoramento NOC SENAI</footer>
</main>
</body>
</html>
"""
SAIDA.parent.mkdir(parents=True, exist_ok=True)
temporario = SAIDA.with_suffix(".tmp")
temporario.write_text(pagina, encoding="utf-8")
temporario.replace(SAIDA)
