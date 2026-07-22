"""
Smoke test do replay (PARITY_PLAN.md P0-5): grava uma run e reproduz —
como o port não usa RNG global em lugar nenhum (toda "aleatoriedade" é
hash determinístico por contador de emissor), a mesma sequência de
inputs deve reproduzir EXATAMENTE a mesma trajetória de HP do boss.

Uso: python smoke_replay.py
"""
import numpy as np

import bullethell  # noqa: F401 — engine no sys.path
from ouroboros.interfaces.null.null_input_provider import NullInputProvider
from ouroboros.interfaces.null.null_renderer import NullRenderer
from bullethell.loaders import load_all
from bullethell.scenes import GameApp, PLAYING, REPLAYING

DATA = load_all()
FRAMES = 400


def _drive_input(inp: NullInputProvider, f: int) -> None:
    """Padrão determinístico de teclas (não precisa ser 'jogável', só
    precisa ser o MESMO padrão gravado e depois relido do replay)."""
    inp.set_action_held("fire", True)
    inp.set_action_held("move_right", (f // 30) % 2 == 0)
    inp.set_action_held("move_left", (f // 30) % 2 == 1)
    inp.set_action_held("move_up", (f % 50) < 10)
    inp.set_action_held("skill", (f % 90) < 5)


def _boss_hp(app: GameApp) -> float:
    bp = app.world.get_pool("boss")
    return float(np.sum(bp.active_view()["hp"][: bp.count])) if bp.count else -1.0


def check(label: str, cond: bool) -> bool:
    print(f"[{'OK ' if cond else 'FAIL'}] {label}")
    return cond


if __name__ == "__main__":
    ok = True
    inp = NullInputProvider()
    app = GameApp(NullRenderer(), inp, None, DATA, save_data={})
    app.sel.update(mode="classic", diff="facil", boss="classic",
                   skill="none", weapon="padrao")
    app.start_game()
    ok &= check("start_game -> PLAYING", app.state == PLAYING)
    ok &= check("grava sem frames antes de jogar", app.replay_frames == [])

    original_hp = []
    for f in range(FRAMES):
        _drive_input(inp, f)
        inp.poll()
        app.tick(1 / 60)
        if app.state != PLAYING:      # boss morreu ou o jogador morreu antes
            break
        original_hp.append(_boss_hp(app))

    ok &= check(f"gravou {len(app.replay_frames)} frames",
               len(app.replay_frames) == len(original_hp))

    app._finish_run("abandon")        # fecha a run (como ESC faria)
    app._start_replay()
    ok &= check("_start_replay -> REPLAYING", app.state == REPLAYING)

    replay_hp = []
    guard = 0
    while app.state == REPLAYING and guard < FRAMES + 10:
        app.tick(1 / 60)              # dt real ignorado — usa o gravado
        guard += 1
        if app.state == REPLAYING:
            replay_hp.append(_boss_hp(app))

    ok &= check("replay rodou o mesmo numero de frames da gravacao",
               len(replay_hp) == len(original_hp))
    same = len(replay_hp) == len(original_hp) and \
        all(a == b for a, b in zip(original_hp, replay_hp))
    ok &= check("trajetoria de HP do boss identica bit-a-bit (determinismo)",
               same)
    if not same and len(replay_hp) == len(original_hp):
        diffs = [(i, a, b) for i, (a, b) in
                 enumerate(zip(original_hp, replay_hp)) if a != b]
        print("  primeiras divergencias:", diffs[:5])

    raise SystemExit(0 if ok else 1)
