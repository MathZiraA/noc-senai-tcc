#!/bin/bash
# ====================================================================
# Instalador do NOC SENAI — Zabbix 7.0 + Grafana + Analista IA + HTTPS + backup
#
# Uso (como root, num Debian 12 limpo, com o projeto já no servidor):
#   1. cp noc.conf.exemplo /etc/noc/noc.conf   e ajuste os IPs (o instalador faz a cópia se faltar)
#   2. bash instalacao/instalar-noc.sh
#
# Pode ser rodado de novo a qualquer momento: cada etapa pula o que já está pronto.
# Senhas e chaves são PERGUNTADAS (sem aparecer na tela) e guardadas em arquivos que só o root lê.
# ====================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # raiz do projeto (pasta acima de instalacao/)
CONF=/etc/noc/noc.conf
NOC=/root/noc
VENV=/opt/noc-analista
PY="$VENV/bin/python"
LOG=/var/log/noc_instalacao.log

passo() { echo; echo "==> $*"; }
ok() { echo "    [ok] $*"; }

[ "$(id -u)" -eq 0 ] || { echo "Rode como root (su - ou sudo)."; exit 1; }
grep -q 'VERSION_ID="12"' /etc/os-release || { echo "Feito para Debian 12 (bookworm)."; exit 1; }

# --------------------------------------------------------------------
passo "1/10 Configuração ($CONF)"
if [ ! -f "$CONF" ]; then
    mkdir -p /etc/noc
    cp "$REPO/noc.conf.exemplo" "$CONF"
    echo "    Criei $CONF a partir do exemplo."
    echo "    Ajuste os IPs (principalmente SERVIDOR_IP) e rode o instalador de novo:"
    echo "      nano $CONF"
    exit 0
fi
# shellcheck disable=SC1090
. "$CONF"
ok "servidor $SERVIDOR_IP, host monitorado $HOST_FILIAL ($LAN_FILIAL)"
timedatectl set-timezone "${FUSO:-America/Sao_Paulo}" || true

# --------------------------------------------------------------------
passo "2/10 Pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq >>"$LOG" 2>&1
apt-get install -y -qq wget curl gnupg ca-certificates openssl python3-venv snmp fonts-dejavu-core \
    locales apache2 mariadb-server rsync >>"$LOG" 2>&1
sed -i 's/^# *pt_BR.UTF-8 UTF-8/pt_BR.UTF-8 UTF-8/' /etc/locale.gen && locale-gen >>"$LOG" 2>&1
ok "pacotes base"

# --------------------------------------------------------------------
passo "3/10 Zabbix 7.0 LTS"
if ! dpkg -s zabbix-server-mysql >/dev/null 2>&1; then
    wget -q -O /tmp/zabbix-release.deb \
        https://repo.zabbix.com/zabbix/7.0/debian/pool/main/z/zabbix-release/zabbix-release_latest_7.0+debian12_all.deb
    dpkg -i /tmp/zabbix-release.deb >>"$LOG" 2>&1
    apt-get update -qq >>"$LOG" 2>&1
    apt-get install -y -qq zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts \
        zabbix-agent2 >>"$LOG" 2>&1
fi
ok "pacotes do Zabbix"

