#!/bin/bash
# ====================================================================
# Blindagem do servidor do NOC (Debian 12), validada em 26/10/2026.
#   - firewall nftables: entra só 22 (Matriz e rede da escola), 80/443/3000 (LANs da Matriz e da Filial) e ping
#   - SSH sem X11, 3 tentativas por conexão, root só por chave; fail2ban bane 1 h após 5 erros em 10 min
#   - Apache sem versão no cabeçalho; Avahi desligado; atualizações de segurança automáticas
# Uso, como root:  bash servidor/seguranca/aplicar.sh
# O firewall entra com trava: se a sessão cair, ele se desfaz sozinho em 180 s. Confirme digitando "ok".
# ====================================================================
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" -eq 0 ] || { echo "Rode como root."; exit 1; }
D=$(date +%Y%m%d)

apt-get install -y -qq nftables fail2ban unattended-upgrades >/dev/null

# Apache: sem versão
cp -p /etc/apache2/conf-available/security.conf "/etc/apache2/conf-available/security.conf.bak-$D"
sed -i -E "s/^\s*ServerTokens .*/ServerTokens Prod/; s/^\s*ServerSignature .*/ServerSignature Off/; s/^\s*TraceEnable .*/TraceEnable Off/" \
    /etc/apache2/conf-available/security.conf
apache2ctl configtest && systemctl reload apache2

# SSH e fail2ban
install -m 644 sshd-10-noc-seguranca.conf /etc/ssh/sshd_config.d/10-noc-seguranca.conf
sshd -t && systemctl reload ssh
install -m 644 fail2ban-noc-sshd.conf /etc/fail2ban/jail.d/noc-sshd.conf
systemctl enable -q --now fail2ban && systemctl restart fail2ban

# Avahi e atualizações automáticas
systemctl disable -q --now avahi-daemon.socket avahi-daemon.service 2>/dev/null || true
printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' > /etc/apt/apt.conf.d/20auto-upgrades

# Firewall com trava de 180 s
nft -c -f nftables.conf
systemd-run --quiet --unit=noc-firewall-rollback --on-active=180 /usr/sbin/nft flush ruleset
nft -f nftables.conf
read -rp "Firewall aplicado. Abra OUTRA sessão SSH e o painel; se tudo funcionar, digite ok: " R
if [ "$R" = "ok" ]; then
    systemctl stop noc-firewall-rollback.timer noc-firewall-rollback.service 2>/dev/null || true
    [ -f /etc/nftables.conf ] && cp -p /etc/nftables.conf "/etc/nftables.conf.bak-$D"
    install -m 600 nftables.conf /etc/nftables.conf
    systemctl enable -q nftables && systemctl restart nftables
    echo "Firewall permanente."
else
    echo "Sem confirmação: o firewall se desfaz sozinho em até 180 s."
fi
