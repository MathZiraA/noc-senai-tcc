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

## Instalação num servidor novo (Debian 12, como root)

Um comando monta tudo: Zabbix 7.0, banco, Apache, HTTPS com CA própria, Grafana, Analista IA, e-mail, dashboards, mapa, página de status, backup diário e tarefas agendadas.

```bash
git clone https://github.com/MathZiraA/noc-senai-tcc.git && cd noc-senai-tcc
bash instalar_noc.sh            # 1ª vez: cria /etc/noc/noc.conf e para
nano /etc/noc/noc.conf          # ajuste SERVIDOR_IP e os IPs da rede
bash instalar_noc.sh            # instala e configura tudo
```

Na segunda execução o instalador **pergunta** (sem mostrar na tela):

1. o **token da API do Zabbix**: ele explica como entrar com a senha padrão, trocá-la e criar o token;
2. a **senha de app do Gmail** da conta que envia os alertas;
3. a **chave do Google Gemini** (opcional; sem ela, tudo funciona menos o Analista IA).

No fim ele gera o bloco RouterOS já com o IP do servidor, para colar no R-FILIAL. O instalador pode ser rodado de novo a qualquer momento: cada etapa pula o que já está pronto. Endereços e nomes ficam em `/etc/noc/noc.conf` (modelo: [`noc.conf.exemplo`](noc.conf.exemplo)); nenhum script tem IP fixo.

Detalhes, testes e solução de problemas estão em [`docs/DOCUMENTACAO.md`](docs/DOCUMENTACAO.md).

## Segurança

Nenhuma senha, token ou chave está neste repositório. Credenciais ficam em arquivos `chmod 600` na VM (`/root/.zabbix_token`, `/root/.zabbix_token_analista`, `/root/.gemini_key`, `/root/.grafana_admin`). Nos scripts RouterOS as senhas aparecem como `<SENHA_...>` para preencher na hora de colar.
