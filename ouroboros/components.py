# ============================================================================
# OuroborosEngine — Componentes do Bullet Hell
# ----------------------------------------------------------------------------
# REGRA: componentes são dataclasses PURAS. Zero lógica, zero métodos além do
# que o dataclass gera. Toda mutação acontece dentro de Sistemas.
#
# Convenções:
#   - slots=True em tudo: menor footprint, acesso a atributo mais rápido,
#     e impede criação acidental de campos fora do schema.
#   - Componentes "Tag" não têm dados. Use a instância-flyweight única do
#     módulo (ex.: ENEMY_BULLET_TAG) ao anexar — sparse-set add/remove é O(1)
#     e reaproveitar a mesma instância mantém o hot loop livre de alocação.
#   - Referências entre entidades são sempre `int` (entity id), nunca objeto.
#   - IDs de dados estáticos (padrões, arquétipos, armas) são crc32 (loaders).
# ============================================================================
from dataclasses import dataclass, field

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
    """半-extensões em torno do Transform. Bosses multi-hitbox usam
    entidades-filhas, cada uma com seu próprio AABBHitbox + BossPart."""
    half_w: float = 20.0
    half_h: float = 20.0


@dataclass(slots=True)
class Lifetime:
    """Segundos restantes. LifetimeSystem devolve a entidade ao pool em t<=0."""
    t: float = 1.0


@dataclass(slots=True)
class Renderable:
    """Só dados — o PygameRenderer decide como desenhar.
    kind: crc32 do sprite/forma ("bullet_round", "player_ship", ...).
    color_id: índice de paleta (mapeia b_type legado p/ cor)."""
    kind: int = 0
    size: float = 4.0
    color_id: int = 0
    layer: int = 0


# ---------------------------------------------------------------------------
# Tags (dataless — use os flyweights no fim do módulo)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PlayerTag: ...

@dataclass(slots=True)
class BossTag: ...

@dataclass(slots=True)
class EnemyBulletTag: ...

@dataclass(slots=True)
class PlayerBulletTag: ...

@dataclass(slots=True)
class MinionTag: ...

@dataclass(slots=True)
class Enabled:
    """Tag de ativação para o pooling zero-GC: entidades dormentes do pool
    mantêm todos os componentes anexados mas SEM Enabled. Sistemas iteram
    view(Comp, Enabled). Spawn = reset de campos + add(ENABLED); despawn =
    remove(Enabled). Nenhuma alocação no hot path."""
    ...


# ---------------------------------------------------------------------------
# Vida / dano
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class Health:
    hp: float = 100.0
    max_hp: float = 100.0


@dataclass(slots=True)
class Damage:
    """Dano de contato de uma bala do jogador (multiplicador sobre base)."""
    amount: float = 1.0


@dataclass(slots=True)
class HitFlash:
    t: float = 0.0


@dataclass(slots=True)
class StunTimer:
    t: float = 0.0


@dataclass(slots=True)
class BossPart:
    """Hitbox-filha de um boss composto (SwarmBoss/WallBoss/Twins).
    Dano recebido é roteado para `root` pelo DamageSystem."""
    root: int = -1


# ---------------------------------------------------------------------------
# Balas inimigas — regra de contato + comportamentos
# (mapeiam 1:1 os b_type / bstate legados; cada comportamento é um
#  componente independente para compor livremente via bullets.json)
# ---------------------------------------------------------------------------

# ContactRule.rule
CONTACT_ALWAYS    = 0   # BTYPE_NORMAL
CONTACT_IF_MOVING = 1   # BTYPE_BLUE   (Yin)
CONTACT_IF_STILL  = 2   # BTYPE_ORANGE (Yang)
CONTACT_NEVER     = 3   # BTYPE_GRAVITY (efeito de campo, sem dano direto)

@dataclass(slots=True)
class ContactRule:
    rule: int = CONTACT_ALWAYS


@dataclass(slots=True)
class Grazeable:
    grazed: bool = False


@dataclass(slots=True)
class Homing:
    """BTYPE_PURPLE. Curva em direção ao jogador por `t_left` segundos."""
    turn_accel: float = 260.0
    max_speed: float = 370.0
    t_left: float = 2.8


@dataclass(slots=True)
class StopAndGo:
    """bstate BSTOP_PENDING/BSTOPPED. Voa travel_t, para pause_t,
    relança em direção a (tx, ty) — snapshot do player no spawn."""
    travel_t: float = 0.60
    pause_t: float = 1.80
    relaunch_speed: float = 260.0
    tx: float = 0.0
    ty: float = 0.0
    stage: int = 0          # 0=voando, 1=parada


@dataclass(slots=True)
class Boomerang:
    """bstate BBOOM_PENDING: após t_left, velocidade *= -factor."""
    t_left: float = 0.85
    factor: float = 1.8


