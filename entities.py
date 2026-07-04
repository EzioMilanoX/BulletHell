"""
Bullet Hell — Game Logic (entities, pools, constants)
Render + loop live in main.py  (`from entities import *`)
"""
import sys, math, random, json
from collections import deque
import numpy as np
import pygame

# ---------------------------------------------------------------------------
# Configurações de tela e gameplay
# ---------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1280, 720
TARGET_FPS          = 60
MAX_BULLETS         = 5000
MAX_PB              = 256

PLAYER_SPEED  = 220.0
PLAYER_SIZE   = 18
PLAYER_RADIUS = 2.5
BULLET_RADIUS = 3.0
HIT_SQ        = (PLAYER_RADIUS + BULLET_RADIUS) ** 2
INVULN_FRAMES = 90
MAX_LIVES     = 3

PLAYER_FIRE_RATE = 0.10
PB_SPEED         = 500.0

BOSS_MAX_HP        = 300
BOSS_SIZE          = 48
PREP_TIME          = 0.65

BOSS_WAYPOINTS = (
    (0.50, 0.50),
    (0.20, 0.20),
    (0.80, 0.20),
    (0.14, 0.50),
    (0.86, 0.50),
    (0.35, 0.28),
    (0.65, 0.28),
    (0.50, 0.18),
)

MAX_EMITTERS     = 20
BLAST_TELEGRAPH  = 1.4
BLAST_N_BULLETS  = 9
BLAST_SPREAD_RAD = math.radians(9)
BLAST_SPEED      = 420.0
BLAST_WAVE_RATE  = 2.2
BLAST_PER_WAVE   = 4

MAX_LASERS       = 16
LASER_TELEGRAPH  = 1.8
LASER_FIRE_DUR   = 0.65
LASER_WAVE_RATE  = 3.0
LASER_N_LINES    = 3
LASER_MIN_SEP_H  = 130.0
LASER_MIN_SEP_V  = 190.0
LASER_HIT_HALF   = 6.0
LASER_WIDTH      = 7

SPREAD_RATE  = 0.80
SPREAD_SPEED = 185.0
RING_RATE    = 1.60
SPIRAL_RATE  = 0.040
SPIRAL_SPEED = 72.0

CRACK_FORM_TIME  = 1.5
CRACK_HOLD_SPEED = 6.0
CRACK_FLY_SPEED  = 185.0
CRACK_BASE = (0.00, 0.30, 0.72, 1.15, 1.55, 2.00, 2.40, 2.82,
              3.25, 3.65, 4.08, 4.48, 4.90, 5.28, 5.65, 5.98)
CRACK_STEPS = (36, 38, 42, 44, 46, 48, 50, 52, 50, 46, 42, 38, 34, 30, 24, 18)
CRACK_SEG1 = 5
CRACK_SEG2 = 11
CRACK_BENDS = (
    (+0.38, -0.25), (-0.30, +0.44), (+0.22, +0.35), (-0.47, -0.18),
    (+0.55, -0.32), (-0.19, +0.27), (+0.33, -0.50), (-0.41, +0.16),
    (+0.48, -0.22), (-0.26, +0.53), (+0.15, -0.44), (-0.37, +0.20),
    (+0.52, -0.15), (-0.23, +0.38), (+0.29, -0.46), (-0.44, +0.31),
)

CIRC_ARMS       = 3
CIRC_FORM_TIME  = 2.5
CIRC_SPIN_SPEED = 2.2
CIRC_STEP_SIZE  = 10
CIRC_MAX_STEPS  = 75
CIRC_FLY_SPEED  = 195.0

FRAC_CUT_ANGLE  = 1.64
FRAC_CUT_HALF   = 365
FRAC_STEP_SIZE  = 22
FRAC_FORM_TIME  = 1.8
FRAC_HOLD_SPEED = 3.0
FRAC_FLY_SPEED  = 165.0
FRAC_TREES = (
    (-230, 2.83, 6, [(-0.45, 7), (+0.38, 7)]),
    ( -85, 2.58, 5, [(-0.50, 8), (+0.05, 6), (+0.52, 8)]),
    (  85, 3.37, 5, [(-0.48, 7), (+0.06, 7), (+0.50, 8)]),
    ( 230, 3.63, 6, [(-0.40, 8), (+0.42, 7)]),
    (-230, 0.292, 6, [(+0.45, 7), (-0.38, 7)]),
    ( -85, 0.562, 5, [(+0.50, 8), (-0.05, 6), (-0.52, 8)]),
    (  85, 6.055, 5, [(+0.48, 7), (-0.06, 7), (-0.50, 8)]),
    ( 230, 5.796, 6, [(+0.40, 8), (-0.42, 7)]),
)

CELL_SIZE  = 64
GRID_COLS  = (SCREEN_W + CELL_SIZE - 1) // CELL_SIZE
GRID_ROWS  = (SCREEN_H + CELL_SIZE - 1) // CELL_SIZE
GRID_CELLS = GRID_COLS * GRID_ROWS
TWO_PI = math.tau

# ---------------------------------------------------------------------------
# Skill+ evolution constants
# ---------------------------------------------------------------------------
DASH_PLUS_IFRAME_DUR   = 0.08    # invulnerability window at dash start (s)
BLINK_PLUS_EMP_R       = 60.0    # EMP radius at blink origin (px)
EMP_PLUS_BUFF_DUR      = 5.0     # damage buff duration (s)
EMP_PLUS_DMG_PER_BULL  = 0.01    # +1% weapon damage per bullet destroyed
OVERCLOCK_PLUS_FR_MULT = 0.25    # fire rate period multiplier → 4× shots/s
OVERCLOCK_PLUS_SPD_F   = 0.25    # player speed fraction during OC+ (25%)
SHIELD_PLUS_CD_FRAC    = 0.50    # CD refund on shield break
SHIELD_PLUS_RING_N     = 8       # player bullets spawned on shield break
SHIELD_PLUS_RING_SPD   = 220.0   # ring bullet speed (px/s)
TIMEDIL_PLUS_RADIUS    = 80.0    # bullet shatter radius when timedil ends (px)
PARRY_PLUS_HOMING_DMG  = 1.5     # damage of each PARRY+ homing bullet

# Mastery achievement targets (unlock skill+ version)
MASTERY_DASH_GRAZES    = 50      # cumulative grazes during dash frames
MASTERY_PARRY_BURST    = 5       # bullets reflected in a single activation
MASTERY_EMP_BULLETS    = 200     # bullets destroyed in a single EMP use
MASTERY_OC_DMG         = 500.0   # HP damage in one Overclock window
MASTERY_SHIELD_PERFECT = 10      # cumulative perfect blocks (hit <0.15s after activation)

# ---------------------------------------------------------------------------
# Estados do jogo
# ---------------------------------------------------------------------------
PLAYING, WIN, GAMEOVER, REPLAYING = 0, 1, 2, 8
SELECT_DIFF, SELECT_BOSS, SELECT_SKILL, SELECT_WEAPON, SELECT_MUTATOR = 3, 4, 5, 6, 7
MAIN_MENU = 9
RECORDS   = 10
SETTINGS     = 11
ACHIEVEMENTS     = 12
SELECT_GAME_MODE = 13
BOSS_RUSH_PAUSE      = 14
SELECT_RUSH_PLAYLIST = 16   # sub-menu: escolher playlist do Boss Rush

# Dificuldade
DIFF_TEST    = -1  # Godmode — apenas por cheats/dev mode
DIFF_EASY    = 0
DIFF_NORMAL  = 1
DIFF_HARD    = 2
DIFF_EXPERT  = 3   # Segundo Fôlego · PREP ×0.5 · balas menores
DIFF_ABISSAL = 4   # Balas de Vingança · Fragmentação

# Habilidades
SKILL_NONE      = 0
SKILL_DASH      = 1
SKILL_PARRY     = 2
SKILL_FOCUS     = 3
SKILL_EMP       = 4
SKILL_BLINK     = 5
SKILL_OVERCLOCK = 6
SKILL_SHIELD    = 7
N_SKILLS        = 8

DASH_DURATION = 0.18
DASH_MULT     = 6.0
DASH_COOLDOWN = 1.2
PARRY_DURATION = 0.13
PARRY_RANGE    = PLAYER_RADIUS + BULLET_RADIUS + 12.0
PARRY_COOLDOWN = 1.2
FOCUS_DRAIN_RATE = 1.5
FOCUS_REGEN_RATE = 0.45
FOCUS_SLOW       = 0.32
EMP_RADIUS   = 340.0
EMP_COOLDOWN = 8.0
EMP_STUN     = 1.0
BLINK_DIST     = 190.0
BLINK_COOLDOWN = 2.0
OVERCLOCK_DURATION       = 3.0
OVERCLOCK_CD             = 12.0
OVERCLOCK_FIRE_RATE_MULT = 0.45   # fire period × this during overclock
SHIELD_DURATION          = 2.5
SHIELD_CD                = 15.0

# Armas
WEAPON_DEFAULT = 0
WEAPON_SPREAD  = 1
WEAPON_NEEDLE  = 2
WEAPON_CHARGED = 3
WEAPON_BURST   = 4
WEAPON_HOMING  = 5
WEAPON_FLAK    = 6
WEAPON_CHAKRAM = 7
WEAPON_PLASMA  = 8
WEAPON_ORBIT   = 9
N_WEAPONS              = 10

# ---- FLAK stats
FLAK_FIRE_RATE     = 0.50
FLAK_SPEED         = 200.0
FLAK_SIZE          = 8.0
FLAK_TIMER         = 0.40
FLAK_SHRAPNEL_N    = 5
FLAK_SHRAPNEL_ARC  = 0.70   # leque em radianos (~40°)
FLAK_SHRAPNEL_SPD  = 400.0
FLAK_SHRAPNEL_DMG  = 0.4
FLAK_SHRAPNEL_SIZE = 3.0

# ---- CHAKRAM stats
CHAKRAM_FIRE_RATE  = 0.70
CHAKRAM_SPEED      = 580.0
CHAKRAM_SIZE       = 7.0
CHAKRAM_DMG        = 2.0
CHAKRAM_DRAG       = 1600.0  # desaceleração px/s² — decelera e inverte
CHAKRAM_CATCH_R    = 22.0    # raio de captura pelo jogador no retorno

# ---- PLASMA stats
PLASMA_FIRE_RATE   = 0.06
PLASMA_SPEED       = 100.0
PLASMA_SIZE        = 11.0
PLASMA_DPS         = 10.0
PLASMA_LIFESPAN    = 1.2

# ---- ORBIT (Satélite) stats
ORBIT_FIRE_RATE    = 0.35
ORBIT_RADIUS       = 44.0
ORBIT_ANG_SPD      = 4.0    # rad/s de rotação orbital
ORBIT_DMG          = 0.6
ORBIT_SIZE         = 5.0
ORBIT_MAX          = 4      # máximo simultâneo

# ---- Player bullet type identifiers (pb_type field)
PB_NORMAL        = 0
PB_FLAK          = 1
PB_CHAKRAM       = 2
PB_PLASMA        = 3
PB_ORBIT         = 4
PB_HOMING_HELD   = 5   # TELEGUIADO+: míssil orbitando até soltar botão
PB_PLASMA_PUDDLE = 6   # PLASMA+: poça de calor estacionária

# ---- Weapon+ constants
DEFAULT_PLUS_BOUNCES   = 2       # PADRÃO+: ricochetes em paredes laterais
SPREAD_PLUS_DMG        = 1.20    # SPREAD+: dano 2× (normal 0.60)
SPREAD_PLUS_MAX_RANGE  = 150.0   # SPREAD+: px antes de expirar
NEEDLE_PLUS_CD_MULT    = 1.20    # AGULHA+: CD 20% maior
NEEDLE_PLUS_PIERCE_CD  = 0.25    # AGULHA+: janela de imunidade após perfurar
CHARGED_PLUS_FRAG_N    = 6       # CARREGADO+: estilhaços radiais ao acertar
CHARGED_PLUS_FRAG_SPD  = 320.0
CHARGED_PLUS_FRAG_DMG  = 0.5
CHARGED_PLUS_FRAG_SZ   = 3.0
BURST_PLUS_ARM_T       = 0.60    # BURST+: s parado antes de acelerar
BURST_PLUS_MAX_SPD     = 800.0   # BURST+: velocidade após armar
BURST_PLUS_INIT_SPD    = 80.0    # BURST+: velocidade inicial (lenta)
HOMING_PLUS_ORBIT_R    = 50.0    # TELEGUIADO+: raio de órbita enquanto segura
HOMING_PLUS_ORB_SPD    = 3.5     # TELEGUIADO+: rad/s de rotação enquanto segura
HOMING_PLUS_FIRE_RATE  = 0.45    # TELEGUIADO+: intervalo entre spawns enquanto segura
CHAKRAM_PLUS_DPS       = 8.0     # CHAKRAM+: DPS enquanto congelado no ar
PLASMA_PLUS_PUDDLE_T   = 1.20    # PLASMA+: duração da poça (s)
PLASMA_PLUS_PUDDLE_DPS = 3.0     # PLASMA+: DPS da poça (menor que plasma direto)
ORBIT_PLUS_AGGRO_R     = 250.0   # SATÉLITE+: raio de detecção de ameaças
ORBIT_PLUS_LAUNCH_CD   = 2.5     # SATÉLITE+: s entre lançamentos automáticos

# ---- Mastery thresholds — weapon+
MASTERY_W_DEFAULT_HITS  = 150
MASTERY_W_SPREAD_CLOSE  = 50
MASTERY_W_NEEDLE_PHASE  = 1
MASTERY_W_CHARGED_MULTI = 10
MASTERY_W_BURST_TWINS   = 5
MASTERY_W_HOMING_NOHIT  = 3
MASTERY_W_FLAK_BULLETS  = 15
MASTERY_W_CHAKRAM_ROUND = 30
MASTERY_W_PLASMA_CONT   = 4.0
MASTERY_W_ORBIT_DAMAGE  = 400.0
WEAPON_SPREAD_ANGLE    = math.radians(14.0)
PB_NEEDLE_SPEED        = 900.0   # faster bullet, more forgiving aim
PB_NEEDLE_DAMAGE       = 1.5     # nerf from 2.4; slower fire rate compensates
PB_NEEDLE_FIRE_RATE    = 0.20    # needle fires slower than default (0.10)
PB_SPREAD_DAMAGE       = 0.60    # nerf from 0.65
PB_SPREAD_SPEED        = 380.0   # spread bullets slower than default
PB_CHARGED_MAX_T       = 2.5     # longer max charge window
PB_CHARGED_MIN_DMG     = 2.0     # buff from 1.5 — minimum charge still worthwhile
PB_CHARGED_MAX_DMG     = 8.0     # buff from 6.0 — full charge is devastating
PB_CHARGED_MIN_SIZE    = 5.0
PB_CHARGED_MAX_SIZE    = 14.0
PB_CHARGED_CD          = 1.5     # nerf from 1.2 — longer post-fire lockout
BURST_SHOTS            = 3
BURST_INTERVAL         = 0.05
BURST_CD               = 0.45    # buff from 0.65 — faster repeat
PB_BURST_DAMAGE        = 1.0     # buff from 0.80 — each shot hits harder

# Arma 6 — Teleguiado (enxame de mísseis)
PB_HOMING_N         = 5           # mísseis por rajada
PB_HOMING_DMG       = 0.2         # dano por míssil
PB_HOMING_SPD       = 290.0       # velocidade inicial (px/s)
PB_HOMING_FIRE_RATE = 0.30        # segundos entre rajadas
PB_HOMING_ARC       = math.radians(38)   # dispersão aleatória ±38°
PB_HOMING_HOME_T    = 2.8         # segundos de rastreamento ativo
PB_HOMING_CURL      = 260.0       # força de curvatura (px/s²)
PB_HOMING_MAX_SPD   = 370.0       # velocidade máxima durante rastreamento

# Mutadores
MUTATOR_PREDATOR     = 0
MUTATOR_GHOST        = 1
MUTATOR_GLASS_CANNON = 2
MUTATOR_HORDE        = 3   # Boss: +50% HP, −15% velocidade
MUTATOR_BERSERKER    = 4   # Boss: −25% HP, +35% velocidade
N_MUTATORS           = 5
PREDICT_AIM_TIME     = 0.5
GHOST_NEAR           = 200.0
GHOST_FAR            = 400.0

# Tipos de boss
BOSS_CLASSIC  = 0
BOSS_SWARM    = 1
BOSS_WALL     = 2
BOSS_OMEGA    = 4
# Sete Pecados + chefe final
BOSS_PRIDE    =  8   # Soberba
BOSS_SLOTH    =  9   # Preguiça
BOSS_ENVY     = 10   # Inveja
BOSS_GLUTTONY = 11   # Gula
BOSS_GREED    = 12   # Avareza
BOSS_LUST     = 13   # Luxúria
BOSS_WRATH    = 14   # Ira
BOSS_SIN      = 15   # Pecado Original (chefe final)
BOSS_DUMMY    = 16   # Saco de Pancadas — apenas dev/cheat

# ---------------------------------------------------------------------------
# Bullet types (TwinsBoss)
# ---------------------------------------------------------------------------
BTYPE_NORMAL  = 0   # padrão — dano sempre
BTYPE_BLUE    = 1   # Yin  — dano somente se jogador está se movendo
BTYPE_ORANGE  = 2   # Yang — dano somente se jogador está parado
BTYPE_PURPLE  = 3   # Yang P2 — rastreador curvado (homing)
BTYPE_TETHER  = 4   # algema: par de balas ligadas por fio laser
BTYPE_GRAVITY = 5   # poço gravitacional: puxa o jogador sem dano direto
BTYPE_PHASE   = 6   # bala fantasma: alterna sólida/fantasma a cada 0.5s (btgt_x = timer)
BTYPE_SPIN    = 7   # bala giratória: vetor velocidade rotaciona (btgt_x = taxa rad/s)

# Constantes de comportamento dos novos b_types
BULLET_GRAVITY_PULL     = 90.0   # aceleração de atração gravitacional (px/s²)
BULLET_GRAVITY_MIN_DIST = 28.0   # abaixo disso a gravidade para de agir
BULLET_PHASE_PERIOD     = 1.0    # duração do ciclo completo sólido+fantasma (s)
BULLET_PHASE_SOLID      = 0.5    # por quanto tempo fica sólida por ciclo (s)

TWIN_MOVING_THRESH = 14.0    # px/s mínimo para considerar jogador "se movendo"

# ---------------------------------------------------------------------------
# TwinsBoss (Gêmeos Yin / Yang)
# ---------------------------------------------------------------------------
BOSS_TWINS         = 6
TWIN_SIZE          = 28
TWIN_YIN_SPEED     = 75.0
TWIN_YANG_ORBIT_R  = 270.0   # raio da órbita de Yang ao redor do jogador
TWIN_YANG_SPEED    = 250.0   # px/s de Yang em direção ao alvo de órbita
TWIN_SHOOT_YIN     = 1.6     # s entre grades azuis de Yin
TWIN_SHOOT_YANG    = 1.1     # s entre ondas laranjas de Yang
TWIN_RAGE_MULT     = 1.75    # multiplicador de cadência em rage

# -- Ataques conjuntos fase 1 ------------------------------------------------
TWIN_JOINT_CD         = 9.0    # s entre ataques conjuntos
TWIN_HELIX_ORBIT_R    = 140.0  # raio do orbit durante Hélice
TWIN_HELIX_ORBIT_W    = 1.2    # rad/s do orbit
TWIN_HELIX_FIRE_RATE  = 0.065  # s por par de balas
TWIN_HELIX_BSPEED     = 148.0
TWIN_HELIX_DURATION   = 5.5

TWIN_PEND_DURATION    = 7.0
TWIN_PEND_WALL_SPEED  = 30.0   # px/s inward por parede
TWIN_PEND_BALL_RATE   = 0.48   # s entre pares de bolas laranjas
TWIN_PEND_BALL_SPEED  = 205.0

# -- Fase 2 — sobrevivente após absorção -------------------------------------
TWIN_SURVIVOR_SCALE   = 1.6    # escala visual do sobrevivente

# -- Balas roxas (Yang dominante fase 2) -------------------------------------
TWIN_PURPLE_HOME_T    = 2.0    # s de rastreamento
TWIN_PURPLE_HOME_CURL = 195.0  # px/s² de aceleração em direção ao jogador
TWIN_PURPLE_MAX_SPD   = 255.0
TWIN_PURPLE_SPEED     = 145.0  # velocidade inicial ao acordar

# -- Yang dominante — ataques fase 2 ----------------------------------------
YANG_WASP_N           = 15     # balas por cluster de vespa
YANG_WASP_WAKE_T      = 0.55   # s de dormência antes de acordar
YANG_WASP_DASHES      = 5      # dashes no zigzag
YANG_DASH_DIST        = 210.0  # px por dash
YANG_DASH_DUR         = 0.13   # duração de cada dash
YANG_WHIP_N           = 22     # balas no chicote
YANG_WHIP_ARC         = 0.055  # spread angular do pilar (rad)
YANG_METEOR_RATE      = 0.038  # s entre balas da chuva
YANG_METEOR_SPD_MIN   = 355.0
YANG_METEOR_SPD_MAX   = 495.0
YANG_METEOR_DUR       = 3.5

# -- Yin dominante — ataques fase 2 -----------------------------------------
YIN_CHESS_COLS        = 9
YIN_CHESS_ROWS        = 7
YIN_CHESS_SPEED       = 575.0  # balas rápidas para cobrir tela "instantaneamente"
YIN_CHESS_SAFE_N      = 3      # colunas vazias (zonas seguras)
YIN_LAB_ROWS          = 6
YIN_LAB_SPEED         = 80.0
YIN_LAB_GAP           = 54.0   # px entre balas numa linha do labirinto
YIN_INV_CD            = 15.0   # s entre pulsos de inversão
YIN_INV_CHARGE_T      = 1.3    # s de carga antes do pulso disparar
# Yin P2 — minefield (atk 2)
YIN_MINE_N            = 30     # minas espalhadas na tela
YIN_MINE_WAKE_SPD     = 215.0  # velocidade das minas ao acordar no pulso
# Yin P2 — chess cage (atk 3)
YIN_CAGE_HALF         = 105    # metade do lado do cage (210×210 px)
YIN_CAGE_DENSITY      = 9      # balas por parede
YIN_CAGE_FLICKER_T    = 0.68   # s entre flicker de interior azul/laranja
YIN_CAGE_FILL_N       = 10     # balas interiores por flicker
YIN_CAGE_FILL_SPD     = 52.0   # velocidade de derive das balas interiores
# Yang P2 — phantom dash (atk 3)
YANG_PHANTOM_SPD       = 1350.0  # px/s do dash
YANG_PHANTOM_TRAIL_INT = 0.042   # s entre spawns do rastro
YANG_PHANTOM_PERP_SPD  = 160.0   # velocidade perpendicular do rastro
YANG_PHANTOM_PERP_N    = 5       # pares de balas por spawn de rastro
YANG_PHANTOM_PHASE_DUR = 6.5     # duração total da fase
YANG_PHANTOM_PAUSE     = 0.55    # pausa entre dashes

# ---------------------------------------------------------------------------
# SummonerBoss (Invocador)
# ---------------------------------------------------------------------------
BOSS_SUMMONER        = 7
N_BOSS_TYPES         = 17      # total de tipos (incluindo Pecados + Dummy)
N_CLASSIC_BOSS_TYPES = 6       # bosses no selector clássico
CLASSIC_BOSS_IDS     = [BOSS_CLASSIC, BOSS_SWARM, BOSS_WALL,
                         BOSS_TWINS, BOSS_SUMMONER, BOSS_OMEGA]
SUMMONER_SIZE        = 38
SUMMONER_TELEPORT_CD = 4.2
SUMMONER_SUMMON_CD   = 2.6

# ---------------------------------------------------------------------------
# EnemyPool (lacaios do Invocador)
# ---------------------------------------------------------------------------
MAX_ENEMIES            = 64
ETYPE_KAMIKAZE         = 0
ETYPE_SENTINEL         = 1
ETYPE_BUBBLE           = 2    # Bolha da Preguiça — estacionária, timer de explosão
BUBBLE_EXPLODE_T       = 8.0  # s antes da explosão automática
BUBBLE_HP              = 12.0
BUBBLE_BURST_N         = 12   # balas no anel de explosão
ENEMY_KAMIKAZE_HP      = 8.0
ENEMY_KAMIKAZE_SPEED   = 195.0
ENEMY_KAMIKAZE_SIZE    = 12
ENEMY_SENTINEL_HP      = 20.0
ENEMY_SENTINEL_SIZE    = 14
SENTINEL_FIRE_RATE     = 2.2   # s entre disparos de cada sentinela
SENTINEL_BULLET_SPEED  = 140.0

# ---------------------------------------------------------------------------
# Nova habilidade: Dilatação Temporal
# ---------------------------------------------------------------------------
SKILL_TIMEDILATION    = 8
N_SKILLS              = 9      # era 8
TIMEDILATION_DURATION = 2.0   # s que balas ficam congeladas
TIMEDILATION_CD       = 12.0

# ---------------------------------------------------------------------------
# Novo mutador: Claustrofobia
# ---------------------------------------------------------------------------
MUTATOR_CLAUSTROFOBIA = 5
N_MUTATORS            = 6      # era 5
ARENA_SHRINK          = 0.14   # fração de cada borda removida

# ---------------------------------------------------------------------------
# Game modes
# ---------------------------------------------------------------------------
GAME_MODE_CLASSIC       = 0
GAME_MODE_BOSS_RUSH     = 1
GAME_MODE_WAVE_SURVIVAL = 2

BOSS_RUSH_ORDER = [BOSS_CLASSIC, BOSS_SWARM, BOSS_WALL,
                   BOSS_TWINS, BOSS_SUMMONER, BOSS_OMEGA]

# ---------------------------------------------------------------------------
# BulletPool behavior states (Mago do Tempo)
# ---------------------------------------------------------------------------
BNORMAL       = 0   # voa normalmente
BSTOP_PENDING = 1   # vai parar quando btimer zerar
BSTOPPED      = 2   # parado, vai re-disparar quando btimer zerar
BBOOM_PENDING = 3   # vai inverter a velocidade quando btimer zerar
BSLEEPING     = 4   # dorme (v=0) até btimer zerar, então acorda como BTYPE_PURPLE

# ---------------------------------------------------------------------------
# HazardPool — zonas de perigo residuais (denial of area)
# ---------------------------------------------------------------------------
MAX_HAZARDS          = 20
HAZARD_SLOW          = 0    # reduz velocidade do jogador à metade
HAZARD_BURN          = 1    # dano periódico a cada HAZARD_BURN_INTERVAL segundos
HAZARD_BURN_INTERVAL = 0.5

# ---------------------------------------------------------------------------
# Swarm boss
# ---------------------------------------------------------------------------
SWARM_ORBIT_RADIUS   = 130.0
SWARM_ORBIT_SPEED    = 0.75   # rad/s
SWARM_UNIT_SIZE      = 34
SWARM_CROSSFIRE_RATE = 1.6
SWARM_WAYPOINTS = (
    (0.50, 0.25), (0.25, 0.18), (0.75, 0.18),
    (0.30, 0.38), (0.70, 0.38), (0.50, 0.30),
    (0.18, 0.28), (0.82, 0.28),
)

# ---------------------------------------------------------------------------
# Wall boss
# ---------------------------------------------------------------------------
WALL_HEIGHT       = 60
WALL_MAX_DESCENT  = int(SCREEN_H * 0.30)   # 216 px de topo
WALL_DESCENT_SPEED = 150.0                  # px/s
WALL_CANNON_SEP   = 110                     # px entre canhões
WALL_RAIN_RATE    = 0.22                    # s entre rajadas de chuva
WALL_RAIN_SPEED   = 220.0
WALL_PILLAR_RATE  = 0.09                    # s entre balas do pilar
WALL_PILLAR_SPEED = 300.0

# ---------------------------------------------------------------------------
# Time Mage boss
# ---------------------------------------------------------------------------
TM_STOPGO_RATE        = 1.8    # s entre bursts de stop-and-go
STOPGO_TRAVEL_TIME    = 0.60   # s que a bala voa antes de parar
STOPGO_PAUSE          = 1.80   # s que a bala fica parada
STOPGO_RELAUNCH_SPEED = 260.0  # px/s após relanço
TM_BOOM_RATE          = 2.2    # s entre bursts de boomerang
TM_BOOM_N             = 8      # balas por burst de boomerang
TM_BOOM_SPEED         = 190.0  # px/s inicial
TM_BOOM_REVERSE_TIME  = 0.85   # s antes de inverter
TM_TELEPORT_INTERVAL  = 3.2    # s entre teleportes (fase 3)

# ---------------------------------------------------------------------------
# Graze
# ---------------------------------------------------------------------------
GRAZE_RANGE = PLAYER_SIZE / 2.0          # raio do sprite visual (~9px)
GRAZE_SQ    = (GRAZE_RANGE + BULLET_RADIUS) ** 2

# ---------------------------------------------------------------------------
# Partículas
# ---------------------------------------------------------------------------
MAX_PARTICLES    = 1200
PARTICLE_GRAVITY = 220.0   # px/s²

# Paleta
BG_COLOR  = (10,  10,  18)
ORANGE    = (255, 165,   0)
SKYBLUE   = (135, 206, 235)
RED_COL   = (220,  20,  60)
MAROON    = (128,   0,   0)
WHITE     = (255, 255, 255)
GREEN     = (  0, 220,   0)
YELLOW    = (255, 220,   0)
DKGRAY    = ( 64,  64,  64)
CYAN      = (  0, 255, 200)
PURPLE    = (180,   0, 255)
DARKRED   = ( 50,   0,   0)
DARKBLUE  = ( 20,  20,  80)


