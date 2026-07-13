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
- [x] Smoke headless 24/24 (armas, variantes, todos os bosses, lasers)

Fase 4:
- [ ] Habilidades (dash/parry/focus/emp/blink/overclock/shield/timedil) e Skill+
- [ ] Mutadores, fragmentação ABISSAL, hazards, partículas, HUD/menus
- [ ] Bosses restantes do legado (Omega, Summoner+minions, SINS)
- [ ] Save/conquistas (SaveManager fora do World, I/O só em menu)

O jogo legado (`main.py`) permanece intacto e jogável — o port evolui em
paralelo até a paridade.
