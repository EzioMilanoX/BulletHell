# ============================================================================
# OuroborosEngine — Componentes do Bullet Hell (camada ECS do híbrido)
# ----------------------------------------------------------------------------
# REGRA: componentes são dataclasses PURAS — zero lógica. Toda mutação
# acontece em Sistemas (systems.py).
#
# ESCOPO: este arquivo cobre a camada de ENTIDADES do híbrido — player,
# balas do jogador (≤256), bosses/partes, emissores, lacaios, lasers e
# hazards. Balas inimigas (5000) e partículas (1200) NÃO são entidades:
# vivem em resources SoA (resources.py) processados por kernels NumPy.
# Justificativa e benchmark: MIGRATION.md §1.
#
# Convenções:
#   - slots=True: menos memória, acesso mais rápido, campos fixos.
#   - Tags sem dados usam a instância-flyweight única do fim do módulo —
#     anexar sempre a MESMA instância mantém o loop livre de alocação.
#   - Referência entre entidades = int (entity id), nunca objeto.
#   - IDs de dados estáticos = zlib.crc32 (loaders.py).
# ============================================================================
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Núcleo espacial
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Transform:
    x: float = 0.0
    y: float = 0.0


@dataclass(slots=True)
class Velocity:
    vx: float = 0.0
    vy: float = 0.0


@dataclass(slots=True)
class CircleHitbox:
    radius: float = 4.0


@dataclass(slots=True)
class AABBHitbox:
    """Semi-extensões em torno do Transform. Boss multi-hitbox (Swarm/Wall/
    Twins) = entidades-filhas, cada uma com AABBHitbox + BossPart."""
    half_w: float = 20.0
    half_h: float = 20.0


@dataclass(slots=True)
class Lifetime:
    t: float = 1.0


@dataclass(slots=True)
class Renderable:
    """Só dados — o PygameRenderer decide como desenhar."""
    kind: int = 0        # crc32 da forma ("bullet_round", "chakram", ...)
    size: float = 4.0
    color_id: int = 0
    layer: int = 0


@dataclass(slots=True)
class Health:
    hp: float = 100.0
    max_hp: float = 100.0


@dataclass(slots=True)
class HitFlash:
    t: float = 0.0


@dataclass(slots=True)
class StunTimer:
    t: float = 0.0


# ---------------------------------------------------------------------------
# Tags (flyweights no fim do módulo)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PlayerTag: ...

@dataclass(slots=True)
class BossTag: ...

@dataclass(slots=True)
class PlayerBulletTag: ...

@dataclass(slots=True)
class MinionTag: ...

@dataclass(slots=True)
class Enabled:
    """Pooling zero-GC: entidades dormentes mantêm todos os componentes mas
    ficam sem Enabled. Sistemas iteram view(Comp, ..., Enabled). Spawn =
    reset de campos + add(ENABLED); despawn = remove(Enabled)."""
    ...


@dataclass(slots=True)
class BossPart:
    """Hitbox-filha de boss composto; DamageSystem roteia dano para root."""
    root: int = -1


# ---------------------------------------------------------------------------
# Balas do jogador — composição por arma (receitas em weapons.json)
# Cada arma = conjunto de componentes; as variantes + só acrescentam/ajustam.
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Damage:
    amount: float = 1.0


@dataclass(slots=True)
class PierceOnHit:
    """AGULHA+: não é destruída no hit; CD por bala entre hits (0.25s)."""
    cooldown: float = 0.25
    t_left: float = 0.0


@dataclass(slots=True)
class RangeLimit:
    """SPREAD+: alcance máximo convertido em tempo no spawn."""
    t_left: float = 0.395


@dataclass(slots=True)
class WallBounce:
    """PADRÃO+: ricochetes restantes nas paredes laterais."""
    left: int = 2


@dataclass(slots=True)
class DelayedAccel:
    """BURST+ (minas de atraso): lenta até arm_t, depois acelera para
    max_speed na direção capturada no disparo."""
    arm_t: float = 0.60
    max_speed: float = 800.0
    aim_x: float = 0.0
    aim_y: float = -1.0
    armed: bool = False


@dataclass(slots=True)
class Fuse:
    """FLAK: detona em t_left → spawn_pattern (crc32, patterns.json seção
    player). FLAK+: frozen congela o timer com fire seguro; soltar zera."""
    t_left: float = 0.40
    spawn_pattern: int = 0
    frozen: bool = False


CHAKRAM_OUT, CHAKRAM_RETURN, CHAKRAM_FROZEN = 0, 1, 2

@dataclass(slots=True)
class ChakramMotion:
    """Desacelera (drag), inverte, retorna; captura a catch_radius do dono.
    CHAKRAM+: congela no ápice aplicando frozen_dps ao boss."""
    state: int = CHAKRAM_OUT
    drag: float = 1600.0
    catch_radius: float = 22.0
    frozen_dps: float = 8.0


@dataclass(slots=True)
class DoTBeam:
    """PLASMA (e poça do PLASMA+): DPS por sobreposição com o boss;
    NUNCA é consumida pela colisão."""
    dps: float = 10.0


@dataclass(slots=True)
class SpawnOnExpire:
    """PLASMA+: ao expirar Lifetime, spawna arquétipo (poça) parado aqui."""
    archetype: int = 0


@dataclass(slots=True)
class OrbitAround:
    """SATÉLITE (gemas) e TELEGUIADO+ (mísseis em espera): Transform é
    ESCRITA pelo OrbitSystem — a entidade não tem Velocity enquanto orbita."""
    anchor: int = -1
    radius: float = 44.0
    angle: float = 0.0
    angular_speed: float = 4.0


