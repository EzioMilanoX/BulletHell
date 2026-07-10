"""
Sistemas de gameplay do Bullet Hell sobre a OuroborosEngine.

Seguem o contrato de `ISystem`: pools resolvidas UMA vez no __init__,
`update()` vetorizado via `active_view()`/`intersect_entity_indices`,
nenhuma instanciação de objeto Python por entidade no hot path.
Entidades trafegam como `PackedEntityId` (int primitivo); cada pool de
projétil guarda o próprio handle na coluna "self" para permitir
`world.destroy_entity` sem reconstruir generation.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from ouroboros.core.memory.component_pool import intersect_entity_indices
from ouroboros.core.memory.memory_manager import MemoryManager
from ouroboros.core.systems.base_system import ISystem
from ouroboros.interfaces.input_provider import IInputProvider

from bullethell.ids import sid
from bullethell.loaders import GameData, PatternDef
from bullethell.schemas import (
    BEH_BOOMERANG, BEH_NONE, BEH_SLEEPER, BEH_STOPGO,
    CONTACT_IF_MOVING, CONTACT_IF_STILL, CONTACT_NEVER,
    PALETTE, SCREEN_H, SCREEN_W,
)

if TYPE_CHECKING:
    from ouroboros.core.world import World

TWO_PI = math.tau
PLAYER_SPEED = 220.0
PLAYER_HIT_R = 10.0
PLAYER_GRAZE_R = 26.0
PLAYER_INVULN = 1.5
CULL_MARGIN = 24.0

# Armas selecionáveis pelas teclas 1..5 (as 5 "special" virão na fase 2)
WEAPON_KEYS = ("padrao", "spread", "agulha", "teleguiado", "plasma")


# ---------------------------------------------------------------------------
# util compartilhado (funções módulo-nível: sem estado, sem alocação de objeto)
# ---------------------------------------------------------------------------

def _player_row(player_pool, transform_pool):
    """(entity_index, transform_row) do jogador, ou (-1, -1)."""
    idx = player_pool.active_entity_indices()
    if idx.size == 0:
        return -1, -1
    i = int(idx[0])
    return i, transform_pool.dense_row_of(i)


# ===========================================================================
class PlayerControlSystem(ISystem):
    """Input → velocity do jogador; decrementos de timers do jogador."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider) -> None:
        self._input = input_provider
        self._player = memory_manager.get_pool("player")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")

    def update(self, world: "World", delta_time: float) -> None:
        i, _ = _player_row(self._player, self._transform)
        if i < 0:
            return
        dx = (1.0 if self._input.is_action_held("move_right") else 0.0) - \
             (1.0 if self._input.is_action_held("move_left") else 0.0)
        dy = (1.0 if self._input.is_action_held("move_down") else 0.0) - \
             (1.0 if self._input.is_action_held("move_up") else 0.0)
        if dx != 0.0 and dy != 0.0:
            dx *= 0.7071; dy *= 0.7071
        vrow = self._velocity.dense_row_of(i)
        vv = self._velocity.active_view()
        vv["linear_x"][vrow] = dx * PLAYER_SPEED
        vv["linear_y"][vrow] = dy * PLAYER_SPEED

        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        if pv["invuln_t"][prow] > 0.0:
            pv["invuln_t"][prow] -= delta_time
        if pv["fire_cd"][prow] > 0.0:
            pv["fire_cd"][prow] -= delta_time


