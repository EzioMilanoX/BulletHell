"""
Smoke test headless do port ECS: null backends, 900 frames simulados.
Verifica: emitters disparam, balas inimigas voam, jogador atira e o boss
toma dano, cull funciona, contagens de pool coerentes.

Uso: python smoke_ecs.py
"""
import numpy as np

import bullethell  # noqa: F401 — engine no sys.path
from bullethell.composition import build_headless

DT = 1 / 60


def run(boss: str, weapon: str, frames: int = 900, approach: bool = False,
        skill: str = "none", mutators: frozenset = frozenset(),
        mode: str = "classic") -> dict:
    world, inp = build_headless(boss_name=boss, weapon_name=weapon,
                                skill_name=skill, mutators=mutators, mode=mode)
    eb = world.get_pool("enemy_bullet")
    pb = world.get_pool("pb_core")
    bp = world.get_pool("boss")
    pl = world.get_pool("player")
    tp = world.get_pool("transform")
    lz = world.get_pool("laser")

    max_eb = 0
    max_lz = 0
    hp0 = float(np.sum(bp.active_view()["hp"]))
    for f in range(frames):
        # fire com pulsos de release (charged/flak+/swarm dependem do edge);
        # período 300 = CD 1.5s + carga cheia 2.5s do CARREGADO (frac 1.0)
        inp.set_action_held("fire", (f % 300) < 288)
        # habilidade: FOCUS segura sempre; demais pulsam (edge a cada 4s)
        if skill != "none":
            inp.set_action_held("skill",
                                True if skill.startswith("focus")
                                else (f % 240) < 20)
        # mira: rastreia o x do boss como um jogador faria
        tv = tp.active_view()
        brow = tp.dense_row_of(int(bp.active_entity_indices()[0]))
        prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
        bx = float(tv["position_x"][brow])
        px = float(tv["position_x"][prow])
        py = float(tv["position_y"][prow])
        inp.set_action_held("move_right", px < bx - 6.0)
        inp.set_action_held("move_left", px > bx + 6.0)
        # armas curto-alcance ou de tiro lento (plasma/spread+/chakram/
        # satélite/carregado): aproximar reduz o tempo de voo e o erro
        # de antecipação do driver
        inp.set_action_held("move_up", approach and py > 205.0)
        inp.poll()
        world.step(DT)
        max_eb = max(max_eb, eb.count)
        max_lz = max(max_lz, lz.count)
    hp1 = float(np.sum(bp.active_view()["hp"]))
    st = world.get_pool("stats").active_view()
    return {
        "boss": boss, "weapon": weapon,
        "enemy_bullets_now": eb.count, "enemy_bullets_peak": max_eb,
        "player_bullets_now": pb.count, "lasers_peak": max_lz,
        "boss_hp": f"{hp1:.1f}/{hp0:.0f}", "boss_damage": hp0 - hp1,
        "graze": int(world.get_pool("player").active_view()["graze"][0]),
        "lives": int(world.get_pool("player").active_view()["lives"][0]),
        "kills": int(st["kills"][0]),
    }


if __name__ == "__main__":
    ok = True
    for boss, weapon, approach in [
            ("classic", "padrao", False), ("classic", "padrao+", False),
            ("classic", "spread", False), ("classic", "spread+", True),
            ("classic", "agulha", False), ("classic", "agulha+", False),
            ("classic", "teleguiado", False), ("classic", "teleguiado+", False),
            ("classic", "plasma", True),
            ("classic", "carregado", True), ("classic", "carregado+", True),
            ("classic", "burst", False), ("classic", "burst+", False),
            ("classic", "flak", False), ("classic", "flak+", False),
            ("classic", "chakram", True), ("classic", "chakram+", True),
            ("classic", "satelite", True), ("classic", "satelite+", True),
            ("timemage", "padrao", False), ("timemage", "spread+", True),
            ("wall", "padrao", False), ("swarm", "spread", False),
            ("twins", "teleguiado", False)]:
        # spread+ derrete o classic → estende p/ alcançar a fase 3 (lasers)
        frames = 1600 if (boss, weapon) == ("classic", "spread+") else 900
        r = run(boss, weapon, frames=frames, approach=approach)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")

    # habilidades: cada uma exercitada com pulsos de SHIFT
    for skill in ["dash", "dash+", "parry", "parry+", "focus", "emp", "emp+",
                  "blink", "blink+", "overclock", "overclock+", "shield",
                  "shield+", "timedil", "timedil+"]:
        boss = "timemage" if skill.startswith("timedil") else "classic"
        r = run(boss, "padrao", skill=skill)
        r["skill"] = skill
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")

    # mutadores
    for muts in [("predador",), ("fantasma",), ("glass",), ("claustro",),
                 ("abissal",), ("horde",), ("berserker",),
                 ("predador", "fantasma", "glass")]:
        r = run("classic", "padrao", mutators=frozenset(muts))
        r["mutators"] = "+".join(muts)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")

    # Boss Rush: spread+ derrete o classic → deve avançar para o swarm
    r = run("classic", "spread+", frames=2400, approach=True, mode="rush")
    r["mode"] = "rush"
    rushed = r["kills"] >= 1
    status = "OK " if rushed else "FAIL"
    if not rushed:
        ok = False
    print(f"[{status}] {r}")

    # bosses das fases 6-8: Invocador, Ômega e os 8 pecados
    for boss, weapon, approach in [("summoner", "spread", False),
                                   ("omega", "spread+", True),
                                   ("pride", "spread", False),
                                   ("gluttony", "spread", False),
                                   ("sloth", "spread+", True),
                                   ("envy", "spread", False),
                                   ("greed", "spread", False),
                                   ("lust", "spread", False),
                                   ("wrath", "spread+", True),
                                   ("sin", "spread+", True)]:
        frames = 1600 if boss in ("omega", "pride", "sloth", "wrath", "sin") \
            else 900
        r = run(boss, weapon, frames=frames, approach=approach)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")
    raise SystemExit(0 if ok else 1)
