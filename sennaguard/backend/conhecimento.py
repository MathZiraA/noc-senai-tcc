"""Base de conhecimento: quando um chamado é resolvido, a IA rascunha problema, causa e solução; um analista revisa e publica.
Os artigos publicados aparecem como sugestão quando alguém descreve um problema parecido ao abrir um chamado.
"""
import json
import logging
import re
import threading
import time
import unicodedata

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import auth
import ia
import tempo_real
from banco import db

router = APIRouter()
log = logging.getLogger("sennaguard.conhecimento")
VAZIAS = set("a o e de da do das dos em no na nos nas um uma para por com sem que se ao os as foi esta esta muito".split())


def criar_tabelas(con, simulacao=False):
    con.execute("""create table if not exists artigos (id integer primary key, titulo text not null, problema text, causa text,
                   solucao text, categoria text, origem_chamado integer, status text default 'rascunho', autor text,
                   criado_em integer, atualizado_em integer)""")
    if simulacao and not con.execute("select 1 from artigos").fetchone():
        agora = int(time.time())
        for t, p, c, s, cat in [
            ("Sistema lento na Filial com a rede no rádio",
             "Sistemas da Filial (vendas, estoque) ficam lentos, mas a internet abre.",
             "A fibra caiu ou degradou e o tráfego passou para o rádio, que tem menos banda e mais latência (~6 ms contra 0,6 ms).",
             "Confira no painel se o caminho ativo é o rádio. Se for, a lentidão é esperada até a fibra voltar; o NOC já é avisado sozinho. "
             "Se o caminho for a fibra, abra um chamado com o nome do sistema e do computador.", "lentidao"),
            ("Computador da Filial sem rede depois de trocar de lugar",
             "Um computador ficou sem acesso depois de ser mudado de mesa.",
             "O cabo foi ligado na porta ether5 do switch, que fica sem link na configuração atual.",
             "Ligue o cabo numa porta da rede local (ether3 ou ether4) ou peça ao NOC para habilitar a porta.", "sem_acesso"),
            ("Quedas rápidas de conexão a cada poucos minutos",
             "A conexão cai por alguns segundos e volta sozinha, várias vezes por hora.",
             "Conector LC da fibra sujo ou mal encaixado no sfp1: a fibra oscila e o OSPF fica trocando de caminho.",
             "O NOC limpa e reencaixa o conector LC do sfp1 na Filial e acompanha o alerta 'Link FIBRA instável' por 24 h.", "instavel"),
        ]:
            con.execute("insert into artigos (titulo, problema, causa, solucao, categoria, status, autor, criado_em, atualizado_em) values (?,?,?,?,?,?,?,?,?)",
                        (t, p, c, s, cat, "publicado", "noc-analista", agora - 86400 * 9, agora - 86400 * 9))


def _palavras(texto):
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return {p for p in re.findall(r"[a-z0-9]{3,}", t) if p not in VAZIAS}


def buscar(consulta, limite=10, incluir_rascunhos=False):
    """Ordena pelos termos em comum com título (peso 3), problema (2) e solução/causa (1)."""
    termos = _palavras(consulta)
    with db() as con:
        artigos = [dict(r) for r in con.execute("select * from artigos" + ("" if incluir_rascunhos else " where status='publicado'"))]
    if not termos:
        return sorted(artigos, key=lambda a: -a["atualizado_em"])[:limite]
    pontuados = []
    for a in artigos:
        nota = 3 * len(termos & _palavras(a["titulo"])) + 2 * len(termos & _palavras(a["problema"])) \
            + len(termos & _palavras(f"{a['causa']} {a['solucao']}"))
        if nota:
            pontuados.append((nota, a))
    return [a for _, a in sorted(pontuados, key=lambda x: -x[0])][:limite]


