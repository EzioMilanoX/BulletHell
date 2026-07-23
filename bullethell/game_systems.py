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

import dataclasses
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
    CHAKRAM_FROZEN, CHAKRAM_OUT, CHAKRAM_RETURN,
    CONTACT_IF_MOVING, CONTACT_IF_STILL, CONTACT_NEVER,
    LASER_H, LASER_V, MINION_BUBBLE, MINION_KAMIKAZE, MINION_MINE,
    MINION_SENTINEL, ORBIT_GEM, ORBIT_HELD, PALETTE, SCREEN_H, SCREEN_W,
    SFX_BOOM, SFX_EMP, SFX_HIT, SFX_MINE, SFX_SHIELD, TETHER_NONE,
)

if TYPE_CHECKING:
    from ouroboros.core.world import World

TWO_PI = math.tau
PLAYER_SPEED = 220.0
PLAYER_HIT_R = 10.0
PLAYER_GRAZE_R = 26.0
PLAYER_INVULN = 1.5
CULL_MARGIN = 24.0

# constantes das armas special (legado)
CHARGED_MAX_T = 2.5
CHARGED_MIN_DMG, CHARGED_MAX_DMG = 2.0, 8.0
CHARGED_MIN_SZ, CHARGED_MAX_SZ = 5.0, 14.0
CHARGED_PLUS_FRAC = 0.85
BURST_INTERVAL = 0.05
FLAK_SHRAP_N, FLAK_SHRAP_SPD, FLAK_SHRAP_DMG = 5, 400.0, 0.4
FLAK_SHRAP_ARC = 0.698                       # 40°
CHAKRAM_DRAG, CHAKRAM_CATCH_R = 1600.0, 22.0
ORBIT_MAX_GEMS, SWARM_MAX_HELD = 4, 8
INTERCEPT_RANGE, INTERCEPT_CD = 250.0, 2.5
# bosses compostos / lasers (legado)
SWARM_ORBIT_SPEED = 0.75          # rad/s do triângulo
WALL_DESCENT_SPEED = 150.0        # px/s
WALL_MAX_Y = 216.0
SUMMONER_TELEPORT_CD = 4.2        # s entre teleportes do Invocador
MINION_RADIUS = 10.0              # semi-extensão do lacaio (20px)
BUBBLE_EXPLODE_T = 8.0            # Preguiça: bolha estoura sozinha após 8s
BUBBLE_BURST_N, BUBBLE_BURST_SPD = 12, 120.0   # anel ao estourar (fixo, sem speed_mult)
# Soberba (Pride): holofote
SPOT_HALF = 44.0                  # meia-largura do holofote (88px)
SPOT_SWEEP = 95.0                 # px/s de varredura

# Boss Rush (legado: BOSS_RUSH_ORDER e SINS Rush → desbloqueia ABISSAL)
RUSH_ORDERS = {
    1: ("classic", "swarm", "wall", "timemage", "twins", "summoner", "omega"),
    2: ("pride", "sloth", "envy", "gluttony", "greed", "lust", "wrath", "sin"),
}
SINS_RUSH_HP_SCALE = 1.15   # legado: hp_scale_per_stage do SINS Rush (spec §11)

_MINION_COLORS = {
    MINION_KAMIKAZE: (255, 120, 60),
    MINION_SENTINEL: (170, 170, 220),   # fantasmas da Preguiça
    MINION_BUBBLE:   (120, 200, 230),   # bolhas-sentinela
    MINION_MINE:     (255, 215, 0),     # moedas da Avareza / minas do Pecado
}


def spawn_enemy_bullet(world: "World", mm: MemoryManager, x: float, y: float,
                       vx: float, vy: float, color: int = 0,
                       radius: float = 4.0, bounces: int = 0,
                       homing_t: float = 0.0) -> int:
    """Spawna uma bala inimiga 'simples' fora do EmitterSystem (explosões
    de minas, anéis de slam, Sétimo Selo). Escreve TODAS as colunas."""
    eb = mm.get_pool("enemy_bullet")
    if eb.count >= eb.capacity - 1:
        return -1
    packed = world.create_entity("enemy_bullet")
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform")
    trow = t.dense_row_of(idx); tv = t.active_view()
    tv["position_x"][trow] = x
    tv["position_y"][trow] = y
    tv["scale_x"][trow] = tv["scale_y"][trow] = radius / 4.0
    v = mm.get_pool("velocity")
    vrow = v.dense_row_of(idx); vv = v.active_view()
    vv["linear_x"][vrow] = vx
    vv["linear_y"][vrow] = vy
    s = mm.get_pool("sprite")
    srow = s.dense_row_of(idx); sv = s.active_view()
    sv["texture_id"][srow] = SHAPE_CIRCLE
    r, g, b = PALETTE.get(color, (255, 64, 90))
    sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = r, g, b
    sv["tint_a"][srow] = 255
    sv["layer_z"][srow] = 10
    erow = eb.dense_row_of(idx); ev = eb.active_view()
    ev["self"][erow] = np.uint64(packed)
    ev["tether"][erow] = TETHER_NONE
    ev["color"][erow] = color
    ev["contact"][erow] = 0
    ev["radius"][erow] = radius
    ev["grazed"][erow] = 0
    ev["homing_t"][erow] = homing_t
    ev["spin"][erow] = 0.0
    ev["phase_p"][erow] = 0.0
    ev["phase_t"][erow] = 0.0
    ev["gravity"][erow] = 0.0
    ev["bounces"][erow] = bounces
    ev["fragment"][erow] = 0
    ev["beh"][erow] = BEH_NONE
    ev["beh_t"][erow] = 0.0
    ev["p1"][erow] = ev["p2"][erow] = ev["p3"][erow] = 0.0
    ev["tgt_x"][erow] = ev["tgt_y"][erow] = 0.0
    ev["stage"][erow] = 0
    return packed


SHAPE_RECT, SHAPE_CIRCLE = 0, 1   # ouroboros.interfaces.renderer


def add_shake(mm: MemoryManager, amount: float) -> None:
    """Acumula screen shake no clock (a cena decai e aplica o offset)."""
    ck = mm.get_pool("clock")
    if ck.count:
        ck.active_view()["shake"][0] = min(
            18.0, float(ck.active_view()["shake"][0]) + amount)


def add_sfx(mm: MemoryManager, bit: int) -> None:
    """Marca um evento sonoro no bitmask do frame (a cena toca e limpa)."""
    ck = mm.get_pool("clock")
    if ck.count:
        ck.active_view()["sfx"][0] |= bit


def spawn_particles(world: "World", mm: MemoryManager, x: float, y: float,
                    color, n: int, speed: float = 160.0,
                    ttl: float = 0.45, seed: int = 0) -> None:
    """Explosão radial de partículas (círculos que somem em fade)."""
    pt = mm.get_pool("particle")
    for j in range(n):
        if pt.count >= pt.capacity - 1:
            return
        packed = world.create_entity("particle_entity")
        idx = packed & 0xFFFFFFFF
        a = ((seed * 2654435761 + j * 97561) % 6283) / 1000.0
        spd = speed * (0.4 + ((seed * 40503 + j * 131) % 601) / 1000.0)
        t = mm.get_pool("transform")
        trow = t.dense_row_of(idx); tv = t.active_view()
        tv["position_x"][trow] = x
        tv["position_y"][trow] = y
        tv["scale_x"][trow] = tv["scale_y"][trow] = 0.75
        v = mm.get_pool("velocity")
        vrow = v.dense_row_of(idx); vv = v.active_view()
        vv["linear_x"][vrow] = math.cos(a) * spd
        vv["linear_y"][vrow] = math.sin(a) * spd
        s = mm.get_pool("sprite")
        srow = s.dense_row_of(idx); sv = s.active_view()
        sv["texture_id"][srow] = SHAPE_CIRCLE
        sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = color
        sv["tint_a"][srow] = 255
        sv["layer_z"][srow] = 18
        prow = pt.dense_row_of(idx); pv = pt.active_view()
        pv["self"][prow] = np.uint64(packed)
        pv["ttl"][prow] = pv["ttl0"][prow] = ttl


def handle_player_death(pv, prow, mods_view, stats_view) -> bool:
    """Morte do jogador: conta em stats; no modo arcade (menus) retorna
    True e deixa lives < 0 para a cena detectar o GAMEOVER; fora dele
    (smoke/CLI) respawna como antes."""
    stats_view["deaths"][0] += 1
    if mods_view["arcade"][0]:
        return True
    pv["lives"][prow] = 0 if mods_view["glass"][0] else 3
    return False


