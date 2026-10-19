"""Gera docs/equipamentos.html: a ficha de configuração de cada equipamento da bancada.

Os scripts vêm direto de routeros/ (com as senhas como <SENHA_...>), então a página nunca diverge do que é
aplicado. O estado de cada equipamento e o histórico de mudanças ficam em EQUIPAMENTOS e MUDANCAS, abaixo:
ao mudar algo na bancada, atualize aqui e rode  python bancada\\gerar_ficha.py
"""
import html
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "docs" / "equipamentos.html"
ATUALIZADO = "19/10/2026 17:45"

# estado: ok | pendente | falha | fora
EQUIPAMENTOS = [
    {
        "id": "r-matriz", "nome": "R-MATRIZ", "papel": "Roteador da Matriz", "estado": "ok",
        "estado_txt": "Configurado em 16/10/2026 14:40",
        "dados": [("Modelo", "MikroTik hEX S (RB760iGS)"), ("RouterOS", "7.24.5 (veio com 6.48.2)"),
                  ("MAC da ether3", "74:4D:28:3C:11:DF"), ("Usuário", "admin_senai (o admin está desativado)"),
                  ("Senha", "definida pelo aluno no gerador; não fica registrada aqui")],
        "lan": "192.168.10.0/24", "gw": "192.168.10.1", "loopback": "10.255.255.1/32",
        "fibra": ("10.0.1.1/30", "10.0.1.2"), "radio": ("10.0.2.1/29", "10.0.2.2"),
        "ospf": ("ospf-matriz", "10.255.255.1"), "netwatch": "10.0.1.2", "backup": "backup_matriz_<data>",
        "portas": [
            ("ether1", "ether1-WAN-RADIO", "Rádio (backup)", "radio", "10.0.2.1/29",
             "porta LAN da fonte PoE da antena RADIO-P2P-MATRIZ (a porta POE da fonte vai na antena)"),
            ("ether2", "ether2-INTERNET", "Internet da escola", "internet", "DHCP da escola",
             "ponto de rede da escola com internet (pendente: o cabo testado em 19/10 estava sem sinal)"),
            ("ether3", "ether3-LAN", "Rede local", "lan", "bridge-LAN", "notebook da Matriz (192.168.10.198, DHCP)"),
            ("ether4", "ether4-LAN", "Rede local", "lan", "bridge-LAN", "porta dedicada da iDRAC do servidor Dell T440 (192.168.10.30)"),
            ("ether5", "ether5-LAN", "Rede local", "lan", "bridge-LAN", "porta de rede comum do servidor Dell T440: ESXi (192.168.10.40) e VMs"),
            ("sfp1", "sfp1-WAN-FIBRA", "Fibra (principal)", "fibra", "10.0.1.1/30", "módulo SFP + fibra até a sfp1 do R-FILIAL"),
        ],
        "scripts": [("r-matriz.rsc", "Configuração completa")],
        "notas": ["Verificado: o notebook recebe 192.168.10.199 pelo DHCP e alcança 192.168.10.1 e a loopback 10.255.255.1."],
    },
    {
        "id": "r-filial", "nome": "R-FILIAL", "papel": "Roteador da Filial", "estado": "ok",
        "estado_txt": "Configurado em 16/10/2026 14:54",
        "dados": [("Modelo", "MikroTik hEX S (RB760iGS)"), ("RouterOS", "7.24.5 (veio com 6.47.3)"),
                  ("MAC da ether3", "C4:AD:34:FF:26:1F"), ("Usuário", "admin_senai (o admin fica desativado)"),
                  ("Usuário do NOC", "zabbix-ia, somente leitura, login por chave SSH"),
                  ("Senha", "definida pelo aluno no gerador; não fica registrada aqui")],
        "lan": "192.168.20.0/24", "gw": "192.168.20.1", "loopback": "10.255.255.2/32",
        "fibra": ("10.0.1.2/30", "10.0.1.1"), "radio": ("10.0.2.2/29", "10.0.2.1"),
        "ospf": ("ospf-filial", "10.255.255.2"), "netwatch": "10.0.1.1", "backup": "backup_filial_<data>",
        "portas": [
            ("ether1", "ether1-WAN-RADIO", "Rádio (backup)", "radio", "10.0.2.2/29",
             "porta LAN da fonte PoE da antena RADIO-P2P-FILIAL (a porta POE da fonte vai na antena)"),
            ("ether2", "ether2-reserva", "Reserva", "livre", "—", "nada"),
            ("ether3", "ether3-LAN", "Rede local", "lan", "bridge-LAN", "PC da Filial N07S12-1243997 (192.168.20.197, DHCP)"),
            ("ether4", "ether4-LAN", "Rede local", "lan", "bridge-LAN", "livre (PCs ou SW-FILIAL)"),
            ("ether5", "ether5-LAN", "Rede local", "lan", "bridge-LAN", "livre (PCs ou SW-FILIAL)"),
            ("sfp1", "sfp1-WAN-FIBRA", "Fibra (principal)", "fibra", "10.0.1.2/30", "módulo SFP + fibra até a sfp1 do R-MATRIZ"),
        ],
        "scripts": [("r-filial.rsc", "Configuração completa"),
                    ("routeros-r-filial-noc.rsc", "Integração com o NOC (SNMP, firewall e usuário de leitura)")],
        "notas": ["Verificado: o notebook recebe 192.168.20.199 pelo DHCP e alcança 192.168.20.1 e a loopback 10.255.255.2.",
                  "O gerador junta os dois scripts num só arquivo, com a chave SSH do Analista IA na própria linha (ssh-keys add key=...).",
                  "Chave do zabbix-ia colada à mão em 16/10 (a linha de import do arquivo tinha falhado).",
                  "Testes de 16/10 16:15: 2 vizinhos OSPF (fibra e rádio), ping só pelo rádio 0% de perda (~2,3 ms), fibra ~0,6 ms.",
                  "Teste de failover em 16/10 16:15: fibra desligada → 3,9 s sem resposta e o tráfego seguiu pelo rádio (5,5 ms); fibra religada → volta sem nenhuma perda.",
                  "SNMP v2c com a comunidade public_senai, respondendo só ao Zabbix (192.168.10.50)."],
    },
]


