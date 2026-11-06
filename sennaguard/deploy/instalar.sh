#!/usr/bin/env bash
# Instala ou atualiza o SennaGuard no servidor do NOC (Debian 12, como root), ao lado do Zabbix.
#
#   git clone https://github.com/MathZiraA/sennaguard.git /opt/sennaguard
#   bash /opt/sennaguard/deploy/instalar.sh
#
# Publica em https://<SERVIDOR_IP>/sennaguard/ pelo Apache que já serve o Zabbix (HTTPS com a CA do NOC).
# Os PCs da Filial chegam por OSPF (fibra ou rádio): o R-MATRIZ já libera 192.168.20.0/24 -> 192.168.10.0/24.
# Pode rodar de novo a qualquer momento: cada etapa pula o que já está pronto.
set -euo pipefail

APP=/opt/sennaguard
ETC=/etc/sennaguard
DADOS=/var/lib/sennaguard
PORTA=8010
NOC_CONF=/etc/noc/noc.conf
LIVRO=/var/lib/noc-analista/chamados.jsonl

[ "$(id -u)" = 0 ] || { echo "Rode como root."; exit 1; }
cd "$(dirname "$0")/.."
[ "$(pwd)" = "$APP" ] || { echo "Clone o repositório em $APP (git clone ... $APP)."; exit 1; }
conf() { grep -E "^\s*$1\s*=" "$NOC_CONF" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' " || true; }

echo "==> 1/7 Pacotes"
apt-get install -y -qq python3-venv curl iputils-ping >/dev/null
if ! node -v 2>/dev/null | grep -qE '^v(2[0-9]|[3-9][0-9])'; then
    # Tailwind 4 pede Node 20+; o Debian 12 traz o 18
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
    apt-get install -y -qq nodejs >/dev/null
fi

echo "==> 2/7 Usuário do serviço"
id sennaguard >/dev/null 2>&1 || useradd --system --home "$DADOS" --shell /usr/sbin/nologin sennaguard
install -d -o sennaguard -g sennaguard -m 750 "$DADOS"

echo "==> 3/7 Backend (Python)"
[ -d "$APP/.venv" ] || python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/backend/requirements.txt"

echo "==> 4/7 Interface (compilação)"
(cd "$APP/frontend" && npm ci --no-audit --no-fund --loglevel=error && npm run build >/dev/null)

echo "==> 5/7 Configuração ($ETC/sennaguard.env)"
install -d -m 750 -o root -g sennaguard "$ETC"
if [ ! -f "$ETC/sennaguard.env" ]; then
    TOKEN=$(cat /root/.zabbix_token 2>/dev/null || true)
    [ -n "$TOKEN" ] || read -rsp "Token da API do Zabbix: " TOKEN && echo
    cat > "$ETC/sennaguard.env" <<EOF
ZABBIX_URL=http://localhost/zabbix/api_jsonrpc.php
ZABBIX_TOKEN=$TOKEN
NOC_HOST=$(conf HOST_FILIAL || echo R-FILIAL)
NOC_FIBRA_FILIAL=$(conf FIBRA_FILIAL)
NOC_RADIO_FILIAL=$(conf RADIO_FILIAL)
NOC_LIVRO=$LIVRO
SENNAGUARD_BANCO=$DADOS/sennaguard.db
COOKIE_SEGURO=1
EOF
    sed -i '/=$/d' "$ETC/sennaguard.env"  # tira as chaves que o noc.conf não tinha (ficam no padrão)
    chmod 640 "$ETC/sennaguard.env"; chown root:sennaguard "$ETC/sennaguard.env"
fi
# O serviço lê o livro de chamados do Analista IA (só leitura, pelo grupo). O setgid na pasta faz o
# livro criado depois (primeiro chamado NOC-xxx) já nascer com o grupo sennaguard.
install -d "$(dirname "$LIVRO")"
chgrp sennaguard "$(dirname "$LIVRO")" && chmod g+rxs "$(dirname "$LIVRO")"
[ -f "$LIVRO" ] && chgrp sennaguard "$LIVRO" && chmod 640 "$LIVRO"

# Variáveis que versões novas do SennaGuard precisam (acrescenta só as que faltam, sem mexer nas existentes)
env_garante() { grep -q "^$1=" "$ETC/sennaguard.env" || echo "$1=$2" >> "$ETC/sennaguard.env"; }
env_garante NOC_LAN_FILIAL "$(conf LAN_FILIAL || true)"
env_garante NOC_LOOPBACK_MATRIZ "$(conf LOOPBACK_MATRIZ || true)"
env_garante NOC_LOOPBACK_FILIAL "$(conf LOOPBACK_FILIAL || true)"
sed -i '/=$/d' "$ETC/sennaguard.env"
if ! grep -q "^TELEGRAM_TOKEN=" "$ETC/sennaguard.env"; then
    read -rsp "Token do bot do Telegram (crie no @BotFather; Enter para pular): " TG; echo
    [ -n "$TG" ] && echo "TELEGRAM_TOKEN=$TG" >> "$ETC/sennaguard.env"
fi

# Chaves: IA (mesmas do Analista IA) e SSH de leitura dos MikroTik (mesma do Analista, para o backup)
copia_segredo() { [ -f "$1" ] && install -m 600 -o sennaguard -g sennaguard "$1" "$2" || true; }
copia_segredo /root/.gemini_key "$ETC/gemini_key"
copia_segredo /root/.anthropic_key "$ETC/anthropic_key"
copia_segredo /root/.ssh/id_ed25519_mikrotik "$ETC/mikrotik_key"
# Chave própria do teste de failover (usuário com escrita no R-MATRIZ, só para desligar/religar a sfp1)
if [ ! -f "$ETC/mikrotik_teste_key" ]; then
    ssh-keygen -q -t ed25519 -N "" -C "sennaguard-teste" -f "$ETC/mikrotik_teste_key"
    chown sennaguard:sennaguard "$ETC/mikrotik_teste_key" "$ETC/mikrotik_teste_key.pub"; chmod 600 "$ETC/mikrotik_teste_key"
    MOSTRAR_ROUTEROS=1
fi

echo "==> 6/7 Serviço systemd e Apache"
install -m 644 "$APP/deploy/sennaguard.service" /etc/systemd/system/sennaguard.service
install -m 644 "$APP/deploy/apache-sennaguard.conf" /etc/apache2/conf-available/sennaguard.conf
a2enmod -q proxy proxy_http headers >/dev/null
a2enconf -q sennaguard >/dev/null
systemctl daemon-reload
systemctl enable -q sennaguard
systemctl restart sennaguard
apache2ctl configtest 2>/dev/null && systemctl reload apache2

echo "==> 7/7 Primeiro administrador"
# O .env é lido dentro do processo do usuário sennaguard: os tokens não aparecem na lista de processos
ADMINS=$(runuser -u sennaguard -- bash -c 'set -a; . "$0"; set +a; shift; exec "$@"' "$ETC/sennaguard.env" _ "$APP/.venv/bin/python" -c \
    "import sys; sys.path.insert(0,'$APP/backend'); import main; main.iniciar(); print(main.db().execute(\"select count(*) from usuarios where papel='Administrador'\").fetchone()[0])")
if [ "$ADMINS" = 0 ]; then
    read -rp "E-mail do administrador: " EMAIL
    read -rp "Nome: " NOME
    runuser -u sennaguard -- bash -c 'set -a; . "$0"; set +a; shift; exec "$@"' "$ETC/sennaguard.env" _ \
        "$APP/.venv/bin/python" "$APP/backend/gerenciar.py" criar-admin --email "$EMAIL" --nome "$NOME"
fi

sleep 1
if curl -fsS "http://127.0.0.1:$PORTA/api/publico" >/dev/null; then
    IP=$(conf SERVIDOR_IP); IP=${IP:-$(hostname -I | awk '{print $1}')}
    echo
    echo "SennaGuard no ar: https://$IP/sennaguard/"
    echo "Na Filial, o PC precisa confiar na CA do NOC (http://$IP/NOC-SENAI-CA.crt), como para o Zabbix."
else
    echo "O serviço não respondeu. Veja: journalctl -u sennaguard -n 50"; exit 1
fi
if [ "${MOSTRAR_ROUTEROS:-}" = 1 ]; then
    IP=$(conf SERVIDOR_IP); IP=${IP:-$(hostname -I | awk '{print $1}')}
    echo
    echo "Para o teste de failover, cole no terminal do R-MATRIZ (WinBox > New Terminal):"
    echo "  /file add name=sennaguard-teste.pub contents=\"$(cat "$ETC/mikrotik_teste_key.pub")\""
    echo "  /user group add name=sennaguard-teste policy=ssh,read,write,test,policy,!winbox,!web,!api,!ftp"
    echo "  /user add name=sennaguard-teste group=sennaguard-teste address=$IP/32 password=$(openssl rand -hex 16)"
    echo "  /user ssh-keys import public-key-file=sennaguard-teste.pub user=sennaguard-teste"
    echo "O backup usa o usuário zabbix-ia (leitura), que precisa existir também no R-MATRIZ com a mesma chave do Analista IA."
fi
