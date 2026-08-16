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

    raise SystemExit(0 if ok else 1)