# ===========================================================================
# GameConfig
# ===========================================================================
class GameConfig:
    _SPEED  = {DIFF_TEST: 1.0, DIFF_EASY: 0.75, DIFF_NORMAL: 1.0,
               DIFF_HARD: 1.30, DIFF_EXPERT: 1.50, DIFF_ABISSAL: 1.65}
    _HP     = {DIFF_TEST: 50,  DIFF_EASY: 200,  DIFF_NORMAL: 300,
               DIFF_HARD: 400, DIFF_EXPERT: 480, DIFF_ABISSAL: 560}
    DIFF_LABELS  = {DIFF_TEST: "TESTE", DIFF_EASY: "FÁCIL", DIFF_NORMAL: "NORMAL",
                    DIFF_HARD: "DIFÍCIL", DIFF_EXPERT: "EXPERT", DIFF_ABISSAL: "ABISSAL"}
    BOSS_LABELS  = {BOSS_CLASSIC: "CLÁSSICO", BOSS_SWARM: "ENXAME",
                    BOSS_WALL: "PAREDÃO",  BOSS_OMEGA: "ÔMEGA ★",
                    BOSS_TWINS: "GÊMEOS",  BOSS_SUMMONER: "INVOCADOR"}
    SKILL_LABELS = {SKILL_NONE: "NENHUMA", SKILL_DASH: "DASH", SKILL_PARRY: "PARRY",
                    SKILL_FOCUS: "FOCO",   SKILL_EMP:  "EMP",  SKILL_BLINK: "BLINK",
                    SKILL_OVERCLOCK: "OVERCLOCK", SKILL_SHIELD: "ESCUDO",
                    SKILL_TIMEDILATION: "DILATAÇÃO"}
    WEAPON_LABELS = {WEAPON_DEFAULT: "PADRÃO",   WEAPON_SPREAD: "SPREAD",
                     WEAPON_NEEDLE:  "AGULHA",   WEAPON_CHARGED: "CARREGADO",
                     WEAPON_BURST:   "BURST",    WEAPON_HOMING: "TELEGUIADO",
                     WEAPON_FLAK:    "FLAK",     WEAPON_CHAKRAM: "CHAKRAM",
                     WEAPON_PLASMA:  "PLASMA",   WEAPON_ORBIT: "SATÉLITE"}
    MUTATOR_LABELS = {MUTATOR_PREDATOR: "PREDADOR", MUTATOR_GHOST: "FANTASMA",
                      MUTATOR_GLASS_CANNON: "CANHÃO DE VIDRO",
                      MUTATOR_HORDE: "HORDA", MUTATOR_BERSERKER: "BERSERKER",
                      MUTATOR_CLAUSTROFOBIA: "CLAUSTROFOBIA"}

    def __init__(self, diff: int = DIFF_NORMAL, boss_type: int = BOSS_CLASSIC,
                 skill: int = SKILL_NONE, weapon: int = WEAPON_DEFAULT,
                 mutators: frozenset = frozenset(), skill_plus: bool = False,
                 weapon_plus: bool = False):
        self.diff        = diff
        self.boss_type   = boss_type
        self.skill       = skill
        self.weapon      = weapon
        self.mutators    = mutators
        self.skill_plus  = skill_plus
        self.weapon_plus = weapon_plus
        self.speed_mult = self._SPEED.get(diff, 1.0)
        self.boss_hp    = self._HP.get(diff, 300)
        # Mutator modifiers applied at config creation
        if MUTATOR_HORDE in mutators:
            self.boss_hp    = int(self.boss_hp * 1.5)
            self.speed_mult *= 0.85
        if MUTATOR_BERSERKER in mutators:
            self.boss_hp    = int(self.boss_hp * 0.75)
            self.speed_mult *= 1.35

    @property
    def multiplier(self) -> float:
        return 1.0 + 0.25 * len(self.mutators)


# ===========================================================================
# Difficulty
# ===========================================================================
class Difficulty:
    _SPREAD = {1: (5, math.radians(35)), 2: (6, math.radians(45)), 3: (7, math.radians(56))}
    _RING   = {1: (26, 132.0), 2: (28, 150.0), 3: (32, 170.0)}
    _SPIRAL = {1: (6, 0.10),   2: (6, 0.15),   3: (8, 0.18)}
    RING_TARGET_ARC = 30.0
    RING_MIN_GAP    = math.radians(18)
    RING_MAX_GAP    = math.radians(55)

    def __init__(self, menu_diff: int = DIFF_NORMAL):
        self._tier  = 1
        self._diff  = menu_diff
        self.speed_mult = GameConfig._SPEED.get(menu_diff, 1.0)
        self._bonus = 1 if menu_diff >= DIFF_HARD else 0

    @property
    def prep_scale(self) -> float:
        return 0.5 if self._diff >= DIFF_EXPERT else 1.0

    @property
    def second_wind(self) -> bool:
        return self._diff >= DIFF_EXPERT

    @property
    def revenge_bullets(self) -> bool:
        return self._diff >= DIFF_ABISSAL

    def update(self, hp, max_hp):
        ratio = hp / max_hp
        if ratio > 0.66:   self._tier = 1
        elif ratio > 0.33: self._tier = 2
        else:              self._tier = 3

    @property
    def tier(self) -> int: return self._tier

    def spread_params(self):
        n, spread = self._SPREAD[self._tier]
        return n + self._bonus, spread

    def ring_params(self, player_dist: float):
        n, speed = self._RING[self._tier]
        n += self._bonus
        r = max(player_dist, 40.0)
        gap_rad = max(self.RING_MIN_GAP, min(self.RING_MAX_GAP, self.RING_TARGET_ARC / r))
        return n, gap_rad, speed

    def spiral_params(self):
        return self._SPIRAL[self._tier]


# ===========================================================================
# BulletPool — SoA, com suporte a estados de comportamento (Mago do Tempo)
# ===========================================================================
class BulletPool:
    def __init__(self):
        self.bx      = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.by      = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.bvx     = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.bvy     = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.active  = np.zeros(MAX_BULLETS, dtype=np.bool_)
        self.parried = np.zeros(MAX_BULLETS, dtype=np.bool_)
        self.grazed  = np.zeros(MAX_BULLETS, dtype=np.bool_)
        # Behavior state para Mago do Tempo
        self.bstate  = np.zeros(MAX_BULLETS, dtype=np.int8)
        self.btimer  = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.btgt_x  = np.zeros(MAX_BULLETS, dtype=np.float32)
        self.btgt_y  = np.zeros(MAX_BULLETS, dtype=np.float32)
        # Tipo e flags de bala
        self.b_type      = np.zeros(MAX_BULLETS, dtype=np.int8)
        self.b_invisible = np.zeros(MAX_BULLETS, dtype=bool)  # Labirinto Invisível
        self.b_bounces   = np.zeros(MAX_BULLETS, dtype=np.int8)
        self.b_ricochet  = np.zeros(MAX_BULLETS, dtype=np.bool_)
        self.b_fragment  = np.zeros(MAX_BULLETS, dtype=np.bool_)  # True = não fragmenta novamente
        self.free_stack: list = list(range(MAX_BULLETS - 1, -1, -1))
        self.active_count = 0
        self._screen_wrap = False   # quando True balas envolvem a tela (SinBoss P2)
        self._abissal    = False    # DIFF_ABISSAL: ativa fragmentação
        self._frag_n     = 0        # fragmentos pendentes de parry a spawnar no próx. update
        self._frag_x     = np.zeros(64, dtype=np.float32)
        self._frag_y     = np.zeros(64, dtype=np.float32)
        self._frag_vx    = np.zeros(64, dtype=np.float32)
        self._frag_vy    = np.zeros(64, dtype=np.float32)
        self._frag_type  = np.zeros(64, dtype=np.int8)

    def acquire(self) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx]      = True
        self.bstate[idx]      = BNORMAL
        self.btimer[idx]      = 0.0
        self.b_type[idx]      = BTYPE_NORMAL
        self.b_invisible[idx] = False
        self.b_bounces[idx]   = 0
        self.b_ricochet[idx]  = False
        self.b_fragment[idx]  = False
        self.active_count += 1
        return idx

    def release(self, idx: int):
        self.active[idx]      = False
        self.parried[idx]     = False
        self.grazed[idx]      = False
        self.bstate[idx]      = BNORMAL
        self.btimer[idx]      = 0.0
        self.b_type[idx]      = BTYPE_NORMAL
        self.b_invisible[idx] = False
        self.b_bounces[idx]   = 0
        self.b_ricochet[idx]  = False
        self.b_fragment[idx]  = False
        self.btgt_x[idx]      = 0.0
        self.btgt_y[idx]      = 0.0
        self.free_stack.append(idx)
        self.active_count -= 1

    def clear(self):
        self.active[:]      = False
        self.parried[:]     = False
        self.grazed[:]      = False
        self.bstate[:]      = BNORMAL
        self.b_type[:]      = BTYPE_NORMAL
        self.b_invisible[:] = False
        self.b_bounces[:]   = 0
        self.b_ricochet[:]  = False
        self.b_fragment[:]  = False
        self.active_count = 0
        self._frag_n = 0
        self.free_stack = list(range(MAX_BULLETS - 1, -1, -1))

    def _spawn_fragment_pair(self, fx, fy, fvx, fvy, btype=BTYPE_NORMAL):
        """Spawna 2 fragmentos em ±30° da direção de retorno, herdando tipo/cor da bala mãe."""
        _away = math.atan2(-fvy, -fvx)
        _spd  = math.hypot(fvx, fvy)
        for _da in (-0.524, 0.524):
            _bidx = self.acquire()
            if _bidx < 0: return
            _ang = _away + _da
            self.bx[_bidx]        = fx
            self.by[_bidx]        = fy
            self.bvx[_bidx]       = math.cos(_ang) * _spd
            self.bvy[_bidx]       = math.sin(_ang) * _spd
            self.b_type[_bidx]    = btype
            self.b_bounces[_bidx] = 0
            self.b_fragment[_bidx]= True

    def spawn_tether(self, x1: float, y1: float, vx1: float, vy1: float,
                     x2: float, y2: float, vx2: float, vy2: float) -> bool:
        """Spawn um par de balas algema. Retorna True se ambas foram alocadas."""
        if len(self.free_stack) < 2: return False
        i = self.free_stack.pop()
        j = self.free_stack.pop()
        for idx, (x, y, vx, vy) in ((i, (x1, y1, vx1, vy1)), (j, (x2, y2, vx2, vy2))):
            self.active[idx]  = True
            self.bx[idx]      = x;   self.by[idx]  = y
            self.bvx[idx]     = vx;  self.bvy[idx] = vy
            self.b_type[idx]  = BTYPE_TETHER
            self.bstate[idx]  = BNORMAL
            self.active_count += 1
        self.btgt_x[i] = float(j)   # i conhece j
        self.btgt_x[j] = float(i)   # j conhece i
        return True

    def tether_check(self, px: float, py: float, player_r: float = 6.0) -> bool:
        """Retorna True se o jogador intersecta algum fio de tether ativo."""
        tether_m = self.active & (self.b_type == BTYPE_TETHER)
        idxs     = np.where(tether_m)[0]
        seen: set = set()
        for _i in idxs:
            i = int(_i)
            if i in seen: continue
            j = int(round(float(self.btgt_x[i])))
            if j < 0 or j >= len(self.active): continue
            if not self.active[j]: continue
            seen.add(i); seen.add(j)
            ax, ay = float(self.bx[i]), float(self.by[i])
            bx2, by2 = float(self.bx[j]), float(self.by[j])
            abx = bx2 - ax; aby = by2 - ay
            ab_sq = abx*abx + aby*aby
            if ab_sq < 1e-6: continue
            t = max(0.0, min(1.0, ((px - ax)*abx + (py - ay)*aby) / ab_sq))
            cx2 = ax + t*abx; cy2 = ay + t*aby
            if (px - cx2)**2 + (py - cy2)**2 <= player_r * player_r:
                return True
        return False

    def update(self, dt: float, px: float = 0.0, py: float = 0.0):
        # ABISSAL: spawna fragmentos de parry enfileirados por parry_player
        if self._frag_n > 0:
            for _fi in range(self._frag_n):
                self._spawn_fragment_pair(
                    float(self._frag_x[_fi]), float(self._frag_y[_fi]),
                    float(self._frag_vx[_fi]), float(self._frag_vy[_fi]),
                    int(self._frag_type[_fi]))
            self._frag_n = 0

        # Processa estados de comportamento (apenas para balas não-normais)
        non_normal = np.where(self.active & (self.bstate != BNORMAL))[0]
        for i in non_normal:
            idx = int(i)
            st = int(self.bstate[idx])
            self.btimer[idx] -= dt
            if st == BSTOP_PENDING and self.btimer[idx] <= 0.0:
                self.bvx[idx] = 0.0
                self.bvy[idx] = 0.0
                self.bstate[idx] = BSTOPPED
                self.btimer[idx] = STOPGO_PAUSE
            elif st == BSTOPPED and self.btimer[idx] <= 0.0:
                dx = self.btgt_x[idx] - self.bx[idx]
                dy = self.btgt_y[idx] - self.by[idx]
                mag = math.sqrt(dx * dx + dy * dy) + 1e-6
                self.bvx[idx] = dx / mag * STOPGO_RELAUNCH_SPEED
                self.bvy[idx] = dy / mag * STOPGO_RELAUNCH_SPEED
                self.bstate[idx] = BNORMAL
            elif st == BBOOM_PENDING and self.btimer[idx] <= 0.0:
                self.bvx[idx] *= -1.8
                self.bvy[idx] *= -1.8
                self.bstate[idx] = BNORMAL
            elif st == BSLEEPING and self.btimer[idx] <= 0.0:
                # Bala de vespa acorda: dispara em direção à posição atual do jogador
                dx = px - self.bx[idx]; dy = py - self.by[idx]
                mag = math.sqrt(dx * dx + dy * dy) + 1e-6
                self.bvx[idx] = dx / mag * TWIN_PURPLE_SPEED
                self.bvy[idx] = dy / mag * TWIN_PURPLE_SPEED
                self.b_type[idx]  = BTYPE_PURPLE
                self.btimer[idx]  = random.uniform(TWIN_PURPLE_HOME_T * 0.4,
                                                   TWIN_PURPLE_HOME_T)
                self.bstate[idx]  = BNORMAL

        # Homing roxo vetorizado (apenas BTYPE_PURPLE em voo normal com timer > 0)
        homing = self.active & (self.b_type == BTYPE_PURPLE) & (self.btimer > 0.0) & (self.bstate == BNORMAL)
        if homing.any():
            hi = np.where(homing)[0]
            self.btimer[hi] -= dt
            dx = px - self.bx[hi]; dy = py - self.by[hi]
            dist = np.sqrt(dx * dx + dy * dy) + 1e-3
            nx = dx / dist; ny = dy / dist
            self.bvx[hi] += nx * (TWIN_PURPLE_HOME_CURL * dt)
            self.bvy[hi] += ny * (TWIN_PURPLE_HOME_CURL * dt)
            spd = np.sqrt(self.bvx[hi] ** 2 + self.bvy[hi] ** 2)
            over = spd > TWIN_PURPLE_MAX_SPD
            if over.any():
                oi = hi[over]
                self.bvx[oi] = self.bvx[oi] / spd[over] * TWIN_PURPLE_MAX_SPD
                self.bvy[oi] = self.bvy[oi] / spd[over] * TWIN_PURPLE_MAX_SPD

        # BTYPE_PHASE: cicla timer de fase (btgt_x = tempo acumulado, 0→PERIOD)
        phase_m = self.active & (self.b_type == BTYPE_PHASE)
        if phase_m.any():
            self.btgt_x[phase_m] += dt
            wrap_m = phase_m & (self.btgt_x >= BULLET_PHASE_PERIOD)
            self.btgt_x[wrap_m] -= BULLET_PHASE_PERIOD

        # BTYPE_SPIN: rotaciona o vetor velocidade (btgt_x = taxa rad/s, btgt_y = sinal dir)
        spin_m = self.active & (self.b_type == BTYPE_SPIN)
        if spin_m.any():
            si = np.where(spin_m)[0]
            theta = self.btgt_x[si] * dt
            cos_a = np.cos(theta); sin_a = np.sin(theta)
            vx_new = self.bvx[si] * cos_a - self.bvy[si] * sin_a
            vy_new = self.bvx[si] * sin_a + self.bvy[si] * cos_a
            self.bvx[si] = vx_new
            self.bvy[si] = vy_new

        mask = self.active
        self.bx[mask] += self.bvx[mask] * dt
        self.by[mask] += self.bvy[mask] * dt

        # Ricochet: reflete nas bordas da tela para balas com bounces restantes
        ricochet_m = mask & (self.b_bounces > 0)
        if ricochet_m.any():
            ri = np.where(ricochet_m)[0]
            hit_L = self.bx[ri] < 0.0
            hit_R = self.bx[ri] > float(SCREEN_W)
            hit_T = self.by[ri] < 0.0
            hit_B = self.by[ri] > float(SCREEN_H)
            hit_wall = hit_L | hit_R | hit_T | hit_B
            if hit_wall.any():
                hw = ri[hit_wall]
                lr_m = hit_L[hit_wall] | hit_R[hit_wall]
                if lr_m.any():
                    self.bvx[hw[lr_m]] = -self.bvx[hw[lr_m]]
                tb_m = hit_T[hit_wall] | hit_B[hit_wall]
                if tb_m.any():
                    self.bvy[hw[tb_m]] = -self.bvy[hw[tb_m]]
                self.bx[hw] = np.clip(self.bx[hw], 2.0, float(SCREEN_W) - 2.0)
                self.by[hw] = np.clip(self.by[hw], 2.0, float(SCREEN_H) - 2.0)
                self.b_bounces[hw] -= 1
                self.b_ricochet[hw] = True

        if self._screen_wrap:
            # SinBoss P2 — balas envolvem a tela em vez de sair
            wm = self.active & (self.b_bounces == 0)
            self.bx[wm] = (self.bx[wm] % float(SCREEN_W) + SCREEN_W) % SCREEN_W
            self.by[wm] = (self.by[wm] % float(SCREEN_H) + SCREEN_H) % SCREEN_H
        else:
            M = 50.0
            oob = mask & (
                (self.bx < -M) | (self.bx > SCREEN_W + M) |
                (self.by < -M) | (self.by > SCREEN_H + M)
            )
            if self._abissal:
                for idx in np.where(oob)[0]:
                    i = int(idx)
                    if not self.b_fragment[i]:
                        self._spawn_fragment_pair(
                            float(max(0.0, min(float(SCREEN_W), self.bx[i]))),
                            float(max(0.0, min(float(SCREEN_H), self.by[i]))),
                            float(self.bvx[i]), float(self.bvy[i]),
                            int(self.b_type[i]))
                    self.release(i)
            else:
                for idx in np.where(oob)[0]:
                    self.release(int(idx))


# ===========================================================================
# HazardPool — zonas de perigo residuais (denial of area), 20 slots pré-alocados
# ===========================================================================
class HazardPool:
    def __init__(self):
        self.hx       = np.zeros(MAX_HAZARDS, dtype=np.float32)
        self.hy       = np.zeros(MAX_HAZARDS, dtype=np.float32)
        self.hr       = np.zeros(MAX_HAZARDS, dtype=np.float32)
        self.htimer   = np.zeros(MAX_HAZARDS, dtype=np.float32)
        self.htype    = np.zeros(MAX_HAZARDS, dtype=np.int8)
        self.hburn_cd = np.zeros(MAX_HAZARDS, dtype=np.float32)
        self.active   = np.zeros(MAX_HAZARDS, dtype=np.bool_)
        self.free_stack: list = list(range(MAX_HAZARDS - 1, -1, -1))

    def spawn(self, x: float, y: float, radius: float,
              duration: float, htype: int = HAZARD_BURN) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.hx[idx] = x;  self.hy[idx] = y
        self.hr[idx] = radius; self.htimer[idx] = duration
        self.htype[idx] = htype; self.hburn_cd[idx] = 0.0
        self.active[idx] = True
        return idx

    def release(self, idx: int):
        self.active[idx] = False
        self.free_stack.append(idx)

    def clear(self):
        self.active[:] = False
        self.free_stack = list(range(MAX_HAZARDS - 1, -1, -1))

    def update(self, dt: float):
        for i in np.where(self.active)[0]:
            i = int(i)
            self.htimer[i] -= dt
            if self.htimer[i] <= 0.0:
                self.release(i)
            elif self.hburn_cd[i] > 0.0:
                self.hburn_cd[i] -= dt

    def check_player(self, px: float, py: float) -> int:
        """Retorna htype do primeiro hazard que contém o jogador, ou -1."""
        active_i = np.where(self.active)[0]
        if active_i.size == 0: return -1
        dx = self.hx[active_i] - px
        dy = self.hy[active_i] - py
        in_hz = dx * dx + dy * dy < self.hr[active_i] * self.hr[active_i]
        if in_hz.any():
            return int(self.htype[active_i[np.where(in_hz)[0][0]]])
        return -1

    def tick_burn(self, px: float, py: float) -> bool:
        """True se um HAZARD_BURN sobrepõe o jogador e o cooldown expirou."""
        for i in np.where(self.active)[0]:
            i = int(i)
            if int(self.htype[i]) != HAZARD_BURN: continue
            dx = self.hx[i] - px; dy = self.hy[i] - py
            if dx * dx + dy * dy < self.hr[i] * self.hr[i]:
                if self.hburn_cd[i] <= 0.0:
                    self.hburn_cd[i] = HAZARD_BURN_INTERVAL
                    return True
        return False


# ===========================================================================
# PlayerBulletPool
# ===========================================================================
class PlayerBulletPool:
    def __init__(self):
        self.px      = np.zeros(MAX_PB, dtype=np.float32)
        self.py      = np.zeros(MAX_PB, dtype=np.float32)
        self.pvx     = np.zeros(MAX_PB, dtype=np.float32)
        self.pvy     = np.full(MAX_PB, -PB_SPEED, dtype=np.float32)
        self.active  = np.zeros(MAX_PB, dtype=np.bool_)
        self.damage  = np.ones(MAX_PB,  dtype=np.float32)
        self.pb_size   = np.full(MAX_PB, 4.0, dtype=np.float32)
        self.pb_homing = np.zeros(MAX_PB, dtype=np.bool_)
        self.pb_home_t = np.zeros(MAX_PB, dtype=np.float32)
        self.pb_type    = np.zeros(MAX_PB, dtype=np.int8)     # PB_NORMAL/FLAK/etc
        self.pb_timer   = np.zeros(MAX_PB, dtype=np.float32)  # multi-purpose timer per type
        self.pb_state   = np.zeros(MAX_PB, dtype=np.int8)     # per-type state flags
        self.pb_orbit_a = np.zeros(MAX_PB, dtype=np.float32)  # ORBIT angle / BURST+ aim angle
        self.pb_bounces = np.zeros(MAX_PB, dtype=np.int8)     # PADRÃO+: ricochetes restantes
        self.pb_pierce  = np.zeros(MAX_PB, dtype=np.bool_)    # AGULHA+: perfura sem destruir
        # Pre-allocated hit buffer for CARREGADO+ shrapnel (no GC during gameplay)
        self._hit_buf   = np.zeros((16, 2), dtype=np.float32)  # [(px, py), ...]
        self._hit_buf_n = 0
        self.free_stack: list = list(range(MAX_PB - 1, -1, -1))
        self.active_count = 0

    def acquire(self, damage: float = 1.0, vx: float = 0.0, vy: float = -PB_SPEED,
                size: float = 4.0, homing: bool = False, home_t: float = 0.0,
                pb_type: int = PB_NORMAL, timer: float = 0.0,
                state: int = 0, orbit_angle: float = 0.0,
                bounces: int = 0, pierce: bool = False) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx]     = True
        self.damage[idx]     = damage
        self.pvx[idx]        = vx
        self.pvy[idx]        = vy
        self.pb_size[idx]    = size
        self.pb_homing[idx]  = homing
        self.pb_home_t[idx]  = home_t
        self.pb_type[idx]    = pb_type
        self.pb_timer[idx]   = timer
        self.pb_state[idx]   = state
        self.pb_orbit_a[idx] = orbit_angle
        self.pb_bounces[idx] = bounces
        self.pb_pierce[idx]  = pierce
        self.active_count   += 1
        return idx

    def release(self, idx: int):
        self.active[idx]     = False
        self.damage[idx]     = 1.0
        self.pvx[idx]        = 0.0
        self.pvy[idx]        = -PB_SPEED
        self.pb_size[idx]    = 4.0
        self.pb_homing[idx]  = False
        self.pb_home_t[idx]  = 0.0
        self.pb_type[idx]    = PB_NORMAL
        self.pb_timer[idx]   = 0.0
        self.pb_state[idx]   = 0
        self.pb_orbit_a[idx] = 0.0
        self.pb_bounces[idx] = 0
        self.pb_pierce[idx]  = False
        self.free_stack.append(idx)
        self.active_count -= 1

    def update(self, dt: float, tx: float = 0.0, ty: float = 0.0):
        mask = self.active

        # ---- PLASMA (moving): countdown de vida — release ou spawn poça quando expira
        plasma_m = mask & (self.pb_type == PB_PLASMA)
        if plasma_m.any():
            self.pb_timer[plasma_m] -= dt
            for _idx in np.where(plasma_m & (self.pb_timer <= 0.0))[0]:
                _idx = int(_idx)
                if self.pb_state[_idx] == 1:   # PLASMA+: beacom → gera poça
                    _px2, _py2 = float(self.px[_idx]), float(self.py[_idx])
                    self.release(_idx)
                    _pu = self.acquire(0.0, 0.0, 0.0, size=PLASMA_SIZE,
                                       pb_type=PB_PLASMA_PUDDLE,
                                       timer=PLASMA_PLUS_PUDDLE_T, state=0)
                    if _pu >= 0:
                        self.px[_pu] = _px2; self.py[_pu] = _py2
                else:
                    self.release(_idx)

        # ---- PLASMA_PUDDLE: countdown de vida separado
        puddle_m = mask & (self.pb_type == PB_PLASMA_PUDDLE)
        if puddle_m.any():
            self.pb_timer[puddle_m] -= dt
            for _idx in np.where(puddle_m & (self.pb_timer <= 0.0))[0]:
                self.release(int(_idx))

        # ---- FLAK: countdown de detonação — spawn estilhaços quando expira
        flak_m = self.active & (self.pb_type == PB_FLAK)
        if flak_m.any():
            self.pb_timer[flak_m] -= dt
            expired_f = flak_m & (self.pb_timer <= 0.0)
            if expired_f.any():
                detonated = np.where(expired_f)[0].tolist()
                for _fi in detonated:
                    _fi = int(_fi)
                    _fx, _fy = float(self.px[_fi]), float(self.py[_fi])
                    self.release(_fi)
                    for _k in range(FLAK_SHRAPNEL_N):
                        _t   = _k / max(1, FLAK_SHRAPNEL_N - 1) - 0.5
                        _ang = -math.pi / 2.0 + _t * FLAK_SHRAPNEL_ARC
                        _svx = math.cos(_ang) * FLAK_SHRAPNEL_SPD
                        _svy = math.sin(_ang) * FLAK_SHRAPNEL_SPD
                        _si  = self.acquire(FLAK_SHRAPNEL_DMG, _svx, _svy,
                                            size=FLAK_SHRAPNEL_SIZE)
                        if _si >= 0:
                            self.px[_si] = _fx;  self.py[_si] = _fy

        # ---- BURST+: arm countdown — bala parada acelera após BURST_PLUS_ARM_T
        # pb_type==PB_NORMAL, pb_timer>0, pb_state==0  →  arming phase
        burst_arm_m = self.active & (self.pb_type == PB_NORMAL) & (self.pb_timer > 0.0) & (self.pb_state == 0)
        if burst_arm_m.any():
            self.pb_timer[burst_arm_m] -= dt
            for _bi in np.where(burst_arm_m & (self.pb_timer <= 0.0))[0]:
                _bi = int(_bi)
                _ang = float(self.pb_orbit_a[_bi])  # aim angle stored at spawn
                self.pvx[_bi] = math.cos(_ang) * BURST_PLUS_MAX_SPD
                self.pvy[_bi] = math.sin(_ang) * BURST_PLUS_MAX_SPD
                self.pb_state[_bi] = 1   # armed

        # ---- AGULHA+: pierce cooldown decrement
        pierce_cd_m = self.active & self.pb_pierce & (self.pb_timer > 0.0)
        if pierce_cd_m.any():
            self.pb_timer[pierce_cd_m] -= dt
            np.maximum(self.pb_timer, 0.0, out=self.pb_timer)

        # ---- SPREAD+: range countdown — bullets with pb_state==1 and timer expire
        # pb_type==PB_NORMAL, pb_state==1, pb_timer>0  →  SPREAD+ range-limited
        spread_rng_m = self.active & (self.pb_type == PB_NORMAL) & (self.pb_state == 1) & (self.pb_timer > 0.0)
        if spread_rng_m.any():
            self.pb_timer[spread_rng_m] -= dt
            for _sri in np.where(spread_rng_m & (self.pb_timer <= 0.0))[0]:
                self.release(int(_sri))

        # ---- CHAKRAM: aplica drag (desacelera, inverte e retorna)
        # pb_state==2 (CHAKRAM+): frozen — zeramos velocidade (mantido por main.py enquanto fire held)
        chakram_m = self.active & (self.pb_type == PB_CHAKRAM)
        if chakram_m.any():
            _ci = np.where(chakram_m)[0]
            frz_m = self.pb_state[_ci] == 2
            if frz_m.any():
                _fci = _ci[frz_m]
                self.pvx[_fci] = 0.0; self.pvy[_fci] = 0.0
            mov_m = ~frz_m
            if mov_m.any():
                _mci = _ci[mov_m]
                self.pvy[_mci] += CHAKRAM_DRAG * dt
                self.pb_state[_mci[self.pvy[_mci] > 0.0]] = 1   # marcar retorno

        # ---- Posição: todos menos ORBIT e HOMING_HELD (posições gerenciadas externamente)
        mask = self.active
        move_m = mask & (self.pb_type != PB_ORBIT) & (self.pb_type != PB_HOMING_HELD)
        self.px[move_m] += self.pvx[move_m] * dt
        self.py[move_m] += self.pvy[move_m] * dt

        # ---- PADRÃO+: ricochetear em paredes laterais
        bounce_m = mask & (self.pb_bounces > 0)
        if bounce_m.any():
            _bl = bounce_m & (self.px < 0.0)
            _br = bounce_m & (self.px > float(SCREEN_W))
            if _bl.any():
                self.px[_bl] = 0.0; self.pvx[_bl] *= -1.0; self.pb_bounces[_bl] -= 1
            if _br.any():
                self.px[_br] = float(SCREEN_W); self.pvx[_br] *= -1.0; self.pb_bounces[_br] -= 1

        # Homing missiles: curve toward target while home_t > 0
        homing_m = mask & self.pb_homing & (self.pb_home_t > 0.0)
        if homing_m.any():
            hi = np.where(homing_m)[0]
            self.pb_home_t[hi] -= dt
            dx = tx - self.px[hi]; dy = ty - self.py[hi]
            dist = np.sqrt(dx * dx + dy * dy) + 1e-3
            # Curva dinâmica: gira mais devagar conforme acelera (míssil realista)
            spd_pre  = np.sqrt(self.pvx[hi] ** 2 + self.pvy[hi] ** 2) + 1e-3
            spd_norm = np.clip(spd_pre / PB_HOMING_MAX_SPD, 0.0, 1.0)
            dyn_curl = PB_HOMING_CURL * (1.0 - spd_norm * 0.65)
            self.pvx[hi] += (dx / dist) * (dyn_curl * dt)
            self.pvy[hi] += (dy / dist) * (dyn_curl * dt)
            spd = np.sqrt(self.pvx[hi] ** 2 + self.pvy[hi] ** 2)
            over = spd > PB_HOMING_MAX_SPD
            if over.any():
                oi = hi[over]; s = spd[over]
                self.pvx[oi] = self.pvx[oi] / s * PB_HOMING_MAX_SPD
                self.pvy[oi] = self.pvy[oi] / s * PB_HOMING_MAX_SPD

        # OOB: exclui ORBIT, HOMING_HELD e PLASMA_PUDDLE (poças são estacionárias)
        oob = mask & (self.pb_type != PB_ORBIT) & (self.pb_type != PB_HOMING_HELD) & \
              (self.pb_type != PB_PLASMA_PUDDLE) & \
              ((self.py < -10.0) | (self.py > SCREEN_H + 10.0) |
               (self.px < -10.0) | (self.px > SCREEN_W + 10.0))
        for idx in np.where(oob)[0]:
            self.release(int(idx))


