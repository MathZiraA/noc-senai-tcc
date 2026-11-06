# NOC SENAI — Monitoramento de redundância Fibra x Rádio com Zabbix e IA

Projeto de TCC (SENAI 2026): rede Matriz/Filial com dois enlaces (fibra principal e rádio de backup, OSPF) monitorada por Zabbix 7.0, com Grafana, página de status e um **Analista NOC com IA** que investiga cada incidente e envia o relatório por e-mail.

![Arquitetura](docs/arquitetura.png)

## O que tem aqui

| Pasta | Conteúdo |
| --- | --- |
| [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md) | Documentação técnica completa (topologia, servidor, monitoramento, dashboards, e-mail, IA, segurança, dia da montagem, operação, testes na bancada real) |
| [`docs/equipamentos.html`](docs/equipamentos.html) | Ficha da bancada: o que está configurado em cada equipamento e o histórico de mudanças (gerada por `bancada/gerar_ficha.py`) |
| [`bancada/`](bancada) | Configuração automática dos MikroTik (gerar, testar, aplicar, conferir); o passo a passo para remontar está em [`instalacao/bancada-remontar.md`](instalacao/bancada-remontar.md) |
| [`noc/`](noc) | Scripts Python que configuram o Zabbix pela API e o serviço do Analista IA. Na VM ficam em `/root/noc` |
| [`sennaguard/`](sennaguard) | **Painel web do NOC** (FastAPI + React): login por perfil, chamados, backups, mapa, teste de failover. Instala em `/opt/noc-senai-tcc/sennaguard` — ver [`sennaguard/README.md`](sennaguard/README.md) |
| [`instalacao/`](instalacao) | Instaladores e guias para montar tudo num servidor novo (NOC + SennaGuard + bancada) |
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

## Revisão CTI (10/2026)

Pedidos da reunião com a CTI, já implementados (detalhes na seção 14 da documentação):

- **Portas:** ether1 = rádio, sfp1 = fibra óptica (SFP), ether2 = reserva, ether3/4/5 = rede local em `bridge-LAN`.
- **Loopback /32** em cada roteador (`10.255.255.1` / `10.255.255.2`): router-id do OSPF e endereço de monitoramento, alcançável pela fibra ou pelo rádio.
- **Fibra degradada:** alertas de latência, perda, piora em relação ao normal e previsão, mesmo sem a fibra cair.
- **Troca por qualidade:** netwatch no MikroTik (RouterOS 7.4+) sobe o custo OSPF da fibra para 200 quando ela degrada, e o tráfego vai para o rádio.
- **Chamados:** queda que passa de 1 h gera o chamado `NOC-<n>` com e-mail formal ao cliente e registro num livro encadeado por SHA-256 (`noc/chamados.py --verificar`).
- **Antenas** monitoradas como hosts próprios.
- **Testes:** `simular_queda.py --cenario queda|degradacao|chamado`.

## Bancada real (16/10/2026)

Os dois MikroTik hEX S (RouterOS 7.24.5) e as duas antenas Ubiquiti PowerBeam M5 estão configurados e testados:

- **Fibra** (sfp1): OSPF fechado, ~0,6 ms. **Rádio** (ether1): sinal de -53/-52 dBm, 0% de perda à distância, 6,4 ms.
- **Failover:** queda da fibra resolvida em 3,9 s pelo rádio; volta para a fibra sem perda.
- Detalhes nas seções 19 a 21 da documentação e na ficha `docs/equipamentos.html`.

## Instalação num servidor novo (Debian 12, como root)

Os instaladores e os guias ficam na pasta [`instalacao/`](instalacao). Coloque o projeto no servidor em `/opt/noc-senai-tcc` (cópia, `rsync` ou pendrive — **não** é por `git`) e rode um comando que monta tudo: Zabbix 7.0, banco, Apache, HTTPS com CA própria, Grafana, Analista IA, e-mail, dashboards, mapa, página de status, backup diário e tarefas agendadas.

```bash
cp /opt/noc-senai-tcc/noc.conf.exemplo /etc/noc/noc.conf   # 1ª vez: ajuste SERVIDOR_IP e os IPs da rede
nano /etc/noc/noc.conf
bash /opt/noc-senai-tcc/instalacao/instalar-noc.sh         # instala e configura tudo
```

Depois, o painel: `bash /opt/noc-senai-tcc/instalacao/instalar-sennaguard.sh`.

Na segunda execução o instalador **pergunta** (sem mostrar na tela):

1. o **token da API do Zabbix**: ele explica como entrar com a senha padrão, trocá-la e criar o token;
2. a **senha de app do Gmail** da conta que envia os alertas;
3. a **chave do Google Gemini** (opcional; sem ela, tudo funciona menos o Analista IA).

No fim ele gera o bloco RouterOS já com o IP do servidor, para colar no R-FILIAL. O instalador pode ser rodado de novo a qualquer momento: cada etapa pula o que já está pronto. Endereços e nomes ficam em `/etc/noc/noc.conf` (modelo: [`noc.conf.exemplo`](noc.conf.exemplo)); nenhum script tem IP fixo.

Passo a passo completo, preparo da VM e solução de problemas em [`instalacao/`](instalacao). Documentação técnica em [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md).

## Segurança

Nenhuma senha, token ou chave está neste repositório. Credenciais ficam em arquivos `chmod 600` na VM (`/root/.zabbix_token`, `/root/.zabbix_token_analista`, `/root/.gemini_key`, `/root/.grafana_admin`). Nos scripts RouterOS as senhas aparecem como `<SENHA_...>` para preencher na hora de colar.