# ===========================================================================
class WeaponFireSystem(ISystem):
    """Cadência + spawn de balas-entidade conforme weapons.json.
    A composição registra 1 arquétipo por arma ("pb_<nome>") com as pools
    da receita; aqui só se escolhe o arquétipo e se escrevem os valores."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider,
                 data: GameData) -> None:
        self._input = input_provider
        self._data = data
        self._mm = memory_manager
        self._player = memory_manager.get_pool("player")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._sprite = memory_manager.get_pool("sprite")
        self._pb_core = memory_manager.get_pool("pb_core")

    def update(self, world: "World", delta_time: float) -> None:
        i, trow = _player_row(self._player, self._transform)
        if i < 0:
            return
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()

        # troca de arma (teclas 1..5) e toggle da variante + (tecla P)
        for slot, wname in enumerate(WEAPON_KEYS):
            if self._input.is_action_pressed(f"weapon_{slot + 1}"):
                pv["weapon_id"][prow] = sid(wname)
        if self._input.is_action_pressed("toggle_plus"):
            cur = self._data.weapons.get(int(pv["weapon_id"][prow]))
            if cur is not None:
                target = cur.name[:-1] if cur.name.endswith("+") else cur.name + "+"
                if sid(target) in self._data.weapons:
                    pv["weapon_id"][prow] = sid(target)

        wd = self._data.weapons.get(int(pv["weapon_id"][prow]))
        if wd is None or wd.special:
            return                                  # armas "special": fase 2
        if not self._input.is_action_held("fire") or pv["fire_cd"][prow] > 0.0:
            return
        if self._pb_core.count + wd.shots >= self._pb_core.capacity:
            return                                  # pool de balas cheio
        pv["fire_cd"][prow] = wd.fire_rate

        tv = self._transform.active_view()
        px = float(tv["position_x"][trow])
        py = float(tv["position_y"][trow])
        base = -math.pi / 2
        n = wd.shots
        for k in range(n):
            th = base if n == 1 else base - wd.arc / 2 + wd.arc * k / (n - 1)
            packed = world.create_entity("pb_" + wd.name)
            idx = packed & 0xFFFFFFFF
            row_t = self._transform.dense_row_of(idx)
            tv2 = self._transform.active_view()
            tv2["position_x"][row_t] = px
            tv2["position_y"][row_t] = py
            tv2["scale_x"][row_t] = tv2["scale_y"][row_t] = wd.size / 4.0
            row_v = self._velocity.dense_row_of(idx)
            vv = self._velocity.active_view()
            vv["linear_x"][row_v] = math.cos(th) * wd.speed
            vv["linear_y"][row_v] = math.sin(th) * wd.speed
            row_s = self._sprite.dense_row_of(idx)
            sv = self._sprite.active_view()
            sv["tint_r"][row_s], sv["tint_g"][row_s], sv["tint_b"][row_s] = 120, 220, 255
            sv["tint_a"][row_s] = 255
            sv["layer_z"][row_s] = 5
            row_c = self._pb_core.dense_row_of(idx)
            cv = self._pb_core.active_view()
            cv["self"][row_c] = np.uint64(packed)
            cv["damage"][row_c] = wd.damage
            cv["radius"][row_c] = wd.size
            for pool_name, fields in wd.init:      # pools extras da receita
                pool = self._mm.get_pool(pool_name)
                row = pool.dense_row_of(idx)
                view = pool.active_view()
                for fname, fval in fields:
                    view[fname][row] = fval


# ===========================================================================
class WaypointSystem(ISystem):
    """Movimento de boss por waypoints com easing smoothstep (bosses.json)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._boss = memory_manager.get_pool("boss")
        self._waypoint = memory_manager.get_pool("waypoint")
        self._transform = memory_manager.get_pool("transform")

    def update(self, world: "World", delta_time: float) -> None:
        indices = intersect_entity_indices(self._boss, self._waypoint, self._transform)
        for raw in indices:                        # ≤2 bosses: loop primitivo
            i = int(raw)
            bdef = self._data.bosses[int(self._boss.active_view()["boss_id"][self._boss.dense_row_of(i)])]
            route = bdef.route
            if len(route) < 2:
                continue
            wrow = self._waypoint.dense_row_of(i)
            wv = self._waypoint.active_view()
            seg = int(wv["seg"][wrow])
            x0, y0, _ = route[seg % len(route)]
            x1, y1, dur = route[(seg + 1) % len(route)]
            wv["seg_t"][wrow] += delta_time
            u = min(float(wv["seg_t"][wrow]) / dur, 1.0)
            s = u * u * (3.0 - 2.0 * u)
            trow = self._transform.dense_row_of(i)
            tv = self._transform.active_view()
            tv["position_x"][trow] = x0 + (x1 - x0) * s
            tv["position_y"][trow] = y0 + (y1 - y0) * s
            if u >= 1.0:
                wv["seg"][wrow] = seg + 1
                wv["seg_t"][wrow] = 0.0


