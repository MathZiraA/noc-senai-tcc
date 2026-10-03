#!/bin/bash
set -e

# 1. Atualizar repositórios e instalar utilitários
apt update && apt upgrade -y
apt install -y wget curl mariadb-server

# 2. Instalar o repositório oficial do Zabbix 7.0 LTS
wget https://repo.zabbix.com/zabbix/7.0/debian/pool/main/z/zabbix-release/zabbix-release_latest_7.0+debian12_all.deb
dpkg -i zabbix-release_latest_7.0+debian12_all.deb
apt update

# 3. Instalar Zabbix Server, Frontend, Apache e Agente
apt install -y zabbix-server-mysql zabbix-frontend-php zabbix-apache-conf zabbix-sql-scripts zabbix-agent2

# 4. Criar o banco de dados e usuário
DB_PASS="<REMOVIDA>"

mariadb -e "CREATE DATABASE zabbix CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;"
mariadb -e "CREATE USER 'zabbix'@'localhost' IDENTIFIED BY '$DB_PASS';"
mariadb -e "GRANT ALL PRIVILEGES ON zabbix.* TO 'zabbix'@'localhost';"
mariadb -e "FLUSH PRIVILEGES;"

# 5. Importar o schema inicial do Zabbix
zcat /usr/share/zabbix-sql-scripts/mysql/server.sql.gz | mysql -u zabbix -p"$DB_PASS" zabbix

# 6. Configurar a senha no arquivo de configuração do Zabbix Server
sed -i "s/# DBPassword=/DBPassword=$DB_PASS/" /etc/zabbix/zabbix_server.conf

# 7. Reiniciar e habilitar os serviços
systemctl restart zabbix-server zabbix-agent2 apache2 mariadb
systemctl enable zabbix-server zabbix-agent2 apache2 mariadb

echo "Instalação concluída com sucesso!"
