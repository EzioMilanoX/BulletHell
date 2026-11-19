"""Mecânicas dedicadas dos bosses do Decálogo (portado de smoke_ecs.py).

Cada teste monta um mundo headless novo, força a fase que interessa (HP
abaixo do threshold → BossPhaseSystem cascateia) e confere o efeito da
gimmick direto nas pools — inclusive os 3 bugs corrigidos na Fase 14k
(boss fugindo da tela, pilar sem aviso, puxão irresistível).
"""
import math

import pytest

from helpers import (boss_pos, boss_view, force_boss_hp, player_pos,
                     player_prow, player_view, set_player_pos, step)

from bullethell.composition import build_headless
from bullethell.game_systems import (
    BEH_SETTLE, BOSS_SCREEN_MARGIN, MINION_INNOCENT, MINION_MINE,
    PART_FAKE, PART_REAL, PICKUP_KIND_ASCETIC, RESTITUTION_FR_DEBUFF,
    RESTITUTION_ORB_TTL, RESTITUTION_SPEED_DEBUFF, RUSH_ORDERS,
    spawn_enemy_bullet, spawn_minion, spawn_pickup, spawn_player_bullet,
)
from bullethell.ids import sid
from bullethell.schemas import (CONTACT_ALWAYS, CONTACT_NEVER, LASER_H,
                                LASER_V, SCREEN_W)


def _mundo(boss: str, **kw):
    return build_headless(boss_name=boss, weapon_name="padrao", **kw)


# ---------------------------------------------------------------------------
# Icon — "ache o alvo certo"
# ---------------------------------------------------------------------------

class TestIcon:

    def _hit_part(self, world, inp, k):
        tp = world.get_pool("transform")
        pt = world.get_pool("part")
        eb = world.get_pool("enemy_bullet")
        row = tp.dense_row_of(int(pt.active_entity_indices()[k]))
        x = float(tp.active_view()["position_x"][row])
        y = float(tp.active_view()["position_y"][row])
        hp_before = float(boss_view(world)["hp"][0])
        eb_before = eb.count
        spawn_player_bullet(world, world, "pb_padrao", x, y, 0.0, 0.0, 5.0,
                            3.0, color=(255, 255, 255))
        step(world, inp)
        return hp_before, float(boss_view(world)["hp"][0]), eb_before, eb.count

    def _part_of_kind(self, world, kind):
        pt = world.get_pool("part")
        kinds = pt.active_view()["kind"]
        return next(k for k in range(pt.count) if int(kinds[k]) == kind)

    def test_fase0_raiz_invulneravel(self):
        world, inp = _mundo("icon")
        step(world, inp)
        assert int(boss_view(world)["invuln"][0]) == 1

    def test_clone_falso_revida_sem_dano(self):
        world, inp = _mundo("icon")
        step(world, inp)
        hp0, hp1, eb0, eb1 = self._hit_part(world, inp,
                                            self._part_of_kind(world, PART_FAKE))
        assert hp1 == pytest.approx(hp0)
        assert eb1 - eb0 >= 14

    def test_clone_real_toma_dano(self):
        world, inp = _mundo("icon")
        step(world, inp)
        hp0, hp1, _, _ = self._hit_part(world, inp,
                                        self._part_of_kind(world, PART_REAL))
        assert hp1 < hp0

    def test_fase2_revela_a_raiz(self):
        world, inp = _mundo("icon")
        step(world, inp)
        force_boss_hp(world, 0.32)
        step(world, inp, 3)                      # cascateia 0->1->2
        bv = boss_view(world)
        pt = world.get_pool("part")
        assert int(bv["phase_idx"][0]) == 2
        assert int(bv["invuln"][0]) == 0
        assert all(int(pt.active_view()["kind"][k]) == 4 for k in range(pt.count))


# ---------------------------------------------------------------------------
# Lineage (Honra) e Truth (Verdade)
# ---------------------------------------------------------------------------