# ===========================================================================
class BossPhaseSystem(ISystem):
    """Troca o conjunto de emitters quando hp/max cruza o threshold da
    próxima fase; em hp<=0 reinicia o boss (loop infinito de treino)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._boss = memory_manager.get_pool("boss")
        self._emitter = memory_manager.get_pool("emitter")

    def update(self, world: "World", delta_time: float) -> None:
        for raw in self._boss.active_entity_indices():
            i = int(raw)
            brow = self._boss.dense_row_of(i)
            bv = self._boss.active_view()
            bdef = self._data.bosses[int(bv["boss_id"][brow])]
            frac = float(bv["hp"][brow]) / float(bv["max_hp"][brow])
            phase = int(bv["phase_idx"][brow])
            if bv["hp"][brow] <= 0.0:              # derrotado → reinicia
                bv["hp"][brow] = bv["max_hp"][brow]
                bv["phase_idx"][brow] = 0
                self._swap_emitters(world, i, bdef.phases[0])
                continue
            nxt = phase + 1
            if nxt < len(bdef.phases) and frac <= bdef.phases[phase].hp_above:
                bv["phase_idx"][brow] = nxt
                self._swap_emitters(world, i, bdef.phases[nxt])

    def _swap_emitters(self, world: "World", boss_index: int, phase_def) -> None:
        ev = self._emitter.active_view()
        parents = ev["parent"][: self._emitter.count]
        for k in range(self._emitter.count):       # ≤32 emitters
            if int(parents[k]) & 0xFFFFFFFF == boss_index:
                world.destroy_entity(int(ev["self"][k]))
        spawn_emitters(world, self._emitter, boss_index, phase_def)


def spawn_emitters(world: "World", emitter_pool, boss_index: int, phase_def) -> None:
    """Cria as entidades-emitter de uma fase (usado na composição e na troca).
    `parent` guarda apenas o index do boss (generation irrelevante aqui:
    o boss nunca é destruído durante a luta)."""
    for pattern_sid, off_x, off_y in phase_def.emitters:
        packed = world.create_entity("emitter")
        idx = packed & 0xFFFFFFFF
        row = emitter_pool.dense_row_of(idx)
        view = emitter_pool.active_view()
        view["self"][row] = np.uint64(packed)
        view["pattern_id"][row] = pattern_sid
        view["t"][row] = 0.0
        view["phase_angle"][row] = 0.0
        view["shot_count"][row] = 0
        view["parent"][row] = np.uint64(boss_index)
        view["off_x"][row] = off_x
        view["off_y"][row] = off_y


# ===========================================================================
class EmitterSystem(ISystem):
    """Executa PatternDefs: spawna balas inimigas como ENTIDADES, escrevendo
    as colunas do arquétipo (bullet_archetypes.json). Emissões `laser` e
    `pair` ficam para a fase 2 do port (ver MIGRATION.md)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._emitter = memory_manager.get_pool("emitter")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._sprite = memory_manager.get_pool("sprite")
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        pi, ptrow = _player_row(self._player, self._transform)
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]) if ptrow >= 0 else SCREEN_W / 2
        py = float(tv["position_y"][ptrow]) if ptrow >= 0 else SCREEN_H * 0.8

        for k in range(self._emitter.count):       # ≤32 emitters
            ev = self._emitter.active_view()
            if ev["warmup"][k] > 0.0:
                ev["warmup"][k] -= delta_time
                continue
            pat = self._data.patterns[int(ev["pattern_id"][k])]
            ev["t"][k] += delta_time
            # origem = transform do boss-pai + offset
            parent_idx = int(ev["parent"][k]) & 0xFFFFFFFF
            prow = self._transform.dense_row_of(parent_idx)
            if prow < 0:
                continue
            ox = float(tv["position_x"][prow]) + float(ev["off_x"][k])
            oy = float(tv["position_y"][prow]) + float(ev["off_y"][k])
            while ev["t"][k] >= pat.period:
                ev["t"][k] -= pat.period
                self._emit(world, k, pat, ox, oy, px, py)

    # -- formas de emissão --------------------------------------------------

    def _emit(self, world, k, pat: PatternDef, ox, oy, px, py) -> None:
        ev = self._emitter.active_view()
        if pat.emit == "arc":
            aim = math.atan2(py - oy, px - ox) if pat.aim == "player" else math.pi / 2
            n = pat.count
            for j in range(n):
                th = aim if n == 1 else aim - pat.arc / 2 + pat.arc * j / (n - 1)
                self._spawn(world, pat, ox, oy, th, px, py)
        elif pat.emit == "ring":
            gap_c = 0.0
            if pat.gap > 0.0:
                to_p = math.atan2(py - oy, px - ox)
                gap_c = to_p + math.pi / 2 + float(ev["shot_count"][k]) * pat.gap_step
            ev["shot_count"][k] += 1
            for j in range(pat.count):
                th = j * (TWO_PI / pat.count)
                if pat.gap > 0.0:
                    d = abs(((th - gap_c + math.pi) % TWO_PI) - math.pi)
                    if d <= pat.gap / 2:
                        continue
                self._spawn(world, pat, ox, oy, th, px, py)
        elif pat.emit == "spiral":
            ev["phase_angle"][k] += pat.spin_speed * pat.period
            for j in range(pat.arms):
                th = float(ev["phase_angle"][k]) + j * (TWO_PI / pat.arms)
                self._spawn(world, pat, ox, oy, th, px, py)
        elif pat.emit == "rain":
            col_w = SCREEN_W / pat.count
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            for j in range(pat.count):
                # gap determinístico barato (hash inteiro), sem RNG global
                if ((seed * 2654435761 + j * 40503) & 0xFF) < int(pat.gap * 256):
                    continue
                self._spawn(world, pat, (j + 0.5) * col_w, -8.0, math.pi / 2, px, py)
        elif pat.emit == "stream":
            if pat.track == "player_x":
                ev["phase_angle"][k] += (px - float(ev["phase_angle"][k])) * 0.12
                ox = float(ev["phase_angle"][k])
            self._spawn(world, pat, ox, oy, math.pi / 2, px, py)
        # "laser"/"pair": fase 2 do port

    def _spawn(self, world, pat: PatternDef, x, y, theta, px, py) -> None:
        if self._eb.count >= self._eb.capacity - 1:
            return                                  # pool cheio: descarta
        arch = self._data.archetypes[pat.bullet]
        packed = world.create_entity("enemy_bullet")
        idx = packed & 0xFFFFFFFF
        trow = self._transform.dense_row_of(idx)
        tv = self._transform.active_view()
        tv["position_x"][trow] = x
        tv["position_y"][trow] = y
        tv["scale_x"][trow] = tv["scale_y"][trow] = arch.radius / 4.0
        vrow = self._velocity.dense_row_of(idx)
        vv = self._velocity.active_view()
        vv["linear_x"][vrow] = math.cos(theta) * pat.speed
        vv["linear_y"][vrow] = math.sin(theta) * pat.speed
        srow = self._sprite.dense_row_of(idx)
        sv = self._sprite.active_view()
        r, g, b = PALETTE.get(arch.color, (255, 64, 90))
        sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = r, g, b
        sv["tint_a"][srow] = 255
        sv["layer_z"][srow] = 10
        erow = self._eb.dense_row_of(idx)
        eb = self._eb.active_view()
        eb["self"][erow] = np.uint64(packed)
        eb["contact"][erow] = arch.contact
        eb["radius"][erow] = arch.radius
        eb["grazed"][erow] = 0
        eb["homing_t"][erow] = arch.homing_t
        eb["spin"][erow] = arch.spin
        eb["phase_p"][erow] = arch.phase_period
        eb["phase_t"][erow] = 0.0
        eb["gravity"][erow] = arch.gravity
        eb["bounces"][erow] = arch.bounces
        eb["beh"][erow] = arch.beh
        eb["beh_t"][erow] = arch.p1
        eb["p1"][erow], eb["p2"][erow], eb["p3"][erow] = arch.p1, arch.p2, arch.p3
        eb["tgt_x"][erow], eb["tgt_y"][erow] = px, py   # snapshot p/ stop&go
        eb["stage"][erow] = 0