# ===========================================================================
# EmitterPool
# ===========================================================================
class EmitterPool:
    def __init__(self):
        self.ex     = np.zeros(MAX_EMITTERS, dtype=np.float32)
        self.ey     = np.zeros(MAX_EMITTERS, dtype=np.float32)
        self.angle  = np.zeros(MAX_EMITTERS, dtype=np.float32)
        self.timer  = np.zeros(MAX_EMITTERS, dtype=np.float32)
        self.espeed = np.full(MAX_EMITTERS, BLAST_SPEED, dtype=np.float32)
        self.fired  = np.zeros(MAX_EMITTERS, dtype=np.bool_)
        self.active = np.zeros(MAX_EMITTERS, dtype=np.bool_)
        self.free_stack: list = list(range(MAX_EMITTERS - 1, -1, -1))
        self.active_count = 0

    def acquire(self) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx] = True
        self.fired[idx]  = False
        self.active_count += 1
        return idx

    def release(self, idx: int):
        self.active[idx] = False
        self.free_stack.append(idx)
        self.active_count -= 1

    def clear(self):
        self.active[:] = False
        self.active_count = 0
        self.free_stack = list(range(MAX_EMITTERS - 1, -1, -1))

    def update(self, dt: float, pool: BulletPool):
        for i in np.where(self.active)[0]:
            idx = int(i)
            self.timer[idx] -= dt
            if not self.fired[idx] and self.timer[idx] <= 0.0:
                self._fire(idx, pool)
                self.timer[idx] = 0.28
                self.fired[idx] = True
            elif self.fired[idx] and self.timer[idx] <= 0.0:
                self.release(idx)

    def _fire(self, idx: int, pool: BulletPool):
        ang  = float(self.angle[idx])
        spd  = float(self.espeed[idx])
        x, y = float(self.ex[idx]), float(self.ey[idx])
        half = BLAST_SPREAD_RAD / 2.0
        n    = BLAST_N_BULLETS
        for i in range(n):
            t     = i / (n - 1) if n > 1 else 0.5
            theta = ang - half + t * BLAST_SPREAD_RAD
            bidx  = pool.acquire()
            if bidx < 0: return
            pool.bx[bidx]  = x;  pool.by[bidx]  = y
            pool.bvx[bidx] = math.cos(theta) * spd
            pool.bvy[bidx] = math.sin(theta) * spd


# ===========================================================================
# LaserPool
# ===========================================================================
class LaserPool:
    def __init__(self):
        self.lpos   = np.zeros(MAX_LASERS, dtype=np.float32)
        self.horiz  = np.zeros(MAX_LASERS, dtype=np.bool_)
        self.timer  = np.zeros(MAX_LASERS, dtype=np.float32)
        self.active = np.zeros(MAX_LASERS, dtype=np.bool_)
        self.free_stack: list = list(range(MAX_LASERS - 1, -1, -1))
        self.active_count = 0

    def acquire(self, pos: float, horiz: bool) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx] = True
        self.lpos[idx]   = pos
        self.horiz[idx]  = horiz
        self.timer[idx]  = LASER_TELEGRAPH
        self.active_count += 1
        return idx

    def release(self, idx: int):
        self.active[idx] = False
        self.free_stack.append(idx)
        self.active_count -= 1

    def clear(self):
        self.active[:] = False
        self.active_count = 0
        self.free_stack = list(range(MAX_LASERS - 1, -1, -1))

    def update(self, dt: float):
        for i in np.where(self.active)[0]:
            idx = int(i)
            self.timer[idx] -= dt
            if self.timer[idx] <= -(LASER_FIRE_DUR + 0.15):
                self.release(idx)

    def check_player(self, px: float, py: float) -> bool:
        for i in np.where(self.active)[0]:
            idx = int(i)
            if self.timer[idx] > 0.0: continue
            pos = float(self.lpos[idx])
            if bool(self.horiz[idx]):
                if abs(py - pos) <= LASER_HIT_HALF: return True
            else:
                if abs(px - pos) <= LASER_HIT_HALF: return True
        return False


# ===========================================================================
# ParticlePool — física simples: velocidade + gravidade + fade
# ===========================================================================
class ParticlePool:
    def __init__(self):
        self.px      = np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.py      = np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.pvx     = np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.pvy     = np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.life    = np.zeros(MAX_PARTICLES, dtype=np.float32)  # restante em s
        self.max_life= np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.r       = np.zeros(MAX_PARTICLES, dtype=np.uint8)
        self.g       = np.zeros(MAX_PARTICLES, dtype=np.uint8)
        self.b       = np.zeros(MAX_PARTICLES, dtype=np.uint8)
        self.radius  = np.zeros(MAX_PARTICLES, dtype=np.float32)
        self.active  = np.zeros(MAX_PARTICLES, dtype=np.bool_)
        self.free_stack: list = list(range(MAX_PARTICLES - 1, -1, -1))
        self.active_count = 0

    def acquire(self) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx] = True
        self.active_count += 1
        return idx

    def release(self, idx: int):
        self.active[idx] = False
        self.free_stack.append(idx)
        self.active_count -= 1

    def emit(self, x: float, y: float, color: tuple, n: int,
             speed_lo: float, speed_hi: float,
             life_lo: float, life_hi: float,
             radius: float = 3.0, gravity: float = PARTICLE_GRAVITY):
        for _ in range(n):
            idx = self.acquire()
            if idx < 0: return
            angle = random.uniform(0.0, TWO_PI)
            spd   = random.uniform(speed_lo, speed_hi)
            lt    = random.uniform(life_lo, life_hi)
            self.px[idx]       = x
            self.py[idx]       = y
            self.pvx[idx]      = math.cos(angle) * spd
            self.pvy[idx]      = math.sin(angle) * spd
            self.life[idx]     = lt
            self.max_life[idx] = lt
            self.r[idx], self.g[idx], self.b[idx] = color[0], color[1], color[2]
            self.radius[idx]   = radius

    def update(self, dt: float):
        mask = self.active
        self.pvx[mask] += 0.0
        self.pvy[mask] += PARTICLE_GRAVITY * dt
        self.px[mask]  += self.pvx[mask] * dt
        self.py[mask]  += self.pvy[mask] * dt
        self.life[mask] -= dt
        dead = np.where(mask & (self.life <= 0.0))[0]
        for idx in dead:
            self.release(int(idx))