OUTROS = [
    ("Antenas do rádio P2P", "ok", "Ubiquiti PowerBeam M5 300 (airOS 6.1.7, sem os pratos). Enlace ativo desde 16/10/2026 16:11",
     [("RADIO-P2P-MATRIZ", "Ponto de acesso, WDS, 10.0.2.3/29, gateway 10.0.2.1, MAC 80:2A:A8:2A:9B:E6, ether1 do R-MATRIZ"),
      ("RADIO-P2P-FILIAL", "Estação, WDS, 10.0.2.4/29, gateway 10.0.2.1 (corrigido em 19/10), MAC 44:D9:E7:B4:63:A9, ether1 do R-FILIAL"),
      ("Rede sem fio", "SSID SENAI_LINK_P2P_BACKUP, WPA2-AES PSK (chave definida pelo aluno), Brasil, canal automático 40 MHz"),
      ("Sinal medido (16/10 16:55)", "Filial recebe -53 dBm (H -64 / V -52), Matriz recebe -52 dBm: dentro da faixa da CTI (-50 a -60). Ruído -104 dBm, CCQ 99,1%, 300/300 Mbps, airMAX 96%/91%, 5505 MHz (DFS) 40 MHz"),
      ("Monitoramento no Zabbix", "Ping e SNMP (MIB UBNT-AirMAX): sinal, ruído, CCQ, estações e airMAX a cada 30 s. Alertas: sinal abaixo de -60 dBm (atenção), abaixo de -70 (grave), acima de -40 (forte demais), CCQ abaixo de 80% e AP sem estação."),
      ("Ajuste pendente", "Diferença de 12 dB entre as polarizações H e V na Filial: girar uma antena no próprio eixo até igualar (ideal até ~5 dB)"),
      ("Potência", "-4 dBm (bancada, antenas a poucos metros)"), ("MTU", "2000 (o airOS aceita até 2024)"),
      ("Gestão", "páginas web em https://10.0.2.3 e https://10.0.2.4; SNMP ativo (comunidade definida pelo aluno), contato NOC SENAI TCC"),
      ("Fonte PoE", "Ubiquiti GP-A240-050, 24 V passivo: porta POE na antena, porta LAN na ether1 do roteador")]),
    ("Notebook de testes", "ok", "Pega IP pelo DHCP do roteador em que estiver ligado",
     [("Ligação", "porta 3 de um dos roteadores"), ("Na Matriz", "192.168.10.100 a .199"),
      ("Na Filial", "192.168.20.100 a .199"),
      ("Ping pela fibra", "ping -S <IP do cabo> 192.168.10.1 (o -S evita que o Windows use o Wi-Fi)")]),
    ("PCs do projeto", "pendente", "Scripts prontos em bancada\\saida (pc-matriz.ps1 e pc-filial.ps1)",
     [("PC-MATRIZ", "192.168.10.10/24, gateway 192.168.10.1, MTU 2000, ping liberado"),
      ("PC-FILIAL", "192.168.20.10/24, gateway 192.168.20.1, MTU 2000, ping liberado"),
      ("PC da Filial hoje (19/10)", "N07S12-1243997, IP automático 192.168.20.197 (MAC B4:45:06:7B:85:58), ping liberado no firewall; pc-filial.ps1 ainda não aplicado")]),
    ("Servidor ESXi (rack compartilhado)", "pendente", "Configurando: o grupo é o primeiro a usar o servidor; a gerência fica na rede da Matriz",
     [("Servidor", "Dell PowerEdge T440, service tag 9NRHYR2, BIOS 1.4.8"),
      ("iDRAC9 Enterprise", "192.168.10.30/24 (porta dedicada da iDRAC na ether4 do R-MATRIZ), gateway e DNS 192.168.10.1; console virtual em https://192.168.10.30"),
      ("Gerência do ESXi", "192.168.10.40/24, gateway 192.168.10.1, DNS 192.168.10.1, nome esxi-noc; acesso em https://192.168.10.40"),
      ("Placa física 1", "porta de rede comum do servidor na ether5 do R-MATRIZ: gerência do ESXi e port group VM Network"),
      ("Internet", "pela ether2-INTERNET do R-MATRIZ (NAT): não precisa de segunda placa no servidor"),
      ("Outros grupos", "acessam o ESXi pela rede da Matriz ou com uma liberação específica para 192.168.10.40")]),
    ("Servidor Zabbix (VM no ESXi)", "pendente", "VM nova com Debian 12 + instalar_noc.sh (docs/SERVIDOR-INSTALACAO.md)",
     [("Recursos", "2 vCPU, 4 a 8 GB de RAM, 60 GB de disco"),
      ("Placa de rede", "VM Network → 192.168.10.50/24, gateway 192.168.10.1, DNS 192.168.10.1 (internet pelo R-MATRIZ)"),
      ("Monitora", "R-FILIAL pela loopback 10.255.255.2, fibra, rádio e as duas antenas (ping + SNMP)")]),
]

