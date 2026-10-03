# NOC SENAI — Monitoramento de redundância Fibra x Rádio com Zabbix e IA

Projeto de TCC (SENAI 2026): rede Matriz/Filial com dois enlaces (fibra principal e rádio de backup, OSPF) monitorada por Zabbix 7.0, com Grafana, página de status e um **Analista NOC com IA** que investiga cada incidente e envia o relatório por e-mail.

![Arquitetura](docs/arquitetura.png)

## O que tem aqui

| Pasta | Conteúdo |
| --- | --- |
| [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md) | Documentação técnica completa (topologia, servidor, monitoramento, dashboards, e-mail, IA, segurança, dia da montagem, operação) |
| [`noc/`](noc) | Scripts Python que configuram o Zabbix pela API e o serviço do Analista IA. Na VM ficam em `/root/noc` |
| [`routeros/`](routeros) | Scripts dos MikroTiks (R-MATRIZ, R-FILIAL, switches, nova filial) e o bloco de integração com o NOC |
| [`grafana/`](grafana) | Dashboard do Grafana e arquivos de provisionamento (o da fonte de dados é só exemplo) |
| [`sistema/`](sistema) | Unidade systemd do analista e tarefas do cron |
| [`historico/`](historico) | Scripts da primeira versão (feitos com o Gemini), com as senhas removidas |

## Componentes

- **Zabbix 7.0** em VM Debian 12 (`192.168.10.50` na rede da Matriz, `192.168.137.50` pelo NAT do notebook).
- **Monitoramento:** ping em cada enlace a cada 10 s, alcance da LAN da Filial a cada 1 s, caminho ativo calculado, SNMP do R-FILIAL (template *Mikrotik by SNMP*).
- **9 triggers:** fibra caída/failover, rádio caído, Filial isolada, failover lento, fibra instável, latência alta e 3 de previsão de degradação do rádio.
- **Tempo de failover** medido em segundos a cada queda da fibra.
- **Dashboards:** Zabbix (3 páginas, incluindo mapa da topologia) e Grafana (`:3000`, tela para TV).
- **Página de status** para os usuários da Filial em `/status`.
- **E-mail** via Gmail: alerta, análise da IA e normalização.
- **Analista IA:** Google Gemini (camada gratuita) com 6 ferramentas somente leitura; Claude opcional.

## Instalação resumida (na VM, como root)

```bash
# 1. Python para a IA e os scripts
apt install -y python3-venv snmp
python3 -m venv /opt/noc-analista && /opt/noc-analista/bin/pip install anthropic google-genai

# 2. Copiar noc/ para /root/noc e gravar as credenciais (nunca no código)
echo "TOKEN_API_ZABBIX" > /root/.zabbix_token && chmod 600 /root/.zabbix_token
echo "CHAVE_GEMINI"     > /root/.gemini_key   && chmod 600 /root/.gemini_key

# 3. Configurar o Zabbix (todos os scripts podem ser rodados de novo sem duplicar nada)
cd /root/noc
/opt/noc-analista/bin/python fix_redundancia.py
/opt/noc-analista/bin/python setup_zabbix_analista.py
/opt/noc-analista/bin/python mapa_topologia.py
/opt/noc-analista/bin/python dash_noc.py
/opt/noc-analista/bin/python setup_grafana.py   # requer Grafana + plugin alexanderzobnin-zabbix-app

# 4. Serviço e tarefas agendadas
cp ../sistema/noc-analista.service /etc/systemd/system/ && systemctl enable --now noc-analista
cp ../sistema/cron.d/* /etc/cron.d/
```

Detalhes, testes e solução de problemas estão em [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md).

## Segurança

Nenhuma senha, token ou chave está neste repositório. Credenciais ficam em arquivos `chmod 600` na VM (`/root/.zabbix_token`, `/root/.zabbix_token_analista`, `/root/.gemini_key`, `/root/.grafana_admin`). Nos scripts RouterOS as senhas aparecem como `<SENHA_...>` para preencher na hora de colar.