# ===========================================================================
# SpatialHash
# ===========================================================================
class SpatialHash:
    def __init__(self):
        self.cell_count = np.zeros(GRID_CELLS, dtype=np.int32)
        self.cell_start = np.zeros(GRID_CELLS, dtype=np.int32)
        self.sorted_idx = np.zeros(MAX_BULLETS, dtype=np.int32)

    def build(self, pool: BulletPool):
        active_idx = np.where(pool.active)[0]
        self.cell_count[:] = 0
        if not len(active_idx): return
        gx = np.clip(pool.bx[active_idx].astype(np.int32) // CELL_SIZE, 0, GRID_COLS-1)
        gy = np.clip(pool.by[active_idx].astype(np.int32) // CELL_SIZE, 0, GRID_ROWS-1)
        cells = gy * GRID_COLS + gx
        order = np.argsort(cells, kind='stable')
        self.sorted_idx[:len(active_idx)] = active_idx[order]
        self.cell_count[:] = np.bincount(cells[order], minlength=GRID_CELLS)
        self.cell_start[0] = 0
        np.cumsum(self.cell_count[:-1], out=self.cell_start[1:])

    def parry_player(self, px: float, py: float, pool: BulletPool,
                     pb_pool=None, parry_plus: bool = False) -> int:
        r    = PARRY_RANGE
        r_sq = r * r
        gx0  = max(0,           int((px - r) / CELL_SIZE))
        gx1  = min(GRID_COLS-1, int((px + r) / CELL_SIZE))
        gy0  = max(0,           int((py - r) / CELL_SIZE))
        gy1  = min(GRID_ROWS-1, int((py + r) / CELL_SIZE))
        reflected_count = 0
        for cy in range(gy0, gy1 + 1):
            for cx in range(gx0, gx1 + 1):
                c     = cy * GRID_COLS + cx
                start = int(self.cell_start[c])
                count = int(self.cell_count[c])
                if not count: continue
                cands = self.sorted_idx[start:start + count]
                dx = pool.bx[cands] - px
                dy = pool.by[cands] - py
                for idx in cands[(dx * dx + dy * dy) <= r_sq]:
                    if pool.active[idx] and not pool.parried[idx]:
                        if pool._abissal and not pool.b_fragment[idx]:
                            # ABISSAL: destrói e enfileira fragmentos em vez de refletir
                            if pool._frag_n < 62:
                                pool._frag_x[pool._frag_n]    = float(pool.bx[idx])
                                pool._frag_y[pool._frag_n]    = float(pool.by[idx])
                                pool._frag_vx[pool._frag_n]   = float(pool.bvx[idx])
                                pool._frag_vy[pool._frag_n]   = float(pool.bvy[idx])
                                pool._frag_type[pool._frag_n] = int(pool.b_type[idx])
                                pool._frag_n += 1
                            pool.release(int(idx))
                        elif parry_plus and pb_pool is not None:
                            # PARRY+ (Royal Guard): converte bala inimiga em míssil homing
                            pidx = pb_pool.acquire(PARRY_PLUS_HOMING_DMG, 0.0, -PB_SPEED,
                                                   size=3.0, homing=True,
                                                   home_t=PB_HOMING_HOME_T)
                            if pidx >= 0:
                                pb_pool.px[pidx] = float(pool.bx[idx])
                                pb_pool.py[pidx] = float(pool.by[idx])
                            pool.release(int(idx))
                            reflected_count += 1
                        else:
                            pool.bvx[idx]    *= -1.0
                            pool.bvy[idx]    *= -1.0
                            pool.parried[idx] = True
                            reflected_count += 1
        return reflected_count

    def query_player(self, px: float, py: float, pool: BulletPool,
                     pvx: float = 0.0, pvy: float = 0.0) -> int:
        r = PLAYER_RADIUS + BULLET_RADIUS
        gx0 = max(0,           int((px-r)/CELL_SIZE))
        gx1 = min(GRID_COLS-1, int((px+r)/CELL_SIZE))
        gy0 = max(0,           int((py-r)/CELL_SIZE))
        gy1 = min(GRID_ROWS-1, int((py+r)/CELL_SIZE))
        hits = 0
        player_moving = (pvx*pvx + pvy*pvy) > TWIN_MOVING_THRESH * TWIN_MOVING_THRESH
        for cy in range(gy0, gy1+1):
            for cx in range(gx0, gx1+1):
                c     = cy*GRID_COLS + cx
                start = int(self.cell_start[c])
                count = int(self.cell_count[c])
                if not count: continue
                cands = self.sorted_idx[start:start+count]
                dx = pool.bx[cands] - px
                dy = pool.by[cands] - py
                for idx in cands[(dx*dx + dy*dy) <= HIT_SQ]:
                    if pool.active[idx]:
                        bt = int(pool.b_type[idx])
                        # Yin (azul): só dano se jogador se move
                        if bt == BTYPE_BLUE and not player_moving:
                            continue
                        # Yang (laranja): só dano se jogador parado
                        if bt == BTYPE_ORANGE and player_moving:
                            continue
                        # Gravitacional: não causa dano direto
                        if bt == BTYPE_GRAVITY:
                            continue
                        # Phase: só dano quando sólida (primeira metade do ciclo)
                        if bt == BTYPE_PHASE and float(pool.btgt_x[idx]) >= BULLET_PHASE_SOLID:
                            continue
                        pool.release(int(idx))
                        hits += 1
        return hits

    def query_graze(self, px: float, py: float, pool: BulletPool) -> int:
        """Count bullets in graze zone (GRAZE_SQ) but outside HIT_SQ. Marks grazed to prevent repeats."""
        r = GRAZE_RANGE + BULLET_RADIUS
        gx0 = max(0,           int((px-r)/CELL_SIZE))
        gx1 = min(GRID_COLS-1, int((px+r)/CELL_SIZE))
        gy0 = max(0,           int((py-r)/CELL_SIZE))
        gy1 = min(GRID_ROWS-1, int((py+r)/CELL_SIZE))
        grazes = 0
        for cy in range(gy0, gy1+1):
            for cx in range(gx0, gx1+1):
                c     = cy*GRID_COLS + cx
                start = int(self.cell_start[c])
                count = int(self.cell_count[c])
                if not count: continue
                cands = self.sorted_idx[start:start+count]
                dx = pool.bx[cands] - px
                dy = pool.by[cands] - py
                d2 = dx*dx + dy*dy
                graze_cands = cands[(d2 > HIT_SQ) & (d2 <= GRAZE_SQ)]
                for idx in graze_cands:
                    if pool.active[idx] and not pool.grazed[idx]:
                        pool.grazed[idx] = True
                        grazes += 1
        return grazes


def check_graze(shash: 'SpatialHash', pool: BulletPool, player: 'Player') -> int:
    """Returns number of new grazes this frame. Caller handles CD reduction + effects."""
    if player.invuln > 0: return 0
    count = shash.query_graze(player.cx, player.cy, pool)
    if count:
        player.graze_count += count
    return count


# ===========================================================================
# Player
# ===========================================================================
class Player:
    def __init__(self, config: 'GameConfig' = None):
        self.x          = SCREEN_W / 2.0 - PLAYER_SIZE / 2.0
        self.y          = SCREEN_H * 0.82
        self.invuln     = 0
        self.total_hits = 0
        self.shoot_acc  = 0.0

        cfg_skill    = config.skill    if config else SKILL_NONE
        cfg_weapon   = config.weapon   if config else WEAPON_DEFAULT
        cfg_mutators = config.mutators if config else frozenset()
        self.skill   = cfg_skill
        self.weapon  = cfg_weapon
        self.lives   = 1 if MUTATOR_GLASS_CANNON in cfg_mutators else MAX_LIVES
        self.mutators = cfg_mutators

        # Arena bounds (MUTATOR_CLAUSTROFOBIA encolhe a área de jogo)
        if MUTATOR_CLAUSTROFOBIA in cfg_mutators:
            mx = int(SCREEN_W * ARENA_SHRINK)
            my = int(SCREEN_H * ARENA_SHRINK)
        else:
            mx, my = 0, 0
        self._arena_x0 = float(mx)
        self._arena_y0 = float(my)
        self._arena_x1 = float(SCREEN_W - PLAYER_SIZE - mx)
        self._arena_y1 = float(SCREEN_H - PLAYER_SIZE - my)

        self.skill_t       = 0.0
        self.skill_cd      = 0.0
        self.is_dashing    = False
        self.controls_inverted = False
        self.is_parrying   = False
        self.is_focusing   = False
        self.focus_energy  = 1.0
        self.emp_triggered = False
        self.vx = 0.0
        self.vy = 0.0
        self.graze_count  = 0
        self.parry_count  = 0
        self.trail        = deque(maxlen=6)
        self._trail_show  = 0.0
        # Charged weapon state
        self.charge_t      = 0.0
        self.is_charging   = False
        self.charge_cd     = 0.0
        # Burst weapon state
        self.burst_cd      = 0.0
        self.burst_q       = 0
        self.burst_sub_t   = 0.0
        # Homing weapon state
        self.homing_cd     = 0.0
        # CD compartilhado para novas armas (FLAK/CHAKRAM/PLASMA/ORBIT)
        self.extra_cd      = 0.0
        # Overclock / Orbital Cannon state
        self.is_overclocking = False
        # Shield state
        self.is_shielding    = False
        # blink origin — usado por BLINK+
        self._blink_fired    = False
        self._blink_ox       = 0.0
        self._blink_oy       = 0.0
        # SKILL_TIMEDILATION state
        self.is_timedilating   = False
        self.timedil_timer     = 0.0

        # Skill+ — flag lida do config
        self.skill_plus  = getattr(config, 'skill_plus', False) if config else False
        # Weapon+ — flag lida do config
        self.weapon_plus = getattr(config, 'weapon_plus', False) if config else False
        # DASH+: i-frames no início do dash
        self._dash_iframe_t    = 0.0
        self._graze_dash_acc   = 0     # grazes durante dash (esta sessão)
        # PARRY+: rastreio de burst por ativação
        self._parry_burst_acc  = 0     # balas refletidas na ativação atual
        self._parry_burst_max  = 0     # máximo em uma ativação esta sessão
        # EMP+: buff de dano
        self._emp_buff_timer   = 0.0
        self._emp_dmg_mult     = 1.0
        self._emp_max_session  = 0     # máximo de balas destruídas em um EMP
        # OVERCLOCK+: rastreio de dano
        self._oc_dmg_acc       = 0.0   # dano na janela atual
        self._oc_dmg_max       = 0.0   # máximo em uma janela esta sessão
        self._oc_was_active    = False  # estado anterior do overclock
        # SHIELD+: perfect block + break
        self._shield_broke     = False  # flag: escudo quebrou neste frame
        self._shield_perfect_acc = 0   # perfect blocks esta sessão
        # TIMEDILATION+: estilhaçar ao terminar
        self._timedil_just_ended = False
        self._timedil_close_used = False  # ativou timedil com bala <5px
        # Weapon mastery trackers (acumuladores por run)
        self._wm_consec_hits    = 0      # PADRÃO: acertos consecutivos sem errar
        self._wm_close_events   = 0      # SPREAD: hits a <40px do boss
        self._wm_needle_misses  = 0      # AGULHA: erros na fase atual
        self._wm_needle_phase_ok = 0     # AGULHA: fases completas com ≤5 erros
        self._wm_charged_multi  = 0      # CARREGADO: kills com ≥3 em 1 tiro max
        self._wm_burst_twins    = 0      # BURST: all-3 hits nos Gêmeos
        self._wm_homing_nohit_w = 0      # HOMING: ondas sem tomar hit
        self._wm_homing_in_wave = False  # HOMING: tomou hit nesta onda?
        self._wm_flak_kills     = 0      # FLAK: projéteis destruídos por 1 explosão
        self._wm_chakram_round  = 0      # CHAKRAM: hits ida+volta no boss
        self._wm_chakram_hit_fwd = False # CHAKRAM: acertou na ida?
        self._wm_plasma_contact = 0.0    # PLASMA: máx. contato contínuo
        self._wm_plasma_streak  = 0.0    # PLASMA: streak atual
        self._wm_orbit_dmg      = 0.0    # ORBIT: dano total de satélites
        self._orbit_launch_cd   = 0.0    # SATÉLITE+: CD entre lançamentos auto

    @property
    def cx(self) -> float: return self.x + PLAYER_SIZE / 2.0
    @property
    def cy(self) -> float: return self.y + PLAYER_SIZE / 2.0

    def update(self, dt: float, keys):
        self.emp_triggered = False
        skill_key = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        if self.skill == SKILL_DASH:
            if skill_key and self.skill_cd <= 0 and not self.is_dashing:
                self.is_dashing = True
                self.skill_t    = DASH_DURATION
                self.skill_cd   = DASH_COOLDOWN
                if self.skill_plus:
                    self._dash_iframe_t = DASH_PLUS_IFRAME_DUR
            if self.is_dashing:
                self.skill_t -= dt
                if self.skill_t <= 0: self.is_dashing = False
            if self._dash_iframe_t > 0:
                self._dash_iframe_t = max(0.0, self._dash_iframe_t - dt)
            if self.skill_cd > 0: self.skill_cd -= dt

        elif self.skill == SKILL_PARRY:
            if skill_key and self.skill_cd <= 0 and not self.is_parrying:
                self.is_parrying = True
                self.skill_t     = PARRY_DURATION
                self.skill_cd    = PARRY_COOLDOWN
            if self.is_parrying:
                self.skill_t -= dt
                if self.skill_t <= 0: self.is_parrying = False
            if self.skill_cd > 0: self.skill_cd -= dt

        elif self.skill == SKILL_FOCUS:
            if skill_key and self.focus_energy > 0:
                self.is_focusing  = True
                self.focus_energy = max(0.0, self.focus_energy - FOCUS_DRAIN_RATE * dt)
                if self.focus_energy == 0.0: self.is_focusing = False
            else:
                self.is_focusing  = False
                self.focus_energy = min(1.0, self.focus_energy + FOCUS_REGEN_RATE * dt)

        elif self.skill == SKILL_EMP:
            if self.skill_cd > 0: self.skill_cd -= dt
            if skill_key and self.skill_cd <= 0:
                self.emp_triggered = True
                self.skill_cd      = EMP_COOLDOWN

        elif self.skill == SKILL_BLINK:
            if self.skill_cd > 0: self.skill_cd -= dt

        elif self.skill == SKILL_OVERCLOCK:
            if self.skill_cd > 0: self.skill_cd -= dt
            if self.is_overclocking:
                self.skill_t -= dt
                if self.skill_t <= 0: self.is_overclocking = False
            elif skill_key and self.skill_cd <= 0:
                self.is_overclocking = True
                self.skill_t  = OVERCLOCK_DURATION
                self.skill_cd = OVERCLOCK_CD

        elif self.skill == SKILL_SHIELD:
            if self.skill_cd > 0: self.skill_cd -= dt
            if self.is_shielding:
                self.skill_t -= dt
                if self.skill_t <= 0: self.is_shielding = False
            elif skill_key and self.skill_cd <= 0:
                self.is_shielding = True
                self.skill_t  = SHIELD_DURATION

        elif self.skill == SKILL_TIMEDILATION:
            if self.skill_cd > 0: self.skill_cd -= dt
            self._timedil_just_ended = False
            if self.is_timedilating:
                self.timedil_timer -= dt
                if self.timedil_timer <= 0:
                    self.is_timedilating = False
                    if self.skill_plus:
                        self._timedil_just_ended = True
            elif skill_key and self.skill_cd <= 0:
                self.is_timedilating = True
                self.timedil_timer   = TIMEDILATION_DURATION
                self.skill_cd        = TIMEDILATION_CD

        # EMP+: decair buff de dano
        if self._emp_buff_timer > 0:
            self._emp_buff_timer = max(0.0, self._emp_buff_timer - dt)
            if self._emp_buff_timer <= 0:
                self._emp_dmg_mult = 1.0

        self._blink_fired = False
        dx = dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:    dy -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dy += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:  dx -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx += 1.0
        if dx and dy: dx *= 0.7071; dy *= 0.7071
        if self.controls_inverted: dx = -dx; dy = -dy

        if self.skill == SKILL_BLINK and skill_key and self.skill_cd <= 0:
            self._blink_ox   = self.cx
            self._blink_oy   = self.cy
            self._blink_fired = True
            bx = (dx if dx or dy else 0.0) * BLINK_DIST
            by = (dy if dx or dy else -1.0) * BLINK_DIST
            self.x = max(self._arena_x0, min(self.x + bx, self._arena_x1))
            self.y = max(self._arena_y0, min(self.y + by, self._arena_y1))
            self.skill_cd = BLINK_COOLDOWN

        spd = PLAYER_SPEED * (DASH_MULT if self.is_dashing else 1.0)
        px_before = self.x;  py_before = self.y
        self.x += dx * spd * dt
        self.y += dy * spd * dt
        self.x = max(self._arena_x0, min(self.x, self._arena_x1))
        self.y = max(self._arena_y0, min(self.y, self._arena_y1))

        if dt > 0:
            self.vx = (self.x - px_before) / dt
            self.vy = (self.y - py_before) / dt

        if self.is_dashing:
            self.trail.append((self.cx, self.cy))
            self._trail_show = 0.12
        elif self._trail_show > 0.0:
            self._trail_show = max(0.0, self._trail_show - dt)

        if self.invuln > 0: self.invuln -= 1

    def try_absorb_hit(self) -> bool:
        """Returns True if the SHIELD skill absorbed the hit (no damage taken)."""
        if self.skill != SKILL_SHIELD or not self.is_shielding:
            return False
        # SHIELD+: perfect block = acerto nos primeiros 0.15s após ativação
        if self.skill_plus and self.skill_t > SHIELD_DURATION - 0.15:
            self._shield_perfect_acc += 1
        self.is_shielding = False
        self.skill_t  = 0.0
        self.skill_cd = SHIELD_CD
        if self.skill_plus:
            self.skill_cd = SHIELD_CD * SHIELD_PLUS_CD_FRAC   # 50% CD refund
            self._shield_broke = True                           # sinaliza emissão de ring
        return True


# ===========================================================================
# NullBoss — placeholder para Wave Survival (sem boss ativo na onda)
# ===========================================================================
class NullBoss:
    """Placeholder que não dispara, não toma dano e não aparece na tela."""
    BOSS_TYPE    = -1
    PATTERN_NAME = {}

    def __init__(self):
        self.hp          = self.max_hp = 999_999.0
        self.x           = float(SCREEN_W) / 2
        self.y           = float(SCREEN_H) / 2
        self.flash_frames = 0
        self.stun_timer   = 0.0
        self.pattern      = 0
        self.in_prep      = False
        self.phase_t      = 0.0

    def get_aabb_list(self):                                           return []
    def take_damage(self, *a):                                         pass
    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0): pass


# ===========================================================================
# Boss (Clássico)
# ===========================================================================
class Boss:
    SPREAD, RING, SPIRAL, SHARD, CIRCULAR, FRACTURE, BLASTER, LASER, STOP_AND_GO, BOOMERANG = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
    CYCLE     = [SPREAD, RING, SPIRAL, SPREAD, RING, SHARD, CIRCULAR, FRACTURE, BLASTER, LASER, STOP_AND_GO, BOOMERANG]
    DURATIONS = {SPREAD: 3.5, RING: 4.2, SPIRAL: 5.5, SHARD: 5.0,
                 CIRCULAR: 8.0, FRACTURE: 5.5, BLASTER: 7.0, LASER: 9.0,
                 STOP_AND_GO: 5.5, BOOMERANG: 5.5}
    PATTERN_COLOR = {SPREAD: RED_COL, RING: CYAN, SPIRAL: (80, 80, 255),
                     SHARD: (200, 255, 200), CIRCULAR: (255, 200, 80),
                     FRACTURE: CYAN, BLASTER: (255, 80, 60), LASER: (80, 180, 255),
                     STOP_AND_GO: (180, 80, 255), BOOMERANG: (255, 200, 80)}
    PATTERN_NAME  = {SPREAD: "SPREAD", RING: "RING", SPIRAL: "SPIRAL",
                     SHARD: "SHARDS", CIRCULAR: "CIRCULAR", FRACTURE: "FRACTURE",
                     BLASTER: "BLASTER", LASER: "LASER",
                     STOP_AND_GO: "STOP&GO", BOOMERANG: "BOOMERANG"}
    BOSS_TYPE = BOSS_CLASSIC

    def __init__(self, config: 'GameConfig' = None):
        if config is None: config = GameConfig()
        self.x, self.y = SCREEN_W / 2.0, SCREEN_H / 2.0
        self.size        = BOSS_SIZE
        self.hp = self.max_hp = config.boss_hp
        self.flash_frames = 0
        self.speed_mult   = config.speed_mult
        self.menu_diff    = config.diff
        self._runtime_cycle = self._build_cycle(config.diff)
        self._idx    = 0
        self.pattern   = self._runtime_cycle[0]
        self.in_prep   = True
        self.fake_prep = False
        self.phase_t   = 0.0
        self.fire_acc  = 0.0
        self.angle     = 0.0
        self.ring_fire_count = 0
        self.crack_indices:  list = []
        self.crack_released: bool = False
        self.crack_rotation: float = 0.0
        self.circ_arms_idx: list = [[], [], []]
        self.circ_angle:    float = 0.0
        self.circ_released: bool  = False
        self.frac_segments: list = []
        self.frac_released: bool = False
        self._laser_wave_horiz: bool = True
        self.stun_timer: float = 0.0
        self.mutators: frozenset = config.mutators if config else frozenset()
        self._init_movement()

    def get_aabb_list(self):
        h = self.size / 2.0
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def _build_cycle(self, diff: int) -> list:
        if diff == DIFF_EASY:
            return [self.SPREAD, self.RING, self.SPREAD, self.RING,
                    self.SPIRAL, self.SHARD, self.RING, self.SPREAD]
        elif diff == DIFF_HARD:
            base = [self.SPREAD, self.RING, self.SPIRAL, self.SPREAD]
            adv  = [self.RING, self.SHARD, self.CIRCULAR, self.FRACTURE, self.BLASTER, self.LASER,
                    self.STOP_AND_GO, self.BOOMERANG]
            random.shuffle(adv)
            return base + adv
        else:
            return list(self.CYCLE)

    def _init_movement(self):
        self._move_sx:  float = self.x
        self._move_sy:  float = self.y
        self._move_tx:  float = self.x
        self._move_ty:  float = self.y
        self._move_t:   float = 0.0
        self._move_dur: float = 0.0
        self._moving:   bool  = False
        self._wp_last:  int   = 0
        self.preview_aim: float = 0.0
        self.preview_gap: float = 0.0
        self._pick_and_go()

    def take_damage(self, n, diff: Difficulty):
        self.hp = max(0.0, self.hp - n)
        self.flash_frames = 8
        diff.update(self.hp, self.max_hp)

    def update(self, dt: float, pool: BulletPool, ep: EmitterPool, lp: LaserPool,
               px: float, py: float, diff: Difficulty,
               pvx: float = 0.0, pvy: float = 0.0):
        if self.hp <= 0: return
        if self.flash_frames > 0: self.flash_frames -= 1

        if self.stun_timer > 0:
            self.stun_timer -= dt
            self._move_update(dt)
            return

        self.phase_t += dt
        self._move_update(dt)

        aim_px = px + pvx * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else px
        aim_py = py + pvy * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else py
        aim_px = max(0.0, min(aim_px, SCREEN_W))
        aim_py = max(0.0, min(aim_py, SCREEN_H))

        to_player        = math.atan2(aim_py - self.y, aim_px - self.x)
        self.preview_aim = math.atan2(py - self.y, px - self.x)
        self.preview_gap = to_player + math.pi / 2

        _pt_scale = getattr(diff, 'prep_scale', 1.0)
        if self.in_prep:
            if self.fake_prep and self.phase_t >= PREP_TIME * 0.55 * _pt_scale:
                # Bait: corta o telegraph antes do fim e troca por SPREAD imediato
                self.fake_prep = False
                self.pattern   = self.SPREAD
                self.in_prep   = False
                self.phase_t   = 0.0
                self.fire_acc  = SPREAD_RATE
                self._pick_and_go()
            elif self.phase_t >= PREP_TIME * _pt_scale:
                self.in_prep  = False
                self.phase_t  = 0.0
                self.ring_fire_count = 0
                if self.pattern == self.SHARD:
                    self.crack_indices  = []
                    self.crack_released = False
                    self.crack_rotation = self.angle
                elif self.pattern == self.CIRCULAR:
                    self.circ_arms_idx  = [[], [], []]
                    self.circ_angle     = self.angle
                    self.circ_released  = False
                elif self.pattern == self.FRACTURE:
                    self.frac_segments  = []
                    self.frac_released  = False
                elif self.pattern == self.LASER:
                    self._laser_wave_horiz = True
                if self.pattern == self.SPREAD:
                    self.fire_acc = SPREAD_RATE
                elif self.pattern == self.RING:
                    self.fire_acc = RING_RATE
                elif self.pattern == self.BLASTER:
                    self.fire_acc = BLAST_WAVE_RATE
                elif self.pattern == self.LASER:
                    self.fire_acc = LASER_WAVE_RATE
                elif self.pattern == self.STOP_AND_GO:
                    self.fire_acc = max(SPREAD_RATE, TM_STOPGO_RATE)
                elif self.pattern == self.BOOMERANG:
                    self.fire_acc = TM_BOOM_RATE
                else:
                    self.fire_acc = 0.0
        else:
            self.fire_acc += dt
            if self.pattern == self.SPREAD:    self._do_spread(pool, aim_px, aim_py, diff)
            elif self.pattern == self.RING:    self._do_ring(pool, aim_px, aim_py, diff)
            elif self.pattern == self.SPIRAL:  self._do_spiral(pool, diff)
            elif self.pattern == self.SHARD:   self._do_shard(pool, diff)
            elif self.pattern == self.CIRCULAR: self._do_circ(pool)
            elif self.pattern == self.FRACTURE: self._do_fracture(pool)
            elif self.pattern == self.BLASTER:  self._do_blaster(ep, aim_px, aim_py)
            elif self.pattern == self.LASER:    self._do_laser(lp)
            elif self.pattern == self.STOP_AND_GO: self._do_stop_and_go(pool, aim_px, aim_py, diff, px, py)
            elif self.pattern == self.BOOMERANG:   self._do_boomerang(pool, aim_px, aim_py)

            if self.phase_t >= self.DURATIONS[self.pattern]:
                self._idx = (self._idx + 1) % len(self._runtime_cycle)
                if self._idx == 0 and self.menu_diff == DIFF_HARD:
                    base = [self.SPREAD, self.RING]
                    adv  = [self.SPIRAL, self.RING, self.SHARD, self.CIRCULAR,
                            self.FRACTURE, self.BLASTER, self.LASER,
                            self.STOP_AND_GO, self.BOOMERANG]
                    random.shuffle(adv)
                    self._runtime_cycle = base + adv
                self.pattern   = self._runtime_cycle[self._idx]
                self.in_prep   = True
                self.fake_prep = (self.pattern == self.LASER and random.random() < 0.30)
                self.phase_t   = 0.0
                self.fire_acc  = 0.0
                self._pick_and_go()

    def _do_spread(self, pool, px, py, diff):
        while self.fire_acc >= SPREAD_RATE:
            self.fire_acc -= SPREAD_RATE
            n, cone = diff.spread_params()
            aim  = math.atan2(py - self.y, px - self.x)
            half = cone / 2
            for i in range(n):
                t     = i / (n - 1)
                theta = aim - half + t * cone
                idx   = pool.acquire()
                if idx < 0: return
                pool.bx[idx] = self.x; pool.by[idx] = self.y
                pool.bvx[idx] = math.cos(theta) * SPREAD_SPEED * self.speed_mult
                pool.bvy[idx] = math.sin(theta) * SPREAD_SPEED * self.speed_mult

    def _do_ring(self, pool, px, py, diff):
        while self.fire_acc >= RING_RATE:
            self.fire_acc -= RING_RATE
            dx   = px - self.x;  dy = py - self.y
            dist = math.sqrt(dx*dx + dy*dy)
            n, gap_rad, speed = diff.ring_params(dist)
            to_player  = math.atan2(dy, dx)
            gap_center = to_player + math.pi / 2 + self.ring_fire_count * (math.pi / 3)
            half_gap   = gap_rad / 2
            sep        = TWO_PI / n
            for i in range(n):
                angle = i * sep
                delta = abs(((angle - gap_center + math.pi) % TWO_PI) - math.pi)
                if delta <= half_gap: continue
                idx = pool.acquire()
                if idx < 0: return
                pool.bx[idx] = self.x; pool.by[idx] = self.y
                pool.bvx[idx] = math.cos(angle) * speed * self.speed_mult
                pool.bvy[idx] = math.sin(angle) * speed * self.speed_mult
            self.ring_fire_count += 1

    def _do_spiral(self, pool, diff):
        arms, step = diff.spiral_params()
        sep = TWO_PI / arms
        while self.fire_acc >= SPIRAL_RATE:
            self.fire_acc -= SPIRAL_RATE
            for a in range(arms):
                idx = pool.acquire()
                if idx < 0: return
                theta = self.angle + a * sep
                pool.bx[idx] = self.x; pool.by[idx] = self.y
                pool.bvx[idx] = math.cos(theta) * SPIRAL_SPEED * self.speed_mult
                pool.bvy[idx] = math.sin(theta) * SPIRAL_SPEED * self.speed_mult
            self.angle = (self.angle + step) % TWO_PI

    def _do_shard(self, pool, diff):
        if not self.crack_indices:
            self._spawn_crack_formation(pool, diff)
        if not self.crack_released and self.phase_t >= CRACK_FORM_TIME:
            self._release_cracks(pool, diff)

    def _spawn_crack_formation(self, pool, diff):
        n_cracks = 13 + diff.tier
        for i in range(min(n_cracks, len(CRACK_BASE))):
            theta  = CRACK_BASE[i] + self.crack_rotation
            b1, b2 = CRACK_BENDS[i]
            rx = ry = 0.0
            for j, step in enumerate(CRACK_STEPS):
                if j < CRACK_SEG1:    seg_theta = theta
                elif j < CRACK_SEG2:  seg_theta = theta + b1
                else:                 seg_theta = theta + b1 + b2
                rx += math.cos(seg_theta) * step
                ry += math.sin(seg_theta) * step
                idx = pool.acquire()
                if idx < 0: return
                self.crack_indices.append(idx)
                pool.bx[idx]  = self.x + rx
                pool.by[idx]  = self.y + ry
                mag = math.sqrt(rx * rx + ry * ry)
                if mag > 0.1:
                    pool.bvx[idx] = (rx / mag) * CRACK_HOLD_SPEED
                    pool.bvy[idx] = (ry / mag) * CRACK_HOLD_SPEED

    def _release_cracks(self, pool, diff):
        self.crack_released = True
        speed = (CRACK_FLY_SPEED + (diff.tier - 1) * 20.0) * self.speed_mult
        for idx in self.crack_indices:
            if not pool.active[idx]: continue
            pool.bvx[idx] = 0.0
            pool.bvy[idx] = speed

    def _do_circ(self, pool):
        if self.circ_released: return
        curr_angle = self.circ_angle - CIRC_SPIN_SPEED * self.phase_t
        grow_rate  = CIRC_MAX_STEPS * CIRC_STEP_SIZE / CIRC_FORM_TIME
        curr_len   = grow_rate * min(self.phase_t, CIRC_FORM_TIME)
        n_target   = min(int(curr_len / CIRC_STEP_SIZE), CIRC_MAX_STEPS)
        sep = TWO_PI / CIRC_ARMS
        for arm in range(CIRC_ARMS):
            arm_angle = curr_angle + arm * sep
            cs, sn    = math.cos(arm_angle), math.sin(arm_angle)
            while len(self.circ_arms_idx[arm]) < n_target:
                j   = len(self.circ_arms_idx[arm])
                r   = (j + 1) * CIRC_STEP_SIZE
                idx = pool.acquire()
                if idx < 0: break
                pool.bx[idx]  = self.x + cs * r
                pool.by[idx]  = self.y + sn * r
                pool.bvx[idx] = 0.0
                pool.bvy[idx] = 0.0
                self.circ_arms_idx[arm].append(idx)
        if self.phase_t >= CIRC_FORM_TIME:
            self._release_circ(pool)

    def _release_circ(self, pool):
        self.circ_released = True
        for arm_list in self.circ_arms_idx:
            for idx in arm_list:
                if not pool.active[idx]: continue
                dx  = pool.bx[idx] - self.x
                dy  = pool.by[idx] - self.y
                mag = math.sqrt(dx * dx + dy * dy)
                if mag < 0.1: continue
                pool.bvx[idx] = -(dx / mag) * CIRC_FLY_SPEED * self.speed_mult
                pool.bvy[idx] = -(dy / mag) * CIRC_FLY_SPEED * self.speed_mult

    def _do_fracture(self, pool):
        if not self.frac_segments:
            self._spawn_fracture(pool)
        if not self.frac_released and self.phase_t >= FRAC_FORM_TIME:
            self._release_fracture(pool)

    def _spawn_fracture(self, pool):
        cx = SCREEN_W / 2.0;  cy = SCREEN_H / 2.0
        cc = math.cos(FRAC_CUT_ANGLE);  cs = math.sin(FRAC_CUT_ANGLE)

        def spawn(x, y, ux, uy):
            idx = pool.acquire()
            if idx < 0: return False
            pool.bx[idx]  = x;  pool.by[idx]  = y
            pool.bvx[idx] = ux * FRAC_HOLD_SPEED
            pool.bvy[idx] = uy * FRAC_HOLD_SPEED
            self.frac_segments.append((idx, ux, uy))
            return True

        n_half = int(FRAC_CUT_HALF / FRAC_STEP_SIZE)
        for k in range(-n_half, n_half + 1):
            s    = k * FRAC_STEP_SIZE
            sign = 1 if k >= 0 else -1
            if not spawn(cx + cc * s, cy + cs * s, cc * sign, cs * sign): return

        for (cut_s, trunk_ang, trunk_n, branches) in FRAC_TREES:
            ox = cx + cc * cut_s;  oy = cy + cs * cut_s
            tc = math.cos(trunk_ang);  ts = math.sin(trunk_ang)
            for j in range(1, trunk_n + 1):
                r = j * FRAC_STEP_SIZE
                if not spawn(ox + tc * r, oy + ts * r, tc, ts): return
            bx_o = ox + tc * trunk_n * FRAC_STEP_SIZE
            by_o = oy + ts * trunk_n * FRAC_STEP_SIZE
            for (rel_a, n_b) in branches:
                ba = trunk_ang + rel_a
                bc = math.cos(ba);  bs = math.sin(ba)
                for j in range(1, n_b + 1):
                    r = j * FRAC_STEP_SIZE
                    if not spawn(bx_o + bc * r, by_o + bs * r, bc, bs): return

    def _release_fracture(self, pool):
        self.frac_released = True
        for idx, ux, uy in self.frac_segments:
            if not pool.active[idx]: continue
            pool.bvx[idx] = ux * FRAC_FLY_SPEED * self.speed_mult
            pool.bvy[idx] = uy * FRAC_FLY_SPEED * self.speed_mult

    def _pick_and_go(self):
        candidates = [i for i in range(len(BOSS_WAYPOINTS)) if i != self._wp_last]
        self._wp_last  = random.choice(candidates)
        self._move_sx  = self.x;  self._move_sy = self.y
        self._move_tx  = BOSS_WAYPOINTS[self._wp_last][0] * SCREEN_W
        self._move_ty  = BOSS_WAYPOINTS[self._wp_last][1] * SCREEN_H
        self._move_t   = 0.0
        self._move_dur = PREP_TIME * 0.92
        self._moving   = True

    def _move_update(self, dt: float):
        if not self._moving or not self.in_prep: return
        self._move_t = min(self._move_t + dt, self._move_dur)
        frac = self._move_t / self._move_dur
        t    = frac * frac * (3.0 - 2.0 * frac)
        self.x = self._move_sx + (self._move_tx - self._move_sx) * t
        self.y = self._move_sy + (self._move_ty - self._move_sy) * t
        if self._move_t >= self._move_dur:
            self.x, self.y = self._move_tx, self._move_ty
            self._moving   = False

    def _do_blaster(self, ep, px, py):
        while self.fire_acc >= BLAST_WAVE_RATE:
            self.fire_acc -= BLAST_WAVE_RATE
            self._spawn_blaster_wave(ep, px, py)

    def _spawn_blaster_wave(self, ep, px, py):
        for _ in range(BLAST_PER_WAVE):
            ex, ey = self._random_edge_pos()
            angle  = math.atan2(py - ey, px - ex)
            idx    = ep.acquire()
            if idx < 0: return
            ep.ex[idx]    = ex;  ep.ey[idx]    = ey
            ep.angle[idx] = angle
            ep.timer[idx]  = BLAST_TELEGRAPH
            ep.espeed[idx] = BLAST_SPEED * self.speed_mult

    @staticmethod
    def _random_edge_pos() -> tuple:
        edge = random.randint(0, 3)
        M    = 60.0
        if edge == 0:   return random.uniform(M, SCREEN_W - M), 0.0
        elif edge == 1: return random.uniform(M, SCREEN_W - M), float(SCREEN_H)
        elif edge == 2: return 0.0, random.uniform(M, SCREEN_H - M)
        else:           return float(SCREEN_W), random.uniform(M, SCREEN_H - M)

    def _do_laser(self, lp):
        while self.fire_acc >= LASER_WAVE_RATE:
            self.fire_acc -= LASER_WAVE_RATE
            self._spawn_laser_wave(lp)

    def _spawn_laser_wave(self, lp):
        horiz = self._laser_wave_horiz
        self._laser_wave_horiz = not horiz
        if horiz:
            positions = self._pick_laser_positions(LASER_N_LINES, 80.0, SCREEN_H - 80.0, LASER_MIN_SEP_H)
            for p in positions: lp.acquire(p, True)
        else:
            positions = self._pick_laser_positions(LASER_N_LINES, 80.0, SCREEN_W - 80.0, LASER_MIN_SEP_V)
            for p in positions: lp.acquire(p, False)

    @staticmethod
    def _pick_laser_positions(n, lo, hi, min_sep) -> list:
        positions: list = []
        for _ in range(n):
            for _ in range(60):
                p = random.uniform(lo, hi)
                if all(abs(p - q) >= min_sep for q in positions):
                    positions.append(p)
                    break
        return positions

    def _do_stop_and_go(self, pool, px, py, diff, real_px, real_py):
        while self.fire_acc >= TM_STOPGO_RATE:
            self.fire_acc -= TM_STOPGO_RATE
            n, cone = diff.spread_params()
            aim  = math.atan2(py - self.y, px - self.x)
            half = cone / 2
            for i in range(n):
                t     = i / max(n - 1, 1)
                theta = aim - half + t * cone
                idx   = pool.acquire()
                if idx < 0: return
                pool.bx[idx]     = self.x;  pool.by[idx]     = self.y
                pool.bvx[idx]    = math.cos(theta) * SPREAD_SPEED * self.speed_mult
                pool.bvy[idx]    = math.sin(theta) * SPREAD_SPEED * self.speed_mult
                pool.bstate[idx] = BSTOP_PENDING
                pool.btimer[idx] = STOPGO_TRAVEL_TIME
                pool.btgt_x[idx] = real_px
                pool.btgt_y[idx] = real_py

    def _do_boomerang(self, pool, px, py):
        while self.fire_acc >= TM_BOOM_RATE:
            self.fire_acc -= TM_BOOM_RATE
            away = math.atan2(self.y - py, self.x - px)
            sep  = TWO_PI / TM_BOOM_N
            for i in range(TM_BOOM_N):
                theta = away + i * sep
                idx   = pool.acquire()
                if idx < 0: return
                pool.bx[idx]     = self.x;  pool.by[idx]     = self.y
                pool.bvx[idx]    = math.cos(theta) * TM_BOOM_SPEED * self.speed_mult
                pool.bvy[idx]    = math.sin(theta) * TM_BOOM_SPEED * self.speed_mult
                pool.bstate[idx] = BBOOM_PENDING
                pool.btimer[idx] = TM_BOOM_REVERSE_TIME


# ===========================================================================
# SwarmBoss — 3 unidades compartilhando HP, formação triangular orbitando
# ===========================================================================
class SwarmBoss:
    CROSSFIRE, RING_VOLLEY, LASER_GRID = 0, 1, 2
    _CYCLE = [CROSSFIRE, RING_VOLLEY, CROSSFIRE, LASER_GRID]
    _DURATIONS = {0: 4.5, 1: 5.5, 2: 7.5}
    PATTERN_COLOR = {0: RED_COL, 1: CYAN, 2: (80, 180, 255)}
    PATTERN_NAME  = {0: "CROSSFIRE", 1: "RING VOLLEY", 2: "LASER GRID"}
    BOSS_TYPE = BOSS_SWARM

    def __init__(self, config: 'GameConfig' = None):
        if config is None: config = GameConfig()
        self.cx = SCREEN_W / 2.0   # centro da formação
        self.cy = SCREEN_H * 0.25
        self.orbit_angle = 0.0
        self.hp = self.max_hp = config.boss_hp
        self.flash_frames = 0
        self.speed_mult = config.speed_mult
        self.mutators = config.mutators if config else frozenset()
        self.size = SWARM_UNIT_SIZE  # compat

        self.unit_x = np.zeros(3, dtype=np.float32)
        self.unit_y = np.zeros(3, dtype=np.float32)
        self._update_units()

        self._idx = 0
        self.pattern = self._CYCLE[0]
        self.in_prep = True
        self.phase_t = 0.0
        self.fire_acc = 0.0
        self.ring_fire_count = 0
        self.stun_timer = 0.0
        self.preview_aim = 0.0
        self.preview_gap = 0.0

        self._move_sx = self.cx;  self._move_sy = self.cy
        self._move_tx = self.cx;  self._move_ty = self.cy
        self._move_t = 0.0;  self._move_dur = 1.0
        self._moving = False;  self._wp_last = 0
        self._pick_and_go()

    # compat properties for HP bar and collision
    @property
    def x(self): return self.cx
    @property
    def y(self): return self.cy

    def get_aabb_list(self):
        h = SWARM_UNIT_SIZE / 2.0
        return [(float(self.unit_x[i]) - h, float(self.unit_y[i]) - h,
                 float(self.unit_x[i]) + h, float(self.unit_y[i]) + h)
                for i in range(3)]

    def _update_units(self):
        sep = TWO_PI / 3
        for i in range(3):
            a = self.orbit_angle + i * sep
            self.unit_x[i] = self.cx + math.cos(a) * SWARM_ORBIT_RADIUS
            self.unit_y[i] = self.cy + math.sin(a) * SWARM_ORBIT_RADIUS

    def _pick_and_go(self):
        candidates = [i for i in range(len(SWARM_WAYPOINTS)) if i != self._wp_last]
        self._wp_last = random.choice(candidates)
        self._move_sx = self.cx;  self._move_sy = self.cy
        self._move_tx = SWARM_WAYPOINTS[self._wp_last][0] * SCREEN_W
        self._move_ty = SWARM_WAYPOINTS[self._wp_last][1] * SCREEN_H
        self._move_t = 0.0
        self._move_dur = PREP_TIME * 0.92
        self._moving = True

    def _move_update(self, dt):
        if not self._moving or not self.in_prep: return
        self._move_t = min(self._move_t + dt, self._move_dur)
        frac = self._move_t / self._move_dur
        t    = frac * frac * (3.0 - 2.0 * frac)
        self.cx = self._move_sx + (self._move_tx - self._move_sx) * t
        self.cy = self._move_sy + (self._move_ty - self._move_sy) * t
        if self._move_t >= self._move_dur:
            self.cx, self.cy = self._move_tx, self._move_ty
            self._moving = False

    def take_damage(self, n, diff: Difficulty):
        self.hp = max(0.0, self.hp - n)
        self.flash_frames = 8
        diff.update(self.hp, self.max_hp)

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.flash_frames > 0: self.flash_frames -= 1

        self.orbit_angle = (self.orbit_angle + SWARM_ORBIT_SPEED * dt) % TWO_PI
        self._move_update(dt)
        self._update_units()

        if self.stun_timer > 0:
            self.stun_timer -= dt
            return

        aim_px = px + pvx * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else px
        aim_py = py + pvy * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else py
        aim_px = max(0.0, min(aim_px, SCREEN_W))
        aim_py = max(0.0, min(aim_py, SCREEN_H))
        self.preview_aim = math.atan2(py - self.cy, px - self.cx)
        self.preview_gap = self.preview_aim + math.pi / 2

        self.phase_t += dt

        if self.in_prep:
            if self.phase_t >= PREP_TIME:
                self.in_prep = False
                self.phase_t = 0.0
                self.ring_fire_count = 0
                self.fire_acc = SWARM_CROSSFIRE_RATE
        else:
            self.fire_acc += dt
            if self.pattern == self.CROSSFIRE:
                self._do_crossfire(pool, aim_px, aim_py, diff)
            elif self.pattern == self.RING_VOLLEY:
                self._do_ring_volley(pool, aim_px, aim_py, diff)
            elif self.pattern == self.LASER_GRID:
                self._do_laser_grid(lp)

            dur = self._DURATIONS.get(self.pattern, 5.0)
            if self.phase_t >= dur:
                self._idx = (self._idx + 1) % len(self._CYCLE)
                self.pattern = self._CYCLE[self._idx]
                self.in_prep = True
                self.phase_t = 0.0
                self.fire_acc = 0.0
                self._pick_and_go()

    def _do_crossfire(self, pool, px, py, diff):
        while self.fire_acc >= SWARM_CROSSFIRE_RATE:
            self.fire_acc -= SWARM_CROSSFIRE_RATE
            n, cone = diff.spread_params()
            for u in range(3):
                ux, uy = float(self.unit_x[u]), float(self.unit_y[u])
                aim  = math.atan2(py - uy, px - ux)
                half = cone / 2
                for i in range(n):
                    t     = i / max(n - 1, 1)
                    theta = aim - half + t * cone
                    idx   = pool.acquire()
                    if idx < 0: return
                    pool.bx[idx] = ux;  pool.by[idx] = uy
                    pool.bvx[idx] = math.cos(theta) * SPREAD_SPEED * self.speed_mult
                    pool.bvy[idx] = math.sin(theta) * SPREAD_SPEED * self.speed_mult

    def _do_ring_volley(self, pool, px, py, diff):
        while self.fire_acc >= RING_RATE:
            self.fire_acc -= RING_RATE
            u  = self.ring_fire_count % 3
            ux = float(self.unit_x[u]);  uy = float(self.unit_y[u])
            dx = px - ux;  dy = py - uy
            dist = math.sqrt(dx*dx + dy*dy)
            n, gap_rad, speed = diff.ring_params(dist)
            to_player  = math.atan2(dy, dx)
            gap_center = to_player + math.pi / 2 + self.ring_fire_count * (math.pi / 3)
            half_gap   = gap_rad / 2
            sep        = TWO_PI / n
            for i in range(n):
                angle = i * sep
                delta = abs(((angle - gap_center + math.pi) % TWO_PI) - math.pi)
                if delta <= half_gap: continue
                idx = pool.acquire()
                if idx < 0: return
                pool.bx[idx] = ux;  pool.by[idx] = uy
                pool.bvx[idx] = math.cos(angle) * speed * self.speed_mult
                pool.bvy[idx] = math.sin(angle) * speed * self.speed_mult
            self.ring_fire_count += 1

    def _do_laser_grid(self, lp):
        while self.fire_acc >= LASER_WAVE_RATE:
            self.fire_acc -= LASER_WAVE_RATE
            for u in range(3):
                if u < 2:
                    pos = float(self.unit_y[u])
                    lp.acquire(max(80.0, min(pos, SCREEN_H - 80.0)), True)
                else:
                    pos = float(self.unit_x[u])
                    lp.acquire(max(80.0, min(pos, SCREEN_W - 80.0)), False)


# ===========================================================================
# WallBoss — barra horizontal que desce do topo, chuva + pilar
# ===========================================================================
class WallBoss:
    RAIN, PILLAR = 0, 1
    _CYCLE = [RAIN, PILLAR, RAIN, PILLAR, RAIN]
    _DURATIONS = {RAIN: 4.5, PILLAR: 5.5}
    PATTERN_COLOR = {RAIN: (80, 150, 255), PILLAR: (255, 120, 60)}
    PATTERN_NAME  = {RAIN: "RAIN", PILLAR: "PILLAR"}
    BOSS_TYPE = BOSS_WALL

    def __init__(self, config: 'GameConfig' = None):
        if config is None: config = GameConfig()
        self.wall_width  = float(SCREEN_W)
        self.wall_height = float(WALL_HEIGHT)
        self.y    = -self.wall_height - 10.0   # acima da tela
        self.hp   = self.max_hp = config.boss_hp
        self.flash_frames = 0
        self.speed_mult = config.speed_mult
        self.mutators   = config.mutators if config else frozenset()
        self.size = WALL_HEIGHT  # compat

        # Canhões ao longo da largura
        self._cannon_xs: list = []
        cx = WALL_CANNON_SEP / 2.0
        while cx < SCREEN_W:
            self._cannon_xs.append(cx)
            cx += WALL_CANNON_SEP

        # Vida por canhão + fúria
        _n = len(self._cannon_xs)
        _hp_each = float(config.boss_hp) / max(1, _n)
        self.cannon_hp    = np.full(_n, _hp_each, dtype=np.float32)
        self.cannon_alive = np.ones(_n, dtype=np.bool_)
        self._rage_mult   = 1.0   # aumenta a cada canhão destruído

        self.stun_timer = 0.0
        self._idx = 0
        self.pattern = self.RAIN
        self.in_prep = True
        self.phase_t = 0.0
        self.fire_acc = 0.0
        self._runtime_cycle = list(self._CYCLE)
        self._rain_gap_set: set = set()
        self._pillar_x: float = SCREEN_W / 2.0
        self.preview_aim = 0.0
        self.preview_gap = 0.0

    # compat
    @property
    def x(self): return SCREEN_W / 2.0

    def get_aabb_list(self):
        return [(0.0, self.y, float(SCREEN_W), self.y + self.wall_height)]

    def take_damage(self, n, diff: Difficulty):
        self.hp = max(0.0, self.hp - n)
        self.flash_frames = 8
        diff.update(self.hp, self.max_hp)
        # Distribui dano para um canhão vivo aleatório (e.g. parry, dano global)
        alive_i = np.where(self.cannon_alive)[0]
        if alive_i.size > 0:
            ci = int(alive_i[random.randrange(len(alive_i))])
            self.cannon_hp[ci] = max(0.0, self.cannon_hp[ci] - n)
            if self.cannon_hp[ci] <= 0:
                self.cannon_alive[ci] = False
                self._rage_mult = 1.0 + float(np.sum(~self.cannon_alive)) * 0.3

    def take_damage_at_x(self, bx: float, n: float, diff: Difficulty):
        """Roteia dano para o canhão mais próximo de bx (player bullet x-routing)."""
        self.hp = max(0.0, self.hp - n)
        self.flash_frames = 8
        diff.update(self.hp, self.max_hp)
        alive_i = np.where(self.cannon_alive)[0]
        if alive_i.size == 0: return
        xs = np.array([self._cannon_xs[int(i)] for i in alive_i], dtype=np.float32)
        nearest = int(alive_i[int(np.argmin(np.abs(xs - bx)))])
        self.cannon_hp[nearest] = max(0.0, self.cannon_hp[nearest] - n)
        if self.cannon_hp[nearest] <= 0:
            self.cannon_alive[nearest] = False
            self._rage_mult = 1.0 + float(np.sum(~self.cannon_alive)) * 0.3

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.flash_frames > 0: self.flash_frames -= 1

        # Desce até a posição de ataque
        if self.y < WALL_MAX_DESCENT:
            self.y = min(self.y + WALL_DESCENT_SPEED * dt, float(WALL_MAX_DESCENT))
            return

        if self.stun_timer > 0:
            self.stun_timer -= dt
            return

        aim_px = px + pvx * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else px
        aim_py = py + pvy * PREDICT_AIM_TIME if MUTATOR_PREDATOR in self.mutators else py
        aim_px = max(0.0, min(aim_px, SCREEN_W))
        self.preview_aim = math.atan2(py - (self.y + self.wall_height / 2), px - SCREEN_W / 2)
        self.preview_gap = self.preview_aim + math.pi / 2

        self.phase_t += dt

        if self.in_prep:
            if self.phase_t >= PREP_TIME:
                self.in_prep = False
                self.phase_t = 0.0
                if self.pattern == self.RAIN:
                    n_gap = max(1, len(self._cannon_xs) // 3)
                    self._rain_gap_set = set(random.sample(range(len(self._cannon_xs)), n_gap))
                    self.fire_acc = WALL_RAIN_RATE
                elif self.pattern == self.PILLAR:
                    self._pillar_x = aim_px
                    self.fire_acc = WALL_PILLAR_RATE
        else:
            self.fire_acc += dt
            if self.pattern == self.RAIN:
                self._do_rain(pool)
            elif self.pattern == self.PILLAR:
                self._do_pillar(pool, aim_px)

            dur = self._DURATIONS.get(self.pattern, 4.5)
            if self.phase_t >= dur:
                self._idx = (self._idx + 1) % len(self._runtime_cycle)
                self.pattern = self._runtime_cycle[self._idx]
                self.in_prep = True
                self.phase_t = 0.0
                self.fire_acc = 0.0

    def _do_rain(self, pool):
        while self.fire_acc >= WALL_RAIN_RATE:
            self.fire_acc -= WALL_RAIN_RATE
            cannon_y = self.y + self.wall_height
            for i, cx in enumerate(self._cannon_xs):
                if i in self._rain_gap_set: continue
                if not self.cannon_alive[i]: continue  # canhão destruído — não dispara
                idx = pool.acquire()
                if idx < 0: return
                pool.bx[idx] = cx
                pool.by[idx] = cannon_y
                pool.bvx[idx] = random.uniform(-18.0, 18.0)
                pool.bvy[idx] = WALL_RAIN_SPEED * self.speed_mult * self._rage_mult

    def _do_pillar(self, pool, px):
        while self.fire_acc >= WALL_PILLAR_RATE:
            self.fire_acc -= WALL_PILLAR_RATE
            self._pillar_x += (px - self._pillar_x) * 0.08
            self._pillar_x = max(20.0, min(self._pillar_x, SCREEN_W - 20.0))
            idx = pool.acquire()
            if idx < 0: return
            pool.bx[idx] = self._pillar_x
            pool.by[idx] = self.y + self.wall_height
            pool.bvx[idx] = 0.0
            pool.bvy[idx] = WALL_PILLAR_SPEED * self.speed_mult * self._rage_mult


# ===========================================================================
# Collision helpers (usam get_aabb_list — funciona com todos os boss types)
# ===========================================================================
def check_boss_collision(pb: PlayerBulletPool, boss, diff: Difficulty,
                         glass_cannon: bool = False, dmg_mult: float = 1.0) -> int:
    if boss.hp <= 0: return 0
    if getattr(boss, 'invulnerable', False): return 0
    mult = (3.0 if glass_cannon else 1.0) * dmg_mult
    # Reset hit buffer for CARREGADO+ shrapnel spawning
    pb._hit_buf_n = 0
    # Piercing bullets on cooldown are skipped — do not apply effective_m globally here
    # because WallBoss/TwinsBoss handle hit detection differently per-bullet.

    # WallBoss: dano roteado para o canhão mais próximo do bullet.px
    if isinstance(boss, WallBoss):
        total_hits = 0
        x0, y0, x1, y1 = 0.0, boss.y, float(SCREEN_W), boss.y + boss.wall_height
        _plasma_excl = (pb.pb_type == PB_PLASMA) | (pb.pb_type == PB_PLASMA_PUDDLE)
        mask = pb.active & ~_plasma_excl & (pb.px >= x0) & (pb.px <= x1) & (pb.py >= y0) & (pb.py <= y1)
        for pidx in np.where(mask)[0]:
            pidx = int(pidx)
            if not pb.active[pidx]: continue
            if pb.pb_pierce[pidx] and pb.pb_timer[pidx] > 0.0: continue  # pierce cooldown
            boss.take_damage_at_x(float(pb.px[pidx]), float(pb.damage[pidx]) * mult, diff)
            if pb.pb_pierce[pidx]:
                pb.pb_timer[pidx] = NEEDLE_PLUS_PIERCE_CD
            else:
                if pb.pb_state[pidx] == 2 and pb._hit_buf_n < 16:  # CARREGADO+
                    pb._hit_buf[pb._hit_buf_n, 0] = pb.px[pidx]
                    pb._hit_buf[pb._hit_buf_n, 1] = pb.py[pidx]
                    pb._hit_buf_n += 1
                pb.release(pidx)
            total_hits += 1
        return total_hits

    # TwinsBoss: dano por AABB (um gemêo por vez)
    if isinstance(boss, TwinsBoss):
        total_hits = 0
        _plasma_excl = (pb.pb_type == PB_PLASMA) | (pb.pb_type == PB_PLASMA_PUDDLE)
        for aabb_idx, (x0, y0, x1, y1) in enumerate(boss.get_aabb_list()):
            mask = pb.active & ~_plasma_excl & (pb.px >= x0) & (pb.px <= x1) & (pb.py >= y0) & (pb.py <= y1)
            hits = [int(i) for i in np.where(mask)[0]
                    if pb.active[i] and not (pb.pb_pierce[i] and pb.pb_timer[i] > 0.0)]
            if not hits: continue
            pierce_h = [i for i in hits if pb.pb_pierce[i]]
            normal_h = [i for i in hits if not pb.pb_pierce[i]]
            dmg = float(sum(pb.damage[i] for i in hits)) * mult
            boss.take_damage_targeted(dmg, aabb_idx, diff)
            for idx in pierce_h:
                pb.pb_timer[idx] = NEEDLE_PLUS_PIERCE_CD
            for idx in normal_h:
                if pb.pb_state[idx] == 2 and pb._hit_buf_n < 16:  # CARREGADO+
                    pb._hit_buf[pb._hit_buf_n, 0] = pb.px[idx]
                    pb._hit_buf[pb._hit_buf_n, 1] = pb.py[idx]
                    pb._hit_buf_n += 1
                pb.release(idx)
            total_hits += len(hits)
        return total_hits

    # Caminho padrão (todos os outros bosses)
    _plasma_excl = (pb.pb_type == PB_PLASMA) | (pb.pb_type == PB_PLASMA_PUDDLE)
    hit_set: set = set()
    for (x0, y0, x1, y1) in boss.get_aabb_list():
        mask = pb.active & ~_plasma_excl & (pb.px >= x0) & (pb.px <= x1) & (pb.py >= y0) & (pb.py <= y1)
        for idx in np.where(mask)[0]:
            if not (pb.pb_pierce[idx] and pb.pb_timer[idx] > 0.0):
                hit_set.add(int(idx))
    if not hit_set: return 0
    hit_list = [i for i in hit_set if pb.active[i]]
    if not hit_list: return 0
    pierce_hits = [i for i in hit_list if pb.pb_pierce[i]]
    normal_hits = [i for i in hit_list if not pb.pb_pierce[i]]
    all_dmg = float(sum(pb.damage[i] for i in hit_list)) * mult
    boss.take_damage(all_dmg, diff)
    for idx in pierce_hits:
        pb.pb_timer[idx] = NEEDLE_PLUS_PIERCE_CD
    for idx in normal_hits:
        if pb.pb_state[idx] == 2 and pb._hit_buf_n < 16:  # CARREGADO+
            pb._hit_buf[pb._hit_buf_n, 0] = pb.px[idx]
            pb._hit_buf[pb._hit_buf_n, 1] = pb.py[idx]
            pb._hit_buf_n += 1
        pb.release(idx)
    return len(hit_list)


def check_parried_boss_collision(pool: BulletPool, boss, diff: Difficulty,
                                 glass_cannon: bool = False) -> int:
    if boss.hp <= 0: return 0
    mask = pool.active & pool.parried
    idxs = np.where(mask)[0]
    if not len(idxs): return 0
    hit_set: set = set()
    for (x0, y0, x1, y1) in boss.get_aabb_list():
        hm = ((pool.bx[idxs] >= x0) & (pool.bx[idxs] <= x1) &
              (pool.by[idxs] >= y0) & (pool.by[idxs] <= y1))
        for idx in idxs[hm]:
            hit_set.add(int(idx))
    if not hit_set: return 0
    hit_list = [i for i in hit_set if pool.active[i]]
    if not hit_list: return 0
    dmg = float(len(hit_list)) * (3.0 if glass_cannon else 1.0)
    boss.take_damage(dmg, diff)
    for idx in hit_list:
        pool.release(idx)
    return len(hit_list)


def check_plasma_boss_collision(pb: PlayerBulletPool, boss, diff: 'Difficulty',
                                glass_cannon: bool = False, dt: float = 0.0167) -> int:
    """PLASMA e PLASMA+: aplica DPS por frame sem liberar as balas.
    Poças (PB_PLASMA_PUDDLE) aplicam DPS reduzido.
    Retorna 1 se algum plasma está em contato, 0 caso contrário."""
    if boss.hp <= 0: return 0
    mult = 3.0 if glass_cannon else 1.0
    total_hit = 0
    plasma_m  = pb.active & (pb.pb_type == PB_PLASMA)
    puddle_m  = pb.active & (pb.pb_type == PB_PLASMA_PUDDLE)
    has_beam   = plasma_m.any()
    has_puddle = puddle_m.any()
    if not has_beam and not has_puddle: return 0
    for (x0, y0, x1, y1) in boss.get_aabb_list():
        if has_beam:
            hit_m = plasma_m & (pb.px >= x0) & (pb.px <= x1) & (pb.py >= y0) & (pb.py <= y1)
            cnt = int(hit_m.sum())
            if cnt > 0:
                boss.take_damage(PLASMA_DPS * cnt * dt * mult, diff)
                total_hit += cnt
        if has_puddle:
            phit_m = puddle_m & (pb.px >= x0) & (pb.px <= x1) & (pb.py >= y0) & (pb.py <= y1)
            pcnt = int(phit_m.sum())
            if pcnt > 0:
                boss.take_damage(PLASMA_PLUS_PUDDLE_DPS * pcnt * dt * mult, diff)
                total_hit += pcnt
    return 1 if total_hit > 0 else 0


# ===========================================================================
# ReplayRecorder — replay determinístico por seed + bitmask de inputs
# ===========================================================================
# Bitmask para 8 teclas de jogo (bits 0-7)
_KEY_BITS = [
    pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d,
    pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
]
_SKILL_BIT  = 8    # bit 8 = skill key (shift)
_FIRE_BIT   = 9    # bit 9 = fire (space/z)


# ===========================================================================
# OmegaBoss — Boss secreto com 4 fases (usa sub-bosses via composição)
# ===========================================================================
class OmegaBoss:
    """Secret boss: 4 phases cycling through all boss types.
    Phase order: WallBoss → SwarmBoss → Boss (Classic) → Boss (Classic, max speed).
    HP is shared across all phases (25% per phase). Teleports in non-wall phases."""
    BOSS_TYPE = BOSS_OMEGA
    _PHASE_CLS  = None   # filled after class definition
    _PHASE_TYPE = [BOSS_WALL, BOSS_SWARM, BOSS_CLASSIC, BOSS_CLASSIC]
    PHASE_NAMES  = ["FASE 1: MURALHA", "FASE 2: ENXAME",
                    "FASE 3: CLÁSSICO", "FASE 4: CAOS"]
    PHASE_COLORS = [(80, 160, 255), (200, 60, 220), (255, 200, 50), (255, 60, 60)]
    PATTERN_NAME = {}   # delegates to sub

    def __init__(self, config: 'GameConfig' = None):
        if config is None: config = GameConfig()
        self._config        = config
        self.hp             = self.max_hp = config.boss_hp * 2
        self.flash_frames   = 0
        self.mutators       = config.mutators
        self.stun_timer     = 0.0
        self.menu_diff      = config.diff
        self._phase_idx     = -1
        self._sub           = None
        self._teleport_timer = 0.0
        self._next_phase()

    # ---- phase management ------------------------------------------------
    def _next_phase(self):
        self._phase_idx = min(self._phase_idx + 1, 3)
        cls_list = [WallBoss, SwarmBoss, Boss, Boss]
        sub_cfg = GameConfig(
            self._config.diff,
            self._PHASE_TYPE[self._phase_idx],
            SKILL_NONE, WEAPON_DEFAULT,
            self._config.mutators,
        )
        sub_cfg.speed_mult = self._config.speed_mult * (1.0 + self._phase_idx * 0.15)
        sub_cfg.boss_hp    = 9999  # sub-boss must not die independently
        self._sub = cls_list[self._phase_idx](sub_cfg)
        self._sub.hp = self._sub.max_hp = 9999

    # ---- interface properties (delegate to sub) --------------------------
    @property
    def x(self) -> float:
        return SCREEN_W / 2.0 if isinstance(self._sub, WallBoss) else self._sub.x

    @property
    def y(self) -> float:
        return self._sub.y

    @property
    def size(self) -> int:
        return self._sub.size

    @property
    def in_prep(self) -> bool:
        return self._sub.in_prep

    @property
    def pattern(self):
        return self._sub.pattern

    def get_aabb_list(self):
        return self._sub.get_aabb_list()

    # ---- damage + phase transition ----------------------------------------
    def take_damage(self, dmg: float, diff):
        self.hp = max(0.0, self.hp - dmg)
        self.flash_frames     = 6
        self._sub.flash_frames = 6
        # Transition at 75% / 50% / 25% HP boundaries
        threshold = self.max_hp * (1.0 - (self._phase_idx + 1) * 0.25)
        if self.hp <= threshold and self._phase_idx < 3:
            self._next_phase()

    def update(self, dt: float, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            return
        # Teleporte periódico em fases não-Muralha
        if not isinstance(self._sub, WallBoss):
            self._teleport_timer += dt
            if self._teleport_timer >= TM_TELEPORT_INTERVAL:
                self._teleport_timer = 0.0
                for _ in range(12):
                    _tx = random.uniform(SCREEN_W * 0.1, SCREEN_W * 0.9)
                    _ty = random.uniform(SCREEN_H * 0.08, SCREEN_H * 0.45)
                    if (_tx - px) ** 2 + (_ty - py) ** 2 > 180 ** 2:
                        if isinstance(self._sub, SwarmBoss):
                            self._sub.cx, self._sub.cy = _tx, _ty
                        else:
                            self._sub.x, self._sub.y = _tx, _ty
                        break
        self._sub.hp         = 9999
        self._sub.stun_timer = 0.0
        self._sub.update(dt, pool, ep, lp, px, py, diff, pvx, pvy)
        self._sub.hp = 9999
        if self.flash_frames > 0:
            self.flash_frames -= 1


# ===========================================================================
# EnemyPool — lacaios (Kamikazes + Sentinelas) do SummonerBoss
# ===========================================================================
class EnemyPool:
    def __init__(self):
        self.ex     = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self.ey     = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self.evx    = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self.evy    = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self.ehp    = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self.etype  = np.zeros(MAX_ENEMIES, dtype=np.int8)
        self.etmr   = np.zeros(MAX_ENEMIES, dtype=np.float32)  # shoot timer / fuse
        self.active = np.zeros(MAX_ENEMIES, dtype=np.bool_)
        self.e_hit_flash = np.zeros(MAX_ENEMIES, dtype=np.int8)   # frames restantes de flash branco
        self.free_stack: list = list(range(MAX_ENEMIES - 1, -1, -1))
        self.active_count = 0
        # Buffer de mortes para emissão de partículas no local correto (zero-GC)
        self._kill_xs = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self._kill_ys = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self._kill_n  = 0
        # Buffer de hits não-letais para faíscas (zero-GC)
        self._hit_xs  = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self._hit_ys  = np.zeros(MAX_ENEMIES, dtype=np.float32)
        self._hit_n   = 0

    def acquire(self, x: float, y: float, etype: int) -> int:
        if not self.free_stack: return -1
        idx = self.free_stack.pop()
        self.active[idx] = True
        self.ex[idx]     = x;  self.ey[idx] = y
        self.evx[idx]    = 0.0; self.evy[idx] = 0.0
        self.etype[idx]  = etype
        self.etmr[idx]   = 0.0
        self.e_hit_flash[idx] = 0
        if etype == ETYPE_KAMIKAZE:
            self.ehp[idx] = ENEMY_KAMIKAZE_HP
        elif etype == ETYPE_BUBBLE:
            self.ehp[idx] = BUBBLE_HP
            self.etmr[idx] = BUBBLE_EXPLODE_T   # reutiliza etmr como timer de explosão
        else:
            self.ehp[idx] = ENEMY_SENTINEL_HP
        self.active_count += 1
        return idx

    def release(self, idx: int):
        self.active[idx] = False
        self.free_stack.append(idx)
        self.active_count -= 1

    def clear(self):
        self.active[:] = False
        self.e_hit_flash[:] = 0
        self.active_count = 0
        self.free_stack = list(range(MAX_ENEMIES - 1, -1, -1))

    def update(self, dt: float, pool: 'BulletPool', px: float, py: float, speed_mult: float):
        _flash_on = np.where(self.e_hit_flash > 0)[0]
        if _flash_on.size:
            self.e_hit_flash[_flash_on] -= 1
        for i in np.where(self.active)[0]:
            idx = int(i)
            if self.etype[idx] == ETYPE_BUBBLE:
                self.etmr[idx] -= dt
                if self.etmr[idx] <= 0.0:
                    sx, sy = float(self.ex[idx]), float(self.ey[idx])
                    self.release(idx)
                    for k in range(BUBBLE_BURST_N):
                        ang = k * (TWO_PI / BUBBLE_BURST_N)
                        bidx = pool.acquire()
                        if bidx < 0: continue
                        pool.bx[bidx] = sx; pool.by[bidx] = sy
                        pool.bvx[bidx] = math.cos(ang) * 120.0
                        pool.bvy[bidx] = math.sin(ang) * 120.0
                continue
            if self.etype[idx] == ETYPE_KAMIKAZE:
                # Acelera em direção ao jogador
                dx = px - float(self.ex[idx]); dy = py - float(self.ey[idx])
                dist = math.sqrt(dx*dx + dy*dy) + 1.0
                spd  = ENEMY_KAMIKAZE_SPEED * speed_mult
                self.evx[idx] += dx / dist * spd * 3.0 * dt
                self.evy[idx] += dy / dist * spd * 3.0 * dt
                s = math.sqrt(self.evx[idx]**2 + self.evy[idx]**2)
                if s > spd:
                    self.evx[idx] = self.evx[idx] / s * spd
                    self.evy[idx] = self.evy[idx] / s * spd
                self.ex[idx] += self.evx[idx] * dt
                self.ey[idx] += self.evy[idx] * dt
                # Remove se sair muito da tela
                if (self.ex[idx] < -150 or self.ex[idx] > SCREEN_W + 150 or
                    self.ey[idx] < -150 or self.ey[idx] > SCREEN_H + 150):
                    self.release(idx)
            else:  # SENTINEL — estacionária, dispara em cruz
                self.etmr[idx] += dt
                cd = SENTINEL_FIRE_RATE / speed_mult
                if self.etmr[idx] >= cd:
                    self.etmr[idx] -= cd
                    bspd = SENTINEL_BULLET_SPEED * speed_mult
                    sx, sy = float(self.ex[idx]), float(self.ey[idx])
                    for vx, vy in ((0.0, -bspd), (0.0, bspd), (-bspd, 0.0), (bspd, 0.0)):
                        bidx = pool.acquire()
                        if bidx >= 0:
                            pool.bx[bidx] = sx; pool.by[bidx] = sy
                            pool.bvx[bidx] = vx; pool.bvy[bidx] = vy

    def check_pb_hit(self, pb: 'PlayerBulletPool', glass_cannon: bool = False) -> int:
        """Checa colisão de PlayerBullets com inimigos. Retorna kills.
        Mortes: _kill_xs/_kill_ys/_kill_n. Hits não-letais: _hit_xs/_hit_ys/_hit_n."""
        kills = 0
        self._kill_n = 0
        self._hit_n  = 0
        active_e = np.where(self.active)[0]
        if not len(active_e): return 0
        for i in active_e:
            i = int(i)
            if not self.active[i]: continue
            ex, ey = float(self.ex[i]), float(self.ey[i])
            if self.etype[i] == ETYPE_KAMIKAZE:
                es = float(ENEMY_KAMIKAZE_SIZE)
            elif self.etype[i] == ETYPE_BUBBLE:
                es = 16.0
            else:
                es = float(ENEMY_SENTINEL_SIZE)
            snap = np.where(pb.active)[0]
            if not len(snap): break
            dx = np.abs(pb.px[snap] - ex)
            dy = np.abs(pb.py[snap] - ey)
            in_range = snap[(dx <= es) & (dy <= es)]
            for pidx in in_range:
                pidx = int(pidx)
                if pb.active[pidx]:
                    mult = 3.0 if glass_cannon else 1.0
                    self.ehp[i] -= float(pb.damage[pidx]) * mult
                    pb.release(pidx)
            if self.active[i]:
                if self.ehp[i] <= 0:
                    if self._kill_n < MAX_ENEMIES:
                        self._kill_xs[self._kill_n] = ex
                        self._kill_ys[self._kill_n] = ey
                        self._kill_n += 1
                    self.release(i)
                    kills += 1
                elif len(in_range):
                    # Hit não-letal — flash + faísca
                    self.e_hit_flash[i] = 4
                    if self._hit_n < MAX_ENEMIES:
                        self._hit_xs[self._hit_n] = ex
                        self._hit_ys[self._hit_n] = ey
                        self._hit_n += 1
        return kills

    def check_player_hit(self, px: float, py: float) -> int:
        """Kamikazes que tocam o jogador explodem. Retorna número de hits."""
        r_sq = (PLAYER_RADIUS + ENEMY_KAMIKAZE_SIZE) ** 2
        kamis = np.where(self.active & (self.etype == ETYPE_KAMIKAZE))[0]
        hits = 0
        for i in kamis:
            i = int(i)
            dx = float(self.ex[i]) - px; dy = float(self.ey[i]) - py
            if dx*dx + dy*dy <= r_sq:
                self.release(i)
                hits += 1
        return hits


# ===========================================================================
# WaveManager — orquestrador do modo Wave Survival
# ===========================================================================
class WaveManager:
    """Zero-GC: usa enm_pool pré-alocado; wave_defs carregados antes de PLAYING."""

    WAVE_WIN = 30   # ondas a concluir para vitória

    def __init__(self, wave_defs: list):
        self._defs       = wave_defs   # list[dict] de waves.json
        self.wave_n      = 0           # onda atual (0-indexed)
        self._spawned    = 0
        self._spawn_cd   = 0.0
        self._wave_done  = False
        self.boss_wave   = False
        self.boss_type   = -1
        self.game_won    = False
        self._start_cd   = 2.0         # pausa antes do primeiro spawn

    def _def(self) -> dict:
        if self.wave_n < len(self._defs):
            return self._defs[self.wave_n]
        n = self.wave_n
        return {"enemies": 5 + n * 2,
                "kamikaze_ratio": max(0.3, 1.0 - n * 0.025),
                "spawn_interval": max(0.35, 1.5 - n * 0.04)}

    def start_wave(self):
        d = self._def()
        self.boss_wave  = bool(d.get("boss_wave", False))
        self.boss_type  = int(d.get("boss_type", BOSS_CLASSIC)) if self.boss_wave else -1
        self._spawned   = 0
        self._spawn_cd  = float(d.get("spawn_interval", 1.2))
        self._wave_done = False
        self._start_cd  = 2.0

    def next_wave(self):
        self.wave_n += 1
        if self.wave_n >= self.WAVE_WIN:
            self.game_won = True
            return
        self.start_wave()

    def update(self, dt: float, enm_pool: 'EnemyPool', px: float, py: float) -> bool:
        """Retorna True quando a onda terminou (todos spawneados e mortos)."""
        if self._wave_done or self.boss_wave or self.game_won:
            return False
        if self._start_cd > 0:
            self._start_cd -= dt
            return False
        d     = self._def()
        total = int(d.get("enemies", 5))
        ivl   = float(d.get("spawn_interval", 1.2))
        kr    = float(d.get("kamikaze_ratio", 0.5))
        self._spawn_cd -= dt
        if self._spawned < total and self._spawn_cd <= 0:
            self._spawn_cd = ivl
            side = random.randint(0, 3)
            if side == 0:   ex, ey = random.uniform(50, SCREEN_W - 50), -30.0
            elif side == 1: ex, ey = SCREEN_W + 30.0, random.uniform(50, SCREEN_H - 50)
            elif side == 2: ex, ey = random.uniform(50, SCREEN_W - 50), SCREEN_H + 30.0
            else:           ex, ey = -30.0, random.uniform(50, SCREEN_H - 50)
            etype = ETYPE_KAMIKAZE if random.random() < kr else ETYPE_SENTINEL
            enm_pool.acquire(ex, ey, etype)
            self._spawned += 1
        if self._spawned >= total and enm_pool.active_count == 0:
            self._wave_done = True
            return True
        return False


# ===========================================================================
# BossRushConfig — playlist orientada a dados para o modo Boss Rush
# ===========================================================================
class BossRushConfig:
    """Define uma sequência de bosses para o modo Boss Rush. Zero-GC: shuffle ocorre
    em start_run(), não durante o PLAYING."""

    CLASSIC: 'BossRushConfig | None' = None   # inicializado abaixo
    SINS:    'BossRushConfig | None' = None

    def __init__(self, label: str, pool_ids: list,
                 is_random: bool = False,
                 fixed_final_boss_id: int = None,
                 hp_scale_per_stage: float = 1.0):
        self.label               = label
        self.pool_ids            = list(pool_ids)
        self.is_random           = is_random
        self.fixed_final_boss_id = fixed_final_boss_id
        self.hp_scale_per_stage  = hp_scale_per_stage


class BossRushManager:
    """Orquestra a sequência de bosses de forma genérica e orientada a dados."""

    def __init__(self, rush_config: BossRushConfig, game_config: 'GameConfig'):
        self._rcfg      = rush_config
        self._gcfg      = game_config
        self._sequence: list = []
        self.stage_idx  = 0
        self.done       = False
        self._build_sequence()

    def _build_sequence(self):
        ids = list(self._rcfg.pool_ids)
        if self._rcfg.is_random:
            random.shuffle(ids)
        final = self._rcfg.fixed_final_boss_id
        if final is not None:
            if final in ids:
                ids.remove(final)
            ids.append(final)
        self._sequence = ids

    def current_boss_id(self) -> int:
        if self.stage_idx < len(self._sequence):
            return self._sequence[self.stage_idx]
        return -1

    def make_game_config_for_stage(self) -> 'GameConfig':
        boss_id = self.current_boss_id()
        scale   = self._rcfg.hp_scale_per_stage ** self.stage_idx
        cfg     = GameConfig(self._gcfg.diff, boss_id,
                             self._gcfg.skill, self._gcfg.weapon,
                             self._gcfg.mutators)
        cfg.boss_hp = max(1, int(cfg.boss_hp * scale))
        return cfg

    def advance(self):
        self.stage_idx += 1
        if self.stage_idx >= len(self._sequence):
            self.done = True

    def reinit(self, boss_id: int, stage_index: int):
        """Força sequência de um boss — usado para dev/teste."""
        self._sequence = [boss_id]
        self.stage_idx = stage_index
        self.done      = False

    def stage_count(self) -> int:
        return len(self._sequence)

    @property
    def label(self) -> str:
        return self._rcfg.label


# Playlists pré-definidas (inicializadas após as constantes de boss estarem definidas)
BossRushConfig.CLASSIC = BossRushConfig(
    label="BOSS RUSH CLÁSSICO",
    pool_ids=[BOSS_CLASSIC, BOSS_SWARM, BOSS_WALL,
              BOSS_TWINS, BOSS_SUMMONER, BOSS_OMEGA],
    is_random=False, hp_scale_per_stage=1.0,
)
BossRushConfig.SINS = BossRushConfig(
    label="OS 7 PECADOS",
    pool_ids=[BOSS_PRIDE, BOSS_SLOTH, BOSS_ENVY, BOSS_GLUTTONY,
              BOSS_GREED, BOSS_LUST, BOSS_WRATH],
    is_random=True, fixed_final_boss_id=BOSS_SIN, hp_scale_per_stage=1.15,
)


# ===========================================================================
# TwinsBoss — Gêmeos Yin (azul, lento) e Yang (laranja, rápido)
# ===========================================================================
class TwinsBoss:
    BOSS_TYPE    = BOSS_TWINS
    PATTERN_NAME = {0: "FASE 1", 1: "YANG DOMINANTE", 2: "YIN DOMINANTE",
                    10: "HÉLICE DE DNA", 11: "PÊNDULO ESMAGADOR"}

    _CORNERS = [(0.25,0.22), (0.75,0.22), (0.25,0.60), (0.75,0.60)]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        hp  = cfg.boss_hp
        self.hp = self.max_hp = float(hp)
        self.flash_frames = 0
        self.stun_timer   = 0.0
        self.mutators     = cfg.mutators
        self.menu_diff    = cfg.diff
        self.speed_mult   = cfg.speed_mult
        self.in_prep      = True
        self.phase_t      = 0.0
        self.pattern      = 0

        # Sub-entidades
        self.yin_hp  = float(hp) / 2.0
        self.yang_hp = float(hp) / 2.0
        self.yin_alive  = True
        self.yang_alive = True
        self.rage       = False

        # Posições
        self.yin_x  = SCREEN_W * 0.28
        self.yin_y  = SCREEN_H * 0.28
        self.yang_x = SCREEN_W * 0.72
        self.yang_y = SCREEN_H * 0.28
        self._yang_ang = 0.0

        # Timers de tiro individuais (fase 1)
        self.yin_shoot_t  = 0.0
        self.yang_shoot_t = 0.0

        # Waypoints de Yin
        self._yin_tsx = self.yin_x; self._yin_tsy = self.yin_y
        self._yin_ttx = self.yin_x; self._yin_tty = self.yin_y
        self._yin_mt  = 0.0; self._yin_md = 1.0
        self._yin_pick_wp()

        # Conquistas
        self.t             = 0.0
        self.yin_death_time  = -1.0
        self.yang_death_time = -1.0

        # -- Fase 1: ataques conjuntos ------------------------------------
        self._joint_cd     = 4.0
        self._joint_atk    = None   # None | 'helix' | 'pendulum'
        self._joint_t      = 0.0
        self._helix_ang    = 0.0
        self._helix_fire_t = 0.0
        self._pend_lx      = SCREEN_W * 0.12
        self._pend_rx      = SCREEN_W * 0.88
        self._pend_fire_t  = 0.0
        self._pend_wall_t  = 0.0

        # -- Fase 2: sobrevivente após absorção ---------------------------
        self._phase          = 1
        self._scenario       = None   # 'yang' | 'yin'
        self.absorb_emit     = False  # sinal one-shot para main.py
        self._absorb_x       = 0.0; self._absorb_y = 0.0
        self._survivor_scale = 1.0

        # Fase 2 — estado atual
        self._p2_atk  = 0
        self._p2_t    = 0.0

        # Yang P2 — wasp
        self._wasp_tx = None; self._wasp_ty = None
        self._wasp_n  = 0
        # Yang P2 — whip / meteor
        self._meteor_t   = 0.0; self._meteor_cnt = 0

        # Yin P2 — chess
        self._chess_fired = False; self._chess_t = 0.0
        # Yin P2 — labyrinth
        self._lab_t = 0.0; self._lab_row = 0
        # Yin P2 — minefield
        self._mine_placed = False
        # Yin P2 — chess cage
        self._cage_placed = False; self._cage_cx = 0.0; self._cage_cy = 0.0
        self._cage_flicker_t = 0.0; self._cage_phase = 0
        # Yin P2 — inversion pulse
        self._inv_cd        = 6.0   # começa mais cedo para o jogador ver logo
        self._inv_charging  = False
        self._inv_charge_t  = 0.0
        self.inversion_flash = False  # sinal one-shot para main.py
        # Yang P2 — phantom dash
        self._phantom_going  = False
        self._phantom_vx     = 0.0
        self._phantom_wait   = 0.0
        self._phantom_trail_t = 0.0
        self._yang_dashing   = False

    # -- geometria ----------------------------------------------------------
    def get_aabb_list(self):
        h = int(TWIN_SIZE * self._survivor_scale)
        aabbs = []
        if self.yin_alive:
            aabbs.append((self.yin_x - h, self.yin_y - h,
                          self.yin_x + h, self.yin_y + h))
        if self.yang_alive:
            aabbs.append((self.yang_x - h, self.yang_y - h,
                          self.yang_x + h, self.yang_y + h))
        return aabbs if aabbs else [(0, 0, 0, 0)]

    @property
    def x(self): return self.yin_x if self.yin_alive else self.yang_x
    @property
    def y(self): return self.yin_y if self.yin_alive else self.yang_y
    @property
    def size(self): return int(TWIN_SIZE * self._survivor_scale * 2)

    # -- dano ---------------------------------------------------------------
    def take_damage(self, dmg: float, diff):
        self._damage_yin(dmg / 2.0); self._damage_yang(dmg / 2.0)

    def take_damage_targeted(self, dmg: float, aabb_idx: int, diff):
        alive = []
        if self.yin_alive:  alive.append('yin')
        if self.yang_alive: alive.append('yang')
        if aabb_idx < len(alive):
            if alive[aabb_idx] == 'yin': self._damage_yin(dmg)
            else:                         self._damage_yang(dmg)

    def _damage_yin(self, dmg: float):
        if not self.yin_alive: return
        actual = min(dmg, self.yin_hp)
        self.hp = max(0.0, self.hp - actual)
        self.yin_hp = max(0.0, self.yin_hp - dmg)
        self.flash_frames = 6
        if self.yin_hp <= 0:
            self.yin_alive = False
            self.yin_death_time = self.t
            if self.yang_alive and self._phase == 1:
                self._trigger_absorption('yang')

    def _damage_yang(self, dmg: float):
        if not self.yang_alive: return
        actual = min(dmg, self.yang_hp)
        self.hp = max(0.0, self.hp - actual)
        self.yang_hp = max(0.0, self.yang_hp - dmg)
        self.flash_frames = 6
        if self.yang_hp <= 0:
            self.yang_alive = False
            self.yang_death_time = self.t
            if self.yin_alive and self._phase == 1:
                self._trigger_absorption('yin')

    def _trigger_absorption(self, scenario: str):
        self._phase    = 2
        self._scenario = scenario
        if scenario == 'yang':          # Yin morreu, Yang sobrevive
            self._absorb_x = self.yin_x; self._absorb_y = self.yin_y
            self.yang_hp = self.max_hp;  self.hp = self.max_hp
            self.yang_x  = SCREEN_W * 0.5; self.yang_y = SCREEN_H * 0.3
        else:                           # Yang morreu, Yin sobrevive
            self._absorb_x = self.yang_x; self._absorb_y = self.yang_y
            self.yin_hp  = self.max_hp;  self.hp = self.max_hp
            self.yin_x   = SCREEN_W * 0.5; self.yin_y = SCREEN_H * 0.3
        self._survivor_scale = TWIN_SURVIVOR_SCALE
        self.absorb_emit     = True
        self.rage            = False
        self._p2_atk = 0; self._p2_t = 0.0
        self._wasp_tx = None; self._wasp_n = 0
        self._chess_fired = False; self._chess_t = 0.0
        self._lab_t = 0.0; self._lab_row = 0
        self._meteor_t = 0.0; self._meteor_cnt = 0
        self._inv_cd = 6.0; self._inv_charging = False; self._inv_charge_t = 0.0
        self.inversion_flash = False
        self._mine_placed = False
        self._cage_placed = False; self._cage_flicker_t = 0.0; self._cage_phase = 0
        self._phantom_going = False; self._phantom_vx = 0.0
        self._phantom_wait = 0.0; self._phantom_trail_t = 0.0; self._yang_dashing = False
        self.pattern  = 1 if scenario == 'yang' else 2

    # -- movimento Yin ------------------------------------------------------
    def _yin_pick_wp(self):
        idx = random.randrange(len(self._CORNERS))
        self._yin_tsx = self.yin_x; self._yin_tsy = self.yin_y
        self._yin_ttx = self._CORNERS[idx][0] * SCREEN_W
        self._yin_tty = self._CORNERS[idx][1] * SCREEN_H
        dist = math.sqrt((self._yin_ttx-self._yin_tsx)**2 +
                         (self._yin_tty-self._yin_tsy)**2) + 1.0
        self._yin_mt = 0.0
        self._yin_md = dist / (TWIN_YIN_SPEED * self.speed_mult)

    def _yin_move(self, dt: float):
        if not self.yin_alive: return
        self._yin_mt = min(self._yin_mt + dt, self._yin_md)
        t = self._yin_mt / self._yin_md if self._yin_md > 0 else 1.0
        t = t*t*(3.0 - 2.0*t)
        self.yin_x = self._yin_tsx + (self._yin_ttx - self._yin_tsx) * t
        self.yin_y = self._yin_tsy + (self._yin_tty - self._yin_tsy) * t
        if self._yin_mt >= self._yin_md: self._yin_pick_wp()

    def _yang_orbit(self, dt: float, px: float, py: float):
        if not self.yang_alive: return
        spd = TWIN_YANG_SPEED * self.speed_mult
        self._yang_ang += (spd / (TWIN_YANG_ORBIT_R + 1.0)) * dt
        tx = max(TWIN_SIZE*2.0, min(SCREEN_W-TWIN_SIZE*2.0,
                 px + math.cos(self._yang_ang) * TWIN_YANG_ORBIT_R))
        ty = max(TWIN_SIZE*2.0, min(SCREEN_H*0.75,
                 py + math.sin(self._yang_ang) * TWIN_YANG_ORBIT_R))
        dx = tx-self.yang_x; dy = ty-self.yang_y
        d  = math.sqrt(dx*dx+dy*dy)+1.0
        self.yang_x += dx/d*min(d, spd*dt)
        self.yang_y += dy/d*min(d, spd*dt)

    # -- tiros individuais fase 1 ------------------------------------------
    def _shoot_yin(self, pool, px, py, diff):
        bspd = 145.0 * diff.speed_mult
        ang0 = math.atan2(py - self.yin_y, px - self.yin_x)
        for k in range(8):
            bidx = pool.acquire()
            if bidx < 0: break
            ang = ang0 + k * (TWO_PI / 8.0)
            pool.bx[bidx]=self.yin_x; pool.by[bidx]=self.yin_y
            pool.bvx[bidx]=math.cos(ang)*bspd; pool.bvy[bidx]=math.sin(ang)*bspd
            pool.b_type[bidx]=BTYPE_BLUE

    def _shoot_yang(self, pool, px, py, diff):
        bspd = 175.0 * diff.speed_mult
        for k in range(12):
            bidx = pool.acquire()
            if bidx < 0: break
            ang = k * (TWO_PI / 12.0)
            pool.bx[bidx]=self.yang_x; pool.by[bidx]=self.yang_y
            pool.bvx[bidx]=math.cos(ang)*bspd; pool.bvy[bidx]=math.sin(ang)*bspd
            pool.b_type[bidx]=BTYPE_ORANGE

    # -- ataques conjuntos fase 1 ------------------------------------------
    def _start_joint_attack(self):
        self._joint_atk = 'pendulum' if self._joint_atk == 'helix' else 'helix'
        self._joint_t = 0.0; self._helix_fire_t = 0.0; self._helix_ang = 0.0
        self._pend_lx = SCREEN_W * 0.12; self._pend_rx = SCREEN_W * 0.88
        self._pend_fire_t = 0.0; self._pend_wall_t = 0.0
        self.pattern = 10 if self._joint_atk == 'helix' else 11

    def _update_joint(self, dt, pool, px, py, diff):
        dur = TWIN_HELIX_DURATION if self._joint_atk == 'helix' else TWIN_PEND_DURATION
        self._joint_t += dt
        if self._joint_t >= dur:
            self._joint_atk = None; self._joint_cd = TWIN_JOINT_CD; self.pattern = 0
            return
        if self._joint_atk == 'helix': self._update_helix(dt, pool, diff)
        else:                           self._update_pendulum(dt, pool, diff)

    def _update_helix(self, dt, pool, diff):
        cx = SCREEN_W * 0.5; cy = SCREEN_H * 0.32
        self._helix_ang += TWIN_HELIX_ORBIT_W * dt
        for ang_off, b_type, alive in [
            (0.0,      BTYPE_BLUE,   self.yin_alive),
            (math.pi,  BTYPE_ORANGE, self.yang_alive),
        ]:
            ang = self._helix_ang + ang_off
            ox  = cx + math.cos(ang) * TWIN_HELIX_ORBIT_R
            oy  = cy + math.sin(ang) * TWIN_HELIX_ORBIT_R
            if b_type == BTYPE_BLUE:   self.yin_x  = ox; self.yin_y  = oy
            else:                       self.yang_x = ox; self.yang_y = oy

        self._helix_fire_t += dt
        if self._helix_fire_t >= TWIN_HELIX_FIRE_RATE:
            self._helix_fire_t -= TWIN_HELIX_FIRE_RATE
            bspd = TWIN_HELIX_BSPEED * diff.speed_mult
            for ang_off, ox, oy, b_type, alive in [
                (0.0,     self.yin_x,  self.yin_y,  BTYPE_BLUE,   self.yin_alive),
                (math.pi, self.yang_x, self.yang_y, BTYPE_ORANGE, self.yang_alive),
            ]:
                if not alive: continue
                ang  = self._helix_ang + ang_off
                bidx = pool.acquire()
                if bidx < 0: continue
                pool.bx[bidx]=ox; pool.by[bidx]=oy
                pool.bvx[bidx]=math.cos(ang)*bspd; pool.bvy[bidx]=math.sin(ang)*bspd
                pool.b_type[bidx]=b_type

    def _update_pendulum(self, dt, pool, diff):
        self._pend_wall_t += dt
        if self._pend_wall_t >= 1.1:
            self._pend_wall_t = 0.0
            self._fire_pend_walls(pool)
        self._pend_fire_t += dt
        if self._pend_fire_t >= TWIN_PEND_BALL_RATE / diff.speed_mult:
            self._pend_fire_t = 0.0
            self._fire_pend_balls(pool, diff)
        self._pend_lx = min(self._pend_lx + TWIN_PEND_WALL_SPEED*dt, SCREEN_W*0.45)
        self._pend_rx = max(self._pend_rx - TWIN_PEND_WALL_SPEED*dt, SCREEN_W*0.55)
        # Posiciona Yin e Yang nas paredes
        self.yin_x  = self._pend_lx; self.yin_y  = SCREEN_H * 0.3
        self.yang_x = self._pend_rx; self.yang_y = SCREEN_H * 0.3

    def _fire_pend_walls(self, pool):
        for k in range(10):
            y = SCREEN_H * 0.1 + k * (SCREEN_H * 0.8 / 9.0)
            for x, vx in [(self._pend_lx, TWIN_PEND_WALL_SPEED*0.6),
                          (self._pend_rx, -TWIN_PEND_WALL_SPEED*0.6)]:
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx]=x; pool.by[bidx]=y
                pool.bvx[bidx]=vx; pool.bvy[bidx]=0.0
                pool.b_type[bidx]=BTYPE_BLUE

    def _fire_pend_balls(self, pool, diff):
        bspd = TWIN_PEND_BALL_SPEED * diff.speed_mult
        for _ in range(3):
            y = random.uniform(SCREEN_H*0.15, SCREEN_H*0.75)
            for x, vx in [(0.0, bspd), (float(SCREEN_W), -bspd)]:
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx]=x; pool.by[bidx]=y
                pool.bvx[bidx]=vx; pool.bvy[bidx]=random.uniform(-22,22)
                pool.b_type[bidx]=BTYPE_ORANGE

    # -- fase 2A: Yang Dominante ------------------------------------------
    _YANG_P2_DUR = [9.0, 5.5, YANG_METEOR_DUR + 1.5, YANG_PHANTOM_PHASE_DUR]

    def _update_yang_p2(self, dt, pool, px, py, diff):
        self._p2_t += dt
        if self._p2_t >= self._YANG_P2_DUR[self._p2_atk % 4]:
            self._p2_t = 0.0
            self._p2_atk = (self._p2_atk + 1) % 4
            self._wasp_tx = None; self._wasp_n = 0
            self._meteor_t = 0.0; self._meteor_cnt = 0
            if self._p2_atk == 2:
                self.yang_x = SCREEN_W*0.5; self.yang_y = SCREEN_H*0.06
            if self._p2_atk == 3:
                # Inicia dash fantasma: posiciona Yang na borda esquerda
                sc = self._survivor_scale
                self.yang_x  = -TWIN_SIZE * sc
                self.yang_y  = max(60.0, min(float(SCREEN_H) - 60.0, py))
                self._phantom_vx    = YANG_PHANTOM_SPD * diff.speed_mult
                self._phantom_going = False
                self._phantom_wait  = 0.45   # telegrama inicial
                self._phantom_trail_t = 0.0
                self._yang_dashing  = False
        atk = self._p2_atk % 4
        if   atk == 0: self._update_wasp(dt, pool, px, py)
        elif atk == 1: self._update_whip_phase(dt, pool, diff, px, py)
        elif atk == 2: self._update_meteor(dt, pool, px, py, diff)
        else:          self._update_phantom_dash(dt, pool, px, py, diff)

    def _update_phantom_dash(self, dt, pool, px, py, diff):
        sc = self._survivor_scale
        hs = TWIN_SIZE * sc
        if not self._phantom_going:
            self._phantom_wait -= dt
            if self._phantom_wait <= 0.0:
                self._phantom_going   = True
                self._yang_dashing    = True
                self._phantom_trail_t = 0.0
            return
        # Move Yang em alta velocidade
        self.yang_x += self._phantom_vx * dt
        # Rastreia suavemente o Y do jogador durante o dash
        self.yang_y += (py - self.yang_y) * min(1.0, 2.8 * dt)
        # Rastro perpendicular de balas laranjas
        self._phantom_trail_t += dt
        if self._phantom_trail_t >= YANG_PHANTOM_TRAIL_INT:
            self._phantom_trail_t = 0.0
            perp = YANG_PHANTOM_PERP_SPD * diff.speed_mult
            for k in range(1, YANG_PHANTOM_PERP_N + 1):
                offset = k * 14.0
                for vy_sign in (-1.0, 1.0):
                    bidx = pool.acquire()
                    if bidx >= 0:
                        pool.bx[bidx]     = self.yang_x
                        pool.by[bidx]     = self.yang_y + vy_sign * offset
                        pool.bvx[bidx]    = 0.0
                        pool.bvy[bidx]    = vy_sign * perp
                        pool.b_type[bidx] = BTYPE_ORANGE
        # Verifica saída da tela
        exited = (self._phantom_vx > 0 and self.yang_x > SCREEN_W + hs) or \
                 (self._phantom_vx < 0 and self.yang_x < -hs)
        if exited:
            self._phantom_going  = False
            self._yang_dashing   = False
            # Inverte direção e reposiciona na borda oposta
            self._phantom_vx = -self._phantom_vx
            self.yang_x = (-hs if self._phantom_vx > 0 else float(SCREEN_W) + hs)
            self.yang_y = max(60.0, min(float(SCREEN_H) - 60.0, py))
            self._phantom_wait = YANG_PHANTOM_PAUSE

    def _update_wasp(self, dt, pool, px, py):
        if self._wasp_n >= YANG_WASP_DASHES: return
        if self._wasp_tx is None:
            ang = random.uniform(0, TWO_PI)
            r   = YANG_DASH_DIST * random.uniform(0.9, 1.3)
            self._wasp_tx = max(TWIN_SIZE*3, min(SCREEN_W-TWIN_SIZE*3,
                               SCREEN_W*0.5 + math.cos(ang)*r))
            self._wasp_ty = max(TWIN_SIZE*3, min(SCREEN_H*0.72,
                               SCREEN_H*0.38 + math.sin(ang)*r*0.55))
        dx = self._wasp_tx-self.yang_x; dy = self._wasp_ty-self.yang_y
        dist = math.sqrt(dx*dx+dy*dy)+1e-6
        move = min(dist, 550.0*dt)
        self.yang_x += dx/dist*move; self.yang_y += dy/dist*move
        if dist-move <= 2.0:
            for _ in range(YANG_WASP_N):
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx]    = self.yang_x + random.uniform(-6,6)
                pool.by[bidx]    = self.yang_y + random.uniform(-6,6)
                pool.bvx[bidx]   = 0.0; pool.bvy[bidx] = 0.0
                pool.b_type[bidx]  = BTYPE_PURPLE
                pool.bstate[bidx]  = BSLEEPING
                pool.btimer[bidx]  = YANG_WASP_WAKE_T
            self._wasp_n += 1; self._wasp_tx = None

    def _update_whip_phase(self, dt, pool, diff, px, py):
        # Dispara um chicote a cada ~1.4s durante a fase
        prev_i = int((self._p2_t - dt) / 1.4)
        curr_i = int(self._p2_t / 1.4)
        if curr_i > prev_i or self._p2_t < 0.05:
            self._shoot_whip(pool, diff, px, py)

    def _shoot_whip(self, pool, diff, px, py):
        ang_to_p = math.atan2(py-self.yang_y, px-self.yang_x)
        bspd = 170.0 * diff.speed_mult
        for i in range(YANG_WHIP_N):
            frac = i / max(YANG_WHIP_N-1, 1)   # 0=ponta(bloqueia logo) 1=base(curva mais)
            ang  = ang_to_p + random.uniform(-YANG_WHIP_ARC, YANG_WHIP_ARC)
            bidx = pool.acquire()
            if bidx < 0: break
            pool.bx[bidx]=self.yang_x; pool.by[bidx]=self.yang_y
            pool.bvx[bidx]=math.cos(ang)*bspd*(1.0+frac*0.12)
            pool.bvy[bidx]=math.sin(ang)*bspd*(1.0+frac*0.12)
            pool.b_type[bidx]=BTYPE_PURPLE
            pool.btimer[bidx]=TWIN_PURPLE_HOME_T*frac   # ponta=0, base=máximo

    def _update_meteor(self, dt, pool, px, py, diff):
        self._meteor_t += dt
        if self._meteor_t >= YANG_METEOR_RATE / diff.speed_mult:
            self._meteor_t = 0.0
            spd   = random.uniform(YANG_METEOR_SPD_MIN, YANG_METEOR_SPD_MAX)*diff.speed_mult
            btype = BTYPE_ORANGE if self._meteor_cnt % 2 == 0 else BTYPE_PURPLE
            self._meteor_cnt += 1
            bidx  = pool.acquire()
            if bidx >= 0:
                pool.bx[bidx]  = random.uniform(SCREEN_W*0.08, SCREEN_W*0.92)
                pool.by[bidx]  = -8.0
                pool.bvx[bidx] = random.uniform(-28.0, 28.0)
                pool.bvy[bidx] = spd
                pool.b_type[bidx] = btype
                if btype == BTYPE_PURPLE:
                    pool.btimer[bidx] = random.uniform(TWIN_PURPLE_HOME_T * 0.25,
                                                       TWIN_PURPLE_HOME_T)

    # -- fase 2B: Yin Dominante -------------------------------------------
    _YIN_P2_DUR = [8.0, 10.0, 9.0, 7.0]   # chess / labyrinth / minefield / cage

    def _update_yin_p2(self, dt, pool, px, py, diff):
        self._p2_t += dt
        if self._p2_t >= self._YIN_P2_DUR[self._p2_atk % 4]:
            self._p2_t = 0.0; self._p2_atk = (self._p2_atk + 1) % 4
            self._chess_fired = False; self._chess_t = 0.0
            self._lab_row = 0;         self._lab_t   = 0.0
            self._mine_placed = False
            self._cage_placed = False; self._cage_flicker_t = 0.0; self._cage_phase = 0
        self._yin_move(dt)
        atk = self._p2_atk
        if   atk == 0: self._update_chess(dt, pool, diff)
        elif atk == 1: self._update_labyrinth(dt, pool, diff)
        elif atk == 2: self._update_minefield(dt, pool)
        else:          self._update_cage(dt, pool, diff, px, py)
        # Pulso de inversão — independente do ciclo de ataques
        if self._inv_charging:
            self._inv_charge_t += dt
            if self._inv_charge_t >= YIN_INV_CHARGE_T:
                active = pool.active
                blue_m   = active & (pool.b_type == BTYPE_BLUE)
                orange_m = active & (pool.b_type == BTYPE_ORANGE)
                # Minas adormecidas: balas azuis imóveis ganham velocidade ao inverter
                near_zero = (np.abs(pool.bvx) < 1.0) & (np.abs(pool.bvy) < 1.0)
                mine_m = blue_m & near_zero
                if mine_m.any():
                    mi = np.where(mine_m)[0]
                    dx = px - pool.bx[mi]; dy = py - pool.by[mi]
                    dist = np.sqrt(dx*dx + dy*dy) + 1e-3
                    spd = YIN_MINE_WAKE_SPD * diff.speed_mult
                    pool.bvx[mi] = dx / dist * spd
                    pool.bvy[mi] = dy / dist * spd
                # Inversão de cor
                pool.b_type[blue_m]   = BTYPE_ORANGE
                pool.b_type[orange_m] = BTYPE_BLUE
                self._inv_charging  = False
                self._inv_charge_t  = 0.0
                self._inv_cd        = YIN_INV_CD
                self.inversion_flash = True
        else:
            self._inv_cd -= dt
            if self._inv_cd <= 0.0:
                self._inv_charging = True
                self._inv_charge_t = 0.0

    # -- Minefield (atk 2) -------------------------------------------------
    def _update_minefield(self, dt, pool):
        if not self._mine_placed:
            self._mine_placed = True
            self._fire_minefield(pool)

    def _fire_minefield(self, pool):
        for _ in range(YIN_MINE_N):
            bidx = pool.acquire()
            if bidx < 0: break
            pool.bx[bidx]  = random.uniform(SCREEN_W * 0.08, SCREEN_W * 0.92)
            pool.by[bidx]  = random.uniform(SCREEN_H * 0.08, SCREEN_H * 0.72)
            pool.bvx[bidx] = 0.0; pool.bvy[bidx] = 0.0
            pool.b_type[bidx] = BTYPE_BLUE

    # -- Chess Cage (atk 3) -----------------------------------------------
    def _update_cage(self, dt, pool, diff, px, py):
        if not self._cage_placed:
            self._cage_placed = True
            # Centro do cage = posição atual do jogador, clampeada dentro da tela
            self._cage_cx = float(max(YIN_CAGE_HALF + 14,
                                      min(SCREEN_W - YIN_CAGE_HALF - 14, px)))
            self._cage_cy = float(max(YIN_CAGE_HALF + 14,
                                      min(SCREEN_H - YIN_CAGE_HALF - 14, py)))
            self._fire_cage_walls(pool)
            self._cage_flicker_t = 0.0; self._cage_phase = 0
        self._cage_flicker_t += dt
        if self._cage_flicker_t >= YIN_CAGE_FLICKER_T:
            self._cage_flicker_t = 0.0
            self._cage_phase ^= 1
            btype = BTYPE_BLUE if self._cage_phase == 0 else BTYPE_ORANGE
            half  = float(YIN_CAGE_HALF)
            spd   = YIN_CAGE_FILL_SPD * diff.speed_mult
            for _ in range(YIN_CAGE_FILL_N):
                x = self._cage_cx + random.uniform(-half * 0.82, half * 0.82)
                y = self._cage_cy + random.uniform(-half * 0.82, half * 0.82)
                bidx = pool.acquire()
                if bidx < 0: break
                dx = x - self._cage_cx; dy = y - self._cage_cy
                mag = math.sqrt(dx*dx + dy*dy) + 1e-3
                pool.bx[bidx] = x; pool.by[bidx] = y
                pool.bvx[bidx] = dx / mag * spd
                pool.bvy[bidx] = dy / mag * spd
                pool.b_type[bidx] = btype

    def _fire_cage_walls(self, pool):
        cx = self._cage_cx; cy = self._cage_cy
        half = float(YIN_CAGE_HALF); n = YIN_CAGE_DENSITY
        for t in range(n + 1):
            frac = t / n
            pos = cx - half + 2.0 * half * frac
            for bx, by, vx, vy in [
                (pos,      cy - half,  0.0, -22.0),   # topo  → deriva pra cima
                (pos,      cy + half,  0.0,  22.0),   # base  → deriva pra baixo
                (cx - half, cy - half + 2.0*half*frac, -22.0, 0.0),  # esq → esq
                (cx + half, cy - half + 2.0*half*frac,  22.0, 0.0),  # dir → dir
            ]:
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx] = bx; pool.by[bidx] = by
                pool.bvx[bidx] = vx; pool.bvy[bidx] = vy
                pool.b_type[bidx] = BTYPE_NORMAL

    def _update_chess(self, dt, pool, diff):
        self._chess_t += dt
        if not self._chess_fired and self._chess_t >= 0.5:
            self._chess_fired = True; self._fire_chess(pool, diff)
        if self._chess_t >= 1.5:
            interval = 1.9 / diff.speed_mult
            if int((self._chess_t-dt-1.5)/interval) < int((self._chess_t-1.5)/interval):
                self._fire_chess_orange(pool, diff)

    def _fire_chess(self, pool, diff):
        safe = set(random.sample(range(YIN_CHESS_COLS), YIN_CHESS_SAFE_N))
        cw   = SCREEN_W / YIN_CHESS_COLS
        bspd = YIN_CHESS_SPEED * diff.speed_mult
        for c in range(YIN_CHESS_COLS):
            if c in safe: continue
            x = cw * (c + 0.5)
            for r in range(YIN_CHESS_ROWS):
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx]=x; pool.by[bidx]=float(-8 - r*34)
                pool.bvx[bidx]=0.0; pool.bvy[bidx]=bspd
                pool.b_type[bidx]=BTYPE_BLUE

    def _fire_chess_orange(self, pool, diff):
        bspd = 195.0 * diff.speed_mult
        for _ in range(3):
            y = random.uniform(SCREEN_H*0.2, SCREEN_H*0.7)
            for x, vx in [(0.0, bspd), (float(SCREEN_W), -bspd)]:
                bidx = pool.acquire()
                if bidx < 0: break
                pool.bx[bidx]=x; pool.by[bidx]=y
                pool.bvx[bidx]=vx; pool.bvy[bidx]=0.0
                pool.b_type[bidx]=BTYPE_ORANGE

    def _update_labyrinth(self, dt, pool, diff):
        if self._lab_row >= YIN_LAB_ROWS: return
        self._lab_t += dt
        if self._lab_t >= 1.4:
            self._lab_t -= 1.4
            self._fire_lab_row(pool, diff, self._lab_row)
            self._lab_row += 1

    def _fire_lab_row(self, pool, diff, row_idx):
        y    = SCREEN_H*0.12 + row_idx*(SCREEN_H*0.76/max(YIN_LAB_ROWS-1,1))
        bvx  = -(YIN_LAB_SPEED * diff.speed_mult)
        phase = row_idx * 1.4
        x = float(SCREEN_W) + YIN_LAB_GAP
        while x > -YIN_LAB_GAP:
            if math.sin(x/(YIN_LAB_GAP*1.6)+phase) <= 0.28:
                bidx = pool.acquire()
                if bidx >= 0:
                    pool.bx[bidx]=x; pool.by[bidx]=y
                    pool.bvx[bidx]=bvx; pool.bvy[bidx]=0.0
                    pool.b_type[bidx]=BTYPE_BLUE
                    pool.b_invisible[bidx]=True
            x -= YIN_LAB_GAP

    # -- update principal --------------------------------------------------
    def update(self, dt: float, pool, ep, lp, px: float, py: float,
               diff, pvx: float = 0.0, pvy: float = 0.0):
        if self.hp <= 0: return
        self.t += dt
        if self.flash_frames > 0: self.flash_frames -= 1
        # sinais one-shot: resetar no frame seguinte ao que foram setados
        if self.absorb_emit:    self.absorb_emit    = False
        if self.inversion_flash: self.inversion_flash = False

        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer-dt); return

        # Fase 2 — sobrevivente
        if self._phase == 2:
            if self._scenario == 'yang': self._update_yang_p2(dt, pool, px, py, diff)
            else:                         self._update_yin_p2(dt, pool, px, py, diff)
            return

        # Fase 1 — ataques conjuntos têm prioridade
        if self._joint_atk is not None:
            self._update_joint(dt, pool, px, py, diff)
        else:
            self._joint_cd -= dt
            if self._joint_cd <= 0.0:
                self._start_joint_attack()
            else:
                self._yin_move(dt); self._yang_orbit(dt, px, py)
                yin_rate  = TWIN_SHOOT_YIN  / diff.speed_mult
                yang_rate = TWIN_SHOOT_YANG / diff.speed_mult
                if self.yin_alive:
                    self.yin_shoot_t += dt
                    if self.yin_shoot_t >= yin_rate:
                        self.yin_shoot_t -= yin_rate; self._shoot_yin(pool, px, py, diff)
                if self.yang_alive:
                    self.yang_shoot_t += dt
                    if self.yang_shoot_t >= yang_rate:
                        self.yang_shoot_t -= yang_rate; self._shoot_yang(pool, px, py, diff)


