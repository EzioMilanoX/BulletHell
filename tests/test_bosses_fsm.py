"""Máquina de fases dos bosses e gimmicks dos pecados — a intenção de
test_boss_fsm.py/test_sin_bosses.py do legado, contra os sistemas ECS
(BossPhaseSystem/BossGimmickSystem/WaypointSystem) e bosses.json.

No legado cada boss era uma classe com FSM própria; no port a FSM é
genérica e data-driven: `phases[i].hp_above` decide a troca, e a
`gimmick` da fase liga o comportamento especial.
"""
import pytest

from helpers import (boss_pos, boss_view, force_boss_hp, player_pos,
                     player_prow, player_view, set_player_pos, step)

from bullethell.composition import build_headless
from bullethell.game_systems import SPOT_HALF, spawn_player_bullet
from bullethell.ids import sid


def _mundo(boss="classic", **kw):
    kw.setdefault("weapon_name", "padrao")
    return build_headless(boss_name=boss, **kw)


def _fase(world, k=0) -> int:
    return int(boss_view(world)["phase_idx"][k])


def _forca_fase(world, inp, data, alvo: int, k: int = 0) -> None:
    """Põe o HP logo abaixo do threshold que leva à fase `alvo`."""
    bv = boss_view(world)
    bdef = data.bosses[int(bv["boss_id"][k])]
    bv["phase_idx"][k] = alvo - 1
    bv["hp"][k] = bv["max_hp"][k] * bdef.phases[alvo - 1].hp_above - 1.0
    step(world, inp)
    assert _fase(world, k) == alvo


# ---------------------------------------------------------------------------
# FSM genérica
# ---------------------------------------------------------------------------

class TestFasesPorHp:

    def test_comeca_na_fase_0_com_hp_cheio(self):
        world, inp = _mundo()
        step(world, inp)
        bv = boss_view(world)
        assert _fase(world) == 0
        assert float(bv["hp"][0]) == pytest.approx(float(bv["max_hp"][0]))

    def test_cada_threshold_avanca_uma_fase(self, data):
        world, inp = _mundo()
        fases = data.bosses[sid("classic")].phases
        assert len(fases) == 5
        for i in range(len(fases) - 1):
            force_boss_hp(world, fases[i].hp_above - 0.01)
            step(world, inp)
            assert _fase(world) == i + 1

    def test_hp_acima_do_threshold_nao_avanca(self, data):
        world, inp = _mundo()
        force_boss_hp(world, data.bosses[sid("classic")].phases[0].hp_above + 0.02)
        step(world, inp, 10)
        assert _fase(world) == 0

    def test_queda_brusca_cascateia_uma_fase_por_frame(self):
        world, inp = _mundo()
        force_boss_hp(world, 0.01)
        step(world, inp)
        assert _fase(world) == 1
        step(world, inp, 3)
        assert _fase(world) == 4

    def test_troca_de_fase_troca_os_emitters(self, data):
        world, inp = _mundo()
        em = world.get_pool("emitter")

        def padroes():
            return sorted(int(p) for p in em.active_view()["pattern_id"][:em.count])

        antes = padroes()
        _forca_fase(world, inp, data, 1)
        step(world, inp)                       # destroy diferido: flush
        depois = padroes()
        esperado = sorted(e[0] for e in data.bosses[sid("classic")].phases[1].emitters)
        assert depois == esperado
        assert depois != antes

    def test_hp_zero_fora_da_ultima_fase_so_pina_em_1(self):
        world, inp = _mundo("sin")
        boss_view(world)["hp"][0] = 0.0
        step(world, inp)
        bv = boss_view(world)
        assert float(bv["hp"][0]) > 0.0
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 0

    def test_classico_reinicia_ao_morrer(self, data):
        world, inp = _mundo()
        _forca_fase(world, inp, data, 4)
        boss_view(world)["hp"][0] = 0.0
        step(world, inp)
        bv = boss_view(world)
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1
        assert _fase(world) == 0
        assert float(bv["hp"][0]) == pytest.approx(float(bv["max_hp"][0]))


