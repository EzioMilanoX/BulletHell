# PARITY_PLAN.md — o que falta para o port ECS igualar (ou superar) o legado

> **Progresso (Fase 13, ver MIGRATION.md):** **Todos os P0 (P0-1 a
> P0-5) e todos os P1 (P1-1 a P1-7) já aplicados**, mais o dev overlay/
> cheats de P2, o `balance.json` hot-reload, o texto de "SELECT_RUSH_
> PLAYLIST" e o escalonamento de HP do SINS RUSH. Os detalhes de cada
> um continuam abaixo (specs exatas + aproximações assumidas) — leia
> como registro do que foi decidido, não mais como pendência. Resta só
> **Tela Cheia** (exigiria método novo no `IRenderer` da engine — fora
> do escopo deste port) e itens cosméticos de P3 já documentados.

## 0. Como isto foi produzido

Estudo exaustivo do legado (`main.py` ~3700 linhas + `entities.py` ~5500
linhas) via: (1) 6 agentes de extração de spec citando `arquivo:linha` para
cada número/cor/timing/texto (render de gameplay, HUD, bosses não-SINS,
bosses SINS, menus/telas, jogador+armas+skills+dificuldade+meta); (2)
captura manual de 8 screenshots do legado rodando (menu → seleção → jogo →
game over); (3) leitura completa do port atual (`bullethell/*.py`,
`bullethell/data/*.json`, `scenes.py`, `composition.py`). As specs
completas dos 6 agentes (~180KB) estão preservadas no scratchpad da sessão
(`visual_reference_notes.md` + jornal do workflow) caso seja preciso
revisitar um número específico.

Convenção de prioridade: **P0** quebra a experiência/estrutura central (o
jogo "não é o mesmo jogo"); **P1** gap visível de paridade (o jogador nota
a diferença numa run normal); **P2** meta/polish (não afeta o "feel"
minuto-a-minuto); **P3** cosmético/numérico menor.

---

## 1. Resumo executivo — por que "nada está como o esperado"

O port tem os 16 bosses jogáveis e os sistemas de armas/skills/mutadores
razoavelmente fiéis *nos números centrais*. Mas ele diverge do legado em
cinco eixos estruturais que dominam a sensação de jogo, não em detalhes
de acabamento:

1. **Não existe progressão/gating.** No legado, quase tudo começa
   bloqueado e se conquista jogando (dificuldades, skills, skill+/arma+,
   o boss ÔMEGA, o mutador CLAUSTROFOBIA). No port, tudo está disponível
   desde o primeiro segundo — não há save de desbloqueios, só
   estatísticas soltas.
2. **A dificuldade é uma estrutura diferente.** O legado tem 5 tiers
   (FÁCIL/NORMAL/DIFÍCIL/EXPERT/ABISSAL), cada um com mecânicas próprias
   (Segundo Fôlego no EXPERT; Fragmentação+Vingança no ABISSAL, que é a
   recompensa por vencer o SINS Rush) e uma DDA (Difficulty) que reage ao
   HP do boss em tempo real. O port tem 3 dificuldades como multiplicador
   plano de HP/velocidade — sem DDA, sem EXPERT, sem ABISSAL como tier
   (virou um mutador opcional de graça).
3. **O menu é outro produto visualmente.** Card com barra colorida,
   step-dots com breadcrumb, layout de 2 colunas com painel gigante — vs.
   uma lista central genérica no port. Faltam telas inteiras (RECORDS,
   SISTEMA/SETTINGS) e o overlay de dev mode.
4. **O boss Clássico está incompleto e um boss que nunca existiu no
   legado foi inventado.** Da lista de patterns real (10), o port só
   roda 5 no Clássico; os outros 2 numéricos existentes (STOP&GO,
   BOOMERANG) foram religados a um boss "Mago do Tempo" que não existe no
   jogo original.
5. **Faltam sistemas inteiros**: replay, dev cheats (F9/F10/F3-F8),
   Segundo Fôlego, DDA, tela RECORDS, tela SETTINGS.

O bom: as **armas e skills batem bem** nos números centrais (fire rate,
dano, cooldowns quase todos conferem contra `entities.py`), os
**gimmicks dos pecados** (holofote da Soberba, portão de fantasmas da
Preguiça, roubo de CD da Inveja, slam da Ira, Sétimo Selo) estão
implementados com a lógica certa, e o **áudio procedural do port já supera
o legado** (que é literalmente mudo — `AudioManager` existe mas nunca é
alimentado, spec §9 do documento de jogador/meta).

---

## 2. P0 — Quebram a experiência/estrutura central

### P0-1. Meta-progressão / gating ausente por completo — ✅ resolvido (Fase 13b)

