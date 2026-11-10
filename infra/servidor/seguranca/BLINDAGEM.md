# Blindagem da camada web (Fase 2) e teste de resiliência (Fase 3)

Depois da Fase 1 (detecção), o servidor recebeu três camadas de defesa contra flood/DoS na camada web, e um
teste de carga controlado comprovou que elas seguram o tipo de ataque que antes derrubava o site.

## As três camadas (defesa em profundidade)

| Camada | Arquivo | O que faz |
| --- | --- | --- |
| **Firewall (nftables)** | `nftables.conf` | Por IP de origem em 80/443: no máx. 60 conexões novas/s e 100 simultâneas; o excesso é descartado (e contado em `noc_drop_input`) |
| **Apache (mod_evasive)** | `mod-evasive-noc.conf` | Responde 403 a quem passa de 25 req/s à mesma página ou 150 req/s ao site, bloqueando o IP por 30 s |
| **fail2ban (jail HTTP)** | `fail2ban-noc-http.conf` + `filter-noc-http-flood.conf` | Bane no firewall, por 10 min, o IP que ultrapassa 400 requisições em 20 s |

As três coexistem com o SSH (porta 22) sempre aberto à gerência; o ban HTTP do fail2ban atinge só 80/443.

## Como aplicar

No servidor, como root, com o projeto em `/opt/noc-senai-tcc`:

```bash
bash /opt/noc-senai-tcc/infra/servidor/seguranca/blindar-web.sh    # mod_evasive + fail2ban
nft -f /opt/noc-senai-tcc/infra/servidor/seguranca/nftables.conf   # limite por IP no firewall
```

> O firewall deve ser recarregado com uma trava de auto-reversão (reverter após alguns minutos se a
> conectividade cair), por segurança. O `nftables.conf` usa recarga atômica só da própria tabela, preservando
> a tabela e os banimentos do fail2ban.

## Resultado do teste de resiliência (10/11/2026)

Ataque controlado a partir de um cliente da LAN: **4000 requisições, 200 simultâneas** contra o site.

| Métrica | Resultado |
| --- | --- |
| Respostas ao atacante | **90% bloqueadas** (3593 × 403 do mod_evasive), 98 descartadas pelo firewall, 309 servidas |
| Apache | **permaneceu no ar** — teste local sempre 200; workers ocupados no pico ~100 (de 150), recuperados em segundos |
| Firewall | +616 pacotes descartados pelo limite por IP (`noc_drop_input`) |
| fail2ban | **baniu o IP atacante** em ~2 s após ultrapassar o limite |
| Monitoramento (Fase 1) | registrou o pico: 99 conexões no site, `apache_busy` 100, descartes do firewall |

Na Fase 1 (sem blindagem), um flood equivalente saturava o Apache e derrubava o site. Com a Fase 2, o mesmo
ataque é absorvido e o site continua respondendo.

## Ajuste fino

Os limites são conservadores (pensados para um ataque sustentado). Para tornar o alerta mais sensível ou
adequá-lo ao tráfego real, ajuste as macros do host NOC-SERVIDOR no Zabbix e os números em
`mod-evasive-noc.conf` / `fail2ban-noc-http.conf`, observando o tráfego normal por alguns dias.
