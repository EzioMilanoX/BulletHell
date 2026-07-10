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
from ouroboros.core.systems.physics_system import PhysicsSystem
from ouroboros.core.world import World

from bullethell.ids import sid
from bullethell.loaders import GameData, load_all
from bullethell.schemas import GAME_POOL_CAPACITY, GAME_SCHEMAS, SCREEN_H, SCREEN_W
from bullethell import game_systems as gs

ENTITY_CAPACITY = 8192


def build_world(data: GameData, input_provider, boss_name: str = "classic",
                weapon_name: str = "padrao") -> World:
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
    world.register_archetype("emitter", ("emitter",))
    world.register_archetype("enemy_bullet", ("transform", "velocity", "sprite",
                                              "enemy_bullet"))
    # arquétipos de bala do jogador: 1 por arma (base + variante +)
    for wdef in data.weapons.values():
        world.register_archetype(
            "pb_" + wdef.name,
            ("transform", "velocity", "sprite", "pb_core") + wdef.pools)

    # sistemas — ordem do frame (MIGRATION.md §3)
    world.register_system(gs.PlayerControlSystem(mm, input_provider))
    world.register_system(gs.WeaponFireSystem(mm, input_provider, data))
    world.register_system(gs.BossPhaseSystem(mm, data))
    world.register_system(gs.WaypointSystem(mm, data))
    world.register_system(gs.EmitterSystem(mm, data))
    world.register_system(PhysicsSystem(mm))               # engine: Transform += Velocity*dt
    world.register_system(gs.EnemyBulletBehaviorSystem(mm))
    world.register_system(gs.PlayerBulletHomingSystem(mm))
    world.register_system(gs.MaintenanceSystem(mm))
    world.register_system(gs.PlayerHitSystem(mm))
    world.register_system(gs.PlayerBulletVsBossSystem(mm))

    _spawn_player(world, mm, data, weapon_name)
    _spawn_boss(world, mm, data, boss_name)
    return world


def _spawn_player(world: World, mm: MemoryManager, data: GameData, weapon_name: str) -> None:
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
    pv["lives"][row] = 3
    pv["weapon_id"][row] = sid(weapon_name)


def _spawn_boss(world: World, mm: MemoryManager, data: GameData, boss_name: str) -> None:
    bdef = data.bosses[sid(boss_name)]
    packed = world.create_entity("boss")
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform"); row = t.dense_row_of(idx); tv = t.active_view()
    x0, y0 = (bdef.route[0][0], bdef.route[0][1]) if bdef.route else (SCREEN_W / 2, 100.0)
    tv["position_x"][row] = x0
    tv["position_y"][row] = y0
    half_w = bdef.parts[0][2] if bdef.parts else 24.0
    half_h = bdef.parts[0][3] if bdef.parts else 24.0
    tv["scale_x"][row] = half_w / 4.0
    tv["scale_y"][row] = half_h / 4.0
    s = mm.get_pool("sprite"); row = s.dense_row_of(idx); sv = s.active_view()
    sv["tint_r"][row], sv["tint_g"][row], sv["tint_b"][row] = 230, 60, 120
    sv["tint_a"][row] = 255
    sv["layer_z"][row] = 15
    h = mm.get_pool("hitbox"); row = h.dense_row_of(idx); hv = h.active_view()
    hv["half_width"][row] = half_w
    hv["half_height"][row] = half_h
    b = mm.get_pool("boss"); row = b.dense_row_of(idx); bv = b.active_view()
    bv["boss_id"][row] = sid(boss_name)
    bv["hp"][row] = bv["max_hp"][row] = bdef.hp
    bv["phase_idx"][row] = 0
    gs.spawn_emitters(world, mm.get_pool("emitter"), idx, bdef.phases[0])


def build_game(boss_name: str = "classic", weapon_name: str = "padrao") -> GameLoop:
    """Composição com janela pygame real."""
    from ouroboros.adapters.pygame_backend.pygame_audio_engine import PygameAudioEngine
    from ouroboros.adapters.pygame_backend.pygame_input_provider import PygameInputProvider
    from ouroboros.adapters.pygame_backend.pygame_renderer import PygameRenderer
    from bullethell.loaders import DATA_DIR

    data = load_all()
    renderer = PygameRenderer()
    renderer.initialize(SCREEN_W, SCREEN_H, "BULLET HELL — OuroborosEngine")
    input_provider = PygameInputProvider()
    input_provider.load_bindings(str(DATA_DIR / "input_bindings.json"))
    world = build_world(data, input_provider, boss_name, weapon_name)
    return GameLoop(world, renderer, input_provider, PygameAudioEngine())


def build_headless(boss_name: str = "classic", weapon_name: str = "padrao"):
    """Composição para testes: null backends, controle manual do step.
    Retorna (world, input_provider, memory acessível via world.get_pool)."""
    from ouroboros.interfaces.null.null_input_provider import NullInputProvider

    data = load_all()
    input_provider = NullInputProvider()
    world = build_world(data, input_provider, boss_name, weapon_name)
    return world, input_provider