MUDANCAS = [  # mais recente primeiro
    ("19/10/2026 17:45", "Portas", "Mapa de portas completo: cada porta dos dois roteadores com o que está ligado nela. R-MATRIZ: ether2 virou ether2-INTERNET (DHCP da escola, NAT, DNS e rota padrão anunciada no OSPF); ether4 = iDRAC; ether5 = servidor (ESXi)."),
    ("19/10/2026 17:15", "Servidor", "Servidor identificado: Dell PowerEdge T440 (9NRHYR2) com iDRAC9 ligada na ether4 do R-MATRIZ. IP da iDRAC trocado de 192.168.10.40 para 192.168.10.30, liberando o .40 para o ESXi. Plano de IPs: .30 iDRAC, .40 ESXi, .50 VM do Zabbix, .51 a .99 para VMs de outros grupos."),
    ("19/10/2026 16:30", "Servidor", "Mudança de plano: o NOC roda numa VM dentro do VMware ESXi de um servidor de rack compartilhado (não mais Debian direto no PC). Gerência do ESXi na rede da Matriz: 192.168.10.40."),
    ("19/10/2026 16:10", "Failover", "tracert do notebook da Matriz ao PC da Filial: com a fibra, salto 2 = 10.0.1.2 (fibra, ~5 ms); com o cabo da fibra desconectado, salto 2 = 10.0.2.2 (rádio, ~7 ms), sem perder o PC. Prova visual da troca de caminho para a apresentação."),
    ("19/10/2026 16:00", "PCs", "Notebook da Matriz (192.168.10.198) pinga o PC da Filial (192.168.20.197) sem perda, 5 ms, TTL 126; caminho R-MATRIZ → fibra (10.0.1.2) → PC. O PC só respondeu depois de liberar o ping no firewall do Windows."),
    ("19/10/2026 15:35", "Switches", "switches.rsc refeito no padrão dos roteadores: todas as portas em bridge com MTU 2000, gerência 192.168.10.2 / 192.168.20.2, só SSH/WinBox (SW-MATRIZ só da Matriz; SW-FILIAL da Filial e da Matriz), SNMP para o Zabbix, firewall da gerência e backup diário."),
    ("19/10/2026 15:30", "Testes", "Bateria completa da Matriz: 286 pings em 60 s até o R-FILIAL sem perda (2,0 ms); tracert direto 192.168.10.1 → 192.168.20.1; 2 vizinhos OSPF (fibra e rádio), rotas pela fibra; ping só pelo rádio 0% (2 ms); MTU 2000 sem fragmentar pela fibra e pelo rádio; netwatch up; nenhum erro no log do R-MATRIZ."),
    ("19/10/2026 15:10", "Acessos", "A Matriz gerencia tudo e a Filial não gerencia a Matriz: R-FILIAL aceita SSH/WinBox vindos da Matriz (regra 5b) e bloqueia os PCs da Filial nas páginas das antenas; R-MATRIZ aceita SSH/WinBox só da rede da Matriz. Opção 121 no DHCP do R-MATRIZ (rotas do projeto pelo cabo). Testado da Matriz: WinBox/SSH do R-FILIAL e páginas das duas antenas abrem."),
    ("19/10/2026 14:55", "Rádio", "Gateway da antena da Filial trocado para 10.0.2.1: ela passou a responder direto da Matriz (0% de perda, 3 ms)."),
    ("19/10/2026 14:40", "Mapeamento", "Bancada religada e mapeada: notebook na ether3 do R-MATRIZ; antena da Matriz (AP) ligada no R-MATRIZ (2,1 ms) e a da Filial do outro lado do rádio; fibra e rádio funcionando."),
    ("17/10/2026", "Zabbix", "Revisão contra a reunião da CTI: antenas passam a ter SNMP no Zabbix (sinal, ruído, CCQ, airMAX) com alertas da faixa -60 a -50 dBm; testado no Zabbix do protótipo. Achado: gateway da antena da Filial deve ser 10.0.2.1 para o Zabbix enxergá-la (pendente, antenas desmontadas)."),
    ("16/10/2026 17:30", "Ambos", "Comandos de serviços aplicados nos dois roteadores. Verificado da rede da Filial: R-FILIAL responde só nas portas 22 e 8291; 443, 2000, 80, 21, 23 e 8728 fechadas. R-MATRIZ não aceita gerência vinda de fora da sua rede local."),
    ("16/10/2026 17:20", "Ambos", "Pedido do Piffer (CTI): só os serviços necessários. Desligados o reverse-proxy e o btest; a regra de gerência do firewall passou a aceitar só SSH (22) e WinBox (8291). Comandos para colar nos dois roteadores; scripts atualizados."),
    ("16/10/2026 17:00", "R-FILIAL", "Removidos os atalhos temporários de acesso às antenas (NAT TEMP: sinal antena). Nenhum item temporário restante."),
    ("16/10/2026 16:55", "Rádio", "Sinal medido nas duas antenas: -53 dBm (Filial) e -52 dBm (Matriz), dentro da faixa pedida pela CTI. Atalho temporário de acesso às antenas criado no R-FILIAL."),
    ("16/10/2026 16:40", "Rádio", "Teste à distância, R-FILIAL do outro lado da sala e sem fibra: 289 pings em 60 s, 0% de perda, 6,4 ms de média (5 a 11 ms). Ping nos dois sentidos entre os notebooks (no da Filial foi liberado o ping no firewall do Windows)."),
    ("16/10/2026 16:17", "Failover", "Teste: com a fibra desligada no R-FILIAL a rede ficou 3,9 s sem resposta (8 de 729 pings) e passou para o rádio; na volta da fibra, nenhuma perda. Latência entre notebooks: 4,4 ms pela fibra, 5,5 ms pelo rádio."),
    ("16/10/2026 16:16", "R-FILIAL", "Removidos os itens temporários das antenas (NAT, IP 192.168.1.1 e descoberta em todas as portas)."),
    ("16/10/2026 16:15", "Rádio", "Antenas Ubiquiti PowerBeam M5 configuradas (Matriz = ponto de acesso 10.0.2.3, Filial = estação 10.0.2.4, WDS). Rádio passando tráfego: segundo vizinho OSPF e ping só pelo rádio com 0% de perda."),
    ("16/10/2026 16:14", "Notebooks", "Notebook da Filial alcança o notebook da Matriz (192.168.10.199), TTL 126."),
    ("16/10/2026 15:15", "R-FILIAL", "Log mostrou erro na última linha do arquivo (import da chave SSH do zabbix-ia). Gerador corrigido para cadastrar a chave direto na linha; o resto da configuração foi aplicado."),
    ("16/10/2026 15:05", "Rádio", "Porta 1 do R-FILIAL com link (100 Mbps), mas as antenas não respondem em 10.0.2.3/10.0.2.4 e o rádio não passa tráfego: falta configurar as antenas."),
    ("16/10/2026 15:05", "Fibra", "Fibra ligada na sfp1 dos dois roteadores: OSPF fechado, 0% de perda, ~0,6 ms; a Filial chega na Matriz com TTL 63."),
    ("16/10/2026 14:54", "R-FILIAL", "Equipamento novo configurado do zero: RouterOS 6.47.3 → 7.24.5, arquivo testado sem erros e aplicado."),
    ("16/10/2026 14:40", "R-MATRIZ", "Equipamento novo configurado do zero: RouterOS 6.48.2 → 7.24.5, arquivo testado sem erros e aplicado."),
    ("16/10/2026", "Bancada", "A escola trocou os equipamentos. Toda a configuração está sendo refeita com os modelos corrigidos."),
    ("14/10/2026", "R-FILIAL", "Teste do rádio: porta 1 sem link. A configuração está certa; o problema é o equipamento do rádio."),
    ("14/10/2026", "Ambos", "Fibra movida da ether2 para a sfp1 (módulo SFP). A ether2 virou reserva."),
    ("14/10/2026", "Ambos", "DHCP na rede local (.100 a .199), L2MTU 2026 para o MTU 2000 e OSPF passive sem =yes."),
    ("14/10/2026", "Ambos", "Primeira configuração dos hEX S anteriores, atualizados de RouterOS 6 para 7.24.5."),
]