- **Legado** (`entities.py:5035-5495`, `SaveManager`): persiste
  `highest_cleared_diff`, `unlocked_skills` (começa só `[NENHUMA, DASH]`),
  `unlocked_mutators`, `omega_boss_unlocked`, `sins_rush_cleared`,
  `mastery` (7 desafios), `skill_plus_unlocked`, `weapon_mastery` (10
  desafios), `weapon_plus_unlocked`, `settings`. As telas de seleção
  mostram `[BLOQUEADO]` e a navegação pula itens travados
  (`_nav_diff`/`_nav_skill`/`_nav_boss`, main.py:1783-1805).
- **Port** (`main_ecs.py:26-35` `_load_save`): só
  `runs/total_kills/total_deaths/total_graze/achievements`. `scenes.py`
  não tem nenhum conceito de "locked" — `MENU_DIFF`/`MENU_SKILL`/
  `MENU_WEAPON`/`MENU_MUT`/`MENU_BOSS` mostram e permitem tudo desde o
  primeiro boot. `_has_plus()` (scenes.py:229-231) só checa se a
  variante "+" **existe nos dados**, nunca se foi **desbloqueada** —
  ou seja, todo skill+/arma+ está disponível de graça a qualquer hora.
- **Impacto:** esta é provavelmente a causa nº1 de "nada está como o
  esperado" — o jogo legado é sobre *ganhar* acesso; o port é um sandbox
  aberto.
- **Ação recomendada:** portar `SaveManager` inteiro (campos, gating,
  `on_win`/`on_death`, cheat_unlock_all/wipe_save) para o formato
  `save_ecs.json`; adicionar bloqueio + skip-de-navegação nos menus do
  port; wire the 13 conquistas atuais (e expandir para as 32 do legado,
  ver P1-6) a recompensas reais.

### P0-2. Dificuldade: estrutura de 5 tiers vs. 3 multiplicadores planos, sem DDA — ✅ resolvido (Fase 13a)

- **Legado** (`entities.py:565-665`): 5 tiers com `speed_mult`/`boss_hp`
  próprios (TEST/EASY 0.75·200/NORMAL 1.0·300/HARD 1.3·400/EXPERT
  1.5·480/ABISSAL 1.65·560) + classe `Difficulty` (DDA) que recalcula um
  `tier` (1/2/3) a cada dano no boss pelo HP ratio (`>0.66`/`>0.33`/resto)
  e escala `spread_params`/`ring_params`/`spiral_params` (mais projéteis e
  anéis maiores em tier alto, `+1` bônus em dificuldades ≥HARD). EXPERT
  ativa `prep_scale=0.5` (telegraphs 2× mais rápidos) e o **Segundo
  Fôlego** (boss "sobrevive" com 1 HP por 3s quando morreria, uma vez por
  run — main.py:3343-3363). ABISSAL ativa **Fragmentação** (balas
  refletidas/OOB viram 2 fragmentos) e **Balas de Vingança** (anel homing
  ao trocar de fase/matar minion) e só é destravada vencendo o SINS Rush.
- **Port** (`composition.py:27-31` `DIFFICULTIES`): 3 entradas
  `facil/normal/dificil` como `(hp_mult, spd_mult)` fixo — nenhuma DDA,
  nenhum `tier`, nenhum EXPERT, e "abissal" foi reaproveitado como
  **mutador opcional de checkbox** (`scenes.py:88` `MUTATORS` lista
  `("abissal", ...)`, gratuito desde o início) que só liga a flag
  `fragment` na colisão — sem Balas de Vingança, sem gate de
  desbloqueio.
- **Ação recomendada:** adicionar EXPERT/ABISSAL como dificuldades de
  verdade (5ª/4ª posição no `_DIFF_ORDER`), implementar a classe
  `Difficulty`/DDA (tier por HP ratio, escala de `count`/`arc`/`gap` nos
  patterns dependente do tier — hoje `patterns.json` tem valores únicos,
  estáticos), Segundo Fôlego, e mover Fragmentação+Vingança de "mutador
  livre" para "efeito de ABISSAL" gated por `sins_rush_cleared`.

### P0-3. Boss Clássico incompleto + boss inventado ("Mago do Tempo") — ✅ resolvido (Fase 13c, ver nota abaixo)

- **Legado** (spec bosses-core §2, `entities.py:1790-2236`): CLÁSSICO tem
  **10 padrões**: SPREAD, RING, SPIRAL, SHARD, CIRCULAR, FRACTURE,
  BLASTER, LASER, STOP_AND_GO, BOOMERANG — com ciclo dependente da
  dificuldade (EASY usa um subconjunto simples; HARD reembaralha a cada
  volta), movimento por 8 waypoints com easing smoothstep, e 30% de
  chance de *fake prep* no LASER que corta para um SPREAD imediato.