class ParticleSystem(ISystem):
    """Fade + gravidade leve + expiração das partículas (kernel NumPy)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._pt = memory_manager.get_pool("particle")
        self._velocity = memory_manager.get_pool("velocity")
        self._sprite = memory_manager.get_pool("sprite")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pt.count
        if n == 0:
            return
        pv = self._pt.active_view()
        pv["ttl"] -= delta_time
        idxs = self._pt.active_entity_indices()
        vrows = self._velocity.dense_rows_of(idxs)
        self._velocity.active_view()["linear_y"][vrows] += 220.0 * delta_time
        srows = self._sprite.dense_rows_of(idxs)
        frac = np.clip(pv["ttl"] / np.maximum(pv["ttl0"], 1e-3), 0.0, 1.0)
        self._sprite.active_view()["tint_a"][srows] = (frac * 255).astype(np.uint8)
        dead = pv["ttl"] <= 0.0
        for h in pv["self"][dead]:
            world.destroy_entity(int(h))


def spawn_boss(world: "World", mm: MemoryManager, data: GameData,
               boss_name: str) -> None:
    """Spawna um boss completo (raiz, partes, emitters da fase 0).
    Usado pela composição no boot e pelo Boss Rush em runtime."""
    if boss_name == "twins":                     # composto por 2 raízes
        spawn_boss(world, mm, data, "twin_yin")
        spawn_boss(world, mm, data, "twin_yang")
        return

    bdef = data.bosses[sid(boss_name)]
    composite = len(bdef.parts) > 0
    packed = world.create_entity("boss_hidden" if composite else "boss")
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform")
    row = t.dense_row_of(idx); tv = t.active_view()
    x0, y0 = (bdef.route[0][0], bdef.route[0][1]) if bdef.route \
        else (SCREEN_W / 2, 100.0)
    if bdef.motion == "descend":
        y0 = 30.0                                # entra pelo topo
    tv["position_x"][row] = x0
    tv["position_y"][row] = y0
    if not composite:                            # raiz visível com hitbox
        half_w, half_h = bdef.hitbox
        tv["scale_x"][row] = half_w / 4.0
        tv["scale_y"][row] = half_h / 4.0
        s = mm.get_pool("sprite")
        srow = s.dense_row_of(idx); sv = s.active_view()
        sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = 230, 60, 120
        sv["tint_a"][srow] = 255
        sv["layer_z"][srow] = 15
        h = mm.get_pool("hitbox")
        hrow = h.dense_row_of(idx); hv = h.active_view()
        hv["half_width"][hrow] = half_w
        hv["half_height"][hrow] = half_h
    b = mm.get_pool("boss")
    brow = b.dense_row_of(idx); bv = b.active_view()
    bv["self"][brow] = np.uint64(packed)
    bv["boss_id"][brow] = sid(boss_name)
    mods = mm.get_pool("run_mods").active_view()
    hp_mult = float(mods["hp_mult"][0])
    if int(mods["rush"][0]) == 2:        # SINS RUSH: HP +15%/stage (legado)
        hp_mult *= SINS_RUSH_HP_SCALE ** int(mods["rush_idx"][0])
    bv["hp"][brow] = bv["max_hp"][brow] = bdef.hp * hp_mult
    bv["phase_idx"][brow] = 0
    bv["stun_t"][brow] = 0.0
    bv["aux_angle"][brow] = bv["aux2"][brow] = 0.0
    bv["invuln"][brow] = 0
    bv["tier"][brow] = 1                          # DDA: recalculado no 1º frame
    bv["sw_t"][brow] = bv["sw_acc"][brow] = 0.0    # Segundo Fôlego (EXPERT+)

    part_indices = []
    pt = mm.get_pool("part")
    for (dx, dy, hw, hh) in bdef.parts:          # hitboxes-filhas visíveis
        p_packed = world.create_entity("part")
        pidx = p_packed & 0xFFFFFFFF
        prow_t = t.dense_row_of(pidx)
        tvp = t.active_view()                    # re-busca: attach cresceu
        tvp["position_x"][prow_t] = x0 + dx
        tvp["position_y"][prow_t] = y0 + dy
        tvp["scale_x"][prow_t] = hw / 4.0
        tvp["scale_y"][prow_t] = hh / 4.0
        s = mm.get_pool("sprite")
        srow = s.dense_row_of(pidx); sv = s.active_view()
        sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = 230, 60, 120
        sv["tint_a"][srow] = 255
        sv["layer_z"][srow] = 15
        h = mm.get_pool("hitbox")
        hrow = h.dense_row_of(pidx); hv = h.active_view()
        hv["half_width"][hrow] = hw
        hv["half_height"][hrow] = hh
        prow = pt.dense_row_of(pidx); pv = pt.active_view()
        pv["self"][prow] = np.uint64(p_packed)
        pv["root"][prow] = idx
        pv["off_x"][prow] = dx
        pv["off_y"][prow] = dy
        part_indices.append(pidx)

    spawn_emitters(world, mm.get_pool("emitter"), idx, bdef.phases[0],
                   tuple(part_indices))


def spawn_minion(world: "World", mm: MemoryManager, x: float, y: float,
                 kind: int, hp: float, speed: float) -> int:
    """Spawna um lacaio (kamikaze/sentinela/bolha). Retorna packed ou -1."""
    minion = mm.get_pool("minion")
    if minion.count >= minion.capacity - 1:
        return -1
    packed = world.create_entity("minion")
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform")
    trow = t.dense_row_of(idx); tv = t.active_view()
    tv["position_x"][trow] = x
    tv["position_y"][trow] = y
    tv["scale_x"][trow] = tv["scale_y"][trow] = MINION_RADIUS / 4.0
    v = mm.get_pool("velocity")
    vrow = v.dense_row_of(idx); vv = v.active_view()
    vv["linear_x"][vrow] = 0.0
    vv["linear_y"][vrow] = speed if kind == MINION_KAMIKAZE else 0.0
    s = mm.get_pool("sprite")
    srow = s.dense_row_of(idx); sv = s.active_view()
    sv["texture_id"][srow] = SHAPE_CIRCLE
    r, g, b = _MINION_COLORS.get(kind, (255, 120, 60))
    sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = r, g, b
    sv["tint_a"][srow] = 255
    sv["layer_z"][srow] = 12
    mrow = minion.dense_row_of(idx); mv = minion.active_view()
    mv["self"][mrow] = np.uint64(packed)
    mv["kind"][mrow] = kind
    mv["hp"][mrow] = hp
    mv["speed"][mrow] = speed
    mv["timer"][mrow] = BUBBLE_EXPLODE_T if kind == MINION_BUBBLE else 0.0
    return packed
LASER_TELEGRAPH, LASER_FIRE_DUR = 1.8, 0.65
LASER_HALF = 6.0
FOCUS_MAX = 3.0                   # s de energia de FOCUS


def _destroy_bullets_within(world, eb_pool, transform_pool,
                            cx: float, cy: float, radius: float) -> int:
    """Enfileira a destruição das balas inimigas num raio. Retorna quantas."""
    n = eb_pool.count
    if n == 0:
        return 0
    ebv = eb_pool.active_view()
    idxs = eb_pool.active_entity_indices()
    trows = transform_pool.dense_rows_of(idxs)
    tv = transform_pool.active_view()
    dx = tv["position_x"][trows] - cx
    dy = tv["position_y"][trows] - cy
    m = dx * dx + dy * dy <= radius * radius
    for h in ebv["self"][m]:
        world.destroy_entity(int(h))
    return int(m.sum())

# Armas selecionáveis pelas teclas 1..0
WEAPON_KEYS = ("padrao", "spread", "agulha", "teleguiado", "plasma",
               "carregado", "burst", "flak", "chakram", "satelite")


def spawn_player_bullet(world: "World", mm: MemoryManager, arch_name: str,
                        x: float, y: float, vx: float, vy: float,
                        damage: float, size: float,
                        color=(120, 220, 255)) -> int:
    """Spawna uma bala do jogador e escreve os campos base (transform,
    velocity, sprite, pb_core). Retorna o PackedEntityId ou -1 (pool cheio)."""
    pb_core = mm.get_pool("pb_core")
    if pb_core.count >= pb_core.capacity:
        return -1
    packed = world.create_entity(arch_name)
    idx = packed & 0xFFFFFFFF
    t = mm.get_pool("transform")
    row = t.dense_row_of(idx); tv = t.active_view()
    tv["position_x"][row] = x
    tv["position_y"][row] = y
    tv["scale_x"][row] = tv["scale_y"][row] = size / 4.0
    v = mm.get_pool("velocity")
    row = v.dense_row_of(idx); vv = v.active_view()
    vv["linear_x"][row] = vx
    vv["linear_y"][row] = vy
    s = mm.get_pool("sprite")
    row = s.dense_row_of(idx); sv = s.active_view()
    sv["texture_id"][row] = SHAPE_CIRCLE
    sv["tint_r"][row], sv["tint_g"][row], sv["tint_b"][row] = color
    sv["tint_a"][row] = 255
    sv["layer_z"][row] = 5
    row = pb_core.dense_row_of(idx); cv = pb_core.active_view()
    cv["self"][row] = np.uint64(packed)
    cv["damage"][row] = damage
    cv["radius"][row] = size
    return packed


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
class SkillSystem(ISystem):
    """As 8 habilidades + variantes '+' (skills.json). Escreve as escalas
    de tempo na pool `clock` e os multiplicadores no player — roda ANTES
    de PlayerControl/WeaponFire, que os consomem."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider,
                 data: GameData) -> None:
        self._input = input_provider
        self._data = data
        self._mm = memory_manager
        self._player = memory_manager.get_pool("player")
        self._transform = memory_manager.get_pool("transform")
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._boss = memory_manager.get_pool("boss")
        self._clock = memory_manager.get_pool("clock")
        self._pb_homing = memory_manager.get_pool("pb_homing")
        self._stats = memory_manager.get_pool("stats")
        self._mastery = memory_manager.get_pool("mastery")
        self._hitbox = memory_manager.get_pool("hitbox")
        self._part = memory_manager.get_pool("part")

    def update(self, world: "World", delta_time: float) -> None:
        ck = self._clock.active_view()
        ck["world"][0] = 1.0
        ck["bullets"][0] = 1.0
        i, trow = _player_row(self._player, self._transform)
        if i < 0:
            return
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        pv["speed_mult"][prow] = 1.0
        pv["fr_mult"][prow] = 1.0
        if pv["dmg_t"][prow] > 0.0:                 # buff do EMP+ expira
            pv["dmg_t"][prow] -= delta_time
            if pv["dmg_t"][prow] <= 0.0:
                pv["dmg_mult"][prow] = 1.0
        if pv["skill_cd"][prow] > 0.0:
            pv["skill_cd"][prow] -= delta_time
        pv["skill_age"][prow] += delta_time

        if self._input.is_action_pressed("toggle_skill_plus"):
            cur = self._data.skills.get(int(pv["skill_id"][prow]))
            if cur is not None:
                target = cur.name[:-1] if cur.name.endswith("+") else cur.name + "+"
                if sid(target) in self._data.skills:
                    pv["skill_id"][prow] = sid(target)

        sd = self._data.skills.get(int(pv["skill_id"][prow]))
        if sd is None or sd.name == "none":
            return
        plus = sd.name.endswith("+")
        base = sd.name[:-1] if plus else sd.name
        pressed = self._input.is_action_pressed("skill")
        held = self._input.is_action_held("skill")
        tv = self._transform.active_view()
        px = float(tv["position_x"][trow]); py = float(tv["position_y"][trow])

        was_active = pv["skill_t"][prow] > 0.0
        if was_active:
            pv["skill_t"][prow] -= delta_time
        expired = was_active and pv["skill_t"][prow] <= 0.0
        ready = pv["skill_cd"][prow] <= 0.0

        if base == "dash":
            if pressed and ready:
                pv["skill_t"][prow] = sd.duration
                pv["skill_cd"][prow] = sd.cd
                if plus:                            # DASH+: i-frames
                    pv["invuln_t"][prow] = max(float(pv["invuln_t"][prow]), sd.aux)
            if pv["skill_t"][prow] > 0.0:
                pv["speed_mult"][prow] = sd.power

        elif base == "parry":
            if pressed and ready:
                pv["skill_t"][prow] = sd.duration
                pv["skill_cd"][prow] = sd.cd
                if self._mastery.count:                 # PARRY+: nova janela
                    self._mastery.active_view()["parry_burst"][0] = 0
            if pv["skill_t"][prow] > 0.0:
                n = self._parry(world, sd, plus, px, py)
                if n and self._mastery.count:
                    mv = self._mastery.active_view()
                    mv["parry_burst"][0] += n
                    mv["parry_burst_max"][0] = max(mv["parry_burst_max"][0],
                                                   mv["parry_burst"][0])

        elif base == "focus":
            en = float(pv["focus_en"][prow])
            if held and en > 0.0:
                pv["focus_en"][prow] = max(0.0, en - sd.drain * delta_time)
                ck["world"][0] = sd.scale
                ck["bullets"][0] = sd.scale         # balas também em câmera lenta
            else:
                pv["focus_en"][prow] = min(FOCUS_MAX, en + sd.regen * delta_time)

        elif base == "emp":
            if pressed and ready:
                pv["skill_cd"][prow] = sd.cd
                n = _destroy_bullets_within(world, self._eb, self._transform,
                                            px, py, sd.radius)
                spawn_particles(world, self._mm, px, py, (100, 200, 255),
                                20, speed=340.0, ttl=0.5, seed=int(px))
                add_shake(self._mm, 6.0)
                add_sfx(self._mm, SFX_EMP)
                if self._mastery.count:                 # EMP+ (Sobrecarga)
                    mv = self._mastery.active_view()
                    mv["emp_max"][0] = max(mv["emp_max"][0], n)
                if plus:                            # EMP+: buff, sem stun
                    pv["dmg_mult"][prow] = 1.0 + n * sd.buff_per
                    pv["dmg_t"][prow] = sd.buff_dur
                elif sd.stun > 0.0:
                    bv = self._boss.active_view()
                    bv["stun_t"][: self._boss.count] = sd.stun

        elif base == "blink":
            if pressed and ready:
                pv["skill_cd"][prow] = sd.cd
                dx = (1.0 if self._input.is_action_held("move_right") else 0.0) - \
                     (1.0 if self._input.is_action_held("move_left") else 0.0)
                dy = (1.0 if self._input.is_action_held("move_down") else 0.0) - \
                     (1.0 if self._input.is_action_held("move_up") else 0.0)
                if dx == 0.0 and dy == 0.0:
                    dy = -1.0
                d = math.hypot(dx, dy)
                nx = min(max(px + dx / d * sd.power, 9.0), SCREEN_W - 9.0)
                ny = min(max(py + dy / d * sd.power, 9.0), SCREEN_H - 9.0)
                tv["position_x"][trow] = nx
                tv["position_y"][trow] = ny
                if self._mastery.count and not \
                        self._mastery.active_view()["blink_pass"][0]:
                    self._check_blink_pass(px, py, nx, ny)
                if plus:                            # BLINK+: EMP na origem
                    _destroy_bullets_within(world, self._eb, self._transform,
                                            px, py, sd.radius)

        elif base == "overclock":
            if pressed and ready:
                pv["skill_t"][prow] = sd.duration
                pv["skill_cd"][prow] = sd.cd
                if self._mastery.count:                 # OVERCLOCK+: nova janela
                    self._mastery.active_view()["oc_dmg"][0] = 0.0
            if pv["skill_t"][prow] > 0.0:
                pv["fr_mult"][prow] = sd.fr
                if plus:                            # OVERCLOCK+: berserk lento
                    pv["speed_mult"][prow] = sd.speed

        elif base == "shield":
            if pressed and ready and not pv["shield_up"][prow]:
                pv["shield_up"][prow] = 1
                pv["skill_t"][prow] = sd.duration
                pv["skill_age"][prow] = 0.0
                pv["skill_cd"][prow] = sd.cd
            if pv["shield_up"][prow] and pv["skill_t"][prow] <= 0.0:
                pv["shield_up"][prow] = 0           # expirou sem absorver

        elif base == "timedil":
            if pressed and ready:
                pv["skill_t"][prow] = sd.duration
                pv["skill_cd"][prow] = sd.cd
                if self._mastery.count and not \
                        self._mastery.active_view()["timedil_close"][0]:
                    self._check_timedil_close(px, py)
            if pv["skill_t"][prow] > 0.0:
                ck["bullets"][0] = 0.0              # congela balas inimigas
            if expired and plus:                    # TIMEDIL+: estilhaço
                _destroy_bullets_within(world, self._eb, self._transform,
                                        px, py, sd.radius)

    def _parry(self, world, sd, plus: bool, px: float, py: float) -> int:
        """Reflete balas no raio: destrói a inimiga e spawna uma bala do
        jogador contra o boss (PARRY+: míssil homing de 1.5). Retorna
        quantas balas foram refletidas (PARRY+: burst da janela atual)."""
        n = self._eb.count
        if n == 0:
            return 0
        ebv = self._eb.active_view()
        idxs = self._eb.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        tv = self._transform.active_view()
        dx = tv["position_x"][trows] - px
        dy = tv["position_y"][trows] - py
        m = dx * dx + dy * dy <= sd.radius * sd.radius
        if not m.any():
            return 0
        if self._stats.count:                        # gate do ESCUDO (50 total)
            self._stats.active_view()["parries"][0] += int(m.sum())
        bx, by = px, py - 500.0                     # fallback: para cima
        if self._boss.count > 0:
            btrow = self._transform.dense_row_of(int(self._boss.active_entity_indices()[0]))
            bx = float(tv["position_x"][btrow]); by = float(tv["position_y"][btrow])
        for k in np.where(m)[0]:
            x = float(tv["position_x"][trows[k]])
            y = float(tv["position_y"][trows[k]])
            world.destroy_entity(int(ebv["self"][k]))
            ddx = bx - x; ddy = by - y
            d = math.hypot(ddx, ddy) or 1.0
            if plus:                                # PARRY+ (Royal Guard)
                packed = spawn_player_bullet(world, self._mm, "pb_teleguiado",
                                             x, y, ddx / d * 370.0, ddy / d * 370.0,
                                             sd.power, 4.0, color=(255, 255, 160))
                if packed >= 0:
                    hrow = self._pb_homing.dense_row_of(packed & 0xFFFFFFFF)
                    hv = self._pb_homing.active_view()
                    hv["turn"][hrow] = 260.0
                    hv["vmax"][hrow] = 370.0
                    hv["t"][hrow] = 2.8
            else:
                spawn_player_bullet(world, self._mm, "pb_padrao", x, y,
                                    ddx / d * 500.0, ddy / d * 500.0,
                                    sd.power, 4.0, color=(255, 255, 160))
        return int(m.sum())

    def _check_blink_pass(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """BLINK+ (Relâmpago Fantasma): marca se a linha do teleporte
        (amostrada em t=0.25/0.5/0.75) cruzou o AABB de algum boss."""
        mv = self._mastery.active_view()
        for t in (0.25, 0.5, 0.75):
            sx, sy = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for raw in self._boss.active_entity_indices():
                bi = int(raw)
                if self._boss.active_view()["invuln"][self._boss.dense_row_of(bi)]:
                    continue
                if self._aabb_contains(bi, sx, sy):
                    mv["blink_pass"][0] = 1
                    return
            pv2 = self._part.active_view()
            for k in range(self._part.count):
                if self._aabb_contains(int(pv2["self"][k]) & 0xFFFFFFFF, sx, sy):
                    mv["blink_pass"][0] = 1
                    return

    def _aabb_contains(self, entity_idx: int, x: float, y: float) -> bool:
        trow = self._transform.dense_row_of(entity_idx)
        hrow = self._hitbox.dense_row_of(entity_idx)
        if trow < 0 or hrow < 0:
            return False
        tv = self._transform.active_view(); hv = self._hitbox.active_view()
        cx = float(tv["position_x"][trow]); cy = float(tv["position_y"][trow])
        hw = float(hv["half_width"][hrow]); hh = float(hv["half_height"][hrow])
        return abs(x - cx) <= hw and abs(y - cy) <= hh

    def _check_timedil_close(self, px: float, py: float) -> None:
        """DILATAÇÃO+ (Ruptura Temporal): marca se havia uma bala inimiga
        a <=5px do jogador no instante da ativação."""
        if self._eb.count == 0:
            return
        tv = self._transform.active_view()
        idxs = self._eb.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        dx = tv["position_x"][trows] - px
        dy = tv["position_y"][trows] - py
        if bool(((dx * dx + dy * dy) <= 25.0).any()):
            self._mastery.active_view()["timedil_close"][0] = 1


# ===========================================================================
class ScaledMovementSystem(ISystem):
    """Substitui o PhysicsSystem da engine: integra Transform += Velocity×dt
    com TRÊS escalas — jogador sempre 1.0; balas inimigas usam clock.bullets
    (DILATAÇÃO congela); todo o resto usa clock.world (FOCUS desacelera)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._player = memory_manager.get_pool("player")
        self._clock = memory_manager.get_pool("clock")

    def update(self, world: "World", delta_time: float) -> None:
        from ouroboros.core.memory.component_pool import intersect_entity_indices as _ix
        idx = _ix(self._transform, self._velocity)
        if idx.size == 0:
            return
        ck = self._clock.active_view()
        scale = np.full(idx.shape[0], float(ck["world"][0]), dtype=np.float32)
        eb_rows = self._eb.dense_rows_of(idx)
        scale[eb_rows != -1] = float(ck["bullets"][0])
        pl_idx = self._player.active_entity_indices()
        if pl_idx.size:
            scale[idx == int(pl_idx[0])] = 1.0
        trows = self._transform.dense_rows_of(idx)
        vrows = self._velocity.dense_rows_of(idx)
        tv = self._transform.active_view()
        vv = self._velocity.active_view()
        tv["position_x"][trows] += vv["linear_x"][vrows] * delta_time * scale
        tv["position_y"][trows] += vv["linear_y"][vrows] * delta_time * scale


# ===========================================================================
class PlayerControlSystem(ISystem):
    """Input → velocity do jogador; decrementos de timers do jogador."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider) -> None:
        self._input = input_provider
        self._player = memory_manager.get_pool("player")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._clock = memory_manager.get_pool("clock")

    def update(self, world: "World", delta_time: float) -> None:
        i, _ = _player_row(self._player, self._transform)
        if i < 0:
            return
        dx = (1.0 if self._input.is_action_held("move_right") else 0.0) - \
             (1.0 if self._input.is_action_held("move_left") else 0.0)
        dy = (1.0 if self._input.is_action_held("move_down") else 0.0) - \
             (1.0 if self._input.is_action_held("move_up") else 0.0)
        if self._clock.active_view()["invert"][0]:  # Luxúria: atração fatal
            dx, dy = -dx, -dy
        if dx != 0.0 and dy != 0.0:
            dx *= 0.7071; dy *= 0.7071
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        speed = PLAYER_SPEED * float(pv["speed_mult"][prow])   # DASH/OC+
        vrow = self._velocity.dense_row_of(i)
        vv = self._velocity.active_view()
        vv["linear_x"][vrow] = dx * speed
        vv["linear_y"][vrow] = dy * speed
        if pv["invuln_t"][prow] > 0.0:
            pv["invuln_t"][prow] -= delta_time
        if pv["fire_cd"][prow] > 0.0:
            pv["fire_cd"][prow] -= delta_time


# ===========================================================================
class WeaponFireSystem(ISystem):
    """Cadência + spawn de balas-entidade conforme weapons.json.
    Armas data-driven puras (padrão/spread/agulha/teleguiado/plasma/flak/
    chakram) usam o caminho padrão; `special` despacha para os quatro
    estados que precisam de máquina própria: charged, burst, orbit, swarm."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider,
                 data: GameData) -> None:
        self._input = input_provider
        self._data = data
        self._mm = memory_manager
        self._player = memory_manager.get_pool("player")
        self._transform = memory_manager.get_pool("transform")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_orbit = memory_manager.get_pool("pb_orbit")
        self._pb_shrap = memory_manager.get_pool("pb_shrap")
        self._mods = memory_manager.get_pool("run_mods")
        self._fr = 1.0                               # mults frame-local
        self._dmg = 1.0

    def update(self, world: "World", delta_time: float) -> None:
        i, trow = _player_row(self._player, self._transform)
        if i < 0:
            return
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()

        # troca de arma (teclas 1..0) e toggle da variante + (tecla P)
        for slot, wname in enumerate(WEAPON_KEYS):
            if self._input.is_action_pressed(f"weapon_{slot + 1}"):
                pv["weapon_id"][prow] = sid(wname)
                pv["charge_t"][prow] = 0.0
                pv["burst_left"][prow] = 0
        if self._input.is_action_pressed("toggle_plus"):
            cur = self._data.weapons.get(int(pv["weapon_id"][prow]))
            if cur is not None:
                target = cur.name[:-1] if cur.name.endswith("+") else cur.name + "+"
                if sid(target) in self._data.weapons:
                    pv["weapon_id"][prow] = sid(target)

        wd = self._data.weapons.get(int(pv["weapon_id"][prow]))
        if wd is None:
            return
        # multiplicadores: habilidades (OVERCLOCK / EMP+) + CANHÃO DE VIDRO
        self._fr = float(pv["fr_mult"][prow])
        self._dmg = float(pv["dmg_mult"][prow])
        if self._mods.active_view()["glass"][0]:
            self._dmg *= 3.0
        tv = self._transform.active_view()
        px = float(tv["position_x"][trow])
        py = float(tv["position_y"][trow])
        held = self._input.is_action_held("fire")
        released = self._input.is_action_released("fire")

        if wd.special == "charged":
            self._charged(world, wd, pv, prow, px, py, held, released, delta_time)
        elif wd.special == "burst":
            self._burst(world, wd, pv, prow, px, py, held, delta_time)
        elif wd.special == "orbit":
            self._orbit(world, wd, pv, prow, px, py, held)
        elif wd.special == "swarm":
            self._swarm(world, wd, pv, prow, px, py, held, released)
        elif held and pv["fire_cd"][prow] <= 0.0:
            pv["fire_cd"][prow] = wd.fire_rate * self._fr
            n = wd.shots
            base = -math.pi / 2
            for k in range(n):
                th = base if n == 1 else base - wd.arc / 2 + wd.arc * k / (n - 1)
                self._fire_one(world, wd, px, py, th)

    # -- helpers --------------------------------------------------------------

    def _fire_one(self, world, wd, px, py, theta, damage=None, size=None,
                  speed=None, arch=None) -> int:
        spd = wd.speed if speed is None else speed
        packed = spawn_player_bullet(
            world, self._mm, arch or ("pb_" + wd.name), px, py,
            math.cos(theta) * spd, math.sin(theta) * spd,
            (wd.damage if damage is None else damage) * self._dmg,
            wd.size if size is None else size)
        if packed >= 0:
            self._write_recipe(packed & 0xFFFFFFFF, wd)
        return packed

    def _write_recipe(self, idx: int, wd) -> None:
        for pool_name, fields in wd.init:
            pool = self._mm.get_pool(pool_name)
            row = pool.dense_row_of(idx)
            view = pool.active_view()
            for fname, fval in fields:
                view[fname][row] = fval

    # -- specials -------------------------------------------------------------

    def _charged(self, world, wd, pv, prow, px, py, held, released, dt) -> None:
        if pv["fire_cd"][prow] > 0.0:
            return
        if held:
            pv["charge_t"][prow] = min(float(pv["charge_t"][prow]) + dt, CHARGED_MAX_T)
            return
        if released and pv["charge_t"][prow] > 0.0:
            frac = float(pv["charge_t"][prow]) / CHARGED_MAX_T
            dmg = CHARGED_MIN_DMG + (CHARGED_MAX_DMG - CHARGED_MIN_DMG) * frac
            size = CHARGED_MIN_SZ + (CHARGED_MAX_SZ - CHARGED_MIN_SZ) * frac
            packed = self._fire_one(world, wd, px, py, -math.pi / 2,
                                    damage=dmg, size=size)
            # CARREGADO+: estilhaços só com carga quase cheia (≥85%)
            if packed >= 0 and wd.name.endswith("+"):
                row = self._pb_shrap.dense_row_of(packed & 0xFFFFFFFF)
                if row != -1:
                    self._pb_shrap.active_view()["n"][row] = \
                        6 if frac >= CHARGED_PLUS_FRAC else 0
            pv["charge_t"][prow] = 0.0
            pv["fire_cd"][prow] = wd.fire_rate * self._fr

    def _burst(self, world, wd, pv, prow, px, py, held, dt) -> None:
        if pv["burst_left"][prow] > 0:               # meio da rajada
            pv["burst_t"][prow] -= dt
            if pv["burst_t"][prow] <= 0.0:
                pv["burst_t"][prow] = BURST_INTERVAL
                pv["burst_left"][prow] -= 1
                self._fire_one(world, wd, px, py, -math.pi / 2)
            return
        if held and pv["fire_cd"][prow] <= 0.0:
            pv["fire_cd"][prow] = wd.fire_rate * self._fr
            pv["burst_left"][prow] = wd.shots - 1
            pv["burst_t"][prow] = BURST_INTERVAL
            self._fire_one(world, wd, px, py, -math.pi / 2)

    def _orbit(self, world, wd, pv, prow, px, py, held) -> None:
        if not held or pv["fire_cd"][prow] > 0.0:
            return
        ov = self._pb_orbit.active_view()
        gems = int(np.sum(ov["kind"] == ORBIT_GEM))
        if gems >= ORBIT_MAX_GEMS:
            return
        pv["fire_cd"][prow] = wd.fire_rate
        packed = self._fire_one(world, wd, px, py, -math.pi / 2, speed=0.0)
        if packed >= 0:                              # espalha as gemas
            row = self._pb_orbit.dense_row_of(packed & 0xFFFFFFFF)
            self._pb_orbit.active_view()["angle"][row] = gems * (TWO_PI / ORBIT_MAX_GEMS)

    def _swarm(self, world, wd, pv, prow, px, py, held, released) -> None:
        """TELEGUIADO+: segurar acumula mísseis orbitando; soltar lança
        todos como mísseis homing da arma base."""
        if held and pv["fire_cd"][prow] <= 0.0:
            ov = self._pb_orbit.active_view()
            n_held = int(np.sum(ov["kind"] == ORBIT_HELD))
            if n_held < SWARM_MAX_HELD:
                pv["fire_cd"][prow] = wd.fire_rate * self._fr
                packed = self._fire_one(world, wd, px, py, -math.pi / 2, speed=0.0)
                if packed >= 0:
                    row = self._pb_orbit.dense_row_of(packed & 0xFFFFFFFF)
                    self._pb_orbit.active_view()["angle"][row] = \
                        n_held * (TWO_PI / SWARM_MAX_HELD)
        if released:
            base = self._data.weapons.get(sid("teleguiado"))
            ov = self._pb_orbit.active_view()
            idxs = self._pb_orbit.active_entity_indices()
            tv = self._transform.active_view()
            cv = self._pb_core.active_view()
            for k in range(self._pb_orbit.count):    # snapshot: novos mísseis
                if ov["kind"][k] != ORBIT_HELD:      # não têm pb_orbit
                    continue
                eidx = int(idxs[k])
                trow = self._transform.dense_row_of(eidx)
                x = float(tv["position_x"][trow]); y = float(tv["position_y"][trow])
                crow = self._pb_core.dense_row_of(eidx)
                world.destroy_entity(int(cv["self"][crow]))
                self._fire_one(world, base, x, y, -math.pi / 2)


# ===========================================================================
class WaypointSystem(ISystem):
    """Movimento de boss por waypoints com easing smoothstep (bosses.json)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._boss = memory_manager.get_pool("boss")
        self._waypoint = memory_manager.get_pool("waypoint")
        self._transform = memory_manager.get_pool("transform")
        self._clock = memory_manager.get_pool("clock")
        self._mods = memory_manager.get_pool("run_mods")

    def update(self, world: "World", delta_time: float) -> None:
        delta_time *= float(self._clock.active_view()["world"][0])   # FOCUS
        delta_time *= float(self._mods.active_view()["spd_mult"][0])  # HORDE/BERSERKER
        indices = intersect_entity_indices(self._boss, self._waypoint, self._transform)
        for raw in indices:                        # ≤2 bosses: loop primitivo
            i = int(raw)
            brow_ = self._boss.dense_row_of(i)
            if self._boss.active_view()["stun_t"][brow_] > 0.0:      # EMP
                continue
            bdef = self._data.bosses[int(self._boss.active_view()["boss_id"][brow_])]
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
        self._mm = memory_manager
        self._boss = memory_manager.get_pool("boss")
        self._emitter = memory_manager.get_pool("emitter")
        self._part = memory_manager.get_pool("part")
        self._mods = memory_manager.get_pool("run_mods")
        self._stats = memory_manager.get_pool("stats")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        mods = self._mods.active_view()
        diff_ord = int(mods["diff_ord"][0])
        for raw in self._boss.active_entity_indices():
            i = int(raw)
            brow = self._boss.dense_row_of(i)
            bv = self._boss.active_view()
            if bv["stun_t"][brow] > 0.0:            # decrementa stun do EMP
                bv["stun_t"][brow] -= delta_time
            bdef = self._data.bosses[int(bv["boss_id"][brow])]
            frac = float(bv["hp"][brow]) / float(bv["max_hp"][brow])
            bv["tier"][brow] = 1 if frac > 0.66 else (2 if frac > 0.33 else 3)  # DDA
            phase = int(bv["phase_idx"][brow])

            if bv["sw_t"][brow] > 0.0:              # Segundo Fôlego em andamento
                bv["sw_t"][brow] -= delta_time
                bv["sw_acc"][brow] += delta_time
                if bv["sw_t"][brow] <= 0.0:
                    bv["hp"][brow] = 0.0            # tempo esgotado: morre de vez
                else:
                    if bv["sw_acc"][brow] >= 0.45:
                        bv["sw_acc"][brow] -= 0.45
                        self._second_wind_burst(world, i, bv, brow, initial=False)
                    continue                        # imortal enquanto durar

            if bv["hp"][brow] <= 0.0:
                if phase < len(bdef.phases) - 1:   # ainda há fases (Pecado:
                    bv["hp"][brow] = 1.0           # floor até o Sétimo Selo)
                    frac = 1.0 / float(bv["max_hp"][brow])
                elif diff_ord >= 3 and not mods["sw_used"][0]:   # EXPERT+/ABISSAL
                    mods["sw_used"][0] = 1         # Segundo Fôlego: 1×/run
                    bv["hp"][brow] = 1.0
                    bv["invuln"][brow] = 1         # imune durante a sobrevida
                    bv["sw_t"][brow] = 3.0
                    bv["sw_acc"][brow] = 0.0
                    self._second_wind_burst(world, i, bv, brow, initial=True)
                    add_shake(self._mm, 14.0)
                    continue
                else:                              # derrotado
                    sv_ = self._stats.active_view()
                    sv_["kills"][0] += 1
                    trow_ = self._mm.get_pool("transform").dense_row_of(i)
                    if trow_ >= 0:                 # explosão de morte
                        tvx = self._mm.get_pool("transform").active_view()
                        spawn_particles(world, self._mm,
                                        float(tvx["position_x"][trow_]),
                                        float(tvx["position_y"][trow_]),
                                        (255, 200, 80), 26, speed=260.0,
                                        ttl=0.7, seed=i)
                        add_shake(self._mm, 12.0)
                        add_sfx(self._mm, SFX_BOOM)
                    mode = int(mods["rush"][0])
                    if mode in (1, 2):             # Boss Rush / SINS
                        self._rush_advance(world, i, brow, bv)
                    elif mode == 3:                # Waves: só remove; o
                        self._destroy_boss(world, i, brow, bv)   # WaveSystem avança
                    else:                          # clássico → reinicia
                        bv["hp"][brow] = bv["max_hp"][brow]
                        bv["phase_idx"][brow] = 0
                        bv["aux_angle"][brow] = bv["aux2"][brow] = 0.0
                        bv["invuln"][brow] = 0
                        self._reset_waypoint_timer(i)
                        self._swap_emitters(world, i, bdef.phases[0])
                    continue
            nxt = phase + 1
            if nxt < len(bdef.phases) and frac <= bdef.phases[phase].hp_above:
                bv["phase_idx"][brow] = nxt
                bv["aux_angle"][brow] = bv["aux2"][brow] = 0.0   # estado limpo
                self._reset_waypoint_timer(i)      # timers de gimmick (20s/30s)
                self._swap_emitters(world, i, bdef.phases[nxt])

    def _second_wind_burst(self, world: "World", boss_index: int, bv, brow,
                           initial: bool) -> None:
        """Rajada em anel do Segundo Fôlego (EXPERT+): 32 balas iniciais a
        230px/s; depois um anel de 18 a cada 0.45s girando com o timer."""
        trow = self._mm.get_pool("transform").dense_row_of(boss_index)
        if trow < 0:
            return
        tv = self._mm.get_pool("transform").active_view()
        x = float(tv["position_x"][trow]); y = float(tv["position_y"][trow])
        if initial:
            n, base_speed, rot = 32, 230.0, 0.0
        else:
            n, base_speed, rot = 18, 190.0, float(bv["sw_t"][brow]) * 1.5
        for j in range(n):
            a = rot + j * (TWO_PI / n)
            spd = base_speed if initial else base_speed + (j % 3) * 20.0
            spawn_enemy_bullet(world, self._mm, x, y,
                               math.cos(a) * spd, math.sin(a) * spd)

    def _reset_waypoint_timer(self, boss_index: int) -> None:
        wp = self._mm.get_pool("waypoint")
        wrow = wp.dense_row_of(boss_index)
        if wrow >= 0:
            wv = wp.active_view()
            wv["seg"][wrow] = 0
            wv["seg_t"][wrow] = 0.0

    def _destroy_boss(self, world: "World", boss_index: int, brow, bv) -> None:
        """Remove raiz + partes + emitters do boss (destruição diferida)."""
        ev = self._emitter.active_view()
        for k in range(self._emitter.count):
            if int(ev["root"][k]) == boss_index:
                world.destroy_entity(int(ev["self"][k]))
        pvw = self._part.active_view()
        for k in range(self._part.count):
            if int(pvw["root"][k]) == boss_index:
                world.destroy_entity(int(pvw["self"][k]))
        world.destroy_entity(int(bv["self"][brow]))

    def _rush_advance(self, world: "World", boss_index: int, brow, bv) -> None:
        """Boss Rush: destrói o boss atual e spawna o próximo da sequência;
        jogador ganha +1 vida (legado)."""
        # twins: a outra raiz ainda viva? só remove esta, não avança
        # (destroy é diferido → count mente; o boss morto tem hp<=0, então
        # qualquer hp>0 restante é um irmão vivo)
        hp_all = self._boss.active_view()["hp"][: self._boss.count]
        others_alive = bool(np.any(hp_all > 0.0))
        self._destroy_boss(world, boss_index, brow, bv)
        if others_alive:
            return
        mods = self._mods.active_view()
        order = RUSH_ORDERS[int(mods["rush"][0])]
        mods["rush_idx"][0] = (int(mods["rush_idx"][0]) + 1) % len(order)
        # +1 vida de cura entre bosses (cap 3)
        pl = self._player.active_entity_indices()
        if pl.size:
            prow = self._player.dense_row_of(int(pl[0]))
            pv = self._player.active_view()
            pv["lives"][prow] = min(3, int(pv["lives"][prow]) + 1)
        spawn_boss(world, self._mm, self._data, order[int(mods["rush_idx"][0])])

    def _swap_emitters(self, world: "World", boss_index: int, phase_def) -> None:
        ev = self._emitter.active_view()
        for k in range(self._emitter.count):       # ≤32 emitters
            if int(ev["root"][k]) == boss_index:
                world.destroy_entity(int(ev["self"][k]))
        spawn_emitters(world, self._emitter, boss_index, phase_def,
                       parts_of(self._part, boss_index))
        # lacaios de entrada da fase (Preguiça: 3 fantasmas espalhados)
        n_min, kind, hp, speed = phase_def.minions
        for j in range(int(n_min)):
            x = SCREEN_W * (0.25 + 0.25 * j)
            y = 150.0 + (j * 97) % 250
            spawn_minion(world, self._mm, x, y, int(kind), float(hp), float(speed))


def parts_of(part_pool, boss_index: int) -> tuple:
    """Entity indices das partes cuja raiz é `boss_index` (ordem de spawn)."""
    pv = part_pool.active_view()
    idxs = part_pool.active_entity_indices()
    return tuple(int(idxs[k]) for k in range(part_pool.count)
                 if int(pv["root"][k]) == boss_index)


def spawn_emitters(world: "World", emitter_pool, boss_index: int, phase_def,
                   part_indices: tuple = ()) -> None:
    """Cria as entidades-emitter de uma fase (usado na composição e na
    troca). `parent` = origem (parte, se o emitter declara `part`; senão a
    raiz); `root` = boss raiz, usado no swap de fase. Guardam apenas o
    entity index (o boss nunca é destruído durante a luta)."""
    for pattern_sid, off_x, off_y, part_idx in phase_def.emitters:
        parent = (part_indices[part_idx]
                  if 0 <= part_idx < len(part_indices) else boss_index)
        packed = world.create_entity("emitter")
        idx = packed & 0xFFFFFFFF
        row = emitter_pool.dense_row_of(idx)
        view = emitter_pool.active_view()
        view["self"][row] = np.uint64(packed)
        view["pattern_id"][row] = pattern_sid
        view["t"][row] = 0.0
        view["phase_angle"][row] = 0.0
        view["shot_count"][row] = 0
        view["parent"][row] = np.uint64(parent)
        view["root"][row] = np.uint64(boss_index)
        view["off_x"][row] = off_x
        view["off_y"][row] = off_y


# ===========================================================================
class BossMotionSystem(ISystem):
    """Movimentos de boss composto e posicionamento das partes:
    `swarm_orbit` gira o triângulo de unidades (0.75 rad/s) ao redor da
    raiz; `descend` desce a raiz do topo (150px/s) até y=216. Partes são
    sempre reposicionadas em raiz + offset (rotacionado no orbit).
    Roda após o WaypointSystem e antes do EmitterSystem."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._boss = memory_manager.get_pool("boss")
        self._part = memory_manager.get_pool("part")
        self._transform = memory_manager.get_pool("transform")
        self._clock = memory_manager.get_pool("clock")
        self._mods = memory_manager.get_pool("run_mods")

    def update(self, world: "World", delta_time: float) -> None:
        delta_time *= float(self._clock.active_view()["world"][0])   # FOCUS
        delta_time *= float(self._mods.active_view()["spd_mult"][0])  # HORDE/BERSERKER
        tv = self._transform.active_view()
        bv = self._boss.active_view()
        for raw in self._boss.active_entity_indices():
            bi = int(raw)
            brow = self._boss.dense_row_of(bi)
            if bv["stun_t"][brow] > 0.0:                             # EMP
                continue
            bdef = self._data.bosses[int(bv["boss_id"][brow])]
            if bdef.motion == "descend":
                trow = self._transform.dense_row_of(bi)
                y = float(tv["position_y"][trow])
                if y < WALL_MAX_Y:
                    tv["position_y"][trow] = min(WALL_MAX_Y,
                                                 y + WALL_DESCENT_SPEED * delta_time)
            elif bdef.motion == "swarm_orbit":
                bv["aux_angle"][brow] += SWARM_ORBIT_SPEED * delta_time
            elif bdef.motion == "track_x":          # persegue o x do jogador
                pl_idx = world.get_pool("player").active_entity_indices()
                if pl_idx.size:
                    ptrow = self._transform.dense_row_of(int(pl_idx[0]))
                    trow = self._transform.dense_row_of(bi)
                    x = float(tv["position_x"][trow])
                    x += (float(tv["position_x"][ptrow]) - x) * bdef.motion_rate * delta_time
                    tv["position_x"][trow] = min(max(x, 100.0), SCREEN_W - 100.0)
            elif bdef.motion == "teleport":         # Invocador
                bv["aux_angle"][brow] += delta_time
                if bv["aux_angle"][brow] >= SUMMONER_TELEPORT_CD:
                    bv["aux_angle"][brow] -= SUMMONER_TELEPORT_CD
                    # posição determinística por hash do contador (waypoint.seg)
                    wrow = None
                    if world.get_pool("waypoint").is_attached(bi):
                        wp = world.get_pool("waypoint")
                        wrow = wp.dense_row_of(bi)
                        wp.active_view()["seg"][wrow] += 1
                        seed = int(wp.active_view()["seg"][wrow])
                    else:
                        seed = int(bv["hp"][brow])
                    trow = self._transform.dense_row_of(bi)
                    tv["position_x"][trow] = 120.0 + ((seed * 2654435761) % 997) / 997.0 * (SCREEN_W - 240.0)
                    tv["position_y"][trow] = 60.0 + ((seed * 40503 + 7) % 499) / 499.0 * 150.0

        n = self._part.count
        if n == 0:
            return
        pv = self._part.active_view()
        idxs = self._part.active_entity_indices()
        for k in range(n):                          # ≤8 partes
            root_idx = int(pv["root"][k])
            rrow = self._transform.dense_row_of(root_idx)
            brow = self._boss.dense_row_of(root_idx)
            if rrow < 0 or brow < 0:
                continue
            rx = float(tv["position_x"][rrow]); ry = float(tv["position_y"][rrow])
            ox = float(pv["off_x"][k]); oy = float(pv["off_y"][k])
            bdef = self._data.bosses[int(bv["boss_id"][brow])]
            if bdef.motion == "swarm_orbit":
                a = float(bv["aux_angle"][brow])
                c, s = math.cos(a), math.sin(a)
                ox, oy = ox * c - oy * s, ox * s + oy * c
            trow = self._transform.dense_row_of(int(idxs[k]))
            tv["position_x"][trow] = rx + ox
            tv["position_y"][trow] = ry + oy


# ===========================================================================
class LaserSystem(ISystem):
    """Vigas axis-aligned: telegrafam (sem dano, tint apagado), disparam
    (dano por sobreposição, tint aceso) e expiram."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._laser = memory_manager.get_pool("laser")
        self._sprite = memory_manager.get_pool("sprite")
        self._transform = memory_manager.get_pool("transform")
        self._player = memory_manager.get_pool("player")
        self._clock = memory_manager.get_pool("clock")
        self._mods = memory_manager.get_pool("run_mods")
        self._stats = memory_manager.get_pool("stats")

    def update(self, world: "World", delta_time: float) -> None:
        delta_time *= float(self._clock.active_view()["world"][0])   # FOCUS
        n = self._laser.count
        if n == 0:
            return
        lv = self._laser.active_view()
        tele = lv["telegraph_t"] > 0.0
        lv["telegraph_t"][tele] -= delta_time
        firing = ~tele
        lv["fire_t"][firing] -= delta_time

        idxs = self._laser.active_entity_indices()
        srows = self._sprite.dense_rows_of(idxs)
        sv = self._sprite.active_view()
        sv["tint_r"][srows[firing]] = 255
        sv["tint_g"][srows[firing]] = 70
        sv["tint_b"][srows[firing]] = 70

        i, ptrow = _player_row(self._player, self._transform)
        if ptrow >= 0 and firing.any():
            tv = self._transform.active_view()
            px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
            prow = self._player.dense_row_of(i)
            pv = self._player.active_view()
            if pv["invuln_t"][prow] <= 0.0:
                h_hit = firing & (lv["axis"] == LASER_H) & \
                        (np.abs(py - lv["pos"]) <= lv["half"] + 9.0)
                v_hit = firing & (lv["axis"] == LASER_V) & \
                        (np.abs(px - lv["pos"]) <= lv["half"] + 9.0)
                if h_hit.any() or v_hit.any():
                    if pv["shield_up"][prow]:       # ESCUDO absorve o laser
                        pv["shield_up"][prow] = 0
                        pv["invuln_t"][prow] = 0.5
                    else:
                        pv["invuln_t"][prow] = PLAYER_INVULN
                        pv["lives"][prow] -= 1
                        if pv["lives"][prow] < 0:
                            handle_player_death(pv, prow,
                                                self._mods.active_view(),
                                                self._stats.active_view())

        dead = firing & (lv["fire_t"] <= 0.0)
        for h in lv["self"][dead]:
            world.destroy_entity(int(h))


# DDA (Difficulty do legado, entities.py:618-665): escala count/arc/velocidade
# dos padrões marcados `dda` (spread/ring/spiral do Clássico e do Enxame) pelo
# tier de HP do boss (1: >66%, 2: >33%, 3: resto); +1 projétil em DIFÍCIL+.
_DDA_SPREAD = {1: (5, math.radians(35.0)), 2: (6, math.radians(45.0)),
               3: (7, math.radians(56.0))}
_DDA_RING = {1: (26, 132.0), 2: (28, 150.0), 3: (32, 170.0)}
_DDA_SPIRAL = {1: (6, 2.5), 2: (6, 3.75), 3: (8, 4.5)}
_RING_TARGET_ARC = 30.0
_RING_MIN_GAP, _RING_MAX_GAP = math.radians(18.0), math.radians(55.0)


# ===========================================================================
class EmitterSystem(ISystem):
    """Executa PatternDefs: spawna balas inimigas como ENTIDADES, escrevendo
    as colunas do arquétipo (bullet_archetypes.json). Emissões `laser` e
    `pair` ficam para a fase 2 do port (ver MIGRATION.md)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._mm = memory_manager
        self._emitter = memory_manager.get_pool("emitter")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._sprite = memory_manager.get_pool("sprite")
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._laser = memory_manager.get_pool("laser")
        self._minion = memory_manager.get_pool("minion")
        self._player = memory_manager.get_pool("player")
        self._boss = memory_manager.get_pool("boss")
        self._clock = memory_manager.get_pool("clock")
        self._mods = memory_manager.get_pool("run_mods")
        self._abissal = False

    def _dda_pattern(self, pat: PatternDef, root_idx: int, bonus: int,
                     ox: float, oy: float, px: float, py: float) -> PatternDef:
        """Substitui count/arc/velocidade/braços pelo tier de HP do boss
        raiz (DDA — Difficulty do legado). `root_idx` já é o entity index
        puro (ver spawn_emitters), não um PackedEntityId."""
        brow = self._boss.dense_row_of(root_idx)
        tier = int(self._boss.active_view()["tier"][brow]) if brow >= 0 else 1
        if tier not in (1, 2, 3):
            tier = 1
        if pat.emit == "arc":
            n, arc = _DDA_SPREAD[tier]
            return dataclasses.replace(pat, count=n + bonus, arc=arc)
        if pat.emit == "ring":
            n, speed = _DDA_RING[tier]
            r = max(math.hypot(px - ox, py - oy), 40.0)
            gap = min(max(_RING_TARGET_ARC / r, _RING_MIN_GAP), _RING_MAX_GAP)
            return dataclasses.replace(pat, count=n + bonus, speed=speed, gap=gap)
        if pat.emit == "spiral":
            arms, spin = _DDA_SPIRAL[tier]
            return dataclasses.replace(pat, arms=arms, spin_speed=spin)
        return pat

    def update(self, world: "World", delta_time: float) -> None:
        delta_time *= float(self._clock.active_view()["world"][0])   # FOCUS
        mods = self._mods.active_view()
        self._abissal = bool(mods["abissal"][0])
        dda_bonus = 1 if int(mods["diff_ord"][0]) >= 2 else 0
        pi, ptrow = _player_row(self._player, self._transform)
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]) if ptrow >= 0 else SCREEN_W / 2
        py = float(tv["position_y"][ptrow]) if ptrow >= 0 else SCREEN_H * 0.8
        if mods["predator"][0] and pi >= 0:         # PREDADOR: mira 0.5s à frente
            pvrow = self._velocity.dense_row_of(pi)
            vv = self._velocity.active_view()
            px += float(vv["linear_x"][pvrow]) * 0.5
            py += float(vv["linear_y"][pvrow]) * 0.5

        for k in range(self._emitter.count):       # ≤32 emitters
            ev = self._emitter.active_view()
            if ev["warmup"][k] > 0.0:
                ev["warmup"][k] -= delta_time
                continue
            # boss atordoado (EMP) não dispara
            root_brow = self._boss.dense_row_of(int(ev["root"][k]))
            if root_brow >= 0 and self._boss.active_view()["stun_t"][root_brow] > 0.0:
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
            if pat.dda:
                pat = self._dda_pattern(pat, int(ev["root"][k]), dda_bonus,
                                        ox, oy, px, py)
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
        elif pat.emit == "pair":
            aim = math.atan2(py - oy, px - ox)
            p1 = self._spawn(world, pat, ox, oy, aim - pat.arc / 2, px, py)
            p2 = self._spawn(world, pat, ox, oy, aim + pat.arc / 2, px, py)
            if p1 is not None and p2 is not None:   # amarra o arame
                eb = self._eb.active_view()
                eb["tether"][self._eb.dense_row_of(p1 & 0xFFFFFFFF)] = np.uint64(p2)
                eb["tether"][self._eb.dense_row_of(p2 & 0xFFFFFFFF)] = np.uint64(p1)
        elif pat.emit == "summon":                  # lacaio (Invocador/Preguiça)
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            for j in range(pat.count):
                if pat.kind == MINION_KAMIKAZE:
                    x, y = ox, oy + 30.0
                else:                               # estático: posição hash
                    h1 = (seed * 2654435761 + j * 97561) % 997
                    h2 = (seed * 40503 + j * 69621 + 13) % 499
                    x = 100.0 + h1 / 997.0 * (SCREEN_W - 200.0)
                    y = 120.0 + h2 / 499.0 * 260.0
                spawn_minion(world, self._mm, x, y, pat.kind, pat.hp, pat.speed)
        elif pat.emit == "orbit_ring":              # Gula: anel orbital
            ev["phase_angle"][k] += 1.396 * pat.period   # 80°/s
            base = float(ev["phase_angle"][k])
            for j in range(pat.count):
                ang = base + j * (TWO_PI / pat.count)
                bx_ = ox + math.cos(ang) * 100.0
                by_ = oy + math.sin(ang) * 100.0
                p = self._spawn(world, pat, bx_, by_, 0.0, px, py)
                if p is not None:                   # tangencial + deriva
                    vrow = self._velocity.dense_row_of(p & 0xFFFFFFFF)
                    vv2 = self._velocity.active_view()
                    vv2["linear_x"][vrow] = -math.sin(ang) * pat.speed
                    vv2["linear_y"][vrow] = math.cos(ang) * pat.speed + 55.0
        elif pat.emit == "teeth":                   # Gula: fileira com vão
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            gy = 80.0 + ((seed * 2654435761) % 997) / 997.0 * 120.0
            gap = 180.0 + ((seed * 40503 + 7) % 499) / 499.0 * 80.0
            gap_cx = gap / 2 + ((seed * 69621 + 3) % 991) / 991.0 * (SCREEN_W - gap)
            x = 0.0
            while x < SCREEN_W:
                if abs(x - gap_cx) > gap / 2:
                    self._spawn(world, pat, x, gy, math.pi / 2, px, py)
                x += 50.0
        elif pat.emit == "radial_random":           # Gula: regurgitar
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            ang = ((seed * 2654435761) % 6283) / 1000.0
            self._spawn(world, pat, ox, oy, ang, px, py)
        elif pat.emit == "spotlight_rain":          # Soberba: chuva do holofote
            brow = self._boss.dense_row_of(int(ev["root"][k]))
            if brow < 0:
                return
            spot_x = float(self._boss.active_view()["aux_angle"][brow])
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            for j in range(pat.count):
                jit = (((seed * 2654435761 + j * 97561) % 997) / 997.0 - 0.5) * 36.0
                vx_j = (((seed * 40503 + j * 69621) % 499) / 499.0 - 0.5) * 70.0
                vy_j = 180.0 + ((seed * 69621 + j * 13) % 991) / 991.0 * 80.0
                p = self._spawn(world, pat, spot_x + jit, oy + 34.0,
                                math.pi / 2, px, py)
                if p is not None:
                    vrow = self._velocity.dense_row_of(p & 0xFFFFFFFF)
                    vv2 = self._velocity.active_view()
                    vv2["linear_x"][vrow] = vx_j
                    vv2["linear_y"][vrow] = vy_j
        elif pat.emit == "geo":                     # Soberba: formas yin/yang
            ev["shot_count"][k] += 1
            shape = int(ev["shot_count"][k]) & 1    # alterna quadrado/triângulo
            narms = 4 if shape == 0 else 3
            ev["phase_angle"][k] += 0.96 * pat.period    # 55°/s
            base = float(ev["phase_angle"][k])
            arch_name = "std/yin_blue" if shape == 0 else "std/yang_orange"
            pat_bullet = sid(arch_name)
            for i in range(narms):
                b0 = base + i * (TWO_PI / narms)
                for spread in (-0.12, 0.0, 0.12):
                    p = self._spawn_as(world, pat, pat_bullet, ox, oy + 34.0,
                                       b0 + spread, px, py)
                    if p is not None:               # deriva descendente
                        vrow = self._velocity.dense_row_of(p & 0xFFFFFFFF)
                        vv2 = self._velocity.active_view()
                        vv2["linear_y"][vrow] += 55.0
        elif pat.emit == "mirror":                  # Inveja: espelha a arma
            pl_idx = self._player.active_entity_indices()
            if pl_idx.size == 0:
                return
            prow = self._player.dense_row_of(int(pl_idx[0]))
            wd = self._data.weapons.get(
                int(self._player.active_view()["weapon_id"][prow]))
            wname = (wd.name[:-1] if wd and wd.name.endswith("+")
                     else (wd.name if wd else "padrao"))
            if pat.kind == 1:                       # fase 2: cicla armas (2s)
                ev["phase_angle"][k] += pat.period
                cyc = int(float(ev["phase_angle"][k]) / 2.0) % 4
                wname = ("spread", "agulha", "burst", "teleguiado")[cyc]
            down = math.pi / 2
            if wname == "spread":
                for a in (-25.0, -12.0, 0.0, 12.0, 25.0):
                    self._spawn_as(world, pat, sid("std/yang_orange"),
                                   ox, oy + 30.0, down + math.radians(a), px, py)
            elif wname == "agulha":
                p = self._spawn_as(world, pat, sid("std/yin_blue"),
                                   ox, oy + 30.0, down, px, py)
                if p is not None:
                    vrow = self._velocity.dense_row_of(p & 0xFFFFFFFF)
                    self._velocity.active_view()["linear_y"][vrow] = 480.0
            elif wname in ("burst", "carregado"):
                for off in (-12.0, 0.0, 12.0):
                    self._spawn(world, pat, ox + off, oy + 30.0, down, px, py)
            elif wname == "teleguiado":
                seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
                for j in range(4):
                    jit = (((seed * 2654435761 + j * 97561) % 997) / 997.0 - 0.5)
                    self._spawn_as(world, pat, sid("std/homing_purple"),
                                   ox, oy + 30.0, down + jit * 1.05, px, py)
            else:                                   # padrão e demais
                self._spawn(world, pat, ox, oy + 30.0, down, px, py)
        elif pat.emit == "corridor_rain":           # Avareza: corredores
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            # paredes deslocam a cada ~4s (hash do bloco de tempo)
            blk = seed // 7
            w0 = SCREEN_W * (0.20 + ((blk * 2654435761) % 499) / 499.0 * 0.18)
            w1 = SCREEN_W * (0.62 + ((blk * 40503 + 3) % 499) / 499.0 * 0.18)
            for cx_ in (w0 / 2.0, (w1 + SCREEN_W) / 2.0):
                for j in range(pat.count):
                    jit = (((seed * 69621 + j * 97561) % 997) / 997.0 - 0.5) * 60.0
                    p = self._spawn(world, pat, cx_ + jit, -8.0, down_ := math.pi / 2, px, py)
                    if p is not None:
                        vrow = self._velocity.dense_row_of(p & 0xFFFFFFFF)
                        vv2 = self._velocity.active_view()
                        vv2["linear_x"][vrow] = (((seed * 13 + j * 7) % 51) - 25.0)
                        vv2["linear_y"][vrow] = 160.0 + ((seed * 17 + j * 11) % 71)
        elif pat.emit == "border_random":           # Avareza: despejo
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            inset = min(180.0, float(ev["phase_angle"][k]) + 12.0 * pat.period)
            ev["phase_angle"][k] = inset
            h1 = ((seed * 2654435761) % 997) / 997.0
            h2 = ((seed * 40503 + 7) % 499) / 499.0
            side = seed & 3
            if side == 0:
                bx_, by_ = inset + h1 * (SCREEN_W - 2 * inset), inset
            elif side == 1:
                bx_, by_ = inset + h1 * (SCREEN_W - 2 * inset), SCREEN_H - inset
            elif side == 2:
                bx_, by_ = inset, inset + h2 * (SCREEN_H - 2 * inset)
            else:
                bx_, by_ = SCREEN_W - inset, inset + h2 * (SCREEN_H - 2 * inset)
            ang = ((seed * 69621) % 6283) / 1000.0
            self._spawn(world, pat, bx_, by_, ang, px, py)
        elif pat.emit == "hazard":                  # Luxúria: névoa SLOW
            hz = self._mm.get_pool("hazard")
            if hz.count >= hz.capacity - 1:
                return
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            x = 120.0 + ((seed * 2654435761) % 997) / 997.0 * (SCREEN_W - 240.0)
            y = 150.0 + ((seed * 40503 + 7) % 499) / 499.0 * (SCREEN_H - 250.0)
            packed = world.create_entity("hazard_entity")
            idx = packed & 0xFFFFFFFF
            trow = self._transform.dense_row_of(idx)
            tv2 = self._transform.active_view()
            tv2["position_x"][trow] = x
            tv2["position_y"][trow] = y
            tv2["scale_x"][trow] = tv2["scale_y"][trow] = pat.speed / 4.0
            srow = self._sprite.dense_row_of(idx)
            sv = self._sprite.active_view()
            sv["texture_id"][srow] = SHAPE_CIRCLE
            sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = 200, 70, 130
            sv["tint_a"][srow] = 80                 # névoa translúcida (M1!)
            sv["layer_z"][srow] = 2                 # atrás de tudo
            hrow = hz.dense_row_of(idx)
            hv = hz.active_view()
            hv["self"][hrow] = np.uint64(packed)
            hv["radius"][hrow] = pat.speed          # speed reusado como raio
            hv["t"][hrow] = pat.hp                  # hp reusado como duração
        elif pat.emit == "edge_burst":               # Classico: BLASTER
            seed = int(ev["shot_count"][k]); ev["shot_count"][k] += 1
            side = seed & 3
            h1 = ((seed * 2654435761) % 997) / 997.0
            h2 = ((seed * 40503 + 7) % 499) / 499.0
            if side == 0:
                ex, ey = h1 * SCREEN_W, -8.0
            elif side == 1:
                ex, ey = h1 * SCREEN_W, SCREEN_H + 8.0
            elif side == 2:
                ex, ey = -8.0, h2 * SCREEN_H
            else:
                ex, ey = SCREEN_W + 8.0, h2 * SCREEN_H
            aim = math.atan2(py - ey, px - ex)
            n = pat.count
            for j in range(n):
                th = aim if n == 1 else aim - pat.arc / 2 + pat.arc * j / (n - 1)
                self._spawn(world, pat, ex, ey, th, px, py)
        elif pat.emit == "laser":
            seed = int(ev["shot_count"][k])
            ev["shot_count"][k] += 1
            for j in range(pat.count):
                if self._laser.count >= self._laser.capacity:
                    return
                pos = 120.0 + ((seed * 2654435761 + j * 97561) % 997) / 997.0 \
                    * (SCREEN_H - 320.0)
                packed = world.create_entity("laser")
                idx = packed & 0xFFFFFFFF
                lrow = self._laser.dense_row_of(idx)
                lv = self._laser.active_view()
                lv["self"][lrow] = np.uint64(packed)
                lv["axis"][lrow] = LASER_H
                lv["pos"][lrow] = pos
                lv["half"][lrow] = LASER_HALF
                lv["telegraph_t"][lrow] = LASER_TELEGRAPH
                lv["fire_t"][lrow] = LASER_FIRE_DUR
                trow = self._transform.dense_row_of(idx)
                tv2 = self._transform.active_view()
                tv2["position_x"][trow] = SCREEN_W / 2
                tv2["position_y"][trow] = pos
                tv2["scale_x"][trow] = SCREEN_W / 8.0
                tv2["scale_y"][trow] = (LASER_HALF * 2 + 2) / 8.0
                srow = self._sprite.dense_row_of(idx)
                sv = self._sprite.active_view()
                sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = 130, 30, 45
                sv["tint_a"][srow] = 255
                sv["layer_z"][srow] = 8

    def _spawn(self, world, pat: PatternDef, x, y, theta, px, py):
        return self._spawn_as(world, pat, pat.bullet, x, y, theta, px, py)

    def _spawn_as(self, world, pat: PatternDef, bullet_sid: int,
                  x, y, theta, px, py):
        if self._eb.count >= self._eb.capacity - 1:
            return None                             # pool cheio: descarta
        arch = self._data.archetypes[bullet_sid]
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
        sv["texture_id"][srow] = SHAPE_CIRCLE
        r, g, b = PALETTE.get(arch.color, (255, 64, 90))
        sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = r, g, b
        sv["tint_a"][srow] = 255
        sv["layer_z"][srow] = 10
        erow = self._eb.dense_row_of(idx)
        eb = self._eb.active_view()
        eb["self"][erow] = np.uint64(packed)
        eb["tether"][erow] = TETHER_NONE
        eb["color"][erow] = arch.color
        eb["contact"][erow] = arch.contact
        eb["radius"][erow] = arch.radius
        eb["grazed"][erow] = 0
        eb["homing_t"][erow] = arch.homing_t
        eb["spin"][erow] = arch.spin
        eb["phase_p"][erow] = arch.phase_period
        eb["phase_t"][erow] = 0.0
        eb["gravity"][erow] = arch.gravity
        eb["bounces"][erow] = arch.bounces
        eb["fragment"][erow] = 1 if (arch.fragment or self._abissal) else 0
        eb["beh"][erow] = arch.beh
        eb["beh_t"][erow] = arch.p1
        eb["p1"][erow], eb["p2"][erow], eb["p3"][erow] = arch.p1, arch.p2, arch.p3
        eb["tgt_x"][erow], eb["tgt_y"][erow] = px, py   # snapshot p/ stop&go
        eb["stage"][erow] = 0
        return packed


# ===========================================================================
class EnemyBulletBehaviorSystem(ISystem):
    """Kernel vetorizado dos comportamentos de bala inimiga: homing, spin,
    phase, gravity (puxa o jogador), stop&go, boomerang, sleeper."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")
        self._clock = memory_manager.get_pool("clock")

    def update(self, world: "World", delta_time: float) -> None:
        # balas congeladas (DILATAÇÃO) ou lentas (FOCUS) escalam os timers
        delta_time *= float(self._clock.active_view()["bullets"][0])
        if delta_time <= 0.0:
            return
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
        self._mm = memory_manager
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._sprite = memory_manager.get_pool("sprite")
        self._player = memory_manager.get_pool("player")
        self._mods = memory_manager.get_pool("run_mods")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_range = memory_manager.get_pool("pb_range")
        self._pb_life = memory_manager.get_pool("pb_life")
        self._pb_pierce = memory_manager.get_pool("pb_pierce")
        self._pb_bounce = memory_manager.get_pool("pb_bounce")

    def _spawn_fragments(self, world, x: float, y: float,
                         vx: float, vy: float, color: int) -> None:
        """ABISSAL: 2 fragmentos em ±30° da direção de retorno, herdando
        a velocidade escalar e a cor do pai. Fragmentos não re-fragmentam."""
        spd = math.hypot(vx, vy)
        if spd < 1.0 or self._eb.count >= self._eb.capacity - 2:
            return
        back = math.atan2(-vy, -vx)
        for dth in (-0.524, 0.524):
            packed = world.create_entity("enemy_bullet")
            idx = packed & 0xFFFFFFFF
            th = back + dth
            trow = self._transform.dense_row_of(idx)
            tvf = self._transform.active_view()
            tvf["position_x"][trow] = min(max(x, 1.0), SCREEN_W - 1.0)
            tvf["position_y"][trow] = min(max(y, 1.0), SCREEN_H - 1.0)
            tvf["scale_x"][trow] = tvf["scale_y"][trow] = 1.0
            vrow = self._velocity.dense_row_of(idx)
            vvf = self._velocity.active_view()
            vvf["linear_x"][vrow] = math.cos(th) * spd
            vvf["linear_y"][vrow] = math.sin(th) * spd
            srow = self._sprite.dense_row_of(idx)
            svf = self._sprite.active_view()
            svf["texture_id"][srow] = SHAPE_CIRCLE
            r, g, b = PALETTE.get(int(color), (255, 64, 90))
            svf["tint_r"][srow], svf["tint_g"][srow], svf["tint_b"][srow] = r, g, b
            svf["tint_a"][srow] = 255
            svf["layer_z"][srow] = 10
            erow = self._eb.dense_row_of(idx)
            ebf = self._eb.active_view()
            ebf["self"][erow] = np.uint64(packed)
            ebf["tether"][erow] = TETHER_NONE
            ebf["color"][erow] = color
            ebf["contact"][erow] = 0
            ebf["radius"][erow] = 4.0
            ebf["grazed"][erow] = 0
            ebf["homing_t"][erow] = 0.0
            ebf["spin"][erow] = 0.0
            ebf["phase_p"][erow] = 0.0
            ebf["phase_t"][erow] = 0.0
            ebf["gravity"][erow] = 0.0
            ebf["bounces"][erow] = 0
            ebf["fragment"][erow] = 0
            ebf["beh"][erow] = BEH_NONE
            ebf["beh_t"][erow] = 0.0
            ebf["stage"][erow] = 0

    def update(self, world: "World", delta_time: float) -> None:
        tv = self._transform.active_view()
        vv = self._velocity.active_view()
        mods = self._mods.active_view()

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
            # ABISSAL/fragmenting: revenge bullets antes do cull
            frag = out & (eb["fragment"] != 0)
            for k in np.where(frag)[0]:
                self._spawn_fragments(
                    world,
                    float(bx[k]), float(by[k]),
                    float(vv["linear_x"][vrows[k]]),
                    float(vv["linear_y"][vrows[k]]),
                    int(eb["color"][k]))
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

        # ---- clamp do jogador (CLAUSTROFOBIA encolhe 14% por borda) --------
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow >= 0:
            mx = SCREEN_W * 0.14 if mods["claustro"][0] else 9.0
            my = SCREEN_H * 0.14 if mods["claustro"][0] else 9.0
            tv["position_x"][ptrow] = min(max(float(tv["position_x"][ptrow]), mx), SCREEN_W - mx)
            tv["position_y"][ptrow] = min(max(float(tv["position_y"][ptrow]), my), SCREEN_H - my)


