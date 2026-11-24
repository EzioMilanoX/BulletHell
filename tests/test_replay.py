"""Replay e determinismo (portado de smoke_replay.py + a intenção do
ReplayRecorder do legado). O port não usa RNG global — toda
"aleatoriedade" é hash determinístico por contador — então a mesma
sequência de inputs reproduz EXATAMENTE a mesma trajetória.

Gravação/reprodução são da engine (`ouroboros.bootstrap.replay`, testada
lá: bordas, fim, arquivo, dessincronização); aqui fica o que é do jogo — as
ações gravadas, a cena de replay e o determinismo dos sistemas.
"""
import numpy as np
import pytest

from helpers import make_app, step

from ouroboros.bootstrap.replay import ActionMask
from ouroboros.interfaces.null.null_input_provider import NullInputProvider

from bullethell.composition import build_headless
from bullethell.scenes import PLAYING, REPLAY_ACTIONS, REPLAY_HASH_EVERY, REPLAYING

FRAMES = 400


def _drive_input(inp, f: int) -> None:
    """Padrão determinístico de teclas (não precisa ser 'jogável')."""
    inp.set_action_held("fire", True)
    inp.set_action_held("move_right", (f // 30) % 2 == 0)
    inp.set_action_held("move_left", (f // 30) % 2 == 1)
    inp.set_action_held("move_up", (f % 50) < 10)
    inp.set_action_held("skill", (f % 90) < 5)


def _boss_hp(world) -> float:
    bp = world.get_pool("boss")
    return float(np.sum(bp.active_view()["hp"][: bp.count])) if bp.count else -1.0


# ---------------------------------------------------------------------------
# as ações gravadas
# ---------------------------------------------------------------------------

def test_acoes_do_replay_um_bit_cada_na_ordem_de_sempre():
    """A ordem é o formato: mudar quebra replays (só acrescentar no fim)."""
    assert REPLAY_ACTIONS[:8] == ("move_up", "move_down", "move_left", "move_right",
                                  "fire", "skill", "toggle_plus", "toggle_skill_plus")
    mask = ActionMask(REPLAY_ACTIONS)
    inp = NullInputProvider()
    assert mask.encode(inp) == 0
    inp.set_action_held("fire", True)
    inp.set_action_held("move_left", True)
    inp.poll()
    assert mask.encode(inp) == (1 << REPLAY_ACTIONS.index("fire")) | \
        (1 << REPLAY_ACTIONS.index("move_left"))


# ---------------------------------------------------------------------------
# determinismo da simulação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("boss", ["classic", "truth", "sin"])
def test_mesmos_inputs_mesma_simulacao(boss):
    """Dois mundos independentes com o mesmo input → bit-a-bit iguais."""
    trajetorias = []
    for _ in range(2):
        world, inp = build_headless(boss_name=boss, weapon_name="spread",
                                    skill_name="dash", difficulty="abissal")
        hp = []
        for f in range(300):
            _drive_input(inp, f)
            step(world, inp)
            hp.append((_boss_hp(world), world.get_pool("enemy_bullet").count))
        trajetorias.append(hp)
    assert trajetorias[0] == trajetorias[1]


def test_grava_e_reproduz_bit_a_bit(data):
    app, inp = make_app(data)
    app.sel.update(mode="classic", diff="facil", boss="classic",
                   skill="none", weapon="padrao")
    app.start_game()
    assert app.state == PLAYING
    assert len(app.replay) == 0

    original = []
    for f in range(FRAMES):
        _drive_input(inp, f)
        inp.poll()
        app.tick(1 / 60)
        if app.state != PLAYING:
            break
        original.append(_boss_hp(app.world))
    assert len(app.replay) == len(original)
    gravado = app.replay.replay()
    assert len(gravado.hash_frames) == -(-len(original) // REPLAY_HASH_EVERY)
    assert gravado.game_version and gravado.seed == 0

    app._finish_run("abandon")              # fecha a run (como ESC faria)
    app._start_replay()
    assert app.state == REPLAYING

    reproduzido = []
    guard = 0
    while app.state == REPLAYING and guard < FRAMES + 10:
        app.tick(1 / 60)                    # dt real ignorado — usa o gravado
        guard += 1
        if app.state == REPLAYING:
            reproduzido.append(_boss_hp(app.world))
    assert reproduzido == original
    assert not app._replay_input.desynced     # os hashes de estado bateram


def test_cheat_na_gravacao_aparece_como_dessincronizacao(data):
    """Godmode (dev mode) mexe no jogador fora do input gravado: o replay não
    é mais a run que aconteceu, e o hash pega isso no primeiro segundo."""
    app, inp = make_app(data)
    app.sel.update(mode="classic", diff="facil", boss="classic",
                   skill="none", weapon="padrao")
    app.start_game()
    app.godmode = True
    for f in range(2 * REPLAY_HASH_EVERY + 5):
        _drive_input(inp, f)
        inp.poll()
        app.tick(1 / 60)
    app.godmode = False
    app._finish_run("abandon")
    app._start_replay()
    while app.state == REPLAYING:
        app.tick(1 / 60)
    assert app._replay_input.desynced
    assert app._replay_input.desync_frame == 0
