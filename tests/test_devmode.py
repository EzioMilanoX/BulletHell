"""Dev overlay/cheats (portado de smoke_devmode.py): a sequência secreta
W W S S A D A D liga/desliga o dev mode; com ele ligado, F9/F10 (qualquer
estado), F6 e F5/F3/F4/F7 (gameplay) fazem o que o legado fazia, e o
hot-reload de data/*.json só acontece com o dev mode ligado.
"""
import os

import pytest

from helpers import make_app, press, toggle_dev_mode

from bullethell.loaders import DATA_DIR
from bullethell.scenes import PLAYING


@pytest.fixture
def app_dev(data):
    app, inp = make_app(data)
    toggle_dev_mode(app, inp)
    assert app.dev_mode is True
    return app, inp


def test_f9_destrava_tudo(app_dev):
    app, inp = app_dev
    press(app, inp, "cheat_unlock")
    assert app.save["highest_cleared_diff"] == 4
    assert app.save["sins_rush_cleared"]
    assert len(app.save["unlocked_skills"]) == 9
    assert app._plus_unlocked("skill", "dash")
    assert app._plus_unlocked("weapon", "plasma")


def test_f10_apaga_save_e_reseta_selecao(app_dev):
    app, inp = app_dev
    press(app, inp, "cheat_unlock")
    app.sel.update(diff="dificil", skill="emp", weapon="plasma", muts={"predador"})
    press(app, inp, "cheat_wipe")
    assert app.save["highest_cleared_diff"] == 0
    assert app.sel["diff"] == "facil"
    assert app.sel["skill"] == "none"
    assert app.sel["muts"] == set()


def test_cheats_de_gameplay(app_dev):
    app, inp = app_dev
    press(app, inp, "cheat_godmode")
    assert app.godmode is True

    app.sel.update(mode="classic", diff="facil", boss="classic",
                   skill="none", weapon="padrao", muts=set())
    app.start_game()
    assert app.state == PLAYING
    app.tick(1 / 60)
    pl = app.world.get_pool("player")
    prow = pl.dense_row_of(int(pl.active_entity_indices()[0]))
    assert float(pl.active_view()["invuln_t"][prow]) > 100.0, "god mode"

    bp = app.world.get_pool("boss")
    max_hp = float(bp.active_view()["max_hp"][0])
    press(app, inp, "cheat_hp50")
    assert float(bp.active_view()["hp"][0]) == pytest.approx(max_hp * 0.5, abs=1e-3)

    # F7 antes do F4, enquanto ainda sobra fase pra avançar
    fase = int(bp.active_view()["phase_idx"][0])
    press(app, inp, "cheat_phase")
    assert int(bp.active_view()["phase_idx"][0]) == fase + 1

    press(app, inp, "cheat_hp10")
    assert float(bp.active_view()["hp"][0]) == pytest.approx(max_hp * 0.1, abs=1e-3)

    kills = int(app.world.get_pool("stats").active_view()["kills"][0])
    press(app, inp, "cheat_kill")
    assert int(app.world.get_pool("stats").active_view()["kills"][0]) == kills + 1


def test_sequencia_desliga_e_cheats_param(app_dev):
    app, inp = app_dev
    toggle_dev_mode(app, inp)
    assert app.dev_mode is False
    hcd = app.save.get("highest_cleared_diff", 0)
    press(app, inp, "cheat_unlock")
    assert app.save.get("highest_cleared_diff", 0) == hcd


def test_hot_reload_so_com_dev_mode(data):
    """O mtime alvo precisa superar o MAIOR mtime entre data/*.json (não
    só o do próprio arquivo), senão outro .json mais recente domina."""
    app, inp = make_app(data)
    target = DATA_DIR / "skills.json"
    original = target.stat().st_mtime
    future = app._data_dir_mtime() + 5.0
    try:
        os.utime(target, (future, future))
        old_data = app._data
        inp.poll()
        app.tick(1.5)                          # dev mode off: não recarrega
        assert app._data is old_data

        toggle_dev_mode(app, inp)
        assert app.dev_mode is True
        inp.poll()
        app.tick(1.5)                          # passa do check de ~1s
        assert app._data is not old_data
        assert app.dev_flash_msg == "BALANCE RELOADED"
    finally:
        os.utime(target, (original, original))  # não deixa lixo
