"""
BULLET HELL sobre a OuroborosEngine (port ECS).

Uso:
    python main_ecs.py [--boss classic|timemage|wall] [--weapon <nome>]
    (armas: padrao spread agulha teleguiado plasma carregado burst flak
     chakram satelite — sufixo + para a variante evoluída, ex.: agulha+)

Controles: WASD move · ESPAÇO atira (segurar/soltar tem mecânica por arma)
           SHIFT habilidade · 1-0 troca arma · P variante+ arma · O variante+ skill
"""
import argparse

import bullethell  # noqa: F401  — garante a engine no sys.path
from bullethell.composition import build_game


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boss", default="classic",
                    choices=["classic", "timemage", "wall", "swarm", "twins",
                             "summoner", "omega"])
    ap.add_argument("--weapon", default="padrao")
    ap.add_argument("--skill", default="none",
                    choices=["none", "dash", "parry", "focus", "emp", "blink",
                             "overclock", "shield", "timedil"])
    ap.add_argument("--mutators", default="",
                    help="lista separada por vírgula: predador,fantasma,"
                         "glass,claustro,abissal,horde,berserker")
    args = ap.parse_args()
    muts = frozenset(m.strip() for m in args.mutators.split(",") if m.strip())
    build_game(boss_name=args.boss, weapon_name=args.weapon,
               skill_name=args.skill, mutators=muts).run()


if __name__ == "__main__":
    main()