# ===========================================================================
class PlayerHitSystem(ISystem):
    """Jogador × balas inimigas: check vetorizado completo (regras de
    contato Yin/Yang, janela sólida do phaser, graze no anel externo)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._mm = memory_manager
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")
        self._mods = memory_manager.get_pool("run_mods")
        self._stats = memory_manager.get_pool("stats")
        self._mastery = memory_manager.get_pool("mastery")

    def _absorb_or_damage(self, world, pv, prow, px: float, py: float) -> None:
        """Aplica um hit no jogador respeitando o ESCUDO."""
        if pv["shield_up"][prow]:
            pv["shield_up"][prow] = 0
            pv["invuln_t"][prow] = 0.5
            spawn_particles(world, self._mm, px, py, (120, 255, 160), 10,
                            seed=int(px))
            add_sfx(self._mm, SFX_SHIELD)
            sd = self._data.skills.get(int(pv["skill_id"][prow]))
            # SHIELD+ bloco perfeito: anel de balas + reembolso de CD
            if sd is not None and sd.name == "shield+" \
                    and float(pv["skill_age"][prow]) < sd.perfect:
                pv["skill_cd"][prow] *= (1.0 - sd.refund)
                if self._mastery.count:
                    self._mastery.active_view()["shield_perfects"][0] += 1
                for j in range(sd.ring_n):
                    th = j * (TWO_PI / sd.ring_n)
                    spawn_player_bullet(world, self._mm, "pb_padrao", px, py,
                                        math.cos(th) * sd.ring_spd,
                                        math.sin(th) * sd.ring_spd,
                                        1.0, 4.0, color=(120, 255, 160))
            return
        pv["invuln_t"][prow] = PLAYER_INVULN
        pv["lives"][prow] -= 1
        spawn_particles(world, self._mm, px, py, (240, 240, 255), 14,
                        speed=220.0, seed=int(px + py))
        add_shake(self._mm, 8.0)
        add_sfx(self._mm, SFX_HIT)

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
                self._absorb_or_damage(world, pv, prow, px, py)
                if pv["lives"][prow] < 0:          # game over
                    if not handle_player_death(pv, prow,
                                               self._mods.active_view(),
                                               self._stats.active_view()):
                        for h in eb["self"][: self._eb.count]:
                            world.destroy_entity(int(h))   # respawn limpa
                    return

        graze = (eb["grazed"] == 0) & harmful & (d2 <= PLAYER_GRAZE_R ** 2) & (d2 > hit_r2)
        cnt = int(graze.sum())
        if cnt:
            eb["grazed"][graze] = 1
            pv["graze"][prow] += cnt
            if self._mastery.count:                 # DASH+: graze durante i-frames
                sd = self._data.skills.get(int(pv["skill_id"][prow]))
                if sd is not None and sd.name == "dash+" and \
                        float(pv["skill_t"][prow]) > 0.0:
                    self._mastery.active_view()["dash_graze"][0] += cnt

        # TETHER: o arame entre o par fere se o jogador cruza o segmento
        te = eb["tether"] != TETHER_NONE
        if te.any() and pv["invuln_t"][prow] <= 0.0:
            tv = self._transform.active_view()
            for k in np.where(te)[0]:
                partner = int(eb["tether"][k])
                if not world.is_alive(partner):
                    eb["tether"][k] = TETHER_NONE
                    continue
                if int(eb["self"][k]) > partner:    # processa cada par 1×
                    continue
                ptr = self._transform.dense_row_of(partner & 0xFFFFFFFF)
                ax = float(tv["position_x"][trows[k]])
                ay = float(tv["position_y"][trows[k]])
                bx_ = float(tv["position_x"][ptr])
                by_ = float(tv["position_y"][ptr])
                sx, sy = bx_ - ax, by_ - ay
                l2 = sx * sx + sy * sy
                t = 0.0 if l2 == 0.0 else max(0.0, min(1.0, ((px - ax) * sx + (py - ay) * sy) / l2))
                qx, qy = ax + t * sx, ay + t * sy
                if (px - qx) ** 2 + (py - qy) ** 2 <= PLAYER_HIT_R ** 2:
                    self._absorb_or_damage(world, pv, prow, px, py)
                    if pv["lives"][prow] < 0:
                        handle_player_death(pv, prow, self._mods.active_view(),
                                            self._stats.active_view())
                    break


# ===========================================================================
class PlayerBulletVsBossSystem(ISystem):
    """Balas do jogador × AABB do boss: dano normal consome; AGULHA+
    atravessa com cooldown; PLASMA aplica DPS sem nunca ser consumida
    (a regra que corrigiu o bug do plasma no legado)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._mm = memory_manager
        self._data = data
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_pierce = memory_manager.get_pool("pb_pierce")
        self._pb_dot = memory_manager.get_pool("pb_dot")
        self._pb_shrap = memory_manager.get_pool("pb_shrap")
        self._pb_orbit = memory_manager.get_pool("pb_orbit")
        self._transform = memory_manager.get_pool("transform")
        self._hitbox = memory_manager.get_pool("hitbox")
        self._boss = memory_manager.get_pool("boss")
        self._part = memory_manager.get_pool("part")
        self._player = memory_manager.get_pool("player")
        self._mastery = memory_manager.get_pool("mastery")
        self._dot_contact_this_frame = False

    def update(self, world: "World", delta_time: float) -> None:
        if self._pb_core.count == 0 or self._boss.count == 0:
            return
        tv = self._transform.active_view()
        pb_idx = self._pb_core.active_entity_indices()
        pb_trows = self._transform.dense_rows_of(pb_idx)
        bxs = tv["position_x"][pb_trows]
        bys = tv["position_y"][pb_trows]
        cv = self._pb_core.active_view()

        # PADRÃO/SPREAD (masteries): arma nunca troca no meio da run — o
        # weapon_id do jogador já identifica TODAS as balas na tela
        weapon_name = ""
        overclock_on = False
        pi = self._player.active_entity_indices()
        if pi.size and self._mastery.count:
            prow = self._player.dense_row_of(int(pi[0]))
            pv = self._player.active_view()
            wd = self._data.weapons.get(int(pv["weapon_id"][prow]))
            weapon_name = wd.name if wd is not None else ""
            sd = self._data.skills.get(int(pv["skill_id"][prow]))
            overclock_on = sd is not None and sd.name.startswith("overclock") \
                and float(pv["skill_t"][prow]) > 0.0

        self._dot_contact_this_frame = False
        # bosses com hitbox própria (classic/timemage/twins)
        for raw in self._boss.active_entity_indices():
            bi = int(raw)
            self._collide_aabb(world, bi, bi, tv, pb_idx, bxs, bys, cv,
                               delta_time, weapon_name, overclock_on)
        # partes de boss composto (wall/swarm) — dano roteado à raiz
        pvw = self._part.active_view()
        p_idxs = self._part.active_entity_indices()
        for k in range(self._part.count):
            self._collide_aabb(world, int(p_idxs[k]), int(pvw["root"][k]),
                               tv, pb_idx, bxs, bys, cv, delta_time,
                               weapon_name, overclock_on)

        if self._mastery.count:                   # PLASMA+: contato contínuo
            mv = self._mastery.active_view()
            if self._dot_contact_this_frame:
                mv["plasma_contact"][0] += delta_time
                mv["plasma_max"][0] = max(mv["plasma_max"][0],
                                          mv["plasma_contact"][0])
            else:
                mv["plasma_contact"][0] = 0.0

    def _collide_aabb(self, world, hit_entity: int, boss_entity: int, tv,
                      pb_idx, bxs, bys, cv, delta_time: float,
                      weapon_name: str, overclock_on: bool = False) -> None:
        btrow = self._transform.dense_row_of(hit_entity)
        hrow = self._hitbox.dense_row_of(hit_entity)
        brow = self._boss.dense_row_of(boss_entity)
        if btrow < 0 or hrow < 0 or brow < 0:
            return
        if self._boss.active_view()["invuln"][brow]:   # gimmick dos pecados
            return
        hv = self._hitbox.active_view()
        cx = float(tv["position_x"][btrow]); cy = float(tv["position_y"][btrow])
        hw = float(hv["half_width"][hrow]); hh = float(hv["half_height"][hrow])
        inside = ((bxs >= cx - hw) & (bxs <= cx + hw) &
                  (bys >= cy - hh) & (bys <= cy + hh))
        if not inside.any():
            return

        bv = self._boss.active_view()
        mv = self._mastery.active_view() if self._mastery.count else None

        # PLASMA (DoT): dano contínuo, bala nunca consumida
        drows = self._pb_dot.dense_rows_of(pb_idx)
        is_dot = drows != -1
        dot_in = inside & is_dot
        if dot_in.any():
            dv = self._pb_dot.active_view()
            total_dps = float(np.sum(dv["dps"][drows[dot_in]]))
            bv["hp"][brow] -= total_dps * delta_time
            self._dot_contact_this_frame = True

        # Dano de impacto (consome, exceto pierce em cooldown)
        prows = self._pb_pierce.dense_rows_of(pb_idx)
        is_pierce = prows != -1
        orows = self._pb_orbit.dense_rows_of(pb_idx)
        is_orbit = orows != -1
        impact = inside & ~is_dot
        if impact.any():
            pv = self._pb_pierce.active_view()
            # pierce pronto: causa dano e entra em CD (não consome)
            pierce_ready = impact & is_pierce
            if pierce_ready.any():
                ready = pv["t"][prows[pierce_ready]] <= 0.0
                rows_sel = np.where(pierce_ready)[0][ready]
                dmg = float(np.sum(cv["damage"][rows_sel]))
                bv["hp"][brow] -= dmg
                pv["t"][prows[rows_sel]] = pv["cd"][prows[rows_sel]]
                if mv is not None and rows_sel.size:
                    if weapon_name.startswith("satelite"):
                        mv["orbit_damage"][0] += dmg   # SATÉLITE+ (interceptor)
                    if overclock_on:
                        mv["oc_dmg"][0] += dmg
                        mv["oc_dmg_max"][0] = max(mv["oc_dmg_max"][0], mv["oc_dmg"][0])
            # bala normal: dano + destruição (+ CARREGADO+ estilhaça)
            normal = impact & ~is_pierce
            if normal.any():
                dmg = float(np.sum(cv["damage"][normal]))
                bv["hp"][brow] -= dmg
                if mv is not None:
                    if overclock_on:
                        mv["oc_dmg"][0] += dmg
                        mv["oc_dmg_max"][0] = max(mv["oc_dmg_max"][0], mv["oc_dmg"][0])
                    orbit_hit = normal & is_orbit
                    if orbit_hit.any():              # SATÉLITE: dano das gemas
                        mv["orbit_damage"][0] += float(np.sum(cv["damage"][orbit_hit]))
                    if weapon_name.startswith("padrao"):        # PADRÃO+
                        mv["default_streak"][0] += int(normal.sum())
                        mv["default_max"][0] = max(mv["default_max"][0],
                                                   mv["default_streak"][0])
                    elif weapon_name.startswith("spread"):      # SPREAD+
                        near = normal & (np.hypot(bxs - cx, bys - cy) < 40.0)
                        mv["spread_close"][0] += int(near.sum())
                for k in np.where(normal)[0][:4]:   # faíscas de impacto
                    spawn_particles(world, self._mm, float(bxs[k]),
                                    float(bys[k]), (255, 220, 150), 2,
                                    speed=110.0, ttl=0.25, seed=int(bxs[k]))
                srows = self._pb_shrap.dense_rows_of(pb_idx)
                sv = self._pb_shrap.active_view() if self._pb_shrap.count else None
                for k in np.where(normal)[0]:
                    srow = int(srows[k])
                    if sv is not None and srow != -1 and int(sv["n"][srow]) > 0:
                        sn = int(sv["n"][srow])
                        for j in range(sn):
                            th = j * (TWO_PI / sn)
                            spawn_player_bullet(
                                world, self._mm, "pb_padrao",
                                float(bxs[k]), float(bys[k]),
                                math.cos(th) * float(sv["speed"][srow]),
                                math.sin(th) * float(sv["speed"][srow]),
                                float(sv["dmg"][srow]), 3.0,
                                color=(255, 200, 60))
                    world.destroy_entity(int(cv["self"][k]))


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


