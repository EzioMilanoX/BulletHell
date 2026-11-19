"""Instrumentação das masteries de skill+/arma+ (portado de
smoke_mastery.py): jogando headless, os contadores da pool `mastery`
reagem aos eventos certos dentro dos sistemas (SkillSystem/
PlayerHitSystem/PlayerBulletVsBossSystem). A lógica de desbloqueio em si
está em test_progressao.py.
"""
import math

from helpers import (DT, boss_pos, follow_boss_and_step, player_pos,
                     set_player_pos, step)

from bullethell.composition import build_headless
from bullethell.game_systems import spawn_enemy_bullet


def _mundo(skill="none", weapon="padrao"):
    return build_headless(boss_name="classic", weapon_name=weapon,
                          skill_name=skill, mode="classic")


def _mastery(world):
    return world.get_pool("mastery").active_view()


def _anel(world, raio, n):
    px, py = player_pos(world)
    for j in range(n):
        a = j * (math.tau / n)
        spawn_enemy_bullet(world, world, px + math.cos(a) * raio,
                           py + math.sin(a) * raio, 0.0, 0.0)


def test_emp_destroi_o_anel_numa_ativacao():
    world, inp = _mundo("emp")
    _anel(world, 60, 20)
    inp.set_action_held("skill", True)
    step(world, inp)
    assert int(_mastery(world)["emp_max"][0]) == 20


def test_parry_reflete_o_grupo_numa_janela():
    world, inp = _mundo("parry")
    _anel(world, 10, 6)
    inp.set_action_held("skill", True)
    step(world, inp)
    assert int(_mastery(world)["parry_burst_max"][0]) == 6


def test_dilatacao_marca_bala_colada():
    world, inp = _mundo("timedil")
    px, py = player_pos(world)
    spawn_enemy_bullet(world, world, px + 2.0, py, 0.0, 0.0)
    inp.set_action_held("skill", True)
    step(world, inp)
    assert bool(_mastery(world)["timedil_close"][0])


def test_escudo_bloco_perfeito():
    world, inp = _mundo("shield+")
    inp.set_action_held("skill", True)
    step(world, inp)                          # ativa o escudo (skill_age=0)
    inp.set_action_held("skill", False)
    px, py = player_pos(world)
    spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)   # hit a <0.15s
    step(world, inp)
    assert int(_mastery(world)["shield_perfects"][0]) == 1


def test_blink_atravessa_o_boss():
    world, inp = _mundo("blink")
    bx, by = boss_pos(world)
    set_player_pos(world, bx, by + 150.0)     # 150px abaixo do boss
    inp.set_action_held("move_up", True)      # blink de 190px pra cima
    inp.set_action_held("skill", True)
    step(world, inp)
    assert bool(_mastery(world)["blink_pass"][0])


def test_dash_plus_graze_durante_iframes():
    world, inp = _mundo("dash+")
    inp.set_action_held("move_right", True)
    inp.set_action_held("skill", True)
    inp.poll()
    world.step(DT)                            # ativa o dash (skill_t>0)
    inp.set_action_held("skill", False)
    inp.set_action_held("move_right", False)  # para (a 1320px/s passaria direto)
    px, py = player_pos(world)
    # zona de graze real: entre HIT_R e GRAZE_R (26) — não dentro do HIT_R
    spawn_enemy_bullet(world, world, px + 20.0, py, 0.0, 0.0)
    step(world, inp)
    assert int(_mastery(world)["dash_graze"][0]) >= 1


def test_padrao_sequencia_de_acertos():
    world, inp = _mundo()
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 40.0, 90)
    assert int(_mastery(world)["default_max"][0]) >= 5


def test_spread_acertos_de_perto():
    world, inp = _mundo(weapon="spread")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 30.0, 90)
    assert int(_mastery(world)["spread_close"][0]) >= 1


def test_plasma_contato_continuo():
    world, inp = _mundo(weapon="plasma")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 25.0, 90)
    assert float(_mastery(world)["plasma_max"][0]) > 0.0


def test_satelite_dano_das_gemas():
    world, inp = _mundo(weapon="satelite")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 0.0, 180)
    assert float(_mastery(world)["orbit_damage"][0]) > 0.0


def test_overclock_dano_na_janela():
    world, inp = _mundo("overclock")
    inp.set_action_held("fire", True)
    inp.set_action_held("skill", True)
    follow_boss_and_step(world, inp, 40.0, 1)
    inp.set_action_held("skill", False)
    follow_boss_and_step(world, inp, 40.0, 90)   # janela de 3s
    assert float(_mastery(world)["oc_dmg_max"][0]) > 0.0
