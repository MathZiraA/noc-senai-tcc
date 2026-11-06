#!/bin/bash
# ====================================================================
# Preparação do servidor do NOC num Debian 12 recém-instalado (VM no ESXi ou PC)
#
# Faz o que o instalar-noc.sh não faz e depois chama ele:
#   1. rede fixa na rede da Matriz (192.168.10.50/24, gateway e DNS 192.168.10.1 = R-MATRIZ, internet pela ether2 dele)
#   2. pacotes básicos (ssh, open-vm-tools quando for VM do VMware)
#   3. confere que o projeto já está em /opt/noc-senai-tcc (o deploy NÃO é por git)
#   4. cria /etc/noc/noc.conf
#   5. cria a chave SSH que o Analista IA usa para ler o R-FILIAL e mostra os comandos para cadastrá-la nele
#   6. (opcional) autoriza o notebook do projeto a entrar por SSH, para o Claude acompanhar
#   7. roda o instalar-noc.sh (Zabbix, banco, HTTPS, Grafana, Analista IA, e-mail, chamados, backup...)
#
# ANTES de rodar: copie a pasta do projeto para /opt/noc-senai-tcc (cópia pela rede, rsync/scp
# por SSH ou pendrive — não é por git). Exemplo, a partir do seu PC:
#   rsync -a --exclude .git --exclude .venv --exclude node_modules ./noc-senai-tcc/ root@192.168.10.50:/opt/noc-senai-tcc/
#
# Uso, como root, no CONSOLE do servidor (a etapa 1 muda o IP e derrubaria uma sessão SSH):
#   bash /opt/noc-senai-tcc/instalacao/preparar-servidor.sh
# Pode ser rodado de novo: cada etapa pula o que já está feito.
# ====================================================================
set -euo pipefail

IP_SERVIDOR="${IP_SERVIDOR:-192.168.10.50}"
MASCARA="${MASCARA:-24}"
GATEWAY="${GATEWAY:-192.168.10.1}"
DNS="${DNS:-192.168.10.1}"
NOME="${NOME:-noc-senai}"
DESTINO=/opt/noc-senai-tcc
CHAVE_MK=/root/.ssh/id_ed25519_mikrotik
# Chave pública do notebook do projeto (só permite entrar com a chave privada que fica no notebook)
CHAVE_NOTEBOOK="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHgeQGECWtxmwPMhFO6QFNEbs6Qc51he/Hc+2jA7K+fM claude-noc@pc"

passo() { echo; echo "==> $*"; }
ok() { echo "    [ok] $*"; }

[ "$(id -u)" -eq 0 ] || { echo "Rode como root:  su -   (e depois bash instalacao/preparar-servidor.sh)"; exit 1; }
grep -q 'VERSION_ID="12"' /etc/os-release || { echo "Precisa ser Debian 12 (bookworm). Esta máquina: $(. /etc/os-release; echo "$PRETTY_NAME")"; exit 1; }

# --------------------------------------------------------------------
passo "1/7 Rede fixa: $IP_SERVIDOR/$MASCARA, gateway $GATEWAY"
hostnamectl set-hostname "$NOME"
grep -q "$NOME" /etc/hosts || echo "127.0.1.1 $NOME" >> /etc/hosts
if ip -4 addr | grep -q "inet $IP_SERVIDOR/"; then
    ok "o IP $IP_SERVIDOR já está configurado"
else
    mapfile -t PLACAS < <(ls /sys/class/net | grep -vE '^(lo|docker|veth|virbr)')
    if [ "${#PLACAS[@]}" -eq 1 ]; then
        PLACA="${PLACAS[0]}"
    else
        echo "    Placas encontradas:"; for p in "${PLACAS[@]}"; do echo "      - $p ($(cat /sys/class/net/$p/operstate))"; done
        read -rp "    Qual placa vai na rede da Matriz? " PLACA
    fi
    cp /etc/network/interfaces "/etc/network/interfaces.antes-noc.$(date +%s)"
    cat > /etc/network/interfaces <<EOF