# ===========================================================================
# SummonerBoss — Invocador que teleporta e convoca lacaios
# ===========================================================================
class SummonerBoss:
    BOSS_TYPE    = BOSS_SUMMONER
    PATTERN_NAME = {0: "SUMMON", 1: "BLITZ"}

    _CORNERS = [
        (0.18, 0.18), (0.82, 0.18),
        (0.18, 0.65), (0.82, 0.65),
    ]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.flash_frames = 0
        self.stun_timer   = 0.0
        self.mutators     = cfg.mutators
        self.menu_diff    = cfg.diff
        self.speed_mult   = cfg.speed_mult
        self.in_prep      = True
        self.phase_t      = 0.0
        self.pattern      = 0

        self.x = SCREEN_W * 0.5
        self.y = SCREEN_H * 0.25
        self.size = SUMMONER_SIZE

        self._teleport_t = 0.0
        self._summon_t   = 0.0
        self._corner_idx = 0
        self._wave       = 0     # alterna tipo de summon

        # EnemyPool injetado pelo new_game() depois da construção
        self.enm_pool: 'EnemyPool | None' = None

    def get_aabb_list(self):
        h = self.size
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, dmg: float, diff):
        self.hp = max(0.0, self.hp - dmg)
        self.flash_frames = 8
        diff.update(self.hp, self.max_hp)

    def _teleport(self):
        self._corner_idx = (self._corner_idx + 1) % 4
        cx, cy = self._CORNERS[self._corner_idx]
        self.x = cx * SCREEN_W
        self.y = cy * SCREEN_H

    def _summon_wave(self):
        if self.enm_pool is None: return
        # Alterna: par → kamikazes, ímpar → sentinela
        if self._wave % 2 == 0:
            for _ in range(3):
                sx = random.uniform(SCREEN_W * 0.15, SCREEN_W * 0.85)
                sy = random.uniform(SCREEN_H * 0.05, SCREEN_H * 0.20)
                self.enm_pool.acquire(sx, sy, ETYPE_KAMIKAZE)
        else:
            sx = random.uniform(SCREEN_W * 0.25, SCREEN_W * 0.75)
            sy = random.uniform(SCREEN_H * 0.25, SCREEN_H * 0.55)
            self.enm_pool.acquire(sx, sy, ETYPE_SENTINEL)
        self._wave += 1

    def _fire_burst(self, pool: 'BulletPool', diff):
        bspd = 180.0 * diff.speed_mult
        for k in range(8):
            ang  = k * (TWO_PI / 8.0)
            bidx = pool.acquire()
            if bidx >= 0:
                pool.bx[bidx]  = self.x; pool.by[bidx]  = self.y
                pool.bvx[bidx] = math.cos(ang) * bspd
                pool.bvy[bidx] = math.sin(ang) * bspd

    def update(self, dt: float, pool, ep, lp, px: float, py: float,
               diff, pvx: float = 0.0, pvy: float = 0.0):
        if self.hp <= 0: return
        if self.flash_frames > 0: self.flash_frames -= 1

        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME:
                self.in_prep = False; self.phase_t = 0.0
            return

        if self.stun_timer > 0:
            self.stun_timer = max(0.0, self.stun_timer - dt)
            return

        self._teleport_t += dt
        self._summon_t   += dt

        if self._teleport_t >= SUMMONER_TELEPORT_CD / diff.speed_mult:
            self._teleport_t -= SUMMONER_TELEPORT_CD / diff.speed_mult
            self._teleport()
            self._fire_burst(pool, diff)

        if self._summon_t >= SUMMONER_SUMMON_CD / diff.speed_mult:
            self._summon_t -= SUMMONER_SUMMON_CD / diff.speed_mult
            self._summon_wave()


