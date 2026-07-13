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
- [x] Smoke headless 57/57

Fase 9 (dependências da engine ou meta-jogo):
- [ ] Save/conquistas/maestria (SaveManager fora do World, I/O só em menu)
- [ ] Visual do holofote/telegraphs (camada de efeitos no renderer)
- [ ] Partículas/juice (pipeline de texturas da engine)
- [ ] Menus/seleção e modos Boss Rush/Wave Survival (texto no renderer)

O jogo legado (`main.py`) permanece intacto e jogável — o port evolui em
paralelo até a paridade.