- **Port** (`bullethell/data/bosses.json:4-18`): boss `"classic"` só
  referencia `classic/spread`, `classic/ring`, `classic/spiral`,
  `classic/circular_saw`, `classic/laser_wave` — **5 dos 8 padrões-base**
  (faltam SHARD, FRACTURE, BLASTER por completo — não há sequer um
  `pattern` com esse comportamento no arquivo). Os dois padrões restantes
  do clássico (STOP_AND_GO/BOOMERANG) **existem** em
  `patterns.json:33-42` (`timemage/stopgo_volley`,
  `timemage/boomerang_burst`) mas foram religados a um boss chamado
  **`"timemage"` que não existe no jogo legado** (não há "Mago do Tempo"
  em `entities.py`/`main.py` — é uma invenção do port).
- **Ação recomendada:** (a) implementar os padrões SHARD (16 polilinhas
  de rachadura, `entities.py:2014-2048`), FRACTURE (linha de corte +
  árvores, `entities.py:2085-2130`) e BLASTER (4 emissores nas bordas +
  `HazardPool` de queimadura, `entities.py:2153-2176`); (b) devolver
  STOP_AND_GO/BOOMERANG ao roster do Clássico; (c) decidir o destino do
  boss "Mago do Tempo" — ou removê-lo (fiel ao legado) ou mantê-lo
  explicitamente como conteúdo *novo* do port, deixando isso claro na UI
  em vez de ele ocupar o lugar de padrões do Clássico que faltam.

  **O que foi feito (Fase 13c):** "Mago do Tempo" foi **mantido** (é
  conteúdo funcional, não vale jogar fora) e o Clássico passou a
  referenciar os MESMOS padrões `timemage/stopgo_volley` e
  `timemage/boomerang_burst` — os dois bosses agora compartilham esses
  padrões em vez de o Clássico ficar sem eles. SHARD e FRACTURE foram
  implementados como **aproximação**: em vez da geometria exata de
  polilinhas do legado, reusam a máquina STOPGO já existente no port
  (crescem devagar por 1.5s/1.8s como o legado, mas ao disparar
  redirecionam para o *snapshot do jogador* em vez de "para baixo" fixo
  ou "continuar na própria direção"). BLASTER ganhou um emit type novo
  (`edge_burst`) que spawna dos 4 lados da tela mirando o jogador, sem a
  queimadura de `HazardPool` periódica do legado (fica como P2/P3 se
  quiser mais fidelidade). O Clássico agora tem 5 fases (era 3) para
  encaixar os 10 padrões sem empilhar emitters demais por fase; a DDA
  (tier 1/2/3 por HP) continua fixa em 0.66/0.33 no código,
  independente de quantas fases o boss declara.

### P0-4. Menu: outra linguagem visual + telas inteiras faltando — ✅ resolvido (Fase 13d)

- **Legado** (spec menus §0.5-0.9, §10, §12, §16): cards com barra
  vertical colorida à esquerda, cursor `▶` colorido, **5 step-dots** com
  nome da etapa + breadcrumb acumulado (`FÁCIL › CLÁSSICO › NENHUMA`),
  layout 2 colunas (lista à esquerda 338px / painel grande à direita com
  borda superior colorida + "wash" translúcido), badge `[BLOQUEADO]`,
  telas **RECORDS** (5 stats persistidos) e **SISTEMA/SETTINGS** (tela
  cheia, screen shake, mostrar hitbox — liga/desliga de verdade), overlay
  de **dev mode** (sequência secreta `WWSSADAD`, badge `[ DEV ]`, painel
  F9/F10/F3-F8, hot-reload de `balance.json`).
- **Port** (`scenes.py:233-276` `_menu`): lista central genérica com
  fundo roxo translúcido no item selecionado e `►` dourado — sem cards,
  sem step-dots, sem breadcrumb, sem coluna de descrição rica. Não há
  `MENU_RECORDS`, não há `MENU_SETTINGS` no enum de estados
  (`scenes.py:27-28`), não há overlay de dev mode, não há cheats.