# ===========================================================================
class GhostTintSystem(ISystem):
    """Mutador FANTASMA: balas inimigas ficam invisíveis entre 200-400px
    do boss (o renderer placeholder ignora alpha, então o tint vai a
    preto — invisível no fundo preto — e é restaurado pela PALETTE)."""

    GHOST_NEAR, GHOST_FAR = 200.0, 400.0

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._eb = memory_manager.get_pool("enemy_bullet")
        self._transform = memory_manager.get_pool("transform")
        self._sprite = memory_manager.get_pool("sprite")
        self._boss = memory_manager.get_pool("boss")
        self._mods = memory_manager.get_pool("run_mods")

    def update(self, world: "World", delta_time: float) -> None:
        if not self._mods.active_view()["ghost"][0]:
            return
        n = self._eb.count
        if n == 0 or self._boss.count == 0:
            return
        tv = self._transform.active_view()
        btrow = self._transform.dense_row_of(int(self._boss.active_entity_indices()[0]))
        bx = float(tv["position_x"][btrow]); by = float(tv["position_y"][btrow])
        eb = self._eb.active_view()
        idxs = self._eb.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        srows = self._sprite.dense_rows_of(idxs)
        dx = tv["position_x"][trows] - bx
        dy = tv["position_y"][trows] - by
        d2 = dx * dx + dy * dy
        hidden = (d2 > self.GHOST_NEAR ** 2) & (d2 < self.GHOST_FAR ** 2)
        sv = self._sprite.active_view()
        sv["tint_r"][srows[hidden]] = 0
        sv["tint_g"][srows[hidden]] = 0
        sv["tint_b"][srows[hidden]] = 0
        vis = ~hidden
        if vis.any():                                # restaura pela PALETTE
            for cid, (r, g, b) in PALETTE.items():
                m = vis & (eb["color"] == cid)
                if m.any():
                    sv["tint_r"][srows[m]] = r
                    sv["tint_g"][srows[m]] = g
                    sv["tint_b"][srows[m]] = b


