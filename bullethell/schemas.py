"""
Schemas (numpy structured dtypes) das ComponentPools ESPECÍFICAS do jogo.
Seguem o modelo de `ouroboros.core.components.schemas`: descritores de
layout de memória, nunca classes instanciadas por entidade.

Pools genéricas da engine (transform/velocity/hitbox/sprite) vêm de
COMPONENT_SCHEMAS; estas complementam com o vocabulário do bullet hell.
"""
from __future__ import annotations

from typing import Dict

import numpy as np

# ---------------------------------------------------------------------------
# Constantes de domínio (semântica das colunas)
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1280, 720

# enemy_bullet["contact"]
CONTACT_ALWAYS, CONTACT_IF_MOVING, CONTACT_IF_STILL, CONTACT_NEVER = 0, 1, 2, 3
# enemy_bullet["beh"]
BEH_NONE, BEH_STOPGO, BEH_BOOMERANG, BEH_SLEEPER = 0, 1, 2, 3

PLAYER_DTYPE = np.dtype([
    ("lives",      np.int8),
    ("invuln_t",   np.float32),
    ("fire_cd",    np.float32),
    ("weapon_id",  np.uint32),   # sid do nome em weapons.json (já com "+")
    ("graze",      np.uint32),
    ("charge_t",   np.float32),  # CARREGADO: tempo de carga acumulado
    ("burst_left", np.int8),     # BURST: tiros restantes da rajada
    ("burst_t",    np.float32),  # BURST: intervalo até o próximo tiro
    ("aux_cd",     np.float32),  # SATÉLITE+: CD do interceptor
])

BOSS_DTYPE = np.dtype([
    ("boss_id",   np.uint32),    # sid em bosses.json
    ("hp",        np.float32),
    ("max_hp",    np.float32),
    ("phase_idx", np.int8),
    ("stun_t",    np.float32),
    ("aux_angle", np.float32),   # swarm: ângulo orbital; wall: (reserva)
])

PART_DTYPE = np.dtype([          # hitbox-filha de boss composto
    ("self",  np.uint64),
    ("root",  np.int64),         # entity index do boss raiz (recebe o dano)
    ("off_x", np.float32),       # offset base em relação à raiz
    ("off_y", np.float32),
])

# laser.axis
LASER_H, LASER_V = 0, 1
LASER_DTYPE = np.dtype([
    ("self",        np.uint64),
    ("axis",        np.uint8),
    ("pos",         np.float32), # y se horizontal, x se vertical
    ("half",        np.float32), # meia-espessura da viga
    ("telegraph_t", np.float32), # >0 = telegrafando (sem dano)
    ("fire_t",      np.float32), # duração do disparo
])

WAYPOINT_DTYPE = np.dtype([
    ("seg",    np.int32),
    ("seg_t",  np.float32),
])

EMITTER_DTYPE = np.dtype([
    ("self",        np.uint64),  # PackedEntityId desta própria entidade
    ("pattern_id",  np.uint32),
    ("t",           np.float32),
    ("phase_angle", np.float32),
    ("shot_count",  np.uint32),
    ("warmup",      np.float32),
    ("parent",      np.uint64),  # entity index da ORIGEM (boss raiz ou parte)
    ("root",        np.uint64),  # entity index do boss raiz (p/ swap de fase)
    ("off_x",       np.float32),
    ("off_y",       np.float32),
])

# tether: sentinela "sem par" (packed id 0 seria uma entidade válida!)
TETHER_NONE = np.uint64(0xFFFFFFFFFFFFFFFF)

ENEMY_BULLET_DTYPE = np.dtype([
    ("self",     np.uint64),
    ("tether",   np.uint64),     # PackedEntityId do par (TETHER_NONE = sem)
    ("contact",  np.uint8),
    ("radius",   np.float32),
    ("grazed",   np.uint8),
    ("homing_t", np.float32),    # >0 = curva ao jogador
    ("spin",     np.float32),    # rad/s no vetor velocidade
    ("phase_p",  np.float32),    # período sólido/fantasma; 0 = off
    ("phase_t",  np.float32),
    ("gravity",  np.float32),    # px/s² de atração no jogador; 0 = off
    ("bounces",  np.int8),
    ("beh",      np.uint8),      # BEH_*
    ("beh_t",    np.float32),
    ("p1",       np.float32),    # parâmetros do comportamento (arquétipo)
    ("p2",       np.float32),
    ("p3",       np.float32),
    ("tgt_x",    np.float32),    # snapshot do jogador (stop&go)
    ("tgt_y",    np.float32),
    ("stage",    np.uint8),
])

