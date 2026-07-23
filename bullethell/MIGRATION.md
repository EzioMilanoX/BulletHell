# Migração BulletHell → OuroborosEngine (ECS)

## 1. A pesquisa e o que a engine real mudou nela

Benchmark nesta máquina (Python 3.14, 5000 balas, movimento apenas):

| Estratégia | ms/frame | vs. NumPy SoA |
|---|---:|---:|
| ECS de dataclasses (1 objeto/entidade) | 0.480 | 135× mais lento |
| ECS sparse-set com dicts | 0.708 | 199× mais lento |
| NumPy SoA vetorizado | 0.004 | 1× |

A conclusão original era "migração híbrida: balas ficam fora do ECS".
**A OuroborosEngine real invalida a ressalva**: `ComponentPool.dense_data`
é um `np.ndarray` estruturado (SoA compactado por sparse-set), `ISystem`
proíbe laço Python por entidade, e entidades trafegam como
`PackedEntityId` (int64 primitivo). Ou seja — a engine JÁ É o híbrido,
generalizado: balas podem ser entidades de verdade porque as pools são
colunas NumPy, não objetos. O port usa ECS pleno, sem carve-out.

## 2. Estrutura do port

```
main_ecs.py                  # entrada: python main_ecs.py [--boss ...] [--weapon ...]
smoke_ecs.py                 # teste headless (null backends): 6 cenários
bullethell/
  __init__.py                # coloca ../OuroborosEngine no sys.path
  ids.py                     # sid() = zlib.crc32(nome)
  schemas.py                 # dtypes das pools do jogo + capacidades fixas
  loaders.py                 # data/*.json → registries por crc32
  game_systems.py            # os ISystem do jogo (vetorizados)
  composition.py             # build_world/build_game/build_headless
  data/
    bullet_archetypes.json   # 13 espécies de bala inimiga
    patterns.json            # 16 padrões de emissão
    weapons.json             # 10 armas (5 portadas + 5 "special")
    bosses.json              # bosses: hp, rota, partes, fases→emitters
    input_bindings.json      # WASD + SPACE + 1..5 + P
  design/                    # rascunhos da fase de design (API hipotética)
```

## 3. Pools e arquétipos

Pools genéricas da engine: `transform`, `velocity`, `hitbox`, `sprite`.
Pools do produto (schemas.py): `player`, `boss`, `waypoint`, `emitter`,
`enemy_bullet` (cap 5000), e as pools de bala do jogador por composição —
`pb_core` + `pb_pierce`/`pb_range`/`pb_bounce`/`pb_dot`/`pb_life`/`pb_homing`.

Arquétipos: `player`, `boss`, `emitter`, `enemy_bullet`, e UM por arma
(`pb_padrao`, `pb_agulha+`, ...) montado de weapons.json — a variante +
de uma arma é literalmente o mesmo arquétipo + pools extras (ex.:
`agulha+` = agulha + `pb_pierce`). Cada pool de projétil guarda o próprio
`PackedEntityId` na coluna `self` para `world.destroy_entity` direto.

## 4. Agenda de sistemas (ordem de registro)

```
PlayerControlSystem        input → velocity do jogador; timers
WeaponFireSystem           cadência + spawn de balas-entidade (weapons.json)
BossPhaseSystem            thresholds de HP → troca emitters (bosses.json)
WaypointSystem             rota do boss com smoothstep
EmitterSystem              patterns.json → spawn de balas inimigas
PhysicsSystem (engine)     Transform += Velocity × delta_time
EnemyBulletBehaviorSystem  homing/spin/phase/gravity/stop&go/boomerang/sleeper
PlayerBulletHomingSystem   TELEGUIADO curva ao boss
MaintenanceSystem          ricochetes, timers (range/life/pierce), cull, clamp
PlayerHitSystem            contato (Yin/Yang/phaser) + graze + vidas
PlayerBulletVsBossSystem   dano; pierce com CD; PLASMA = DPS sem consumo
```

`destroy_entity` é diferido (flush no fim do `World.step`) — os sistemas
de colisão podem destruir à vontade sem invalidar linhas densas do frame.