# ===========================================================================
# PrideBoss — Soberba
# Fase 0: holofote varrendo, escudo exceto na coluna do feixe
# Fase 1: geometria sagrada — quadrados/triângulos giratórios de balas
# Fase 2: força ascendente comprime arena; espiral de balas
# ===========================================================================
class PrideBoss:
    BOSS_TYPE    = BOSS_PRIDE
    PATTERN_NAME = {0: "O HOLOFOTE", 1: "EGO FERIDO", 2: "JULGAMENTO FINAL"}
    _PHASE_HP    = [0.66, 0.33]
    _SPOT_W      = 88.0
    _SWEEP_SPD   = 95.0

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 52.0; self.size = 34
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0
        self._phase      = 0
        self.invulnerable = True
        self.spot_x      = SCREEN_W / 2.0
        self._spot_dir   = 1
        self._fire_acc   = 0.0
        self._geo_angle  = 0.0
        self._geo_acc    = 0.0
        self._geo_shape  = 0   # 0=quadrado 1=triângulo

    @property
    def player_force(self):
        return (0.0, -60.0) if self._phase == 2 else None

    def get_aabb_list(self):
        if self._phase == 0:
            # Coluna de feixe — única zona vulnerável
            sx = max(0.0, self.spot_x - self._SPOT_W / 2)
            ex = min(float(SCREEN_W), self.spot_x + self._SPOT_W / 2)
            return [(sx, 0.0, ex, self.y + self.size)]
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.invulnerable = False
            self._fire_acc = 0.0; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self._fire_acc = 0.0; self.phase_t = 0.0

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._fire_acc += dt
        spd = diff.speed_mult if diff else 1.0
        self.x += (px - self.x) * 1.2 * dt
        self.x = max(100.0, min(float(SCREEN_W) - 100.0, self.x))

        if self._phase == 0:
            self.spot_x += self._SWEEP_SPD * self._spot_dir * spd * dt
            if self.spot_x > SCREEN_W: self.spot_x = SCREEN_W; self._spot_dir = -1
            elif self.spot_x < 0:      self.spot_x = 0;         self._spot_dir =  1
            # Vulnerável apenas quando o jogador está dentro do holofote
            self.invulnerable = abs(px - self.spot_x) > self._SPOT_W / 2
            if self._fire_acc >= 0.18 / spd:
                self._fire_acc = 0.0
                for _ in range(3):
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.spot_x + random.uniform(-18, 18)
                    pool.by[idx] = self.y + self.size
                    pool.bvx[idx] = random.uniform(-35, 35)
                    pool.bvy[idx] = random.uniform(180, 260) * spd

        elif self._phase == 1:
            self._geo_angle += 55.0 * spd * dt
            self._geo_acc   += dt
            if self._geo_acc >= 0.55 / spd:
                self._geo_acc = 0.0; self._geo_shape ^= 1
                n = 4 if self._geo_shape == 0 else 3
                for i in range(n):
                    base = math.radians(self._geo_angle + i * (360.0 / n))
                    for spread in (-0.12, 0.0, 0.12):
                        ang = base + spread
                        spd2 = 145.0 * spd
                        idx = pool.acquire()
                        if idx < 0: continue
                        pool.bx[idx] = self.x; pool.by[idx] = self.y + self.size
                        pool.bvx[idx] = math.cos(ang) * spd2
                        pool.bvy[idx] = math.sin(ang) * spd2 + 55.0
                        pool.b_type[idx] = BTYPE_BLUE if self._geo_shape == 0 else BTYPE_ORANGE

        elif self._phase == 2:
            if self._fire_acc >= 0.28 / spd:
                self._fire_acc = 0.0
                for i in range(5):
                    ang = math.radians(self.phase_t * 85.0 + i * 72.0)
                    spd2 = 195.0 * spd
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y + self.size
                    pool.bvx[idx] = math.cos(ang) * spd2
                    pool.bvy[idx] = max(30.0, math.sin(ang) * spd2)
                    pool.b_type[idx] = BTYPE_PURPLE