# ===========================================================================
class EnemyBulletBehaviorSystem(ISystem):
    """Kernel vetorizado dos comportamentos de bala inimiga: homing, spin,
    phase, gravity (puxa o jogador), stop&go, boomerang, sleeper."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._eb.count
        if n == 0:
            return
        eb = self._eb.active_view()
        indices = self._eb.active_entity_indices()
        trows = self._transform.dense_rows_of(indices)
        vrows = self._velocity.dense_rows_of(indices)
        tv = self._transform.active_view()
        vv = self._velocity.active_view()

        pi, ptrow = _player_row(self._player, self._transform)
        px = float(tv["position_x"][ptrow]) if ptrow >= 0 else SCREEN_W / 2
        py = float(tv["position_y"][ptrow]) if ptrow >= 0 else SCREEN_H * 0.8

        bx = tv["position_x"][trows]
        by = tv["position_y"][trows]

        # HOMING → curva ao jogador
        h = eb["homing_t"] > 0.0
        if h.any():
            eb["homing_t"][h] -= delta_time
            dx = px - bx[h]; dy = py - by[h]
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            vv["linear_x"][vrows[h]] += (dx / d) * 260.0 * delta_time
            vv["linear_y"][vrows[h]] += (dy / d) * 260.0 * delta_time

        # SPIN → rotaciona vetor velocidade
        s = eb["spin"] != 0.0
        if s.any():
            ang = eb["spin"][s] * delta_time
            c, sn = np.cos(ang), np.sin(ang)
            vx = vv["linear_x"][vrows[s]].copy()
            vy = vv["linear_y"][vrows[s]]
            vv["linear_x"][vrows[s]] = vx * c - vy * sn
            vv["linear_y"][vrows[s]] = vx * sn + vy * c

        # PHASE → acumula relógio (solidez lida pelo PlayerHitSystem)
        p = eb["phase_p"] > 0.0
        eb["phase_t"][p] += delta_time

        # GRAVITY → desloca o jogador (campo de atração)
        g = eb["gravity"] > 0.0
        if g.any() and ptrow >= 0:
            dx = px - bx[g]; dy = py - by[g]
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            tv["position_x"][ptrow] -= float(np.sum(dx / d * eb["gravity"][g])) * delta_time
            tv["position_y"][ptrow] -= float(np.sum(dy / d * eb["gravity"][g])) * delta_time

        # Máquina de estados STOP&GO / BOOMERANG / SLEEPER (vetorizada)
        beh = eb["beh"] != BEH_NONE
        if beh.any():
            eb["beh_t"][beh] -= delta_time
            fired = beh & (eb["beh_t"] <= 0.0)
            if fired.any():
                # STOPGO estágio 0: para e espera p2
                m = fired & (eb["beh"] == BEH_STOPGO) & (eb["stage"] == 0)
                if m.any():
                    vv["linear_x"][vrows[m]] = 0.0
                    vv["linear_y"][vrows[m]] = 0.0
                    eb["stage"][m] = 1
                    eb["beh_t"][m] = eb["p2"][m]
                # STOPGO estágio 1: relança ao snapshot a p3 px/s
                m = fired & (eb["beh"] == BEH_STOPGO) & (eb["stage"] == 1) & (eb["beh_t"] <= 0.0)
                # (recalcula beh_t<=0 pois o estágio 0 acima reescreveu)
                m &= eb["beh_t"] <= 0.0
                if m.any():
                    dx = eb["tgt_x"][m] - bx[m]; dy = eb["tgt_y"][m] - by[m]
                    d = np.sqrt(dx * dx + dy * dy) + 1e-6
                    vv["linear_x"][vrows[m]] = dx / d * eb["p3"][m]
                    vv["linear_y"][vrows[m]] = dy / d * eb["p3"][m]
                    eb["beh"][m] = BEH_NONE
                # BOOMERANG: inverte ×p2
                m = fired & (eb["beh"] == BEH_BOOMERANG)
                if m.any():
                    vv["linear_x"][vrows[m]] *= -eb["p2"][m]
                    vv["linear_y"][vrows[m]] *= -eb["p2"][m]
                    eb["beh"][m] = BEH_NONE
                # SLEEPER: acorda mirando o jogador a p2 px/s
                m = fired & (eb["beh"] == BEH_SLEEPER)
                if m.any():
                    dx = px - bx[m]; dy = py - by[m]
                    d = np.sqrt(dx * dx + dy * dy) + 1e-6
                    vv["linear_x"][vrows[m]] = dx / d * eb["p2"][m]
                    vv["linear_y"][vrows[m]] = dy / d * eb["p2"][m]
                    eb["beh"][m] = BEH_NONE


# ===========================================================================
class MaintenanceSystem(ISystem):
    """Pós-movimento: ricochete/cull de balas inimigas, timers e cull de
    balas do jogador, clamp do jogador na tela."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_range = memory_manager.get_pool("pb_range")
        self._pb_life = memory_manager.get_pool("pb_life")
        self._pb_pierce = memory_manager.get_pool("pb_pierce")
        self._pb_bounce = memory_manager.get_pool("pb_bounce")

    def update(self, world: "World", delta_time: float) -> None:
        tv = self._transform.active_view()
        vv = self._velocity.active_view()

        # ---- balas inimigas: ricochete lateral + cull fora da tela -------
        n = self._eb.count
        if n:
            eb = self._eb.active_view()
            idx = self._eb.active_entity_indices()
            trows = self._transform.dense_rows_of(idx)
            vrows = self._velocity.dense_rows_of(idx)
            bx = tv["position_x"][trows]; by = tv["position_y"][trows]
            can_bounce = eb["bounces"] > 0
            hit_wall = can_bounce & ((bx < 0) | (bx > SCREEN_W))
            if hit_wall.any():
                vv["linear_x"][vrows[hit_wall]] *= -1.0
                eb["bounces"][hit_wall] -= 1
            out = ((bx < -CULL_MARGIN) | (bx > SCREEN_W + CULL_MARGIN) |
                   (by < -CULL_MARGIN) | (by > SCREEN_H + CULL_MARGIN))
            out &= ~hit_wall
            for h in eb["self"][out]:              # destruição enfileirada
                world.destroy_entity(int(h))

        # ---- balas do jogador: timers, ricochete PADRÃO+, cull ------------
        n = self._pb_core.count
        if n:
            cv = self._pb_core.active_view()
            idx = self._pb_core.active_entity_indices()
            trows = self._transform.dense_rows_of(idx)
            vrows = self._velocity.dense_rows_of(idx)
            bx = tv["position_x"][trows]; by = tv["position_y"][trows]
            dead = np.zeros(n, dtype=bool)

            # SPREAD+ alcance
            rrows = self._pb_range.dense_rows_of(idx)
            has_r = rrows != -1
            if has_r.any():
                rv = self._pb_range.active_view()
                rv["t"][rrows[has_r]] -= delta_time
                dead |= has_r & np.where(has_r, rv["t"][np.where(has_r, rrows, 0)] <= 0.0, False)

            # PLASMA lifespan
            lrows = self._pb_life.dense_rows_of(idx)
            has_l = lrows != -1
            if has_l.any():
                lv = self._pb_life.active_view()
                lv["t"][lrows[has_l]] -= delta_time
                dead |= has_l & np.where(has_l, lv["t"][np.where(has_l, lrows, 0)] <= 0.0, False)

            # AGULHA+ cooldown de pierce
            prows = self._pb_pierce.dense_rows_of(idx)
            has_p = prows != -1
            if has_p.any():
                pv = self._pb_pierce.active_view()
                cd = pv["t"][prows[has_p]] - delta_time
                pv["t"][prows[has_p]] = np.maximum(cd, 0.0)

            # PADRÃO+ ricochete nas paredes laterais
            brows = self._pb_bounce.dense_rows_of(idx)
            has_b = brows != -1
            if has_b.any():
                bv = self._pb_bounce.active_view()
                wall = has_b & ((bx < 0) | (bx > SCREEN_W))
                if wall.any():
                    left = bv["left"][brows[wall]]
                    can = left > 0
                    w_idx = np.where(wall)[0][can]
                    vv["linear_x"][vrows[w_idx]] *= -1.0
                    bv["left"][brows[w_idx]] -= 1
                    no_more = np.where(wall)[0][~can]
                    dead[no_more] = True

            out = ((bx < -CULL_MARGIN) | (bx > SCREEN_W + CULL_MARGIN) |
                   (by < -CULL_MARGIN) | (by > SCREEN_H + CULL_MARGIN))
            has_bounce_left = np.zeros(n, dtype=bool)
            if has_b.any():
                bv = self._pb_bounce.active_view()
                has_bounce_left[has_b] = bv["left"][brows[has_b]] > 0
            dead |= out & ~has_bounce_left
            for h in cv["self"][dead]:
                world.destroy_entity(int(h))

        # ---- clamp do jogador ---------------------------------------------
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow >= 0:
            tv["position_x"][ptrow] = min(max(float(tv["position_x"][ptrow]), 9.0), SCREEN_W - 9.0)
            tv["position_y"][ptrow] = min(max(float(tv["position_y"][ptrow]), 9.0), SCREEN_H - 9.0)