# ===========================================================================
# Cor da barra de HP por tier da DDA (legado: GREEN/YELLOW/RED_COL na borda,
# main.py:980-981) — aqui usada no preenchimento, que já escala com o hp_frac.
_TIER_COLOR = {1: (0, 220, 0), 2: (255, 220, 0), 3: (220, 20, 60)}


class HudSystem(ISystem):
    """HUD de retângulos (o renderer placeholder não tem texto): barra de
    HP do boss no topo, quadrados de vida embaixo à esquerda, barra de
    CD/energia da habilidade embaixo à direita."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._hud = memory_manager.get_pool("hud")
        self._transform = memory_manager.get_pool("transform")
        self._sprite = memory_manager.get_pool("sprite")
        self._boss = memory_manager.get_pool("boss")
        self._player = memory_manager.get_pool("player")
        self._wave = memory_manager.get_pool("wave")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._hud.count
        if n == 0:
            return
        hv = self._hud.active_view()
        idxs = self._hud.active_entity_indices()
        tv = self._transform.active_view()
        sv = self._sprite.active_view()

        bvv = self._boss.active_view()
        hp_frac = 0.0
        tier = 1
        if self._boss.count:
            hp_frac = float(np.sum(bvv["hp"][: self._boss.count])) / \
                      max(1.0, float(np.sum(bvv["max_hp"][: self._boss.count])))
            tier = int(np.max(bvv["tier"][: self._boss.count]))  # pior tier vivo

        pi = self._player.active_entity_indices()
        lives, cd_frac = 0, 0.0
        if pi.size:
            prow = self._player.dense_row_of(int(pi[0]))
            pv = self._player.active_view()
            lives = int(pv["lives"][prow])
            sd = self._data.skills.get(int(pv["skill_id"][prow]))
            if sd is not None and sd.name != "none":
                if sd.name.startswith("focus"):
                    cd_frac = float(pv["focus_en"][prow]) / FOCUS_MAX
                elif sd.cd > 0.0:
                    cd_frac = 1.0 - min(max(float(pv["skill_cd"][prow]) / sd.cd, 0.0), 1.0)

        for k in range(n):                           # ≤8 elementos de HUD
            kind = int(hv["kind"][k])
            trow = self._transform.dense_row_of(int(idxs[k]))
            srow = self._sprite.dense_rows_of(idxs[k:k + 1])[0]
            if kind == 0:                            # barra de HP do boss
                tv["scale_x"][trow] = max(0.01, 400.0 * hp_frac / 8.0)
                tv["scale_y"][trow] = 10.0 / 8.0
                r, g, b = _TIER_COLOR.get(tier, (255, 70, 100))
                sv["tint_r"][srow], sv["tint_g"][srow], sv["tint_b"][srow] = r, g, b
            elif kind in (1, 2, 3):                  # vidas
                on = lives >= kind
                sv["tint_r"][srow] = 240 if on else 40
                sv["tint_g"][srow] = 240 if on else 40
                sv["tint_b"][srow] = 255 if on else 55
            elif kind == 4:                          # CD/energia da skill
                tv["scale_x"][trow] = max(0.01, 140.0 * cd_frac / 8.0)
                tv["scale_y"][trow] = 8.0 / 8.0
                full = cd_frac >= 0.999
                sv["tint_r"][srow] = 90 if full else 200
                sv["tint_g"][srow] = 220 if full else 160
                sv["tint_b"][srow] = 140 if full else 60
            elif kind == 5:                          # progresso das ondas
                frac = 0.0
                if self._wave.count:
                    frac = max(0, int(self._wave.active_view()["idx"][0]) + 1) \
                        / max(1, len(self._data.waves))
                tv["scale_x"][trow] = max(0.01, 200.0 * frac / 8.0)
                tv["scale_y"][trow] = 6.0 / 8.0


# ===========================================================================
class OrbitSystem(ISystem):
    """SATÉLITE (gemas) e TELEGUIADO+ (mísseis em espera): Transform é
    derivada do jogador — roda DEPOIS do PhysicsSystem e sobrescreve."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._pb_orbit = memory_manager.get_pool("pb_orbit")
        self._transform = memory_manager.get_pool("transform")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pb_orbit.count
        if n == 0:
            return
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        ov = self._pb_orbit.active_view()
        ov["angle"] += ov["ang_speed"] * delta_time
        idxs = self._pb_orbit.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        tv["position_x"][trows] = px + np.cos(ov["angle"]) * ov["radius"]
        tv["position_y"][trows] = py + np.sin(ov["angle"]) * ov["radius"]