## 5. Verificação

- `python smoke_ecs.py` — 6 cenários headless (900 frames cada): padrão,
  spread, agulha+, plasma (com approach — alcance 120px), teleguiado,
  timemage. Verifica spawn de padrões, dano no boss, graze, cull. 6/6 OK.
- `python main_ecs.py` — janela real; render placeholder da engine
  (retângulos coloridos; pipeline de texturas é roadmap da engine).

## 6. Paridade com o legado — checklist

Portado (fases 1–2):
- [x] **10/10 armas com as 10 variantes +**:
      padrão(+ricochete), spread(+ponto-cego 150px), agulha(+pierce CD 0.25),
      teleguiado(+enxame orbital), plasma(DoT sem consumo — o fix do legado),
      carregado(+estilhaços com carga ≥85%), burst(+minas de atraso 80→800),
      flak(+detonador manual), chakram(+congelador 8 DPS),
      satélite(+interceptor a 250px)
- [x] Sistemas dedicados: FuseSystem, ChakramSystem, OrbitSystem,
      PlayerBulletDelaySystem, AutoLaunchSystem (dispatch `special` no
      WeaponFireSystem: charged/burst/orbit/swarm)
- [x] Padrões: arc, ring (vão rotativo), spiral, rain (gaps), stream
      (pillar), **pair (tether)** e **laser** (telegrafa 1.8s → dispara
      0.65s, LaserSystem)
- [x] Arquétipos de bala: normal, yin/yang, homing, phaser, spinner,
      gravity well, ricochete, stop&go, boomerang, sleeper, **tether**
      (dano ponto-segmento no arame entre o par)
- [x] **TODOS os 5 bosses jogáveis**: classic, timemage (tether na fase 3),
      wall (barra descendente = parte única, rain+pillar), swarm (3
      unidades orbitando 0.75 rad/s, HP compartilhado via part.root,
      crossfire por unidade), twins (2 raízes independentes yin+yang)
- [x] Bosses multi-parte: pool `part` (dano roteado à raiz), BossMotionSystem
      (swarm_orbit/descend + posicionamento das partes)
- [x] Graze, vidas/invuln, reset de run
- [x] **8 habilidades + 7 variantes Skill+** (skills.json): dash(+iframes),
      parry(+homing 1.5), focus (câmera lenta 0.32 via pool `clock`),
      emp(+buff de dano em vez de stun), blink(+EMP na origem),
      overclock(+berserk 4×/25% movimento), shield(+bloco perfeito: anel
      de 8 balas e 50% do CD), timedil(+estilhaço 80px ao expirar)
- [x] Escalas de tempo: `ScaledMovementSystem` substitui o PhysicsSystem
      da engine — jogador 1.0, balas inimigas `clock.bullets` (DILATAÇÃO
      congela), resto `clock.world` (FOCUS); cadência/timers de boss,
      emitters, lasers e comportamentos escalam junto; stun do EMP para
      movimento e disparo dos bosses
- [x] **6 mutadores** (pool `run_mods` de 1 linha): PREDADOR (mira 0.5s à
      frente), FANTASMA (balas invisíveis 200-400px do boss — tint preto no
      fundo preto, restaurado pela PALETTE), CANHÃO DE VIDRO (1 vida, ×3),
      CLAUSTROFOBIA (arena −14%/borda), HORDE (HP ×1.5, vel ×0.85),
      BERSERKER (HP ×0.75, vel ×1.35)
- [x] Fragmentação ABISSAL: balas fragmentam em ±30° ao sair da tela
      (coluna `fragment`; revenge bullets em tudo com o mutador `abissal`)
- [x] HUD de retângulos (pool `hud` + HudSystem): barra de HP do boss,
      3 quadrados de vida, barra de CD/energia da habilidade
- [x] **Invocador**: motion `teleport` (salto determinístico por hash a
      cada 4.2s), emissão `summon` (lacaios kamikaze, pool `minion` cap 64,
      MinionAISystem persegue + MinionCombatSystem: balas×lacaio com
      pierce/DoT, contato kamikaze explode no jogador)