# ===========================================================================
class PlayerHitSystem(ISystem):
    """Jogador × balas inimigas: check vetorizado completo (regras de
    contato Yin/Yang, janela sólida do phaser, graze no anel externo)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        if self._eb.count == 0:
            return
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        pvrow = self._velocity.dense_row_of(i)
        vvv = self._velocity.active_view()
        moving = abs(float(vvv["linear_x"][pvrow])) + abs(float(vvv["linear_y"][pvrow])) > 1e-3

        eb = self._eb.active_view()
        idx = self._eb.active_entity_indices()
        trows = self._transform.dense_rows_of(idx)
        dx = tv["position_x"][trows] - px
        dy = tv["position_y"][trows] - py
        d2 = dx * dx + dy * dy

        harmful = eb["contact"] != CONTACT_NEVER
        if moving:
            harmful &= eb["contact"] != CONTACT_IF_STILL
        else:
            harmful &= eb["contact"] != CONTACT_IF_MOVING
        ph = eb["phase_p"] > 0.0
        if ph.any():
            solid = np.mod(eb["phase_t"][ph], eb["phase_p"][ph]) < eb["phase_p"][ph] * 0.5
            hm = harmful[ph]
            harmful[np.where(ph)[0][~solid & hm]] = False

        hit_r2 = (PLAYER_HIT_R + eb["radius"]) ** 2
        hits = harmful & (d2 <= hit_r2)

        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        if hits.any():
            for h in eb["self"][hits]:
                world.destroy_entity(int(h))
            if pv["invuln_t"][prow] <= 0.0:
                pv["invuln_t"][prow] = PLAYER_INVULN
                pv["lives"][prow] -= 1
                if pv["lives"][prow] < 0:          # game over → reset da run
                    pv["lives"][prow] = 3
                    for h in eb["self"][: self._eb.count]:
                        world.destroy_entity(int(h))
                    return

        graze = (eb["grazed"] == 0) & harmful & (d2 <= PLAYER_GRAZE_R ** 2) & (d2 > hit_r2)
        cnt = int(graze.sum())
        if cnt:
            eb["grazed"][graze] = 1
            pv["graze"][prow] += cnt


# ===========================================================================
class PlayerBulletVsBossSystem(ISystem):
    """Balas do jogador × AABB do boss: dano normal consome; AGULHA+
    atravessa com cooldown; PLASMA aplica DPS sem nunca ser consumida
    (a regra que corrigiu o bug do plasma no legado)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_pierce = memory_manager.get_pool("pb_pierce")
        self._pb_dot = memory_manager.get_pool("pb_dot")
        self._transform = memory_manager.get_pool("transform")
        self._hitbox = memory_manager.get_pool("hitbox")
        self._boss = memory_manager.get_pool("boss")

    def update(self, world: "World", delta_time: float) -> None:
        if self._pb_core.count == 0 or self._boss.count == 0:
            return
        tv = self._transform.active_view()
        pb_idx = self._pb_core.active_entity_indices()
        pb_trows = self._transform.dense_rows_of(pb_idx)
        bxs = tv["position_x"][pb_trows]
        bys = tv["position_y"][pb_trows]
        cv = self._pb_core.active_view()

        for raw in self._boss.active_entity_indices():
            bi = int(raw)
            btrow = self._transform.dense_row_of(bi)
            hrow = self._hitbox.dense_row_of(bi)
            if btrow < 0 or hrow < 0:
                continue
            hv = self._hitbox.active_view()
            cx = float(tv["position_x"][btrow]); cy = float(tv["position_y"][btrow])
            hw = float(hv["half_width"][hrow]); hh = float(hv["half_height"][hrow])
            inside = ((bxs >= cx - hw) & (bxs <= cx + hw) &
                      (bys >= cy - hh) & (bys <= cy + hh))
            if not inside.any():
                continue

            brow = self._boss.dense_row_of(bi)
            bv = self._boss.active_view()

            # PLASMA (DoT): dano contínuo, bala nunca consumida
            drows = self._pb_dot.dense_rows_of(pb_idx)
            is_dot = drows != -1
            dot_in = inside & is_dot
            if dot_in.any():
                dv = self._pb_dot.active_view()
                total_dps = float(np.sum(dv["dps"][drows[dot_in]]))
                bv["hp"][brow] -= total_dps * delta_time

            # Dano de impacto (consome, exceto pierce em cooldown)
            prows = self._pb_pierce.dense_rows_of(pb_idx)
            is_pierce = prows != -1
            impact = inside & ~is_dot
            if impact.any():
                pv = self._pb_pierce.active_view()
                # pierce pronto: causa dano e entra em CD (não consome)
                pierce_ready = impact & is_pierce
                if pierce_ready.any():
                    ready = pv["t"][prows[pierce_ready]] <= 0.0
                    rows_sel = np.where(pierce_ready)[0][ready]
                    bv["hp"][brow] -= float(np.sum(cv["damage"][rows_sel]))
                    pv["t"][prows[rows_sel]] = pv["cd"][prows[rows_sel]]
                # bala normal: dano + destruição
                normal = impact & ~is_pierce
                if normal.any():
                    bv["hp"][brow] -= float(np.sum(cv["damage"][normal]))
                    for h in cv["self"][normal]:
                        world.destroy_entity(int(h))


