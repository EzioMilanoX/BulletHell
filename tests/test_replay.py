"""Replay e determinismo (portado de smoke_replay.py + a intenção do
ReplayRecorder do legado). O port não usa RNG global — toda
"aleatoriedade" é hash determinístico por contador — então a mesma
sequência de inputs reproduz EXATAMENTE a mesma trajetória.
"""
import numpy as np
import pytest

from helpers import make_app, step

from ouroboros.interfaces.null.null_input_provider import NullInputProvider

from bullethell.composition import build_headless
from bullethell.replay import REPLAY_ACTIONS, ReplayInputProvider, encode_frame
from bullethell.scenes import PLAYING, REPLAYING

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
# ReplayInputProvider (unidade)
# ---------------------------------------------------------------------------

def test_encode_frame_um_bit_por_acao():
    inp = NullInputProvider()
    assert encode_frame(inp) == 0
    inp.set_action_held("fire", True)
    inp.set_action_held("move_left", True)
    inp.poll()
    bits = encode_frame(inp)
    assert bits == (1 << REPLAY_ACTIONS.index("fire")) | \
        (1 << REPLAY_ACTIONS.index("move_left"))


def test_replay_input_provider_bordas_e_fim():
    fire = 1 << REPLAY_ACTIONS.index("fire")
    rp = ReplayInputProvider([(0, 0.01), (fire, 0.02), (fire, 0.03), (0, 0.04)])
    rp.poll()
    assert not rp.is_action_held("fire")
    rp.poll()
    assert rp.is_action_pressed("fire") and rp.is_action_held("fire")
    assert rp.current_dt() == pytest.approx(0.02)
    rp.poll()
    assert rp.is_action_held("fire") and not rp.is_action_pressed("fire")
    rp.poll()
    assert rp.is_action_released("fire")
    assert not rp.is_action_held("acao_inexistente")
    rp.poll()
    assert not rp.has_more()
    assert rp.current_dt() == pytest.approx(1 / 60)
    assert rp.wants_quit() is False


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
    assert app.replay_frames == []

    original = []
    for f in range(FRAMES):
        _drive_input(inp, f)
        inp.poll()
        app.tick(1 / 60)
        if app.state != PLAYING:
            break
        original.append(_boss_hp(app.world))
    assert len(app.replay_frames) == len(original)

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