- [x] **Ômega ★**: 100% data-driven — 4 fases combinando os padrões de
      todos os bosses (bosses.json, hp 500)
- [x] **Pecados (1ª leva): Soberba, Gula e Preguiça** com as mecânicas
      transversais dos SINS declaradas por fase em bosses.json:
      `force` (sucção/empuxo no jogador), `gimmick: spotlight` (holofote
      varrendo; boss vulnerável só com o jogador no feixe — aux_angle/aux2
      + coluna `invuln`), `gimmick: gate_minions` (invulnerável até os
      fantasmas morrerem), `minions` na entrada de fase, motion `track_x`
      (persegue o x do jogador com taxa configurável)
- [x] Novas emissões: orbit_ring, teeth (fileira com vão), radial_random,
      spotlight_rain, geo (formas yin/yang alternantes); lacaios ganham
      `kind` (kamikaze/sentinela/bolha — estáticos não perseguem)
- [x] **TODOS os 8 pecados** (16/16 bosses do legado jogáveis):
      Inveja (emissão `mirror` espelha a arma do jogador; `skill_thief`
      rouba metade da recuperação do CD), Avareza (`corridor_rain`,
      moedas-mina que explodem por proximidade, `border_random` com borda
      encolhendo), Luxúria (pool `hazard` + HazardSystem: névoas SLOW;
      `invert_controls`; agulhas quase invisíveis), Ira (`slam` com anel
      de choque; `berserk_body`: corpo invulnerável ricocheteando 20s com
      dano por contato), Pecado Original (minas de 16, cascata, 7
      espirais, `seventh_seal`: sobreviva 30s — HP com floor multi-fase
      para não pular o Selo)
- [x] Lacaios `MINION_MINE` (explodem em anel por proximidade; `speed` =
      nº de balas); helper `spawn_enemy_bullet` para gimmicks
- [x] **Modos Boss Rush e SINS Rush** (`--mode rush|sins`): boss derrotado
      → raiz+partes+emitters destruídos e o próximo da sequência entra;
      +1 vida de cura entre bosses; twins tratado (avança só quando os
      dois caem — liveness por hp, não por count, pois destroy é diferido)
- [x] **Fundação do save**: pool `stats` (kills/deaths) + graze; persistido
      em `save_ecs.json` APÓS o GameLoop encerrar (I/O fora do step,
      Constituição §1); totais acumulados entre runs
- [x] **Wave Survival** (`--mode waves`, waves.json): 30 ondas com mistura
      kamikaze/sentinela por intervalo de spawn; bosses nas ondas 10/20/30;
      onda limpa (sem lacaios nem boss) → próxima; endless após a 30;
      barra de progresso roxa no HUD
- [x] Smoke headless 59/59 (rush: swarm no lugar do classic; waves: onda 3
      alcançada limpando lacaios)
- [x] **Interfaces do legado completas** (Fase 11, com o M1/M2 do ROADMAP
      implementados na engine — commit b6801f9):
      - Menus (scenes.py/GameApp): MODO → DIFICULDADE → BOSS → HABILIDADE
        → ARMA → MUTADORES (multi-select), com descrições, variante+ por
        ESPAÇO, navegação W/S + D/ENTER + A/ESC — o fluxo do legado
      - Dificuldades FÁCIL/NORMAL/DIFÍCIL (multiplicadores compostos com
        HORDE/BERSERKER)
      - Modo arcade: morte vira GAMEOVER (sem respawn), vitória por
        objetivo do modo (1 boss / 7 rush / 8 sins / 3 boss-waves);
        telas de WIN/GAMEOVER com stats, T reinicia, R menu, ESC abandona
      - Intro de boss (nome + frase, fade), HUD textual (modo·dif, nome e
        HP numérico do boss, ONDA X/30, VIDAS, skill equipada)
      - Efeitos: partículas (pool `particle` + kernel com fade/gravidade;
        hits, explosões, morte de boss, EMP, escudo), screen shake
        (clock.shake + set_camera_offset), balas circulares, névoa da
        Luxúria translúcida de verdade (alpha)
      - Atalho da área de trabalho abre no menu; save de totais por sessão