- **Ação recomendada:** dado o volume, tratar como um item de trabalho
  dedicado (não uma correção pontual): redesenhar `_menu()` para o
  layout de 2 colunas + step-dots + breadcrumb; adicionar as telas
  RECORDS/SETTINGS que faltam (dá para reusar o layout de lista simples
  atual só para essas duas, que no legado também são mais simples);
  portar o dev overlay como uma feature de baixo risco e alto valor de
  debug.

  **O que foi feito (Fase 13d):** `_menu()` genérico agora desenha cards
  com barra colorida à esquerda (cor por item, igual às tabelas do
  legado — `_DIFF_COLORS`/`_BOSS_COLORS`/`_SKILL_COLORS`/etc.), painel
  de descrição à direita com título colorido + linhas de texto, e
  carrossel centralizado no cursor quando a lista não cabe na área
  visível — tudo nas MESMAS posições de pixel do legado (`MLL_X/MRP_X/
  MC_Y0/MC_Y1`, resolução idêntica 1280×720). As 5 telas do assistente
  (dificuldade/boss/habilidade/arma/mutadores) ganharam o header com 5
  step-dots + nome do passo + breadcrumb das escolhas anteriores. O
  MAIN_MENU virou 5 itens (JOGAR/CONQUISTAS/REGISTROS/SISTEMA/SAIR,
  igual ao legado) com layout de coluna única (sem painel direito,
  como no legado). **REGISTROS** e **SISTEMA** existem agora: REGISTROS
  mostra mortes/parries totais, melhor tempo em DIFÍCIL+, dificuldade e
  skills desbloqueadas; SISTEMA só tem 2 dos 3 toggles do legado —
  **Screen Shake** (real, gate em `_apply_shake`) e **Mostrar Hitbox**
  (real, desenha o raio de colisão do jogador) — "Tela Cheia" ficou de
  fora porque exigiria um método novo no `IRenderer` da engine
  (`OuroborosEngine`), fora do escopo deste port por ora; achei melhor
  não ter um toggle que não faz nada de verdade. O dev overlay (F9/F10/
  sequência secreta) continua pendente — ver P0-5/P2.

### P0-5. Sistemas ausentes por completo: Replay e Segundo Fôlego — ✅ resolvido (Fase 13a/13e)

- Confirmado por grep: `replay`/`Replay`/`REPLAY` não aparece em nenhum
  arquivo de `bullethell/` — o `ReplayRecorder` do legado
  (`entities.py:4988-5029`, tela de GAME OVER com opção `W — Ver
  replay`) não tem equivalente no port.
- Segundo Fôlego (EXPERT) e Balas de Vingança (ABISSAL) também não
  aparecem em nenhum sistema — cobertos em P0-2, listados aqui de novo
  porque são sistemas *inteiros* ausentes, não parâmetros errados.

  **O que foi feito (Fase 13e — replay; Segundo Fôlego já em 13a):**
  `bullethell/replay.py` (novo) — descoberta importante: **o port não
  usa RNG global em sistema nenhum** (`grep -r "random\."
  bullethell/game_systems.py` não acha nada; toda "aleatoriedade" é hash
  determinístico por contador de emissor). Isso significa que, ao
  contrário do legado (que precisa re-plantar uma seed,
  `random.seed(seed)`), a simulação do port já é 100% determinística só
  pela sequência de inputs — bastou gravar `(bitmask, dt)` por frame
  (`GameApp.replay_frames`) e reproduzi-los por um
  `ReplayInputProvider` que implementa o mesmo contrato de
  `IInputProvider` lendo da gravação em vez do SO. `W` na tela de fim
  reconstrói o `World` com a MESMA config da run (boss/arma/skill/
  mutadores/dificuldade) e alimenta os frames gravados; ESC durante o
  replay (ou o fim dos frames) volta para WIN/GAMEOVER conforme o HP do
  boss, igual ao legado. `smoke_replay.py` (novo) prova bit-a-bit que a
  trajetória de HP do boss é IDÊNTICA entre a run original e o replay.

---

## 3. P1 — Gaps visíveis de paridade

### P1-1. HUD: barra de HP sem cor por tier, sem nome de padrão, sem PREP — ✅ resolvido (Fase 13a/13f)

- **Legado** (spec HUD §1): fill `RED_COL`(>66%)/`ORANGE`(>33%)/`YELLOW`
  senão; borda na cor do tier DDA (`GREEN`/`YELLOW`/`RED_COL`); marcas
  brancas em 66%/33%; texto **dentro** da barra:
  `"BOSS  {hp}/{max}   {PATTERN}{ [PREP]}{extra}   T{tier}"`.
- **Port** (`bullethell/game_systems.py:2143-2145` `HudSystem`): a barra
  é um retângulo de tint fixo `(255,70,100)` (`composition.py:157`) que
  só escala em largura por `hp_frac` — sem cor por tier (não há DDA, ver
  P0-2), sem nome de padrão, sem `[PREP]`. O texto de boss/HP é
  desenhado **separadamente** como texto puro em `scenes.py:506-512`
  (`_render_hud`), duplicando a informação sem coordenar com o retângulo
  sprite.
- **Ação:** depende de P0-2 (DDA) para a cor por tier; nome do padrão
  ativo já está disponível via `emitter.pattern_id` — dá para resolver e
  mostrar sem esperar o DDA.

  **O que foi feito:** cor por tier + `T{tier}` já saíram na Fase 13a
  junto com a DDA. O nome do padrão saiu na Fase 13f:
  `_active_pattern_text()` lê os emitters cujo `root` é o boss atual e
  mostra até 2 nomes derivados de `PatternDef.name` (ex.:
  `classic/circular_saw` → "CIRCULAR SAW"). `[PREP]` continua de fora —
  não existe telegraph de boss no port (ver observação em P0-3).

