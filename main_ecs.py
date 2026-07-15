"""
BULLET HELL sobre a OuroborosEngine (port ECS).

Sem argumentos: abre o MENU completo (modo → dificuldade → boss →
habilidade → arma → mutadores), como no jogo original.

Com argumentos: pula direto para a partida (útil para testes/atalhos):
    python main_ecs.py --play [--mode ...] [--boss ...] [--weapon ...]
                              [--skill ...] [--mutators a,b] [--diff ...]

Controles: WASD move · ESPAÇO atira · SHIFT habilidade · 1-0 troca arma
           P variante+ arma · O variante+ skill · ESC menu
Menus:     W/S navegar · D/ENTER confirmar · A/ESC voltar
           ESPAÇO alterna variante+ (telas de habilidade/arma)
Fim de run: T joga de novo · R volta ao menu
"""
import argparse
import json
from pathlib import Path

import bullethell  # noqa: F401  — garante a engine no sys.path

SAVE_PATH = Path(__file__).parent / "save_ecs.json"


def _persist_totals(totals: dict) -> None:
    """I/O de save SÓ aqui, após o loop encerrar (Constituição §1)."""
    if totals["runs"] == 0:
        return
    save = {"runs": 0, "total_kills": 0, "total_deaths": 0, "total_graze": 0}
    if SAVE_PATH.exists():
        try:
            save.update(json.loads(SAVE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    save["runs"] += totals["runs"]
    save["total_kills"] += totals["kills"]
    save["total_deaths"] += totals["deaths"]
    save["total_graze"] += totals["graze"]
    SAVE_PATH.write_text(json.dumps(save, indent=2), encoding="utf-8")
    print(f"sessão: {totals['kills']} kills em {totals['runs']} runs — "
          f"totais: {save['total_kills']} kills / {save['total_deaths']} mortes"
          f" / {save['total_graze']} grazes em {save['runs']} runs")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--play", action="store_true",
                    help="pula o menu e inicia direto com as opções dadas")
    ap.add_argument("--mode", default="classic",
                    choices=["classic", "rush", "sins", "waves"])
    ap.add_argument("--diff", default="normal",
                    choices=["facil", "normal", "dificil"])
    ap.add_argument("--boss", default="classic",
                    choices=["classic", "timemage", "wall", "swarm", "twins",
                             "summoner", "omega", "pride", "gluttony", "sloth",
                             "envy", "greed", "lust", "wrath", "sin"])
    ap.add_argument("--weapon", default="padrao")
    ap.add_argument("--skill", default="none",
                    choices=["none", "dash", "parry", "focus", "emp", "blink",
                             "overclock", "shield", "timedil"])
    ap.add_argument("--mutators", default="")
    args = ap.parse_args()

    from ouroboros.adapters.pygame_backend.pygame_audio_engine import PygameAudioEngine
    from ouroboros.adapters.pygame_backend.pygame_input_provider import PygameInputProvider
    from ouroboros.adapters.pygame_backend.pygame_renderer import PygameRenderer
    from bullethell.loaders import DATA_DIR, load_all
    from bullethell.scenes import GameApp
    from bullethell.schemas import SCREEN_H, SCREEN_W

    data = load_all()
    renderer = PygameRenderer()
    renderer.initialize(SCREEN_W, SCREEN_H, "BULLET HELL — OuroborosEngine")
    input_provider = PygameInputProvider()
    input_provider.load_bindings(str(DATA_DIR / "input_bindings.json"))
    app = GameApp(renderer, input_provider, PygameAudioEngine(), data)

    app.sel["mode"] = args.mode
    app.sel["diff"] = args.diff
    app.sel["boss"] = args.boss
    app.sel["skill"] = args.skill.rstrip("+")
    app.sel["skill_plus"] = args.skill.endswith("+")
    app.sel["weapon"] = args.weapon.rstrip("+")
    app.sel["weapon_plus"] = args.weapon.endswith("+")
    app.sel["muts"] = set(m.strip() for m in args.mutators.split(",") if m.strip())
    if args.play:
        app.start_game()

    try:
        app.run()
    finally:
        _persist_totals(app.totals)
        renderer.shutdown()


if __name__ == "__main__":
    main()
