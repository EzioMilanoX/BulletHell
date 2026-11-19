"""Menus sobre o SceneStack (portado de smoke_menu.py + menu_smoke de
smoke_ecs.py): navegação MAIN → REGISTROS/SISTEMA → assistente completo
até PLAYING, toggles de SISTEMA persistindo em save["settings"], e um
check com o PygameRenderer real (buffer de pixels) contra a classe de bug
"tela preta com botões invisíveis" (14n).
"""
import numpy as np
import pytest

from helpers import make_app, press

from bullethell.scenes import (MC_Y0, MC_Y1, MENU_BOSS, MENU_DIFF, MENU_MAIN,
                               MENU_MODE, MENU_MUT, MENU_RECORDS,
                               MENU_SETTINGS, MENU_SKILL, MENU_WEAPON, MLL_W,
                               MLL_X, PLAYING)


def test_boot_abre_no_menu_principal(data):
    app, _ = make_app(data)
    assert app.state == MENU_MAIN


def test_registros_abre_e_volta(data):
    app, inp = make_app(data)
    press(app, inp, "move_down")
    press(app, inp, "move_down")
    assert app.cursor == 2
    press(app, inp, "confirm")
    assert app.state == MENU_RECORDS
    press(app, inp, "back")
    assert app.state == MENU_MAIN
    assert app.cursor == 0, "cursor do menu principal reseta ao voltar"


def test_sistema_toggles_persistem_no_save(data):
    app, inp = make_app(data)
    for _ in range(3):
        press(app, inp, "move_down")
    assert app.cursor == 3
    press(app, inp, "confirm")
    assert app.state == MENU_SETTINGS
    assert app.save["settings"]["screen_shake"] is True

    press(app, inp, "confirm")
    assert app.save["settings"]["screen_shake"] is False
    press(app, inp, "move_down")
    press(app, inp, "confirm")
    assert app.save["settings"]["show_hitbox"] is True
    press(app, inp, "move_down")
    press(app, inp, "confirm")
    assert app.save["settings"]["fullscreen"] is True
    assert app._r._is_fullscreen is True, "toggle chama set_fullscreen no renderer"
    press(app, inp, "back")
    assert app.state == MENU_MAIN


def test_save_antigo_sem_fullscreen_ganha_default_desligado(data):
    """Bug real corrigido em 44372fa: save sem a chave começava LIGADO."""
    app, _ = make_app(data, save={"settings": {"screen_shake": False,
                                               "show_hitbox": False}})
    assert app.save["settings"]["fullscreen"] is False
    assert app.save["settings"]["screen_shake"] is False


def test_assistente_completo_ate_playing(data):
    app, inp = make_app(data)
    press(app, inp, "confirm")                     # JOGAR
    assert app.state == MENU_MODE
    press(app, inp, "confirm")                     # CLÁSSICO
    assert app.state == MENU_DIFF
    press(app, inp, "confirm")                     # única destravada: FÁCIL
    assert app.state == MENU_BOSS
    press(app, inp, "confirm")                     # CLÁSSICO
    assert app.state == MENU_SKILL
    press(app, inp, "confirm")                     # NENHUMA
    assert app.state == MENU_WEAPON
    press(app, inp, "confirm")                     # PADRÃO
    assert app.state == MENU_MUT
    for _ in range(8):          # pula o CLAUSTROFOBIA travado até '► COMEÇAR'
        if app.cursor == 6:
            break
        press(app, inp, "move_down")
    assert app.cursor == 6
    press(app, inp, "confirm")
    assert app.state == PLAYING
    assert app.world is not None


def test_assistente_com_dash_e_wrap_ate_playing(data):
    """Variação do smoke_ecs: troca a habilidade e usa o wrap do cursor."""
    app, inp = make_app(data)
    for action in ("confirm", "confirm", "confirm", "confirm",   # até SKILL
                   "move_down", "confirm",                       # DASH
                   "confirm",                                    # PADRÃO
                   "move_up", "confirm"):                        # wrap → COMEÇAR
        press(app, inp, action)
    for _ in range(120):
        inp.poll()
        app.tick(1 / 60)
    assert app.state == PLAYING
    assert app.sel["skill"] == "dash"


def test_wizard_desenha_os_itens_de_verdade(data):
    """NullRenderer não desenha nada — só um buffer de pixels real pega o
    bug em que a WizardScene desenhava em update() (antes do begin_frame()
    limpar a tela) e nada aparecia."""
    pygame = pytest.importorskip("pygame")
    from ouroboros.adapters.pygame_backend.pygame_renderer import PygameRenderer

    renderer = PygameRenderer()
    renderer.initialize(1280, 720, "teste")
    try:
        app, inp = make_app(data, renderer=renderer)
        app.tick(1 / 60)
        press(app, inp, "confirm")                 # JOGAR -> MENU_MODE
        region = pygame.surfarray.array3d(renderer._surface)[
            MLL_X:MLL_X + MLL_W, MC_Y0:MC_Y1, :]
        assert not np.all(region == np.array((8, 8, 14)))
    finally:
        renderer.shutdown()