# ===========================================================================
class PlayerBulletDelaySystem(ISystem):
    """BURST+ (minas de atraso): após armar (t≤0), dispara na direção
    capturada a vmax. t vai a 1e9 para nunca rearmar."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._pb_delay = memory_manager.get_pool("pb_delay")
        self._velocity = memory_manager.get_pool("velocity")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pb_delay.count
        if n == 0:
            return
        dv = self._pb_delay.active_view()
        pending = dv["t"] < 1e8
        if not pending.any():
            return
        dv["t"][pending] -= delta_time
        fire = pending & (dv["t"] <= 0.0)
        if fire.any():
            idxs = self._pb_delay.active_entity_indices()
            vrows = self._velocity.dense_rows_of(idxs)
            vv = self._velocity.active_view()
            vv["linear_x"][vrows[fire]] = dv["ax"][fire] * dv["vmax"][fire]
            vv["linear_y"][vrows[fire]] = dv["ay"][fire] * dv["vmax"][fire]
            dv["t"][fire] = 1e9


# ===========================================================================
class FuseSystem(ISystem):
    """FLAK: fusível detona em estilhaços (5 × 0.4 dano, leque 40° para
    cima, 400px/s). FLAK+ (detonador): fire seguro congela os fusíveis;
    soltar zera todos (detonação simultânea)."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider,
                 data: GameData) -> None:
        self._input = input_provider
        self._data = data
        self._mm = memory_manager
        self._pb_fuse = memory_manager.get_pool("pb_fuse")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._transform = memory_manager.get_pool("transform")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pb_fuse.count
        if n == 0:
            return
        fv = self._pb_fuse.active_view()
        i, _ = _player_row(self._player, self._transform)
        if i >= 0:
            prow = self._player.dense_row_of(i)
            wd = self._data.weapons.get(
                int(self._player.active_view()["weapon_id"][prow]))
            if wd is not None and wd.name == "flak+":
                fv["frozen"][:] = 1 if self._input.is_action_held("fire") else 0
                if self._input.is_action_released("fire"):
                    fv["t"][:] = 0.0

        ticking = fv["frozen"] == 0
        fv["t"][ticking] -= delta_time
        expired = fv["t"] <= 0.0
        if not expired.any():
            return
        idxs = self._pb_fuse.active_entity_indices()
        tv = self._transform.active_view()
        cv = self._pb_core.active_view()
        for k in np.where(expired)[0]:
            eidx = int(idxs[k])
            trow = self._transform.dense_row_of(eidx)
            x = float(tv["position_x"][trow]); y = float(tv["position_y"][trow])
            crow = self._pb_core.dense_row_of(eidx)
            world.destroy_entity(int(cv["self"][crow]))
            for j in range(FLAK_SHRAP_N):
                th = -math.pi / 2 - FLAK_SHRAP_ARC / 2 + \
                     FLAK_SHRAP_ARC * j / (FLAK_SHRAP_N - 1)
                spawn_player_bullet(world, self._mm, "pb_padrao", x, y,
                                    math.cos(th) * FLAK_SHRAP_SPD,
                                    math.sin(th) * FLAK_SHRAP_SPD,
                                    FLAK_SHRAP_DMG, 3.0, color=(255, 160, 40))


