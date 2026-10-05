#!/bin/bash
# Backup diário do NOC (cron 02:30): banco do Zabbix + configurações. Guarda 7 dias em /var/backups/noc.
# Ao terminar, avisa o Zabbix (item noc.backup.mb no host "Zabbix server"); se faltar por 26 h, abre um problema.
set -euo pipefail
umask 077  # os arquivos contêm credenciais: só o root lê

DESTINO=/var/backups/noc
DATA=$(date +%Y-%m-%d_%H%M)
mkdir -p "$DESTINO"
chmod 700 "$DESTINO"

# Banco: dump consistente sem travar o Zabbix
mysqldump --single-transaction --quick --routines --triggers zabbix | gzip > "$DESTINO/zabbix-banco-$DATA.sql.gz"

# Configurações e dados pequenos (inclui credenciais: a pasta é só do root)
tar czf "$DESTINO/noc-config-$DATA.tar.gz" --ignore-failed-read \
    /etc/zabbix /etc/grafana /var/lib/grafana/grafana.db /var/lib/grafana/dashboards \
    /etc/apache2/sites-available /etc/apache2/conf-available /etc/ssl/noc /root/noc-ca \
    /root/noc /etc/cron.d/noc-* /etc/systemd/system/noc-analista.service \
    /etc/NetworkManager/system-connections /var/lib/noc-analista \
    /root/.zabbix_token /root/.zabbix_token_analista /root/.gemini_key /root/.grafana_admin \
    /root/.ssh/id_ed25519_mikrotik /root/.ssh/id_ed25519_mikrotik.pub 2>/dev/null

find "$DESTINO" -type f -mtime +7 -delete
TOTAL_MB=$(du -sm "$DESTINO" | cut -f1)
echo "$(date '+%F %T') backup ok: $(ls -1 "$DESTINO" | wc -l) arquivos, ${TOTAL_MB} MB"

cd /root/noc && /opt/noc-analista/bin/python -c "
from zbx import call
call('history.push', [{'host': 'Zabbix server', 'key': 'noc.backup.mb', 'value': $TOTAL_MB}])"