if ! mysql -N -e "SHOW DATABASES LIKE 'zabbix'" | grep -q zabbix; then
    SENHA_BANCO=$(openssl rand -hex 16)
    mysql -e "CREATE DATABASE zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
              CREATE USER 'zabbix'@'localhost' IDENTIFIED BY '$SENHA_BANCO';
              GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';
              SET GLOBAL log_bin_trust_function_creators = 1;"
    echo "    importando o esquema do banco (alguns minutos)..."
    zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql --default-character-set=utf8mb4 -uzabbix \
        -p"$SENHA_BANCO" zabbix
    mysql -e "SET GLOBAL log_bin_trust_function_creators = 0;"
    sed -i "s/^# *DBPassword=.*/DBPassword=$SENHA_BANCO/" /etc/zabbix/zabbix_server.conf
    # Configuração do site gerada aqui: o assistente web do Zabbix não é necessário
    cp /usr/share/zabbix/conf/zabbix.conf.php.example /etc/zabbix/web/zabbix.conf.php
    sed -i "s/^\$DB\['PASSWORD'\].*/\$DB['PASSWORD']\t\t\t= '$SENHA_BANCO';/; s/^\$ZBX_SERVER_NAME.*/\$ZBX_SERVER_NAME\t\t= 'NOC SENAI';/" \
        /etc/zabbix/web/zabbix.conf.php
    chown www-data:www-data /etc/zabbix/web/zabbix.conf.php
    chmod 600 /etc/zabbix/web/zabbix.conf.php
    unset SENHA_BANCO
    ok "banco criado com senha aleatória (está em /etc/zabbix/zabbix_server.conf)"
else
    ok "banco já existe"
fi
systemctl enable --now zabbix-server zabbix-agent2 apache2 >>"$LOG" 2>&1
systemctl restart apache2

# --------------------------------------------------------------------
passo "4/10 Código do NOC e ambiente Python"
mkdir -p "$NOC"
rsync -a --exclude __pycache__ "$REPO/noc/" "$NOC/"
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip anthropic google-genai pillow >>"$LOG" 2>&1
ok "código em $NOC, Python em $VENV"

# --------------------------------------------------------------------
passo "5/10 HTTPS (CA própria do NOC)"
# O Grafana entra antes do certificado: o grupo 'grafana' precisa existir para ler a chave
if ! dpkg -s grafana >/dev/null 2>&1; then
    mkdir -p /etc/apt/keyrings
    wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor --yes -o /etc/apt/keyrings/grafana.gpg
    echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
        > /etc/apt/sources.list.d/grafana.list
    apt-get update -qq >>"$LOG" 2>&1
    apt-get install -y -qq grafana >>"$LOG" 2>&1
fi
bash "$NOC/setup_https.sh" | tail -1

# --------------------------------------------------------------------
passo "6/10 Grafana + plugin do Zabbix"
[ -d /var/lib/grafana/plugins/alexanderzobnin-zabbix-app ] || \
    grafana cli plugins install alexanderzobnin-zabbix-app >>"$LOG" 2>&1
chown -R grafana:grafana /var/lib/grafana
ok "Grafana $(grafana server -v 2>/dev/null | awk '{print $2}')"

# --------------------------------------------------------------------
passo "7/10 Credenciais (nada aparece na tela)"
URL_ZABBIX="https://$SERVIDOR_IP/zabbix"
if [ ! -s /root/.zabbix_token ]; then
    cat <<EOF
    Falta o token da API do Zabbix. No navegador:
      1. Abra $URL_ZABBIX  (aceite o aviso do certificado ou instale NOC-SENAI-CA.crt)
      2. Entre com Admin / zabbix  (senha padrão de instalação)
      3. TROQUE a senha do Admin: User settings > Profile > Change password
      4. Users > API tokens > Create API token: nome "noc-automacao", usuário Admin, sem validade
EOF
    read -rsp "    Cole o token aqui e tecle Enter: " TOKEN; echo
    printf '%s' "$TOKEN" > /root/.zabbix_token && chmod 600 /root/.zabbix_token
    unset TOKEN
fi
"$PY" -c "import sys; sys.path.insert(0, '$NOC'); from zbx import call; call('host.get', {'limit': 1})" \
    || { echo "    [erro] token recusado pelo Zabbix. Apague /root/.zabbix_token e rode de novo."; exit 1; }
ok "token do Zabbix válido"