# Gerado por preparar-servidor.sh (NOC SENAI)
source /etc/network/interfaces.d/*

auto lo
iface lo inet loopback

# Rede da Matriz: R-MATRIZ é o gateway (internet pela ether2 dele, NAT) e o DNS
auto $PLACA
iface $PLACA inet static
    address $IP_SERVIDOR/$MASCARA
    gateway $GATEWAY
EOF
    printf 'nameserver %s\n' "$DNS" > /etc/resolv.conf
    systemctl restart networking || { ip addr flush dev "$PLACA"; ifup "$PLACA"; }
    ok "placa $PLACA com $IP_SERVIDOR/$MASCARA"
fi
ping -c2 -W2 "$GATEWAY" >/dev/null && ok "R-MATRIZ ($GATEWAY) responde" || echo "    [aviso] o R-MATRIZ não respondeu: confira o cabo/port group"
if wget -q --spider --timeout=10 https://deb.debian.org/debian/; then ok "internet funcionando"
else echo "    [erro] sem internet: confira o cabo da ether2 do R-MATRIZ (rede da escola)."; exit 1; fi

# --------------------------------------------------------------------
passo "2/7 Pacotes básicos"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl wget ca-certificates openssh-server sudo nano rsync >/dev/null
if systemd-detect-virt -q && [ "$(systemd-detect-virt)" = "vmware" ]; then
    apt-get install -y -qq open-vm-tools >/dev/null && ok "open-vm-tools (VM do VMware)"
fi
timedatectl set-timezone America/Sao_Paulo || true
ok "ssh e utilitários"

# --------------------------------------------------------------------
passo "3/7 Projeto do NOC em $DESTINO"
# O deploy não é por git: o projeto é copiado para o servidor antes de rodar este script.
if [ -d "$DESTINO/instalacao" ] && [ -d "$DESTINO/noc" ] && [ -f "$DESTINO/noc.conf.exemplo" ]; then
    ok "projeto encontrado em $DESTINO"
else
    cat <<EOF
    [erro] não achei o projeto em $DESTINO.
    Copie a pasta do projeto para lá antes de rodar este script, por exemplo do seu PC:
      rsync -a --exclude .git --exclude .venv --exclude node_modules ./noc-senai-tcc/ root@$IP_SERVIDOR:$DESTINO/
    (ou leve por pendrive). Depois rode de novo: bash $DESTINO/instalacao/preparar-servidor.sh
EOF
    exit 1
fi

# --------------------------------------------------------------------
passo "4/7 Configuração do NOC (/etc/noc/noc.conf)"
mkdir -p /etc/noc
if [ ! -f /etc/noc/noc.conf ]; then
    sed "s/^SERVIDOR_IP=.*/SERVIDOR_IP=$IP_SERVIDOR/" "$DESTINO/noc.conf.exemplo" > /etc/noc/noc.conf
    ok "criado a partir do exemplo (SERVIDOR_IP=$IP_SERVIDOR)"
else
    ok "já existe (mantido)"
fi

# --------------------------------------------------------------------
passo "5/7 Chave SSH do Analista IA (leitura do R-FILIAL)"
mkdir -p /root/.ssh && chmod 700 /root/.ssh
if [ ! -f "$CHAVE_MK" ]; then
    ssh-keygen -q -t ed25519 -N "" -C "noc-analista@$NOME" -f "$CHAVE_MK"
    ok "chave nova criada em $CHAVE_MK"
else
    ok "chave já existe"
fi
PUB="$(cat "$CHAVE_MK.pub")"
cat <<EOF
    Cadastre esta chave no R-FILIAL (WinBox > New Terminal), trocando a do protótipo:
      /user ssh-keys remove [find user=zabbix-ia]
      /user ssh-keys add user=zabbix-ia key="$PUB"
EOF

# --------------------------------------------------------------------
passo "6/7 Acesso SSH do notebook do projeto (opcional)"
if grep -qF "$CHAVE_NOTEBOOK" /root/.ssh/authorized_keys 2>/dev/null; then
    ok "o notebook já está autorizado"
else
    read -rp "    Autorizar o notebook do projeto a entrar como root por chave (para o Claude acompanhar)? [s/N] " R
    if [[ "${R,,}" == s* ]]; then
        echo "$CHAVE_NOTEBOOK" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
        sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
        systemctl restart ssh
        ok "autorizado (root só entra com chave, nunca com senha)"
    fi
fi

# --------------------------------------------------------------------
passo "7/7 Instalador do NOC (Zabbix, Grafana, Analista IA, e-mail, chamados, backup)"
echo "    Ele vai pedir, sem mostrar na tela: o token da API do Zabbix, a senha de app do Gmail e a chave do Gemini."
bash "$DESTINO/instalacao/instalar-noc.sh"

cat <<EOF

====================================================================
 Servidor preparado. Para conferir a bancada a partir dele:
   cd /root/noc && /opt/noc-analista/bin/python validar_bancada.py
 Não esqueça de cadastrar a chave nova no R-FILIAL (passo 5).
====================================================================
EOF