### P1-2. Boss Sloth (Preguiça): fase de fantasmas não é passiva, HP dos fantasmas errado — ✅ resolvido (Fase 13f)

- **Legado** (spec bosses-sins §2): fase 0 só deriva+bolhas (sem ataque
  ofensivo do boss); fase 1 (`dark_mode`) o boss fica **invulnerável e
  não ataca**, só espera os 3 `ETYPE_SENTINEL` (HP=20 cada) morrerem.
- **Port** (`bosses.json:148-157`): fase 0 tem `sloth/bubbles` **e**
  `summoner/volley` (um ataque extra que não existe no legado nesta
  fase); fase 1 (`gate_minions`) tem um emitter ativo
  (`swarm/ring_volley`) rodando **enquanto o boss deveria estar mudo**
  esperando os fantasmas morrerem; `minions: [3, 1, 6.0, 0.0]` dá HP
  **6.0** aos fantasmas, não os 20.0 do legado (`ENEMY_SENTINEL_HP`,
  `entities.py:449-452`).
- **Ação:** remover `swarm/ring_volley` da fase 1 do Sloth (ela deve ficar
  sem `emitters`), remover `summoner/volley` da fase 0, e corrigir o HP
  dos fantasmas para 20.0 em `minions`.

  **O que foi feito:** as duas remoções + o HP 20.0 saíram como
  planejado. Corrigir isso **expôs um gap real**: sem o
  `summoner/volley` "emprestado" mascarando o problema, ficou claro que
  as bolhas da fase 0 (`ETYPE_BUBBLE`) nunca implementavam o estouro em
  anel do legado (`BUBBLE_EXPLODE_T=8s` → `BUBBLE_BURST_N=12` balas) —
  era só um alvo estático. Adicionado: campo `minion.timer` (novo),
  inicializado em `spawn_minion` só para bolhas, decrementado em
  `MinionCombatSystem` — ao expirar, estoura um anel de 12 balas a
  120px/s (fixo, sem `speed_mult`, igual ao legado) e destrói a bolha.
  HP da bolha corrigido de 2.0 para 12.0 (`BUBBLE_HP`).

### P1-3. Skill PARRY: raio de deflexão maior que o legado — ✅ resolvido (Fase 13f)

- **Legado**: `PARRY_RANGE = PLAYER_RADIUS + BULLET_RADIUS + 12.0 = 17.5`
  px (`entities.py:171`, confirmado visualmente no anel ciano do
  jogador).
- **Port** (`skills.json:12-14`): `"radius": 25.0` — 43% maior que o
  legado, torna o parry sensivelmente mais fácil de acertar.
- **Ação:** trocar para `17.5`.

  **O que foi feito:** `skills.json` atualizado para `17.5`; a descrição
  do menu de skills (Fase 13d) já tinha sido escrita com o valor certo.

### P1-4. Boss roster do modo Clássico expõe todos os 15 bosses, legado só expõe 6 — ✅ resolvido (Fase 13f)

- **Legado** (spec menus §6): `SELECT_BOSS` só lista
  `CLASSIC_BOSS_IDS = [CLÁSSICO, ENXAME, PAREDÃO, GÊMEOS, INVOCADOR,
  ÔMEGA]` — os 8 pecados só são jogáveis via **SINS Rush**, nunca
  escolhidos individualmente no modo Clássico.
- **Port** (`scenes.py:59-65` `BOSSES`): lista todos os 15 IDs (incluindo
  os 8 pecados e o "timemage" inventado) diretamente no modo Clássico.
- **Ação:** é uma escolha de design razoável (dar acesso direto aos
  pecados é mais conveniente), mas diverge da estrutura original — se o
  objetivo é fidelidade, restringir `MENU_BOSS` no modo `classic` ao
  roster de 6 do legado e manter os pecados exclusivos do SINS Rush (ou
  documentar a divergência como intencional).

  **O que foi feito:** optou-se pela fidelidade — `CLASSIC_BOSSES`
  (novo, `scenes.py`) filtra `BOSSES` para exatamente os 6 nomes do
  legado, na mesma ordem (preservar a ordem de `BOSSES` já dá a ordem
  certa: CLÁSSICO/ENXAME/PAREDÃO/GÊMEOS/INVOCADOR/ÔMEGA). Os 8 pecados
  continuam jogáveis via SINS RUSH e o "Mago do Tempo" via BOSS RUSH —
  nenhum boss ficou inacessível, só a tela de seleção do modo Clássico
  ficou fiel ao roster original.