# ===========================================================================
# SlothBoss — Preguiça
# Fase 0: deriva aleatória, spawna bolhas-Sentinela de baixo HP
# Fase 1: invulnerável, modo escuro, spawn 3 fantasmas (sentinelas)
# Fase 2: balas grandes e lentas em ondas densas
# ===========================================================================
class SlothBoss:
    BOSS_TYPE    = BOSS_SLOTH
    PATTERN_NAME = {0: "SONAMBULISMO", 1: "TERROR NOTURNO", 2: "O DESPERTAR BRUTAL"}
    _PHASE_HP    = [0.66, 0.33]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 80.0; self.size = 40
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self.invulnerable = False
        self.dark_mode    = False
        self._bubble_cd   = 3.5
        self._drift_t     = 0.0; self._drift_vx = 0.0; self._drift_vy = 0.0
        self._ph1_done    = False
        self._brute_acc   = 0.0
        self.enm_pool: 'EnemyPool | None' = None

    def get_aabb_list(self):
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        if self.invulnerable: return
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.invulnerable = True
            self.dark_mode = True; self.phase_t = 0.0
            if self.enm_pool: self.enm_pool.clear()
            self._spawn_phantoms()
        elif self._phase == 1 and not self.invulnerable and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.dark_mode = False; self.phase_t = 0.0

    def _spawn_phantoms(self):
        if not self.enm_pool: return
        for i in range(3):
            ex = SCREEN_W * (0.25 + i * 0.25); ey = random.uniform(150, 400)
            self.enm_pool.acquire(ex, ey, ETYPE_SENTINEL)

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt
        spd = diff.speed_mult if diff else 1.0

        if self._phase == 0:
            self._drift_t += dt
            if self._drift_t >= 2.5:
                self._drift_t = 0.0
                self._drift_vx = random.uniform(-55, 55)
                self._drift_vy = random.uniform(-30, 30)
            self.x = max(80.0, min(SCREEN_W - 80.0, self.x + self._drift_vx * dt))
            self.y = max(50.0, min(200.0,            self.y + self._drift_vy * dt))
            self._bubble_cd -= dt
            if self._bubble_cd <= 0:
                self._bubble_cd = 3.5 / spd
                if self.enm_pool:
                    bx = random.uniform(100, SCREEN_W - 100)
                    by = random.uniform(120, 380)
                    self.enm_pool.acquire(bx, by, ETYPE_BUBBLE)

        elif self._phase == 1:
            # Aguarda fantasmas morrerem para despertar
            if self.enm_pool and self.enm_pool.active_count == 0 and not self._ph1_done:
                self._ph1_done    = True
                self.invulnerable = False
                self.dark_mode    = False

        elif self._phase == 2:
            self._brute_acc += dt
            rate = 0.35 / spd
            if self._brute_acc >= rate:
                self._brute_acc = 0.0
                for ang_deg in range(0, 360, 45):
                    ang = math.radians(ang_deg + self.phase_t * 18.0)
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 185.0
                    pool.bvy[idx] = math.sin(ang) * 185.0
                    pool.b_type[idx] = BTYPE_NORMAL


# ===========================================================================
# EnvyBoss — Inveja
# Fase 0: espelha a arma do jogador, dispara para baixo
# Fase 1: rouba cooldown (player_skill_penalty), tira do parry
# Fase 2: troca de arma aleatória a cada 2s (caos)
# ===========================================================================
class EnvyBoss:
    BOSS_TYPE    = BOSS_ENVY
    PATTERN_NAME = {0: "O ESPELHO", 1: "O LADRÃO", 2: "A CÓPIA IMPERFEITA"}
    _PHASE_HP    = [0.66, 0.33]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 60.0; self.size = 32
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self.invulnerable = False
        self._player_weapon = cfg.weapon
        self._fire_acc      = 0.0
        self._cycle_weapon  = 0
        self._cycle_timer   = 0.0
        self.player_skill_penalty = 0.0   # slowdown do skill_cd (lido por main.py)

    def get_aabb_list(self):
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1
            self.player_skill_penalty = 0.50; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2
            self.player_skill_penalty = 0.0; self.phase_t = 0.0

    def _fire_mirrored(self, pool, spd_mult):
        bsy = self.y + self.size
        w = self._player_weapon
        if w == WEAPON_DEFAULT:
            idx = pool.acquire()
            if idx >= 0:
                pool.bx[idx] = self.x; pool.by[idx] = bsy
                pool.bvx[idx] = 0.0;   pool.bvy[idx] = 230.0 * spd_mult
        elif w == WEAPON_SPREAD:
            for a in (-25, -12, 0, 12, 25):
                rad = math.radians(90.0 + a)
                idx = pool.acquire()
                if idx < 0: continue
                pool.bx[idx] = self.x; pool.by[idx] = bsy
                pool.bvx[idx] = math.cos(rad) * 185.0 * spd_mult
                pool.bvy[idx] = math.sin(rad) * 185.0 * spd_mult
                pool.b_type[idx] = BTYPE_ORANGE
        elif w == WEAPON_NEEDLE:
            idx = pool.acquire()
            if idx >= 0:
                pool.bx[idx] = self.x; pool.by[idx] = bsy
                pool.bvx[idx] = 0.0;   pool.bvy[idx] = 480.0 * spd_mult
                pool.b_type[idx] = BTYPE_BLUE
        elif w in (WEAPON_BURST, WEAPON_CHARGED):
            for off in (-12, 0, 12):
                idx = pool.acquire()
                if idx < 0: continue
                pool.bx[idx] = self.x + off; pool.by[idx] = bsy
                pool.bvx[idx] = 0.0; pool.bvy[idx] = 210.0 * spd_mult
        elif w == WEAPON_HOMING:
            arc = math.radians(30)
            for _ in range(4):
                ang = math.radians(90.0) + random.uniform(-arc, arc)
                idx = pool.acquire()
                if idx < 0: continue
                pool.bx[idx] = self.x; pool.by[idx] = bsy
                pool.bvx[idx] = math.cos(ang) * 200.0 * spd_mult
                pool.bvy[idx] = math.sin(ang) * 200.0 * spd_mult
                pool.b_type[idx] = BTYPE_PURPLE
                pool.btimer[idx] = 2.0

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._fire_acc += dt
        spd = diff.speed_mult if diff else 1.0
        self.x += (px - self.x) * 1.8 * dt
        self.x = max(60.0, min(float(SCREEN_W) - 60.0, self.x))

        if self._phase == 0:
            if self._fire_acc >= 0.22 / spd:
                self._fire_acc = 0.0; self._fire_mirrored(pool, spd)
        elif self._phase == 1:
            if self._fire_acc >= 0.35 / spd:
                self._fire_acc = 0.0
                for a in range(0, 360, 60):
                    ang = math.radians(a); idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 140.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 140.0 * spd
                    pool.b_type[idx] = BTYPE_BLUE
        elif self._phase == 2:
            self._cycle_timer += dt
            if self._cycle_timer >= 2.0 / spd:
                self._cycle_timer = 0.0
                self._cycle_weapon = (self._cycle_weapon + 1) % 4
            if self._fire_acc >= 0.30 / spd:
                self._fire_acc = 0.0
                _w_saved = self._player_weapon
                self._player_weapon = [WEAPON_SPREAD, WEAPON_NEEDLE,
                                        WEAPON_BURST, WEAPON_HOMING][self._cycle_weapon]
                self._fire_mirrored(pool, spd)
                self._player_weapon = _w_saved


# ===========================================================================
# GluttonyBoss — Gula
# Fase 0: sucção fraca (player_force ascendente) + anéis orbitais
# Fase 1: sucção forte + fileiras horizontais de balas (dentes)
# Fase 2: gravidade invertida (player empurrado para baixo) + ricochetes veneno
# ===========================================================================
class GluttonyBoss:
    BOSS_TYPE    = BOSS_GLUTTONY
    PATTERN_NAME = {0: "BURACO NEGRO", 1: "FORNALHA", 2: "REGURGITAR"}
    _PHASE_HP    = [0.66, 0.33]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 50.0; self.size = 44
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self._orb_angle   = 0.0
        self._orb_fire    = 0.0
        self._teeth_acc   = 0.0
        self._reg_acc     = 0.0

    @property
    def player_force(self):
        if   self._phase == 0: return (0.0, -48.0)
        elif self._phase == 1: return (0.0, -85.0)
        elif self._phase == 2: return (0.0,  70.0)
        return None

    def get_aabb_list(self):
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.phase_t = 0.0

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt
        spd = diff.speed_mult if diff else 1.0
        self.x += (px - self.x) * 0.6 * dt
        self.x = max(120.0, min(float(SCREEN_W) - 120.0, self.x))

        if self._phase == 0:
            # Anéis orbitais de balas ao redor do boss
            self._orb_angle += 80.0 * spd * dt
            self._orb_fire  += dt
            if self._orb_fire >= 0.65 / spd:
                self._orb_fire = 0.0
                for i in range(8):
                    ang = math.radians(self._orb_angle + i * 45.0)
                    r = 100.0
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x + math.cos(ang) * r
                    pool.by[idx] = self.y + math.sin(ang) * r
                    # Velocidade tangencial (órbita) com deriva descendente
                    pool.bvx[idx] = -math.sin(ang) * 125.0
                    pool.bvy[idx] =  math.cos(ang) * 125.0 + 55.0

        elif self._phase == 1:
            self._teeth_acc += dt
            if self._teeth_acc >= 0.8 / spd:
                self._teeth_acc = 0.0
                gy = random.uniform(80, 200)
                gap = random.uniform(180, 260)
                gap_cx = random.uniform(gap / 2, SCREEN_W - gap / 2)
                step = 50.0
                x = 0.0
                while x < SCREEN_W:
                    if abs(x - gap_cx) > gap / 2:
                        idx = pool.acquire()
                        if idx >= 0:
                            pool.bx[idx] = x; pool.by[idx] = gy
                            pool.bvx[idx] = 0.0; pool.bvy[idx] = 110.0 * spd
                    x += step

        elif self._phase == 2:
            self._reg_acc += dt
            if self._reg_acc >= 0.20 / spd:
                self._reg_acc = 0.0
                ang = random.uniform(0, TWO_PI)
                idx = pool.acquire()
                if idx >= 0:
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    s = 170.0 * spd
                    pool.bvx[idx] = math.cos(ang) * s
                    pool.bvy[idx] = math.sin(ang) * s
                    pool.b_type[idx] = BTYPE_ORANGE
                    pool.b_bounces[idx] = 3


# ===========================================================================
# GreedBoss — Avareza
# Fase 0: paredes verticais dividem a arena em corredores
# Fase 1: moedas estáticas que explodem ao ser atingidas pelo jogador
# Fase 2: borda de balas que encolhe + ricochetes internos
# ===========================================================================
class GreedBoss:
    BOSS_TYPE    = BOSS_GREED
    PATTERN_NAME = {0: "CORREDORES DE OURO", 1: "O PEDÁGIO", 2: "ORDEM DE DESPEJO"}
    _PHASE_HP    = [0.66, 0.33]
    MAX_COINS    = 32

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 60.0; self.size = 36
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        # Fase 0 — paredes
        self.wall_x = [SCREEN_W * 0.33, SCREEN_W * 0.67]
        self._wall_shift_t = 0.0
        self._fire_acc = 0.0
        # Fase 1 — moedas (pool pré-alocado zero-GC)
        self.coin_x      = np.zeros(self.MAX_COINS, dtype=np.float32)
        self.coin_y      = np.zeros(self.MAX_COINS, dtype=np.float32)
        self.coin_active = np.zeros(self.MAX_COINS, dtype=np.bool_)
        self._coin_free: list = list(range(self.MAX_COINS - 1, -1, -1))
        self._coin_cd    = 0.0
        # Fase 2 — borda encolhendo
        self.border_inset = 0.0
        self._border_fire = 0.0

    def get_aabb_list(self):
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.phase_t = 0.0; self.border_inset = 0.0

    def coin_acquire(self, x, y):
        if not self._coin_free: return
        idx = self._coin_free.pop()
        self.coin_x[idx] = x; self.coin_y[idx] = y; self.coin_active[idx] = True

    def coin_explode(self, idx: int, pool: 'BulletPool'):
        cx, cy = float(self.coin_x[idx]), float(self.coin_y[idx])
        self.coin_active[idx] = False; self._coin_free.append(idx)
        for k in range(8):
            ang = k * (TWO_PI / 8.0)
            bidx = pool.acquire()
            if bidx < 0: continue
            pool.bx[bidx] = cx; pool.by[bidx] = cy
            pool.bvx[bidx] = math.cos(ang) * 200.0
            pool.bvy[bidx] = math.sin(ang) * 200.0
            pool.b_type[bidx] = BTYPE_ORANGE

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._fire_acc += dt
        spd = diff.speed_mult if diff else 1.0
        self.x += (px - self.x) * 0.8 * dt
        self.x = max(80.0, min(float(SCREEN_W) - 80.0, self.x))

        if self._phase == 0:
            self._wall_shift_t += dt
            if self._wall_shift_t >= 4.0:
                self._wall_shift_t = 0.0
                self.wall_x[0] = random.uniform(SCREEN_W * 0.20, SCREEN_W * 0.38)
                self.wall_x[1] = random.uniform(SCREEN_W * 0.62, SCREEN_W * 0.80)
            # Dispara rafagas nos corredores perigosos (esquerda e direita)
            if self._fire_acc >= 0.60 / spd:
                self._fire_acc = 0.0
                for cx in (self.wall_x[0] / 2, (self.wall_x[1] + SCREEN_W) / 2):
                    for _ in range(4):
                        idx = pool.acquire()
                        if idx < 0: break
                        pool.bx[idx] = cx + random.uniform(-30, 30)
                        pool.by[idx] = 0.0
                        pool.bvx[idx] = random.uniform(-25, 25)
                        pool.bvy[idx] = random.uniform(160, 230) * spd

        elif self._phase == 1:
            self._coin_cd -= dt
            if self._coin_cd <= 0:
                self._coin_cd = 1.8 / spd
                self.coin_acquire(random.uniform(80, SCREEN_W - 80),
                                  random.uniform(150, SCREEN_H - 150))
            if self._fire_acc >= 0.90 / spd:
                self._fire_acc = 0.0
                ang = math.atan2(py - self.y, px - self.x)
                for off in (-0.15, 0.0, 0.15):
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang + off) * 155.0 * spd
                    pool.bvy[idx] = math.sin(ang + off) * 155.0 * spd
                    pool.b_type[idx] = BTYPE_BLUE

        elif self._phase == 2:
            self.border_inset = min(180.0, self.border_inset + 12.0 * dt)
            self._border_fire += dt
            if self._border_fire >= 0.15 / spd:
                self._border_fire = 0.0
                bi = self.border_inset
                cx_r = random.choice(
                    [random.uniform(bi, bi + 30),
                     random.uniform(SCREEN_W - bi - 30, SCREEN_W - bi),
                     random.uniform(bi, SCREEN_W - bi),
                     random.uniform(bi, SCREEN_W - bi)]
                )
                cy_r = random.choice(
                    [bi, SCREEN_H - bi, random.uniform(bi, bi + 30),
                     random.uniform(SCREEN_H - bi - 30, SCREEN_H - bi)]
                )
                ang = random.uniform(0, TWO_PI)
                idx = pool.acquire()
                if idx >= 0:
                    pool.bx[idx] = cx_r; pool.by[idx] = cy_r
                    pool.bvx[idx] = math.cos(ang) * 180.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 180.0 * spd
                    pool.b_type[idx] = BTYPE_ORANGE
                    pool.b_bounces[idx] = 3


# ===========================================================================
# LustBoss — Luxúria
# Fase 0: zonas de névoa lenta (HazardPool) + adagas rápidas
# Fase 1: força magnética ascendente + padrões de coração giratórios
# Fase 2: flores decorativas (visual poluição) + agulhas quase invisíveis
# ===========================================================================
class LustBoss:
    BOSS_TYPE    = BOSS_LUST
    PATTERN_NAME = {0: "NÉVOA DE FEROMÔNIOS", 1: "ATRAÇÃO FATAL", 2: "O TRUQUE DE MÁGICA"}
    _PHASE_HP    = [0.66, 0.33]

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 55.0; self.size = 32
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self._fog_cd      = 2.0
        self._dagger_acc  = 0.0
        self._heart_angle = 0.0
        self._heart_acc   = 0.0
        self._flower_acc  = 0.0
        self._needle_acc  = 0.0
        # Hazard spawn requests — drenados pelo game loop (zero-GC)
        self._hz_n = 0
        self._hz_x = np.zeros(4, dtype=np.float32)
        self._hz_y = np.zeros(4, dtype=np.float32)

    @property
    def controls_inverted(self) -> bool:
        return not self.in_prep and self._phase == 1

    @property
    def player_force(self):
        return (0.0, -65.0) if self._phase == 1 else None

    def get_aabb_list(self):
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.phase_t = 0.0

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._dagger_acc += dt
        spd = diff.speed_mult if diff else 1.0
        self.x += (px - self.x) * 2.0 * dt
        self.x = max(80.0, min(float(SCREEN_W) - 80.0, self.x))

        if self._phase == 0:
            self._fog_cd -= dt
            if self._fog_cd <= 0:
                self._fog_cd = 2.5 / spd
                if self._hz_n < 4:
                    self._hz_x[self._hz_n] = random.uniform(120, SCREEN_W - 120)
                    self._hz_y[self._hz_n] = random.uniform(150, SCREEN_H - 100)
                    self._hz_n += 1
            if self._dagger_acc >= 0.40 / spd:
                self._dagger_acc = 0.0
                ang = math.atan2(py - self.y, px - self.x) + random.uniform(-0.3, 0.3)
                idx = pool.acquire()
                if idx >= 0:
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 340.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 340.0 * spd
                    pool.b_type[idx] = BTYPE_BLUE

        elif self._phase == 1:
            self._heart_angle += 45.0 * spd * dt
            self._heart_acc   += dt
            if self._heart_acc >= 0.55 / spd:
                self._heart_acc = 0.0
                for i in range(6):
                    ang = math.radians(self._heart_angle + i * 60.0)
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 165.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 165.0 * spd
                    pool.b_type[idx] = BTYPE_ORANGE

        elif self._phase == 2:
            self._flower_acc += dt; self._needle_acc += dt
            # Flores decorativas — balas grandes e lentas (visual poluição, baixo dano)
            if self._flower_acc >= 0.45 / spd:
                self._flower_acc = 0.0
                for i in range(12):
                    ang = math.radians(i * 30.0 + self.phase_t * 15.0)
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 55.0
                    pool.bvy[idx] = math.sin(ang) * 55.0
                    pool.b_type[idx] = BTYPE_ORANGE
            # Agulhas ocultas — rápidas, invisíveis
            if self._needle_acc >= 0.18 / spd:
                self._needle_acc = 0.0
                ang = math.atan2(py - self.y, px - self.x) + random.uniform(-0.4, 0.4)
                idx = pool.acquire()
                if idx >= 0:
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 420.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 420.0 * spd
                    pool.b_invisible[idx] = True


# ===========================================================================
# WrathBoss — Ira
# Fase 0: rastreia X do jogador, rafagas densas para baixo
# Fase 1: slam no chão, anéis de choque expansivos, retorna ao teto
# Fase 2: corpo em chamas ricocheteando, sem disparos (dano por contato)
# ===========================================================================
class WrathBoss:
    BOSS_TYPE    = BOSS_WRATH
    PATTERN_NAME = {0: "O SANGUE FERVE", 1: "ONDA DE CHOQUE", 2: "MODO BERSERKER"}
    _PHASE_HP    = [0.66, 0.33]
    body_r       = 26.0

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 50.0; self.size = 34
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self._fire_acc    = 0.0
        # Fase 1 — slam
        self._slam_state  = 0   # 0=top 1=diving 2=floor 3=rising
        self._slam_timer  = 0.0
        self._slam_y      = 0.0
        self._ring_y      = 0.0; self._ring_active = False; self._ring_r = 0.0
        # Fase 2 — corpo ricocheteando
        self.body_dmg_active = False
        self.body_x   = SCREEN_W / 2.0; self.body_y = SCREEN_H / 2.0
        self._body_vx = 320.0;          self._body_vy = 240.0
        self._berserker_timer = 0.0   # expira em 20s → boss morre

    def get_aabb_list(self):
        if self._phase == 2: return []    # corpo ricocheteando — sem hitbox de bala
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        if self._phase == 2: return   # invulnerável em Berserker
        self.hp = max(0.0, self.hp - n); self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.phase_t = 0.0; self._slam_state = 0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.phase_t = 0.0
            self.body_dmg_active = True; self.get_aabb_list = lambda: []

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.hp <= 0: return
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._fire_acc += dt
        spd = diff.speed_mult if diff else 1.0

        if self._phase == 0:
            # Rastreia X do jogador
            self.x += (px - self.x) * 2.5 * dt
            self.x = max(50.0, min(float(SCREEN_W) - 50.0, self.x))
            if self._fire_acc >= 0.12 / spd:
                self._fire_acc = 0.0
                for off in (-15, 0, 15):
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x + off; pool.by[idx] = self.y + self.size
                    pool.bvx[idx] = random.uniform(-20, 20)
                    pool.bvy[idx] = random.uniform(200, 280) * spd

        elif self._phase == 1:
            self._slam_timer -= dt
            if self._slam_state == 0:   # top — aguarda slam
                if self._slam_timer <= 0:
                    self._slam_state = 1; self._slam_timer = 0.4
                    self._slam_y = self.y
            elif self._slam_state == 1:  # diving
                self.y += (SCREEN_H - 80.0 - self.y) * 12.0 * dt
                if abs(self.y - (SCREEN_H - 80.0)) < 5 or self._slam_timer <= 0:
                    self.y = SCREEN_H - 80.0
                    self._slam_state = 2; self._slam_timer = 0.6
                    self._ring_y = self.y; self._ring_active = True; self._ring_r = 0.0
                    # Disparo de impacto
                    for k in range(12):
                        ang = k * (TWO_PI / 12.0)
                        idx = pool.acquire()
                        if idx < 0: break
                        pool.bx[idx] = self.x; pool.by[idx] = self.y
                        pool.bvx[idx] = math.cos(ang) * 160.0 * spd
                        pool.bvy[idx] = math.sin(ang) * 160.0 * spd
            elif self._slam_state == 2:  # floor — anel expansivo
                if self._ring_active: self._ring_r += 300.0 * dt
                if self._ring_r > max(SCREEN_W, SCREEN_H): self._ring_active = False
                if self._slam_timer <= 0:
                    self._slam_state = 3; self._slam_timer = 0.5
            elif self._slam_state == 3:  # rising back
                self.y += (50.0 - self.y) * 8.0 * dt
                if abs(self.y - 50.0) < 5 or self._slam_timer <= 0:
                    self.y = 50.0; self._slam_state = 0; self._slam_timer = 2.5 / spd
            # Rastreia X em todas as fases
            self.x += (px - self.x) * 1.8 * dt
            self.x = max(50.0, min(float(SCREEN_W) - 50.0, self.x))

        elif self._phase == 2:
            # Corpo ricocheteando — jogador deve sobreviver 20s
            self._berserker_timer += dt
            if self._berserker_timer >= 20.0:
                self.hp = 0.0   # corpo esgota — boss morre
                return
            self.body_x += self._body_vx * dt
            self.body_y += self._body_vy * dt
            if self.body_x < self.body_r or self.body_x > SCREEN_W - self.body_r:
                self._body_vx = -self._body_vx
                self.body_x = max(self.body_r, min(SCREEN_W - self.body_r, self.body_x))
            if self.body_y < self.body_r or self.body_y > SCREEN_H - self.body_r:
                self._body_vy = -self._body_vy
                self.body_y = max(self.body_r, min(SCREEN_H - self.body_r, self.body_y))
            # Aceleração crescente
            acc = 1.0 + self.phase_t * 0.08
            self._body_vx = math.copysign(min(abs(self._body_vx) * acc, 600.0), self._body_vx)
            self._body_vy = math.copysign(min(abs(self._body_vy) * acc, 600.0), self._body_vy)


# ===========================================================================
# SinBoss — Pecado Original (chefe final, 4 fases)
# Fase 0: Quimera — fantasmas + minas + gaiola encolhendo + ricochetes
# Fase 1: Corrupção — screen_wrap ativo; cascatas infinitas
# Fase 2: Pureza Matemática — 7 espirais simultâneas, quase sem espaço
# Fase 3: O Sétimo Selo — invulnerável 30s; balas roxas de aproximação;
#          ao expirar: hp→0 (aciona morte normal)
# ===========================================================================
class SinBoss:
    BOSS_TYPE    = BOSS_SIN
    PATTERN_NAME = {0: "A QUIMERA",  1: "A CORRUPÇÃO",
                    2: "PUREZA MATEMÁTICA", 3: "O SÉTIMO SELO"}
    _PHASE_HP    = [0.75, 0.50, 0.25]
    _SIN_COLORS  = [
        (255, 215,   0),   # Soberba — ouro
        (80,   0, 120),    # Preguiça — roxo
        (0,  180,  60),    # Inveja — verde
        (120,  20, 20),    # Gula — carmim
        (200, 160,   0),   # Avareza — âmbar
        (220,  80, 160),   # Luxúria — rosa
        (220,  50,  20),   # Ira — laranja-vermelho
    ]
    MAX_MINES    = 64

    def __init__(self, config=None):
        cfg = config or GameConfig()
        self.hp = self.max_hp = float(cfg.boss_hp)
        self.x = SCREEN_W / 2.0; self.y = 60.0; self.size = 40
        self.flash_frames = 0; self.stun_timer = 0.0; self.in_prep = True
        self.phase_t = 0.0; self.pattern = 0; self._phase = 0
        self.invulnerable    = False
        self.survive_timer   = 0.0   # contagem regressiva no Sétimo Selo
        self._color_t        = 0.0   # para ciclar cores
        # Fase 0 — minas pré-alocadas
        self._mine_x      = np.zeros(self.MAX_MINES, dtype=np.float32)
        self._mine_y      = np.zeros(self.MAX_MINES, dtype=np.float32)
        self._mine_active = np.zeros(self.MAX_MINES, dtype=np.bool_)
        self._mine_free: list = list(range(self.MAX_MINES - 1, -1, -1))
        self._mine_cd    = 0.0
        # Fase 1 — cascata
        self._casc_acc   = 0.0
        # Fase 2 — espirais
        self._spiral_angles = np.linspace(0, TWO_PI, 7, endpoint=False)
        self._spiral_acc    = 0.0
        # Fase 3
        self._purple_acc = 0.0
        self._final_done = False
        # Cor atual (para render)
        self.color_index = 0

    @property
    def current_color(self):
        return self._SIN_COLORS[self.color_index % 7]

    def _mine_acquire(self, x, y):
        if not self._mine_free: return
        idx = self._mine_free.pop()
        self._mine_x[idx] = x; self._mine_y[idx] = y
        self._mine_active[idx] = True

    def _mine_explode(self, idx: int, pool: 'BulletPool'):
        cx, cy = float(self._mine_x[idx]), float(self._mine_y[idx])
        self._mine_active[idx] = False; self._mine_free.append(idx)
        for k in range(16):
            ang = k * (TWO_PI / 16.0)
            bidx = pool.acquire()
            if bidx < 0: continue
            pool.bx[bidx] = cx; pool.by[bidx] = cy
            pool.bvx[bidx] = math.cos(ang) * 180.0
            pool.bvy[bidx] = math.sin(ang) * 180.0

    def get_aabb_list(self):
        if self.invulnerable: return []
        h = self.size / 2
        return [(self.x - h, self.y - h, self.x + h, self.y + h)]

    def take_damage(self, n, diff):
        if self.invulnerable: return
        self.hp = max(0.01, self.hp - n)   # floor 0.01 para não acionar WIN antes do Selo
        self.flash_frames = 8
        if diff: diff.update(self.hp, self.max_hp)
        r = self.hp / self.max_hp
        if self._phase == 0 and r <= self._PHASE_HP[0]:
            self._phase = 1; self.pattern = 1; self.phase_t = 0.0
        elif self._phase == 1 and r <= self._PHASE_HP[1]:
            self._phase = 2; self.pattern = 2; self.phase_t = 0.0
        elif self._phase == 2 and r <= self._PHASE_HP[2]:
            self._phase = 3; self.pattern = 3; self.phase_t = 0.0
            self.invulnerable = True
            self.survive_timer = 30.0
            self.hp = max(0.01, self.hp)

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        if self.in_prep:
            self.phase_t += dt
            if self.phase_t >= PREP_TIME: self.in_prep = False; self.phase_t = 0.0
            return
        if self.hp <= 0 and not self.invulnerable: return
        if self.stun_timer > 0: self.stun_timer = max(0.0, self.stun_timer - dt); return
        if self.flash_frames > 0: self.flash_frames -= 1
        self.phase_t += dt; self._color_t += dt
        self.color_index = int(self._color_t * 3.0) % 7
        spd = diff.speed_mult if diff else 1.0

        # Minas — checagem de proximidade com jogador (todas as fases exceto 3)
        if self._phase < 3:
            for mi in np.where(self._mine_active)[0]:
                mi = int(mi)
                dx = px - float(self._mine_x[mi]); dy = py - float(self._mine_y[mi])
                if dx*dx + dy*dy <= 45.0**2:
                    self._mine_explode(mi, pool)

        if self._phase == 0:
            self._mine_cd -= dt
            if self._mine_cd <= 0:
                self._mine_cd = 2.2 / spd
                self._mine_acquire(random.uniform(80, SCREEN_W - 80),
                                   random.uniform(120, SCREEN_H - 120))
            # Fantasmas de dash + bolas de ricochete
            if self._casc_acc >= 0: self._casc_acc += dt
            if self._casc_acc >= 0.45 / spd:
                self._casc_acc = 0.0
                for k in range(6):
                    ang = math.radians(k * 60.0 + self.phase_t * 30.0)
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * 190.0 * spd
                    pool.bvy[idx] = math.sin(ang) * 190.0 * spd
                    pool.b_type[idx] = BTYPE_ORANGE
                    pool.b_bounces[idx] = 2

        elif self._phase == 1:
            # Cascata infinita — balas que saem pela borda reaparecem pelo outro lado
            # (screen_wrap é ativado/desativado por main.py ao detectar a fase)
            self._casc_acc += dt
            if self._casc_acc >= 0.12 / spd:
                self._casc_acc = 0.0
                ang = math.atan2(py - self.y, px - self.x) + random.uniform(-0.5, 0.5)
                for off in (-0.25, 0.0, 0.25):
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    a2 = ang + off
                    pool.bvx[idx] = math.cos(a2) * 200.0 * spd
                    pool.bvy[idx] = math.sin(a2) * 200.0 * spd

        elif self._phase == 2:
            self._spiral_acc += dt
            if self._spiral_acc >= 0.045 / spd:
                self._spiral_acc = 0.0
                self._spiral_angles += 0.04 * spd
                for i, ang in enumerate(self._spiral_angles):
                    speed_v = 160.0 * spd + i * 12.0
                    idx = pool.acquire()
                    if idx < 0: break
                    pool.bx[idx] = self.x; pool.by[idx] = self.y
                    pool.bvx[idx] = math.cos(ang) * speed_v
                    pool.bvy[idx] = math.sin(ang) * speed_v

        elif self._phase == 3:
            if self._final_done: return
            self.survive_timer -= dt
            if self.survive_timer <= 0.0:
                # Sobreviveu — chefe morre
                self.invulnerable = False
                self.hp = 0.0
                self._final_done = True
                return
            # Balas roxas de aproximação (devem se mover em direção ao jogador;
            # se o jogador fugir aumenta densidade)
            self._purple_acc += dt
            rate = max(0.08, 0.25 - (30.0 - self.survive_timer) * 0.004) / spd
            if self._purple_acc >= rate:
                self._purple_acc = 0.0
                for k in range(3):
                    ang = random.uniform(0, TWO_PI)
                    idx = pool.acquire()
                    if idx < 0: break
                    rx = SCREEN_W / 2.0 + math.cos(ang) * 320.0
                    ry = SCREEN_H / 2.0 + math.sin(ang) * 220.0
                    pool.bx[idx] = rx; pool.by[idx] = ry
                    # Mira no jogador
                    tx = px - rx; ty = py - ry
                    mag = math.sqrt(tx*tx + ty*ty) + 1.0
                    pool.bvx[idx] = tx / mag * 130.0 * spd
                    pool.bvy[idx] = ty / mag * 130.0 * spd
                    pool.b_type[idx] = BTYPE_PURPLE
                    pool.btimer[idx] = 3.0


