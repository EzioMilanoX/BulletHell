"""
Composition root do BulletHell: monta World + pools + arquétipos +
sistemas na ordem correta, cria as entidades iniciais e devolve um
GameLoop pronto. Espelha o papel de `ouroboros.bootstrap.CompositionRoot`,
registrando por cima o vocabulário do produto (como a docstring de lá
prescreve).
"""
from __future__ import annotations

import numpy as np

from ouroboros.bootstrap.game_loop import GameLoop
from ouroboros.core.components.schemas import COMPONENT_SCHEMAS
from ouroboros.core.memory.memory_manager import MemoryManager
from ouroboros.core.world import World

from bullethell.ids import sid
from bullethell.loaders import GameData, load_all
from bullethell.schemas import GAME_POOL_CAPACITY, GAME_SCHEMAS, SCREEN_H, SCREEN_W
from bullethell import game_systems as gs

ENTITY_CAPACITY = 8192


# Dificuldade → multiplicadores de HP/velocidade do boss (legado:
# FÁCIL ×0.75/HP200, NORMAL ×1.0/HP300, DIFÍCIL ×1.3/HP400)
DIFFICULTIES = {
    "facil":   (0.70, 0.85),
    "normal":  (1.00, 1.00),
    "dificil": (1.33, 1.18),
}


def build_world(data: GameData, input_provider, boss_name: str = "classic",
                weapon_name: str = "padrao", skill_name: str = "none",
                mutators: frozenset = frozenset(), mode: str = "classic",
                difficulty: str = "normal", arcade: bool = False) -> World:
    """Monta o World completo do jogo (sem backends — quem escolhe
    renderer/input é o chamador: janela real ou null/headless)."""
    mm = MemoryManager(entity_capacity=ENTITY_CAPACITY)

    # pools genéricas da engine + pools do produto
    for name, dtype in COMPONENT_SCHEMAS.items():
        mm.create_pool(name, dtype, dense_capacity=ENTITY_CAPACITY)
    for name, dtype in GAME_SCHEMAS.items():
        mm.create_pool(name, dtype, dense_capacity=GAME_POOL_CAPACITY[name])

    world = World(mm, max_structural_commands=8192)

    # arquétipos fixos
    world.register_archetype("player", ("transform", "velocity", "sprite", "player"))
    world.register_archetype("boss", ("transform", "velocity", "sprite", "hitbox",
                                      "boss", "waypoint"))
    world.register_archetype("boss_hidden", ("transform", "velocity", "boss",
                                             "waypoint"))   # raiz de composto
    world.register_archetype("part", ("transform", "sprite", "hitbox", "part"))
    world.register_archetype("laser", ("transform", "sprite", "laser"))
    world.register_archetype("minion", ("transform", "velocity", "sprite", "minion"))
    world.register_archetype("hazard_entity", ("transform", "sprite", "hazard"))
    world.register_archetype("particle_entity", ("transform", "velocity",
                                                 "sprite", "particle"))
    world.register_archetype("emitter", ("emitter",))
    world.register_archetype("enemy_bullet", ("transform", "velocity", "sprite",
                                              "enemy_bullet"))
    # arquétipos de bala do jogador: 1 por arma (base + variante +)
    for wdef in data.weapons.values():
        world.register_archetype(
            "pb_" + wdef.name,
            ("transform", "velocity", "sprite", "pb_core") + wdef.pools)

    # sistemas — ordem do frame (MIGRATION.md §3)
    world.register_system(gs.SkillSystem(mm, input_provider, data))  # escreve clock/mults
    world.register_system(gs.PlayerControlSystem(mm, input_provider))
    world.register_system(gs.WeaponFireSystem(mm, input_provider, data))
    world.register_system(gs.BossPhaseSystem(mm, data))
    world.register_system(gs.WaveSystem(mm, data))         # Wave Survival
    world.register_system(gs.WaypointSystem(mm, data))
    world.register_system(gs.BossMotionSystem(mm, data))   # partes/orbit/descend
    world.register_system(gs.BossGimmickSystem(mm, data))  # pecados: holofote/força/gate
    world.register_system(gs.EmitterSystem(mm, data))
    world.register_system(gs.LaserSystem(mm))
    world.register_system(gs.MinionAISystem(mm))           # kamikazes perseguem
    world.register_system(gs.HazardSystem(mm))             # névoas SLOW (Luxúria)
    world.register_system(gs.ScaledMovementSystem(mm))     # física com escalas de tempo
    world.register_system(gs.OrbitSystem(mm))              # pós-física: sobrescreve Transform
    world.register_system(gs.EnemyBulletBehaviorSystem(mm))
    world.register_system(gs.PlayerBulletHomingSystem(mm))
    world.register_system(gs.PlayerBulletDelaySystem(mm))  # BURST+
    world.register_system(gs.FuseSystem(mm, input_provider, data))      # FLAK
    world.register_system(gs.ChakramSystem(mm, input_provider, data))   # CHAKRAM
    world.register_system(gs.AutoLaunchSystem(mm, data))   # SATÉLITE+
    world.register_system(gs.ParticleSystem(mm))           # juice
    world.register_system(gs.MaintenanceSystem(mm))
    world.register_system(gs.GhostTintSystem(mm))          # mutador FANTASMA
    world.register_system(gs.PlayerHitSystem(mm, data))
    world.register_system(gs.PlayerBulletVsBossSystem(mm))
    world.register_system(gs.MinionCombatSystem(mm))       # lacaios do Invocador
    world.register_system(gs.HudSystem(mm, data))

    _spawn_clock(world, mm, mutators, difficulty, arcade)
    _spawn_hud(world, mm)
    _spawn_player(world, mm, data, weapon_name, skill_name,
                  glass=("glass" in mutators))
    # modos: classic = boss escolhido em loop; rush/sins = sequência;
    # waves = Wave Survival (WaveSystem controla os spawns)
    rush_kind = {"classic": 0, "rush": 1, "sins": 2, "waves": 3}.get(mode, 0)
    mods = mm.get_pool("run_mods")
    mods.active_view()["rush"][0] = rush_kind
    mods.active_view()["rush_idx"][0] = 0
    world.register_archetype("stats_entity", ("stats",))
    world.create_entity("stats_entity")
    world.register_archetype("wave_entity", ("wave",))
    wpacked = world.create_entity("wave_entity")
    wrow = mm.get_pool("wave").dense_row_of(wpacked & 0xFFFFFFFF)
    mm.get_pool("wave").active_view()["idx"][wrow] = -1   # 1ª onda no 1º frame
    if rush_kind in (1, 2):
        _spawn_boss(world, mm, data, gs.RUSH_ORDERS[rush_kind][0])
    elif rush_kind == 0:
        _spawn_boss(world, mm, data, boss_name)
    # waves: sem boss inicial — o WaveSystem começa a onda 1
    return world