ROTULO = {"ok": "Configurado", "pendente": "Pendente", "falha": "Com defeito", "fora": "Fora do MVP"}
e = html.escape


def script(nome):
    return (RAIZ / "routeros" / nome).read_text(encoding="utf-8").rstrip()


def painel_portas(portas):
    blocos = "".join(
        f'<div class="porta {c}"><span class="led"></span><b>{e(p)}</b><small>{e(papel)}</small></div>'
        for p, _, papel, c, _, _ in portas)
    return f'<div class="painel" aria-label="Painel frontal do hEX S">{blocos}</div>'


def tabela(linhas, cab=None):
    head = "".join(f"<th>{e(c)}</th>" for c in cab) if cab else ""
    corpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in l) + "</tr>" for l in linhas)
    return f'<div class="rolagem"><table>{"<thead><tr>" + head + "</tr></thead>" if head else ""}<tbody>{corpo}</tbody></table></div>'


def roteador(r):
    lan, gw = r["lan"], r["gw"]
    rede = gw.rsplit(".", 1)[0]
    portas = tabela([(f"<code>{e(p)}</code>", f"<code>{e(n)}</code>", e(papel), e(end), e(liga))
                     for p, n, papel, c, end, liga in r["portas"]], ["Porta", "Nome", "Uso", "Endereço", "Liga em"])
    ender = tabela([
        ("Rede local (bridge-LAN)", f"<code>{gw}/24</code>", f"rede {lan}"),
        ("Loopback", f"<code>{r['loopback']}</code>", "router-id do OSPF e endereço de monitoramento"),
        ("Fibra (sfp1)", f"<code>{r['fibra'][0]}</code>", f"outra ponta: <code>{r['fibra'][1]}</code>"),
        ("Rádio (ether1)", f"<code>{r['radio'][0]}</code>", f"outra ponta: <code>{r['radio'][1]}</code>"),
        ("DHCP", f"<code>{rede}.100–{rede}.199</code>", f"pool-LAN, gateway {gw}, concessão de 1 h; opção 121 com as rotas do projeto (dispensa o -S no ping)"),
    ], ["Item", "Valor", "Observação"])
    ospf = tabela([
        ("Instância", f"<code>{r['ospf'][0]}</code>, router-id <code>{r['ospf'][1]}</code>, área 0.0.0.0"),
        ("sfp1-WAN-FIBRA", "ptp, custo <b>10</b> (preferida); vai a 200 quando a fibra degrada"),
        ("ether1-WAN-RADIO", "ptp, custo <b>100</b> (backup)"),
        ("bridge-LAN e loopback", "passive: anunciadas sem formar vizinhança"),
        ("Netwatch da fibra", f"ICMP em <code>{r['netwatch']}</code> a cada 10 s, 20 pacotes; média &gt; 30 ms ou perda &gt; 10% "
                              "sobe o custo da fibra para 200 e o tráfego vai para o rádio"),
    ])
    seg = tabela([
        ("Serviços desligados", "telnet, ftp, www, www-ssl, api, api-ssl, reverse-proxy e o servidor de teste de banda (btest)"),
        ("SSH e WinBox", "R-MATRIZ: só da rede da Matriz. R-FILIAL: da rede da Filial e da Matriz (regra 5b). A Filial não gerencia a Matriz nem as antenas"),
        ("Descoberta de vizinhos e MAC-WinBox", "só na rede local (LAN_MGMT)"),
        ("Firewall de entrada", "aceita estabelecidas, ICMP, OSPF e, vindo das LANs, só SSH (22) e WinBox (8291); bloqueia o resto"),
        ("Firewall de passagem", "libera Matriz ↔ Filial; bloqueia o que entra pelas WAN sem ter sido pedido"),
        ("Backup", f"diário às 00:00, arquivo <code>{e(r['backup'])}</code>"),
    ])
    dados = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in r["dados"])
    notas = "".join(f"<li>{e(n)}</li>" for n in r["notas"])
    scripts = "".join(
        f'<details><summary><span>{e(desc)}</span><code>routeros/{e(n)}</code></summary>'
        f'<div class="acoes"><button type="button" class="copiar" data-alvo="s-{r["id"]}-{i}">Copiar</button></div>'
        f'<pre id="s-{r["id"]}-{i}"><code>{e(script(n))}</code></pre></details>'
        for i, (n, desc) in enumerate(r["scripts"]))
    return f"""
<section class="equip" id="{r['id']}">
  <header class="equip-cab">
    <div><p class="papel">{e(r['papel'])}</p><h2>{e(r['nome'])}</h2></div>
    <span class="estado {r['estado']}">{ROTULO[r['estado']]}</span>
  </header>
  <p class="estado-txt">{e(r['estado_txt'])}</p>
  <dl class="dados">{dados}</dl>
  {painel_portas(r["portas"])}
  <h3>Portas</h3>{portas}
  <h3>Endereçamento</h3>{ender}
  <h3>Roteamento</h3>{ospf}
  <h3>Segurança e manutenção</h3>{seg}
  {'<ul class="notas">' + notas + '</ul>' if notas else ''}
  <h3>Scripts</h3>{scripts}
</section>"""