### P1-5. Mutadores: ABISSAL misturado com os mutadores de verdade — ✅ resolvido (Fase 13a)

Coberto em P0-2, mas vale registrar aqui como item de UI: a lista
`MUTATORS` (`scenes.py:83-89`) tem 7 itens (o legado tem 6:
PREDADOR/FANTASMA/CANHÃO DE VIDRO/HORDA/BERSERKER/CLAUSTROFOBIA) — o 7º é
o "abissal" que deveria ser dificuldade, não mutador.

### P1-6. Conquistas: 13 de 32, sem secretas, sem barra de progresso, sem recompensas reais — ✅ parcialmente resolvido (Fase 13g)

- **Legado** (spec menus §11.1): 32 conquistas, várias com contador e
  barra de progresso (`grazes_100`, `parries_50`, `parries_200`), 5
  secretas (nome vira `"???"` até desbloquear), cada uma concede uma
  recompensa real (skill, skill+, arma+, mutador, boss).
- **Port** (`scenes.py:31-45` `ACHIEVEMENTS`): 13 entradas, sem
  progresso/contador, sem secretas, sem campo de recompensa — e como não
  há gating (P0-1), "recompensa" não significa nada hoje.
- **Ação:** depende de P0-1. Depois de portar o `SaveManager`, expandir a
  lista e conectar cada conquista à sua recompensa real.

  **O que foi feito (Fase 13g):** `ACHIEVEMENTS` foi de 13 para **20**
  entradas com id/nome/descrição/recompensa reais: as **15 não-mastery**
  do legado (`ACHIEVEMENTS_DEF`, main.py:1896-1986 — mesmos nomes onde
  aplicável: INICIANTE/VETERANO/MESTRE/ESQUIVADOR/ESPADACHIM/
  PERFECCIONISTA/RISCO MÁXIMO/IMPARÁVEL/EQUILÍBRIO PERFEITO/PACIFISTA DE
  ELITE/SENHOR DO PARRY/SPEED RUNNER/ALÉM DO LIMITE/INTOCÁVEL/O FIM,
  as 5 secretas mostrando `"???"` até desbloquear) **+ 5 bônus** que o
  port já tinha para as conclusões de modo que o legado não trata como
  conquista dedicada (PRIMEIRO SANGUE/CONQUISTADOR/REDENÇÃO/
  SOBREVIVENTE/CORAÇÃO DE VIDRO). Barra de progresso real para
  ESQUIVADOR/ESPADACHIM/SENHOR DO PARRY (lê `total_graze`/
  `total_parries` acumulados). EQUILÍBRIO PERFEITO e PACIFISTA DE ELITE
  usam a mesma aproximação já assumida em P0-1 (vencer os Gêmeos/
  Invocador, sem medir o timing exato/contagem de lacaios do legado).
  As 32 conquistas de mastery (sp_*/wp_*) do legado não viraram
  entradas na tela de CONQUISTAS (são "silenciosas", como já eram as
  17 masteries no legado — ver P1-7 para o que de fato ficou
  rastreado); a tela de CONQUISTAS ganhou cursor + carrossel (20 itens
  não cabem mais numa lista estática) e mostra recompensa/progresso do
  item selecionado.

### P1-7. Weapon mastery / skill mastery: sem equivalente — ✅ resolvido (Fase 13i)

- **Legado**: 7 desafios de skill+ e 10 de arma+ (spec player-meta §8) —
  vários **nem no legado são realmente rastreados** (bug documentado no
  próprio legado, spec observa que AGULHA/CARREGADO/BURST/TELEGUIADO/
  FLAK/CHAKRAM mastery nunca incrementam). O port não tem sistema de
  mastery algum — as variantes "+" são liberadas de graça (P0-1).
