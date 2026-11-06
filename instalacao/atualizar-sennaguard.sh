#!/usr/bin/env bash
# Atualiza o SennaGuard para a versão que está em /opt/noc-senai-tcc.
#
# O deploy NÃO usa git pull: coloque a versão nova do projeto em /opt/noc-senai-tcc
# (cópia, rsync, pendrive — como preferir), mantendo /etc/sennaguard e /var/lib/sennaguard,
# e rode este script. Ele apenas reexecuta o instalador, que reconstrói o venv e a interface
# e reinicia o serviço, preservando banco, usuários e configuração.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
bash "$REPO/instalacao/instalar-sennaguard.sh"