def outros():
    cards = []
    for nome, est, txt, itens in OUTROS:
        linhas = "".join(f"<dt>{e(k)}</dt><dd>{e(v)}</dd>" for k, v in itens)
        cards.append(f'<article class="outro"><header><h3>{e(nome)}</h3><span class="estado {est}">{ROTULO[est]}</span></header>'
                     f'<p class="estado-txt">{e(txt)}</p><dl class="dados">{linhas}</dl></article>')
    return "".join(cards)


def resumo():
    linhas = [(f'<a href="#{r["id"]}">{e(r["nome"])}</a>', f'<span class="estado {r["estado"]}">{ROTULO[r["estado"]]}</span>',
               f"<code>{r['gw']}</code>", f"<code>{r['loopback'].split('/')[0]}</code>") for r in EQUIPAMENTOS]
    return tabela(linhas, ["Equipamento", "Estado", "IP na LAN", "Loopback"])


CSS = """
/* Layout: coluna única de leitura; cada roteador é uma ficha com o painel de portas do hEX S no topo */
:root{
  --bg:#f6f7f8; --surface:#ffffff; --fg:#17202a; --muted:#5b6672; --line:#d9dee3; --accent:#0b6b74;
  --fibra:#c99700; --radio:#7a4fc2; --lan:#2d7d46; --livre:#8a939c;
  --ok:#2d7d46; --pend:#a86400; --falha:#b3261e; --fora:#5b6672;
  --code-bg:#eef1f3;
  --f-body:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#12171c; --surface:#1a2128; --fg:#e4e9ee; --muted:#9aa6b1; --line:#2c353e; --accent:#4fb8c1;
  --fibra:#e8c13a; --radio:#a98be6; --lan:#5fbf7c; --livre:#7c8792;
  --ok:#5fbf7c; --pend:#e0a14a; --falha:#ef7268; --fora:#9aa6b1; --code-bg:#20282f; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#12171c; --surface:#1a2128; --fg:#e4e9ee; --muted:#9aa6b1; --line:#2c353e; --accent:#4fb8c1;
  --fibra:#e8c13a; --radio:#a98be6; --lan:#5fbf7c; --livre:#7c8792;
  --ok:#5fbf7c; --pend:#e0a14a; --falha:#ef7268; --fora:#9aa6b1; --code-bg:#20282f; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font-family:var(--f-body);font-size:15px;line-height:1.55}
.pagina{max-width:960px;margin:0 auto;padding-inline:20px;padding-block:28px 64px;display:grid;gap:28px}
h1,h2,h3{text-wrap:balance;line-height:1.2;margin:0}
h1{font-size:1.9rem;font-weight:600;letter-spacing:-.01em}
h2{font-size:1.5rem;font-weight:600}
h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600;margin-top:8px}
p{margin:0;max-width:68ch}
a{color:var(--accent)}
code,pre{font-family:var(--f-mono);font-size:.86em}
td code,dd code{background:var(--code-bg);padding:1px 5px;border-radius:4px}
.topo{display:grid;gap:10px}
.topo .meta{color:var(--muted);font-size:.9rem;font-variant-numeric:tabular-nums}
.indice{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:.92rem}
.equip{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:22px;display:grid;gap:14px;min-width:0}
.equip-cab,.outro header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.papel{color:var(--muted);font-size:.85rem}
.estado{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid currentColor;white-space:nowrap}
.estado::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.estado.ok{color:var(--ok)} .estado.pendente{color:var(--pend)} .estado.falha{color:var(--falha)} .estado.fora{color:var(--fora)}
.estado-txt{color:var(--muted);font-size:.92rem}
.dados{display:grid;grid-template-columns:minmax(120px,max-content) 1fr;gap:6px 18px;margin:0}
.dados dt{color:var(--muted);font-size:.9rem}
.dados dd{margin:0;min-width:0;overflow-wrap:anywhere}
.painel{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;background:var(--code-bg);border:1px solid var(--line);border-radius:8px;padding:10px}
.porta{display:grid;justify-items:center;gap:3px;padding:8px 4px;border-radius:6px;background:var(--surface);border:1px solid var(--line);text-align:center;min-width:0}
.porta b{font-family:var(--f-mono);font-size:.82rem}
.porta small{font-size:.7rem;color:var(--muted);line-height:1.2}
.led{width:10px;height:10px;border-radius:2px;background:var(--livre)}
.porta.fibra .led{background:var(--fibra)} .porta.internet .led{background:var(--accent)} .porta.internet{border-color:var(--accent)} .porta.radio .led{background:var(--radio)} .porta.lan .led{background:var(--lan)}
.porta.fibra{border-color:var(--fibra)} .porta.radio{border-color:var(--radio)}
.rolagem{overflow-x:auto;min-width:0}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th{text-align:left;font-weight:600;color:var(--muted);font-size:.8rem;border-bottom:1px solid var(--line);padding:6px 10px 6px 0}
td{border-bottom:1px solid var(--line);padding:7px 10px 7px 0;vertical-align:top;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
.notas{margin:0;padding-left:18px;color:var(--muted);font-size:.9rem;display:grid;gap:4px}
details{border:1px solid var(--line);border-radius:8px;min-width:0}
summary{cursor:pointer;padding:10px 14px;display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 12px;font-weight:500}
summary code{color:var(--muted);font-weight:400}
summary:focus-visible,button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.acoes{display:flex;justify-content:flex-end;padding:0 14px}
button.copiar{font:inherit;font-size:.82rem;padding:4px 12px;border-radius:6px;border:1px solid var(--line);background:var(--surface);color:var(--fg);cursor:pointer}
button.copiar:hover{border-color:var(--accent);color:var(--accent)}
pre{margin:8px 0 0;padding:14px;background:var(--code-bg);border-top:1px solid var(--line);overflow-x:auto;line-height:1.45;border-radius:0 0 8px 8px}
.outros{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.outro{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px;display:grid;gap:10px;align-content:start;min-width:0}
.outro h3{text-transform:none;letter-spacing:0;color:var(--fg);font-size:1.05rem;margin:0}
.secao{display:grid;gap:12px}
.secao > h2{font-size:1.2rem}
@media (max-width:560px){
  .painel{grid-template-columns:repeat(3,minmax(0,1fr))}
  .dados{grid-template-columns:1fr} .dados dt{margin-top:6px}
  .equip{padding:16px}
}
"""