if ! "$PY" -c "import sys; sys.path.insert(0, '$NOC'); from zbx import call
sys.exit(0 if call('mediatype.get', {'filter': {'name': ['Gmail Alertas SENAI']}}) else 1)"; then
    echo "    Falta a senha de app do Gmail de $EMAIL (myaccount.google.com/apppasswords)."
    read -rsp "    Cole a senha de app (16 letras) e tecle Enter: " SENHA_APP; echo
    printf '%s' "$SENHA_APP" > /root/.gmail_app && chmod 600 /root/.gmail_app   # setup_email.py apaga depois
    unset SENHA_APP
fi
if [ ! -s /root/.gemini_key ] && [ ! -s /root/.anthropic_key ]; then
    echo "    Chave do Google Gemini para o Analista IA (aistudio.google.com > API keys)."
    read -rsp "    Cole a chave (ou só Enter para instalar sem IA): " CHAVE; echo
    if [ -n "$CHAVE" ]; then printf '%s' "$CHAVE" > /root/.gemini_key && chmod 600 /root/.gemini_key; fi
    unset CHAVE
fi

# --------------------------------------------------------------------
passo "8/10 Configuração do Zabbix pela API"
cd "$NOC"
"$PY" -c "from zbx import call; a = call('user.get', {'filter': {'username': ['Admin']}})[0]
call('user.update', {'userid': a['userid'], 'lang': 'pt_BR'})" && ok "interface do Admin em português"
"$PY" fix_redundancia.py
zabbix_server -R config_cache_reload >/dev/null 2>&1 || true
"$PY" setup_email.py
"$PY" setup_chamados.py
"$PY" setup_zabbix_analista.py
"$PY" setup_backup.py
# Fundo do mapa traz as sub-redes escritas: só redesenha se forem diferentes das do protótipo
if [ "$REDE_MATRIZ" != "192.168.10.0/24" ] || [ "$REDE_FILIAL" != "192.168.20.0/24" ]; then
    "$PY" mapa_visual.py
fi
"$PY" mapa_topologia.py
"$PY" dash_noc.py

# --------------------------------------------------------------------
passo "9/10 Grafana, serviços e tarefas agendadas"
"$PY" setup_grafana.py
chown -R grafana:grafana /var/lib/grafana
systemctl enable grafana-server >>"$LOG" 2>&1 && systemctl restart grafana-server
cp "$REPO/infra/sistema/noc-analista.service" /etc/systemd/system/
systemctl daemon-reload && systemctl enable noc-analista >>"$LOG" 2>&1 && systemctl restart noc-analista
cp "$REPO"/infra/sistema/cron.d/noc-* /etc/cron.d/ && chmod 644 /etc/cron.d/noc-*
chmod 700 "$NOC/backup_noc.sh"
ok "analista, Grafana, backup diário e registro de failover"

# --------------------------------------------------------------------
passo "10/10 Bloco para colar no $HOST_FILIAL"
RSC="$NOC/routeros-${HOST_FILIAL,,}-noc.rsc"
sed -e "s/192\.168\.10\.50/$SERVIDOR_IP/g" \
    -e "s/name=public_senai/name=$SNMP_COMMUNITY/" "$REPO/routeros/routeros-r-filial-noc.rsc" > "$RSC"
ok "gerado $RSC (troque a senha TROQUE_POR_UMA_SENHA_FORTE antes de colar)"

cat <<EOF

====================================================================
 NOC instalado. Endereços (aceite o certificado ou instale a CA):
   Zabbix ............ https://$SERVIDOR_IP/zabbix
   Grafana (TV) ...... https://$SERVIDOR_IP:3000/d/noc-redundancia?kiosk
   Grafana (admin) ... usuário admin, senha em /root/.grafana_admin
   SennaGuard ........ https://$SERVIDOR_IP/sennaguard/ (instale depois: bash instalacao/instalar-sennaguard.sh)
   Certificado da CA . http://$SERVIDOR_IP/NOC-SENAI-CA.crt
 Próximo passo: colar $RSC no $HOST_FILIAL.
 Log completo: $LOG
====================================================================
EOF