def _spawn_clock(world: World, mm: MemoryManager, mutators: frozenset,
                 difficulty: str = "normal", arcade: bool = False) -> None:
    world.register_archetype("clock_entity", ("clock",))
    packed = world.create_entity("clock_entity")
    row = mm.get_pool("clock").dense_row_of(packed & 0xFFFFFFFF)
    cv = mm.get_pool("clock").active_view()
    cv["world"][row] = 1.0
    cv["bullets"][row] = 1.0

    world.register_archetype("run_mods_entity", ("run_mods",))
    packed = world.create_entity("run_mods_entity")
    row = mm.get_pool("run_mods").dense_row_of(packed & 0xFFFFFFFF)
    mv = mm.get_pool("run_mods").active_view()
    mv["predator"][row] = 1 if "predador" in mutators else 0
    mv["ghost"][row] = 1 if "fantasma" in mutators else 0
    mv["glass"][row] = 1 if "glass" in mutators else 0
    mv["claustro"][row] = 1 if "claustro" in mutators else 0
    mv["abissal"][row] = 1 if "abissal" in mutators else 0
    hp_m, spd_m = DIFFICULTIES.get(difficulty, (1.0, 1.0))
    if "horde" in mutators:
        hp_m, spd_m = hp_m * 1.5, spd_m * 0.85
    if "berserker" in mutators:
        hp_m, spd_m = hp_m * 0.75, spd_m * 1.35
    mv["hp_mult"][row] = hp_m
    mv["spd_mult"][row] = spd_m
    mv["arcade"][row] = 1 if arcade else 0


