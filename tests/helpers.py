"""Helpers compartilhados da suíte do port ECS (null backends, headless).

Importável direto dos testes (`from helpers import ...`): o pytest põe
`tests/` no sys.path ao coletar módulos sem `__init__.py`.

`World.get_pool()` delega para o mesmo MemoryManager que os sistemas usam
— por isso os helpers `spawn_*` do jogo aceitam `world` no lugar de `mm`
(eles só chamam `.get_pool(nome)`).
"""
import numpy as np

import bullethell  # noqa: F401 — garante a engine no sys.path
from bullethell.composition import build_headless

DT = 1 / 60


# ---------------------------------------------------------------------------
# World headless (build_headless) — sem GameApp, step manual
# ---------------------------------------------------------------------------

def step(world, inp, n: int = 1) -> None:
    for _ in range(n):
        inp.poll()
        world.step(DT)


def player_trow(world) -> int:
    pl = world.get_pool("player")
    return world.get_pool("transform").dense_row_of(int(pl.active_entity_indices()[0]))


def player_prow(world) -> int:
    pl = world.get_pool("player")
    return pl.dense_row_of(int(pl.active_entity_indices()[0]))


def player_pos(world) -> tuple:
    tv = world.get_pool("transform").active_view()
    row = player_trow(world)
    return float(tv["position_x"][row]), float(tv["position_y"][row])


def set_player_pos(world, x: float, y: float) -> None:
    tv = world.get_pool("transform").active_view()
    row = player_trow(world)
    tv["position_x"][row] = x
    tv["position_y"][row] = y


def player_view(world):
    return world.get_pool("player").active_view()


def boss_trow(world, k: int = 0) -> int:
    bp = world.get_pool("boss")
    return world.get_pool("transform").dense_row_of(int(bp.active_entity_indices()[k]))


def boss_pos(world, k: int = 0) -> tuple:
    tv = world.get_pool("transform").active_view()
    row = boss_trow(world, k)
    return float(tv["position_x"][row]), float(tv["position_y"][row])


def boss_view(world):
    return world.get_pool("boss").active_view()


def force_boss_hp(world, frac: float, k: int = 0) -> None:
    bv = boss_view(world)
    bv["hp"][k] = bv["max_hp"][k] * frac


def follow_boss_and_step(world, inp, offset_y: float, n: int) -> None:
    """Gruda o jogador na posição ATUAL do boss a cada frame (o Clássico
    anda entre waypoints — sem isso o jogador perde o alvo por movimento
    do boss, não por falha do sistema testado)."""
    for _ in range(n):
        bx, by = boss_pos(world)
        set_player_pos(world, bx, by + offset_y)
        step(world, inp)


def simulate(boss: str, weapon: str, frames: int = 900, approach: bool = False,
             skill: str = "none", mutators: frozenset = frozenset(),
             mode: str = "classic", difficulty: str = "normal") -> dict:
    """Partida headless com um "piloto" simples: atira com pulsos de
    release, pulsa a habilidade e segue o x do boss (portado de
    smoke_ecs.run)."""
    world, inp = build_headless(boss_name=boss, weapon_name=weapon,
                                skill_name=skill, mutators=mutators, mode=mode,
                                difficulty=difficulty)
    eb = world.get_pool("enemy_bullet")
    bp = world.get_pool("boss")
    pl = world.get_pool("player")
    tp = world.get_pool("transform")

    max_eb = 0
    hp0 = float(np.sum(bp.active_view()["hp"]))
    for f in range(frames):
        # fire com pulsos de release (charged/flak+/swarm dependem do edge);
        # período 300 = CD 1.5s + carga cheia 2.5s do CARREGADO (frac 1.0)
        inp.set_action_held("fire", (f % 300) < 288)
        # habilidade: FOCUS segura sempre; demais pulsam (edge a cada 4s)
        if skill != "none":
            inp.set_action_held("skill",
                                True if skill.startswith("focus")
                                else (f % 240) < 20)
        # mira: rastreia o x do boss como um jogador faria
        # (waves pode não ter boss: mira o centro)
        tv = tp.active_view()
        prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
        bx = 640.0
        if bp.count:
            brow = tp.dense_row_of(int(bp.active_entity_indices()[0]))
            bx = float(tv["position_x"][brow])
        px = float(tv["position_x"][prow])
        py = float(tv["position_y"][prow])
        inp.set_action_held("move_right", px < bx - 6.0)
        inp.set_action_held("move_left", px > bx + 6.0)
        # armas curto-alcance ou de tiro lento (plasma/spread+/chakram/
        # satélite/carregado): aproximar reduz o tempo de voo e o erro
        # de antecipação do driver
        inp.set_action_held("move_up", approach and py > 205.0)
        inp.poll()
        world.step(DT)
        max_eb = max(max_eb, eb.count)
    hp1 = float(np.sum(bp.active_view()["hp"]))
    st = world.get_pool("stats").active_view()
    wv = world.get_pool("wave").active_view()
    return {
        "enemy_bullets_peak": max_eb,
        "boss_damage": hp0 - hp1,
        "kills": int(st["kills"][0]),
        "wave": int(wv["idx"][0]) + 1 if world.get_pool("wave").count else 0,
    }


# ---------------------------------------------------------------------------
# GameApp com SceneStack (menus, replay, dev mode)
# ---------------------------------------------------------------------------

def make_app(data, save: dict | None = None, renderer=None):
    """GameApp + GameLoop com MainMenuScene no topo, como main_ecs.py monta
    — mas com NullRenderer/NullInputProvider. Retorna (app, input)."""
    from ouroboros.bootstrap.game_loop import GameLoop
    from ouroboros.core.memory.memory_manager import MemoryManager
    from ouroboros.core.world import World
    from ouroboros.interfaces.null.null_input_provider import NullInputProvider
    from ouroboros.interfaces.null.null_renderer import NullRenderer
    from bullethell.scenes import GameApp, MainMenuScene

    inp = NullInputProvider()
    if renderer is None:
        renderer = NullRenderer()
        renderer.initialize(800, 600, "teste")
    app = GameApp(renderer, inp, None, data,
                  save_data={} if save is None else save)
    game_loop = GameLoop(World(MemoryManager(entity_capacity=1)), renderer, inp, None)
    app.game_loop = game_loop
    game_loop.reset_scenes(MainMenuScene(app))
    return app, inp


def press(app, inp, action: str) -> None:
    """Aperta e solta uma ação (dois ticks: borda de subida e de descida)."""
    inp.set_action_held(action, True)
    inp.poll()
    app.tick(1 / 60)
    inp.set_action_held(action, False)
    inp.poll()
    app.tick(1 / 60)


SECRET_SEQUENCE = ("move_up", "move_up", "move_down", "move_down",
                   "move_left", "move_right", "move_left", "move_right")


def toggle_dev_mode(app, inp) -> None:
    for action in SECRET_SEQUENCE:
        press(app, inp, action)
