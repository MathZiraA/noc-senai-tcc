# SennaGuard — sistema de interface

## Direção

Sala de NOC à noite, sobre base **preta**. A referência de estrutura é o painel FlowGest — fundo preto frio, cards escuros com borda sutil, um acento único e disciplinado, sem degradês decorativos. A identidade é a da marca SennaGuard: **roxo `#521B89`** como acento, sobre preto `#0a0c11`. O roxo é o patch de fibra; o teal é o enlace de rádio. Quem usa:
- o operador de plantão, olhando a TV ou o notebook;
- o cliente da Filial, abrindo um chamado.

A primeira leitura de qualquer tela responde a uma pergunta: **a Filial tem redundância agora?**

Princípio: gastar a ousadia em um lugar só. O estado normal é quase todo neutro; a cor só aparece onde há informação (enlace, severidade, status).

## Marca

**LogoSG:** um "S" geométrico angular, traçado em roxo. A variante `tile` (fundo roxo da marca, "S" em branco, raio 9 px) aparece no cabeçalho e no login; a variante simples, em roxo, na barra lateral. Substitui qualquer "S" genérico.

## Assinatura: o trilho do caminho ativo

Matriz ⇄ Filial com dois trilhos. A fibra fica em cima, em roxo, e o rádio embaixo, em teal.

| Estado | Como aparece |
| --- | --- |
| Ativo | tracejado andando (`.trilho-ativo`) e halo de 6 px a 25% |
| Em espera | linha sólida a 45% |
| Fora | tracejado vermelho, cortado no meio |

O trilho aparece em:
- `Trilho` (topo de Equipamentos, que é a página de topologia; a Visão segue a grade da referência);
- `TrilhoMini` (28 px, nas listas de alertas e chamados, em vermelho no enlace atingido; o assunto é o texto antes do ":");
- a faixa do topo do Login;
- a `Foto` do enlace no chamado SG.

**Regra:** todo elemento novo que fale de um enlace usa esse desenho, nunca um ícone genérico.

## Tokens (`frontend/src/index.css`, `@theme`)

Tema escuro (padrão); o tema claro inverte a hierarquia e usa o roxo exato da marca `#521B89` como primário.

| Token | Valor | Uso |
| --- | --- | --- |
| `lateral` | #090a0e | barra lateral (preto frio) |
| `rack` | #0a0c11 | fundo da área de trabalho (preto) |
| `painel` | #12151d | cards |
| `painel-alto` | #1a1e28 | pílulas, chips, menus, diálogos |
| `fenda` | #0c0e14 | campos (afundados) |
| `tinta` / `-2` / `-3` / `-4` | #f3f4f6 / #c1c4cc / #888c97 / #595d68 | texto: principal / apoio / meta / desligado |
| `fibra` | #a06ee8 | enlace principal **e** acento da marca/ação primária (roxo clareado p/ contraste no preto) |
| `radio` | #4fb8c4 | enlace de backup, sinal em dBm |
| `led` | #35c98a | link up, livro íntegro |
| `desastre` `alta` `media` `aviso` | #f0576f #ee7f90 #c783e6 #a98cf0 | severidades: crítico (Desastre/Alta) rosa, aviso (Média/Aviso) lilás. `media` também marca chamado SG aberto |
| `limite` | #b85a7a | linha tracejada do limite crítico nos gráficos |
| `fio` / `fio-forte` | branco 6% / 11% | bordas e divisores |

As cores de severidade só aparecem onde há problema. A tela em estado normal é quase toda cinza-neutra, com o roxo pontuando ação e caminho ativo.

## Profundidade e forma

- **Profundidade:** só bordas (`border-fio`), sem sombra em card. `shadow-2xl` fica só para menus e diálogos flutuantes.
- **Raio:** `rounded-md` 6 px (chips), 7 px (botões), `rounded-lg` 8 px (campos, itens de menu), 10 px (barra de contexto), `rounded-xl` 12 px (cards), `rounded-full` (pílulas de alerta).
- **Brilho:** o `Led` (ponto de 6 px com `box-shadow` da própria cor) é o único brilho da interface. Ele pulsa (`.respira`) só quando o estado exige atenção.
- **Scrollbar:** fina (5 px), trilho transparente.

## Tipografia

- **Fontes:** Bricolage Grotesque (títulos e display), Hanken Grotesk (interface e corpo) e JetBrains Mono (IPs, portas, `NOC-xxx`/`SG-xxx`, hashes). Empacotadas via @fontsource, porque a Filial pode estar sem internet.
- **Escala:** base de 13 px. Meta 10.5–11 · corpo 13 · navegação 13.5 · título de card 17/600 (Bricolage) com o valor ao lado em roxo 17/600 e "há X" 10.5 · título de página 22 em Bricolage, formato migalha (`Enlaces › Matriz ⇄ Filial`).
- **Hierarquia:** feita por peso e tinta, não só por tamanho. Valor 600/`tinta`, rótulo 500/`tinta-2`, meta 400/`tinta-3`.
- **Números:** todo número dinâmico usa `.num` (tabular-nums).