@dataclass(slots=True)
class Sleeper:
    """bstate BSLEEPING: dormente até t_left, acorda mirando o jogador."""
    t_left: float = 1.0
    wake_speed: float = 145.0


@dataclass(slots=True)
class WallBounce:
    """b_bounces legado (ricochet do boss E PADRÃO+ do jogador)."""
    left: int = 1


@dataclass(slots=True)
class FragmentOnDeath:
    """b_fragment / ABISSAL: ao sair da tela ou ser aparada, gera `count`
    fragmentos em ±half_angle herdando velocidade escalar e cor."""
    count: int = 2
    half_angle: float = 0.524      # ±30°


@dataclass(slots=True)
class TetherLink:
    """BTYPE_TETHER: par ligado por arame. Dano se o jogador cruza o
    segmento entre as duas Transforms (teste ponto-segmento no sistema)."""
    partner: int = -1


@dataclass(slots=True)
class GravityPull:
    """BTYPE_GRAVITY: puxa o jogador (px/s²). ContactRule = NEVER."""
    strength: float = 90.0


@dataclass(slots=True)
class PhaseBlink:
    """BTYPE_PHASE: alterna sólido/fantasma. Sólida quando
    (t % period) < solid_frac * period."""
    period: float = 1.0
    solid_frac: float = 0.5
    t: float = 0.0


@dataclass(slots=True)
class AngularVelocity:
    """BTYPE_SPIN: rotaciona o vetor velocidade (rad/s)."""
    rad_per_s: float = 1.0


@dataclass(slots=True)
class DistanceCloak:
    """Mutador FANTASMA: invisível entre near..far px do boss.
    Puro dado de render — o renderer resolve o alpha."""
    near: float = 200.0
    far: float = 400.0


@dataclass(slots=True)
class Parried:
    """Bala refletida por Parry: agora viaja contra o boss e causa dano.
    PARRY+ adiciona também Homing (míssil teleguiado, dano 1.5)."""
    damage: float = 1.0


# ---------------------------------------------------------------------------
# Balas do jogador — comportamentos (mapeiam pb_type/pb_state/pb_timer)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PierceOnHit:
    """AGULHA+: não é destruída no hit; cooldown por bala entre hits."""
    cooldown: float = 0.25
    t_left: float = 0.0


@dataclass(slots=True)
class RangeLimit:
    """SPREAD+: expira ao percorrer o alcance (pré-computado em tempo)."""
    t_left: float = 0.395


@dataclass(slots=True)
class DelayedAccel:
    """BURST+ (minas de atraso): sai a launch inicial, após arm_t acelera
    para max_speed na direção (aim_x, aim_y) capturada no disparo."""
    arm_t: float = 0.60
    max_speed: float = 800.0
    aim_x: float = 0.0
    aim_y: float = -1.0
    armed: bool = False


@dataclass(slots=True)
class Fuse:
    """FLAK: detona em t_left → spawn_pattern (crc32 em patterns.json,
    seção player). FLAK+: `frozen` congela o timer enquanto fire seguro;
    soltar zera t_left (detonação manual)."""
    t_left: float = 0.40
    spawn_pattern: int = 0
    frozen: bool = False


CHAKRAM_OUT    = 0
CHAKRAM_RETURN = 1
CHAKRAM_FROZEN = 2   # CHAKRAM+

@dataclass(slots=True)
class ChakramMotion:
    """Desacelera por drag, inverte no ápice, retorna; capturada a
    catch_radius do jogador. CHAKRAM+ congela no ápice aplicando DPS."""
    state: int = CHAKRAM_OUT
    drag: float = 1600.0
    catch_radius: float = 22.0
    frozen_dps: float = 8.0


@dataclass(slots=True)
class DoTBeam:
    """PLASMA (e poças do PLASMA+): dano por segundo enquanto sobrepõe o
    boss; a bala NUNCA é consumida pela colisão."""
    dps: float = 10.0


@dataclass(slots=True)
class SpawnOnExpire:
    """PLASMA+: ao expirar o Lifetime, spawna o arquétipo `archetype`
    (crc32 em bullets_player.json) parado na posição atual (poça)."""
    archetype: int = 0


@dataclass(slots=True)
class OrbitAround:
    """SATÉLITE (gemas) e TELEGUIADO+ (mísseis em espera): posição
    derivada do anchor — Transform é ESCRITA pelo OrbitSystem, não pelo
    MovementSystem (a entidade não tem Velocity enquanto orbita)."""
    anchor: int = -1
    radius: float = 44.0
    angle: float = 0.0
    angular_speed: float = 4.0


@dataclass(slots=True)
class ShrapnelOnHit:
    """CARREGADO+ (>=85% de carga): no impacto gera estilhaços radiais."""
    count: int = 6
    speed: float = 320.0
    damage: float = 0.5
    size: float = 3.0