def rascunhar_de_chamado(cid: int):
    """Chamado resolvido -> rascunho de artigo (IA quando houver; senão, montado do próprio chamado). Roda em segundo plano."""
    def trabalho():
        with db() as con:
            c = con.execute("select * from chamados_manuais where id=?", (cid,)).fetchone()
            regs = con.execute("select autor_nome, autor_papel, acao, texto from chamado_registros where chamado_id=? order by seq", (cid,)).fetchall()
            if not c or con.execute("select 1 from artigos where origem_chamado=?", (cid,)).fetchone():
                return
        # Notas internas ficam fora: o artigo publicado é lido pelo cliente
        conversa = "\n".join(f"[{r['autor_papel']}] {r['autor_nome']} ({r['acao']}): {r['texto']}"
                             for r in regs if r["texto"] and r["acao"] != "nota")
        rascunho = None
        if ia.provedor():
            try:
                bruto = ia.gerar(
                    "Você escreve artigos curtos para a base de conhecimento de um NOC. Responda APENAS um JSON com as chaves "
                    "titulo, problema, causa, solucao (português, frases curtas, sem dados pessoais).",
                    f"Chamado SG-{cid}: {c['titulo']}\nDescrição: {c['descricao']}\nEstado do enlace na abertura: {c['contexto']}\n\nHistórico:\n{conversa}")
                rascunho = json.loads(bruto[bruto.index("{"):bruto.rindex("}") + 1])
            except Exception as e:
                log.warning("IA não rascunhou o artigo do SG-%s: %s", cid, e)
        if not rascunho:
            ultima = next((r["texto"] for r in reversed(regs) if r["autor_papel"] != "Cliente" and r["acao"] == "comentario"), "")
            rascunho = {"titulo": c["titulo"], "problema": c["descricao"], "causa": "", "solucao": ultima}
        agora = int(time.time())
        with db() as con:
            con.execute("insert into artigos (titulo, problema, causa, solucao, categoria, origem_chamado, status, autor, criado_em, atualizado_em) values (?,?,?,?,?,?,?,?,?,?)",
                        (str(rascunho.get("titulo", c["titulo"]))[:120], rascunho.get("problema", ""), rascunho.get("causa", ""),
                         rascunho.get("solucao", ""), c["categoria"], cid, "rascunho", "IA" if ia.provedor() else "SennaGuard", agora, agora))
        tempo_real.avisar("conhecimento")
    threading.Thread(target=trabalho, daemon=True).start()


class Artigo(BaseModel):
    titulo: str = Field(min_length=4, max_length=120)
    problema: str = Field("", max_length=3000)
    causa: str = Field("", max_length=3000)
    solucao: str = Field(min_length=4, max_length=4000)
    categoria: str = "outro"
    status: str = Field("rascunho", pattern="^(rascunho|publicado)$")


@router.get("/api/conhecimento")
def listar(q: str = "", u=auth.exigir("conhecimento")):
    return buscar(q, 50, incluir_rascunhos="editar_conhecimento" in auth.PERMISSOES[u["papel"]])


@router.get("/api/conhecimento/sugestoes")
def sugestoes(q: str, _=auth.exigir("conhecimento")):
    return [{k: a[k] for k in ("id", "titulo", "problema", "solucao")} for a in buscar(q, 3)] if len(q) >= 8 else []


@router.post("/api/conhecimento", status_code=201)
def criar(a: Artigo, u=auth.exigir("editar_conhecimento")):
    agora = int(time.time())
    with db() as con:
        aid = con.execute("insert into artigos (titulo, problema, causa, solucao, categoria, status, autor, criado_em, atualizado_em) values (?,?,?,?,?,?,?,?,?)",
                          (a.titulo, a.problema, a.causa, a.solucao, a.categoria, a.status, u["nome"], agora, agora)).lastrowid
    tempo_real.avisar("conhecimento")
    return {"id": aid}


@router.put("/api/conhecimento/{aid}", status_code=204)
def editar(aid: int, a: Artigo, u=auth.exigir("editar_conhecimento")):
    with db() as con:
        if not con.execute("update artigos set titulo=?, problema=?, causa=?, solucao=?, categoria=?, status=?, autor=?, atualizado_em=? where id=?",
                           (a.titulo, a.problema, a.causa, a.solucao, a.categoria, a.status, u["nome"], int(time.time()), aid)).rowcount:
            raise HTTPException(404, "Artigo não encontrado.")
    tempo_real.avisar("conhecimento")


@router.delete("/api/conhecimento/{aid}", status_code=204)
def remover(aid: int, _=auth.exigir("editar_conhecimento")):
    with db() as con:
        con.execute("delete from artigos where id=?", (aid,))
    tempo_real.avisar("conhecimento")