# Balas do jogador: composição por pools — cada arma anexa um conjunto
# diferente (arquétipos registrados na composição a partir de weapons.json).
PB_CORE_DTYPE = np.dtype([
    ("self",   np.uint64),
    ("damage", np.float32),
    ("radius", np.float32),
])
PB_PIERCE_DTYPE = np.dtype([("cd", np.float32), ("t", np.float32)])
PB_RANGE_DTYPE  = np.dtype([("t", np.float32)])
PB_BOUNCE_DTYPE = np.dtype([("left", np.int8)])
PB_DOT_DTYPE    = np.dtype([("dps", np.float32)])
PB_LIFE_DTYPE   = np.dtype([("t", np.float32)])
PB_HOMING_DTYPE = np.dtype([
    ("turn", np.float32), ("vmax", np.float32), ("t", np.float32),
])
PB_FUSE_DTYPE = np.dtype([          # FLAK: detona em t → estilhaços
    ("t", np.float32), ("frozen", np.uint8),
])
# ChakramMotion.state
CHAKRAM_OUT, CHAKRAM_RETURN, CHAKRAM_FROZEN = 0, 1, 2
PB_CHAKRAM_DTYPE = np.dtype([
    ("state", np.uint8), ("dps", np.float32),
])
PB_DELAY_DTYPE = np.dtype([         # BURST+: arma após t, dispara a vmax
    ("t", np.float32), ("vmax", np.float32),
    ("ax", np.float32), ("ay", np.float32),
])
# pb_orbit.kind
ORBIT_GEM, ORBIT_HELD = 0, 1        # SATÉLITE gema / TELEGUIADO+ em espera
PB_ORBIT_DTYPE = np.dtype([
    ("kind", np.uint8), ("angle", np.float32),
    ("radius", np.float32), ("ang_speed", np.float32),
])
PB_SHRAP_DTYPE = np.dtype([         # CARREGADO+: estilhaços no impacto
    ("n", np.uint8), ("speed", np.float32), ("dmg", np.float32),
])

GAME_SCHEMAS: Dict[str, np.dtype] = {
    "player":       PLAYER_DTYPE,
    "boss":         BOSS_DTYPE,
    "part":         PART_DTYPE,
    "laser":        LASER_DTYPE,
    "waypoint":     WAYPOINT_DTYPE,
    "emitter":      EMITTER_DTYPE,
    "enemy_bullet": ENEMY_BULLET_DTYPE,
    "pb_core":      PB_CORE_DTYPE,
    "pb_pierce":    PB_PIERCE_DTYPE,
    "pb_range":     PB_RANGE_DTYPE,
    "pb_bounce":    PB_BOUNCE_DTYPE,
    "pb_dot":       PB_DOT_DTYPE,
    "pb_life":      PB_LIFE_DTYPE,
    "pb_homing":    PB_HOMING_DTYPE,
    "pb_fuse":      PB_FUSE_DTYPE,
    "pb_chakram":   PB_CHAKRAM_DTYPE,
    "pb_delay":     PB_DELAY_DTYPE,
    "pb_orbit":     PB_ORBIT_DTYPE,
    "pb_shrap":     PB_SHRAP_DTYPE,
}

# Capacidades densas por pool (teto fixo, nunca realocado — Constituição §1)
GAME_POOL_CAPACITY: Dict[str, int] = {
    "player": 2, "boss": 4, "part": 8, "laser": 16, "waypoint": 4,
    "emitter": 32,
    "enemy_bullet": 5000,
    "pb_core": 256, "pb_pierce": 256, "pb_range": 256, "pb_bounce": 256,
    "pb_dot": 256, "pb_life": 256, "pb_homing": 256,
    "pb_fuse": 256, "pb_chakram": 256, "pb_delay": 256, "pb_orbit": 256,
    "pb_shrap": 256,
}

# Paleta placeholder (color_id do arquétipo → tint RGB do sprite)
PALETTE = {
    0: (255, 64, 90),    # normal (vermelho)
    1: (80, 160, 255),   # yin azul
    2: (255, 150, 50),   # yang laranja
    3: (200, 80, 255),   # homing roxa
    4: (0, 220, 220),    # tether ciano
    5: (120, 90, 160),   # gravity well
    6: (90, 220, 180),   # phaser
    7: (255, 120, 200),  # spinner
    8: (255, 220, 0),    # ricochete amarela
}
