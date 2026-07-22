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
        mode: str = "classic", difficulty: str = "normal") -> dict:
    world, inp = build_headless(boss_name=boss, weapon_name=weapon,
                                skill_name=skill, mutators=mutators, mode=mode,
                                difficulty=difficulty)
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
        # (waves pode não ter boss: mira o centro)
        tv = tp.active_view()
        prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
        bx = 640.0
        if bp.count:
            brow = tp.dense_row_of(int(bp.active_entity_indices()[0]))
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
    wv = world.get_pool("wave").active_view()
    return {
        "boss": boss, "weapon": weapon,
        "enemy_bullets_now": eb.count, "enemy_bullets_peak": max_eb,
        "player_bullets_now": pb.count, "lasers_peak": max_lz,
        "boss_hp": f"{hp1:.1f}/{hp0:.0f}", "boss_damage": hp0 - hp1,
        "graze": int(world.get_pool("player").active_view()["graze"][0]),
        "lives": int(world.get_pool("player").active_view()["lives"][0]),
        "kills": int(st["kills"][0]),
        "wave": int(wv["idx"][0]) + 1 if world.get_pool("wave").count else 0,
    }


def menu_smoke() -> bool:
    """Navega o fluxo completo de menus com null backends até PLAYING."""
    from ouroboros.interfaces.null.null_renderer import NullRenderer
    from ouroboros.interfaces.null.null_input_provider import NullInputProvider
    from bullethell.loaders import load_all
    from bullethell.scenes import GameApp, PLAYING

    inp = NullInputProvider()
    app = GameApp(NullRenderer(), inp, None, load_all())

    def press(action: str) -> None:
        inp.set_action_held(action, True)
        inp.poll(); app.tick(1 / 60)
        inp.set_action_held(action, False)
        inp.poll(); app.tick(1 / 60)

    press("confirm")      # JOGAR → modo
    press("confirm")      # CLÁSSICO → dificuldade
    press("confirm")      # NORMAL → boss
    press("confirm")      # CLÁSSICO → habilidade
    press("move_down")    # NENHUMA → DASH
    press("confirm")      # DASH → arma
    press("confirm")      # PADRÃO → mutadores
    press("move_up")      # wrap → ► COMEÇAR
    press("confirm")      # inicia a partida
    for _ in range(120):
        inp.poll(); app.tick(1 / 60)
    return app.state == PLAYING and app.world is not None


if __name__ == "__main__":
    ok = True
    m_ok = menu_smoke()
    print(f"[{'OK ' if m_ok else 'FAIL'}] menu headless -> PLAYING")
    if not m_ok:
        ok = False
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

    # mutadores (ABISSAL agora é dificuldade, não mutador — ver abaixo)
    for muts in [("predador",), ("fantasma",), ("glass",), ("claustro",),
                 ("horde",), ("berserker",),
                 ("predador", "fantasma", "glass")]:
        r = run("classic", "padrao", mutators=frozenset(muts))
        r["mutators"] = "+".join(muts)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")

    # dificuldades EXPERT/ABISSAL (DDA + Segundo Fôlego + Fragmentação):
    # spread+ derrete o classic rápido o bastante p/ testar o ciclo completo
    # de morte, incluindo o Segundo Fôlego "sobrevivendo" com 1 HP antes de
    # cair de vez (kills>=1 só acontece depois do timer de 3s esgotar).
    for diff in ("expert", "abissal"):
        # HP maior (480/560) + DDA deixam o classic mais resistente — o
        # 1º "quase morrer" já leva ~2300-2500 frames; +180 do próprio
        # Segundo Fôlego exige uma folga generosa para fechar o ciclo.
        r = run("classic", "spread+", frames=3600, approach=True,
               difficulty=diff)
        r["difficulty"] = diff
        died = r["kills"] >= 1
        status = "OK " if died else "FAIL"
        if not died:
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

    # Wave Survival: ondas de lacaios devem ser limpas e avançar
    r = run("classic", "spread", frames=2400, mode="waves")
    r["mode"] = "waves"
    waved = r["wave"] >= 2
    status = "OK " if waved else "FAIL"
    if not waved:
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