def _spawn_hud(world: World, mm: MemoryManager) -> None:
    """5 elementos de HUD: barra de HP (topo), 3 vidas, barra de skill."""
    world.register_archetype("hud_entity", ("transform", "sprite", "hud"))
    layout = [
        (0, SCREEN_W / 2, 14.0, (255, 70, 100)),      # HP do boss
        (1, 22.0, SCREEN_H - 18.0, (240, 240, 255)),  # vidas
        (2, 44.0, SCREEN_H - 18.0, (240, 240, 255)),
        (3, 66.0, SCREEN_H - 18.0, (240, 240, 255)),
        (4, SCREEN_W - 90.0, SCREEN_H - 18.0, (90, 220, 140)),  # skill CD
        (5, SCREEN_W / 2, SCREEN_H - 12.0, (170, 110, 255)),    # ondas
        (6, SCREEN_W / 2, SCREEN_H / 2, (245, 197, 24)),        # holofote
    ]
    t = mm.get_pool("transform"); s = mm.get_pool("sprite"); h = mm.get_pool("hud")
    for kind, x, y, (r, g, b) in layout:
        packed = world.create_entity("hud_entity")
        idx = packed & 0xFFFFFFFF
        row = t.dense_row_of(idx); tv = t.active_view()
        tv["position_x"][row] = x
        tv["position_y"][row] = y
        if kind == 6:                                    # feixe da Soberba
            tv["scale_x"][row] = 88.0 / 8.0
            tv["scale_y"][row] = SCREEN_H / 8.0
        else:
            tv["scale_x"][row] = tv["scale_y"][row] = 1.25   # vidas 10px
        row = s.dense_row_of(idx); sv = s.active_view()
        sv["tint_r"][row], sv["tint_g"][row], sv["tint_b"][row] = r, g, b
        sv["tint_a"][row] = 0 if kind == 6 else 255
        sv["layer_z"][row] = 3 if kind == 6 else 30
        row = h.dense_row_of(idx); hv = h.active_view()
        hv["kind"][row] = kind


def _spawn_player(world: World, mm: MemoryManager, data: GameData,
                  weapon_name: str, skill_name: str = "none",
                  glass: bool = False) -> None:
    packed = world.create_entity("player")
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform"); row = t.dense_row_of(idx); tv = t.active_view()
    tv["position_x"][row] = SCREEN_W / 2
    tv["position_y"][row] = SCREEN_H * 0.82
    tv["scale_x"][row] = tv["scale_y"][row] = 2.25          # 18 px
    s = mm.get_pool("sprite"); row = s.dense_row_of(idx); sv = s.active_view()
    sv["tint_r"][row], sv["tint_g"][row], sv["tint_b"][row] = 240, 240, 255
    sv["tint_a"][row] = 255
    sv["layer_z"][row] = 20
    p = mm.get_pool("player"); row = p.dense_row_of(idx); pv = p.active_view()
    pv["lives"][row] = 0 if glass else 3            # CANHÃO DE VIDRO: 1 vida
    pv["weapon_id"][row] = sid(weapon_name)
    pv["skill_id"][row] = sid(skill_name)
    pv["focus_en"][row] = gs.FOCUS_MAX
    pv["speed_mult"][row] = pv["fr_mult"][row] = pv["dmg_mult"][row] = 1.0


def _spawn_boss(world: World, mm: MemoryManager, data: GameData, boss_name: str) -> None:
    gs.spawn_boss(world, mm, data, boss_name)   # runtime também usa (Boss Rush)


def build_game(boss_name: str = "classic", weapon_name: str = "padrao",
               skill_name: str = "none", mutators: frozenset = frozenset(),
               mode: str = "classic"):
    """Composição com janela pygame. Retorna (GameLoop, World) — o World
    permite ler as estatísticas após o run() para persistir o save."""
    from ouroboros.adapters.pygame_backend.pygame_audio_engine import PygameAudioEngine
    from ouroboros.adapters.pygame_backend.pygame_input_provider import PygameInputProvider
    from ouroboros.adapters.pygame_backend.pygame_renderer import PygameRenderer
    from bullethell.loaders import DATA_DIR

    data = load_all()
    renderer = PygameRenderer()
    renderer.initialize(SCREEN_W, SCREEN_H, "BULLET HELL — OuroborosEngine")
    input_provider = PygameInputProvider()
    input_provider.load_bindings(str(DATA_DIR / "input_bindings.json"))
    world = build_world(data, input_provider, boss_name, weapon_name,
                        skill_name, mutators, mode)
    return GameLoop(world, renderer, input_provider, PygameAudioEngine()), world


def build_headless(boss_name: str = "classic", weapon_name: str = "padrao",
                   skill_name: str = "none", mutators: frozenset = frozenset(),
                   mode: str = "classic", difficulty: str = "normal",
                   arcade: bool = False):
    """Composição para testes: null backends, controle manual do step.
    Retorna (world, input_provider, memory acessível via world.get_pool)."""
    from ouroboros.interfaces.null.null_input_provider import NullInputProvider

    data = load_all()
    input_provider = NullInputProvider()
    world = build_world(data, input_provider, boss_name, weapon_name,
                        skill_name, mutators, mode, difficulty, arcade)
    return world, input_provider