def test_lineage_enrage_so_no_lado_com_mais_hp():
    world, inp = _mundo("lineage")
    bv = boss_view(world)
    bv["hp"][0] = bv["max_hp"][0] * 1.0
    bv["hp"][1] = bv["max_hp"][1] * 0.80            # Δ = 20% > 15%
    step(world, inp)
    assert float(bv["enrage_mult"][0]) == pytest.approx(2.0)
    assert float(bv["enrage_mult"][1]) == pytest.approx(1.0)
    bv["hp"][1] = bv["max_hp"][1] * 0.95            # reequilibra
    step(world, inp)
    assert float(bv["enrage_mult"][0]) == pytest.approx(1.0)


def test_truth_espiral_80_por_cento_fantasma_e_revela_de_perto():
    world, inp = _mundo("truth")
    eb = world.get_pool("enemy_bullet")
    step(world, inp, 30)
    contact = eb.active_view()["contact"][:eb.count]
    n_ghost = int((contact == CONTACT_NEVER).sum())
    n_real = int((contact == CONTACT_ALWAYS).sum())
    assert n_ghost + n_real > 0
    assert 0.70 <= n_ghost / (n_ghost + n_real) <= 0.90

    tp = world.get_pool("transform")
    sp = world.get_pool("sprite")
    idxs = eb.active_entity_indices()
    g_row = next(k for k in range(eb.count)
                 if eb.active_view()["contact"][k] == CONTACT_NEVER)
    g_idx = int(idxs[g_row])
    trow = tp.dense_row_of(g_idx)
    set_player_pos(world, float(tp.active_view()["position_x"][trow]),
                   float(tp.active_view()["position_y"][trow]))
    step(world, inp)
    assert eb.dense_row_of(g_idx) >= 0
    assert int(sp.active_view()["tint_a"][sp.dense_row_of(g_idx)]) == 255


# ---------------------------------------------------------------------------
# Silence (Silêncio) e Sabbath (Descanso)
# ---------------------------------------------------------------------------

def test_silence_trava_skill_e_tentativa_dispara_bolt():
    world, inp = _mundo("silence", skill_name="dash")
    prow = player_prow(world)
    step(world, inp)
    assert float(player_view(world)["skill_locked_t"][prow]) > 0.0
    eb = world.get_pool("enemy_bullet")
    eb0 = eb.count
    inp.set_action_held("skill", True)
    step(world, inp)
    assert eb.count > eb0, "tentar a skill travada deve disparar o bolt"
    assert float(player_view(world)["skill_t"][prow]) <= 0.0


def test_silence_fase1_silencia_a_arma_periodicamente():
    world, inp = _mundo("silence")
    force_boss_hp(world, 0.4)
    prow = player_prow(world)
    inp.set_action_held("fire", True)
    found = False
    for _ in range(360):
        step(world, inp)
        if float(player_view(world)["fire_locked_t"][prow]) > 0.0:
            found = True
            break
    assert found


def test_sabbath_mover_no_descanso_tira_vida():
    world, inp = _mundo("sabbath")
    bv = boss_view(world)
    force_boss_hp(world, 0.4)
    prow = player_prow(world)
    lives0 = int(player_view(world)["lives"][prow])
    step(world, inp)
    for _ in range(300):
        step(world, inp)
        if float(bv["aux_angle"][0]) % 4.0 < 1.0:
            break
    inp.set_action_held("move_right", True)
    step(world, inp)
    assert int(player_view(world)["lives"][prow]) < lives0


# ---------------------------------------------------------------------------
# Ascetic (Ascese)
# ---------------------------------------------------------------------------

def _anel(world, cx, cy, raio=100.0, n=8):
    for j in range(n):
        a = j * (2 * math.pi / n)
        spawn_enemy_bullet(world, world, cx + math.cos(a) * raio,
                           cy + math.sin(a) * raio, 0.0, 0.0, color=0)


