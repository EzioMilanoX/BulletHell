"""
Smoke test das masteries de skill+/arma+ (PARITY_PLAN.md P1-7): confere,
jogando de verdade (headless), que os contadores da pool `mastery` reagem
aos eventos certos — não só a lógica de desbloqueio (isso é coberto por
smoke_gating.py), mas a instrumentação em si dentro dos sistemas
(SkillSystem/PlayerHitSystem/PlayerBulletVsBossSystem).

`World.get_pool()` delega para o mesmo MemoryManager que os sistemas usam
— por isso os helpers `spawn_*` do jogo aceitam `world` no lugar de `mm`
aqui (eles só chamam `.get_pool(nome)`).

Uso: python smoke_mastery.py
"""
import math

import numpy as np

import bullethell  # noqa: F401 — engine no sys.path
from bullethell.composition import build_headless
from bullethell.game_systems import spawn_enemy_bullet

DT = 1 / 60


def check(label: str, cond: bool) -> bool:
    print(f"[{'OK ' if cond else 'FAIL'}] {label}")
    return cond


def mastery(world):
    return world.get_pool("mastery").active_view()


def player_pos(world):
    pl = world.get_pool("player")
    tp = world.get_pool("transform")
    prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
    tv = tp.active_view()
    return float(tv["position_x"][prow]), float(tv["position_y"][prow])


def boss_pos(world):
    bp = world.get_pool("boss")
    tp = world.get_pool("transform")
    brow = tp.dense_row_of(int(bp.active_entity_indices()[0]))
    tv = tp.active_view()
    return float(tv["position_x"][brow]), float(tv["position_y"][brow])


def step_idle(world, inp, n=1):
    for _ in range(n):
        inp.poll()
        world.step(DT)


def follow_boss_and_step(world, inp, offset_y, n):
    """Gruda o jogador na posição ATUAL do boss a cada frame (o Clássico
    anda entre waypoints — sem isso o jogador perde o alvo por movimento
    do boss, não por falha do sistema testado)."""
    tp = world.get_pool("transform")
    pl = world.get_pool("player")
    prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
    for _ in range(n):
        bx, by = boss_pos(world)
        tv = tp.active_view()
        tv["position_x"][prow] = bx
        tv["position_y"][prow] = by + offset_y
        inp.poll(); world.step(DT)


