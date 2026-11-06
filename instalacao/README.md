# Instalação do NOC SENAI

Tudo o que é preciso para montar o projeto num servidor, reunido nesta pasta. O **código-fonte** fica nas pastas do projeto (`noc/`, `sennaguard/`, `routeros/`, `grafana/`…); aqui ficam só os **instaladores e os guias**.

> **Como o código chega ao servidor:** este projeto **não** se instala puxando do GitHub. Coloque a pasta do projeto no servidor em **`/opt/noc-senai-tcc`** do jeito que preferir (cópia pela rede, `rsync`/`scp` por SSH, ou pendrive) e rode os instaladores a partir dela. O GitHub é só onde o código é versionado.

## Ordem recomendada

| Passo | O quê | Arquivo |
| --- | --- | --- |
| 1 | Preparar a VM no servidor (ESXi) | [`vm-esxi.md`](vm-esxi.md) |
| 2 | Instalar o NOC (Zabbix 7.0, Grafana, Analista IA, HTTPS, backup) | [`instalar-noc.sh`](instalar-noc.sh) + [`noc-servidor.md`](noc-servidor.md) |
| 3 | Instalar o painel SennaGuard | [`instalar-sennaguard.sh`](instalar-sennaguard.sh) + [`sennaguard.md`](sennaguard.md) |
| 4 | Montar/remontar a bancada (MikroTik + antenas) | [`bancada-remontar.md`](bancada-remontar.md) |

## 1. NOC (servidor)

Com o projeto em `/opt/noc-senai-tcc`, como root num Debian 12 limpo:

```bash
cp /opt/noc-senai-tcc/noc.conf.exemplo /etc/noc/noc.conf   # ajuste os IPs (SERVIDOR_IP e a rede)
nano /etc/noc/noc.conf
bash /opt/noc-senai-tcc/instalacao/instalar-noc.sh
```

O instalador monta Zabbix 7.0, banco, Apache, HTTPS com CA própria, Grafana, Analista IA, e-mail, dashboards, mapa, página de status, backup diário e as tarefas agendadas. Pode ser rodado de novo quando quiser — cada etapa pula o que já está pronto. Senhas e chaves são **perguntadas** (não aparecem na tela) e guardadas em arquivos `chmod 600` do root. Detalhes e solução de problemas em [`noc-servidor.md`](noc-servidor.md).

## 2. SennaGuard (painel)

Depois que o NOC estiver no ar, no mesmo servidor:

```bash
bash /opt/noc-senai-tcc/instalacao/instalar-sennaguard.sh
```

Publica o painel em `https://<SERVIDOR_IP>/sennaguard/` pelo mesmo Apache. Reaproveita o token do Zabbix, as chaves de IA e a chave SSH de leitura dos MikroTik que o NOC já configurou. Passo a passo (inclusive teste local no Windows/Linux) em [`sennaguard.md`](sennaguard.md).

## Atualizar depois

Coloque a versão nova do projeto em `/opt/noc-senai-tcc` (mantendo `/etc/noc`, `/etc/sennaguard` e `/var/lib/*`) e rode de novo o instalador correspondente. Para o painel há um atalho: [`atualizar-sennaguard.sh`](atualizar-sennaguard.sh).

## referencia/

A pasta [`referencia/`](referencia) guarda roteiros antigos de implantação do SennaGuard (de quando o deploy era por `git`). Ficam como histórico — o guia válido é o [`sennaguard.md`](sennaguard.md).
