# SennaGuard: próximo passo no servidor (ponto de entrada fixo)

Você é uma sessão do Claude com acesso ao servidor do NOC (`192.168.10.50`), direto ou por SSH. O usuário sempre cola a mesma frase, que manda ler este arquivo. Quem mantém este arquivo é o desenvolvedor: a cada mudança, a tarefa da vez aparece na tabela abaixo.

## Como agir

1. Leia o registro do que já foi feito neste servidor:
   `cat /var/lib/sennaguard/passos-feitos.log 2>/dev/null || echo "(nenhum passo feito ainda)"`
2. Na tabela **Tarefas**, de cima para baixo, pegue a primeira cujo **ID** ainda não está no registro.
   Se todas estiverem, diga ao usuário "Nada novo para fazer" e confira só a saúde do painel:
   - `systemctl is-active sennaguard`;
   - `curl -s http://127.0.0.1:8010/api/publico`;
   - as últimas linhas do `journalctl -u sennaguard`.
3. Antes de executar, diga ao usuário qual tarefa vai fazer e quanto ela mexe: só leitura, atualização do painel ou algo que precisa dele.
4. Baixe e siga o roteiro da tarefa. As **Regras de segurança** de `docs/IMPLANTACAO-SERVIDOR.md` valem sempre.
5. Só quando o roteiro terminar **sem pendências**, registre o passo:
   `echo "$(date -Is) <ID> ok $(git -C /opt/sennaguard log --oneline -1 | cut -c1-7)" >> /var/lib/sennaguard/passos-feitos.log`
   Com pendência do usuário, não registre: na próxima vez a tarefa é retomada.
6. Entregue o relatório pedido no roteiro. Termine dizendo qual é a próxima tarefa da tabela, se houver.

Os roteiros ficam em `https://raw.githubusercontent.com/MathZiraA/sennaguard/main/docs/<arquivo>`.

## Tarefas

| ID | Data | Arquivo | O que é |
| --- | --- | --- | --- |
| `2026-10-23-rede` | 23/10/2026 | `ATUALIZAR-E-VALIDAR-REDE.md` | Atualizar o painel (painel personalizável, zoom, anexos, perfil, tour, celular) e refazer tudo o que depende da rede: SSH nos MikroTik, antenas no Zabbix, validação real, backup e teste de ponta a ponta |