if __name__ == "__main__":
    ok = True

    # --- EMP+: destrua N balas numa única ativação (max) --------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="emp", mode="classic")
    px, py = player_pos(world)
    for j in range(20):
        a = j * (math.tau / 20)
        spawn_enemy_bullet(world, world, px + math.cos(a) * 60,
                           py + math.sin(a) * 60, 0.0, 0.0)
    inp.set_action_held("skill", True)
    step_idle(world, inp)
    mv = mastery(world)
    ok &= check("EMP: destrói o anel de 20 balas numa ativação",
               int(mv["emp_max"][0]) == 20)

    # --- PARRY+: reflete N balas numa única janela (max) --------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="parry", mode="classic")
    px, py = player_pos(world)
    for j in range(6):
        a = j * (math.tau / 6)
        spawn_enemy_bullet(world, world, px + math.cos(a) * 10,
                           py + math.sin(a) * 10, 0.0, 0.0)
    inp.set_action_held("skill", True)
    step_idle(world, inp)
    mv = mastery(world)
    ok &= check("PARRY: reflete o grupo de 6 balas numa janela",
               int(mv["parry_burst_max"][0]) == 6)

    # --- DILATAÇÃO+: ativa com uma bala bem colada no jogador ----------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="timedil", mode="classic")
    px, py = player_pos(world)
    spawn_enemy_bullet(world, world, px + 2.0, py, 0.0, 0.0)
    inp.set_action_held("skill", True)
    step_idle(world, inp)
    mv = mastery(world)
    ok &= check("DILATAÇÃO: marca timedil_close com bala a 2px",
               bool(mv["timedil_close"][0]))

    # --- ESCUDO+: bloco perfeito (<0.15s) ------------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="shield+", mode="classic")
    inp.set_action_held("skill", True)
    step_idle(world, inp)                     # ativa o escudo (skill_age=0)
    inp.set_action_held("skill", False)
    px, py = player_pos(world)
    spawn_enemy_bullet(world, world, px, py, 0.0, 0.0)   # hit imediato: <0.15s
    step_idle(world, inp)
    mv = mastery(world)
    ok &= check("ESCUDO: bloco a <0.15s conta como perfeito",
               int(mv["shield_perfects"][0]) == 1)

    # --- BLINK+: teleporte atravessando o corpo do boss ----------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="blink", mode="classic")
    bx, by = boss_pos(world)
    tp = world.get_pool("transform")
    pl = world.get_pool("player")
    prow = tp.dense_row_of(int(pl.active_entity_indices()[0]))
    tv = tp.active_view()
    tv["position_x"][prow] = bx
    tv["position_y"][prow] = by + 150.0        # 150px abaixo do boss
    inp.set_action_held("move_up", True)        # blink de 190px pra cima
    inp.set_action_held("skill", True)
    step_idle(world, inp)
    mv = mastery(world)
    ok &= check("BLINK: teleporte de 190px atravessa o boss (150px de distância)",
               bool(mv["blink_pass"][0]))

    # --- DASH+: graze durante as i-frames ------------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="dash+", mode="classic")
    px, py = player_pos(world)
    inp.set_action_held("move_right", True)
    inp.set_action_held("skill", True)
    inp.poll(); world.step(DT)                 # ativa o dash (skill_t>0)
    inp.set_action_held("skill", False)
    inp.set_action_held("move_right", False)   # para de vez (senão a 1320px/s
                                                # o jogador passa direto pela bala)
    px, py = player_pos(world)                 # posição pós-1º frame de dash
    # zona de graze real: entre HIT_R (14) e GRAZE_R (26) — não HIT_R (senão
    # vira dano, não graze)
    spawn_enemy_bullet(world, world, px + 20.0, py, 0.0, 0.0)
    inp.poll(); world.step(DT)
    mv = mastery(world)
    ok &= check("DASH+: graze durante as i-frames conta para a mastery",
               int(mv["dash_graze"][0]) >= 1)

    # --- PADRÃO+: acertos consecutivos no boss --------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="none", mode="classic")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 40.0, 90)  # colado no boss, tiro reto acerta
    mv = mastery(world)
    ok &= check("PADRÃO: sequência de acertos consecutivos cresce",
               int(mv["default_max"][0]) >= 5)

    # --- SPREAD+: acertos a <40px do boss --------------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="spread",
                               skill_name="none", mode="classic")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 30.0, 90)
    mv = mastery(world)
    ok &= check("SPREAD: acertos <40px do boss acumulam spread_close",
               int(mv["spread_close"][0]) >= 1)

    # --- PLASMA+: contato contínuo -----------------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="plasma",
                               skill_name="none", mode="classic")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 25.0, 90)
    mv = mastery(world)
    ok &= check("PLASMA: contato contínuo acumula tempo (plasma_max > 0)",
               float(mv["plasma_max"][0]) > 0.0)

    # --- SATÉLITE+: dano total das gemas -------------------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="satelite",
                               skill_name="none", mode="classic")
    inp.set_action_held("fire", True)
    follow_boss_and_step(world, inp, 0.0, 180)  # gemas orbitam o boss direto
    mv = mastery(world)
    ok &= check("SATÉLITE: dano das gemas acumula orbit_damage",
               float(mv["orbit_damage"][0]) > 0.0)

    # --- OVERCLOCK+: dano numa única janela (max) ----------------------------
    world, inp = build_headless(boss_name="classic", weapon_name="padrao",
                               skill_name="overclock", mode="classic")
    inp.set_action_held("fire", True)
    inp.set_action_held("skill", True)
    follow_boss_and_step(world, inp, 40.0, 1)
    inp.set_action_held("skill", False)
    follow_boss_and_step(world, inp, 40.0, 90)  # janela de overclock (3s)
    mv = mastery(world)
    ok &= check("OVERCLOCK: dano acumulado na janela ativa (oc_dmg_max > 0)",
               float(mv["oc_dmg_max"][0]) > 0.0)

    raise SystemExit(0 if ok else 1)
