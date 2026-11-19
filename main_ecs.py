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
import sys
from pathlib import Path

import bullethell  # noqa: F401  — garante a engine no sys.path
from ouroboros.bootstrap.save_file import SaveFile

# Path(__file__).parent aponta pra uma pasta temp nova a cada execução sob
# PyInstaller --onefile (sys._MEIPASS muda por processo) — usar a pasta do
# .exe quando congelado, senão o save nunca persiste entre sessões.
_APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) \
    else Path(__file__).parent
SAVE_PATH = _APP_DIR / "save_ecs.json"
BACKUP_PATH = _APP_DIR / "save_ecs.json.bak"


def _load_save() -> dict:
    """Carrega o save no boot (fora do loop de gameplay). Campos de gating
    (PARITY_PLAN.md P0-1): dificuldade/skills/mutador/boss/variantes '+'
    começam bloqueados como no legado — só `unlocked_skills` já traz
    NENHUMA+DASH, o resto se conquista jogando."""
    save = {"runs": 0, "total_kills": 0, "total_deaths": 0,
            "total_graze": 0, "total_parries": 0, "achievements": [],
            "highest_cleared_diff": 0, "sins_rush_cleared": False,
            "decalogue_rush_cleared": False,
            "unlocked_skills": ["none", "dash"],
            "unlocked_mutators": [], "omega_unlocked": False,
            "skill_plus_unlocked": [], "weapon_plus_unlocked": [],
            "best_time_dificil": 0.0,
            "settings": {"screen_shake": True, "show_hitbox": False, "fullscreen": False}}
    # save principal, senão o .bak (gravado pelo _persist() anterior) antes
    # de aceitar os defaults. SaveFile.read() da engine nunca levanta:
    # ausente, JSON corrompido ou raiz que não é objeto viram {} — e {}
    # aqui significa "tenta o próximo".
    for path in (SAVE_PATH, BACKUP_PATH):
        loaded = SaveFile(path).read()
        if loaded:
            save.update(loaded)
            break
    return save


def _apply_boot_settings(renderer, save: dict) -> None:
    """Reaplica no boot o que SISTEMA guardou e precisa do renderer já
    inicializado — hoje só a Tela Cheia. Só troca o modo de tela se o save
    pedir (modo janela é o que `initialize()` já deixou pronto, nenhuma
    troca extra à toa). Se a troca falhar no hardware de quem joga, volta
    pra janela e desliga o toggle no save em vez de derrubar o boot."""
    settings = save.setdefault("settings", {})
    if not settings.get("fullscreen", False):
        return
    try:
        renderer.set_fullscreen(True)
    except Exception:
        settings["fullscreen"] = False


def _persist(save: dict, totals: dict, achieved: set) -> None:
    """I/O de save SÓ aqui, após o loop encerrar (Constituição §1)."""
    save["runs"] += totals["runs"]
    save["total_kills"] += totals["kills"]
    save["total_deaths"] += totals["deaths"]
    save["total_graze"] += totals["graze"]
    save["total_parries"] += totals.get("parries", 0)
    save["achievements"] = sorted(achieved)
    # backup de 1 geração antes de sobrescrever — só de um save que ainda
    # lê como válido: copiar um principal corrompido por cima do .bak
    # destruiria justamente a cópia boa que o _load_save() procuraria.
    previous = SaveFile(SAVE_PATH).read()
    if previous:
        SaveFile(BACKUP_PATH).write(previous)
    # escrita atômica (SaveFile: .tmp ao lado + os.replace) — um
    # desligamento no meio deixa o save anterior intacto, nunca meio JSON.
    # Falha de I/O (pasta sem permissão, disco cheio) devolve False e
    # segue: custa o progresso da sessão, não derruba o jogo ao sair.
    SaveFile(SAVE_PATH).write(save)
    if totals["runs"]:
        print(f"sessão: {totals['kills']} kills em {totals['runs']} runs — "
              f"totais: {save['total_kills']} kills / "
              f"{save['total_deaths']} mortes / {save['total_graze']} grazes"
              f" · conquistas: {len(save['achievements'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--play", action="store_true",
                    help="pula o menu e inicia direto com as opções dadas")
    ap.add_argument("--mode", default="classic",
                    choices=["classic", "rush", "sins", "waves", "decalogo"])
    ap.add_argument("--diff", default="normal",
                    choices=["facil", "normal", "dificil", "expert", "abissal"])
    ap.add_argument("--boss", default="classic",
                    choices=["classic", "timemage", "wall", "swarm", "twins",
                             "summoner", "omega", "pride", "gluttony", "sloth",
                             "envy", "greed", "lust", "wrath", "sin",
                             "monolith", "icon", "lineage", "truth",
                             "silence", "sabbath", "ascetic", "purity",
                             "restitution", "mercy", "decalogue", "bastion"])
    ap.add_argument("--weapon", default="padrao")
    ap.add_argument("--skill", default="none",
                    choices=["none", "dash", "parry", "focus", "emp", "blink",
                             "overclock", "shield", "timedil"])
    ap.add_argument("--mutators", default="")
    args = ap.parse_args()

    from ouroboros.adapters.pygame_backend.pygame_audio_engine import PygameAudioEngine
    from ouroboros.adapters.pygame_backend.pygame_input_provider import PygameInputProvider
    from ouroboros.adapters.pygame_backend.pygame_renderer import PygameRenderer
    from ouroboros.bootstrap.game_loop import GameLoop
    from ouroboros.core.memory.memory_manager import MemoryManager
    from ouroboros.core.world import World
    from bullethell.loaders import DATA_DIR, load_all
    from bullethell.scenes import GameApp, MainMenuScene
    from bullethell.schemas import SCREEN_H, SCREEN_W

    data = load_all()
    save = _load_save()
    renderer = PygameRenderer()
    renderer.initialize(SCREEN_W, SCREEN_H, "BULLET HELL — OuroborosEngine")
    _apply_boot_settings(renderer, save)
    input_provider = PygameInputProvider()
    input_provider.load_bindings(str(DATA_DIR / "input_bindings.json"))
    audio = PygameAudioEngine()
    app = GameApp(renderer, input_provider, audio, data, save_data=save)

    # GameLoop (ROADMAP M8c) e quem possui o loop principal agora, nao mais
    # GameApp.run(). Precisa de um World logo de cara -- este placeholder
    # nunca e de fato atualizado/desenhado: reset_scenes() troca a cena base
    # por MainMenuScene ANTES do primeiro frame (game_loop.run() abaixo).
    # start_game()/_start_replay() trocam por um World de verdade depois,
    # via replace_world().
    placeholder_world = World(MemoryManager(entity_capacity=1))
    game_loop = GameLoop(placeholder_world, renderer, input_provider, audio)
    app.game_loop = game_loop
    game_loop.reset_scenes(MainMenuScene(app))

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
        game_loop.run()
    finally:
        _persist(save, app.totals, app.achieved)
        renderer.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from datetime import datetime
        with open(_APP_DIR / "crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now().isoformat(timespec='seconds')} ===\n")
            f.write(traceback.format_exc())
        raise