@dataclass(slots=True)
class HomingToBoss:
    """Mísseis do jogador (TELEGUIADO, PARRY+, SATÉLITE+ interceptor)."""
    turn_accel: float = 260.0
    max_speed: float = 370.0
    t_left: float = 2.8


@dataclass(slots=True)
class AutoLaunch:
    """SATÉLITE+ interceptor: quando o boss entra em aggro_radius, a gema
    mais próxima vira míssil (troca OrbitAround → Velocity+HomingToBoss)."""
    aggro_radius: float = 250.0
    cd: float = 2.5
    cd_left: float = 0.0


# ---------------------------------------------------------------------------
# Jogador — controle, armas, habilidades
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
    """weapon_id = crc32 do nome em weapons.json; `plus` ativa a variante.
    Estado transiente de disparo mora nos componentes de estado abaixo
    (anexados no setup conforme a arma escolhida)."""
    weapon_id: int = 0
    plus: bool = False
    fire_cd: float = 0.0
    fire_held: bool = False
    fire_released: bool = False   # edge T→F, escrito pelo InputSystem


@dataclass(slots=True)
class ChargeState:
    """CARREGADO: acumula segurando, dispara ao soltar."""
    t: float = 0.0
    max_t: float = 2.5
    post_cd: float = 0.0


@dataclass(slots=True)
class BurstState:
    """BURST: rajada de N tiros com intervalo, depois CD."""
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
    activated_at: float = 0.0    # p/ bloco perfeito (<0.15s) do ESCUDO+


@dataclass(slots=True)
class EmpBuff:
    """EMP+: +1%/bala destruída por 5s."""
    mult: float = 1.0
    t_left: float = 0.0


@dataclass(slots=True)
class DashState:
    t_left: float = 0.0
    iframe_t: float = 0.0        # DASH+ 0.08s


@dataclass(slots=True)
class TimeStopField:
    """DILATAÇÃO ativa: congela Velocity de balas inimigas. DILATAÇÃO+
    estilhaça balas num raio ao expirar."""
    t_left: float = 0.0
    shatter_radius: float = 0.0  # 0 = sem shatter (sem plus)


# ---------------------------------------------------------------------------
# Boss — movimento, fases, emissores
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BossPhases:
    """Thresholds de HP (frações, decrescentes). PhaseSystem incrementa
    `index` quando hp/max_hp cruza o próximo threshold e troca o conjunto
    de emissores conforme bosses.json."""
    boss_id: int = 0             # crc32 do boss em bosses.json
    index: int = 0


@dataclass(slots=True)
class WaypointMover:
    """Movimento por waypoints com easing smoothstep. Os pontos vivem em
    bosses.json (referenciados por route_id); aqui só o cursor."""
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
    """UMA instância de padrão de tiro. Bosses anexam vários (entidades-
    filhas com offset próprio) — pattern overlapping é só ter 2+ Emitters
    ativos. pattern_id = crc32 em patterns.json.
    `phase_angle` é o estado rotativo (espirais/anéis giratórios).
    `warmup_t` cobre o fake-prep (telegrafa sem disparar)."""
    pattern_id: int = 0
    t: float = 0.0
    phase_angle: float = 0.0
    warmup_t: float = 0.0
    parent: int = -1             # entidade cuja Transform serve de origem
    offset_x: float = 0.0
    offset_y: float = 0.0


# ---------------------------------------------------------------------------
# Suporte — lasers, hazards, lacaios
# ---------------------------------------------------------------------------

LASER_H = 0
LASER_V = 1

@dataclass(slots=True)
class LaserBeam:
    """Viga axis-aligned. telegraph_t > 0 = telegrafando (sem dano);
    depois fire_t decresce causando dano por sobreposição."""
    axis: int = LASER_H
    pos: float = 0.0
    thickness: float = 10.0
    telegraph_t: float = 0.8
    fire_t: float = 0.6


HAZARD_SLOW = 0
HAZARD_BURN = 1

@dataclass(slots=True)
class HazardZone:
    kind: int = HAZARD_SLOW
    radius: float = 60.0
    t_left: float = 4.0
    tick_cd: float = 0.0         # BURN: dano a cada 0.5s


@dataclass(slots=True)
class KamikazeAI:
    speed: float = 120.0


# ---------------------------------------------------------------------------
# Flyweights de tags — anexe SEMPRE estas instâncias, nunca crie novas
# no game loop (regra zero-GC).
# ---------------------------------------------------------------------------
PLAYER_TAG        = PlayerTag()
BOSS_TAG          = BossTag()
ENEMY_BULLET_TAG  = EnemyBulletTag()
PLAYER_BULLET_TAG = PlayerBulletTag()
MINION_TAG        = MinionTag()
ENABLED           = Enabled()