- **Ação:** ao portar o gating, não é necessário replicar o bug do
  legado — dá pra portar só as 4 masteries que o legado realmente
  rastreia (`default_hits`, `spread_close`, `plasma_contact`,
  `orbit_damage`) e simplificar as outras 6 para desbloqueio por
  conquista/vitória, que é estritamente melhor que "nunca destrava".

  **O que foi feito:** pool `mastery` nova (11 campos) instrumentada
  dentro dos próprios sistemas de gameplay (não é telemetria de fora —
  é o mesmo código que já processa dano/graze/skill):
  - **7 skills** (todas rastreadas de verdade, igual ao legado): DASH+
    (graze durante `skill_t>0` com `dash+` equipada, em
    `PlayerHitSystem`), PARRY+ (soma por janela de ativação, reseta a
    cada nova ativação, em `SkillSystem._parry`), EMP+ (`n` de
    `_destroy_bullets_within`, já existia — só faltava guardar o
    máximo), OVERCLOCK+ (dano ao boss acumulado enquanto
    `skill_t>0`, em `PlayerBulletVsBossSystem`), ESCUDO+ (bloco
    perfeito já detectado em `_absorb_or_damage`, só faltava contar),
    BLINK+ (amostra a linha do teleporte em t=0.25/0.5/0.75 contra o
    AABB do boss/partes), DILATAÇÃO+ (checa bala a ≤5px no instante da
    ativação).
  - **4 armas reais do legado**: PADRÃO (sequência de acertos
    consecutivos), SPREAD (acertos <40px do boss), PLASMA (contato
    contínuo via o mesmo `dot_contact_this_frame` que já existia),
    SATÉLITE (dano das gemas via `pb_orbit`). Como a arma nunca troca
    no meio da run (não há bind de arma durante PLAYING), o
    `player.weapon_id` já identifica com certeza — sem precisar marcar
    cada bala individualmente.
  - **6 armas nunca rastreadas nem no legado** (AGULHA/CARREGADO/
    BURST/TELEGUIADO/FLAK/CHAKRAM): destravam vencendo com a arma
    equipada — fallback simples, estritamente melhor que nunca
    destravar, sem fingir uma mastery que nem o legado mede.
  - `save["skill_plus_unlocked"]`/`weapon_plus_unlocked` deixaram de
    ser o sentinela `["all"]` (Fase 13b) e viraram listas por item de
    verdade; `_plus_unlocked(categoria, nome)` ganhou o parâmetro do
    nome específico.
  - `smoke_mastery.py` (novo): 11 asserts jogando de verdade (headless)
    que provam a instrumentação em si, não só a regra de desbloqueio
    (essa já era coberta por `smoke_gating.py`, que ganhou +5 asserts).

---

## 4. P2 — Meta / polish

- ~~**RECORDS** e **SETTINGS** ausentes~~ — ✅ resolvido (Fase 13d, ver
  P0-4). **Screen Shake**/**Mostrar Hitbox** também resolvidos (Fase
  13d); **Tela Cheia** segue de fora (exigiria método novo no
  `IRenderer` da engine).
- ~~**SELECT_RUSH_PLAYLIST**~~ — ✅ resolvido (Fase 13j): o port não tem
  essa tela porque promoveu `rush`/`sins` a modos de jogo separados em
  vez de sub-escolha dentro de Boss Rush — funcionalmente equivalente,
  então em vez de recriar a tela optou-se por alinhar o *texto* dos
  dois modos ao vocabulário do legado. `MODES` (`scenes.py`) agora
  descreve **BOSS RUSH** como "7 bosses em ordem fixa — do Clássico ao
  Ômega, +1 vida entre eles... Sem aleatoriedade, HP sem escala" e
  **SINS RUSH** como "7 pecados em ordem fixa + o Pecado Original ao
  fim... HP escala ×1.15 por estágio... Vencer libera a dificuldade
  ABISSAL" — mesma informação que as duas playlists do legado
  comunicavam, sem recriar a tela extra de seleção.
- ~~**SINS RUSH sem escalonamento de HP por estágio**~~ — ✅ resolvido
  (Fase 13j): o legado aumenta o HP de cada boss em +15% por estágio
  dentro do SINS RUSH (spec menus §11); o port aplicava só o
  `hp_mult` da dificuldade, sem esse escalonamento extra. Adicionado
  `SINS_RUSH_HP_SCALE = 1.15` (`game_systems.py`) multiplicado por
  `rush_idx` em `spawn_boss()` quando `run_mods.rush == 2` (SINS).
  `smoke_ecs.py` ganhou um teste dedicado: força a morte do 1º boss
  da fila e confere que o 2º nasce com HP exatamente ×1.15 maior.
- ~~**Dev overlay / cheats**~~ — ✅ resolvido (Fase 13h): sequência
  secreta `WWSSADAD` (lê os 4 `move_*` já vinculados a WASD, sem tocar
  no binding) liga/desliga `dev_mode`; com ele ligado, **F9** (unlock
  all — todas as dificuldades/skills/mutadores/ÔMEGA/variantes "+"),
  **F10** (wipe save — reseta save e seleção), **F6** (god mode —
  reusa o `invuln_t` já existente, sem nenhum sistema novo) funcionam
  em qualquer estado; **F5** (mata o boss), **F3**/**F4** (HP→50%/10%)
  e **F7** (avança fase — empurra o HP para logo abaixo do próximo
  `hp_above`, deixando o `BossPhaseSystem` já existente fazer a
  transição sozinho) só em PLAYING. Badge `[ DEV ]` sempre visível
  (magenta ligado / cinza desligado) + painel de comandos quando
  ligado. **F8 (Sala do Dummy) ficou de fora** — o port não tem um
  boss "saco de pancadas"/dificuldade TESTE equivalente, não haveria o
  que a tecla abrisse. `smoke_devmode.py` (novo) cobre os 7 cheats +
  a sequência secreta ligando/desligando — 16/16 OK.