# ===========================================================================
class ChakramSystem(ISystem):
    """CHAKRAM: drag desacelera; no ápice inverte e retorna ao jogador
    (captura a 22px). CHAKRAM+ (congelador): fire seguro no ápice congela
    o disco aplicando DPS ao boss; soltar retoma o retorno."""

    def __init__(self, memory_manager: MemoryManager, input_provider: IInputProvider,
                 data: GameData) -> None:
        self._input = input_provider
        self._data = data
        self._pb_chakram = memory_manager.get_pool("pb_chakram")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")
        self._boss = memory_manager.get_pool("boss")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._pb_chakram.count
        if n == 0:
            return
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        prow = self._player.dense_row_of(i)
        wd = self._data.weapons.get(
            int(self._player.active_view()["weapon_id"][prow]))
        is_plus = wd is not None and wd.name == "chakram+"
        held = self._input.is_action_held("fire")

        kv = self._pb_chakram.active_view()
        idxs = self._pb_chakram.active_entity_indices()
        vv = self._velocity.active_view()
        cv = self._pb_core.active_view()
        for k in range(n):                          # ≤ poucos discos
            eidx = int(idxs[k])
            vrow = self._velocity.dense_row_of(eidx)
            vx = float(vv["linear_x"][vrow]); vy = float(vv["linear_y"][vrow])
            spd = math.hypot(vx, vy)
            state = int(kv["state"][k])
            if state == CHAKRAM_OUT:
                if spd > 12.0:
                    f = max(0.0, 1.0 - CHAKRAM_DRAG * delta_time / spd)
                    vv["linear_x"][vrow] = vx * f
                    vv["linear_y"][vrow] = vy * f
                elif is_plus and held:
                    kv["state"][k] = CHAKRAM_FROZEN
                    vv["linear_x"][vrow] = vv["linear_y"][vrow] = 0.0
                else:
                    kv["state"][k] = CHAKRAM_RETURN
            elif state == CHAKRAM_FROZEN:
                if self._boss.count > 0:
                    bv = self._boss.active_view()
                    bv["hp"][0] -= float(kv["dps"][k]) * delta_time
                if not held:
                    kv["state"][k] = CHAKRAM_RETURN
            else:                                   # CHAKRAM_RETURN
                trow = self._transform.dense_row_of(eidx)
                dx = px - float(tv["position_x"][trow])
                dy = py - float(tv["position_y"][trow])
                d = math.hypot(dx, dy) or 1.0
                vv["linear_x"][vrow] = dx / d * 580.0
                vv["linear_y"][vrow] = dy / d * 580.0
                if d < CHAKRAM_CATCH_R:
                    crow = self._pb_core.dense_row_of(eidx)
                    world.destroy_entity(int(cv["self"][crow]))


# ===========================================================================
class BossGimmickSystem(ISystem):
    """Gimmicks dos pecados, declarados por fase em bosses.json:
    `force` empurra o jogador (Gula/Soberba); `spotlight` (Soberba fase 0)
    varre um holofote e só deixa o boss vulnerável com o jogador dentro;
    `gate_minions` (Preguiça fase 1) mantém o boss invulnerável até os
    fantasmas morrerem. Roda após o BossMotion e antes do Emitter (o
    spotlight_rain lê aux_angle)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._mm = memory_manager
        self._boss = memory_manager.get_pool("boss")
        self._transform = memory_manager.get_pool("transform")
        self._minion = memory_manager.get_pool("minion")
        self._player = memory_manager.get_pool("player")
        self._waypoint = memory_manager.get_pool("waypoint")
        self._clock = memory_manager.get_pool("clock")
        self._mods = memory_manager.get_pool("run_mods")
        self._stats = memory_manager.get_pool("stats")
        self._hud = memory_manager.get_pool("hud")
        self._sprite = memory_manager.get_pool("sprite")

    def _update_beam(self, spot_x: float, player_inside: bool,
                     visible: bool) -> None:
        """Posiciona o feixe visual do holofote (elemento HUD kind 6)."""
        hv = self._hud.active_view()
        idxs = self._hud.active_entity_indices()
        for k in range(self._hud.count):
            if int(hv["kind"][k]) != 6:
                continue
            eidx = int(idxs[k])
            trow = self._transform.dense_row_of(eidx)
            srow = self._sprite.dense_row_of(eidx)
            tv = self._transform.active_view()
            sv = self._sprite.active_view()
            tv["position_x"][trow] = spot_x
            sv["tint_a"][srow] = (0 if not visible
                                  else 90 if player_inside else 42)
            return

    def _hit_player(self, pv, prow) -> None:
        """Hit de contato de gimmick (corpo da Ira), escudo/glass-aware."""
        if pv["invuln_t"][prow] > 0.0:
            return
        if pv["shield_up"][prow]:
            pv["shield_up"][prow] = 0
            pv["invuln_t"][prow] = 0.5
            return
        pv["invuln_t"][prow] = PLAYER_INVULN
        pv["lives"][prow] -= 1
        add_shake(self._mm, 8.0)
        if pv["lives"][prow] < 0:
            handle_player_death(pv, prow, self._mods.active_view(),
                                self._stats.active_view())

    def update(self, world: "World", delta_time: float) -> None:
        ck = self._clock.active_view()
        ck["invert"][0] = 0
        wdt = delta_time * float(ck["world"][0])
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow])
        py = float(tv["position_y"][ptrow])
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        bv = self._boss.active_view()
        wpv = self._waypoint.active_view()
        spotlight_on = False
        for raw in self._boss.active_entity_indices():
            bi = int(raw)
            brow = self._boss.dense_row_of(bi)
            bdef = self._data.bosses[int(bv["boss_id"][brow])]
            ph = bdef.phases[int(bv["phase_idx"][brow])]

            if ph.force != (0.0, 0.0):              # sucção/empuxo no jogador
                tv["position_x"][ptrow] += ph.force[0] * delta_time
                tv["position_y"][ptrow] += ph.force[1] * delta_time

            gm = ph.gimmick
            if gm == "spotlight":
                spot = float(bv["aux_angle"][brow])
                direction = 1.0 if bv["aux2"][brow] >= 0.0 else -1.0
                spot += SPOT_SWEEP * direction * wdt
                if spot > SCREEN_W:
                    spot, direction = float(SCREEN_W), -1.0
                elif spot < 0.0:
                    spot, direction = 0.0, 1.0
                bv["aux_angle"][brow] = spot
                bv["aux2"][brow] = direction
                # vulnerável só com o jogador dentro do feixe
                inside = abs(px - spot) <= SPOT_HALF
                bv["invuln"][brow] = 0 if inside else 1
                self._update_beam(spot, inside, True)
                spotlight_on = True

            elif gm == "gate_minions":
                bv["invuln"][brow] = 1 if self._minion.count > 0 else 0

            elif gm == "skill_thief":               # Inveja: CD recupera à metade
                bv["invuln"][brow] = 0
                if pv["skill_cd"][prow] > 0.0:
                    pv["skill_cd"][prow] += 0.5 * delta_time

            elif gm == "invert_controls":           # Luxúria: atração fatal
                bv["invuln"][brow] = 0
                ck["invert"][0] = 1

            elif gm == "slam":                      # Ira: onda de choque
                bv["invuln"][brow] = 0
                st = int(bv["aux2"][brow])
                tmr = float(bv["aux_angle"][brow]) - wdt
                trow = self._transform.dense_row_of(bi)
                y = float(tv["position_y"][trow])
                if st == 0 and tmr <= 0.0:          # topo → mergulha
                    st, tmr = 1, 0.4
                elif st == 1:                       # mergulhando
                    y += (SCREEN_H - 80.0 - y) * 12.0 * wdt
                    if abs(y - (SCREEN_H - 80.0)) < 5.0 or tmr <= 0.0:
                        y = SCREEN_H - 80.0
                        st, tmr = 2, 0.6
                        bx0 = float(tv["position_x"][trow])
                        for j in range(12):         # anel de impacto
                            a = j * (TWO_PI / 12.0)
                            spawn_enemy_bullet(world, self._mm, bx0, y,
                                               math.cos(a) * 160.0,
                                               math.sin(a) * 160.0, color=2)
                elif st == 2 and tmr <= 0.0:        # chão → sobe
                    st, tmr = 3, 0.5
                elif st == 3:                       # subindo
                    y += (50.0 - y) * 8.0 * wdt
                    if abs(y - 50.0) < 5.0 or tmr <= 0.0:
                        y, st, tmr = 50.0, 0, 2.5
                tv["position_y"][trow] = y
                bv["aux2"][brow] = st
                bv["aux_angle"][brow] = tmr

            elif gm == "berserk_body":              # Ira: corpo em chamas 20s
                bv["invuln"][brow] = 1
                vx = float(bv["aux_angle"][brow]); vy = float(bv["aux2"][brow])
                if vx == 0.0 and vy == 0.0:
                    vx, vy = 320.0, 240.0
                trow = self._transform.dense_row_of(bi)
                x = float(tv["position_x"][trow]) + vx * wdt
                y = float(tv["position_y"][trow]) + vy * wdt
                if x < 26.0 or x > SCREEN_W - 26.0:
                    vx = -vx; x = min(max(x, 26.0), SCREEN_W - 26.0)
                if y < 26.0 or y > SCREEN_H - 26.0:
                    vy = -vy; y = min(max(y, 26.0), SCREEN_H - 26.0)
                f = 1.0 + 0.08 * wdt                # acelera até 600
                vx = math.copysign(min(abs(vx) * f, 600.0), vx)
                vy = math.copysign(min(abs(vy) * f, 600.0), vy)
                tv["position_x"][trow] = x
                tv["position_y"][trow] = y
                bv["aux_angle"][brow] = vx
                bv["aux2"][brow] = vy
                if (px - x) ** 2 + (py - y) ** 2 <= 36.0 ** 2:
                    self._hit_player(pv, prow)
                wrow = self._waypoint.dense_row_of(bi)
                if wrow >= 0:                       # esgota em 20s
                    wpv["seg_t"][wrow] += delta_time
                    if wpv["seg_t"][wrow] >= 20.0:
                        bv["hp"][brow] = 0.0

            elif gm == "seventh_seal":              # Pecado: sobreviva 30s
                bv["invuln"][brow] = 1
                wrow = self._waypoint.dense_row_of(bi)
                if wrow < 0:
                    continue
                wpv["seg_t"][wrow] += delta_time
                elapsed = float(wpv["seg_t"][wrow])
                rate = max(0.08, 0.25 - elapsed * 0.004)
                acc = float(bv["aux_angle"][brow]) + wdt
                while acc >= rate:
                    acc -= rate
                    seed = int(bv["aux2"][brow]); bv["aux2"][brow] += 1
                    for j in range(3):              # anel elíptico → jogador
                        a = ((seed * 2654435761 + j * 97561) % 6283) / 1000.0
                        rx = SCREEN_W / 2.0 + math.cos(a) * 480.0
                        ry = SCREEN_H / 2.0 + math.sin(a) * 300.0
                        dx = px - rx; dy = py - ry
                        d = math.hypot(dx, dy) or 1.0
                        spawn_enemy_bullet(world, self._mm, rx, ry,
                                           dx / d * 130.0, dy / d * 130.0,
                                           color=3, homing_t=3.0)
                bv["aux_angle"][brow] = acc
                if elapsed >= 30.0:                 # sobreviveu → boss cai
                    bv["hp"][brow] = 0.0

            elif bv["sw_t"][brow] <= 0.0:            # preserva o Segundo Fôlego
                bv["invuln"][brow] = 0
        if not spotlight_on:                        # apaga o feixe
            self._update_beam(0.0, False, False)


# ===========================================================================
class WaveSystem(ISystem):
    """Wave Survival (waves.json): spawna a composição da onda por
    intervalo; onda limpa (sem lacaios nem boss) → próxima; ondas 10/20/30
    são boss waves. Onda 30 vencida → recomeça (endless)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._mm = memory_manager
        self._wave = memory_manager.get_pool("wave")
        self._minion = memory_manager.get_pool("minion")
        self._boss = memory_manager.get_pool("boss")
        self._mods = memory_manager.get_pool("run_mods")
        self._clock = memory_manager.get_pool("clock")

    def update(self, world: "World", delta_time: float) -> None:
        if int(self._mods.active_view()["rush"][0]) != 3 or self._wave.count == 0:
            return
        delta_time *= float(self._clock.active_view()["world"][0])
        wv = self._wave.active_view()

        if self._boss.count > 0:                    # boss wave em andamento
            return
        if wv["pending"][0] > 0:                    # ainda spawnando
            wv["t"][0] -= delta_time
            if wv["t"][0] <= 0.0:
                wave = self._data.waves[int(wv["idx"][0])]
                wv["t"][0] = wave.interval
                wv["pending"][0] -= 1
                seed = int(wv["seed"][0]); wv["seed"][0] += 1
                h1 = ((seed * 2654435761) % 997) / 997.0
                frac_spawned = 1.0 - float(wv["pending"][0]) / max(1, wave.enemies)
                if frac_spawned <= wave.kamikaze_ratio:   # perseguidores 1º
                    spawn_minion(world, self._mm,
                                 60.0 + h1 * (SCREEN_W - 120.0), -12.0,
                                 MINION_KAMIKAZE, 2.0, 130.0)
                else:                               # sentinelas estáticas
                    h2 = ((seed * 40503 + 11) % 499) / 499.0
                    spawn_minion(world, self._mm,
                                 80.0 + h1 * (SCREEN_W - 160.0),
                                 100.0 + h2 * 260.0,
                                 MINION_SENTINEL, 3.0, 0.0)
            return
        if self._minion.count > 0:                  # limpe a onda primeiro
            return

        # onda limpa → avança (wrap: endless)
        nxt = (int(wv["idx"][0]) + 1) % len(self._data.waves)
        wv["idx"][0] = nxt
        wave = self._data.waves[nxt]
        if wave.boss:
            spawn_boss(world, self._mm, self._data, wave.boss)
        else:
            wv["pending"][0] = wave.enemies
            wv["t"][0] = 0.0