class TestSegundoFolego:
    """EXPERT+/ABISSAL: na morte, o boss sobrevive 3s com 1 HP, imune,
    soltando anéis — uma vez por run (legado: Difficulty.second_wind)."""

    def _morre(self, world, inp, data):
        _forca_fase(world, inp, data, 4)
        boss_view(world)["hp"][0] = 0.0
        step(world, inp)

    @pytest.mark.parametrize("diff", ["expert", "abissal"])
    def test_intercepta_a_morte(self, data, diff):
        world, inp = _mundo(difficulty=diff)
        eb = world.get_pool("enemy_bullet")
        self._morre(world, inp, data)
        bv = boss_view(world)
        assert float(bv["hp"][0]) == pytest.approx(1.0)
        assert int(bv["invuln"][0]) == 1
        assert float(bv["sw_t"][0]) > 0.0
        assert eb.count >= 32, "anel inicial de 32 balas"
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 0
        step(world, inp, int(3.2 * 60))        # timer esgota: morre de vez
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1

    def test_normal_nao_tem_segundo_folego(self, data):
        world, inp = _mundo(difficulty="normal")
        self._morre(world, inp, data)
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1

    def test_so_uma_vez_por_run(self, data):
        world, inp = _mundo(difficulty="expert")
        self._morre(world, inp, data)
        step(world, inp, int(3.2 * 60))
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1
        self._morre(world, inp, data)          # 2ª morte: sem sobrevida
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 2


def test_dificuldade_escala_hp_do_boss():
    hp = {}
    for diff in ("facil", "normal", "abissal"):
        world, _ = _mundo(difficulty=diff)
        hp[diff] = float(boss_view(world)["max_hp"][0])
    assert hp["facil"] < hp["normal"] < hp["abissal"]


def test_boss_anda_pela_rota():
    world, inp = _mundo()
    x0, y0 = boss_pos(world)
    step(world, inp, 180)
    x1, y1 = boss_pos(world)
    assert (x1, y1) != (x0, y0)


# ---------------------------------------------------------------------------
# Gimmicks dos pecados
# ---------------------------------------------------------------------------

class TestSoberbaHolofote:

    def _spot(self, world):
        return float(boss_view(world)["aux_angle"][0])

    def test_invulneravel_fora_do_feixe(self):
        world, inp = _mundo("pride")
        step(world, inp)
        set_player_pos(world, self._spot(world) + SPOT_HALF + 200.0
                       if self._spot(world) < 640 else self._spot(world) - SPOT_HALF - 200.0,
                       600.0)
        step(world, inp)
        assert int(boss_view(world)["invuln"][0]) == 1

    def test_vulneravel_dentro_do_feixe(self):
        world, inp = _mundo("pride")
        for _ in range(5):
            step(world, inp)
            set_player_pos(world, self._spot(world), 600.0)
        step(world, inp)
        assert int(boss_view(world)["invuln"][0]) == 0

    def test_holofote_se_move(self):
        world, inp = _mundo("pride")
        step(world, inp)
        s0 = self._spot(world)
        step(world, inp, 30)
        assert self._spot(world) != s0

    def test_dano_fora_do_feixe_ignorado(self):
        world, inp = _mundo("pride")
        step(world, inp)
        spot = self._spot(world)
        set_player_pos(world, spot + 300.0 if spot < 640 else spot - 300.0, 600.0)
        step(world, inp)
        bx, by = boss_pos(world)
        hp0 = float(boss_view(world)["hp"][0])
        spawn_player_bullet(world, world, "pb_padrao", bx, by, 0.0, 0.0, 10.0, 3.0)
        step(world, inp)
        assert float(boss_view(world)["hp"][0]) == pytest.approx(hp0)

    def test_fase2_vento_empurra_pra_cima(self, data):
        world, inp = _mundo("pride")
        _forca_fase(world, inp, data, 2)
        set_player_pos(world, 640.0, 500.0)
        y0 = player_pos(world)[1]
        step(world, inp)
        assert player_pos(world)[1] < y0


