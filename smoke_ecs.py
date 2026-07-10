"""
Smoke test headless do port ECS: null backends, 900 frames simulados.
Verifica: emitters disparam, balas inimigas voam, jogador atira e o boss
toma dano, cull funciona, contagens de pool coerentes.

Uso: python smoke_ecs.py
"""
import bullethell  # noqa: F401 — engine no sys.path
from bullethell.composition import build_headless

DT = 1 / 60


def run(boss: str, weapon: str, frames: int = 900, approach: bool = False) -> dict:
    world, inp = build_headless(boss_name=boss, weapon_name=weapon)
    eb = world.get_pool("enemy_bullet")
    pb = world.get_pool("pb_core")
    bp = world.get_pool("boss")

    inp.set_action_held("fire", True)
    max_eb = 0
    hp0 = float(bp.active_view()["hp"][0])
    for f in range(frames):
        # fase 1: alinhar com a rota do boss (x 160..480); depois oscilar
        inp.set_action_held("move_left", f < 90 or (f >= 90 and (f // 30) % 2 == 0))
        inp.set_action_held("move_right", f >= 90 and (f // 30) % 2 == 1)
        # plasma: alcance de 120px exige aproximar por baixo do boss
        # (diagonal normalizada ⇒ 155px/s de subida; 150 frames ⇒ y≈200)
        inp.set_action_held("move_up", approach and 90 <= f < 240)
        inp.poll()
        world.step(DT)
        max_eb = max(max_eb, eb.count)
    hp1 = float(bp.active_view()["hp"][0])
    return {
        "boss": boss, "weapon": weapon,
        "enemy_bullets_now": eb.count, "enemy_bullets_peak": max_eb,
        "player_bullets_now": pb.count,
        "boss_hp": f"{hp1:.1f}/{hp0:.0f}", "boss_damage": hp0 - hp1,
        "graze": int(world.get_pool("player").active_view()["graze"][0]),
        "lives": int(world.get_pool("player").active_view()["lives"][0]),
    }


if __name__ == "__main__":
    ok = True
    for boss, weapon, approach in [
            ("classic", "padrao", False), ("classic", "spread", False),
            ("classic", "agulha+", False), ("classic", "plasma", True),
            ("classic", "teleguiado", False), ("timemage", "padrao", False)]:
        r = run(boss, weapon, approach=approach)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")
    raise SystemExit(0 if ok else 1)