# ===========================================================================
class HazardSystem(ISystem):
    """Névoas SLOW da Luxúria: expiram por tempo; jogador dentro de uma
    zona tem a velocidade cortada pela metade (roda após o PlayerControl
    e antes do movimento)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._hazard = memory_manager.get_pool("hazard")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._hazard.count
        if n == 0:
            return
        hv = self._hazard.active_view()
        hv["t"] -= delta_time
        dead = hv["t"] <= 0.0
        for h in hv["self"][dead]:
            world.destroy_entity(int(h))

        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        idxs = self._hazard.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        dx = tv["position_x"][trows] - px
        dy = tv["position_y"][trows] - py
        inside = (~dead) & (dx * dx + dy * dy <= hv["radius"] ** 2)
        if inside.any():
            vrow = self._velocity.dense_row_of(i)
            vv = self._velocity.active_view()
            vv["linear_x"][vrow] *= 0.5
            vv["linear_y"][vrow] *= 0.5


# ===========================================================================
class MinionAISystem(ISystem):
    """Lacaios: kamikazes perseguem o jogador; sentinelas/bolhas ficam
    paradas (alvos a destruir). Integração no ScaledMovementSystem."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._minion = memory_manager.get_pool("minion")
        self._transform = memory_manager.get_pool("transform")
        self._velocity = memory_manager.get_pool("velocity")
        self._player = memory_manager.get_pool("player")

    def update(self, world: "World", delta_time: float) -> None:
        n = self._minion.count
        if n == 0:
            return
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        mv = self._minion.active_view()
        chase = mv["kind"] == MINION_KAMIKAZE
        idxs = self._minion.active_entity_indices()
        trows = self._transform.dense_rows_of(idxs)
        vrows = self._velocity.dense_rows_of(idxs)
        vv = self._velocity.active_view()
        if chase.any():
            dx = px - tv["position_x"][trows[chase]]
            dy = py - tv["position_y"][trows[chase]]
            d = np.sqrt(dx * dx + dy * dy) + 1e-6
            vv["linear_x"][vrows[chase]] = dx / d * mv["speed"][chase]
            vv["linear_y"][vrows[chase]] = dy / d * mv["speed"][chase]
        static = ~chase
        if static.any():
            vv["linear_x"][vrows[static]] = 0.0
            vv["linear_y"][vrows[static]] = 0.0


# ===========================================================================
class MinionCombatSystem(ISystem):
    """Balas do jogador × lacaios (impacto consome; PLASMA aplica DPS sem
    consumir) e contato lacaio × jogador (kamikaze: explode no toque)."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._mm = memory_manager
        self._minion = memory_manager.get_pool("minion")
        self._transform = memory_manager.get_pool("transform")
        self._player = memory_manager.get_pool("player")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_dot = memory_manager.get_pool("pb_dot")
        self._pb_pierce = memory_manager.get_pool("pb_pierce")
        self._mods = memory_manager.get_pool("run_mods")
        self._stats = memory_manager.get_pool("stats")

    def _explode_mine(self, world, x: float, y: float, count: int) -> None:
        """Moeda/mina: anel de balas ao explodir (Avareza 8, Pecado 16)."""
        spawn_particles(world, self._mm, x, y, (255, 215, 0), 10, seed=int(x))
        add_shake(self._mm, 4.0)
        add_sfx(self._mm, SFX_MINE)
        for j in range(max(1, count)):
            a = j * (TWO_PI / max(1, count))
            spawn_enemy_bullet(world, self._mm, x, y,
                               math.cos(a) * 190.0, math.sin(a) * 190.0,
                               color=2)

    def update(self, world: "World", delta_time: float) -> None:
        n = self._minion.count
        if n == 0:
            return
        tv = self._transform.active_view()
        mv = self._minion.active_view()
        m_idxs = self._minion.active_entity_indices()
        m_trows = self._transform.dense_rows_of(m_idxs)

        # balas do jogador × lacaios
        if self._pb_core.count:
            pb_idx = self._pb_core.active_entity_indices()
            pb_trows = self._transform.dense_rows_of(pb_idx)
            bxs = tv["position_x"][pb_trows]
            bys = tv["position_y"][pb_trows]
            cv = self._pb_core.active_view()
            drows = self._pb_dot.dense_rows_of(pb_idx)
            is_dot = drows != -1
            prows = self._pb_pierce.dense_rows_of(pb_idx)
            is_pierce = prows != -1
            for k in range(n):                      # ≤64 lacaios
                mx = float(tv["position_x"][m_trows[k]])
                my = float(tv["position_y"][m_trows[k]])
                inside = ((bxs >= mx - MINION_RADIUS) & (bxs <= mx + MINION_RADIUS) &
                          (bys >= my - MINION_RADIUS) & (bys <= my + MINION_RADIUS))
                if not inside.any():
                    continue
                dot_in = inside & is_dot
                if dot_in.any():
                    dv = self._pb_dot.active_view()
                    mv["hp"][k] -= float(np.sum(dv["dps"][drows[dot_in]])) * delta_time
                impact = inside & ~is_dot & ~is_pierce
                if impact.any():
                    mv["hp"][k] -= float(np.sum(cv["damage"][impact]))
                    for h in cv["self"][impact]:
                        world.destroy_entity(int(h))
                pierce_in = inside & is_pierce
                if pierce_in.any():
                    pv = self._pb_pierce.active_view()
                    ready = pv["t"][prows[pierce_in]] <= 0.0
                    sel = np.where(pierce_in)[0][ready]
                    mv["hp"][k] -= float(np.sum(cv["damage"][sel]))
                    pv["t"][prows[sel]] = pv["cd"][prows[sel]]
                if mv["hp"][k] <= 0.0:
                    world.destroy_entity(int(mv["self"][k]))

        # bolhas da Preguiça: estouram sozinhas num anel após 8s (mesmo
        # sem o jogador tocá-las — ETYPE_BUBBLE, BUBBLE_EXPLODE_T)
        bubbles = mv["kind"] == MINION_BUBBLE
        if bubbles.any():
            mv["timer"][bubbles] -= delta_time
            expired = bubbles & (mv["timer"] <= 0.0)
            if expired.any():
                for k in np.where(expired)[0]:
                    bx = float(tv["position_x"][m_trows[k]])
                    by = float(tv["position_y"][m_trows[k]])
                    for j in range(BUBBLE_BURST_N):
                        a = j * (TWO_PI / BUBBLE_BURST_N)
                        spawn_enemy_bullet(world, self._mm, bx, by,
                                           math.cos(a) * BUBBLE_BURST_SPD,
                                           math.sin(a) * BUBBLE_BURST_SPD)
                    world.destroy_entity(int(mv["self"][k]))

        # proximidade com o jogador: kamikaze explode em dano de contato;
        # minas/moedas explodem num anel de balas (sem hit direto)
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0:
            return
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        dx = tv["position_x"][m_trows] - px
        dy = tv["position_y"][m_trows] - py
        d2 = dx * dx + dy * dy
        mines = (mv["kind"] == MINION_MINE) & (d2 <= 45.0 ** 2)
        if mines.any():
            for k in np.where(mines)[0]:
                self._explode_mine(world, float(tv["position_x"][m_trows[k]]),
                                   float(tv["position_y"][m_trows[k]]),
                                   int(mv["speed"][k]))
                world.destroy_entity(int(mv["self"][k]))
        hit = (mv["kind"] == MINION_KAMIKAZE) & \
              (d2 <= (MINION_RADIUS + PLAYER_HIT_R) ** 2)
        if hit.any():
            for k in np.where(hit)[0]:              # kamikaze explode
                spawn_particles(world, self._mm,
                                float(tv["position_x"][m_trows[k]]),
                                float(tv["position_y"][m_trows[k]]),
                                (255, 120, 60), 8, seed=int(m_trows[k]))
                world.destroy_entity(int(mv["self"][k]))
            add_shake(self._mm, 6.0)
            prow = self._player.dense_row_of(i)
            pv = self._player.active_view()
            if pv["invuln_t"][prow] <= 0.0:
                if pv["shield_up"][prow]:
                    pv["shield_up"][prow] = 0
                    pv["invuln_t"][prow] = 0.5
                else:
                    pv["invuln_t"][prow] = PLAYER_INVULN
                    pv["lives"][prow] -= 1
                    if pv["lives"][prow] < 0:
                        handle_player_death(pv, prow,
                                            self._mods.active_view(),
                                            self._stats.active_view())


# ===========================================================================
class AutoLaunchSystem(ISystem):
    """SATÉLITE+ (interceptor): com o boss a ≤250px do jogador, a gema
    mais próxima do boss é convertida em míssil homing (CD 2.5s)."""

    def __init__(self, memory_manager: MemoryManager, data: GameData) -> None:
        self._data = data
        self._mm = memory_manager
        self._pb_orbit = memory_manager.get_pool("pb_orbit")
        self._pb_core = memory_manager.get_pool("pb_core")
        self._pb_homing = memory_manager.get_pool("pb_homing")
        self._transform = memory_manager.get_pool("transform")
        self._player = memory_manager.get_pool("player")
        self._boss = memory_manager.get_pool("boss")

    def update(self, world: "World", delta_time: float) -> None:
        i, ptrow = _player_row(self._player, self._transform)
        if ptrow < 0 or self._boss.count == 0:
            return
        prow = self._player.dense_row_of(i)
        pv = self._player.active_view()
        wd = self._data.weapons.get(int(pv["weapon_id"][prow]))
        if wd is None or wd.name != "satelite+":
            return
        if pv["aux_cd"][prow] > 0.0:
            pv["aux_cd"][prow] -= delta_time
            return
        tv = self._transform.active_view()
        px = float(tv["position_x"][ptrow]); py = float(tv["position_y"][ptrow])
        bi = int(self._boss.active_entity_indices()[0])
        btrow = self._transform.dense_row_of(bi)
        bx = float(tv["position_x"][btrow]); by = float(tv["position_y"][btrow])
        if math.hypot(bx - px, by - py) > INTERCEPT_RANGE:
            return

        ov = self._pb_orbit.active_view()
        idxs = self._pb_orbit.active_entity_indices()
        best_k, best_d = -1, 1e18
        for k in range(self._pb_orbit.count):
            if ov["kind"][k] != ORBIT_GEM:
                continue
            trow = self._transform.dense_row_of(int(idxs[k]))
            d = (float(tv["position_x"][trow]) - bx) ** 2 + \
                (float(tv["position_y"][trow]) - by) ** 2
            if d < best_d:
                best_d, best_k = d, k
        if best_k < 0:
            return
        eidx = int(idxs[best_k])
        trow = self._transform.dense_row_of(eidx)
        x = float(tv["position_x"][trow]); y = float(tv["position_y"][trow])
        crow = self._pb_core.dense_row_of(eidx)
        world.destroy_entity(int(self._pb_core.active_view()["self"][crow]))
        # míssil homing com o dano da gema
        base = self._data.weapons.get(sid("teleguiado"))
        dx = bx - x; dy = by - y
        d = math.hypot(dx, dy) or 1.0
        packed = spawn_player_bullet(world, self._mm, "pb_teleguiado", x, y,
                                     dx / d * 370.0, dy / d * 370.0,
                                     wd.damage, wd.size, color=(255, 220, 0))
        if packed >= 0:
            hrow = self._pb_homing.dense_row_of(packed & 0xFFFFFFFF)
            hv = self._pb_homing.active_view()
            hv["turn"][hrow] = 260.0
            hv["vmax"][hrow] = 370.0
            hv["t"][hrow] = 2.8
        pv["aux_cd"][prow] = INTERCEPT_CD