def test_ascetic_anel_cercando_vazio_liga_gravidade():
    world, inp = _mundo("ascetic")
    px, py = player_pos(world)
    _anel(world, px + 15.0, py)               # centro deslocado (assimétrico)
    step(world, inp)
    eb = world.get_pool("enemy_bullet")
    assert int((eb.active_view()["gravity"][:eb.count] > 0).sum()) >= 6


def test_ascetic_bala_no_buraco_desliga_gravidade():
    world, inp = _mundo("ascetic")
    px, py = player_pos(world)
    _anel(world, px, py)
    spawn_enemy_bullet(world, world, px, py, 0.0, 0.0, color=0)
    step(world, inp)
    eb = world.get_pool("enemy_bullet")
    assert int((eb.active_view()["gravity"][:eb.count] > 0).sum()) == 0


def test_ascetic_renuncia_derruba_coracoes_falsos():
    world, inp = _mundo("ascetic")
    force_boss_hp(world, 0.4)
    pu = world.get_pool("pickup")
    pico = 0
    for _ in range(200):
        step(world, inp)
        pico = max(pico, pu.count)
    assert pico > 0
    assert int(boss_view(world)["phase_idx"][0]) == 1


def test_ascetic_coracao_congela_e_dispara_cruz():
    world, inp = _mundo("ascetic")
    force_boss_hp(world, 0.4)
    step(world, inp)
    pidx = int(world.get_pool("player").active_entity_indices()[0])
    px, py = player_pos(world)
    eb = world.get_pool("enemy_bullet")
    eb0 = eb.count
    spawn_pickup(world, world, px, py, kind=PICKUP_KIND_ASCETIC)
    inp.set_action_held("move_right", True)
    step(world, inp)                          # coleta + spawna a cruz
    assert eb.count >= eb0 + 4
    step(world, inp)                          # freeze_t reafirmado -> aplica
    vel = world.get_pool("velocity")
    assert float(vel.active_view()["linear_x"][vel.dense_row_of(pidx)]) == 0.0


# ---------------------------------------------------------------------------
# Purity (Pureza)
# ---------------------------------------------------------------------------

def _perda_de_vidas_na_zona(zone_x_frac: float, bullet_color: int) -> int:
    world, inp = _mundo("purity")
    prow = player_prow(world)
    set_player_pos(world, SCREEN_W * zone_x_frac, 400.0)
    x, y = player_pos(world)
    lives0 = int(player_view(world)["lives"][prow])
    spawn_enemy_bullet(world, world, x, y, 0.0, 0.0, color=bullet_color)
    step(world, inp)
    return lives0 - int(player_view(world)["lives"][prow])


def test_purity_cor_errada_na_zona_errada_tira_2_vidas():
    assert _perda_de_vidas_na_zona(0.75, 1) == 2   # azul na metade vermelha


def test_purity_cor_certa_na_zona_certa_tira_1_vida():
    assert _perda_de_vidas_na_zona(0.25, 1) == 1   # azul na metade azul


def test_purity_fase1_forca_so_fora_do_anel():
    world, inp = _mundo("purity")
    force_boss_hp(world, 0.4)
    bx, by = boss_pos(world)
    set_player_pos(world, bx, by + 200.0)      # fora do anel, na tela
    step(world, inp)
    y0 = player_pos(world)[1]
    step(world, inp)
    assert player_pos(world)[1] - y0 > 1.0


