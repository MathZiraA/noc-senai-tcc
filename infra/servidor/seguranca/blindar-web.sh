#!/bin/bash
# NOC SENAI — Fase 2 (blindagem da camada web): instala o mod_evasive no Apache e a jail HTTP no fail2ban.
# O limite por IP no firewall (nftables.conf) é aplicado à parte, com trava de auto-reversão.
#
# Uso, como root, no servidor:  bash infra/servidor/seguranca/blindar-web.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Rode como root."; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"
ok() { echo "  ok: $*"; }

echo "1/4 mod_evasive (pacote)"
if ! dpkg -s libapache2-mod-evasive >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq libapache2-mod-evasive
fi
install -d -o www-data -g www-data /var/log/mod_evasive
ok "pacote e diretório de log"

echo "2/4 Configuração do mod_evasive"
install -m 0644 "$AQUI/mod-evasive-noc.conf" /etc/apache2/conf-available/noc-evasive.conf
a2enmod -q evasive >/dev/null
a2enconf -q noc-evasive >/dev/null
if apache2ctl configtest 2>/dev/null; then
  systemctl reload apache2
  ok "mod_evasive ligado (reload do Apache)"
else
  echo "  ATENÇÃO: configtest falhou; Apache NÃO recarregado."; exit 1
fi

echo "3/4 Jail HTTP do fail2ban"
install -m 0644 "$AQUI/filter-noc-http-flood.conf" /etc/fail2ban/filter.d/noc-http-flood.conf
install -m 0644 "$AQUI/fail2ban-noc-http.conf" /etc/fail2ban/jail.d/noc-http.conf
systemctl restart fail2ban
sleep 2
ok "fail2ban reiniciado"

echo "4/4 Verificação"
if fail2ban-client status noc-http-flood >/dev/null 2>&1; then
  ok "jail noc-http-flood ativa"
else
  echo "  ATENÇÃO: jail noc-http-flood não subiu; veja: fail2ban-client status"
fi
echo
echo "Pronto (Apache + fail2ban). Falta aplicar o limite por IP no firewall:"
echo "  (com trava de auto-reversão — ver o passo de deploy)"
