# Configuração real dos roteadores

`R-MATRIZ.rsc` e `R-FILIAL.rsc` são o `/export terse` dos roteadores em produção, feito pelo backup do SennaGuard
(sem senhas, usuários e chaves SSH). **É esta a referência do que está rodando.**

Os scripts da pasta de cima mostram como a rede foi montada, em etapas:

| Arquivo | Para quê |
| --- | --- |
| `r-matriz.rsc`, `r-filial.rsc` | instalação base (portas, OSPF, firewall, NTP, netwatch da fibra) |
| `routeros-r-filial-noc.rsc` | integração da Filial com o NOC (SNMP, usuário zabbix-ia) |
| `wan-redundancia.rsc` | redundância WAN do R-MATRIZ (VIVO + TIN) e SNMP da Matriz |
| `limpar-backups.rsc` | backup binário diário em rodízio de 7 arquivos |
| `template-nova-filial.rsc` | modelo para uma filial nova |
| `switches.rsc` | switches das LANs (SW-MATRIZ na ether3, SW-FILIAL) |

Para atualizar esta pasta: SennaGuard → Backups → **Fazer backup agora** e baixar a versão mais nova de cada roteador.