class TestPurityContaminacao:

    def _mundo_fase2(self):
        world, inp = _mundo("purity")
        force_boss_hp(world, 0.1)               # cascateia até a fase 2
        step(world, inp, 4)
        assert int(boss_view(world)["phase_idx"][0]) == 2
        return world, inp

    def _puxa(self, world, inp, dist):
        bx, by = boss_pos(world)
        set_player_pos(world, bx + dist, by)
        x0 = player_pos(world)[0]
        step(world, inp)
        return player_pos(world)[0] < x0 - 0.01

    def test_anel_encolhe_com_o_tempo(self):
        world, inp = self._mundo_fase2()
        assert not self._puxa(world, inp, 100.0)   # seguro em t~0 (raio 130)
        step(world, inp, 14 * 60)
        assert self._puxa(world, inp, 100.0)       # raio já < 100 em t~15s

    def test_puxao_pode_ser_resistido(self):
        """Bug corrigido (14k): 240px/s > PLAYER_SPEED=220 era irresistível."""
        world, inp = self._mundo_fase2()
        step(world, inp, 14 * 60)
        bx, by = boss_pos(world)
        set_player_pos(world, bx + 400.0, by)      # bem fora do anel
        inp.set_action_held("move_right", True)
        x0 = player_pos(world)[0]
        step(world, inp)
        assert player_pos(world)[0] > x0


# ---------------------------------------------------------------------------
# Restitution (Restituição)
# ---------------------------------------------------------------------------

def _restitution_fase1():
    world, inp = _mundo("restitution")
    step(world, inp)                            # fase 0: confisca
    force_boss_hp(world, 0.4)
    step(world, inp)                            # transiciona p/ fase 1
    return world, inp


def test_restitution_confisca_stats_na_fase0():
    world, inp = _mundo("restitution")
    prow = player_prow(world)
    step(world, inp)
    pv = player_view(world)
    assert float(pv["speed_debuff"][prow]) == pytest.approx(RESTITUTION_SPEED_DEBUFF)
    assert float(pv["fr_debuff"][prow]) == pytest.approx(RESTITUTION_FR_DEBUFF)


def test_restitution_fase1_derruba_orbes():
    world, inp = _mundo("restitution")
    step(world, inp)
    force_boss_hp(world, 0.4)
    pu = world.get_pool("pickup")
    pico = 0
    for _ in range(400):
        step(world, inp)
        pico = max(pico, pu.count)
    assert pico > 0


def test_restitution_coletar_orbe_devolve_stats():
    world, inp = _restitution_fase1()
    prow = player_prow(world)
    pu = world.get_pool("pickup")
    px, py = player_pos(world)
    spawn_pickup(world, world, px, py)          # orbe em cima do jogador
    n0 = pu.count
    pv = player_view(world)
    sd1, fr1 = float(pv["speed_debuff"][prow]), float(pv["fr_debuff"][prow])
    step(world, inp)
    pv = player_view(world)
    assert pu.count == n0 - 1
    assert float(pv["speed_debuff"][prow]) > sd1
    assert float(pv["fr_debuff"][prow]) < fr1


def test_restitution_bala_perto_do_orbe_empurra_e_encurta_ttl():
    world, inp = _restitution_fase1()
    tp = world.get_pool("transform")
    pu = world.get_pool("pickup")
    px, py = player_pos(world)
    ox, oy = px + 300.0, py - 250.0              # longe do jogador
    oidx = spawn_pickup(world, world, ox, oy) & 0xFFFFFFFF
    spawn_enemy_bullet(world, world, ox + 10.0, oy, 0.0, 0.0, color=0)
    step(world, inp)
    trow = tp.dense_row_of(oidx)
    assert trow >= 0
    assert float(tp.active_view()["position_x"][trow]) != ox
    assert float(pu.active_view()["ttl"][pu.dense_row_of(oidx)]) < RESTITUTION_ORB_TTL - 1e-3


# ---------------------------------------------------------------------------
# Mercy (Misericórdia)
# ---------------------------------------------------------------------------

