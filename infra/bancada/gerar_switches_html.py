"""Gera docs/switches.html: os scripts do SW-MATRIZ e do SW-FILIAL prontos para colar, com botão de copiar.

Lê routeros/switches.rsc (a mesma fonte do gerar_configs.py), então a página nunca diverge do arquivo.
A senha pode ser digitada na página: ela só substitui o <SENHA_...> no texto copiado, no navegador de quem
está usando; não é gravada nem enviada a lugar nenhum.
Uso:  python infra\\bancada\\gerar_switches_html.py
"""
import html
from pathlib import Path

from gerar_ficha import CSS  # mesma identidade visual da ficha da bancada

RAIZ = Path(__file__).resolve().parent.parent.parent
DESTINO = RAIZ / "docs" / "switches.html"
texto = (RAIZ / "routeros" / "switches.rsc").read_text(encoding="utf-8")


def secao(nome):
    inicio = texto.index(f"# ---------------- {nome} ")
    fim = texto.find("# ----------------", inicio + 10)
    corpo = texto[inicio:fim if fim != -1 else None].strip().splitlines()[1:]  # sem a linha do título
    return "\n".join(corpo).strip()


SWITCHES = [
    ("sw-matriz", "SW-MATRIZ", "Switch da Matriz", "192.168.10.2", "R-MATRIZ", "&lt;SENHA_ADMIN_MATRIZ&gt;",
     "<SENHA_ADMIN_MATRIZ>", "Gerência só pela rede da Matriz."),
    ("sw-filial", "SW-FILIAL", "Switch da Filial", "192.168.20.2", "R-FILIAL", "&lt;SENHA_ADMIN_FILIAL&gt;",
     "<SENHA_ADMIN_FILIAL>", "Gerência pela rede da Filial e pela Matriz."),
]

EXTRA_CSS = """
.passos{margin:0;padding-left:20px;display:grid;gap:6px}
.senha{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.senha label{font-size:.9rem;color:var(--muted)}
.senha input{font:inherit;font-family:var(--f-mono);font-size:.9rem;padding:6px 10px;border:1px solid var(--line);
  border-radius:6px;background:var(--bg);color:var(--fg);min-width:0;width:16rem;max-width:100%}
.senha input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.aviso{font-size:.85rem;color:var(--muted)}
.cab-script{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
pre.script{border-radius:8px;border:1px solid var(--line);margin:0;max-height:70vh}
.ip-sw{font-size:1rem;background:var(--code-bg);padding:4px 10px;border-radius:6px;border:1px solid var(--line)}
"""

JS = """
document.querySelectorAll('.equip').forEach(function(card){
  var pre = card.querySelector('pre.script'), original = pre.textContent, ph = card.dataset.placeholder;
  var campo = card.querySelector('input'), botao = card.querySelector('button.copiar');
  function atual(){ return campo.value ? original.split(ph).join(campo.value) : original; }
  campo.addEventListener('input', function(){
    botao.textContent = campo.value ? 'Copiar com a senha' : 'Copiar';
  });
  botao.addEventListener('click', function(){
    var t = atual();
    function ok(){ var a = botao.textContent; botao.textContent = 'Copiado'; setTimeout(function(){ botao.textContent = a; }, 1500); }
    function selecionar(){ var r = document.createRange(); r.selectNodeContents(pre); var s = getSelection();
      s.removeAllRanges(); s.addRange(r); botao.textContent = 'Selecionado: Ctrl+C'; }
    try { navigator.clipboard.writeText(t).then(ok, selecionar); } catch (x) { selecionar(); }
  });
});
"""


def card(sid, nome, papel, ip, roteador, ph_html, ph, nota):
    return f"""
<section class="equip" id="{sid}" data-placeholder="{html.escape(ph)}">
  <header class="equip-cab">
    <div><p class="papel">{papel}</p><h2>{nome}</h2></div>
    <code class="ip-sw">{ip}</code>
  </header>
  <ol class="passos">
    <li>Ligue a <b>porta 1</b> do switch numa porta de LAN do {roteador} (3, 4 ou 5) e os PCs nas outras portas.</li>
    <li>Entre no switch pelo WinBox (pelo MAC, na aba Neighbors), com <code>admin</code> e a senha de fábrica.</li>
    <li>Abra <b>New Terminal</b>, cole o script inteiro e aperte Enter. {nota}</li>
    <li>Daí em diante, entre com <code>admin_senai</code> em <code>{ip}</code>.</li>
  </ol>
  <div class="senha">
    <label for="senha-{sid}">Senha do admin_senai (opcional)</label>
    <input id="senha-{sid}" type="password" autocomplete="off" spellcheck="false" placeholder="troca o {ph_html}">
  </div>
  <p class="aviso">A senha digitada só entra no texto copiado, neste navegador. Ela não é gravada nem enviada.</p>
  <div class="cab-script"><h3>Script</h3><button type="button" class="copiar">Copiar</button></div>
  <pre class="script"><code>{html.escape(secao(nome))}</code></pre>
</section>"""


pagina = f"""<title>Scripts dos Switches</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}{EXTRA_CSS}</style>
<main class="pagina">
  <header class="topo">
    <p class="papel">TCC SENAI 2026 · Rede Matriz/Filial</p>
    <h1>Scripts dos Switches</h1>
    <p>Configuração completa de cada switch MikroTik (RouterOS 7), pronta para colar no terminal do switch de fábrica.
       Todas as portas ficam no mesmo switch com MTU 2000, a gerência fica restrita a SSH e WinBox e o Zabbix lê o switch por SNMP.</p>
    <p class="aviso">Para switch MikroTik com SwOS (linha CSS) ou de outra marca, estes scripts não se aplicam.</p>
  </header>
  {''.join(card(*s) for s in SWITCHES)}
</main>
<script>{JS}</script>
"""
DESTINO.write_text(pagina, encoding="utf-8")
print(f"gerado {DESTINO.relative_to(RAIZ)} ({len(pagina) // 1024} KB)")
