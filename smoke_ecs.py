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

    # Decálogo Rush: spread+ derrete o monolith (1º estágio, ordem canônica
    # dos mandamentos) → deve avançar pro icon (2º estágio)
    r = run("classic", "spread+", frames=2400, approach=True, mode="decalogo")
    r["mode"] = "decalogo"
    rushed = r["kills"] >= 1
    status = "OK " if rushed else "FAIL"
    if not rushed:
        ok = False
    print(f"[{status}] {r}")

    # SINS RUSH: HP escala +15%/stage (legado, spec menus §11) — o
    # 2º boss da fila deve ter mais HP máximo que o 1º só pelo estágio
    from bullethell.composition import build_headless as _bh
    from bullethell.game_systems import SINS_RUSH_HP_SCALE as _SC
    w_sins, inp_sins = _bh(mode="sins")
    bp_sins = w_sins.get_pool("boss")
    hp0 = float(bp_sins.active_view()["max_hp"][0])
    # precisa estar na ÚLTIMA fase para hp<=0 valer como morte de verdade
    # (senão BossPhaseSystem só pina em 1.0 e avança de fase)
    from bullethell.loaders import load_all as _la
    n_phases = len(_la().bosses[int(bp_sins.active_view()["boss_id"][0])].phases)
    bp_sins.active_view()["phase_idx"][0] = n_phases - 1
    bp_sins.active_view()["hp"][0] = 0.0        # força a morte do 1º boss
    inp_sins.poll(); w_sins.step(DT)
    hp1 = float(bp_sins.active_view()["max_hp"][0])
    expected = hp0 * _SC
    scaled = abs(hp1 - expected) < 1e-3
    status = "OK " if scaled else "FAIL"
    if not scaled:
        ok = False
    print(f"[{status}] SINS RUSH hp_scale: boss0={hp0:.0f} -> "
         f"boss1={hp1:.0f} (esperado {expected:.0f}, ×{_SC} por estágio)")

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

    # Decálogo #1 — Monolith: 4 pilares-isca (nunca dão dano, revidam ao
    # serem atingidos), fase 1 orbita rápido. Danificável via mira ingênua
    # (aim "center") já que a raiz também tem hitbox — diferente do Icon.
    r = run("monolith", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Decálogo #2 — Icon: propositalmente FORA do loop genérico acima — a
    # mira ingênua (mira o x da raiz) nunca acerta os clones, que ficam
    # deslocados; "boss_damage=0" aqui seria o resultado ESPERADO da
    # mecânica (é um boss de "ache o alvo certo"), não um bug, então
    # testamos os comportamentos específicos diretamente via pool.
    from bullethell.composition import build_headless as _bh2
    from bullethell.game_systems import spawn_player_bullet as _spb
    from bullethell.game_systems import PART_FAKE as _PF, PART_REAL as _PR

    w_ic, inp_ic = _bh2(boss_name="icon", weapon_name="padrao")
    bp_ic = w_ic.get_pool("boss"); pt_ic = w_ic.get_pool("part")
    tp_ic = w_ic.get_pool("transform"); eb_ic = w_ic.get_pool("enemy_bullet")
    inp_ic.poll(); w_ic.step(DT)          # 1 frame: icon_hide liga o invuln
    ok_icon_hide = int(bp_ic.active_view()["invuln"][0]) == 1
    print(f"[{'OK ' if ok_icon_hide else 'FAIL'}] icon: invuln=1 na fase 0 "
         f"(gimmick icon_hide)")
    if not ok_icon_hide:
        ok = False

    part_idxs = pt_ic.active_entity_indices()
    kinds_ic = pt_ic.active_view()["kind"]
    fake_k = next(k for k in range(pt_ic.count) if int(kinds_ic[k]) == _PF)
    real_k = next(k for k in range(pt_ic.count) if int(kinds_ic[k]) == _PR)

    def _hit_part(k):
        prow_t = tp_ic.dense_row_of(int(part_idxs[k]))
        x = float(tp_ic.active_view()["position_x"][prow_t])
        y = float(tp_ic.active_view()["position_y"][prow_t])
        hp_before = float(bp_ic.active_view()["hp"][0])
        eb_before = eb_ic.count
        _spb(w_ic, w_ic, "pb_padrao", x, y, 0.0, 0.0, 5.0, 3.0,
            color=(255, 255, 255))
        inp_ic.poll(); w_ic.step(DT)
        return hp_before, float(bp_ic.active_view()["hp"][0]), eb_before, eb_ic.count

    hp0, hp1, eb0, eb1 = _hit_part(fake_k)
    fake_ok = abs(hp1 - hp0) < 1e-6 and (eb1 - eb0) >= 14
    print(f"[{'OK ' if fake_ok else 'FAIL'}] icon: clone falso atingido -> "
         f"hp inalterado ({hp0:.0f}->{hp1:.0f}) + burst de {eb1 - eb0} balas")
    if not fake_ok:
        ok = False

    hp0, hp1, eb0, eb1 = _hit_part(real_k)
    real_ok = hp1 < hp0 - 1e-6
    print(f"[{'OK ' if real_ok else 'FAIL'}] icon: clone real atingido -> "
         f"hp cai ({hp0:.0f}->{hp1:.0f})")
    if not real_ok:
        ok = False

    # força a fase 2 (33%) e confere a revelação: partes viram guard, raiz
    # perde o invuln (via fallback normal — gimmick vazio nessa fase)
    bp_ic.active_view()["hp"][0] = bp_ic.active_view()["max_hp"][0] * 0.32
    for _ in range(3):                    # deixa o phase_idx cascatear 0->1->2
        inp_ic.poll(); w_ic.step(DT)
    phase2_ok = (int(bp_ic.active_view()["phase_idx"][0]) == 2
                and int(bp_ic.active_view()["invuln"][0]) == 0
                and all(int(pt_ic.active_view()["kind"][k]) == 4
                        for k in range(pt_ic.count)))
    print(f"[{'OK ' if phase2_ok else 'FAIL'}] icon: fase 2 revela a raiz "
         f"(invuln=0) e vira guard nos 4 cantos")
    if not phase2_ok:
        ok = False

    # Decálogo #5 — Lineage: Sol+Lua danificáveis via mira ingênua (raízes
    # normais, sem invuln/parte especial) — entram no loop genérico.
    r = run("lineage", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Decálogo #7 — Truth: espiral 80% fantasma, mas a raiz em si nunca é
    # invulnerável — também entra no loop genérico.
    r = run("truth", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Lineage: enrage dispara só no lado com MAIS hp quando a diferença
    # passa de 15%, e desliga quando reequilibra
    w_ln, inp_ln = _bh2(boss_name="lineage", weapon_name="padrao")
    bp_ln = w_ln.get_pool("boss")
    bv_ln = bp_ln.active_view()
    bv_ln["hp"][0] = bv_ln["max_hp"][0] * 1.0
    bv_ln["hp"][1] = bv_ln["max_hp"][1] * 0.80        # Δ = 20% > 15%
    inp_ln.poll(); w_ln.step(DT)
    enrage_ok = (abs(float(bv_ln["enrage_mult"][0]) - 2.0) < 1e-6
                and abs(float(bv_ln["enrage_mult"][1]) - 1.0) < 1e-6)
    print(f"[{'OK ' if enrage_ok else 'FAIL'}] lineage: diff hp>15% -> so o "
         f"lado com mais hp enrage (sol={bv_ln['enrage_mult'][0]:.1f}, "
         f"lua={bv_ln['enrage_mult'][1]:.1f})")
    if not enrage_ok:
        ok = False
    bv_ln["hp"][1] = bv_ln["max_hp"][1] * 0.95         # reequilibra
    inp_ln.poll(); w_ln.step(DT)
    rebalance_ok = abs(float(bv_ln["enrage_mult"][0]) - 1.0) < 1e-6
    print(f"[{'OK ' if rebalance_ok else 'FAIL'}] lineage: reequilibrado -> "
         f"enrage volta a 1.0 (sol={bv_ln['enrage_mult'][0]:.1f})")
    if not rebalance_ok:
        ok = False

    # Truth: proporção fantasma/real ~80/20 e revelação por raio no jogador
    from bullethell.schemas import CONTACT_ALWAYS, CONTACT_NEVER
    w_tr, inp_tr = _bh2(boss_name="truth", weapon_name="padrao")
    eb_tr = w_tr.get_pool("enemy_bullet")
    for _ in range(30):
        inp_tr.poll(); w_tr.step(DT)
    n_ghost = int((eb_tr.active_view()["contact"][:eb_tr.count] == CONTACT_NEVER).sum())
    n_real = int((eb_tr.active_view()["contact"][:eb_tr.count] == CONTACT_ALWAYS).sum())
    total = n_ghost + n_real
    ratio = n_ghost / total if total else 0.0
    ratio_ok = total > 0 and 0.70 <= ratio <= 0.90
    print(f"[{'OK ' if ratio_ok else 'FAIL'}] truth: ~80% fantasma "
         f"(ghost={n_ghost} real={n_real} ratio={ratio:.2f})")
    if not ratio_ok:
        ok = False

    tp_tr = w_tr.get_pool("transform"); sp_tr = w_tr.get_pool("sprite")
    idxs_tr = eb_tr.active_entity_indices()
    ghost_rows = [k for k in range(eb_tr.count)
                  if eb_tr.active_view()["contact"][k] == CONTACT_NEVER]
    g_idx = int(idxs_tr[ghost_rows[0]])
    g_trow = tp_tr.dense_row_of(g_idx)
    gx = float(tp_tr.active_view()["position_x"][g_trow])
    gy = float(tp_tr.active_view()["position_y"][g_trow])
    pl_tr = w_tr.get_pool("player")
    p_trow = tp_tr.dense_row_of(int(pl_tr.active_entity_indices()[0]))
    tp_tr.active_view()["position_x"][p_trow] = gx
    tp_tr.active_view()["position_y"][p_trow] = gy
    inp_tr.poll(); w_tr.step(DT)
    g_row_after = eb_tr.dense_row_of(g_idx)
    reveal_ok = (g_row_after >= 0
                and int(sp_tr.active_view()["tint_a"][sp_tr.dense_row_of(g_idx)]) == 255)
    print(f"[{'OK ' if reveal_ok else 'FAIL'}] truth: fantasma perto do "
         f"jogador revela (tint_a->255)")
    if not reveal_ok:
        ok = False

    # Decálogo #3 — Silence e #4 — Sabbath: raízes normais, sem parte
    # especial escondendo nada — entram no loop genérico.
    for boss in ("silence", "sabbath"):
        r = run(boss, "padrao", frames=1600, approach=False)
        spawned = r["enemy_bullets_peak"] > 0
        damaged = r["boss_damage"] > 0
        status = "OK " if (spawned and damaged) else "FAIL"
        if not (spawned and damaged):
            ok = False
        print(f"[{status}] {r}")

    # Silence fase 0: skill travada + tentativa dispara o bolt inescapável
    w_sl, inp_sl = _bh2(boss_name="silence", weapon_name="padrao", skill_name="dash")
    pl_sl = w_sl.get_pool("player")
    prow_sl = pl_sl.dense_row_of(int(pl_sl.active_entity_indices()[0]))
    inp_sl.poll(); w_sl.step(DT)
    locked_ok = float(pl_sl.active_view()["skill_locked_t"][prow_sl]) > 0.0
    print(f"[{'OK ' if locked_ok else 'FAIL'}] silence: skill_locked_t>0 na fase 0")
    if not locked_ok:
        ok = False

    eb_sl = w_sl.get_pool("enemy_bullet")
    eb0 = eb_sl.count
    inp_sl.set_action_held("skill", True)
    inp_sl.poll(); w_sl.step(DT)
    bolt_ok = eb_sl.count > eb0
    skill_t = float(pl_sl.active_view()["skill_t"][prow_sl])
    print(f"[{'OK ' if bolt_ok and skill_t <= 0.0 else 'FAIL'}] silence: "
         f"tentar skill travada dispara o bolt (eb {eb0}->{eb_sl.count}) "
         f"e a skill nao ativa de verdade (skill_t={skill_t})")
    if not (bolt_ok and skill_t <= 0.0):
        ok = False

    # Silence fase 1: arma silenciada periodicamente (2s a cada 5s)
    w_sl2, inp_sl2 = _bh2(boss_name="silence", weapon_name="padrao")
    bp_sl2 = w_sl2.get_pool("boss")
    bp_sl2.active_view()["hp"][0] = bp_sl2.active_view()["max_hp"][0] * 0.4
    pl_sl2 = w_sl2.get_pool("player")
    prow_sl2 = pl_sl2.dense_row_of(int(pl_sl2.active_entity_indices()[0]))
    inp_sl2.set_action_held("fire", True)
    found_lock = False
    for _ in range(360):
        inp_sl2.poll(); w_sl2.step(DT)
        if float(pl_sl2.active_view()["fire_locked_t"][prow_sl2]) > 0.0:
            found_lock = True
            break
    print(f"[{'OK ' if found_lock else 'FAIL'}] silence: fase 1 silencia a "
         f"arma em algum momento do ciclo de 5s")
    if not found_lock:
        ok = False

    # Sabbath: mover/atirar na janela de descanso tira vida; parado nao
    w_sb, inp_sb = _bh2(boss_name="sabbath", weapon_name="padrao")
    bp_sb = w_sb.get_pool("boss")
    bv_sb = bp_sb.active_view()
    bv_sb["hp"][0] = bv_sb["max_hp"][0] * 0.4
    pl_sb = w_sb.get_pool("player")
    prow_sb = pl_sb.dense_row_of(int(pl_sb.active_entity_indices()[0]))
    lives0 = int(pl_sb.active_view()["lives"][prow_sb])
    inp_sb.poll(); w_sb.step(DT)
    for _ in range(300):
        inp_sb.poll(); w_sb.step(DT)
        if float(bv_sb["aux_angle"][0]) % 4.0 < 1.0:
            break
    inp_sb.set_action_held("move_right", True)
    inp_sb.poll(); w_sb.step(DT)
    lives1 = int(pl_sb.active_view()["lives"][prow_sb])
    punish_ok = lives1 < lives0
    print(f"[{'OK ' if punish_ok else 'FAIL'}] sabbath: mover na janela de "
         f"descanso tira vida ({lives0}->{lives1})")
    if not punish_ok:
        ok = False

    # Decálogo #6 — Ascetic: raiz normal, sem invuln escondendo nada.
    r = run("ascetic", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Ascetic: anel assimétrico cercando um vazio -> gravity liga e puxa o
    # jogador; bala ocupando o "buraco" -> gravity desliga
    from bullethell.game_systems import spawn_enemy_bullet as _seb
    import math as _math

    w_as, inp_as = _bh2(boss_name="ascetic", weapon_name="padrao")
    pl_as = w_as.get_pool("player"); tp_as = w_as.get_pool("transform")
    prow_as = tp_as.dense_row_of(int(pl_as.active_entity_indices()[0]))
    px_as = float(tp_as.active_view()["position_x"][prow_as])
    py_as = float(tp_as.active_view()["position_y"][prow_as])
    cx_as, cy_as = px_as + 15.0, py_as    # centro do anel deslocado (assimétrico)
    for j in range(8):
        a = j * (2 * _math.pi / 8)
        _seb(w_as, w_as, cx_as + _math.cos(a) * 100.0,
            cy_as + _math.sin(a) * 100.0, 0.0, 0.0, color=0)
    inp_as.poll(); w_as.step(DT)
    eb_as = w_as.get_pool("enemy_bullet")
    n_pull = int((eb_as.active_view()["gravity"][:eb_as.count] > 0).sum())
    trap_on_ok = n_pull >= 6
    print(f"[{'OK ' if trap_on_ok else 'FAIL'}] ascetic: anel cercando vazio "
         f"-> gravity liga ({n_pull}/{eb_as.count})")
    if not trap_on_ok:
        ok = False

    w_as2, inp_as2 = _bh2(boss_name="ascetic", weapon_name="padrao")
    pl_as2 = w_as2.get_pool("player"); tp_as2 = w_as2.get_pool("transform")
    prow_as2 = tp_as2.dense_row_of(int(pl_as2.active_entity_indices()[0]))
    px_as2 = float(tp_as2.active_view()["position_x"][prow_as2])
    py_as2 = float(tp_as2.active_view()["position_y"][prow_as2])
    for j in range(8):
        a = j * (2 * _math.pi / 8)
        _seb(w_as2, w_as2, px_as2 + _math.cos(a) * 100.0,
            py_as2 + _math.sin(a) * 100.0, 0.0, 0.0, color=0)
    _seb(w_as2, w_as2, px_as2, py_as2, 0.0, 0.0, color=0)  # ocupa o "buraco"
    inp_as2.poll(); w_as2.step(DT)
    eb_as2 = w_as2.get_pool("enemy_bullet")
    n_pull2 = int((eb_as2.active_view()["gravity"][:eb_as2.count] > 0).sum())
    trap_off_ok = n_pull2 == 0
    print(f"[{'OK ' if trap_off_ok else 'FAIL'}] ascetic: bala ocupando o "
         f"'buraco' -> gravity desligado ({n_pull2}/{eb_as2.count})")
    if not trap_off_ok:
        ok = False

    # Ascetic fase 1 (Renúncia): corações falsos caem periodicamente
    from bullethell.game_systems import PICKUP_KIND_ASCETIC as _PKA

    w_ar, inp_ar = _bh2(boss_name="ascetic", weapon_name="padrao")
    bp_ar = w_ar.get_pool("boss"); bv_ar = bp_ar.active_view()
    bv_ar["hp"][0] = bv_ar["max_hp"][0] * 0.4     # forca fase 1
    pu_ar = w_ar.get_pool("pickup")
    max_pu_ar = 0
    for _ in range(200):
        inp_ar.poll(); w_ar.step(DT)
        max_pu_ar = max(max_pu_ar, pu_ar.count)
    drop_ok_ar = max_pu_ar > 0 and int(bv_ar["phase_idx"][0]) == 1
    print(f"[{'OK ' if drop_ok_ar else 'FAIL'}] ascetic: fase 1 (Renuncia) "
         f"derruba coracoes falsos (pico={max_pu_ar})")
    if not drop_ok_ar:
        ok = False

    # Ascetic: coletar um coração falso congela o jogador (mesmo com input
    # segurado) e dispara uma cruz 4-way
    from bullethell.game_systems import spawn_pickup as _spu3

    w_af, inp_af = _bh2(boss_name="ascetic", weapon_name="padrao")
    bp_af = w_af.get_pool("boss"); bv_af = bp_af.active_view()
    bv_af["hp"][0] = bv_af["max_hp"][0] * 0.4
    inp_af.poll(); w_af.step(DT)
    pl_af = w_af.get_pool("player"); tp_af = w_af.get_pool("transform")
    pidx_af = int(pl_af.active_entity_indices()[0])
    prow_af = pl_af.dense_row_of(pidx_af); trow_af = tp_af.dense_row_of(pidx_af)
    px_af = float(tp_af.active_view()["position_x"][trow_af])
    py_af = float(tp_af.active_view()["position_y"][trow_af])
    eb_af = w_af.get_pool("enemy_bullet")
    eb0_af = eb_af.count
    _spu3(w_af, w_af, px_af, py_af, kind=_PKA)
    inp_af.set_action_held("move_right", True)
    inp_af.poll(); w_af.step(DT)               # coleta + spawna a cruz
    cross_ok = eb_af.count >= eb0_af + 4
    inp_af.poll(); w_af.step(DT)               # freeze_t reafirmado -> aplica
    vv_af = w_af.get_pool("velocity").active_view()
    vrow_af = w_af.get_pool("velocity").dense_row_of(pidx_af)
    frozen_ok = float(vv_af["linear_x"][vrow_af]) == 0.0
    freeze_ok = cross_ok and frozen_ok
    print(f"[{'OK ' if freeze_ok else 'FAIL'}] ascetic: coletar coracao "
         f"congela (vx={float(vv_af['linear_x'][vrow_af]):.1f} com move_right "
         f"segurado) e dispara cruz 4-way (balas {eb0_af}->{eb_af.count})")
    if not freeze_ok:
        ok = False

    # Decálogo #6b — Purity: raiz normal, sem invuln escondendo nada.
    r = run("purity", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Purity: zona errada tira 2 vidas; zona certa tira só 1
    from bullethell.schemas import SCREEN_W as _SW

    def _hit_zone(zone_x_frac: float, bullet_color: int):
        w_p, inp_p = _bh2(boss_name="purity", weapon_name="padrao")
        pl_p = w_p.get_pool("player"); tp_p = w_p.get_pool("transform")
        pidx_p = int(pl_p.active_entity_indices()[0])
        prow_p = pl_p.dense_row_of(pidx_p)
        trow_p = tp_p.dense_row_of(pidx_p)
        tp_p.active_view()["position_x"][trow_p] = _SW * zone_x_frac
        tp_p.active_view()["position_y"][trow_p] = 400.0
        x = float(tp_p.active_view()["position_x"][trow_p])
        y = float(tp_p.active_view()["position_y"][trow_p])
        lives0 = int(pl_p.active_view()["lives"][prow_p])
        _seb(w_p, w_p, x, y, 0.0, 0.0, color=bullet_color)
        inp_p.poll(); w_p.step(DT)
        lives1 = int(pl_p.active_view()["lives"][prow_p])
        return lives0 - lives1

    lost_wrong = _hit_zone(0.75, 1)   # azul (1) na metade vermelha (direita)
    wrong_ok = lost_wrong == 2
    print(f"[{'OK ' if wrong_ok else 'FAIL'}] purity: cor errada na zona "
         f"errada -> tira 2 vidas (perdeu {lost_wrong})")
    if not wrong_ok:
        ok = False

    lost_right = _hit_zone(0.25, 1)   # azul (1) na metade azul (esquerda)
    right_ok = lost_right == 1
    print(f"[{'OK ' if right_ok else 'FAIL'}] purity: cor certa na zona "
         f"certa -> tira só 1 vida (perdeu {lost_right})")
    if not right_ok:
        ok = False

    # Purity fase 1: força só aplica fora do anel de 120px
    w_p2, inp_p2 = _bh2(boss_name="purity", weapon_name="padrao")
    bp_p2 = w_p2.get_pool("boss")
    bv_p2 = bp_p2.active_view()
    bv_p2["hp"][0] = bv_p2["max_hp"][0] * 0.4
    pl_p2 = w_p2.get_pool("player"); tp_p2 = w_p2.get_pool("transform")
    pidx_p2 = int(pl_p2.active_entity_indices()[0])
    trow_p2 = tp_p2.dense_row_of(pidx_p2)
    bidx_p2 = int(bp_p2.active_entity_indices()[0])
    btrow_p2 = tp_p2.dense_row_of(bidx_p2)
    bx_p2 = float(tp_p2.active_view()["position_x"][btrow_p2])
    by_p2 = float(tp_p2.active_view()["position_y"][btrow_p2])
    tp_p2.active_view()["position_x"][trow_p2] = bx_p2
    tp_p2.active_view()["position_y"][trow_p2] = by_p2 + 200.0   # fora do anel, on-screen
    inp_p2.poll(); w_p2.step(DT)
    y0 = float(tp_p2.active_view()["position_y"][trow_p2])
    inp_p2.poll(); w_p2.step(DT)
    y1 = float(tp_p2.active_view()["position_y"][trow_p2])
    force_ok = (y1 - y0) > 1.0
    print(f"[{'OK ' if force_ok else 'FAIL'}] purity: fora do anel -> "
         f"força empurra pra baixo (y {y0:.1f}->{y1:.1f})")
    if not force_ok:
        ok = False

    # Purity fase 2 (Contaminação): o anel encolhe de verdade com o tempo —
    # 100px do boss é seguro em t~0 (raio inicial 130) mas vira perigoso em
    # t~15s (raio já encolheu abaixo de 100)
    def _purity_contam_pull_active(world_, inp_, prow_, btrow_, dist):
        tv_ = world_.get_pool("transform").active_view()
        bx_ = float(tv_["position_x"][btrow_]); by_ = float(tv_["position_y"][btrow_])
        tv_["position_x"][prow_] = bx_ + dist
        tv_["position_y"][prow_] = by_
        x0_ = float(tv_["position_x"][prow_])
        inp_.poll(); world_.step(DT)
        x1_ = float(world_.get_pool("transform").active_view()["position_x"][prow_])
        return x1_ < x0_ - 0.01

    w_pc, inp_pc = _bh2(boss_name="purity", weapon_name="padrao")
    bp_pc = w_pc.get_pool("boss"); bv_pc = bp_pc.active_view()
    bv_pc["hp"][0] = bv_pc["max_hp"][0] * 0.1     # cascateia ate fase 2
    for _ in range(4):
        inp_pc.poll(); w_pc.step(DT)
    pl_pc = w_pc.get_pool("player"); tp_pc = w_pc.get_pool("transform")
    pidx_pc = int(pl_pc.active_entity_indices()[0])
    prow_pc = tp_pc.dense_row_of(pidx_pc)
    btrow_pc = tp_pc.dense_row_of(int(bp_pc.active_entity_indices()[0]))
    phase2_ok_pc = int(bv_pc["phase_idx"][0]) == 2

    safe_early = not _purity_contam_pull_active(w_pc, inp_pc, prow_pc, btrow_pc, 100.0)
    for _ in range(14 * 60):
        inp_pc.poll(); w_pc.step(DT)
    pulled_late = _purity_contam_pull_active(w_pc, inp_pc, prow_pc, btrow_pc, 100.0)
    shrink_ok = phase2_ok_pc and safe_early and pulled_late
    print(f"[{'OK ' if shrink_ok else 'FAIL'}] purity: contaminacao encolhe "
         f"de verdade (100px seguro em t~0, puxa em t~15s)")
    if not shrink_ok:
        ok = False

    # Decálogo #8 — Restitution: raiz normal, sem invuln escondendo nada.
    r = run("restitution", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Restitution fase 0: confisca speed_debuff/fr_debuff assim que a luta
    # começa (reafirmado toda frame enquanto phase_idx==0)
    from bullethell.game_systems import (
        spawn_pickup as _spu, RESTITUTION_SPEED_DEBUFF as _RSD,
        RESTITUTION_FR_DEBUFF as _RFD,
    )

    w_rt, inp_rt = _bh2(boss_name="restitution", weapon_name="padrao")
    pl_rt = w_rt.get_pool("player")
    prow_rt = pl_rt.dense_row_of(int(pl_rt.active_entity_indices()[0]))
    inp_rt.poll(); w_rt.step(DT)
    sd0 = float(pl_rt.active_view()["speed_debuff"][prow_rt])
    fr0 = float(pl_rt.active_view()["fr_debuff"][prow_rt])
    confisco_ok = abs(sd0 - _RSD) < 1e-6 and abs(fr0 - _RFD) < 1e-6
    print(f"[{'OK ' if confisco_ok else 'FAIL'}] restitution: confisco na "
         f"fase 0 (speed_debuff={sd0:.2f}, fr_debuff={fr0:.2f})")
    if not confisco_ok:
        ok = False

    # Restitution fase 1: derruba orbes dourados ao longo do tempo
    bp_rt = w_rt.get_pool("boss")
    bp_rt.active_view()["hp"][0] = bp_rt.active_view()["max_hp"][0] * 0.4
    pu_rt = w_rt.get_pool("pickup")
    max_pu = 0
    for _ in range(400):
        inp_rt.poll(); w_rt.step(DT)
        max_pu = max(max_pu, pu_rt.count)
    drop_ok = max_pu > 0
    print(f"[{'OK ' if drop_ok else 'FAIL'}] restitution: fase 1 derruba "
         f"orbes ao longo do tempo (pico={max_pu})")
    if not drop_ok:
        ok = False

    # Restitution: coletar um orb devolve speed_debuff/fr_debuff rumo a 1.0
    # (mundo novo — o w_rt anterior já tem a pool `pickup` cheia)
    def _restitution_phase1(world_fn=_bh2):
        w, inp = world_fn(boss_name="restitution", weapon_name="padrao")
        inp.poll(); w.step(DT)                       # fase 0: confisca
        bp = w.get_pool("boss")
        bp.active_view()["hp"][0] = bp.active_view()["max_hp"][0] * 0.4
        inp.poll(); w.step(DT)                        # transiciona p/ fase 1
        return w, inp

    w_rt2, inp_rt2 = _restitution_phase1()
    pl_rt2 = w_rt2.get_pool("player")
    prow_rt2 = pl_rt2.dense_row_of(int(pl_rt2.active_entity_indices()[0]))
    tp_rt2 = w_rt2.get_pool("transform")
    trow_rt2 = tp_rt2.dense_row_of(int(pl_rt2.active_entity_indices()[0]))
    px_rt2 = float(tp_rt2.active_view()["position_x"][trow_rt2])
    py_rt2 = float(tp_rt2.active_view()["position_y"][trow_rt2])
    pu_rt2 = w_rt2.get_pool("pickup")
    _spu(w_rt2, w_rt2, px_rt2, py_rt2)          # orb em cima do jogador
    n0_rt = pu_rt2.count
    sd1 = float(pl_rt2.active_view()["speed_debuff"][prow_rt2])
    fr1 = float(pl_rt2.active_view()["fr_debuff"][prow_rt2])
    inp_rt2.poll(); w_rt2.step(DT)
    n1_rt = pu_rt2.count
    sd2 = float(pl_rt2.active_view()["speed_debuff"][prow_rt2])
    fr2 = float(pl_rt2.active_view()["fr_debuff"][prow_rt2])
    restore_ok = (n1_rt == n0_rt - 1) and sd2 > sd1 and fr2 < fr1
    print(f"[{'OK ' if restore_ok else 'FAIL'}] restitution: coletar orb "
         f"devolve stats (speed_debuff={sd1:.2f}->{sd2:.2f}, "
         f"fr_debuff={fr1:.2f}->{fr2:.2f}, orbs={n0_rt}->{n1_rt})")
    if not restore_ok:
        ok = False

    # Restitution: bala do boss perto de um orb o empurra e reduz o ttl
    # (mundo novo de novo — mesmo motivo)
    from bullethell.game_systems import (
        spawn_enemy_bullet as _seb2, RESTITUTION_ORB_TTL as _ROT,
    )

    w_rt3, inp_rt3 = _restitution_phase1()
    pl_rt3 = w_rt3.get_pool("player"); tp_rt3 = w_rt3.get_pool("transform")
    trow_rt3 = tp_rt3.dense_row_of(int(pl_rt3.active_entity_indices()[0]))
    px_rt3 = float(tp_rt3.active_view()["position_x"][trow_rt3])
    py_rt3 = float(tp_rt3.active_view()["position_y"][trow_rt3])
    pu_rt3 = w_rt3.get_pool("pickup")
    ox_rt, oy_rt = px_rt3 + 300.0, py_rt3 - 250.0     # longe do jogador
    packed_rt = _spu(w_rt3, w_rt3, ox_rt, oy_rt)
    oidx_rt = packed_rt & 0xFFFFFFFF
    _seb2(w_rt3, w_rt3, ox_rt + 10.0, oy_rt, 0.0, 0.0, color=0)
    inp_rt3.poll(); w_rt3.step(DT)
    otrow_rt = tp_rt3.dense_row_of(oidx_rt)
    if otrow_rt >= 0:
        ox1_rt = float(tp_rt3.active_view()["position_x"][otrow_rt])
        ttl1_rt = float(pu_rt3.active_view()["ttl"][pu_rt3.dense_row_of(oidx_rt)])
        recoil_ok = ox1_rt != ox_rt and ttl1_rt < _ROT - 1e-3
    else:
        recoil_ok = False
    print(f"[{'OK ' if recoil_ok else 'FAIL'}] restitution: bala perto do "
         f"orb -> recua e reduz ttl")
    if not recoil_ok:
        ok = False

    # Decálogo #6 — Mercy: raiz normal na fase 0, sem invuln escondendo
    # nada (fase 1 congela hp sob mercy_martyr, mas isso ainda conta como
    # "danificável" via mira ingênua na primeira metade da luta).
    r = run("mercy", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # Mercy fase 0: 4 Inocentes já na entrada da luta; matar um deixa
    # névoa SLOW permanente
    from bullethell.game_systems import MINION_INNOCENT as _MI

    w_mc, inp_mc = _bh2(boss_name="mercy", weapon_name="padrao")
    mn_mc = w_mc.get_pool("minion")
    innocents_ok = (mn_mc.count == 4
                    and all(int(mn_mc.active_view()["kind"][k]) == _MI
                            for k in range(mn_mc.count)))
    print(f"[{'OK ' if innocents_ok else 'FAIL'}] mercy: 4 inocentes na "
         f"entrada da fase 0 (count={mn_mc.count})")
    if not innocents_ok:
        ok = False

    tp_mc = w_mc.get_pool("transform"); hz_mc = w_mc.get_pool("hazard")
    idxs_mc = mn_mc.active_entity_indices()
    k0_mc = int(idxs_mc[0])
    trow_mc = tp_mc.dense_row_of(k0_mc)
    x_mc = float(tp_mc.active_view()["position_x"][trow_mc])
    y_mc = float(tp_mc.active_view()["position_y"][trow_mc])
    _spb(w_mc, w_mc, "pb_padrao", x_mc, y_mc, 0.0, 0.0, 50.0, 3.0,
        color=(255, 255, 255))
    inp_mc.poll(); w_mc.step(DT)
    hazard_ok = mn_mc.count == 3 and hz_mc.count == 1
    print(f"[{'OK ' if hazard_ok else 'FAIL'}] mercy: matar inocente deixa "
         f"nevoa SLOW permanente (minions={mn_mc.count}, hazards={hz_mc.count})")
    if not hazard_ok:
        ok = False

    # Mercy fase 1 (O Mártir): invuln=1 + timer de sobrevivência acumula
    w_mm, inp_mm = _bh2(boss_name="mercy", weapon_name="padrao")
    bp_mm = w_mm.get_pool("boss"); bv_mm = bp_mm.active_view()
    bv_mm["hp"][0] = bv_mm["max_hp"][0] * 0.4
    inp_mm.poll(); w_mm.step(DT)
    martyr_ok = (int(bv_mm["phase_idx"][0]) == 1
                and int(bv_mm["invuln"][0]) == 1)
    for _ in range(60):
        inp_mm.poll(); w_mm.step(DT)
    survive_ok = martyr_ok and float(bv_mm["aux_angle"][0]) > 0.5
    print(f"[{'OK ' if survive_ok else 'FAIL'}] mercy: martirio invuln=1 + "
         f"timer de sobrevivencia acumula ({float(bv_mm['aux_angle'][0]):.2f}s)")
    if not survive_ok:
        ok = False

    # Mercy: mina perto do boss em mercy_martyr causa dano ambiental e
    # marca env_death; ao finalizar a morte o jogador leva hit-kill
    from bullethell.game_systems import spawn_minion as _smi, MINION_MINE as _MM

    w_env, inp_env = _bh2(boss_name="mercy", weapon_name="padrao")
    bp_env = w_env.get_pool("boss"); bv_env = bp_env.active_view()
    tp_env = w_env.get_pool("transform")
    bv_env["hp"][0] = 50.0
    inp_env.poll(); w_env.step(DT)
    btrow_env = tp_env.dense_row_of(int(bp_env.active_entity_indices()[0]))
    bx_env = float(tp_env.active_view()["position_x"][btrow_env])
    by_env = float(tp_env.active_view()["position_y"][btrow_env])
    _smi(w_env, w_env, bx_env, by_env, _MM, 2.0, 8.0)
    inp_env.poll(); w_env.step(DT)
    env_ok = float(bv_env["hp"][0]) <= 0.0 and int(bv_env["env_death"][0]) == 1
    st_env = w_env.get_pool("stats").active_view()
    deaths0 = int(st_env["deaths"][0])
    inp_env.poll(); w_env.step(DT)         # BossPhaseSystem finaliza a morte
    punish_ok = env_ok and int(st_env["deaths"][0]) == deaths0 + 1 \
        and int(bv_env["env_death"][0]) == 0
    print(f"[{'OK ' if punish_ok else 'FAIL'}] mercy: mina mata o boss "
         f"(env_death) -> hit-kill no jogador (deaths {deaths0}->"
         f"{int(st_env['deaths'][0])})")
    if not punish_ok:
        ok = False

    # Mercy: bala do jogador é magnetizada pro boss e, ao tocar, empurra-o
    w_mag, inp_mag = _bh2(boss_name="mercy", weapon_name="padrao")
    bp_mag = w_mag.get_pool("boss"); bv_mag = bp_mag.active_view()
    tp_mag = w_mag.get_pool("transform")
    bv_mag["hp"][0] = bv_mag["max_hp"][0] * 0.4
    inp_mag.poll(); w_mag.step(DT)
    btrow_mag = tp_mag.dense_row_of(int(bp_mag.active_entity_indices()[0]))
    bx_mag = float(tp_mag.active_view()["position_x"][btrow_mag])
    by_mag = float(tp_mag.active_view()["position_y"][btrow_mag])
    from bullethell.game_systems import spawn_player_bullet as _spb2
    _spb2(w_mag, w_mag, "pb_padrao", bx_mag + 10.0, by_mag, 0.0, 0.0, 1.0, 3.0)
    pb_mag = w_mag.get_pool("pb_core")
    n0_mag = pb_mag.count
    inp_mag.poll(); w_mag.step(DT)
    btrow_mag2 = tp_mag.dense_row_of(int(bp_mag.active_entity_indices()[0]))
    bx_mag2 = float(tp_mag.active_view()["position_x"][btrow_mag2])
    magnet_ok = (bx_mag2 < bx_mag - 1.0) and pb_mag.count == n0_mag - 1
    print(f"[{'OK ' if magnet_ok else 'FAIL'}] mercy: bala magnetizada "
         f"empurra o boss e e absorvida (x {bx_mag:.1f}->{bx_mag2:.1f}, "
         f"balas {n0_mag}->{pb_mag.count})")
    if not magnet_ok:
        ok = False

    # DECALOGUE final: root_hitbox=true, danificavel via mira ingenua.
    r = run("decalogue", "padrao", frames=1600, approach=False)
    spawned = r["enemy_bullets_peak"] > 0
    damaged = r["boss_damage"] > 0
    status = "OK " if (spawned and damaged) else "FAIL"
    if not (spawned and damaged):
        ok = False
    print(f"[{status}] {r}")

    # DECALOGUE fase 0 (O Decreto): grade de lasers H+V em tabuleiro
    from bullethell.schemas import LASER_H, LASER_V

    w_dl, inp_dl = _bh2(boss_name="decalogue", weapon_name="padrao")
    lz_dl = w_dl.get_pool("laser")
    for _ in range(100):
        inp_dl.poll(); w_dl.step(DT)
    lv_dl = lz_dl.active_view()
    n_h = int((lv_dl["axis"][:lz_dl.count] == LASER_H).sum())
    n_v = int((lv_dl["axis"][:lz_dl.count] == LASER_V).sum())
    staggered = len(set(round(float(t), 2) for t in lv_dl["telegraph_t"][:lz_dl.count])) >= 2
    grid_ok = n_h > 0 and n_v > 0 and staggered
    print(f"[{'OK ' if grid_ok else 'FAIL'}] decalogue: grade H+V em "
         f"tabuleiro (h={n_h}, v={n_v}, staggered={staggered})")
    if not grid_ok:
        ok = False

    # DECALOGUE fase 1 (O Peso da Lei): bolas caem e assentam empilhando
    # em camadas (BEH_SETTLE)
    from bullethell.game_systems import BEH_SETTLE as _BSET

    w_rs, inp_rs = _bh2(boss_name="decalogue", weapon_name="padrao")
    bp_rs = w_rs.get_pool("boss"); bv_rs = bp_rs.active_view()
    bv_rs["hp"][0] = bv_rs["max_hp"][0] * 0.6      # forca fase 1
    eb_rs = w_rs.get_pool("enemy_bullet")
    for _ in range(700):
        inp_rs.poll(); w_rs.step(DT)
    ebv_rs = eb_rs.active_view()
    tp_rs = w_rs.get_pool("transform")
    idxs_rs = eb_rs.active_entity_indices()
    n_settled = 0
    layers = set()
    for k in range(eb_rs.count):
        if int(ebv_rs["beh"][k]) != _BSET:
            continue
        trow_rs = tp_rs.dense_row_of(int(idxs_rs[k]))
        y = float(tp_rs.active_view()["position_y"][trow_rs])
        if abs(y - float(ebv_rs["p1"][k])) < 0.5:
            n_settled += 1
            layers.add(round(float(ebv_rs["p1"][k]), 1))
    stack_ok = n_settled >= 5 and len(layers) >= 2
    print(f"[{'OK ' if stack_ok else 'FAIL'}] decalogue: bolas assentam "
         f"empilhando em camadas (settled={n_settled}, camadas={len(layers)})")
    if not stack_ok:
        ok = False

    # DECALOGUE fase 2 (O Olho do Juiz): pilar instantaneo no X do jogador
    w_jg, inp_jg = _bh2(boss_name="decalogue", weapon_name="padrao")
    bp_jg = w_jg.get_pool("boss"); bv_jg = bp_jg.active_view()
    bv_jg["hp"][0] = bv_jg["max_hp"][0] * 0.3       # cascateia ate fase 2
    for _ in range(4):
        inp_jg.poll(); w_jg.step(DT)
    pl_jg = w_jg.get_pool("player"); tp_jg = w_jg.get_pool("transform")
    prow_jg = tp_jg.dense_row_of(int(pl_jg.active_entity_indices()[0]))
    px_jg = float(tp_jg.active_view()["position_x"][prow_jg])
    lz_jg = w_jg.get_pool("laser")
    found_pillar = False
    for _ in range(60):
        inp_jg.poll(); w_jg.step(DT)
        if lz_jg.count > 0:
            lvv = lz_jg.active_view()
            found_pillar = (int(bv_jg["phase_idx"][0]) == 2
                            and int(lvv["axis"][0]) == LASER_V
                            and abs(float(lvv["pos"][0]) - px_jg) < 1.0)
            break
    print(f"[{'OK ' if found_pillar else 'FAIL'}] decalogue: pilar "
         f"instantaneo mira o X do jogador ({px_jg:.1f})")
    if not found_pillar:
        ok = False

    # DECALOGUE fase 3 (O Codigo Final): axis_lock alterna X/Y e trava
    # movimento diagonal de verdade
    w_lk, inp_lk = _bh2(boss_name="decalogue", weapon_name="padrao")
    bp_lk = w_lk.get_pool("boss"); bv_lk = bp_lk.active_view()
    bv_lk["hp"][0] = bv_lk["max_hp"][0] * 0.1       # cascateia ate fase 3
    for _ in range(4):
        inp_lk.poll(); w_lk.step(DT)
    ck_lk = w_lk.get_pool("clock")
    seen_locks = set()
    for _ in range(300):
        inp_lk.poll(); w_lk.step(DT)
        seen_locks.add(int(ck_lk.active_view()["axis_lock"][0]))
    alternates_ok = int(bv_lk["phase_idx"][0]) == 3 and seen_locks == {1, 2}
    print(f"[{'OK ' if alternates_ok else 'FAIL'}] decalogue: axis_lock "
         f"alterna X/Y na fase 3 ({sorted(seen_locks)})")
    if not alternates_ok:
        ok = False

    pl_lk = w_lk.get_pool("player"); tp_lk = w_lk.get_pool("transform")
    prow_lk = tp_lk.dense_row_of(int(pl_lk.active_entity_indices()[0]))
    while int(ck_lk.active_view()["axis_lock"][0]) != 1:  # espera a janela so-X
        inp_lk.poll(); w_lk.step(DT)
    inp_lk.set_action_held("move_right", True)
    inp_lk.set_action_held("move_down", True)
    x0_lk = float(tp_lk.active_view()["position_x"][prow_lk])
    y0_lk = float(tp_lk.active_view()["position_y"][prow_lk])
    inp_lk.poll(); w_lk.step(DT)
    x1_lk = float(tp_lk.active_view()["position_x"][prow_lk])
    y1_lk = float(tp_lk.active_view()["position_y"][prow_lk])
    lock_ok = (x1_lk - x0_lk) > 0.5 and abs(y1_lk - y0_lk) < 1e-6
    print(f"[{'OK ' if lock_ok else 'FAIL'}] decalogue: axis_lock=1 trava "
         f"diagonal de verdade (x {x0_lk:.1f}->{x1_lk:.1f}, "
         f"y {y0_lk:.1f}->{y1_lk:.1f})")
    if not lock_ok:
        ok = False

    # Decálogo Rush: cascateia pela ordem canônica dos mandamentos e varre
    # pools sem campo 'root' (minion/pickup/hazard/laser) a cada troca de
    # boss — sem isso, orbes/Inocentes/minas/névoas sobreviveriam pro
    # próximo estágio
    from bullethell.game_systems import RUSH_ORDERS as _RO
    from bullethell.ids import sid as _sid
    from bullethell.loaders import load_all as _la2
    from bullethell.game_systems import spawn_pickup as _spu2, spawn_minion as _smi2
    from bullethell.game_systems import MINION_INNOCENT as _MI2

    _data2 = _la2()
    w_dr, inp_dr = _bh2(mode="decalogo")
    bp_dr = w_dr.get_pool("boss")
    canon_order = _RO[4]

    def _kill_current_and_advance():
        bv = bp_dr.active_view()
        for k in range(bp_dr.count):
            bid = int(bv["boss_id"][k])
            n_ph = len(_data2.bosses[bid].phases)
            bv["phase_idx"][k] = n_ph - 1
            bv["hp"][k] = 0.0
        inp_dr.poll(); w_dr.step(DT)
        inp_dr.poll(); w_dr.step(DT)

    cascade_ok = True
    for i in range(3):                       # monolith -> icon -> silence -> sabbath
        _kill_current_and_advance()
        expected = canon_order[i + 1]
        ids_now = sorted(set(int(bp_dr.active_view()["boss_id"][k])
                             for k in range(bp_dr.count)))
        expected_ids = sorted({_sid(expected)})
        cascade_ok = cascade_ok and (ids_now == expected_ids)
    print(f"[{'OK ' if cascade_ok else 'FAIL'}] decalogo rush: cascateia "
         f"monolith->icon->silence->sabbath na ordem canonica")
    if not cascade_ok:
        ok = False

    pu_dr = w_dr.get_pool("pickup"); mn_dr = w_dr.get_pool("minion")
    _spu2(w_dr, w_dr, 400.0, 300.0)
    _smi2(w_dr, w_dr, 500.0, 300.0, _MI2, 1.0, 0.0)
    n0_dr = pu_dr.count, mn_dr.count
    _kill_current_and_advance()               # sabbath -> lineage
    n1_dr = pu_dr.count, mn_dr.count
    sweep_ok = n0_dr[0] > 0 and n0_dr[1] > 0 and n1_dr == (0, 0)
    print(f"[{'OK ' if sweep_ok else 'FAIL'}] decalogo rush: troca de boss "
         f"varre pickup/minion orfaos ({n0_dr}->{n1_dr})")
    if not sweep_ok:
        ok = False

    raise SystemExit(0 if ok else 1)
