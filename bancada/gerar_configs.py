"""Gera os arquivos finais da bancada em bancada/saida/ (pasta ignorada pelo Git).

Rode no notebook:  python bancada\\gerar_configs.py
Pergunta as senhas (sem mostrar na tela) e monta, a partir de routeros/:
  R-MATRIZ.rsc, R-FILIAL.rsc .... configuração completa (R-FILIAL já inclui a integração com o NOC)
  SW-MATRIZ.rsc, SW-FILIAL.rsc .. switches MikroTik gerenciáveis (opcional)
  noc-analista.pub .............. chave SSH de leitura do Analista IA (vai junto para o R-FILIAL)
  pc-matriz.ps1, pc-filial.ps1 .. IP fixo dos PCs
  RADIOS.txt .................... ficha para configurar os rádios pela página web
Os .rsc contêm as senhas que você digitou: apague bancada/saida/ depois de configurar.
"""
import getpass
import secrets
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MODELOS = RAIZ / "routeros"
SAIDA = Path(__file__).resolve().parent / "saida"
CHAVE_ANALISTA = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ6p8g/oAtn3KK0x8Tze43LoZ5JZ6vePhG3ihVcCquum "
                  "noc-analista@zabbix")

# O MikroTik roda o arquivo logo depois do reset: espera as interfaces subirem antes de configurar
INICIO = """# Gerado por bancada/gerar_configs.py — aplicado com:
#   /system reset-configuration no-defaults=yes skip-backup=yes run-after-reset={arquivo}
:delay 15s
:log info "NOC SENAI: aplicando {arquivo}"
"""
FIM = """
:log info "NOC SENAI: {arquivo} aplicado"
"""


def senha(nome):
    while True:
        s = getpass.getpass(f"Senha do usuário admin_senai no {nome} (não aparece): ")
        if len(s) < 8:
            print("  use pelo menos 8 caracteres")
        elif '"' in s or "\\" in s or "$" in s:
            print('  evite aspas, barra invertida e $ (quebram o script do RouterOS)')
        elif s != getpass.getpass("  repita: "):
            print("  não conferem, de novo")
        else:
            return s


def pergunta(texto, padrao):
    r = input(f"{texto} [{padrao}]: ").strip()
    return r or padrao


def secao_switch(nome):
    """Recorta de switches.rsc o trecho de um switch."""
    texto = (MODELOS / "switches.rsc").read_text(encoding="utf-8")
    inicio = texto.index(f"# ---------------- {nome} ")
    fim = texto.find("# ----------------", inicio + 10)
    return texto[inicio:fim if fim != -1 else None]


def gravar(nome, conteudo):
    # .ps1 com BOM e CRLF (o PowerShell 5.1 do Windows embaralha acentos sem BOM); o resto em UTF-8/LF
    ps1 = nome.endswith(".ps1")
    (SAIDA / nome).write_text(conteudo, encoding="utf-8-sig" if ps1 else "utf-8", newline="\r\n" if ps1 else "\n")
    print(f"  gerado {SAIDA.name}/{nome}")


def main():
    print("== Gerador da bancada NOC SENAI ==\n")
    zabbix = pergunta("IP do servidor Zabbix na LAN da Matriz", "192.168.10.50")
    comunidade = pergunta("Comunidade SNMP", "public_senai")
    senha_matriz = senha("R-MATRIZ")
    senha_filial = senha("R-FILIAL")
    switches = pergunta("Os switches são MikroTik gerenciáveis? (s/n)", "n").lower().startswith("s")
    SAIDA.mkdir(exist_ok=True)
    print()

    # R-MATRIZ
    base = (MODELOS / "r-matriz.rsc").read_text(encoding="utf-8").replace("<SENHA_ADMIN_MATRIZ>", senha_matriz)
    gravar("R-MATRIZ.rsc", INICIO.format(arquivo="R-MATRIZ.rsc") + base + FIM.format(arquivo="R-MATRIZ.rsc"))

    # R-FILIAL = base + integração com o NOC (SNMP, firewall, usuário de leitura com a chave do analista)
    base = (MODELOS / "r-filial.rsc").read_text(encoding="utf-8").replace("<SENHA_ADMIN_FILIAL>", senha_filial)
    noc = (MODELOS / "routeros-r-filial-noc.rsc").read_text(encoding="utf-8")
    noc = (noc.replace("192.168.10.50", zabbix)
              .replace("name=public_senai", f"name={comunidade}")
              .replace("TROQUE_POR_UMA_SENHA_FORTE", secrets.token_urlsafe(18)))  # nunca usada: login por chave
    # A chave vai na própria linha (/user ssh-keys add key=..., RouterOS 7.24): o "import public-key-file" falhava
    # no run-after-reset (arquivo não encontrado logo após o reset), parando o script na última linha.
    linhas = noc.splitlines()
    gravar("R-FILIAL.rsc", INICIO.format(arquivo="R-FILIAL.rsc") + base + "\n" + "\n".join(linhas) + "\n"
           + FIM.format(arquivo="R-FILIAL.rsc"))
    gravar("noc-analista.pub", CHAVE_ANALISTA + "\n")

    if switches:
        for nome, s in (("SW-MATRIZ", senha_matriz), ("SW-FILIAL", senha_filial)):
            trecho = secao_switch(nome).replace("<SENHA_ADMIN_MATRIZ>", s).replace("<SENHA_ADMIN_FILIAL>", s)
            gravar(f"{nome}.rsc", INICIO.format(arquivo=f"{nome}.rsc") + trecho + FIM.format(arquivo=f"{nome}.rsc"))

    # PCs (PowerShell como administrador)
    modelo_pc = (Path(__file__).parent / "modelo_pc.ps1").read_text(encoding="utf-8")
    for nome, ip, gw in (("pc-matriz", "192.168.10.10", "192.168.10.1"), ("pc-filial", "192.168.20.10", "192.168.20.1")):
        gravar(f"{nome}.ps1", modelo_pc.replace("__IP__", ip).replace("__GW__", gw).replace("__ARQUIVO__", f"{nome}.ps1"))

    gravar("RADIOS.txt", """FICHA DOS RÁDIOS P2P (configurar pela página web de cada rádio)

                    RADIO-P2P-MATRIZ            RADIO-P2P-FILIAL
Modo sem fio        Access Point PtP            Station PtP
Modo de rede        Bridge (transparente)       Bridge (transparente)
IP de gerência      10.0.2.3 / 29               10.0.2.4 / 29
Gateway             10.0.2.1                    10.0.2.2
SSID                SENAI_LINK_P2P_BACKUP       conectar em SENAI_LINK_P2P_BACKUP
Segurança           WPA2-PSK (AES)              WPA2-PSK (AES), mesma chave
MTU                 2000 (ou o máximo aceito)   2000 (ou o máximo aceito)

Depois de configurar: do PC-MATRIZ, "ping 10.0.2.4" deve responder.
""")
    print("\nPronto. Próximo passo: bancada\\enviar_mikrotik.ps1 (veja bancada\\LEIA-ME.md).")
    print("ATENÇÃO: os .rsc têm as senhas que você digitou. Apague bancada\\saida depois.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\ncancelado")