def test_preguica_invulneravel_enquanto_ha_sentinelas(data):
    world, inp = _mundo("sloth")
    _forca_fase(world, inp, data, 1)
    step(world, inp)
    mn = world.get_pool("minion")
    assert mn.count > 0
    assert int(boss_view(world)["invuln"][0]) == 1
    for h in mn.active_view()["self"][:mn.count]:
        world.destroy_entity(int(h))
    step(world, inp, 2)
    assert int(boss_view(world)["invuln"][0]) == 0


class TestLuxuriaControlesInvertidos:

    def _invert(self, world):
        return int(world.get_pool("clock").active_view()["invert"][0])

    def test_fase0_normal(self):
        world, inp = _mundo("lust")
        step(world, inp, 5)
        assert self._invert(world) == 0

    def test_fase1_inverte(self, data):
        world, inp = _mundo("lust")
        _forca_fase(world, inp, data, 1)
        step(world, inp)
        assert self._invert(world) == 1
        x0 = player_pos(world)[0]
        inp.set_action_held("move_right", True)
        step(world, inp, 5)
        assert player_pos(world)[0] < x0, "direita vira esquerda"

    def test_fase2_volta_ao_normal(self, data):
        world, inp = _mundo("lust")
        _forca_fase(world, inp, data, 1)
        _forca_fase(world, inp, data, 2)
        step(world, inp)
        assert self._invert(world) == 0


class TestIra:

    def test_slam_dispara_anel_no_impacto(self, data):
        world, inp = _mundo("wrath")
        _forca_fase(world, inp, data, 1)
        eb = world.get_pool("enemy_bullet")
        max_y, pico = 0.0, 0
        for _ in range(6 * 60):
            n0 = eb.count
            step(world, inp)
            max_y = max(max_y, boss_pos(world)[1])
            pico = max(pico, eb.count - n0)
        assert max_y > 500.0, "mergulha até o chão"
        assert pico >= 12, "anel de 12 balas no impacto"

    def test_corpo_em_chamas_invulneravel_rapido_e_esgota_em_20s(self, data):
        world, inp = _mundo("wrath")
        _forca_fase(world, inp, data, 2)
        set_player_pos(world, 40.0, 700.0)
        bv = boss_view(world)
        assert int(bv["invuln"][0]) == 1
        step(world, inp, 60)
        vel = (float(bv["aux_angle"][0]), float(bv["aux2"][0]))
        assert abs(vel[0]) <= 600.0 and abs(vel[1]) <= 600.0
        assert abs(vel[0]) > 320.0, "acelera com o tempo"
        player_view(world)["invuln_t"][player_prow(world)] = 1e6   # não morrer no caminho
        step(world, inp, 20 * 60)
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1


def test_inveja_rouba_metade_da_recarga(data):
    world, inp = _mundo("envy", skill_name="dash")
    _forca_fase(world, inp, data, 1)
    prow = player_prow(world)
    pv = player_view(world)
    pv["skill_cd"][prow] = 2.0
    step(world, inp, 60)
    # recarga normal tiraria 1.0s em 60 frames; com o roubo, só ~0.5s
    assert float(pv["skill_cd"][prow]) == pytest.approx(1.5, abs=0.05)


class TestPecadoSetimoSelo:

    def test_ultima_fase_invulneravel_e_atira_teleguiadas(self, data):
        world, inp = _mundo("sin")
        _forca_fase(world, inp, data, 3)
        eb = world.get_pool("enemy_bullet")
        n0 = eb.count
        step(world, inp, 60)
        assert int(boss_view(world)["invuln"][0]) == 1
        assert eb.count > n0

    def test_sobreviver_30s_derruba_o_boss(self, data):
        world, inp = _mundo("sin")
        _forca_fase(world, inp, data, 3)
        player_view(world)["invuln_t"][player_prow(world)] = 1e6
        step(world, inp, 29 * 60)
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 0
        step(world, inp, 2 * 60)
        assert int(world.get_pool("stats").active_view()["kills"][0]) == 1
