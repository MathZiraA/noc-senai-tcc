# Auto-monitoramento do servidor (Fase 1)

O servidor do NOC passa a **se monitorar** no Zabbix e no Grafana, expondo os sinais que denunciam um
ataque (como um DoS) **antes** de a Fase 2 blindar a camada web. Esta fase é só de **detecção**: nada aqui
bloqueia tráfego — apenas observa e alerta.

## O que é instalado

| Arquivo | Vai para | Função |
| --- | --- | --- |
| `noc-metricas.sh` | `/usr/local/bin/` | Coletor: emite cada métrica de ataque (TCP, Apache, fail2ban, SSH, firewall) |
| `userparameters-noc.conf` | `/etc/zabbix/zabbix_agent2.d/noc.conf` | Expõe `noc.srv[*]` ao Zabbix |
| `sudoers-noc-metricas` | `/etc/sudoers.d/noc-metricas` | `sudo` sem senha só para 3 comandos de leitura (fail2ban, nft, journalctl) |
| `apache-status-noc.conf` | `/etc/apache2/conf-available/noc-status.conf` | `mod_status` só para `127.0.0.1` (workers ocupados) |
| counter `noc_drop_input` | `infra/servidor/seguranca/nftables.conf` | Conta o que o firewall descarta (não muda o que é aceito) |
| `noc/monitorar_servidor.py` | Zabbix (API) | Host **NOC-SERVIDOR** + itens + gatilhos de ataque |
| `noc/grafana_servidor.py` | `/var/lib/grafana/dashboards/noc-servidor.json` | Painel **NOC - Servidor (segurança)** |

## Como aplicar

No servidor, como root, com o projeto em `/opt/noc-senai-tcc`:

```bash
bash /opt/noc-senai-tcc/infra/servidor/monitoramento/aplicar-monitoramento.sh
```

O script instala tudo, reinicia o agente, recarrega o Apache e o firewall (validando antes), cria o host no
Zabbix e provisiona o painel do Grafana. Pode rodar de novo; o host do Zabbix só avisa se já existir.

## O que é monitorado

**Sinais de ataque:** conexões `ESTABLISHED`, `SYN_RECV` (meia-abertas) e `TIME_WAIT`; conexões no site
(80/443); IP de origem com mais conexões; workers do Apache (ocupados/livres) e requisições por segundo;
IPs banidos pelo fail2ban; falhas de SSH por minuto; pacotes por segundo descartados pelo firewall.

**Saúde (consequência comum de um ataque):** CPU, carga média, RAM, swap e disco.

## Gatilhos (alertas)

Caem no grupo *Rede SENAI - Equipamentos*, então já disparam o e-mail e a investigação do Analista IA.

| Alerta | Severidade | Condição (macro ajustável) |
| --- | --- | --- |
| Possível SYN flood | Alta | `SYN_RECV` > `{$NOC_SYN_MAX}` (100) por 1 min |
| Possível flood HTTP | Alta | conexões no site > `{$NOC_HTTP_MAX}` (120) por 1 min |
| Flood de origem única | Alta | um IP > `{$NOC_TOPTALKER_MAX}` (50) conexões |
| Apache saturado | Alta | workers ocupados > `{$NOC_APACHE_MAX}`·`{$NOC_APACHE_PCT}`% (90) |
| SSH sob força bruta | Média | falhas de SSH > `{$NOC_SSHFAIL_MAX}` (10)/min |
| Firewall descartando muito | Aviso | descartes/s > `{$NOC_DROPS_MAX}` (10) |
| CPU / carga / RAM altas | Média | acima do limite por 5 min |
| Disco quase cheio | Alta | uso de `/` > `{$NOC_DISK_MAX}` (90%) |
| Servidor sem telemetria | Alta | sem dados do agente por 3 min |

Os limites são **macros do host NOC-SERVIDOR** no Zabbix: ajuste em *Configuration → Hosts → NOC-SERVIDOR
→ Macros* conforme o tráfego real, sem tocar no código. Depois de observar o normal por alguns dias,
calibre `{$NOC_HTTP_MAX}` e `{$NOC_SYN_MAX}` para o perfil da rede.

## Conferir se está coletando

```bash
zabbix_get -s 127.0.0.1 -k 'noc.srv[synrecv]'     # nº de conexões meia-abertas
zabbix_get -s 127.0.0.1 -k 'noc.srv[apache_busy]' # workers ocupados do Apache
sudo -u zabbix /usr/local/bin/noc-metricas.sh http # testa o coletor como o agente o chama
```

## Próximas fases

- **Fase 2 — blindagem:** limite de conexões/SYN por IP no nftables (80/443), `mod_evasive` no Apache e uma
  jail HTTP no fail2ban. (Altera o que o firewall aceita — exige confirmação e janela.)
- **Fase 3 — teste de resiliência:** carga controlada contra o próprio servidor para validar os limites.