# ===========================================================================
# DummyBoss — Saco de Pancadas para teste de DPS (apenas modo dev/cheat)
# ===========================================================================
class DummyBoss:
    BOSS_TYPE = BOSS_DUMMY
    max_hp    = 999_999.0

    def __init__(self):
        self.x  = float(SCREEN_W // 2 - BOSS_SIZE // 2)
        self.y  = float(SCREEN_H // 3)
        self.cx = self.x + BOSS_SIZE * 0.5
        self.cy = self.y + BOSS_SIZE * 0.5
        self.hp           = 999_999.0
        self.in_prep      = False
        self.phase_t      = 0.0
        self.pattern      = 0
        self.flash_frames = 0
        self.total_damage = 0.0
        self._dps_dmg     = 0.0
        self._dps_t       = 0.0
        self._dps         = 0.0
        # Floating damage numbers — 16 slots pré-alocados
        self._fn_val    = np.zeros(16, dtype=np.float32)
        self._fn_x      = np.zeros(16, dtype=np.float32)
        self._fn_y      = np.zeros(16, dtype=np.float32)
        self._fn_t      = np.zeros(16, dtype=np.float32)
        self._fn_active = np.zeros(16, dtype=np.bool_)
        self._fn_head   = 0

    def get_aabb_list(self):
        s = BOSS_SIZE
        return [(self.x - s, self.y - s, self.x + s * 2, self.y + s * 2)]

    def take_damage(self, n, diff=None):
        self.total_damage += n
        self._dps_dmg     += n
        self.flash_frames  = 8
        slot = self._fn_head % 16
        self._fn_val[slot]    = n
        self._fn_x[slot]      = self.cx + random.uniform(-28.0, 28.0)
        self._fn_y[slot]      = self.y - 8.0
        self._fn_t[slot]      = 1.8
        self._fn_active[slot] = True
        self._fn_head += 1

    def update(self, dt, pool, ep, lp, px, py, diff, pvx=0.0, pvy=0.0):
        self._dps_t += dt
        if self._dps_t >= 1.0:
            self._dps     = self._dps_dmg / self._dps_t
            self._dps_dmg = 0.0
            self._dps_t   = 0.0
        if self.flash_frames > 0:
            self.flash_frames -= 1
        alive = np.where(self._fn_active)[0]
        if alive.size:
            self._fn_y[alive] -= 40.0 * dt
            self._fn_t[alive] -= dt
            expired = alive[self._fn_t[alive] <= 0.0]
            if expired.size:
                self._fn_active[expired] = False


class ReplayRecorder:
    """
    Records (seed, [(input_bitmask, dt), ...]) for deterministic replay.
    Replay: re-seed random with the same seed and feed inputs back frame-by-frame.
    """
    def __init__(self, seed: int):
        self.seed: int   = seed
        self.frames: list = []   # list of (bitmask: int, dt: float)

    @staticmethod
    def keys_to_bitmask(keys) -> int:
        bits = 0
        for bit, k in enumerate(_KEY_BITS):
            if keys[k]: bits |= (1 << bit)
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]: bits |= (1 << _SKILL_BIT)
        if keys[pygame.K_SPACE]  or keys[pygame.K_z]:       bits |= (1 << _FIRE_BIT)
        return bits

    @staticmethod
    def bitmask_to_keys(bitmask: int) -> dict:
        """Returns a dict mirroring pygame.key.get_pressed() for the recorded keys."""
        keys: dict = {}
        for bit, k in enumerate(_KEY_BITS):
            keys[k] = bool(bitmask & (1 << bit))
        keys[pygame.K_LSHIFT] = bool(bitmask & (1 << _SKILL_BIT))
        keys[pygame.K_RSHIFT] = False
        keys[pygame.K_SPACE]  = bool(bitmask & (1 << _FIRE_BIT))
        keys[pygame.K_z]      = False
        return keys

    def record(self, keys, dt: float):
        self.frames.append((self.keys_to_bitmask(keys), dt))

    def replay_frame(self, frame_idx: int):
        """Returns (keys_dict, dt) for the given frame index, or None if out of range."""
        if frame_idx >= len(self.frames): return None
        bitmask, dt = self.frames[frame_idx]
        return self.bitmask_to_keys(bitmask), dt

    def start_replay(self):
        """Re-seed random so the replay is deterministic."""
        random.seed(self.seed)


# ===========================================================================
# SaveManager — persistência JSON (leitura/escrita apenas fora de PLAYING)
# ===========================================================================
class SaveManager:
    SAVE_PATH = "save.json"

    # Dificuldade → skills desbloqueadas ao vencer
    _SKILL_UNLOCKS: dict = {
        DIFF_EASY:   [SKILL_PARRY],
        DIFF_NORMAL: [SKILL_FOCUS],
        DIFF_HARD:   [],   # HARD skills via conquistas
    }

    def __init__(self):
        self.highest_cleared_diff: int = 0
        self.unlocked_skills: list     = [SKILL_NONE, SKILL_DASH]
        self.unlocked_mutators: list   = []    # mutadores desbloqueados via conquistas
        self.omega_boss_unlocked: bool = False
        self.sins_rush_cleared: bool = False   # True = ABISSAL desbloqueado
        self.stats: dict = {
            "total_deaths":       0,
            "best_survival_hard": 0.0,
            "total_parries":      0,
        }
        self.achievements: dict = {
            "total_grazes":      0,
            "no_hit_wins":       0,
            "mutator_hard_wins": 0,
        }
        self.achieved: set = set()   # IDs of unlocked achievement entries
        self.settings: dict = {
            "fullscreen":   False,
            "screen_shake": True,
            "show_hitbox":  False,
        }
        self.mastery: dict = {
            "dash_graze_count":  0,
            "parry_burst_max":   0,
            "emp_bullets_max":   0,
            "oc_dmg_max":        0.0,
            "shield_perfects":   0,
            "blink_boss_pass":   False,
            "timedil_close":     False,
        }
        self.skill_plus_unlocked: set = set()
        self.weapon_mastery: dict = {
            "default_hits":    0,
            "spread_close":    0,
            "needle_phase":    0,
            "charged_multi":   0,
            "burst_twins":     0,
            "homing_nohit":    0,
            "flak_bullets":    0,
            "chakram_round":   0,
            "plasma_contact":  0.0,
            "orbit_damage":    0.0,
        }
        self.weapon_plus_unlocked: set = set()
        self._load()

    # ------------------------------------------------------------------
    def _load(self):
        try:
            with open(self.SAVE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.highest_cleared_diff = int(data.get("highest_cleared_diff", 0))
            raw = data.get("unlocked_skills", [SKILL_NONE, SKILL_DASH])
            self.unlocked_skills = sorted(set([SKILL_NONE] + [int(s) for s in raw]))
            self.unlocked_mutators = [int(m) for m in data.get("unlocked_mutators", [])]
            self.omega_boss_unlocked = bool(data.get("omega_boss_unlocked", False))
            self.sins_rush_cleared = bool(data.get("sins_rush_cleared", False))
            for k, v in data.get("stats", {}).items():
                if k in self.stats:
                    self.stats[k] = type(self.stats[k])(v)
            for k, v in data.get("achievements", {}).items():
                if k in self.achievements:
                    self.achievements[k] = type(self.achievements[k])(v)
            for k, v in data.get("settings", {}).items():
                if k in self.settings:
                    self.settings[k] = bool(v)
            self.achieved = set(data.get("achieved", []))
            saved_mastery = data.get("mastery", {})
            for k, v in saved_mastery.items():
                if k in self.mastery:
                    self.mastery[k] = type(self.mastery[k])(v)
            self.skill_plus_unlocked = set(int(x) for x in data.get("skill_plus_unlocked", []))
            saved_wmastery = data.get("weapon_mastery", {})
            for k, v in saved_wmastery.items():
                if k in self.weapon_mastery:
                    self.weapon_mastery[k] = type(self.weapon_mastery[k])(v)
            self.weapon_plus_unlocked = set(int(x) for x in data.get("weapon_plus_unlocked", []))
        except Exception:
            pass

    def persist(self):
        try:
            with open(self.SAVE_PATH, 'w', encoding='utf-8') as f:
                json.dump({
                    "highest_cleared_diff":    self.highest_cleared_diff,
                    "unlocked_skills":         self.unlocked_skills,
                    "unlocked_mutators":       self.unlocked_mutators,
                    "omega_boss_unlocked":     self.omega_boss_unlocked,
                    "sins_rush_cleared":       self.sins_rush_cleared,
                    "stats":                   self.stats,
                    "achievements":            self.achievements,
                    "achieved":                sorted(self.achieved),
                    "settings":                self.settings,
                    "mastery":                 self.mastery,
                    "skill_plus_unlocked":     sorted(self.skill_plus_unlocked),
                    "weapon_mastery":          self.weapon_mastery,
                    "weapon_plus_unlocked":    sorted(self.weapon_plus_unlocked),
                }, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def diff_locked(self, diff: int) -> bool:
        if diff == DIFF_TEST:    return True          # sempre bloqueado — só cheat
        if diff == DIFF_ABISSAL: return not self.sins_rush_cleared
        return diff > self.highest_cleared_diff

    def skill_locked(self, skill: int) -> bool:
        return skill not in self.unlocked_skills

    def mutator_locked(self, mutator: int) -> bool:
        """CLAUSTROFOBIA precisa ser desbloqueado via conquista; outros sempre livres."""
        if mutator == MUTATOR_CLAUSTROFOBIA:
            return mutator not in self.unlocked_mutators
        return False

    # ------------------------------------------------------------------
    def _check_all_achievements(self, diff: int, elapsed: float, total_hits: int,
                                mutator_count: int, skill: int, boss_type: int,
                                new_unlocks: list, twins_delta: float = -1.0,
                                minion_kills: int = -1, twins_no_dmg_t: float = 0.0):
        """Grant achievement IDs and skill/mutator unlocks. Mutates new_unlocks in place."""
        def _ach(aid: str, display: str, skill_unlock: int = -1,
                 mutator_unlock: int = -1, flag: str = ""):
            if aid in self.achieved:
                return
            self.achieved.add(aid)
            new_unlocks.append(f"Conquista: {display}!")
            if skill_unlock >= 0 and skill_unlock not in self.unlocked_skills:
                self.unlocked_skills.append(skill_unlock)
                new_unlocks.append(
                    f"Habilidade desbloqueada: {GameConfig.SKILL_LABELS[skill_unlock]}")
            if mutator_unlock >= 0 and mutator_unlock not in self.unlocked_mutators:
                self.unlocked_mutators.append(mutator_unlock)
                new_unlocks.append(
                    f"Mutador desbloqueado: {GameConfig.MUTATOR_LABELS[mutator_unlock]}")
        # Difficulty-based
        if diff >= DIFF_EASY:   _ach("easy_win",    "Iniciante")
        if diff >= DIFF_NORMAL: _ach("normal_win",  "Veterano")
        if diff >= DIFF_HARD:   _ach("hard_win",    "Mestre")

        # Counter-based
        if self.achievements["total_grazes"] >= 100:
            _ach("grazes_100",  "Esquivador",      skill_unlock=SKILL_EMP)
        if self.stats["total_parries"] >= 50:
            _ach("parries_50",  "Espadachim",      skill_unlock=SKILL_SHIELD)
        if self.stats["total_parries"] >= 200:
            _ach("parries_200", "Senhor do Parry")

        # Per-win conditions
        if total_hits == 0:
            _ach("no_hit_win",    "Perfecionista",  skill_unlock=SKILL_BLINK)
        if diff == DIFF_HARD and mutator_count >= 1:
            _ach("mutator_hard",  "Risco Máximo",   skill_unlock=SKILL_OVERCLOCK)
        if diff == DIFF_HARD and mutator_count >= 3:
            _ach("omega_unlock",  "Imparável")
        if diff == DIFF_HARD and elapsed < 180.0:
            _ach("speed_hard",    "Speed Runner")
        if mutator_count == N_MUTATORS:
            _ach("all_mutators",  "Além do Limite")
        if skill == SKILL_NONE:
            _ach("no_skill",      "Intocável")
        if boss_type == BOSS_OMEGA and diff == DIFF_HARD:
            _ach("omega_hard",    "O Fim")

        # Novas conquistas — TwinsBoss e SummonerBoss
        if boss_type == BOSS_TWINS and 0.0 <= twins_delta < 3.0:
            _ach("equilibrio_perfeito", "Equilíbrio Perfeito",
                 skill_unlock=SKILL_TIMEDILATION)
        if boss_type == BOSS_SUMMONER and 0 <= minion_kills < 10:
            _ach("pacifista_elite", "Pacifista de Elite",
                 mutator_unlock=MUTATOR_CLAUSTROFOBIA)
    def is_skill_plus_unlocked(self, skill_id: int) -> bool:
        return skill_id in self.skill_plus_unlocked

    _SP_ACH_IDS = {
        SKILL_DASH:         "sp_dash",
        SKILL_PARRY:        "sp_parry",
        SKILL_EMP:          "sp_emp",
        SKILL_BLINK:        "sp_blink",
        SKILL_OVERCLOCK:    "sp_overclock",
        SKILL_SHIELD:       "sp_shield",
        SKILL_TIMEDILATION: "sp_timedil",
    }

    def _check_mastery_unlocks(self, new_unlocks: list):
        """Grant skill+ unlocks when mastery thresholds are reached."""
        _counter_checks = (
            (SKILL_DASH,         "dash_graze_count",  MASTERY_DASH_GRAZES),
            (SKILL_PARRY,        "parry_burst_max",   MASTERY_PARRY_BURST),
            (SKILL_EMP,          "emp_bullets_max",   MASTERY_EMP_BULLETS),
            (SKILL_OVERCLOCK,    "oc_dmg_max",        MASTERY_OC_DMG),
            (SKILL_SHIELD,       "shield_perfects",   MASTERY_SHIELD_PERFECT),
        )
        _bool_checks = (
            (SKILL_BLINK,        "blink_boss_pass"),
            (SKILL_TIMEDILATION, "timedil_close"),
        )
        for skill_id, key, threshold in _counter_checks:
            if skill_id not in self.skill_plus_unlocked and self.mastery[key] >= threshold:
                self.skill_plus_unlocked.add(skill_id)
                self.achieved.add(self._SP_ACH_IDS[skill_id])
                new_unlocks.append(
                    f"★ Maestria: {GameConfig.SKILL_LABELS[skill_id]}+ desbloqueado!")
        for skill_id, key in _bool_checks:
            if skill_id not in self.skill_plus_unlocked and self.mastery[key]:
                self.skill_plus_unlocked.add(skill_id)
                self.achieved.add(self._SP_ACH_IDS[skill_id])
                new_unlocks.append(
                    f"★ Maestria: {GameConfig.SKILL_LABELS[skill_id]}+ desbloqueado!")

    def is_weapon_plus_unlocked(self, weapon_id: int) -> bool:
        return weapon_id in self.weapon_plus_unlocked

    _WP_ACH_IDS = {
        WEAPON_DEFAULT: "wp_default",
        WEAPON_SPREAD:  "wp_spread",
        WEAPON_NEEDLE:  "wp_needle",
        WEAPON_CHARGED: "wp_charged",
        WEAPON_BURST:   "wp_burst",
        WEAPON_HOMING:  "wp_homing",
        WEAPON_FLAK:    "wp_flak",
        WEAPON_CHAKRAM: "wp_chakram",
        WEAPON_PLASMA:  "wp_plasma",
        WEAPON_ORBIT:   "wp_orbit",
    }

    def _check_weapon_mastery_unlocks(self, new_unlocks: list):
        """Grant weapon+ unlocks when weapon mastery thresholds are reached."""
        _checks = (
            (WEAPON_DEFAULT, "default_hits",   MASTERY_W_DEFAULT_HITS),
            (WEAPON_SPREAD,  "spread_close",   MASTERY_W_SPREAD_CLOSE),
            (WEAPON_NEEDLE,  "needle_phase",   MASTERY_W_NEEDLE_PHASE),
            (WEAPON_CHARGED, "charged_multi",  MASTERY_W_CHARGED_MULTI),
            (WEAPON_BURST,   "burst_twins",    MASTERY_W_BURST_TWINS),
            (WEAPON_HOMING,  "homing_nohit",   MASTERY_W_HOMING_NOHIT),
            (WEAPON_FLAK,    "flak_bullets",   MASTERY_W_FLAK_BULLETS),
            (WEAPON_CHAKRAM, "chakram_round",  MASTERY_W_CHAKRAM_ROUND),
        )
        for wid, key, threshold in _checks:
            if wid not in self.weapon_plus_unlocked and self.weapon_mastery[key] >= threshold:
                self.weapon_plus_unlocked.add(wid)
                self.achieved.add(self._WP_ACH_IDS[wid])
                new_unlocks.append(
                    f"★ Maestria: {GameConfig.WEAPON_LABELS[wid]}+ desbloqueado!")
        # Float checks
        if WEAPON_PLASMA not in self.weapon_plus_unlocked and \
                self.weapon_mastery["plasma_contact"] >= MASTERY_W_PLASMA_CONT:
            self.weapon_plus_unlocked.add(WEAPON_PLASMA)
            self.achieved.add(self._WP_ACH_IDS[WEAPON_PLASMA])
            new_unlocks.append(
                f"★ Maestria: {GameConfig.WEAPON_LABELS[WEAPON_PLASMA]}+ desbloqueado!")
        if WEAPON_ORBIT not in self.weapon_plus_unlocked and \
                self.weapon_mastery["orbit_damage"] >= MASTERY_W_ORBIT_DAMAGE:
            self.weapon_plus_unlocked.add(WEAPON_ORBIT)
            self.achieved.add(self._WP_ACH_IDS[WEAPON_ORBIT])
            new_unlocks.append(
                f"★ Maestria: {GameConfig.WEAPON_LABELS[WEAPON_ORBIT]}+ desbloqueado!")

    def update_weapon_mastery(self, player) -> list:
        """Accumulate weapon mastery from completed run. Returns new weapon+ unlock strings."""
        new_unlocks: list = []
        wp = getattr(player, 'weapon', WEAPON_DEFAULT)
        if wp == WEAPON_DEFAULT:
            self.weapon_mastery["default_hits"] = max(
                self.weapon_mastery["default_hits"],
                getattr(player, '_wm_consec_hits', 0))
        elif wp == WEAPON_SPREAD:
            self.weapon_mastery["spread_close"] += getattr(player, '_wm_close_events', 0)
        elif wp == WEAPON_NEEDLE:
            self.weapon_mastery["needle_phase"] += getattr(player, '_wm_needle_phase_ok', 0)
        elif wp == WEAPON_CHARGED:
            self.weapon_mastery["charged_multi"] += getattr(player, '_wm_charged_multi', 0)
        elif wp == WEAPON_BURST:
            self.weapon_mastery["burst_twins"] += getattr(player, '_wm_burst_twins', 0)
        elif wp == WEAPON_HOMING:
            self.weapon_mastery["homing_nohit"] += getattr(player, '_wm_homing_nohit_w', 0)
        elif wp == WEAPON_FLAK:
            self.weapon_mastery["flak_bullets"] = max(
                self.weapon_mastery["flak_bullets"],
                getattr(player, '_wm_flak_kills', 0))
        elif wp == WEAPON_CHAKRAM:
            self.weapon_mastery["chakram_round"] += getattr(player, '_wm_chakram_round', 0)
        elif wp == WEAPON_PLASMA:
            self.weapon_mastery["plasma_contact"] = max(
                self.weapon_mastery["plasma_contact"],
                getattr(player, '_wm_plasma_contact', 0.0))
        elif wp == WEAPON_ORBIT:
            self.weapon_mastery["orbit_damage"] += getattr(player, '_wm_orbit_dmg', 0.0)
        self._check_weapon_mastery_unlocks(new_unlocks)
        return new_unlocks

    def update_mastery(self, player) -> list:
        """Accumulate mastery data from a completed run. Returns new skill+ unlock strings."""
        new_unlocks: list = []
        sk = getattr(player, 'skill', SKILL_NONE)
        if sk == SKILL_DASH:
            self.mastery["dash_graze_count"] += getattr(player, '_graze_dash_acc', 0)
        elif sk == SKILL_PARRY:
            self.mastery["parry_burst_max"] = max(
                self.mastery["parry_burst_max"],
                getattr(player, '_parry_burst_max', 0))
        elif sk == SKILL_EMP:
            self.mastery["emp_bullets_max"] = max(
                self.mastery["emp_bullets_max"],
                getattr(player, '_emp_max_session', 0))
        elif sk == SKILL_OVERCLOCK:
            self.mastery["oc_dmg_max"] = max(
                self.mastery["oc_dmg_max"],
                getattr(player, '_oc_dmg_max', 0.0))
        elif sk == SKILL_SHIELD:
            self.mastery["shield_perfects"] += getattr(player, '_shield_perfect_acc', 0)
        elif sk == SKILL_TIMEDILATION:
            if getattr(player, '_timedil_close_used', False):
                self.mastery["timedil_close"] = True
        # blink_boss_pass and timedil_close (for BLINK) are set directly in main.py
        self._check_mastery_unlocks(new_unlocks)
        return new_unlocks

    def on_win(self, diff: int, elapsed: float, parries: int,
               graze_count: int = 0, mutator_count: int = 0,
               total_hits: int = 0, skill: int = 0, boss_type: int = 0,
               twins_delta: float = -1.0, minion_kills: int = -1,
               twins_no_dmg_t: float = 0.0, sins_rush: bool = False) -> list:
        """Apply win rewards. Returns list of human-readable unlock strings."""
        self.stats["total_parries"] += parries
        if diff == DIFF_HARD:
            self.stats["best_survival_hard"] = max(
                self.stats["best_survival_hard"], elapsed)

        self.achievements["total_grazes"] += graze_count
        if total_hits == 0:
            self.achievements["no_hit_wins"] += 1
        if diff == DIFF_HARD and mutator_count >= 1:
            self.achievements["mutator_hard_wins"] += 1

        new_unlocks: list = []

        next_diff = diff + 1
        if next_diff in (DIFF_NORMAL, DIFF_HARD, DIFF_EXPERT) and self.highest_cleared_diff < next_diff:
            self.highest_cleared_diff = next_diff
            new_unlocks.append(
                f"Dificuldade desbloqueada: {GameConfig.DIFF_LABELS[next_diff]}")
        if sins_rush and not self.sins_rush_cleared:
            self.sins_rush_cleared = True
            new_unlocks.append(f"Dificuldade desbloqueada: {GameConfig.DIFF_LABELS[DIFF_ABISSAL]}")

        for sk in self._SKILL_UNLOCKS.get(diff, []):
            if sk not in self.unlocked_skills:
                self.unlocked_skills.append(sk)
                new_unlocks.append(f"Habilidade desbloqueada: {GameConfig.SKILL_LABELS[sk]}")

        self._check_all_achievements(diff, elapsed, total_hits, mutator_count,
                                     skill, boss_type, new_unlocks,
                                     twins_delta=twins_delta,
                                     minion_kills=minion_kills,
                                     twins_no_dmg_t=twins_no_dmg_t)

        if diff == DIFF_HARD and mutator_count >= 3 and not self.omega_boss_unlocked:
            self.omega_boss_unlocked = True
            new_unlocks.append("★ Boss secreto desbloqueado: ÔMEGA!")

        self.persist()
        return new_unlocks

    def on_death(self):
        self.stats["total_deaths"] += 1
        self.persist()

    # ------------------------------------------------------------------  Dev cheats
    _ALL_ACHIEVEMENT_IDS = (
        # Visible
        "easy_win", "normal_win", "hard_win", "grazes_100", "parries_50",
        "no_hit_win", "mutator_hard", "omega_unlock",
        "equilibrio_perfeito", "pacifista_elite",
        # Skill+
        "sp_dash", "sp_parry", "sp_emp", "sp_blink",
        "sp_overclock", "sp_shield", "sp_timedil",
        # Weapon+
        "wp_default", "wp_spread", "wp_needle", "wp_charged", "wp_burst",
        "wp_homing", "wp_flak", "wp_chakram", "wp_plasma", "wp_orbit",
        # Secrets
        "parries_200", "speed_hard", "all_mutators", "no_skill", "omega_hard",
    )

    def cheat_unlock_all(self):
        self.highest_cleared_diff    = DIFF_EXPERT
        self.sins_rush_cleared       = True
        self.unlocked_skills         = list(range(N_SKILLS))
        self.unlocked_mutators       = [MUTATOR_CLAUSTROFOBIA]
        self.omega_boss_unlocked     = True
        self.achieved                = set(self._ALL_ACHIEVEMENT_IDS)
        self.mastery = {
            "dash_graze_count":  MASTERY_DASH_GRAZES,
            "parry_burst_max":   MASTERY_PARRY_BURST,
            "emp_bullets_max":   MASTERY_EMP_BULLETS,
            "oc_dmg_max":        MASTERY_OC_DMG,
            "shield_perfects":   MASTERY_SHIELD_PERFECT,
            "blink_boss_pass":   True,
            "timedil_close":     True,
        }
        self.skill_plus_unlocked     = set(range(N_SKILLS))
        self.weapon_mastery = {
            "default_hits":    MASTERY_W_DEFAULT_HITS,
            "spread_close":    MASTERY_W_SPREAD_CLOSE,
            "needle_phase":    MASTERY_W_NEEDLE_PHASE,
            "charged_multi":   MASTERY_W_CHARGED_MULTI,
            "burst_twins":     MASTERY_W_BURST_TWINS,
            "homing_nohit":    MASTERY_W_HOMING_NOHIT,
            "flak_bullets":    MASTERY_W_FLAK_BULLETS,
            "chakram_round":   MASTERY_W_CHAKRAM_ROUND,
            "plasma_contact":  MASTERY_W_PLASMA_CONT,
            "orbit_damage":    MASTERY_W_ORBIT_DAMAGE,
        }
        self.weapon_plus_unlocked    = set(range(N_WEAPONS))
        self.persist()

    def wipe_save(self):
        self.highest_cleared_diff   = 0
        self.sins_rush_cleared      = False
        self.unlocked_skills        = [SKILL_NONE, SKILL_DASH]
        self.unlocked_mutators      = []
        self.omega_boss_unlocked    = False
        self.achieved               = set()
        self.stats = {"total_deaths": 0, "best_survival_hard": 0.0, "total_parries": 0}
        self.achievements = {"total_grazes": 0, "no_hit_wins": 0, "mutator_hard_wins": 0}
        self.mastery = {
            "dash_graze_count":  0,
            "parry_burst_max":   0,
            "emp_bullets_max":   0,
            "oc_dmg_max":        0.0,
            "shield_perfects":   0,
            "blink_boss_pass":   False,
            "timedil_close":     False,
        }
        self.skill_plus_unlocked  = set()
        self.weapon_mastery = {
            "default_hits":    0,
            "spread_close":    0,
            "needle_phase":    0,
            "charged_multi":   0,
            "burst_twins":     0,
            "homing_nohit":    0,
            "flak_bullets":    0,
            "chakram_round":   0,
            "plasma_contact":  0.0,
            "orbit_damage":    0.0,
        }
        self.weapon_plus_unlocked = set()
        self.persist()