JS = """
document.querySelectorAll('button.copiar').forEach(function(b){
  b.addEventListener('click', function(){
    var pre = document.getElementById(b.dataset.alvo), texto = pre.innerText;
    function ok(){ b.textContent = 'Copiado'; setTimeout(function(){ b.textContent = 'Copiar'; }, 1500); }
    function selecionar(){ var r = document.createRange(); r.selectNodeContents(pre);
      var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.textContent = 'Selecionado: Ctrl+C'; }
    try { navigator.clipboard.writeText(texto).then(ok, selecionar); } catch (x) { selecionar(); }
  });
});
"""


def main():
    indice = " ".join(f'<a href="#{r["id"]}">{e(r["nome"])}</a>' for r in EQUIPAMENTOS)
    mudancas = tabela([(f"<span style='white-space:nowrap'>{e(d)}</span>", e(q), e(t)) for d, q, t in MUDANCAS],
                      ["Quando", "Onde", "O que mudou"])
    pagina = f"""<title>Ficha da Bancada NOC</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>{CSS}</style>
<main class="pagina">
  <header class="topo">
    <p class="papel">TCC SENAI 2026 · Rede Matriz/Filial com fibra e rádio</p>
    <h1>Ficha da Bancada NOC</h1>
    <p>Tudo o que está configurado em cada equipamento: portas, endereços, roteamento, segurança e os scripts aplicados.
       As senhas não aparecem aqui; nos scripts elas são marcadas como &lt;SENHA_...&gt;.</p>
    <p class="meta">Atualizado em {ATUALIZADO}</p>
    <nav class="indice" aria-label="Equipamentos">{indice} <a href="#outros">Outros equipamentos</a> <a href="#mudancas">Histórico</a></nav>
  </header>
  <section class="secao"><h2>Resumo</h2>{resumo()}</section>
  {''.join(roteador(r) for r in EQUIPAMENTOS)}
  <section class="secao" id="outros"><h2>Outros equipamentos</h2><div class="outros">{outros()}</div></section>
  <section class="secao" id="mudancas"><h2>Histórico de mudanças</h2>{mudancas}</section>
</main>
<script>{JS}</script>
"""
    DESTINO.write_text(pagina, encoding="utf-8")
    print(f"gerado {DESTINO.relative_to(RAIZ)} ({len(pagina) // 1024} KB)")


if __name__ == "__main__":
    main()