- [x] **Fase 12**: holofote da Soberba VISÍVEL (feixe dourado translúcido,
      mais claro com o jogador dentro — elemento HUD kind 6 posicionado
      pelo BossGimmickSystem); **13 conquistas** persistentes com tela
      CONQUISTAS no menu e "★ NOVA CONQUISTA" na vitória; **SFX
      procedurais** (engine 3502b3f: register_tone square/noise/sweep/zap
      via NumPy — zero assets) para hit/explosão/EMP/escudo/mina +
      navegação de menu, roteados dos sistemas via bitmask clock.sfx

- [x] **Fase 13**: estudo exaustivo de paridade legado×port
      (`PARITY_PLAN.md`, specs `arquivo:linha` dos dois lados) revelou que
      a experiência tinha divergido em 5 eixos estruturais, não só
      detalhes — as 3 primeiras correções (P0) já aplicadas:
      - **13a** — dificuldade em **5 tiers de verdade** (era 3
        multiplicadores planos): EXPERT e ABISSAL viram dificuldades
        (ABISSAL saiu da lista de mutadores); **DDA** (Difficulty do
        legado) recalcula o `tier` do boss por HP a cada frame e escala
        count/arc/velocidade do SPREAD/RING/SPIRAL do Clássico e do
        CROSSFIRE/RING_VOLLEY do Enxame; **Segundo Fôlego** (EXPERT+):
        boss sobrevive 3s com 1 HP e invulnerável antes de cair de vez,
        1×/run; barra de HP muda de cor pelo tier (verde/amarelo/vermelho)
      - **13b** — **gating de progressão** no save (`unlocked_skills`,
        `highest_cleared_diff`, `omega_unlocked`, `sins_rush_cleared`,
        `unlocked_mutators`, `skill_plus_unlocked`/`weapon_plus_unlocked`):
        tudo começa travado como no legado (só NENHUMA+DASH livres); menu
        genérico ganha navegação que pula item travado + badge
        `[BLOQUEADO]`; vencer FÁCIL/NORMAL/DIFÍCIL destrava
        NORMAL+PARRY/DIFÍCIL+FOCO/EXPERT+variantes "+"; conquistas
        existentes (esquivador/perfeccionista/além do limite) destravam
        EMP/BLINK/ÔMEGA — mapeamento exato com o legado onde a conquista
        já existe; onde o legado usa mastery que o port não rastreia
        (equilíbrio perfeito, pacifista de elite, as 17 masteries de
        arma/skill), a condição é uma aproximação documentada (ver
        PARITY_PLAN.md P1-6/P1-7)
      - **13c** — Clássico completo: os 10 padrões do legado (faltavam
        SHARD/FRACTURE/BLASTER; STOP&GO/BOOMERANG tinham ido parar
        exclusivamente no boss "Mago do Tempo", que não existe no
        legado) agora rodam nos 8 padrões-base + os 2 emprestados do
        Mago do Tempo, distribuídos em 5 fases; SHARD/FRACTURE reusam a
        máquina STOPGO já existente (crescem devagar e disparam,
        aproximação documentada do redirecionamento exato do legado);
        BLASTER ganha o emit `edge_burst` (novo, ~15 linhas)
      - `smoke_gating.py` (novo): 28 asserts sobre o gating;
        `smoke_ecs.py`: cenários dedicados p/ EXPERT/ABISSAL — 61/61 OK
      - **13d** — Menu redesenhado: `_menu()` genérico agora desenha
        cards com barra colorida por item (cores do legado —
        `_DIFF_COLORS`/`_BOSS_COLORS`/`_SKILL_COLORS`/etc.), painel de
        descrição colorido à direita, e carrossel centralizado no
        cursor — nas mesmas posições de pixel do legado (mesma
        resolução 1280×720). As 5 telas do assistente ganham header com
        step-dots + nome do passo + breadcrumb. MAIN_MENU passa a ter
        os 5 itens do legado (JOGAR/CONQUISTAS/**REGISTROS**/
        **SISTEMA**/SAIR) — as duas telas novas: REGISTROS (mortes,
        parries, melhor tempo Difícil+, dificuldade/skills
        desbloqueadas) e SISTEMA (Screen Shake e Mostrar Hitbox — reais
        e funcionais; "Tela Cheia" ficou de fora por exigir um método
        novo no `IRenderer` da engine, fora de escopo agora — sem
        toggle fingindo funcionar). `smoke_menu.py` (novo): 18 asserts
        cobrindo REGISTROS/SISTEMA/persistência dos toggles/fluxo
        completo do assistente — 61+28+18 OK
      - **13e** — Replay (`W — Ver replay` no fim de jogo): o port não
        usa RNG global em sistema nenhum (toda "aleatoriedade" é hash
        determinístico por contador de emissor), então a simulação já é
        100% determinística só pela sequência de inputs — sem precisar
        replantar seed como o legado. `bullethell/replay.py` (novo):
        `ReplayInputProvider` implementa o mesmo contrato de
        `IInputProvider` lendo `(bitmask, dt)` gravados em vez do SO;
        `W` na tela de fim reconstrói o `World` com a mesma config da
        run e reproduz os frames; ESC ou o fim da gravação volta a
        WIN/GAMEOVER conforme o HP do boss. `smoke_replay.py` (novo)
        prova bit-a-bit que a trajetória de HP do boss é idêntica entre
        a run original e o replay — **todos os P0 do PARITY_PLAN.md
        aplicados** (61+28+18+7 OK nos 4 smoke tests)
      - **13f** — Limpeza dos P1 do PARITY_PLAN.md: nome do padrão ativo
        na barra de HP (`_active_pattern_text`, lê `emitter.pattern_id`);
        Sloth com fase 0 só bolhas (sem `summoner/volley` emprestado) e
        fase 1 muda de verdade (sem `swarm/ring_volley`) — o que expôs
        um gap real (as bolhas nunca estouravam sozinhas): novo campo
        `minion.timer` + lógica em `MinionCombatSystem` implementam o
        `BUBBLE_EXPLODE_T`/`BUBBLE_BURST_N` do legado; raio do PARRY
        25→17.5px; `MENU_BOSS` no modo Clássico restrito aos 6 bosses do
        legado (`CLASSIC_BOSSES`) — pecados só via SINS RUSH, Mago do
        Tempo só via BOSS RUSH; paleta de balas com os RGB exatos do
        legado por tipo. 61+28+18+7 OK
      - **13g** — Conquistas de 13 para **20** reais (id/nome/descrição/
        recompensa): as 15 não-mastery do legado
        (`ACHIEVEMENTS_DEF`, main.py:1896-1986 — 5 delas secretas,
        mostrando `"???"` até desbloquear) + 5 bônus de conclusão de
        modo que o port já tinha. Barra de progresso real para
        ESQUIVADOR/ESPADACHIM/SENHOR DO PARRY. Tela CONQUISTAS ganha
        cursor + carrossel (20 itens não cabem mais numa lista
        estática) e mostra recompensa/progresso do item selecionado.
        As 17 masteries de skill+/arma+ do legado ficam de fora por
        decisão deliberada — uma conquista que nunca pode ser ganha é
        pior que não listá-la (ver PARITY_PLAN.md P1-7, ainda aberto).
        61+43+18+7 OK (smoke_gating.py: 28→43 asserts, com as 15 novas
        sobre as condições de conquista)

Fase 14 (futuro, ver PARITY_PLAN.md P1-7/P2/P3):
- [ ] Masteries de arma/skill do legado (17 desafios — exigem
      instrumentar contagens específicas em vários sistemas)
- [ ] Dev overlay/cheats (F9/F10/F3-F8, sequência secreta, hot-reload)
- [ ] Música procedural ou faixas (play_track já existe na engine)
- [ ] Texturas/sprites (ROADMAP M3 da engine)

O jogo legado (`main.py`) permanece intacto e jogável — o port evolui em
paralelo até a paridade.