def test_mercy_inocentes_e_nevoa_ao_matar_um():
    world, inp = _mundo("mercy")
    mn = world.get_pool("minion")
    hz = world.get_pool("hazard")
    assert mn.count == 4
    assert all(int(mn.active_view()["kind"][k]) == MINION_INNOCENT
               for k in range(mn.count))
    tp = world.get_pool("transform")
    trow = tp.dense_row_of(int(mn.active_entity_indices()[0]))
    spawn_player_bullet(world, world, "pb_padrao",
                        float(tp.active_view()["position_x"][trow]),
                        float(tp.active_view()["position_y"][trow]),
                        0.0, 0.0, 50.0, 3.0, color=(255, 255, 255))
    step(world, inp)
    assert mn.count == 3
    assert hz.count == 1


def test_mercy_martirio_invulneravel_e_acumula_sobrevivencia():
    world, inp = _mundo("mercy")
    force_boss_hp(world, 0.4)
    step(world, inp)
    bv = boss_view(world)
    assert int(bv["phase_idx"][0]) == 1
    assert int(bv["invuln"][0]) == 1
    step(world, inp, 60)
    assert float(bv["aux_angle"][0]) > 0.5


def test_mercy_mina_mata_o_boss_e_pune_o_jogador():
    world, inp = _mundo("mercy")
    bv = boss_view(world)
    bv["hp"][0] = 50.0
    step(world, inp)
    bx, by = boss_pos(world)
    spawn_minion(world, world, bx, by, MINION_MINE, 2.0, 8.0)
    step(world, inp)
    assert float(bv["hp"][0]) <= 0.0
    assert int(bv["env_death"][0]) == 1
    st = world.get_pool("stats").active_view()
    deaths0 = int(st["deaths"][0])
    step(world, inp)                            # BossPhaseSystem finaliza
    assert int(st["deaths"][0]) == deaths0 + 1
    assert int(bv["env_death"][0]) == 0


def test_mercy_bala_magnetizada_empurra_o_boss():
    world, inp = _mundo("mercy")
    force_boss_hp(world, 0.4)
    step(world, inp)
    bx, by = boss_pos(world)
    spawn_player_bullet(world, world, "pb_padrao", bx + 10.0, by, 0.0, 0.0, 1.0, 3.0)
    pb = world.get_pool("pb_core")
    n0 = pb.count
    step(world, inp)
    assert boss_pos(world)[0] < bx - 1.0
    assert pb.count == n0 - 1


def test_mercy_empurroes_nao_tiram_o_boss_da_tela():
    """Bug corrigido (14k): o push não tinha clamp, o boss fugia da tela."""
    world, inp = _mundo("mercy")
    force_boss_hp(world, 0.4)
    step(world, inp)
    for _ in range(200):
        bx, by = boss_pos(world)
        spawn_player_bullet(world, world, "pb_padrao", bx + 10.0, by, 0.0, 0.0, 1.0, 3.0)
        step(world, inp)
    assert boss_pos(world)[0] >= BOSS_SCREEN_MARGIN - 0.5


# ---------------------------------------------------------------------------
# DECALOGUE (boss final)
# ---------------------------------------------------------------------------

def test_decalogue_fase0_grade_de_lasers_em_tabuleiro():
    world, inp = _mundo("decalogue")
    lz = world.get_pool("laser")
    step(world, inp, 100)
    lv = lz.active_view()
    axis = lv["axis"][:lz.count]
    assert int((axis == LASER_H).sum()) > 0
    assert int((axis == LASER_V).sum()) > 0
    assert len(set(round(float(t), 2) for t in lv["telegraph_t"][:lz.count])) >= 2


def test_decalogue_fase1_bolas_empilham_em_camadas():
    world, inp = _mundo("decalogue")
    force_boss_hp(world, 0.6)
    step(world, inp, 700)
    eb = world.get_pool("enemy_bullet")
    tp = world.get_pool("transform")
    ev = eb.active_view()
    idxs = eb.active_entity_indices()
    assentadas, camadas = 0, set()
    for k in range(eb.count):
        if int(ev["beh"][k]) != BEH_SETTLE:
            continue
        y = float(tp.active_view()["position_y"][tp.dense_row_of(int(idxs[k]))])
        if abs(y - float(ev["p1"][k])) < 0.5:
            assentadas += 1
            camadas.add(round(float(ev["p1"][k]), 1))
    assert assentadas >= 5
    assert len(camadas) >= 2


