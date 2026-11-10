#!/bin/bash
# NOC SENAI — aplica a Fase 1 do auto-monitoramento do servidor.
# Instala o coletor de métricas, o UserParameter do agente, o sudo pontual, o mod_status do Apache
# e o contador do firewall; depois cria o host NOC-SERVIDOR no Zabbix e o painel no Grafana.
#
# Uso, como root, no servidor:  bash infra/servidor/monitoramento/aplicar-monitoramento.sh
# Idempotente: pode rodar de novo (só o host do Zabbix avisa se já existir).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Rode como root."; exit 1; }

AQUI="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$AQUI/../../.." && pwd)"
D="$(date +%Y%m%d-%H%M%S)"
ok() { echo "  ok: $*"; }

echo "1/7 Coletor de métricas"
install -m 0755 "$AQUI/noc-metricas.sh" /usr/local/bin/noc-metricas.sh
ok "/usr/local/bin/noc-metricas.sh"

echo "2/7 Regras de sudo (somente leitura)"
install -m 0440 "$AQUI/sudoers-noc-metricas" /etc/sudoers.d/noc-metricas
visudo -cf /etc/sudoers.d/noc-metricas >/dev/null
ok "/etc/sudoers.d/noc-metricas (validado)"

echo "3/7 UserParameter do zabbix-agent2"
install -m 0644 "$AQUI/userparameters-noc.conf" /etc/zabbix/zabbix_agent2.d/noc.conf
systemctl restart zabbix-agent2
ok "agente reiniciado"

echo "4/7 mod_status do Apache (só localhost)"
install -m 0644 "$AQUI/apache-status-noc.conf" /etc/apache2/conf-available/noc-status.conf
a2enmod -q status >/dev/null
a2enconf -q noc-status >/dev/null
if apache2ctl configtest 2>/dev/null; then
  systemctl reload apache2
  ok "mod_status ligado em /server-status (Require local)"
else
  echo "  ATENÇÃO: apache2ctl configtest falhou; Apache NÃO recarregado. Confira a config."
fi

echo "5/7 Contador de descartes do firewall"
NFT="$REPO/infra/servidor/seguranca/nftables.conf"
if [ -f "$NFT" ]; then
  nft list ruleset > "/root/nftables-ruleset.bak-$D" 2>/dev/null || true
  if nft -c -f "$NFT"; then
    nft -f "$NFT"
    ok "nftables recarregado com o counter noc_drop_input (backup em /root/nftables-ruleset.bak-$D)"
  else
    echo "  ATENÇÃO: 'nft -c' falhou; firewall NÃO recarregado. Regras atuais mantidas."
  fi
else
  echo "  aviso: $NFT não encontrado; pulei o firewall."
fi

echo "6/7 Host NOC-SERVIDOR no Zabbix"
python3 "$REPO/noc/monitorar_servidor.py" || echo "  (host já existia ou houve erro — veja a mensagem acima)"

echo "7/7 Painel no Grafana"
python3 "$REPO/noc/grafana_servidor.py"
systemctl restart grafana-server
ok "painel 'NOC - Servidor (segurança)' provisionado"

echo
echo "Pronto. Confira em alguns minutos:"
echo "  - zabbix_get -s 127.0.0.1 -k 'noc.srv[synrecv]'   (deve devolver um número)"
echo "  - Zabbix: host NOC-SERVIDOR com itens recebendo dados"
echo "  - Grafana: painel 'NOC - Servidor (segurança)'"
