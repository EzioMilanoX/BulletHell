"""Colisão e dano (a intenção de test_gameplay.py do legado, contra
PlayerHitSystem/PlayerBulletVsBossSystem/WeaponFireSystem): bala no
jogador tira vida e some; bala longe não; graze no anel externo; bala do
jogador fere o boss e é consumida; boss invulnerável não toma dano;
CANHÃO DE VIDRO triplica o dano e começa com 0 vidas extras; ABISSAL
liga a Fragmentação (balas de revanche).
"""
import numpy as np
import pytest

from helpers import (boss_pos, boss_view, player_pos, player_prow,
                     player_view, step)

from bullethell.composition import build_headless
from bullethell.game_systems import (PLAYER_GRAZE_R, PLAYER_HIT_R,
                                     spawn_enemy_bullet, spawn_player_bullet)


def _mundo_sem_emitters(**kw):
    world, inp = build_headless(**kw)
    em = world.get_pool("emitter")
    for h in em.active_view()["self"][:em.count]:
        world.destroy_entity(int(h))
    step(world, inp)
    return world, inp


class TestBalaNoJogador:

    def test_bala_em_cima_tira_vida_e_some(self):
        world, inp = _mundo_sem_emitters()
        prow = player_prow(world)
        lives0 = int(player_view(world)["lives"][prow])
        px, py = player_pos(world)
        packed = spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)
        step(world, inp)
        assert int(player_view(world)["lives"][prow]) == lives0 - 1
        eb = world.get_pool("enemy_bullet")
        assert eb.dense_row_of(packed & 0xFFFFFFFF) < 0
        assert float(player_view(world)["invuln_t"][prow]) > 0.0

    def test_invulneravel_apos_hit(self):
        world, inp = _mundo_sem_emitters()
        prow = player_prow(world)
        px, py = player_pos(world)
        spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)
        step(world, inp)
        lives1 = int(player_view(world)["lives"][prow])
        spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)
        step(world, inp)
        assert int(player_view(world)["lives"][prow]) == lives1

    def test_bala_longe_nao_acerta(self):
        world, inp = _mundo_sem_emitters()
        prow = player_prow(world)
        lives0 = int(player_view(world)["lives"][prow])
        px, py = player_pos(world)
        spawn_enemy_bullet(world, world, px + 200.0, py - 200.0, 0.0, 0.0)
        step(world, inp)
        assert int(player_view(world)["lives"][prow]) == lives0

    def test_graze_no_anel_externo(self):
        world, inp = _mundo_sem_emitters()
        prow = player_prow(world)
        lives0 = int(player_view(world)["lives"][prow])
        g0 = int(player_view(world)["graze"][prow])
        px, py = player_pos(world)
        dist = (PLAYER_HIT_R + PLAYER_GRAZE_R) / 2 + 4.0
        spawn_enemy_bullet(world, world, px + dist, py, 0.0, 0.0)
        step(world, inp)
        assert int(player_view(world)["lives"][prow]) == lives0
        assert int(player_view(world)["graze"][prow]) == g0 + 1


class TestBalaNoBoss:

    def _tiro_no_boss(self, world, inp, dano=5.0):
        bx, by = boss_pos(world)
        hp0 = float(boss_view(world)["hp"][0])
        packed = spawn_player_bullet(world, world, "pb_padrao", bx, by,
                                     0.0, 0.0, dano, 3.0)
        step(world, inp)
        return hp0, float(boss_view(world)["hp"][0]), packed

    def test_bala_fere_e_e_consumida(self):
        world, inp = _mundo_sem_emitters()
        hp0, hp1, packed = self._tiro_no_boss(world, inp, 5.0)
        assert hp1 == pytest.approx(hp0 - 5.0)
        assert world.get_pool("pb_core").dense_row_of(packed & 0xFFFFFFFF) < 0

    def test_bala_longe_nao_fere(self):
        world, inp = _mundo_sem_emitters()
        bx, by = boss_pos(world)
        hp0 = float(boss_view(world)["hp"][0])
        spawn_player_bullet(world, world, "pb_padrao", bx + 300.0, by + 300.0,
                            0.0, 0.0, 5.0, 3.0)
        step(world, inp)
        assert float(boss_view(world)["hp"][0]) == pytest.approx(hp0)

    def test_boss_invulneravel_nao_toma_dano(self, data):
        """invuln é reafirmado por frame pela gimmick da fase — o Sétimo
        Selo (última fase do Pecado) é o caso canônico de boss imune."""
        world, inp = build_headless(boss_name="sin")
        bv = boss_view(world)
        fases = data.bosses[int(bv["boss_id"][0])].phases
        bv["phase_idx"][0] = len(fases) - 2
        bv["hp"][0] = bv["max_hp"][0] * fases[-2].hp_above - 1.0
        step(world, inp)
        assert int(bv["invuln"][0]) == 1
        hp0, hp1, _ = self._tiro_no_boss(world, inp)
        assert hp1 == pytest.approx(hp0)


def _dano_das_balas_disparadas(mutators=frozenset()):
    world, inp = build_headless(mutators=mutators)
    inp.set_action_held("fire", True)
    pb = world.get_pool("pb_core")
    for _ in range(30):
        step(world, inp)
        if pb.count:
            return float(np.max(pb.active_view()["damage"][:pb.count]))
    raise AssertionError("arma nunca disparou")


def test_canhao_de_vidro_triplica_o_dano():
    normal = _dano_das_balas_disparadas()
    vidro = _dano_das_balas_disparadas(frozenset({"glass"}))
    assert vidro == pytest.approx(normal * 3.0)


def test_canhao_de_vidro_morre_no_primeiro_hit():
    world, inp = _mundo_sem_emitters(mutators=frozenset({"glass"}))
    st = world.get_pool("stats").active_view()
    px, py = player_pos(world)
    spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)
    step(world, inp)
    assert int(st["deaths"][0]) == 1


@pytest.mark.parametrize("diff,esperado", [("normal", 0), ("expert", 0),
                                           ("abissal", 1)])
def test_fragmentacao_so_no_abissal(diff, esperado):
    """Legado: Difficulty.revenge_bullets só no ABISSAL."""
    world, _ = build_headless(difficulty=diff)
    assert int(world.get_pool("run_mods").active_view()["abissal"][0]) == esperado


def test_abissal_bala_que_sai_da_tela_se_fragmenta():
    world, inp = build_headless(difficulty="abissal")
    eb = world.get_pool("enemy_bullet")
    vistos = 0
    for _ in range(600):
        step(world, inp)
        ev = eb.active_view()
        vistos = max(vistos, int((ev["fragment"][:eb.count] != 0).sum()))
    assert vistos > 0, "balas do ABISSAL nascem marcadas para fragmentar"
