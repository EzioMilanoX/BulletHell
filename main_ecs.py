"""
BULLET HELL sobre a OuroborosEngine (port ECS).

Uso:
    python main_ecs.py [--boss classic|timemage] [--weapon padrao|spread|agulha|teleguiado|plasma]

Controles: WASD move · ESPAÇO atira · 1-5 troca arma · P alterna variante +
"""
import argparse

import bullethell  # noqa: F401  — garante a engine no sys.path
from bullethell.composition import build_game


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boss", default="classic", choices=["classic", "timemage", "wall"])
    ap.add_argument("--weapon", default="padrao")
    args = ap.parse_args()
    build_game(boss_name=args.boss, weapon_name=args.weapon).run()


if __name__ == "__main__":
    main()