@dataclass(slots=True)
class ShrapnelOnHit:
    """CARREGADO+ (>=85% de carga): estilhaços radiais no impacto."""
    count: int = 6
    speed: float = 320.0
    damage: float = 0.5
    size: float = 3.0


@dataclass(slots=True)
class HomingToBoss:
    """Mísseis do jogador (TELEGUIADO, PARRY+, interceptor do SATÉLITE+)."""
    turn_accel: float = 260.0
    max_speed: float = 370.0
    t_left: float = 2.8


@dataclass(slots=True)
class AutoLaunch:
    """SATÉLITE+: boss a ≤aggro_radius → gema mais próxima vira míssil
    (OrbitAround sai, Velocity+HomingToBoss entram). CD entre lançamentos."""
    aggro_radius: float = 250.0
    cd: float = 2.5
    cd_left: float = 0.0


# ---------------------------------------------------------------------------
# Jogador — controle, arma, habilidades
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PlayerControlled:
    speed: float = 220.0


@dataclass(slots=True)
class Lives:
    current: int = 3
    invuln_t: float = 0.0


@dataclass(slots=True)
class GrazeMeter:
    count: int = 0
    session: int = 0


@dataclass(slots=True)
class WeaponSlot:
    """weapon_id = crc32 em weapons.json; plus ativa a variante.
    Edges de input são escritos pelo InputSystem."""
    weapon_id: int = 0
    plus: bool = False
    fire_cd: float = 0.0
    fire_held: bool = False
    fire_released: bool = False


@dataclass(slots=True)
class ChargeState:
    t: float = 0.0
    max_t: float = 2.5
    post_cd: float = 0.0


@dataclass(slots=True)
class BurstState:
    shots_left: int = 0
    interval_t: float = 0.0


@dataclass(slots=True)
class SkillSlot:
    skill_id: int = 0
    plus: bool = False
    cd_left: float = 0.0
    active_t: float = 0.0


@dataclass(slots=True)
class FocusMeter:
    energy: float = 1.0
    drain: float = 1.5
    regen: float = 0.45
    time_scale: float = 0.32
    focusing: bool = False


@dataclass(slots=True)
class ShieldState:
    active_t: float = 0.0
    activated_at: float = 0.0      # bloco perfeito (<0.15s) do ESCUDO+


@dataclass(slots=True)
class EmpBuff:
    """EMP+: +1%/bala destruída por 5s."""
    mult: float = 1.0
    t_left: float = 0.0


@dataclass(slots=True)
class DashState:
    t_left: float = 0.0
    iframe_t: float = 0.0          # DASH+ 0.08s


@dataclass(slots=True)
class TimeStopField:
    """DILATAÇÃO: congela balas inimigas. + estilhaça num raio ao expirar."""
    t_left: float = 0.0
    shatter_radius: float = 0.0    # 0 = sem plus


# ---------------------------------------------------------------------------
# Boss — fases, movimento, emissores
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BossPhases:
    """Cursor de fase; thresholds e conjuntos de emitters em bosses.json."""
    boss_id: int = 0               # crc32 em bosses.json
    index: int = 0


@dataclass(slots=True)
class WaypointMover:
    """Waypoints com easing smoothstep; pontos em bosses.json (route_id)."""
    route_id: int = 0
    seg: int = 0
    seg_t: float = 0.0
    seg_dur: float = 2.0


@dataclass(slots=True)
class Teleporter:
    cd: float = 3.2
    cd_left: float = 3.2


@dataclass(slots=True)
class Emitter:
    """UMA instância de padrão de tiro (pattern_id = crc32, patterns.json).
    Bosses anexam N emitters como entidades-filhas → pattern overlapping é
    só ter 2+ ativos. warmup_t telegrafa sem disparar (fake prep).
    phase_angle é o estado rotativo de anéis/espirais."""
    pattern_id: int = 0
    t: float = 0.0
    phase_angle: float = 0.0
    shot_count: int = 0            # ex.: gap rotativo do RING (count * π/3)
    warmup_t: float = 0.0
    parent: int = -1               # origem = Transform desta entidade
    offset_x: float = 0.0
    offset_y: float = 0.0


# ---------------------------------------------------------------------------
# Suporte — lasers, hazards, lacaios
# ---------------------------------------------------------------------------

LASER_H, LASER_V = 0, 1

@dataclass(slots=True)
class LaserBeam:
    """telegraph_t > 0 = telegrafando (sem dano); depois fire_t com dano."""
    axis: int = LASER_H
    pos: float = 0.0
    half_width: float = 6.0
    telegraph_t: float = 1.8
    fire_t: float = 0.65


HAZARD_SLOW, HAZARD_BURN = 0, 1

@dataclass(slots=True)
class HazardZone:
    kind: int = HAZARD_SLOW
    radius: float = 60.0
    t_left: float = 4.0
    tick_cd: float = 0.0           # BURN: tick a cada 0.5s


@dataclass(slots=True)
class KamikazeAI:
    speed: float = 120.0


# ---------------------------------------------------------------------------
# Flyweights — anexe SEMPRE estas instâncias (zero-GC)
# ---------------------------------------------------------------------------
PLAYER_TAG        = PlayerTag()
BOSS_TAG          = BossTag()
PLAYER_BULLET_TAG = PlayerBulletTag()
MINION_TAG        = MinionTag()
ENABLED           = Enabled()