# ===========================================================================
class PlayerBulletHomingSystem(ISystem):
    """TELEGUIADO: curva as balas com pb_homing em direção ao boss."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._pb_homing = memory_manager.get_pool("pb_homing")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._boss = memory_manager.get_pool("boss")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pb_homing.count
        if n == 0 or self._boss.count == 0:
            return
        bi = int(self._boss.active_entity_indices()[0])
        btrow = self._transform.dense_row_of(bi)
        tv = self._transform.active_view()
        bx = float(tv["position_x"][btrow]); by = float(tv["position_y"][btrow])

        hv = self._pb_homing.active_view()
        idx = self._pb_homing.active_entity_indices()
        trows = self._transform.dense_rows_of(idx)
        vrows = self._velocity.dense_rows_of(idx)
        vv = self._velocity.active_view()

        act = hv["t"] > 0.0
        if not act.any():
            return
        hv["t"][act] -= delta_time
        dx = bx - tv["position_x"][trows[act]]
        dy = by - tv["position_y"][trows[act]]
        d = np.sqrt(dx * dx + dy * dy) + 1e-6
        vv["linear_x"][vrows[act]] += (dx / d) * hv["turn"][act] * delta_time
        vv["linear_y"][vrows[act]] += (dy / d) * hv["turn"][act] * delta_time
        spd = np.sqrt(vv["linear_x"][vrows[act]] ** 2 + vv["linear_y"][vrows[act]] ** 2) + 1e-6
        over = spd > hv["vmax"][act]
        if over.any():
            rows_over = vrows[act][over]
            f = hv["vmax"][act][over] / spd[over]
            vv["linear_x"][rows_over] *= f
            vv["linear_y"][rows_over] *= f
