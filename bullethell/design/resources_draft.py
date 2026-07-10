# ============================================================================
# OuroborosEngine — Resources (estado global fora do ECS)
# ----------------------------------------------------------------------------
# O hot path (5000 balas inimigas, 1200 partículas) NÃO usa entidades:
# vive aqui, em SoA NumPy, exatamente como o engine legado — ver
# MIGRATION.md §1 (benchmark: dataclasses são 135-199× mais lentas).
# Sistemas do ECS recebem estes resources e rodam kernels vetorizados.
# ============================================================================
import numpy as np

MAX_ENEMY_BULLETS = 5000

# Colunas de comportamento (substituem bstate/btimer/btgt do legado;
# os PARÂMETROS de cada arquétipo vêm de bullet_archetypes.json)
BEH_NONE, BEH_STOPGO, BEH_BOOMERANG, BEH_SLEEPER = 0, 1, 2, 3

# Regra de contato (b_type legado)
CONTACT_ALWAYS, CONTACT_IF_MOVING, CONTACT_IF_STILL, CONTACT_NEVER = 0, 1, 2, 3


class EnemyBulletStorage:
    """SoA das balas inimigas — mesmo layout do BulletPool legado, com
    free-list. spawn_batch é vetorizado: EmitterSystem calcula os arrays
    de ângulo/velocidade do padrão inteiro e grava de uma vez."""

    def __init__(self, cap: int = MAX_ENEMY_BULLETS):
        self.cap      = cap
        self.x        = np.zeros(cap, np.float32)
        self.y        = np.zeros(cap, np.float32)
        self.vx       = np.zeros(cap, np.float32)
        self.vy       = np.zeros(cap, np.float32)
        self.active   = np.zeros(cap, np.bool_)
        self.contact  = np.zeros(cap, np.int8)     # CONTACT_*
        self.color    = np.zeros(cap, np.int8)     # paleta p/ renderer
        self.radius   = np.full(cap, 4.0, np.float32)
        self.grazed   = np.zeros(cap, np.bool_)
        self.invisible= np.zeros(cap, np.bool_)    # mutador FANTASMA
        # comportamento genérico (arquétipo define os parâmetros)
        self.beh      = np.zeros(cap, np.int8)     # BEH_*
        self.beh_t    = np.zeros(cap, np.float32)  # timer do comportamento
        self.tgt_x    = np.zeros(cap, np.float32)  # alvo (stop&go) / par (tether)
        self.tgt_y    = np.zeros(cap, np.float32)
        self.stage    = np.zeros(cap, np.int8)     # sub-estado do comportamento
        # modificadores ortogonais
        self.homing_t = np.zeros(cap, np.float32)  # >0 = homing ativo
        self.spin     = np.zeros(cap, np.float32)  # rad/s (BTYPE_SPIN)
        self.phase_p  = np.zeros(cap, np.float32)  # período (BTYPE_PHASE); 0=off
        self.phase_t  = np.zeros(cap, np.float32)
        self.gravity  = np.zeros(cap, np.float32)  # px/s² (BTYPE_GRAVITY); 0=off
        self.bounces  = np.zeros(cap, np.int8)     # ricochetes restantes
        self.fragment = np.zeros(cap, np.bool_)    # gera par de fragmentos
        self.tether   = np.full(cap, -1, np.int32) # índice do par; -1=off
        self._free    = list(range(cap - 1, -1, -1))

    # Pré-alocados uma vez; kernels reutilizam (zero-GC)
    def scratch(self, n: int):
        return np.empty(n, np.float32), np.empty(n, np.float32)


MAX_PARTICLES = 1200

class ParticleStorage:
    """Partículas — idêntico ao ParticlePool legado (visual puro)."""
    def __init__(self, cap: int = MAX_PARTICLES):
        self.cap  = cap
        self.x    = np.zeros(cap, np.float32)
        self.y    = np.zeros(cap, np.float32)
        self.vx   = np.zeros(cap, np.float32)
        self.vy   = np.zeros(cap, np.float32)
        self.t    = np.zeros(cap, np.float32)
        self.color= np.zeros(cap, np.int16)
        self.active = np.zeros(cap, np.bool_)


class InputFrame:
    """Snapshot do input por frame (InputSystem escreve, ninguém mais).
    Edges calculados aqui para os sistemas não guardarem estado de tecla."""
    __slots__ = ("mx", "my", "fire", "fire_pressed", "fire_released",
                 "skill", "skill_pressed")
    def __init__(self):
        self.mx = 0.0; self.my = 0.0
        self.fire = False; self.fire_pressed = False; self.fire_released = False
        self.skill = False; self.skill_pressed = False


class Clock:
    """Escalas de tempo do frame (TimeScaleSystem escreve).
    dt_world afeta balas/boss; dt_player só o jogador (FOCUS deixa o
    jogador em velocidade cheia enquanto o mundo desacelera)."""
    __slots__ = ("dt_raw", "dt_world", "dt_player", "hitstop_frames")
    def __init__(self):
        self.dt_raw = 1/60; self.dt_world = 1/60; self.dt_player = 1/60
        self.hitstop_frames = 0


class DamageRing:
    """Fila de eventos de dano pré-alocada (zero-GC). Sistemas de colisão
    empurram (alvo, dano); DamageSystem drena no fim do frame."""
    def __init__(self, cap: int = 256):
        self.target = np.full(cap, -1, np.int32)
        self.amount = np.zeros(cap, np.float32)
        self.n = 0

    # push/drain são feitos por sistemas — mantido sem métodos de lógica
    # além do reset estrutural:
    def clear(self):
        self.n = 0


class MutatorFlags:
    """Flags de run (lidas, nunca mutadas durante o jogo)."""
    __slots__ = ("predator", "ghost", "glass_cannon", "claustrophobia")
    def __init__(self):
        self.predator = False; self.ghost = False
        self.glass_cannon = False; self.claustrophobia = False
