#!/usr/bin/env bash
# Puxa a última versão do GitHub e reinstala (mantém banco, usuários e configuração).
set -euo pipefail
cd /opt/sennaguard
git pull --ff-only
bash deploy/instalar.sh