## Espaçamento (base 4 px)

| Elemento | Medidas |
| --- | --- |
| Card | `px-5 py-5`; card de gráfico `px-9 pt-7 pb-5` |
| Gap entre blocos | `gap-3` (12 px) |
| Barra de contexto | `min-h-[52px] px-7`, itens separados por divisor vertical de 20 px |
| Linhas de lista | `px-3 py-2` (compactas) ou `px-5 py-3.5` (tabelas) |
| Barra lateral | 240 px (recolhida 76 px); logo + "SennaGuard" no topo; itens `h-10`, ícones Phosphor preenchidos 19 px; ativo `#171b24` sem borda; ponto rosa/lilás no lugar de contador |
| Cabeçalho | `h-[76px]`, sem linha; bloco da organização à esquerda (tile roxo com "S" + SENAI + NOC Matriz · Filial) |
| Conteúdo | `max-w-[1400px] px-10` |
| Grade da Visão | `[1fr_300px]`: Latência | Alertas / Tráfego | Caminho ativo |

## Componentes (`components/ui.tsx`, `Modal.tsx`, `Atendimento.tsx`)

- **Botao:** `h-8`, `px-3.5`, raio 7 px, 12.5/500, `active:scale-[0.97]`. Variantes:
  - `primario`: fundo `fibra`, texto branco;
  - `quieto`: cinza cheio `#171a22` ("Exportar relatório");
  - `contorno`: borda `#262a34` ("Últimas 24 horas ▾");
  - `perigo`: vermelho a 12%.
- **Chip:** `h-[26px]`, `px-2.5`, `rounded-md`, 11.5/500, `bg-painel-alto` ("Limites", "Baixar", "Detalhes"); ativo `bg-fibra/20`.
- **Gráfico** (`Grafico.tsx`): sem eixo Y e sem grade; eixo X só com horas cheias; área roxa em gradiente (50% → 4%); acima do limite crítico, linha e área rosa; limites tracejados `6 5` com rótulo "Crítico : 30 ms" à esquerda; incidente = faixa rosa com borda e balão "⚠ Fibra fora / das hh:mm às hh:mm".
- **Pílula de alerta:** `h-[30px]`, `rounded-full`, `bg-painel-alto`: ponto + nome curto 600 + "às dd/mm hh:mm (duração)". O alerta ativo mais grave ganha contorno na cor da severidade. Rodapé "● Crítico n · ● Aviso n · Total n".
- **Campo:** `h-9` (login `h-10`), `bg-fenda`, `border-fio`, foco `border-fibra/60`.
- **Escolha em cartões** (`Opcoes`, papel do usuário): rádio nativo `sr-only`. Selecionado com `border-fibra/60 bg-fibra/10`.
- **Segmentado:** trilho `bg-fenda` p-0.5, item ativo `bg-painel-alto`.
- **Sev:** pílula com o texto na cor da severidade sobre a mesma cor a 12%.
- **StatusChamado:** Led + rótulo. Aberto = `media` (pulsa), em atendimento = `fibra`, resolvido = `led`.
- **Modal:** Radix Dialog.
  - `lado` = gaveta de 520 px para detalhe (alerta, chamado), entrada `gaveta` em 240 ms;
  - centro = 460 px para formulário, entrada `surge` em 200 ms;
  - easing `cubic-bezier(0.23,1,0.32,1)`.
- **Card de alerta na Visão:** ativo = borda da severidade a 45% e fundo a 7%; resolvido = `border-fio`.
- **Histórico** (chamado SG): linha vertical `border-fio`, ponto roxo para a equipe e âmbar para o cliente, hash em mono 10 px `tinta-4`.

## Padrões de tela

- **Título:** h1 22 (Bricolage) e uma frase de apoio em `tinta-3`. A ação primária fica à direita.
- **Lista principal:** um card `!p-0` com linhas separadas por `border-fio`. Clicar abre a gaveta, com o estado na URL (`?id=` ou `?sg=`).
- **Integridade** (chamados): faixa com escudo. Íntegro = `led` a 6%, adulterado = `desastre` a 10%.
- **Perfil Cliente:** vê menos, nunca vê uma tela quebrada. Esconde a barra de contexto do host e troca Alertas por "Seus chamados" com o botão Abrir chamado.
- **Vazio:** borda tracejada `border-fio` com uma frase útil ("Nenhum chamado. Tudo certo com a Filial.").

## Movimento

- Até 240 ms, só `transform` e `opacity`.
- Pressionar: scale 0.97.
- A animação contínua (trilho, Led) é desligada com `prefers-reduced-motion`.
