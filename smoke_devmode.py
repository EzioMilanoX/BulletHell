"""
Smoke test do dev overlay/cheats (PARITY_PLAN.md P2): sequência secreta
W W S S A D A D liga o dev mode; com ele ligado, F9/F10 (qualquer estado)
e F5/F3/F4/F7/F6 (gameplay) fazem o que o legado faz (main.py:1717-1775,
2371-2418). Roda GameApp com backends null, sem janela real.

Uso: python smoke_devmode.py
"""
import os

import numpy as np

import bullethell  # noqa: F401 — engine no sys.path
from ouroboros.interfaces.null.null_input_provider import NullInputProvider
from ouroboros.interfaces.null.null_renderer import NullRenderer
from bullethell.loaders import DATA_DIR, load_all
from bullethell.scenes import GameApp, PLAYING

DATA = load_all()


def press(app: GameApp, inp: NullInputProvider, action: str) -> None:
    inp.set_action_held(action, True)
    inp.poll(); app.tick(1 / 60)
    inp.set_action_held(action, False)
    inp.poll(); app.tick(1 / 60)


def check(label: str, cond: bool) -> bool:
    print(f"[{'OK ' if cond else 'FAIL'}] {label}")
    return cond


if __name__ == "__main__":
    ok = True
    inp = NullInputProvider()
    app = GameApp(NullRenderer(), inp, None, DATA, save_data={})

    # sequência secreta: W W S S A D A D
    for action in ("move_up", "move_up", "move_down", "move_down",
                  "move_left", "move_right", "move_left", "move_right"):
        press(app, inp, action)
    ok &= check("sequencia secreta liga o dev mode", app.dev_mode is True)

    press(app, inp, "cheat_unlock")
    ok &= check("F9 destrava highest_cleared_diff no maximo",
               app.save["highest_cleared_diff"] == 4)
    ok &= check("F9 destrava sins_rush_cleared", app.save["sins_rush_cleared"])
    ok &= check("F9 destrava todas as skills",
               len(app.save["unlocked_skills"]) == 9)
    ok &= check("F9 destrava as variantes '+'",
               app._plus_unlocked("skill", "dash")
               and app._plus_unlocked("weapon", "plasma"))

    app.sel.update(diff="dificil", skill="emp", weapon="plasma",
                  muts={"predador"})
    press(app, inp, "cheat_wipe")
    ok &= check("F10 apaga o save (highest_cleared_diff volta a 0)",
               app.save["highest_cleared_diff"] == 0)
    ok &= check("F10 reseta a selecao (diff volta a facil)",
               app.sel["diff"] == "facil" and app.sel["skill"] == "none"
               and app.sel["muts"] == set())

    press(app, inp, "cheat_godmode")
    ok &= check("F6 liga o god mode", app.godmode is True)

    app.sel.update(mode="classic", diff="facil", boss="classic",
                  skill="none", weapon="padrao", muts=set())
    app.start_game()
    ok &= check("start_game -> PLAYING", app.state == PLAYING)
    app.tick(1 / 60)
    pl = app.world.get_pool("player")
    prow = pl.dense_row_of(int(pl.active_entity_indices()[0]))
    ok &= check("god mode mantem o jogador invulneravel (invuln_t alto)",
               float(pl.active_view()["invuln_t"][prow]) > 100.0)

    bp = app.world.get_pool("boss")
    max_hp = float(bp.active_view()["max_hp"][0])
    press(app, inp, "cheat_hp50")
    hp = float(bp.active_view()["hp"][0])
    ok &= check("F3 poe o boss em 50% do HP",
               abs(hp - max_hp * 0.5) < 1e-3)

    # F7 primeiro, enquanto ainda sobra fase pra avancar (o classico tem 5
    # fases — a 50% de HP ainda da pra subir pelo menos uma)
    phase_before = int(bp.active_view()["phase_idx"][0])
    press(app, inp, "cheat_phase")
    phase_after = int(bp.active_view()["phase_idx"][0])
    ok &= check("F7 avanca a fase do boss",
               phase_after == phase_before + 1)

    press(app, inp, "cheat_hp10")
    hp = float(bp.active_view()["hp"][0])
    ok &= check("F4 poe o boss em 10% do HP",
               abs(hp - max_hp * 0.1) < 1e-3)

    kills_before = int(app.world.get_pool("stats").active_view()["kills"][0])
    press(app, inp, "cheat_kill")
    kills_after = int(app.world.get_pool("stats").active_view()["kills"][0])
    ok &= check("F5 mata o boss (kills incrementa; modo classico reinicia)",
               kills_after == kills_before + 1)

    # desliga o dev mode de novo e confere que os cheats param de responder
    for action in ("move_up", "move_up", "move_down", "move_down",
                  "move_left", "move_right", "move_left", "move_right"):
        press(app, inp, action)
    ok &= check("sequencia secreta desliga o dev mode de novo",
               app.dev_mode is False)
    hcd_before = app.save["highest_cleared_diff"]
    press(app, inp, "cheat_unlock")
    ok &= check("F9 nao faz nada com o dev mode desligado",
               app.save["highest_cleared_diff"] == hcd_before)

    # --- hot-reload de data/*.json (so em dev_mode, ~1s) ---------------------
    # o mtime alvo precisa superar o MAIOR mtime entre data/*.json (nao só o
    # do próprio arquivo) — senão outro .json editado mais recentemente ainda
    # domina o max() e o hot-reload nunca dispara.
    target = DATA_DIR / "skills.json"
    original_mtime = target.stat().st_mtime
    future = app._data_dir_mtime() + 5.0
    try:
        os.utime(target, (future, future))
        old_data = app._data
        inp.poll(); app.tick(1.5)          # dev_mode ainda off: nao recarrega
        ok &= check("hot-reload nao acontece com dev mode desligado",
                   app._data is old_data)

        for action in ("move_up", "move_up", "move_down", "move_down",
                      "move_left", "move_right", "move_left", "move_right"):
            press(app, inp, action)
        ok &= check("sequencia secreta liga o dev mode de novo",
                   app.dev_mode is True)
        inp.poll(); app.tick(1.5)          # passa do check de ~1s
        ok &= check("hot-reload recarrega data/*.json com dev mode ligado",
                   app._data is not old_data)
        ok &= check("hot-reload mostra o flash BALANCE RELOADED",
                   app.dev_flash_msg == "BALANCE RELOADED")
    finally:
        os.utime(target, (original_mtime, original_mtime))  # nao deixa lixo

    raise SystemExit(0 if ok else 1)
