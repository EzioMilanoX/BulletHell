"""
Smoke test do menu redesenhado (PARITY_PLAN.md P0-4): cards coloridos +
step-dots + breadcrumb, telas REGISTROS/SISTEMA novas, e que os toggles de
SISTEMA persistem em save["settings"]. Roda GameApp com backends null,
sem janela real.

Uso: python smoke_menu.py
"""
import bullethell  # noqa: F401 — engine no sys.path
from ouroboros.interfaces.null.null_input_provider import NullInputProvider
from ouroboros.interfaces.null.null_renderer import NullRenderer
from bullethell.loaders import load_all
from bullethell.scenes import (GameApp, MENU_BOSS, MENU_DIFF, MENU_MAIN,
                               MENU_MODE, MENU_MUT, MENU_RECORDS,
                               MENU_SETTINGS, MENU_SKILL, MENU_WEAPON,
                               PLAYING)

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

    ok &= check("boot -> MENU_MAIN", app.state == MENU_MAIN)

    press(app, inp, "move_down"); press(app, inp, "move_down")
    ok &= check("MAIN_MENU cursor 2 = REGISTROS", app.cursor == 2)
    press(app, inp, "confirm")
    ok &= check("REGISTROS abre sem erro", app.state == MENU_RECORDS)
    press(app, inp, "back")
    ok &= check("ESC em REGISTROS -> MENU_MAIN", app.state == MENU_MAIN)

    for _ in range(3):
        press(app, inp, "move_down")
    ok &= check("MAIN_MENU cursor 3 = SISTEMA", app.cursor == 3)
    press(app, inp, "confirm")
    ok &= check("SISTEMA abre sem erro", app.state == MENU_SETTINGS)
    ok &= check("screen_shake começa ligado",
               app.save.get("settings", {}).get("screen_shake", True) is True)
    press(app, inp, "confirm")
    ok &= check("toggle Screen Shake persiste em save['settings']",
               app.save["settings"]["screen_shake"] is False)
    press(app, inp, "move_down")
    press(app, inp, "confirm")
    ok &= check("toggle Mostrar Hitbox persiste em save['settings']",
               app.save["settings"]["show_hitbox"] is True)
    press(app, inp, "back")
    ok &= check("ESC em SISTEMA -> MENU_MAIN", app.state == MENU_MAIN)

    # fluxo completo do assistente com o header novo (cards/step-dots)
    press(app, inp, "confirm")                      # JOGAR
    ok &= check("JOGAR -> MENU_MODE", app.state == MENU_MODE)
    press(app, inp, "confirm")                      # CLÁSSICO
    ok &= check("MODO -> MENU_DIFF (passo 1/5)", app.state == MENU_DIFF)
    press(app, inp, "confirm")                      # única destravada: FÁCIL
    ok &= check("DIFF -> MENU_BOSS (passo 2/5)", app.state == MENU_BOSS)
    press(app, inp, "confirm")                      # CLÁSSICO
    ok &= check("BOSS -> MENU_SKILL (passo 3/5)", app.state == MENU_SKILL)
    press(app, inp, "confirm")                      # NENHUMA
    ok &= check("SKILL -> MENU_WEAPON (passo 4/5)", app.state == MENU_WEAPON)
    press(app, inp, "confirm")                      # PADRÃO
    ok &= check("WEAPON -> MENU_MUT (passo 5/5)", app.state == MENU_MUT)
    for _ in range(8):          # pula o CLAUSTROFOBIA travado até '► COMEÇAR'
        if app.cursor == 6:
            break
        press(app, inp, "move_down")
    ok &= check("cursor chega no botao COMECAR pulando o mutador travado",
               app.cursor == 6)
    press(app, inp, "confirm")
    ok &= check("MUTADORES -> PLAYING", app.state == PLAYING and
               app.world is not None)

    raise SystemExit(0 if ok else 1)
