#!/bin/bash
# noc-metricas.sh — emite UMA métrica de segurança/ataque do servidor do NOC para o zabbix-agent2.
#
# Uso:  noc-metricas.sh <metrica>
# Sempre imprime um único número (0 em caso de erro), para o item nunca ficar "sem suporte" no Zabbix.
# Chamado pelo UserParameter noc.srv[*] (ver userparameters-noc.conf). Roda como usuário zabbix;
# as métricas que exigem root usam sudo -n, liberado só para elas em /etc/sudoers.d/noc-metricas.
set -o pipefail

# Garante um número na saída: lê o stdin e, se não for número, devolve 0.
num() { local v; v="$(cat)"; [[ "$v" =~ ^-?[0-9]+([.][0-9]+)?$ ]] && echo "$v" || echo 0; }

case "$1" in
  # --- Estados de conexão TCP (sinais de flood/esgotamento de porta) ---
  estab)     ss -H -tn state established            2>/dev/null | wc -l | num ;;
  synrecv)   ss -H -tn state syn-recv               2>/dev/null | wc -l | num ;;
  timewait)  ss -H -tn state time-wait              2>/dev/null | wc -l | num ;;
  http)      ss -H -tn state established '( sport = :80 or sport = :443 )' 2>/dev/null | wc -l | num ;;

  # Conexões estabelecidas vindas do IP de origem mais frequente (flood de origem única)
  toptalker)
    ss -H -tn state established 2>/dev/null | awk '{print $4}' | sed -E 's/:[0-9]+$//' \
      | sort | uniq -c | sort -rn | head -1 | awk '{print $1+0}' | num ;;
  toptalker_ip)
    ip="$(ss -H -tn state established 2>/dev/null | awk '{print $4}' | sed -E 's/:[0-9]+$//' \
      | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')"
    echo "${ip:-nenhum}" ;;

  # --- Apache (mod_status, só localhost: ver apache-status-noc.conf) ---
  apache_busy)  curl -sk --max-time 3 https://127.0.0.1/server-status?auto 2>/dev/null | awk -F': ' '/^BusyWorkers:/{print $2}'  | num ;;
  apache_idle)  curl -sk --max-time 3 https://127.0.0.1/server-status?auto 2>/dev/null | awk -F': ' '/^IdleWorkers:/{print $2}'  | num ;;
  apache_rps)   curl -sk --max-time 3 https://127.0.0.1/server-status?auto 2>/dev/null | awk -F': ' '/^ReqPerSec:/{print $2}'    | num ;;

  # --- fail2ban: total de IPs banidos somando todas as jails ---
  fail2ban)
    jails="$(sudo -n fail2ban-client status 2>/dev/null | sed -n 's/.*Jail list:[[:space:]]*//p' | tr ',' ' ')"
    total=0
    for j in $jails; do
      n="$(sudo -n fail2ban-client status "$j" 2>/dev/null | awk '/Currently banned:/{print $NF}')"
      total=$(( total + ${n:-0} ))
    done
    echo "$total" | num ;;

  # --- SSH: tentativas de autenticação falhas nos últimos 60 s ---
  ssh_fail)
    sudo -n journalctl -q _SYSTEMD_UNIT=ssh.service --since "60 seconds ago" 2>/dev/null \
      | grep -c -E "Failed password|authentication failure|Invalid user|Connection closed by authenticating" | num ;;

  # --- nftables: contador de pacotes descartados na entrada (counter noc_drop_input) ---
  nft_drops)
    sudo -n nft list counter inet filter noc_drop_input 2>/dev/null | awk '/packets/{print $2}' | num ;;

  *) echo 0 ;;
esac
