"""
BULLET HELL sobre a OuroborosEngine (port ECS).

Uso:
    python main_ecs.py [--boss classic|timemage|wall] [--weapon <nome>]
    (armas: padrao spread agulha teleguiado plasma carregado burst flak
     chakram satelite — sufixo + para a variante evoluída, ex.: agulha+)

Controles: WASD move · ESPAÇO atira (segurar/soltar tem mecânica por arma)
           SHIFT habilidade · 1-0 troca arma · P variante+ arma · O variante+ skill

Modos: --mode classic (boss escolhido em loop) · rush (7 bosses em
       sequência, +1 vida entre eles) · sins (os 8 pecados até o Selo)
       · waves (Wave Survival: 30 ondas, bosses nas 10/20/30)
"""
import argparse
import json
from pathlib import Path

import bullethell  # noqa: F401  — garante a engine no sys.path
from bullethell.composition import build_game

SAVE_PATH = Path(__file__).parent / "save_ecs.json"


def _persist_stats(world) -> None:
    """I/O de save SÓ aqui, após o GameLoop encerrar (Constituição §1)."""
    stats = world.get_pool("stats").active_view()
    player = world.get_pool("player").active_view()
    kills = int(stats["kills"][0]) if world.get_pool("stats").count else 0
    deaths = int(stats["deaths"][0]) if world.get_pool("stats").count else 0
    graze = int(player["graze"][0]) if world.get_pool("player").count else 0
    save = {"runs": 0, "total_kills": 0, "total_deaths": 0, "total_graze": 0}
    if SAVE_PATH.exists():
        try:
            save.update(json.loads(SAVE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    save["runs"] += 1
    save["total_kills"] += kills
    save["total_deaths"] += deaths
    save["total_graze"] += graze
    SAVE_PATH.write_text(json.dumps(save, indent=2), encoding="utf-8")
    print(f"run: {kills} kills, {deaths} mortes, {graze} grazes — "
          f"totais: {save['total_kills']}/{save['total_deaths']}/{save['total_graze']}"
          f" em {save['runs']} runs")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boss", default="classic",
                    choices=["classic", "timemage", "wall", "swarm", "twins",
                             "summoner", "omega", "pride", "gluttony", "sloth",
                             "envy", "greed", "lust", "wrath", "sin"])
    ap.add_argument("--weapon", default="padrao")
    ap.add_argument("--skill", default="none",
                    choices=["none", "dash", "parry", "focus", "emp", "blink",
                             "overclock", "shield", "timedil"])
    ap.add_argument("--mutators", default="",
                    help="lista separada por vírgula: predador,fantasma,"
                         "glass,claustro,abissal,horde,berserker")
    ap.add_argument("--mode", default="classic",
                    choices=["classic", "rush", "sins", "waves"])
    args = ap.parse_args()
    muts = frozenset(m.strip() for m in args.mutators.split(",") if m.strip())
    loop, world = build_game(boss_name=args.boss, weapon_name=args.weapon,
                             skill_name=args.skill, mutators=muts,
                             mode=args.mode)
    try:
        loop.run()
    finally:
        _persist_stats(world)


if __name__ == "__main__":
    main()