def _decalogue_fase(frac):
    world, inp = _mundo("decalogue")
    force_boss_hp(world, frac)
    step(world, inp, 4)
    return world, inp


def test_decalogue_pilar_mira_o_jogador_e_telegrafa():
    """Bug corrigido (14k): o pilar nascia com telegraph_t=0 (indesviável)."""
    world, inp = _decalogue_fase(0.3)
    px = player_pos(world)[0]
    lz = world.get_pool("laser")
    for _ in range(60):
        step(world, inp)
        if lz.count > 0:
            break
    assert lz.count > 0
    lv = lz.active_view()
    assert int(boss_view(world)["phase_idx"][0]) == 2
    assert int(lv["axis"][0]) == LASER_V
    assert abs(float(lv["pos"][0]) - px) < 1.0
    assert float(lv["telegraph_t"][0]) > 0.1


def test_decalogue_fugir_durante_o_aviso_evita_o_dano():
    world, inp = _decalogue_fase(0.3)
    lives0 = int(player_view(world)["lives"][0])
    lz = world.get_pool("laser")
    avisou = False
    for _ in range(60):
        if avisou:
            inp.set_action_held("move_right", True)
        step(world, inp)
        avisou = avisou or lz.count > 0
    assert int(player_view(world)["lives"][0]) == lives0


def test_decalogue_fase3_axis_lock_alterna_e_trava_diagonal():
    world, inp = _decalogue_fase(0.1)
    ck = world.get_pool("clock")
    vistos = set()
    for _ in range(300):
        step(world, inp)
        vistos.add(int(ck.active_view()["axis_lock"][0]))
    assert int(boss_view(world)["phase_idx"][0]) == 3
    assert vistos == {1, 2}

    while int(ck.active_view()["axis_lock"][0]) != 1:   # janela só-X
        step(world, inp)
    inp.set_action_held("move_right", True)
    inp.set_action_held("move_down", True)
    x0, y0 = player_pos(world)
    step(world, inp)
    x1, y1 = player_pos(world)
    assert x1 - x0 > 0.5
    assert y1 == pytest.approx(y0, abs=1e-6)


# ---------------------------------------------------------------------------
# Decálogo Rush
# ---------------------------------------------------------------------------

class TestDecalogoRush:

    def _mata_e_avanca(self, world, inp, data):
        bp = world.get_pool("boss")
        bv = bp.active_view()
        for k in range(bp.count):
            bv["phase_idx"][k] = len(data.bosses[int(bv["boss_id"][k])].phases) - 1
            bv["hp"][k] = 0.0
        step(world, inp, 2)

    def _ids(self, world):
        bp = world.get_pool("boss")
        return sorted(set(int(bp.active_view()["boss_id"][k]) for k in range(bp.count)))

    def test_cascateia_na_ordem_canonica(self, data):
        world, inp = build_headless(mode="decalogo")
        ordem = RUSH_ORDERS[4]
        assert self._ids(world) == [sid(ordem[0])]
        for i in range(3):                      # monolith→icon→silence→sabbath
            self._mata_e_avanca(world, inp, data)
            assert self._ids(world) == [sid(ordem[i + 1])]

    def test_troca_de_boss_varre_pickup_e_minion_orfaos(self, data):
        world, inp = build_headless(mode="decalogo")
        pu = world.get_pool("pickup")
        mn = world.get_pool("minion")
        spawn_pickup(world, world, 400.0, 300.0)
        spawn_minion(world, world, 500.0, 300.0, MINION_INNOCENT, 1.0, 0.0)
        assert pu.count > 0 and mn.count > 0
        self._mata_e_avanca(world, inp, data)
        assert (pu.count, mn.count) == (0, 0)