- ~~**balance.json + hot-reload**~~ — ✅ resolvido (Fase 13j): não há um
  `balance.json` dedicado, mas o próprio `data/*.json` já cumpre esse
  papel — todo número de gameplay já vive lá. Implementado hot-reload
  por mtime: em `dev_mode`, `GameApp` confere a cada ~1s (acumulado em
  `_reload_check_t`) se algum arquivo em `data/*.json` mudou desde o
  boot (`_data_dir_mtime()`, `scenes.py`); se sim, recarrega via
  `load_all()` e mostra o flash "BALANCE RELOADED". Só vale para a
  **próxima partida** — não repatcha sistemas de uma run já em curso
  (os pools/arquétipos já foram materializados no `World` atual).
  `smoke_devmode.py` ganhou 4 novos asserts: sem `dev_mode` não
  recarrega; com `dev_mode` ligado e mtime futuro, recarrega e mostra
  o flash.

---

## 5. P3 — Pequenos / numéricos

- SPREAD `fire_rate` no port é `0.13` (`weapons.json:9`); o texto do
  menu legado também diz "CD 0.13s", mas o **código** do legado na
  verdade usa a cadência base de 0.10s (bug/inconsistência documentada
  na própria spec do legado, `main.py:2942-2959` vs. `main.py:1255`) — o
  port está fiel ao *texto* do legado, não ao *código*; decisão de
  produto, não bug do port.
- ~~Paleta de cores de balas (`PALETTE` em `schemas.py:266-277`) usa tons
  aproximados, não os RGB exatos do legado por tipo~~ — ✅ resolvido
  (Fase 13f): os 10 tons agora são os RGB exatos do legado por tipo
  (`ORANGE (255,165,0)` para normal, etc.), com os tipos "compostos" do
  legado (gravity/phaser/spinner, que lá são multi-camada) resolvidos
  para o tom mais representativo de cada um.
- Textos de flavor/intro (`BOSS_INTROS` em `scenes.py:91-107`) foram
  reescritos livremente em vez de citar o `_BOSS_INTRO` literal do
  legado (`main.py:1066-1079`) — considerar usar os textos exatos onde
  o boss existe em ambos os jogos, mantendo textos próprios só para
  bosses que só existem no port (ex. "timemage", se ele for mantido).

---

## 6. Onde o port já iguala ou supera o legado

- **Áudio**: o legado é literalmente mudo (`AudioManager` nunca
  alimentado — spec player-meta §9); o port tem SFX procedurais reais
  (`scenes.py:145-152`, tons sintetizados via NumPy) para hit/boom/
  emp/shield/mine + navegação de menu. Manter e expandir, não regredir.
- **Gimmicks dos pecados**: holofote da Soberba (`BossGimmickSystem`,
  `game_systems.py:2428-2442`), portão de fantasmas da Preguiça
  (:2444-2445), roubo de CD da Inveja (:2447-2450), inversão de
  controles da Luxúria (:2452-2454), slam da Ira (:2456-2483), corpo em
  chamas berserker (:2485-2510) e Sétimo Selo (:2512-2535) têm a lógica
  certa e batem bem nos números centrais contra a spec do legado.
- **Armas e skills**: os números centrais de `weapons.json`/`skills.json`
  batem contra `entities.py` na maioria dos campos (fire rate, dano,
  velocidade, cooldowns) — este não é o eixo que precisa de retrabalho
  grande, só ajustes pontuais (P1-3, P3).

---

## 7. Ordem de ataque recomendada

1. **P0-1 (gating/save)** — é pré-requisito de P0-2 (ABISSAL como
   desbloqueio), P1-6 e P1-7. Sem isso, qualquer trabalho em
   progressão fica solto.
2. **P0-2 (dificuldade + DDA)** — maior impacto na sensação de "jogo
   ficando mais difícil de verdade", cruza com P1-1 (cor da barra de
   HP por tier).
3. **P0-3 (Clássico completo)** — é o boss que todo jogador encontra
   primeiro; hoje está visivelmente incompleto.
4. **P0-4 (menu)** — grande volume de trabalho de UI, mas isolado (não
   bloqueia os outros itens); pode rodar em paralelo com 1-3.
5. **P0-5 (replay, Segundo Fôlego)** — replay é standalone; Segundo
   Fôlego sai "de graça" junto com P0-2.
6. **P1-2, P1-3** — correções pontuais e baratas, podem entrar em
   qualquer fase como "enquanto isso".
7. **P2/P3** — depois que o esqueleto estrutural (P0) estiver de pé.
