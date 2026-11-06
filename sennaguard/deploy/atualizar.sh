#!/usr/bin/env bash
# Puxa a última versão do GitHub e reinstala (mantém banco, usuários e configuração).
# O repositório é privado: o servidor precisa de uma deploy key read-only configurada.
set -euo pipefail
cd /opt/noc-senai-tcc
git pull --ff-only
bash sennaguard/deploy/instalar.sh
