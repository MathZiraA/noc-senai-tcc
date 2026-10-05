#!/bin/bash
# HTTPS para Zabbix, página de status (Apache :443) e Grafana (:3000), com uma CA própria do NOC.
# Idempotente: reaproveita a CA e o certificado se já existirem. Rodar como root na VM.
set -euo pipefail

CA_DIR=/root/noc-ca
CERT_DIR=/etc/ssl/noc

# Endereços do certificado: /etc/noc/noc.conf (padrões = protótipo)
[ -f /etc/noc/noc.conf ] && . /etc/noc/noc.conf
SERVIDOR_IP=${SERVIDOR_IP:-192.168.10.50}
SERVIDOR_IPS_EXTRAS=${SERVIDOR_IPS_EXTRAS-192.168.137.50}
SERVIDOR_NOME=${SERVIDOR_NOME:-noc.senai.local}
IPS="IP:$SERVIDOR_IP,IP:127.0.0.1,DNS:localhost,DNS:$SERVIDOR_NOME"
for ip in ${SERVIDOR_IPS_EXTRAS//,/ }; do IPS="$IPS,IP:$ip"; done

mkdir -p "$CA_DIR" "$CERT_DIR"
# Certificado antigo sem o IP atual do servidor: gera outro
if [ -f "$CERT_DIR/noc.crt" ] && ! openssl x509 -in "$CERT_DIR/noc.crt" -noout -ext subjectAltName | grep -q "IP Address:$SERVIDOR_IP\b"; then
    echo "[!] IP do servidor mudou: gerando certificado novo"
    rm -f "$CERT_DIR/noc.crt" "$CERT_DIR/noc.key" "$CERT_DIR/noc-cadeia.crt"
fi
chmod 700 "$CA_DIR"

# 1. Autoridade certificadora do NOC (10 anos). O .crt é público: é ele que se instala no Windows.
if [ ! -f "$CA_DIR/ca.key" ]; then
    openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
        -keyout "$CA_DIR/ca.key" -out "$CA_DIR/ca.crt" \
        -subj "/C=BR/O=NOC SENAI TCC/CN=NOC SENAI - Autoridade Certificadora"
    chmod 600 "$CA_DIR/ca.key"
fi

# 2. Certificado do servidor (825 dias, limite aceito pelos navegadores), válido para os dois IPs da VM
if [ ! -f "$CERT_DIR/noc.crt" ]; then
    openssl req -newkey rsa:2048 -nodes -keyout "$CERT_DIR/noc.key" -out "$CERT_DIR/noc.csr" \
        -subj "/C=BR/O=NOC SENAI TCC/CN=noc.senai.local"
    printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" \
        "$IPS" > "$CERT_DIR/ext.cnf"
    openssl x509 -req -in "$CERT_DIR/noc.csr" -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
        -days 825 -sha256 -extfile "$CERT_DIR/ext.cnf" -out "$CERT_DIR/noc.crt"
    cat "$CERT_DIR/noc.crt" "$CA_DIR/ca.crt" > "$CERT_DIR/noc-cadeia.crt"
    rm -f "$CERT_DIR/noc.csr"
fi
chown root:grafana "$CERT_DIR"/noc.key "$CERT_DIR"/noc-cadeia.crt
chmod 640 "$CERT_DIR/noc.key"
chmod 644 "$CERT_DIR/noc-cadeia.crt"
cp "$CA_DIR/ca.crt" /var/www/html/NOC-SENAI-CA.crt   # para baixar e instalar no navegador

# 3. Apache: site 443 + redireciona HTTP -> HTTPS, menos para o próprio servidor (scripts usam http://localhost)
a2enmod -q ssl rewrite headers
cat > /etc/apache2/sites-available/noc-ssl.conf <<'EOF'
<VirtualHost *:443>
    DocumentRoot /var/www/html
    SSLEngine on
    SSLCertificateFile /etc/ssl/noc/noc-cadeia.crt
    SSLCertificateKeyFile /etc/ssl/noc/noc.key
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
</VirtualHost>
EOF
cat > /etc/apache2/conf-available/noc-redireciona-https.conf <<'EOF'
<VirtualHost *:80>
    DocumentRoot /var/www/html
    RewriteEngine On
    RewriteCond %{REMOTE_ADDR} !^127\.0\.0\.1$
    RewriteCond %{REMOTE_ADDR} !^::1$
    RewriteCond %{REQUEST_URI} !^/NOC-SENAI-CA\.crt$
    RewriteRule ^/(.*)$ https://%{HTTP_HOST}/$1 [R=301,L]
</VirtualHost>
EOF
a2dissite -q 000-default
a2ensite -q noc-ssl
a2enconf -q noc-redireciona-https
apache2ctl configtest
systemctl reload apache2

echo "[ok] HTTPS ativo. CA para instalar no Windows: $CA_DIR/ca.crt"
