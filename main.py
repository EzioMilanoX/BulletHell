"""
Bullet Hell — Render + Loop
Game logic lives in entities.py  (from entities import *)
"""
import sys, math, os, json
from entities import *


# ===========================================================================
# Hot-reload balance watcher (only active in DEV MODE)
# ===========================================================================
_BAL_PATH  = "balance.json"
_bal_mtime = 0.0
_bal_check_acc = 0.0   # accumulates dt; reload check every ~1 s
_BAL: dict = {}        # populated on first load / reload


def _load_balance():
    global _BAL, _bal_mtime
    try:
        _bal_mtime = os.path.getmtime(_BAL_PATH)
        with open(_BAL_PATH, "r", encoding="utf-8") as f:
            _BAL = json.load(f)
    except Exception:
        pass


def _poll_balance(dt: float, dev_mode: bool) -> bool:
    """Call once per frame. Returns True if balance was reloaded."""
    global _bal_check_acc, _bal_mtime
    if not dev_mode:
        return False
    _bal_check_acc += dt
    if _bal_check_acc < 1.0:
        return False
    _bal_check_acc = 0.0
    try:
        mtime = os.path.getmtime(_BAL_PATH)
        if mtime != _bal_mtime:
            _load_balance()
            return True
    except Exception:
        pass
    return False


_load_balance()   # initial load at startup

# ---------------------------------------------------------------------------
# waves.json — Wave Survival definitions (loaded once at startup)
# ---------------------------------------------------------------------------
_WAVES_PATH = "waves.json"
_WAVE_DEFS: list = []


def _load_waves():
    global _WAVE_DEFS
    try:
        with open(_WAVES_PATH, "r", encoding="utf-8") as f:
            _WAVE_DEFS = json.load(f).get("waves", [])
    except Exception:
        _WAVE_DEFS = []


_load_waves()


def _b(section: str, key: str, default):
    """Read a hot-reloadable balance value; falls back to compiled constant."""
    try:
        return type(default)(_BAL[section][key])
    except (KeyError, TypeError):
        return default



# ===========================================================================
# Render — Boss variants
# ===========================================================================
def render_boss(surf: pygame.Surface, boss):
    if boss.hp <= 0 and not getattr(boss, 'invulnerable', False): return
    if isinstance(boss, NullBoss): return
    if isinstance(boss, OmegaBoss):      _render_omega_boss(surf, boss)
    elif isinstance(boss, SwarmBoss):    _render_swarm_boss(surf, boss)
    elif isinstance(boss, WallBoss):     _render_wall_boss(surf, boss)
    elif isinstance(boss, TwinsBoss):    _render_twins_boss(surf, boss)
    elif isinstance(boss, SummonerBoss): _render_summoner_boss(surf, boss)
    elif isinstance(boss, PrideBoss):    _render_pride_boss(surf, boss)
    elif isinstance(boss, SlothBoss):    _render_sloth_boss(surf, boss)
    elif isinstance(boss, EnvyBoss):     _render_envy_boss(surf, boss)
    elif isinstance(boss, GluttonyBoss): _render_gluttony_boss(surf, boss)
    elif isinstance(boss, GreedBoss):    _render_greed_boss(surf, boss)
    elif isinstance(boss, LustBoss):     _render_lust_boss(surf, boss)
    elif isinstance(boss, WrathBoss):    _render_wrath_boss(surf, boss)
    elif isinstance(boss, SinBoss):      _render_sin_boss(surf, boss)
    elif isinstance(boss, DummyBoss):    _render_dummy_boss(surf, boss)
    else:                                _render_classic_boss(surf, boss)


def _render_classic_boss(surf: pygame.Surface, boss: Boss):
    bx = int(boss.x - boss.size / 2);  by = int(boss.y - boss.size / 2)
    bs = boss.size
    body = WHITE if boss.flash_frames > 0 else MAROON
    bord = Boss.PATTERN_COLOR.get(boss.pattern, WHITE)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, bord, (bx, by, bs, bs), 2)
    pygame.draw.line(surf, bord, (int(boss.x), by), (int(boss.x), by + bs))
    pygame.draw.line(surf, bord, (bx, int(boss.y)), (bx + bs, int(boss.y)))


def _render_swarm_boss(surf: pygame.Surface, boss: SwarmBoss):
    bord = SwarmBoss.PATTERN_COLOR.get(boss.pattern, WHITE)
    body = WHITE if boss.flash_frames > 0 else (80, 20, 120)
    h = SWARM_UNIT_SIZE // 2
    for i in range(3):
        ux = int(boss.unit_x[i]);  uy = int(boss.unit_y[i])
        pygame.draw.rect(surf, body, (ux - h, uy - h, SWARM_UNIT_SIZE, SWARM_UNIT_SIZE))
        pygame.draw.rect(surf, bord, (ux - h, uy - h, SWARM_UNIT_SIZE, SWARM_UNIT_SIZE), 2)
        # Connector lines between units
        if i < 2:
            nx = int(boss.unit_x[i + 1]);  ny = int(boss.unit_y[i + 1])
            pygame.draw.line(surf, tuple(c // 3 for c in bord), (ux, uy), (nx, ny), 1)
    # Close the triangle
    pygame.draw.line(surf, tuple(c // 3 for c in bord),
                     (int(boss.unit_x[2]), int(boss.unit_y[2])),
                     (int(boss.unit_x[0]), int(boss.unit_y[0])), 1)


def _render_wall_boss(surf: pygame.Surface, boss: WallBoss):
    if boss.y + boss.wall_height < 0: return
    wy = int(boss.y)
    body = WHITE if boss.flash_frames > 0 else (30, 30, 80)
    bord = WallBoss.PATTERN_COLOR.get(boss.pattern, WHITE)
    pygame.draw.rect(surf, body, (0, wy, SCREEN_W, int(boss.wall_height)))
    pygame.draw.rect(surf, bord, (0, wy, SCREEN_W, int(boss.wall_height)), 2)
    # Draw cannon mouths — skip destroyed, show rubble
    cannon_y = wy + int(boss.wall_height) - 4
    for i, cx in enumerate(boss._cannon_xs):
        icx = int(cx)
        if not boss.cannon_alive[i]:
            # Canhão destruído: marca de destruição em cinza
            pygame.draw.line(surf, (80, 40, 40), (icx - 5, cannon_y - 5), (icx + 5, cannon_y + 5), 2)
            pygame.draw.line(surf, (80, 40, 40), (icx + 5, cannon_y - 5), (icx - 5, cannon_y + 5), 2)
            continue
        if boss.pattern == boss.RAIN:
            pygame.draw.circle(surf, bord, (icx, cannon_y), 5)
        else:
            pygame.draw.rect(surf, bord, (icx - 3, cannon_y - 4, 6, 8))
    # Rage indicator: red border tint when rage_mult > 1
    if boss._rage_mult > 1.0:
        rage_col = (min(255, int(80 * boss._rage_mult)), 30, 30)
        pygame.draw.rect(surf, rage_col, (0, wy, SCREEN_W, int(boss.wall_height)), 3)




def _render_omega_boss(surf: pygame.Surface, boss):
    """Delegate to sub-boss render, then add phase aura overlay."""
    render_boss(surf, boss._sub)
    phase_col = OmegaBoss.PHASE_COLORS[boss._phase_idx]
    if not isinstance(boss._sub, WallBoss):
        cx, cy = int(boss._sub.x), int(boss._sub.y)
        r = boss._sub.size // 2 + 20 + boss._phase_idx * 6
        pygame.draw.circle(surf, phase_col, (cx, cy), r, 2)
        pygame.draw.circle(surf, tuple(c // 3 for c in phase_col), (cx, cy), r + 8, 1)
    else:
        wy = max(0, int(boss._sub.y))
        pygame.draw.line(surf, phase_col, (0, wy), (SCREEN_W, wy), 3)


def _render_twins_boss(surf: pygame.Surface, boss: TwinsBoss):
    flash    = boss.flash_frames > 0
    p2       = boss._phase == 2
    scenario = boss._scenario
    sc       = boss._survivor_scale
    hs_base  = TWIN_SIZE

    def _draw_twin(cx, cy, body_col, bord_col, rune_up: bool):
        hs = int(hs_base * sc)
        ix, iy = int(cx), int(cy)
        body = WHITE if flash else body_col
        pygame.draw.rect(surf, body, (ix-hs, iy-hs, hs*2, hs*2))
        pygame.draw.rect(surf, bord_col, (ix-hs, iy-hs, hs*2, hs*2), 2)
        if rune_up:  # Yin rune
            pygame.draw.line(surf, bord_col, (ix, iy), (ix, iy+hs-4), 2)
            pygame.draw.line(surf, bord_col, (ix-hs+4, iy-hs+4), (ix, iy), 2)
            pygame.draw.line(surf, bord_col, (ix+hs-4, iy-hs+4), (ix, iy), 2)
        else:        # Yang rune
            pygame.draw.line(surf, bord_col, (ix, iy), (ix, iy-hs+4), 2)
            pygame.draw.line(surf, bord_col, (ix-hs+4, iy+hs-4), (ix, iy), 2)
            pygame.draw.line(surf, bord_col, (ix+hs-4, iy+hs-4), (ix, iy), 2)

    # Yin — azul (ou sobrevivente Yin dominante com cor absorvida)
    if boss.yin_alive:
        if p2 and scenario == 'yin':
            body_c = (20, 30, 80); bord_c = (60, 100, 255)  # azul profundo
        else:
            body_c = (40, 80, 200); bord_c = (100, 160, 255)
        _draw_twin(boss.yin_x, boss.yin_y, body_c, bord_c, rune_up=True)

    # Yang — laranja (ou sobrevivente Yang dominante com cor absorvida)
    if boss.yang_alive:
        if p2 and scenario == 'yang':
            body_c = (120, 30, 10); bord_c = (255, 80, 20)  # laranja-sangue
        else:
            body_c = (200, 80, 30); bord_c = (255, 165, 40)
        _draw_twin(boss.yang_x, boss.yang_y, body_c, bord_c, rune_up=False)

    # Linha conectora (apenas fase 1 com ambos vivos)
    if boss.yin_alive and boss.yang_alive and not p2:
        pygame.draw.line(surf, (60, 60, 100),
                         (int(boss.yin_x), int(boss.yin_y)),
                         (int(boss.yang_x), int(boss.yang_y)), 1)

    # Carga do Pulso de Inversão (Yin dominante fase 2)
    if p2 and scenario == 'yin' and boss._inv_charging:
        frac  = min(1.0, boss._inv_charge_t / YIN_INV_CHARGE_T)
        ix, iy = int(boss.yin_x), int(boss.yin_y)
        r_min, r_max = 18, 52
        for ring in range(3):
            r = int(r_min + (r_max - r_min) * frac * ((ring + 1) / 3))
            intensity = int(80 + 175 * frac)
            pygame.draw.circle(surf, (intensity // 4, intensity // 2, intensity),
                               (ix, iy), r, 1 + ring)


def _render_summoner_boss(surf: pygame.Surface, boss: SummonerBoss):
    bx = int(boss.x - boss.size); by = int(boss.y - boss.size)
    bs = boss.size * 2
    body = WHITE if boss.flash_frames > 0 else (70, 20, 120)
    bord = (200, 80, 255)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, bord, (bx, by, bs, bs), 2)
    # Halo mystical rings
    r_base = boss.size + 14
    for dr in (0, 8):
        pygame.draw.circle(surf, tuple(c // 3 for c in bord),
                           (int(boss.x), int(boss.y)), r_base + dr, 1)


def render_enemies(surf: pygame.Surface, enm_pool: EnemyPool):
    """Renderiza kamikazes (vermelho), sentinelas (roxo) e bolhas (ciano) do EnemyPool."""
    active = np.where(enm_pool.active)[0]
    for i in active:
        i = int(i)
        ex, ey = int(enm_pool.ex[i]), int(enm_pool.ey[i])
        _flash = enm_pool.e_hit_flash[i] > 0
        if enm_pool.etype[i] == ETYPE_KAMIKAZE:
            s = ENEMY_KAMIKAZE_SIZE
            _body = WHITE if _flash else (200, 50, 30)
            pygame.draw.rect(surf, _body, (ex - s, ey - s, s*2, s*2))
            if not _flash:
                pygame.draw.rect(surf, (255, 120, 80), (ex - s, ey - s, s*2, s*2), 1)
                pygame.draw.line(surf, (255, 120, 80), (ex, ey - s + 2), (ex, ey + s - 2), 2)
                pygame.draw.line(surf, (255, 120, 80), (ex - 4, ey + s - 6), (ex, ey + s - 2), 2)
                pygame.draw.line(surf, (255, 120, 80), (ex + 4, ey + s - 6), (ex, ey + s - 2), 2)
        elif enm_pool.etype[i] == ETYPE_BUBBLE:
            t_left = float(enm_pool.etmr[i])
            danger = t_left < 3.0
            col = WHITE if _flash else ((0, 255, 220) if not danger or int(t_left * 8) % 2 == 0 else (255, 80, 80))
            pygame.draw.circle(surf, col, (ex, ey), 16, 2)
            pygame.draw.circle(surf, tuple(c // 3 for c in col), (ex, ey), 16)
            if not _flash:
                hp_r = max(0.0, float(enm_pool.ehp[i]) / BUBBLE_HP)
                if hp_r > 0:
                    pygame.draw.arc(surf, (200, 255, 240),
                                    (ex - 12, ey - 12, 24, 24),
                                    0, math.tau * hp_r, 2)
        else:  # SENTINEL
            s = ENEMY_SENTINEL_SIZE
            _body = WHITE if _flash else (60, 20, 100)
            pygame.draw.rect(surf, _body, (ex - s, ey - s, s*2, s*2))
            if not _flash:
                pygame.draw.rect(surf, (170, 80, 230), (ex - s, ey - s, s*2, s*2), 2)
                pygame.draw.line(surf, (170, 80, 230), (ex - s + 2, ey), (ex + s - 2, ey), 2)
                pygame.draw.line(surf, (170, 80, 230), (ex, ey - s + 2), (ex, ey + s - 2), 2)


# ===========================================================================
# Render — Sete Pecados
# ===========================================================================
def _render_pride_boss(surf: pygame.Surface, boss: PrideBoss):
    # Fase 0: corpo segue o holofote (spot_x), não o jogador
    vis_x = boss.spot_x if boss._phase == 0 else boss.x
    bx = int(vis_x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (200, 180, 20)
    # Holofote desenhado ANTES do corpo para que o corpo fique por cima
    if boss._phase == 0:
        sx = int(boss.spot_x - boss._SPOT_W / 2)
        sw = int(boss._SPOT_W)
        beam_surf = pygame.Surface((sw, SCREEN_H), pygame.SRCALPHA)
        beam_surf.fill((255, 255, 180, 28))
        surf.blit(beam_surf, (sx, 0))
        pygame.draw.line(surf, (255, 240, 120), (sx, 0), (sx, SCREEN_H), 1)
        pygame.draw.line(surf, (255, 240, 120), (sx + sw, 0), (sx + sw, SCREEN_H), 1)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, (255, 215, 0), (bx, by, bs, bs), 2)


def _render_sloth_boss(surf: pygame.Surface, boss: SlothBoss):
    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (50, 10, 80)
    bord = (130, 60, 200) if not boss.invulnerable else (60, 60, 80)
    pygame.draw.ellipse(surf, body, (bx, by, bs, bs))
    pygame.draw.ellipse(surf, bord, (bx, by, bs, bs), 2)
    if boss.dark_mode:
        dark = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dark.fill((0, 0, 20, 185))
        surf.blit(dark, (0, 0))
        pygame.draw.ellipse(surf, body, (bx, by, bs, bs))
        pygame.draw.ellipse(surf, bord, (bx, by, bs, bs), 2)


def _render_envy_boss(surf: pygame.Surface, boss: EnvyBoss):
    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (10, 100, 35)
    bord = (0, 220, 80)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, bord, (bx, by, bs, bs), 2)
    # Espelho decorativo
    pygame.draw.line(surf, bord, (int(boss.x), by), (int(boss.x), by + bs))
    if boss._phase == 1:
        # Escudo de cooldown roubado — anel de balas ao redor
        pygame.draw.circle(surf, (0, 180, 60), (int(boss.x), int(boss.y)), bs // 2 + 10, 2)


def _render_gluttony_boss(surf: pygame.Surface, boss: GluttonyBoss):
    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (80, 10, 10)
    pygame.draw.ellipse(surf, body, (bx, by, bs, bs))
    pygame.draw.ellipse(surf, (180, 40, 40), (bx, by, bs, bs), 2)
    # Anel de sucção visual
    r = bs // 2 + 14 + boss._phase * 10
    suction_surf = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
    pygame.draw.circle(suction_surf, (120, 20, 20, 60), (r+2, r+2), r)
    surf.blit(suction_surf, (int(boss.x) - r - 2, int(boss.y) - r - 2))
    pygame.draw.circle(surf, (200, 50, 50), (int(boss.x), int(boss.y)), r, 1)


def _render_greed_boss(surf: pygame.Surface, boss: GreedBoss):
    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (100, 80, 10)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, (200, 160, 0), (bx, by, bs, bs), 2)
    # Fase 0 — paredes verticais
    if boss._phase == 0:
        for wx in boss.wall_x:
            wall_s = pygame.Surface((6, SCREEN_H), pygame.SRCALPHA)
            wall_s.fill((200, 160, 0, 120))
            surf.blit(wall_s, (int(wx) - 3, 0))
            pygame.draw.line(surf, (255, 210, 0), (int(wx), 0), (int(wx), SCREEN_H), 1)
    # Fase 1 — moedas
    elif boss._phase == 1:
        coin_idxs = np.where(boss.coin_active)[0]
        for ci in coin_idxs:
            cx, cy = int(boss.coin_x[ci]), int(boss.coin_y[ci])
            pygame.draw.circle(surf, (200, 160, 0), (cx, cy), 9)
            pygame.draw.circle(surf, (255, 220, 80), (cx, cy), 9, 2)
            pygame.draw.line(surf, (255, 220, 80), (cx, cy - 6), (cx, cy + 6), 2)
    # Fase 2 — borda encolhendo
    elif boss._phase == 2:
        bi = int(boss.border_inset)
        pygame.draw.rect(surf, (200, 160, 0),
                         (bi, bi, SCREEN_W - 2*bi, SCREEN_H - 2*bi), 2)


def _render_lust_boss(surf: pygame.Surface, boss: LustBoss):
    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (110, 30, 70)
    bord = (220, 80, 160)
    pygame.draw.ellipse(surf, body, (bx, by, bs, bs))
    pygame.draw.ellipse(surf, bord, (bx, by, bs, bs), 2)
    if boss._phase == 1:
        # Seta indicando força magnética ascendente
        ax = int(boss.x); ay = int(boss.y) + bs // 2 + 15
        pygame.draw.line(surf, bord, (ax, ay + 20), (ax, ay), 2)
        pygame.draw.polygon(surf, bord, [(ax-5, ay+5), (ax+5, ay+5), (ax, ay)])


def _render_wrath_boss(surf: pygame.Surface, boss: WrathBoss):
    # Fase 2 — só o corpo ricocheteando; o rect estático não deve aparecer
    if boss._phase == 2:
        if boss.body_dmg_active:
            bx2 = int(boss.body_x); by2 = int(boss.body_y)
            r = int(boss.body_r)
            pygame.draw.circle(surf, (220, 60, 10), (bx2, by2), r)
            pygame.draw.circle(surf, (255, 160, 30), (bx2, by2), r, 2)
            for k in range(8):
                fang = math.radians(k * 45 + boss.phase_t * 200.0)
                fx = bx2 + int(math.cos(fang) * (r + 5))
                fy = by2 + int(math.sin(fang) * (r + 5))
                pygame.draw.circle(surf, (255, 100, 0), (fx, fy), 4)
        return

    bx = int(boss.x - boss.size / 2); by = int(boss.y - boss.size / 2); bs = boss.size
    body = WHITE if boss.flash_frames > 0 else (120, 20, 10)
    bord = (220, 50, 20)
    pygame.draw.rect(surf, body, (bx, by, bs, bs))
    pygame.draw.rect(surf, bord, (bx, by, bs, bs), 2)
    # Fase 1 — anel de choque
    if boss._phase == 1 and boss._ring_active:
        r = int(boss._ring_r)
        cx, cy = int(boss.x), int(boss.y)
        if r > 0 and r < max(SCREEN_W, SCREEN_H) + 100:
            ring_col = (200 - min(200, r // 3), 40, 20)
            pygame.draw.circle(surf, ring_col, (cx, cy), r, 2)


def _render_sin_boss(surf: pygame.Surface, boss: SinBoss):
    cx, cy = int(boss.x), int(boss.y); s = boss.size // 2
    col = boss.current_color
    body = WHITE if boss.flash_frames > 0 else tuple(c // 3 for c in col)
    # Tesseract — octógono rotacionado
    t = boss.phase_t * 40.0
    pts = [(cx + int(math.cos(math.radians(t + i * 45)) * s),
            cy + int(math.sin(math.radians(t + i * 45)) * s))
           for i in range(8)]
    pygame.draw.polygon(surf, body, pts)
    pygame.draw.polygon(surf, col, pts, 2)
    # Glitch lines
    for k in range(3):
        ang = math.radians(t * 2 + k * 120)
        r2 = s + 12
        pygame.draw.line(surf, col,
                         (cx + int(math.cos(ang) * s), cy + int(math.sin(ang) * s)),
                         (cx + int(math.cos(ang) * r2), cy + int(math.sin(ang) * r2)), 1)
    # Minas visíveis (Fase 0)
    if boss._phase == 0:
        for mi in np.where(boss._mine_active)[0]:
            mx, my = int(boss._mine_x[mi]), int(boss._mine_y[mi])
            pygame.draw.circle(surf, col, (mx, my), 7, 1)
            pygame.draw.line(surf, col, (mx - 5, my), (mx + 5, my), 1)
            pygame.draw.line(surf, col, (mx, my - 5), (mx, my + 5), 1)
    # Fase 3 — timer de sobrevivência
    if boss._phase == 3 and boss.invulnerable:
        secs = max(0, int(boss.survive_timer) + 1)
        # Exibido no render da HUD (main.py)


def _render_dummy_boss(surf: pygame.Surface, boss: DummyBoss):
    bx, by = int(boss.x), int(boss.y)
    s = BOSS_SIZE
    # Corpo — alvo circular
    col_body = WHITE if boss.flash_frames > 0 else (60, 60, 80)
    pygame.draw.rect(surf, col_body, (bx, by, s, s))
    cx, cy = int(boss.cx), int(boss.cy)
    for r, c in ((s // 2, (200, 60, 60)), (s // 3, (200, 200, 60)), (s // 5, (60, 200, 60))):
        pygame.draw.circle(surf, c, (cx, cy), r, 2)
    # Floating damage numbers
    for i in np.where(boss._fn_active)[0]:
        alpha = max(0, min(255, int(255 * (boss._fn_t[i] / 1.8))))
        val   = int(boss._fn_val[i])
        lbl   = f"+{val:.0f}"
        # Cannot blit with alpha easily here — just draw white text
        _gfx_dummy_label = None  # drawn in HUD section with font


def render_arena_border(surf: pygame.Surface, player: Player):
    """Borda visual da arena Claustrofobia."""
    mx = int(player._arena_x0)
    my = int(player._arena_y0)
    w  = int(player._arena_x1 - player._arena_x0 + PLAYER_SIZE)
    h  = int(player._arena_y1 - player._arena_y0 + PLAYER_SIZE)
    pygame.draw.rect(surf, (120, 40, 40), (mx, my, w, h), 2)


# ===========================================================================
# Render — Telegraph (PREP)
# ===========================================================================
def render_boss_prep(surf: pygame.Surface, boss):
    if isinstance(boss, OmegaBoss):      render_boss_prep(surf, boss._sub)
    elif isinstance(boss, TwinsBoss):    pass   # sem prep visual (cada gemêo faz sua própria)
    elif isinstance(boss, SummonerBoss): pass
    elif isinstance(boss, SwarmBoss):    _render_swarm_prep(surf, boss)
    elif isinstance(boss, WallBoss):     _render_wall_prep(surf, boss)
    elif not hasattr(boss, 'preview_aim'): pass  # SinBosses, DummyBoss, NullBoss
    else:                                _render_classic_prep(surf, boss)


def _render_classic_prep(surf: pygame.Surface, boss: Boss):
    if not boss.in_prep or boss.hp <= 0: return
    bx, by = int(boss.x), int(boss.y)

    if boss.pattern == Boss.SPREAD:
        visual_cone = math.radians(56)
        half = visual_cone / 2
        n = 7
        for i in range(n):
            t     = i / (n - 1)
            angle = boss.preview_aim - half + t * visual_cone
            ex = bx + int(math.cos(angle) * 110)
            ey = by + int(math.sin(angle) * 110)
            pygame.draw.line(surf, (*ORANGE, 160), (bx, by), (ex, ey), 1)
        ex = bx + int(math.cos(boss.preview_aim) * 130)
        ey = by + int(math.sin(boss.preview_aim) * 130)
        pygame.draw.line(surf, ORANGE, (bx, by), (ex, ey), 2)

    elif boss.pattern == Boss.RING:
        gap_angle = boss.preview_gap
        for r in (60, 85, 110):
            gx = bx + int(math.cos(gap_angle) * r)
            gy = by + int(math.sin(gap_angle) * r)
            pygame.draw.circle(surf, (*CYAN, 120), (gx, gy), 4, 1)
        ex = bx + int(math.cos(gap_angle) * 130)
        ey = by + int(math.sin(gap_angle) * 130)
        pygame.draw.line(surf, CYAN, (bx, by), (ex, ey), 2)
        pygame.draw.circle(surf, CYAN, (ex, ey), 7, 2)

    elif boss.pattern == Boss.SPIRAL:
        t     = boss.phase_t / PREP_TIME
        alpha = int(80 + 80 * math.sin(t * math.pi * 6))
        pygame.draw.circle(surf, (*DARKBLUE, alpha),
                           (bx, by), int(50 + 20 * math.sin(t * math.pi * 4)), 3)

    elif boss.pattern == Boss.CIRCULAR:
        t        = boss.phase_t / PREP_TIME
        disp_ang = boss.angle - CIRC_SPIN_SPEED * PREP_TIME * t
        reach    = CIRC_MAX_STEPS * CIRC_STEP_SIZE * t
        col      = (255, 200, 80)
        sep      = TWO_PI / CIRC_ARMS
        for arm in range(CIRC_ARMS):
            arm_angle = disp_ang + arm * sep
            ex = bx + int(math.cos(arm_angle) * reach)
            ey = by + int(math.sin(arm_angle) * reach)
            pygame.draw.line(surf, col, (bx, by), (ex, ey), 2)
            if t > 0.35:
                pygame.draw.circle(surf, col, (ex, ey), 5, 1)

    elif boss.pattern == Boss.SHARD:
        t   = boss.phase_t / PREP_TIME
        rot = boss.angle
        for i in range(len(CRACK_BASE)):
            theta  = CRACK_BASE[i] + rot
            b1, b2 = CRACK_BENDS[i]
            rx, ry = float(bx), float(by)
            for j, step in enumerate(CRACK_STEPS):
                if j < CRACK_SEG1:    seg_theta = theta
                elif j < CRACK_SEG2:  seg_theta = theta + b1
                else:                 seg_theta = theta + b1 + b2
                nx = rx + math.cos(seg_theta) * step * t
                ny = ry + math.sin(seg_theta) * step * t
                pygame.draw.line(surf, (200, 255, 200), (int(rx), int(ry)), (int(nx), int(ny)), 1)
                rx, ry = nx, ny
            if t > 0.6:
                pygame.draw.circle(surf, (200, 255, 200), (int(rx), int(ry)), 3, 1)

    elif boss.pattern == Boss.LASER:
        t     = boss.phase_t / PREP_TIME
        col   = (80, 180, 255)
        reach = int(SCREEN_W * 0.48 * t)
        pygame.draw.line(surf, col, (bx - reach, by), (bx + reach, by), 2)
        pygame.draw.line(surf, col, (bx, by - reach), (bx, by + reach), 2)
        if t > 0.4:
            for d in (-1, 1):
                r2 = int(reach * 0.55)
                pygame.draw.circle(surf, col, (bx + d * r2, by),   4, 1)
                pygame.draw.circle(surf, col, (bx,   by + d * r2), 4, 1)

    elif boss.pattern == Boss.BLASTER:
        t     = boss.phase_t / PREP_TIME
        col   = (255, 80, 60)
        reach = int(110 * t)
        for sx, sy, dx, dy in ((SCREEN_W//2, 0, 0, 1), (SCREEN_W//2, SCREEN_H, 0, -1),
                               (0, SCREEN_H//2, 1, 0), (SCREEN_W, SCREEN_H//2, -1, 0)):
            ex = sx + dx * reach;  ey = sy + dy * reach
            pygame.draw.line(surf, col, (sx, sy), (ex, ey), 2)
            if t > 0.45:
                pygame.draw.circle(surf, col, (ex, ey), 5 + int(t * 4), 1)

    elif boss.pattern == Boss.FRACTURE:
        t  = boss.phase_t / PREP_TIME
        cc = math.cos(FRAC_CUT_ANGLE);  cs = math.sin(FRAC_CUT_ANGLE)
        reach = FRAC_CUT_HALF * t
        pygame.draw.line(surf, CYAN, (bx, by),
                         (bx + int(-cc * reach), by + int(-cs * reach)), 2)
        pygame.draw.line(surf, CYAN, (bx, by),
                         (bx + int( cc * reach), by + int( cs * reach)), 2)
        if t > 0.45:
            tree_t = (t - 0.45) / 0.55
            for (cut_s, trunk_ang, trunk_n, branches) in FRAC_TREES:
                ox = bx + int(cc * cut_s);  oy = by + int(cs * cut_s)
                tc = math.cos(trunk_ang);  ts_a = math.sin(trunk_ang)
                trunk_reach = trunk_n * FRAC_STEP_SIZE * tree_t
                tex = ox + int(tc * trunk_reach);  tey = oy + int(ts_a * trunk_reach)
                pygame.draw.line(surf, CYAN, (ox, oy), (tex, tey), 1)
                if tree_t > 0.6:
                    branch_t = (tree_t - 0.6) / 0.4
                    box = ox + int(tc * trunk_n * FRAC_STEP_SIZE)
                    boy = oy + int(ts_a * trunk_n * FRAC_STEP_SIZE)
                    for (rel_a, n_b) in branches:
                        ba  = trunk_ang + rel_a
                        brc = math.cos(ba);  brs = math.sin(ba)
                        br  = n_b * FRAC_STEP_SIZE * branch_t
                        pygame.draw.line(surf, CYAN, (box, boy),
                                         (box + int(brc * br), boy + int(brs * br)), 1)

    elif boss.pattern == Boss.STOP_AND_GO:
        t   = boss.phase_t / PREP_TIME
        col = (180, 80, 255)
        visual_cone = math.radians(56)
        half = visual_cone / 2
        n = 7
        for i in range(n):
            angle = boss.preview_aim - half + i / max(n - 1, 1) * visual_cone
            ex = bx + int(math.cos(angle) * 110)
            ey = by + int(math.sin(angle) * 110)
            pygame.draw.line(surf, (*col, 140), (bx, by), (ex, ey), 1)
        if t > 0.3:
            r = int(30 * (t - 0.3) / 0.7)
            pygame.draw.circle(surf, col, (bx + int(math.cos(boss.preview_aim) * 90),
                                           by + int(math.sin(boss.preview_aim) * 90)), r, 1)

    elif boss.pattern == Boss.BOOMERANG:
        t   = boss.phase_t / PREP_TIME
        col = (255, 200, 80)
        away = boss.preview_aim + math.pi
        sep  = TWO_PI / TM_BOOM_N
        for i in range(TM_BOOM_N):
            theta = away + i * sep
            reach = int(80 * t)
            ex = bx + int(math.cos(theta) * reach)
            ey = by + int(math.sin(theta) * reach)
            pygame.draw.line(surf, (*col, 160), (bx, by), (ex, ey), 1)
            if t > 0.5:
                pygame.draw.circle(surf, col, (ex, ey), 3, 1)


def _render_swarm_prep(surf: pygame.Surface, boss: SwarmBoss):
    if not boss.in_prep or boss.hp <= 0: return
    t   = boss.phase_t / PREP_TIME
    col = SwarmBoss.PATTERN_COLOR.get(boss.pattern, WHITE)
    for i in range(3):
        ux = int(boss.unit_x[i]);  uy = int(boss.unit_y[i])
        r  = int(20 + 15 * t)
        pygame.draw.circle(surf, tuple(c // 2 for c in col), (ux, uy), r, 2)
    if boss.pattern == SwarmBoss.CROSSFIRE and t > 0.3:
        for i in range(3):
            ux = int(boss.unit_x[i]);  uy = int(boss.unit_y[i])
            aim = boss.preview_aim
            ex  = ux + int(math.cos(aim) * 80 * t)
            ey  = uy + int(math.sin(aim) * 80 * t)
            pygame.draw.line(surf, col, (ux, uy), (ex, ey), 1)


def _render_wall_prep(surf: pygame.Surface, boss: WallBoss):
    if not boss.in_prep or boss.hp <= 0: return
    if boss.y < WALL_MAX_DESCENT - 5: return
    t   = boss.phase_t / PREP_TIME
    col = WallBoss.PATTERN_COLOR.get(boss.pattern, WHITE)
    wy  = int(boss.y) + int(boss.wall_height)
    if boss.pattern == WallBoss.RAIN:
        reach = int(SCREEN_H * 0.4 * t)
        for i, cx in enumerate(boss._cannon_xs):
            if i in boss._rain_gap_set: continue
            if not boss.cannon_alive[i]: continue
            pygame.draw.line(surf, tuple(c // 2 for c in col),
                             (int(cx), wy), (int(cx), wy + reach), 1)
    elif boss.pattern == WallBoss.PILLAR:
        reach = int(SCREEN_H * 0.5 * t)
        px = int(boss._pillar_x)
        pygame.draw.line(surf, col, (px, wy), (px, wy + reach), 2)
        pygame.draw.circle(surf, col, (px, wy + reach), 5, 1)


# ===========================================================================
# Render — Lasers, Emitters, Bullets, Player, HUD
# ===========================================================================
def render_lasers(surf: pygame.Surface, lp: LaserPool):
    active_idx = np.where(lp.active)[0]
    if not len(active_idx): return
    for i in active_idx:
        idx   = int(i)
        timer = float(lp.timer[idx])
        pos   = int(lp.lpos[idx])
        is_h  = bool(lp.horiz[idx])
        if timer > 0.0:
            frac = 1.0 - timer / LASER_TELEGRAPH
            col  = (int(60 + frac * 80), int(140 + frac * 80), 255)
            w    = max(1, int(frac * 2))
            if is_h: pygame.draw.line(surf, col, (0, pos), (SCREEN_W, pos), w)
            else:    pygame.draw.line(surf, col, (pos, 0), (pos, SCREEN_H), w)
        else:
            frac_out  = min(1.0, -timer / LASER_FIRE_DUR)
            intensity = 1.0 - frac_out * 0.55
            col  = (int(80 + intensity * 175), int(160 + intensity * 95), 255)
            glow = (col[0] // 4, col[1] // 4, col[2] // 3)
            if is_h:
                pygame.draw.line(surf, glow,  (0, pos), (SCREEN_W, pos), LASER_WIDTH + 8)
                pygame.draw.line(surf, col,   (0, pos), (SCREEN_W, pos), LASER_WIDTH)
                pygame.draw.line(surf, WHITE, (0, pos), (SCREEN_W, pos), 2)
            else:
                pygame.draw.line(surf, glow,  (pos, 0), (pos, SCREEN_H), LASER_WIDTH + 8)
                pygame.draw.line(surf, col,   (pos, 0), (pos, SCREEN_H), LASER_WIDTH)
                pygame.draw.line(surf, WHITE, (pos, 0), (pos, SCREEN_H), 2)


def render_emitters(surf: pygame.Surface, ep: EmitterPool):
    active_idx = np.where(ep.active)[0]
    if not len(active_idx): return
    for i in active_idx:
        idx = int(i)
        x, y = int(ep.ex[idx]), int(ep.ey[idx])
        ang  = float(ep.angle[idx])
        if not ep.fired[idx]:
            frac = 1.0 - max(ep.timer[idx], 0.0) / BLAST_TELEGRAPH
            r = min(255, 120 + int(frac * 135))
            g = max(0,    70 - int(frac * 70))
            b = max(0,    50 - int(frac * 50))
            col = (r, g, b)
            ex_end = x + int(math.cos(ang) * 1400)
            ey_end = y + int(math.sin(ang) * 1400)
            pygame.draw.line(surf, col, (x, y), (ex_end, ey_end), max(1, int(frac * 2) + 1))
            sz = 10 + int(frac * 9)
            pygame.draw.rect(surf, col,   (x - sz//2, y - sz//2, sz, sz))
            pygame.draw.rect(surf, WHITE, (x - sz//2, y - sz//2, sz, sz), 1)
        else:
            pygame.draw.circle(surf, WHITE, (x, y), 16, 2)
            pygame.draw.circle(surf, (255, 80, 60), (x, y), 10)


LABYRINTH_INVIS_R = 155.0   # raio de invisibilidade do labirinto ao redor do jogador

def render_bullets(surf: pygame.Surface, pool: BulletPool,
                   bsurf: pygame.Surface, psurf: pygame.Surface,
                   boss=None, mutators: frozenset = frozenset(),
                   bsurf_blue: pygame.Surface = None,
                   bsurf_orange: pygame.Surface = None,
                   bsurf_purple: pygame.Surface = None,
                   px: float = 0.0, py: float = 0.0):
    active = np.where(pool.active)[0]
    if not len(active): return

    ghost = boss is not None and MUTATOR_GHOST in mutators
    if ghost:
        bref   = boss.cx if hasattr(boss, 'cx') else boss.x
        bref_y = boss.cy if hasattr(boss, 'cy') else boss.y
        dx  = pool.bx[active] - bref
        dy  = pool.by[active] - bref_y
        d_sq = dx * dx + dy * dy
        visible_mask = pool.parried[active] | (d_sq < GHOST_NEAR**2) | (d_sq > GHOST_FAR**2)
        visible = active[visible_mask]
    else:
        visible = active

    # Oculta balas do Labirinto Invisível quando perto do jogador
    if pool.b_invisible[visible].any():
        dx_p  = pool.bx[visible] - px
        dy_p  = pool.by[visible] - py
        d_p_sq = dx_p*dx_p + dy_p*dy_p
        visible = visible[~(pool.b_invisible[visible] & (d_p_sq < LABYRINTH_INVIS_R**2))]

    normal  = visible[~pool.parried[visible]]
    parried = visible[ pool.parried[visible]]
    if len(normal):
        btypes = pool.b_type[normal]
        for group, gsurf in (
            (normal[btypes == BTYPE_NORMAL],  bsurf),
            (normal[btypes == BTYPE_BLUE],    bsurf_blue   or bsurf),
            (normal[btypes == BTYPE_ORANGE],  bsurf_orange or bsurf),
            (normal[btypes == BTYPE_PURPLE],  bsurf_purple or bsurf),
        ):
            if not len(group): continue
            xs = (pool.bx[group] - 3).astype(np.int32)
            ys = (pool.by[group] - 3).astype(np.int32)
            surf.blits([(gsurf, (int(x), int(y))) for x, y in zip(xs, ys)])
    if len(parried):
        xs = (pool.bx[parried] - 3).astype(np.int32)
        ys = (pool.by[parried] - 3).astype(np.int32)
        surf.blits([(psurf, (int(x), int(y))) for x, y in zip(xs, ys)])

    # Ricochet: balas que já ricochetearam — amarelo brilhante, 1px maior
    ric = visible[pool.b_ricochet[visible]]
    if len(ric):
        for ridx in ric:
            pygame.draw.circle(surf, (255, 220, 0),
                               (int(pool.bx[ridx]), int(pool.by[ridx])), 4)

    # ---- Novos b_types: renderização por bala individual -------------------
    btypes_v = pool.b_type[visible]

    # BTYPE_GRAVITY — círculo pulsante roxo/escuro
    for _gi in visible[btypes_v == BTYPE_GRAVITY]:
        _gx, _gy = int(pool.bx[_gi]), int(pool.by[_gi])
        pygame.draw.circle(surf, (40, 10, 80),  (_gx, _gy), 7)
        pygame.draw.circle(surf, (180, 50, 255), (_gx, _gy), 4)
        pygame.draw.circle(surf, (220, 140, 255),(_gx, _gy), 2)

    # BTYPE_PHASE — sólida ou translúcida conforme o timer de fase
    for _pi in visible[btypes_v == BTYPE_PHASE]:
        _is_solid = float(pool.btgt_x[_pi]) < BULLET_PHASE_SOLID
        _col = (255, 100, 220) if _is_solid else (80, 30, 70)
        pygame.draw.circle(surf, _col, (int(pool.bx[_pi]), int(pool.by[_pi])), 4)
        if _is_solid:
            pygame.draw.circle(surf, (255, 220, 240), (int(pool.bx[_pi]), int(pool.by[_pi])), 2)

    # BTYPE_SPIN — círculo dourado
    for _si in visible[btypes_v == BTYPE_SPIN]:
        _sx, _sy = int(pool.bx[_si]), int(pool.by[_si])
        pygame.draw.circle(surf, (200, 150, 20), (_sx, _sy), 5)
        pygame.draw.circle(surf, (255, 230, 80),  (_sx, _sy), 3)

    # BTYPE_TETHER — pares conectados por fio laser
    _seen_t: set = set()
    for _ti in visible[btypes_v == BTYPE_TETHER]:
        _ti = int(_ti)
        if _ti in _seen_t: continue
        _j = int(round(float(pool.btgt_x[_ti])))
        if 0 <= _j < len(pool.active) and pool.active[_j]:
            _seen_t.add(_ti); _seen_t.add(_j)
            pygame.draw.line(surf, (255, 60, 80),
                             (int(pool.bx[_ti]), int(pool.by[_ti])),
                             (int(pool.bx[_j]),  int(pool.by[_j])), 2)
        pygame.draw.circle(surf, (255, 80, 100),
                           (int(pool.bx[_ti]), int(pool.by[_ti])), 4)


def render_hazards(surf: pygame.Surface, hz: HazardPool):
    for i in np.where(hz.active)[0]:
        i = int(i)
        cx = int(hz.hx[i]); cy = int(hz.hy[i])
        r  = int(hz.hr[i])
        if int(hz.htype[i]) == HAZARD_BURN:
            col_outer = (200, 60, 20)
            col_inner = (100, 25, 8)
        else:
            col_outer = (20, 180, 160)
            col_inner = (8, 80, 70)
        pygame.draw.circle(surf, col_inner, (cx, cy), r)
        pygame.draw.circle(surf, col_outer, (cx, cy), r, 3)
        pygame.draw.circle(surf, col_outer, (cx, cy), max(2, r // 4))


def render_player_bullets(surf: pygame.Surface, pb: PlayerBulletPool):
    for idx in np.where(pb.active)[0]:
        i   = int(idx)
        r   = int(pb.pb_size[i])
        pt  = int(pb.pb_type[i])
        x, y = int(pb.px[i]), int(pb.py[i])
        if pb.pb_homing[i] or pt == PB_HOMING_HELD:
            col = (255, 220, 80) if pt == PB_HOMING_HELD else (120, 255, 80)
            pygame.draw.circle(surf, col, (x, y), 3)
        elif pt == PB_FLAK:
            pygame.draw.circle(surf, (255, 140, 30), (x, y), r)
            pygame.draw.circle(surf, (255, 220, 120), (x, y), max(1, r - 3))
        elif pt == PB_CHAKRAM:
            _chk_col = (255, 50, 200) if pb.pb_state[i] == 2 else (0, 200, 255)  # CHAKRAM+: magenta when frozen
            pygame.draw.circle(surf, _chk_col, (x, y), r)
            pygame.draw.line(surf, WHITE, (x - r, y), (x + r, y), 1)
            pygame.draw.line(surf, WHITE, (x, y - r), (x, y + r), 1)
        elif pt == PB_PLASMA:
            pygame.draw.circle(surf, (130, 40, 220), (x, y), r)
            pygame.draw.circle(surf, (200, 120, 255), (x, y), max(1, r // 2))
        elif pt == PB_PLASMA_PUDDLE:
            _t_frac = max(0.0, float(pb.pb_timer[i])) / PLASMA_PLUS_PUDDLE_T
            _fade = max(60, int(220 * _t_frac))
            pygame.draw.circle(surf, (_fade // 3, _fade // 8, _fade), (x, y), r + 2)
            pygame.draw.circle(surf, (min(255, _fade + 60), 60, 255), (x, y), max(2, r - 2))
        elif pt == PB_ORBIT:
            pygame.draw.circle(surf, (200, 180, 0), (x, y), r)
            pygame.draw.circle(surf, (255, 240, 100), (x, y), max(1, r - 2))
        elif r <= 4:
            pygame.draw.rect(surf, CYAN, (x - 2, y - 6, 4, 12))
        else:
            frac = (r - 4) / (PB_CHARGED_MAX_SIZE - 4)
            col  = (255, int(200 * (1 - frac)), 40)
            pygame.draw.circle(surf, col, (x, y), r)


def render_player(surf: pygame.Surface, player: Player):
    blink = (player.invuln // 5) % 2 == 0
    if player.invuln == 0 or blink:
        color = RED_COL if player.invuln > 0 else SKYBLUE
        pygame.draw.rect(surf, color,
                         (int(player.x), int(player.y), PLAYER_SIZE, PLAYER_SIZE))
    pygame.draw.rect(surf, WHITE, (int(player.cx)-2, int(player.cy)-2, 5, 5))
    if player.is_parrying:
        pygame.draw.circle(surf, CYAN, (int(player.cx), int(player.cy)),
                           int(PARRY_RANGE), 2)
    if player.is_shielding:
        r = PLAYER_SIZE
        pygame.draw.circle(surf, (80, 255, 140), (int(player.cx), int(player.cy)), r, 3)
        pygame.draw.circle(surf, (40, 200, 100), (int(player.cx), int(player.cy)), r + 5, 1)
    if player.is_overclocking:
        pygame.draw.rect(surf, (255, 140, 40),
                         (int(player.x)-3, int(player.y)-3, PLAYER_SIZE+6, PLAYER_SIZE+6), 2)
    if player.is_charging and player.charge_t > 0:
        frac = player.charge_t / PB_CHARGED_MAX_T
        r    = int(PB_CHARGED_MIN_SIZE + (PB_CHARGED_MAX_SIZE - PB_CHARGED_MIN_SIZE) * frac)
        col  = (255, int(200 * (1 - frac)), 40)
        pygame.draw.circle(surf, col, (int(player.cx), int(player.y)), r, 2)


def render_player_trail(surf: pygame.Surface, player: Player):
    if player._trail_show <= 0.0 or not player.trail: return
    n = len(player.trail)
    for i, (tx, ty) in enumerate(player.trail):
        frac = (i + 1) / n
        col  = tuple(int(c * frac * 0.55) for c in SKYBLUE)
        r    = max(1, int(PLAYER_SIZE * 0.30 * frac))
        pygame.draw.circle(surf, col, (int(tx), int(ty)), r)


def render_particles(surf: pygame.Surface, pp: ParticlePool):
    active_idx = np.where(pp.active)[0]
    if not len(active_idx): return
    for i in active_idx:
        idx  = int(i)
        frac = float(pp.life[idx] / pp.max_life[idx])
        r    = max(1, int(pp.radius[idx] * frac))
        col  = (int(pp.r[idx] * frac), int(pp.g[idx] * frac), int(pp.b[idx] * frac))
        pygame.draw.circle(surf, col, (int(pp.px[idx]), int(pp.py[idx])), r)


def render_boss_hpbar(surf: pygame.Surface, font: pygame.Font, boss, diff: Difficulty):
    if boss.hp <= 0: return
    if isinstance(boss, NullBoss): return
    W, H = 520, 22
    bx = (SCREEN_W - W) // 2;  by = 8
    # DummyBoss — mostra DPS em vez de HP
    if isinstance(boss, DummyBoss):
        pygame.draw.rect(surf, (30, 30, 60), (bx, by, W, H))
        _dps_ratio = min(1.0, boss._dps / 10000.0)
        if _dps_ratio > 0:
            pygame.draw.rect(surf, (60, 200, 255), (bx, by, int(W * _dps_ratio), H))
        pygame.draw.rect(surf, (80, 80, 120), (bx, by, W, H), 1)
        _dps_lbl = font.render(
            f"DPS: {int(boss._dps):,}  |  TOTAL: {int(boss.total_damage):,}",
            True, WHITE)
        surf.blit(_dps_lbl, (bx + W//2 - _dps_lbl.get_width()//2, by + 3))
        return
    pygame.draw.rect(surf, DARKRED, (bx, by, W, H))
    ratio = boss.hp / boss.max_hp
    fw    = int(W * ratio)
    fc    = RED_COL if ratio > 0.66 else (ORANGE if ratio > 0.33 else YELLOW)
    if fw > 0:
        pygame.draw.rect(surf, fc, (bx, by, fw, H))

    extra = ""
    if isinstance(boss, OmegaBoss):
        extra = f"  {OmegaBoss.PHASE_NAMES[boss._phase_idx]}"
        phase_fc = OmegaBoss.PHASE_COLORS[boss._phase_idx]
        if fw > 0:
            pygame.draw.rect(surf, phase_fc, (bx, by, fw, H))
        for pct in (0.75, 0.50, 0.25):
            mx = bx + int(W * pct)
            pygame.draw.line(surf, WHITE, (mx, by), (mx, by + H), 1)
    elif isinstance(boss, TwinsBoss):
        half_W = W // 2 - 2
        if boss._phase == 2:
            # Fase 2: barra única centrada para o sobrevivente
            ratio = max(0.0, boss.hp / boss.max_hp)
            if ratio > 0:
                col = (60, 100, 255) if boss._scenario == 'yin' else (255, 80, 20)
                pygame.draw.rect(surf, DARKRED, (bx, by, W, H))
                pygame.draw.rect(surf, col, (bx, by, int(W * ratio), H))
            label = "YIN DOMINANTE" if boss._scenario == 'yin' else "YANG DOMINANTE"
            extra = f"  ★ {label} ★"
        else:
            # Fase 1: barra dual (yin esquerda, yang direita)
            yin_ratio  = max(0.0, boss.yin_hp  / (boss.max_hp / 2))
            yang_ratio = max(0.0, boss.yang_hp / (boss.max_hp / 2))
            pygame.draw.rect(surf, DARKRED, (bx, by, half_W, H))
            if boss.yin_alive and int(half_W * yin_ratio) > 0:
                pygame.draw.rect(surf, (80, 140, 255), (bx, by, int(half_W * yin_ratio), H))
            pygame.draw.rect(surf, DARKRED, (bx + half_W + 4, by, half_W, H))
            if boss.yang_alive and int(half_W * yang_ratio) > 0:
                pygame.draw.rect(surf, (255, 140, 40), (bx+half_W+4, by, int(half_W*yang_ratio), H))
            extra = "  ★RAGE★" if boss.rage else "  YIN | YANG"
    elif isinstance(boss, SummonerBoss):
        if fw > 0:
            pygame.draw.rect(surf, (140, 40, 200), (bx, by, fw, H))
        extra = "  INVOCADOR"
        if enm_pool := getattr(boss, 'enm_pool', None):
            extra += f"  lacaios: {enm_pool.active_count}"
    else:
        for pct in (0.66, 0.33):
            mx = bx + int(W * pct)
            pygame.draw.line(surf, (255, 255, 255), (mx, by), (mx, by + H), 1)

    tier_col = {1: GREEN, 2: YELLOW, 3: RED_COL}[diff.tier]
    pygame.draw.rect(surf, tier_col, (bx, by, W, H), 1)

    pat_name = boss.PATTERN_NAME.get(boss.pattern, "") if hasattr(boss, 'PATTERN_NAME') else ""
    prep = " [PREP]" if boss.in_prep else ""

    t = font.render(
        f"BOSS  {int(boss.hp)}/{boss.max_hp}   {pat_name}{prep}{extra}   T{diff.tier}",
        True, WHITE)
    surf.blit(t, (bx + (W - t.get_width()) // 2, by + 3))


def render_lives(surf: pygame.Surface, lives: int):
    for i in range(MAX_LIVES):
        color = RED_COL if i < lives else (50, 15, 15)
        pygame.draw.rect(surf, color,  (10 + i*22, SCREEN_H - 32, 16, 16))
        pygame.draw.rect(surf, WHITE,  (10 + i*22, SCREEN_H - 32, 16, 16), 1)


def render_skill_hud(surf: pygame.Surface, font: pygame.Font, player: Player):
    if player.skill == SKILL_NONE: return
    x, y = 10, SCREEN_H - 58
    W, H = 90, 8

    if player.skill == SKILL_FOCUS:
        frac = player.focus_energy
        col  = (int(220 * (1 - frac)), int(220 * frac), 40) if not player.is_focusing else WHITE
        pygame.draw.rect(surf, DKGRAY, (x, y, W, H))
        pygame.draw.rect(surf, col, (x, y, int(W * frac), H))
        pygame.draw.rect(surf, WHITE, (x, y, W, H), 1)
        lbl_col = (255, 255, 80) if player.is_focusing else WHITE
        surf.blit(font.render("FOCO [SHIFT]", True, lbl_col), (x + W + 6, y - 2))

    elif player.skill in (SKILL_DASH, SKILL_EMP, SKILL_BLINK, SKILL_PARRY,
                          SKILL_OVERCLOCK, SKILL_SHIELD, SKILL_TIMEDILATION):
        cd_max_map = {SKILL_DASH: DASH_COOLDOWN, SKILL_PARRY: PARRY_COOLDOWN,
                      SKILL_EMP: EMP_COOLDOWN,   SKILL_BLINK: BLINK_COOLDOWN,
                      SKILL_OVERCLOCK: OVERCLOCK_CD, SKILL_SHIELD: SHIELD_CD,
                      SKILL_TIMEDILATION: TIMEDILATION_CD}
        name_map   = {SKILL_DASH: "DASH",  SKILL_PARRY: "PARRY",
                      SKILL_EMP: "EMP",    SKILL_BLINK: "BLINK",
                      SKILL_OVERCLOCK: "OVERCLOCK", SKILL_SHIELD: "ESCUDO",
                      SKILL_TIMEDILATION: "DILATAÇÃO"}
        cd_max  = cd_max_map[player.skill]
        active  = (player.is_dashing or player.is_parrying
                   or player.is_overclocking or player.is_shielding
                   or player.is_timedilating)
        cd_frac = max(0.0, 1.0 - player.skill_cd / cd_max) if player.skill_cd > 0 else 1.0
        col     = (CYAN if cd_frac >= 1.0 else YELLOW) if not active else WHITE
        pygame.draw.rect(surf, DKGRAY, (x, y, W, H))
        if cd_frac > 0:
            pygame.draw.rect(surf, col, (x, y, int(W * cd_frac), H))
        pygame.draw.rect(surf, WHITE, (x, y, W, H), 1)
        lbl_col = (255, 255, 80) if active else WHITE
        surf.blit(font.render(f"{name_map[player.skill]} [SHIFT]", True, lbl_col),
                  (x + W + 6, y - 2))


def render_hash_debug(surf: pygame.Surface, player: Player):
    r = PLAYER_RADIUS + BULLET_RADIUS
    gx0 = max(0,           int((player.cx-r)/CELL_SIZE))
    gx1 = min(GRID_COLS-1, int((player.cx+r)/CELL_SIZE))
    gy0 = max(0,           int((player.cy-r)/CELL_SIZE))
    gy1 = min(GRID_ROWS-1, int((player.cy+r)/CELL_SIZE))
    for cy in range(gy0, gy1+1):
        for cx in range(gx0, gx1+1):
            pygame.draw.rect(surf, CYAN,
                             (cx*CELL_SIZE, cy*CELL_SIZE, CELL_SIZE, CELL_SIZE), 1)


def render_dev_hud(surf: pygame.Surface, font: pygame.Font,
                   fps: float, bullets: int, debug: bool):
    fc = GREEN if fps >= 55 else (YELLOW if fps >= 40 else RED_COL)
    surf.blit(font.render(f"{int(fps)} FPS", True, fc), (10, 10))
    if debug:
        surf.blit(font.render(f"bullets: {bullets}/{MAX_BULLETS}", True, DKGRAY), (10, 30))
        info = font.render(
            f"grid {GRID_COLS}×{GRID_ROWS} = {GRID_CELLS} cells | hitbox r={PLAYER_RADIUS}px",
            True, CYAN)
        surf.blit(info, (10, SCREEN_H - 50))
    hint = font.render("WASD move   SPACE/Z atira   H debug   ESC sai",
                       True, (38, 38, 38))
    surf.blit(hint, (SCREEN_W - hint.get_width() - 10, SCREEN_H - 22))


_BOSS_INTRO = {
    BOSS_CLASSIC:  ("CLÁSSICO",   (192, 32, 32),  "10 padrões. Cada ataque tem uma abertura — encontre-a."),
    BOSS_SWARM:    ("ENXAME",     (140, 60, 220), "3 unidades em formação. Destrua uma por uma."),
    BOSS_WALL:     ("PAREDÃO",    (60, 120, 220), "Uma muralha que desce. Elimine os canhões ou esquive das colunas."),
    BOSS_OMEGA:    ("ÔMEGA ★",    (255, 60, 120), "Quatro chefes em um. Teleporte periódico. Não baixe a guarda."),
    BOSS_TWINS:    ("GÊMEOS",     (80, 120, 255), "Azul para quem se move. Laranja para quem para. Nenhum lado é seguro."),
    BOSS_SUMMONER: ("INVOCADOR",  (48, 192, 144), "Canto a canto, invoção a invocação. O chefe não luta sozinho."),
    BOSS_PRIDE:    ("SOBERBA",    (220, 180, 0),  "Atire dentro do holofote. Fora da luz, é invulnerável."),
    BOSS_SLOTH:    ("PREGUIÇA",   (110, 80, 200), "Fase de sombras: mate os três fantasmas para expô-lo."),
    BOSS_ENVY:     ("INVEJA",     (46, 160, 90),  "Ele copia o que você usa. Mude de estratégia, não de posição."),
    BOSS_GLUTTONY: ("GULA",       (160, 40, 40),  "A gravidade muda em cada fase. Aprenda antes de reagir."),
    BOSS_GREED:    ("AVAREZA",    (210, 160, 20), "Moedas explodem. Destrua-as longe de você."),
    BOSS_LUST:     ("LUXÚRIA",    (220, 80, 160), "Fase 2: seus controles estão invertidos. Confie na memória muscular."),
    BOSS_WRATH:    ("IRA",        (220, 80, 30),  "O mergulho cria ondas de choque. Nunca fique no chão."),
    BOSS_SIN:      ("SIN",        (180, 0, 220),  "Fase 4: invulnerável por 30 segundos. A única saída é sobreviver."),
}


def render_intro(surf: pygame.Surface, big: pygame.Font, font: pygame.Font,
                 t: float, boss_type: int = -1):
    if t <= 0: return
    alpha = min(255, int(t * 180))
    # Flavor text do boss no topo
    if boss_type in _BOSS_INTRO:
        bname, bcol, bflavor = _BOSS_INTRO[boss_type]
        _name_s = big.render(bname, True, bcol)
        _name_s.set_alpha(alpha)
        surf.blit(_name_s, ((SCREEN_W - _name_s.get_width()) // 2, SCREEN_H // 2 - 80))
        _flav_s = font.render(bflavor, True, (200, 200, 200))
        _flav_s.set_alpha(alpha)
        surf.blit(_flav_s, ((SCREEN_W - _flav_s.get_width()) // 2, SCREEN_H // 2 - 24))
    lines = [
        (big,  "DESTRUA O BOSS", WHITE,  SCREEN_H//2 + 70),
        (font, "SPACE / Z — Atirar      WASD / Setas — Mover", CYAN, SCREEN_H//2 + 130),
    ]
    for fnt, text, color, y in lines:
        s = fnt.render(text, True, color)
        s.set_alpha(alpha)
        surf.blit(s, ((SCREEN_W - s.get_width())//2, y))


def render_end_screen(surf: pygame.Surface, big: pygame.Font, font: pygame.Font,
                      title: str, color: tuple, elapsed: float, hits: int,
                      grazes: int = 0, has_replay: bool = False,
                      unlocks: list = None, multiplier: float = 1.0):
    ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 168))
    surf.blit(ov, (0, 0))
    cy = SCREEN_H // 2
    t  = big.render(title, True, color)
    surf.blit(t, ((SCREEN_W - t.get_width())//2, cy - 90))
    m, s = divmod(int(elapsed), 60)
    mult_str = f"  ×{multiplier:.2f}" if multiplier > 1.0 else ""
    stats_lines = [f"Tempo:  {m:02d}:{s:02d}", f"Acertos:  {hits}",
                   f"Graze:  {grazes}{mult_str}"]
    for i, line in enumerate(stats_lines):
        ln = font.render(line, True, WHITE)
        surf.blit(ln, ((SCREEN_W - ln.get_width())//2, cy - 10 + i*26))
    if multiplier > 1.0:
        mt = font.render(f"Multiplicador de Mutadores: ×{multiplier:.2f}", True, YELLOW)
        surf.blit(mt, ((SCREEN_W - mt.get_width())//2, cy + 60))
    if unlocks:
        for j, txt in enumerate(unlocks):
            ul = font.render(f">> {txt}", True, YELLOW)
            surf.blit(ul, ((SCREEN_W - ul.get_width())//2, cy + 70 + j*24))
    actions = "R — Jogar novamente    T — Tentar de novo"
    if has_replay: actions += "    W — Ver replay"
    actions += "    ESC — Menu"
    pr = font.render(actions, True, (140, 140, 140))
    surf.blit(pr, ((SCREEN_W - pr.get_width())//2, SCREEN_H - 40))


# ===========================================================================
# Menu — dados e helpers
# ===========================================================================
_DIFF_COLORS = {
    DIFF_EASY:    (80, 220, 80),
    DIFF_NORMAL:  YELLOW,
    DIFF_HARD:    RED_COL,
    DIFF_EXPERT:  (255, 80, 200),
    DIFF_ABISSAL: (120, 0, 255),
}
_DIFF_DESC = {
    DIFF_EASY:   ["Velocidade ×0.75", "Padrões: SPREAD, RING, SPIRAL, SHARD", "Boss HP: 200"],
    DIFF_NORMAL: ["Velocidade ×1.0",  "Todos os ataques · Ordem fixa",         "Boss HP: 300"],
    DIFF_HARD:   ["Velocidade ×1.3",  "+1 projétil por padrão",               "Boss HP: 400"],
    DIFF_EXPERT: ["Velocidade ×1.50", "PREP ×0.5 · Balas 20% menores",
                  "★ Segundo Fôlego — boss resiste 3s com 1 HP ao morrer",    "Boss HP: 480"],
    DIFF_ABISSAL:["Velocidade ×1.65", "Balas de Fragmentação (OOB/Parry → 2 ricochetes)",
                  "Balas de Vingança — ring roxo ao matar minion/fase",
                  "⚠ Requer vitória no Boss Rush dos 7 Pecados",              "Boss HP: 560"],
}
_BOSS_COLORS = {
    BOSS_CLASSIC:  MAROON,
    BOSS_SWARM:    (140, 60, 220),
    BOSS_WALL:     (60, 120, 220),
    BOSS_OMEGA:    (255, 60, 120),
    BOSS_TWINS:    (80, 120, 255),
    BOSS_SUMMONER: (160, 40, 220),
}
_BOSS_DESC = {
    BOSS_CLASSIC:  ["O Boss Clássico — 10 padrões de ataque rotativos",
                    "SPREAD · RING · SPIRAL · SHARD · CIRC · FRAC · BLAST · LASER",
                    "+ STOP&GO: balas pausam e relançam · BOOMERANG: anel invertido"],
    BOSS_SWARM:    ["3 unidades em formação triangular orbitante",
                    "CROSSFIRE simultâneo · Ring Volley rotativo · Laser Grid",
                    "Cada unidade tem HP próprio — destruir lança anel de fragmentos"],
    BOSS_WALL:     ["Barra horizontal que desce do topo da tela",
                    "RAIN: colunas com lacunas · PILLAR: disparo rastreador denso"],
    BOSS_OMEGA:    ["★ BOSS SECRETO — 4 fases combinando todos os bosses",
                    "Muralha → Enxame → Clássico → Caos · 2× HP · Teleporte periódico",
                    "Desbloqueio: vencer Hard com 3+ Mutadores ativos"],
    BOSS_TWINS:    ["Dois gêmeos Yin (azul) e Yang (laranja) com HP separado",
                    "Yin: lento, dispara grades AZUIS — só dano se você se mover",
                    "Yang: orbitante, dispara anéis LARANJA — só dano se você ficar parado",
                    "★ Conquista: Equilíbrio Perfeito (matar ambos com <3s de diferença)"],
    BOSS_SUMMONER: ["O Invocador teleporta entre cantos e convoca lacaios",
                    "Kamikazes: perseguem o jogador · Sentinelas: disparam em cruz",
                    "★ Conquista: Pacifista de Elite (vencer matando <10 lacaios)"],
}
_SKILL_COLORS = {
    SKILL_NONE:         DKGRAY,
    SKILL_DASH:         (80, 200, 255),
    SKILL_PARRY:        CYAN,
    SKILL_FOCUS:        (255, 220, 60),
    SKILL_EMP:          (255, 80, 200),
    SKILL_BLINK:        (140, 80, 255),
    SKILL_OVERCLOCK:    (255, 140, 40),
    SKILL_SHIELD:       (80, 255, 140),
    SKILL_TIMEDILATION: (160, 200, 255),
}
_SKILL_DESC = {
    SKILL_NONE:  ["Sem habilidade especial"],
    SKILL_DASH:  ["SHIFT — longa distância, colisão ativa",
                  f"Dist: ~{int(PLAYER_SPEED*DASH_MULT*DASH_DURATION)}px · CD: {DASH_COOLDOWN}s"],
    SKILL_PARRY: ["SHIFT — deflecte balas (balas refletidas danificam o boss)",
                  f"Janela: {PARRY_DURATION}s · CD: {PARRY_COOLDOWN}s"],
    SKILL_FOCUS: ["SEGURE SHIFT — câmera lenta nas balas e no boss",
                  "Barra de energia drena em uso, regenera fora"],
    SKILL_EMP:   ["SHIFT — destrói balas em raio massivo + stun no boss",
                  f"Raio: {int(EMP_RADIUS)}px · Stun: {EMP_STUN}s · CD: {EMP_COOLDOWN}s"],
    SKILL_BLINK: ["SHIFT — teleporte instantâneo na direção do input",
                  f"Dist: {int(BLINK_DIST)}px · CD: {BLINK_COOLDOWN}s · sem i-frames"],
    SKILL_OVERCLOCK: ["SHIFT — modo turbo: cadência de tiro 2× por 3s",
                      f"CD: {int(OVERCLOCK_CD)}s  |  Conquista: vencer Hard com Mutador"],
    SKILL_SHIELD:    ["SHIFT — escudo que absorve 1 acerto sem dano",
                      f"Duração: {SHIELD_DURATION}s · CD: {int(SHIELD_CD)}s  |  Conquista: 50 Parries"],
    SKILL_TIMEDILATION: ["SHIFT — congela todas as balas inimigas por 2s",
                         f"Duração: {TIMEDILATION_DURATION}s · CD: {int(TIMEDILATION_CD)}s",
                         "★ BLOQUEADO — vencer Gêmeos com Equilíbrio Perfeito"],
}
_SKILL_PLUS_DESC = {
    SKILL_NONE:  ["Versão+ não disponível para 'Sem Habilidade'"],
    SKILL_DASH:  ["DASH+ — Arrancada Espectral",
                  f"I-frames por {DASH_PLUS_IFRAME_DUR*1000:.0f}ms · Graze durante dash não causa dano",
                  f"Maestria: Graze {MASTERY_DASH_GRAZES} vezes enquanto estiver dashing"],
    SKILL_PARRY: ["PARRY+ — Royal Guard",
                  "Balas deflectidas viram mísseis homing no boss (dano 1.5×)",
                  f"Maestria: reflectir {MASTERY_PARRY_BURST}+ balas em uma única janela de parry"],
    SKILL_EMP:   ["EMP+ — Sobrecarga Sináptica",
                  "EMP não stuna — cada bala destruída concede +1% de dano por 5s",
                  f"Maestria: destruir {MASTERY_EMP_BULLETS}+ balas em ativações de EMP"],
    SKILL_BLINK: ["BLINK+ — Relâmpago Fantasma",
                  "EMP de raio 60px explode na posição de origem do teleporte",
                  "Maestria: teleportar ATRAVÉS do corpo do boss (detectado automaticamente)"],
    SKILL_OVERCLOCK: ["OVERCLOCK+ — Modo Berserk",
                      "4× cadência de tiro · movimento 25% mais lento durante Overclock",
                      f"Maestria: causar {int(MASTERY_OC_DMG)}+ de dano em uma única janela de Overclock"],
    SKILL_SHIELD:    ["SHIELD+ — Muralha Elástica",
                      "Bloco perfeito (<0.15s): anel de 8 balas · CD resetado em 50%",
                      f"Maestria: {MASTERY_SHIELD_PERFECT} blocos perfeitos acumulados"],
    SKILL_TIMEDILATION: ["TIMEDILATION+ — Ruptura Temporal",
                         f"Ao expirar, destrói balas em raio {int(TIMEDIL_PLUS_RADIUS)}px ao redor do jogador",
                         "Maestria: ativar Dilatação quando uma bala estiver a ≤5px (automático)"],
}
_WEAPON_COLORS = {
    WEAPON_DEFAULT: (160, 160, 160),
    WEAPON_SPREAD:  ORANGE,
    WEAPON_NEEDLE:  (80, 255, 180),
    WEAPON_CHARGED: (255, 200, 60),
    WEAPON_BURST:   (255, 100, 100),
    WEAPON_HOMING:  (100, 255, 140),
    WEAPON_FLAK:    (255, 160, 40),
    WEAPON_CHAKRAM: (0, 220, 255),
    WEAPON_PLASMA:  (160, 60, 255),
    WEAPON_ORBIT:   (255, 220, 0),
}
_WEAPON_DESC = {
    WEAPON_DEFAULT: ["1 bala reta · 1.0× dano · CD 0.10s",
                     "Confiável em qualquer situação — o benchmark"],
    WEAPON_SPREAD:  [f"3 balas em cone ±14° · {PB_SPREAD_DAMAGE}× dano cada · CD 0.13s",
                     f"Balas mais lentas ({int(PB_SPREAD_SPEED)}px/s) — melhor vs boss grande"],
    WEAPON_NEEDLE:  [f"1 bala a {int(PB_NEEDLE_SPEED)}px/s · {PB_NEEDLE_DAMAGE}× dano · CD {PB_NEEDLE_FIRE_RATE}s",
                     "Alta velocidade facilita acertar boss evasivo"],
    WEAPON_CHARGED: [f"SEGURE para carregar (até {PB_CHARGED_MAX_T}s) · SOLTE para disparar",
                     f"Dano: {PB_CHARGED_MIN_DMG}× (mínimo) → {PB_CHARGED_MAX_DMG}× (máximo cheio)"],
    WEAPON_BURST:   [f"Dispara {BURST_SHOTS} balas em rajada · {PB_BURST_DAMAGE}× dano cada",
                     f"Intervalo: {int(BURST_INTERVAL*1000)}ms · CD entre rajadas: {BURST_CD}s"],
    WEAPON_HOMING:  [f"Dispara {PB_HOMING_N} mísseis teleguiados · {PB_HOMING_DMG}× dano cada · CD {PB_HOMING_FIRE_RATE}s",
                     "Curvas caóticas — foca em sobreviver enquanto o enxame caça o boss",
                     "Em batalhas com 2 alvos mira o gêmeo mais próximo automaticamente"],
    WEAPON_FLAK:    [f"1 projétil lento ({int(FLAK_SPEED)}px/s) · explode em {FLAK_SHRAPNEL_N} estilhaços após {FLAK_TIMER}s",
                     f"Estilhaços: {FLAK_SHRAPNEL_DMG}× dano cada · leque {int(math.degrees(FLAK_SHRAPNEL_ARC))}° · CD {FLAK_FIRE_RATE}s",
                     "Controle de área — ideal contra lacaios; detonação manual de posicionamento"],
    WEAPON_CHAKRAM: [f"Disco a {int(CHAKRAM_SPEED)}px/s · desacelera, inverte e retorna · {CHAKRAM_DMG}× dano",
                     f"CD {CHAKRAM_FIRE_RATE}s · Capture o retorno chegando perto ({int(CHAKRAM_CATCH_R)}px)",
                     "Dano na ida e na volta se o boss estiver no caminho"],
    WEAPON_PLASMA:  [f"Feixe de curto alcance · {PLASMA_DPS}× DPS · dura {PLASMA_LIFESPAN}s · CD {PLASMA_FIRE_RATE}s",
                     "Atravessa o boss — dano por frame de contato (pierce total)",
                     "Máximo DPS possível mas exige ficar colado ao boss (risco extremo)"],
    WEAPON_ORBIT:   [f"Gemas que orbitam o jogador a {int(ORBIT_RADIUS)}px de raio · {ORBIT_DMG}× dano por toque",
                     f"CD {ORBIT_FIRE_RATE}s · máx {ORBIT_MAX} gemas ativas · {ORBIT_ANG_SPD:.1f} rad/s",
                     "Foque 100% em esquivar — as gemas causam dano ao boss automaticamente"],
}

_WEAPON_PLUS_DESC = {
    WEAPON_DEFAULT: ["RICOCHETE",
                     f"Balas ricocheteiam {DEFAULT_PLUS_BOUNCES}× nas paredes laterais,",
                     "cobrindo ângulos impossíveis.",
                     f"★ Maestria: {MASTERY_W_DEFAULT_HITS} acertos consecutivos sem errar."],
    WEAPON_SPREAD:  ["PONTO-CEGO",
                     f"2× dano ({SPREAD_PLUS_DMG}×) mas alcance máximo de {int(SPREAD_PLUS_MAX_RANGE)}px.",
                     "Ideal para boss grande — encoste e dispare.",
                     f"★ Maestria: {MASTERY_W_SPREAD_CLOSE} hits a <40px do boss."],
    WEAPON_NEEDLE:  ["PENETRANTE",
                     "A bala perfura o boss sem ser destruída.",
                     f"CD +20% mais lento. Excelente vs WallBoss.",
                     f"★ Maestria: {MASTERY_W_NEEDLE_PHASE} fase com ≤5 erros."],
    WEAPON_CHARGED: ["FRAGMENTAÇÃO",
                     "Ao acertar em carga máxima, explode em",
                     f"{CHARGED_PLUS_FRAG_N} estilhaços radiais de {CHARGED_PLUS_FRAG_DMG}× dano.",
                     f"★ Maestria: destruir ≥3 lacaios com 1 tiro, {MASTERY_W_CHARGED_MULTI}×."],
    WEAPON_BURST:   ["MINAS DE ATRASO",
                     f"Balas saem a {int(BURST_PLUS_INIT_SPD)}px/s e aceleram para",
                     f"{int(BURST_PLUS_MAX_SPD)}px/s após {BURST_PLUS_ARM_T}s.",
                     f"★ Maestria: acertar os 3 tiros nos Gêmeos, {MASTERY_W_BURST_TWINS}×."],
    WEAPON_HOMING:  ["SATÉLITE ORBITAL",
                     "Segure = mísseis orbitam o jogador.",
                     "Solte = todos atacam juntos.",
                     f"★ Maestria: {MASTERY_W_HOMING_NOHIT} ondas sem tomar hit."],
    WEAPON_FLAK:    ["DETONAÇÃO REMOTA",
                     "O projétil não explode por timer.",
                     "Explode ao SOLTAR o botão de tiro.",
                     f"★ Maestria: destruir {MASTERY_W_FLAK_BULLETS} projéteis com 1 explosão."],
    WEAPON_CHAKRAM: ["YO-YO",
                     "SEGURE enquanto o disco para no ar:",
                     f"causa {CHAKRAM_PLUS_DPS} DPS contínuo. SOLTE para retornar.",
                     f"★ Maestria: {MASTERY_W_CHAKRAM_ROUND} hits ida+volta no boss."],
    WEAPON_PLASMA:  ["RASTRO TÉRMICO",
                     "Deixa poças de plasma ao longo do trajeto",
                     f"(dura {PLASMA_PLUS_PUDDLE_T}s, {PLASMA_PLUS_PUDDLE_DPS} DPS).",
                     f"★ Maestria: {MASTERY_W_PLASMA_CONT}s de contato contínuo."],
    WEAPON_ORBIT:   ["INTERCEPTADORES",
                     f"Satélites dentro de {int(ORBIT_PLUS_AGGRO_R)}px do boss",
                     "lançam automaticamente para atacá-lo.",
                     f"★ Maestria: {int(MASTERY_W_ORBIT_DAMAGE)} dano total com satélites."],
}

_MUTATOR_COLORS = {
    MUTATOR_PREDATOR:      (255, 60,  60),
    MUTATOR_GHOST:         (140, 100, 255),
    MUTATOR_GLASS_CANNON:  (255, 200, 40),
    MUTATOR_HORDE:         (200, 80,  30),
    MUTATOR_BERSERKER:     (255, 80,  160),
    MUTATOR_CLAUSTROFOBIA: (80,  180, 80),
}
_MUTATOR_DESC = {
    MUTATOR_PREDATOR:      ["Boss mira onde você ESTARÁ em 0.5s",
                            "Circular/Dash ainda funciona — previsível se direto",
                            "Sinergia: BLINK — escape teleportado imprevisível"],
    MUTATOR_GHOST:         ["Balas ficam invisíveis entre 200–400px do boss",
                            "Mantém pressão constante — memória ou morte",
                            "Sinergia: EMP — destrói balas ocultas em área"],
    MUTATOR_GLASS_CANNON:  ["1 vida · 3× dano ao boss · parry 3× mais forte",
                            "Glass Cannon clássico — compensa com agressividade",
                            "Sinergia: SHIELD/PARRY — única chance de absorver acerto"],
    MUTATOR_HORDE:         ["Boss +50% HP · Boss −15% velocidade",
                            "Tank: difícil de matar mas mais lento e previsível",
                            "Sinergia: CARREGADO — tiro cheio maximiza DPS em boss tanque"],
    MUTATOR_BERSERKER:     ["Boss −25% HP · Boss +35% velocidade",
                            "Berserker: mata rápido antes que o boss te alcance",
                            "Sinergia: AGULHA — bala rápida acompanha boss acelerado"],
    MUTATOR_CLAUSTROFOBIA: [f"Arena reduzida em {int(ARENA_SHRINK*100)}% em cada lado",
                            "Menos espaço de esquiva — proximidade constante com o boss",
                            "★ BLOQUEADO — vencer Invocador com Pacifista de Elite"],
}

_MLL_X, _MLL_W = 80,  338
_MRP_X, _MRP_W = 450, 742
_MC_Y0, _MC_Y1 = 150, 666

_STEP_COLS  = [(80,220,80), (80,180,255), (255,220,0), (220,50,60), (140,80,255)]
_STEP_NAMES = ["DIFICULDADE", "BOSS", "HABILIDADE", "ARMA", "MUTADORES"]


def _mbg(surf):
    surf.fill(BG_COLOR)


def _mheader(surf, big, font, step: int, crumb: list):
    """step = 1..5.  Draws 5 progress dots + breadcrumb."""
    cx = SCREEN_W // 2
    sh = big.render("BULLET  HELL", True, (30, 30, 50))
    surf.blit(sh, (cx - sh.get_width()//2 + 2, 10))
    t = big.render("BULLET  HELL", True, WHITE)
    surf.blit(t, (cx - t.get_width()//2, 8))

    dot_r, dot_gap = 5, 20
    n_dots = 5
    span = n_dots * dot_r*2 + (n_dots-1) * dot_gap
    x0 = cx - span // 2 + dot_r
    for i in range(n_dots):
        xd = x0 + i * (dot_r*2 + dot_gap)
        if i < step - 1:
            pygame.draw.circle(surf, tuple(c//2 for c in _STEP_COLS[i]), (xd, 82), dot_r)
        elif i == step - 1:
            pygame.draw.circle(surf, _STEP_COLS[i], (xd, 82), dot_r)
            pygame.draw.circle(surf, WHITE, (xd, 82), dot_r + 3, 1)
        else:
            pygame.draw.circle(surf, (30, 30, 50), (xd, 82), dot_r, 2)

    sn = font.render(_STEP_NAMES[step-1], True, (80, 80, 110))
    surf.blit(sn, (cx - sn.get_width()//2, 94))

    if crumb:
        bc = font.render("  ›  ".join(crumb), True, (52, 52, 78))
        surf.blit(bc, (cx - bc.get_width()//2, 116))

    pygame.draw.line(surf, (26, 26, 46), (72, 140), (SCREEN_W - 72, 140), 1)


def _mhint(surf, font, text: str):
    pygame.draw.rect(surf, (8, 8, 18), (0, 672, SCREEN_W, 48))
    pygame.draw.line(surf, (28, 28, 48), (0, 672), (SCREEN_W, 672), 1)
    ht = font.render(text, True, (58, 58, 80))
    surf.blit(ht, (SCREEN_W//2 - ht.get_width()//2, 688))


def _left_item(surf, font, y: int, h: int, name: str, color: tuple,
               focused: bool, badge: str = ""):
    x, w = _MLL_X, _MLL_W
    bg = (22, 22, 40) if focused else (13, 13, 22)
    pygame.draw.rect(surf, bg, (x, y, w, h))
    bar = color if focused else tuple(max(0, c * 2 // 5) for c in color)
    pygame.draw.rect(surf, bar, (x, y, 4, h))
    nc = WHITE if focused else (95, 95, 110)
    surf.blit(font.render(name, True, nc), (x + 18, y + h//2 - 9))
    if badge:
        bt = font.render(badge, True, bar)
        surf.blit(bt, (x + w - bt.get_width() - 14, y + h//2 - 9))
    if focused:
        pygame.draw.polygon(surf, color,
            [(x+w+4, y+h//2-7), (x+w+4, y+h//2+7), (x+w+16, y+h//2)])
    pygame.draw.line(surf, (20, 20, 36), (x, y+h), (x+w, y+h), 1)


def _right_panel(surf, big, font, name: str, color: tuple, desc: list):
    rx, ry = _MRP_X, _MC_Y0
    rw, rh = _MRP_W, _MC_Y1 - _MC_Y0
    pygame.draw.rect(surf, (11, 11, 21), (rx, ry, rw, rh))
    pygame.draw.rect(surf, (28, 28, 50), (rx, ry, rw, rh), 1)
    pygame.draw.rect(surf, color, (rx, ry, rw, 3))
    wash = pygame.Surface((rw - 2, rh // 2), pygame.SRCALPHA)
    wash.fill((color[0], color[1], color[2], 9))
    surf.blit(wash, (rx + 1, ry + rh // 2))
    nt = big.render(name, True, color)
    surf.blit(nt, (rx + 28, ry + 22))
    sep_y = ry + 98
    pygame.draw.line(surf, tuple(max(0, c//3) for c in color),
                     (rx + 28, sep_y), (rx + rw - 28, sep_y), 1)
    for j, line in enumerate(desc):
        lt = font.render(line, True, (168, 168, 196))
        surf.blit(lt, (rx + 28, sep_y + 18 + j * 30))


# ---- Menu screens -----------------------------------------------------------

_GM_COLORS = [(200, 200, 200), (255, 140, 30), (80, 200, 100)]
_GM_LABELS = ["CLÁSSICO", "BOSS RUSH", "SOBREVIVÊNCIA"]
_GM_DESC   = [
    ["Escolha seu Boss e vença em batalha única.",
     "Modo original — focado, sem surpresas.",
     "Conquistas e recordes habilitados."],
    ["Sequência de Bosses — escolha a playlist.",
     "Cura +1 vida entre cada boss eliminado.",
     "Derrote todos para a vitória final."],
    ["Ondas crescentes de inimigos do EnemyPool.",
     "A cada 10 ondas um Boss aparece.",
     "Sobreviva 30 ondas para vencer."],
]

_RUSH_COLORS  = [(255, 180, 50), (180, 40, 255)]
_RUSH_LABELS  = ["BOSS RUSH CLÁSSICO", "OS 7 PECADOS"]
_RUSH_DESC    = [
    ["8 Bosses em ordem fixa — do clássico ao Ômega.",
     "Sem aleatoriedade — domine cada padrão.",
     "HP sem escala."],
    ["7 bosses dos Pecados Capitais em ordem aleatória.",
     "Chefe final: PECADO ORIGINAL aguarda ao fim.",
     "HP escala +15% por stage."],
]


def render_menu_game_mode(surf, big, font, sel: int):
    _mbg(surf)
    cx = SCREEN_W // 2
    sh = big.render("BULLET  HELL", True, (30, 30, 50))
    surf.blit(sh, (cx - sh.get_width()//2 + 2, 10))
    t  = big.render("BULLET  HELL", True, WHITE)
    surf.blit(t, (cx - t.get_width()//2, 8))
    sn = font.render("MODO DE JOGO", True, (80, 80, 110))
    surf.blit(sn, (cx - sn.get_width()//2, 94))
    pygame.draw.line(surf, (26, 26, 46), (72, 140), (SCREEN_W - 72, 140), 1)

    ITEM_H, GAP = 120, 12
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for i in range(3):
        iy = center_y + (i - sel) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        _left_item(surf, font, iy, ITEM_H, _GM_LABELS[i], _GM_COLORS[i], i == sel)
    surf.set_clip(old_clip)

    _right_panel(surf, big, font, _GM_LABELS[sel], _GM_COLORS[sel], _GM_DESC[sel])
    _mhint(surf, font, "W/S   navegar        D · ENTER   confirmar        ESC   menu principal")


def render_menu_rush_playlist(surf, big, font, sel: int):
    _mbg(surf)
    cx = SCREEN_W // 2
    sh = big.render("BOSS  RUSH", True, (30, 30, 50))
    surf.blit(sh, (cx - sh.get_width()//2 + 2, 10))
    t = big.render("BOSS  RUSH", True, (255, 140, 30))
    surf.blit(t, (cx - t.get_width()//2, 8))
    sn = font.render("SELECIONAR PLAYLIST", True, (80, 80, 110))
    surf.blit(sn, (cx - sn.get_width()//2, 94))
    pygame.draw.line(surf, (26, 26, 46), (72, 140), (SCREEN_W - 72, 140), 1)

    ITEM_H, GAP = 120, 12
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for i in range(2):
        iy = center_y + (i - sel) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        _left_item(surf, font, iy, ITEM_H, _RUSH_LABELS[i], _RUSH_COLORS[i], i == sel)
    surf.set_clip(old_clip)

    _right_panel(surf, big, font, _RUSH_LABELS[sel], _RUSH_COLORS[sel], _RUSH_DESC[sel])
    _mhint(surf, font, "W/S   navegar        D · ENTER   confirmar        ESC   voltar")


def _render_boss_rush_pause(surf, big, font, boss_idx: int, total: int, t_left: float,
                             wave_mode: bool = False, rush_label: str = "BOSS RUSH"):
    """Overlay entre bosses no Boss Rush (ou após boss de onda no Wave Survival)."""
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surf.blit(overlay, (0, 0))

    cx = SCREEN_W // 2

    if wave_mode:
        title = "BOSS DA ONDA ELIMINADO!"
        sub   = "PREPARANDO PRÓXIMA ONDA..."
    else:
        title = f"{rush_label}  —  BOSS {boss_idx}/{total} ELIMINADO!"
        sub   = "+1 VIDA RECUPERADA"

    t1 = big.render(title, True, (255, 220, 60))
    surf.blit(t1, (cx - t1.get_width()//2, 260))

    t2 = font.render(sub, True, (100, 255, 120))
    surf.blit(t2, (cx - t2.get_width()//2, 340))

    secs = max(0, int(t_left) + 1)
    if not wave_mode:
        t3_str = f"Próximo boss em {secs}s..." if t_left > 0.1 else "Preparando..."
    else:
        t3_str = f"Continuando em {secs}s..." if t_left > 0.1 else "Preparando..."
    t3 = font.render(t3_str, True, (160, 160, 200))
    surf.blit(t3, (cx - t3.get_width()//2, 390))


def render_menu_diff(surf, big, font, sel: int, save: SaveManager = None):
    _mbg(surf)
    _mheader(surf, big, font, 1, [])
    ITEM_H, GAP = 114, 10
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    sel_idx = _DIFF_ORDER.index(sel) if sel in _DIFF_ORDER else 0
    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for rank, d in enumerate(_DIFF_ORDER):
        iy = center_y + (rank - sel_idx) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        locked = save is not None and save.diff_locked(d)
        name   = GameConfig.DIFF_LABELS[d] + ("  [BLOQUEADO]" if locked else "")
        col    = (28, 28, 36) if locked else _DIFF_COLORS[d]
        _left_item(surf, font, iy, ITEM_H, name, col, d == sel)
    surf.set_clip(old_clip)

    _right_panel(surf, big, font, GameConfig.DIFF_LABELS[sel], _DIFF_COLORS[sel], _DIFF_DESC[sel])
    _mhint(surf, font, "W/S   navegar        D · ENTER   confirmar        ESC   menu principal")


def render_menu_boss(surf, big, font, sel: int, diff: int, save: 'SaveManager' = None):
    _mbg(surf)
    _mheader(surf, big, font, 2, [GameConfig.DIFF_LABELS[diff]])
    omega_vis   = save is None or save.omega_boss_unlocked
    visible     = [i for i in CLASSIC_BOSS_IDS if i != BOSS_OMEGA or omega_vis]
    cursor_slot = visible.index(sel) if sel in visible else 0
    ITEM_H, GAP = 90, 8
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for slot, i in enumerate(visible):
        iy = center_y + (slot - cursor_slot) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        _left_item(surf, font, iy, ITEM_H, GameConfig.BOSS_LABELS[i], _BOSS_COLORS[i], i == sel)
    surf.set_clip(old_clip)

    _right_panel(surf, big, font, GameConfig.BOSS_LABELS[sel], _BOSS_COLORS[sel], _BOSS_DESC[sel])
    _mhint(surf, font, "W/S   navegar        D · ENTER   confirmar        A · ESC   voltar")


def render_menu_skill(surf, big, font, sel: int, diff: int, boss: int,
                      save: SaveManager = None, sel_skill_plus: bool = False):
    _mbg(surf)
    _mheader(surf, big, font, 3, [GameConfig.DIFF_LABELS[diff], GameConfig.BOSS_LABELS[boss]])
    ITEM_H, GAP = 60, 4
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for i in range(N_SKILLS):
        iy = center_y + (i - sel) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        locked = save is not None and save.skill_locked(i)
        plus_badge = "★+" if (save is not None and save.is_skill_plus_unlocked(i)) else ""
        name   = GameConfig.SKILL_LABELS[i] + (plus_badge and f"  {plus_badge}") + ("  [BLOQUEADO]" if locked else "")
        col    = (28, 28, 36) if locked else _SKILL_COLORS[i]
        _left_item(surf, font, iy, ITEM_H, name, col, i == sel)
    surf.set_clip(old_clip)

    plus_avail = save is not None and save.is_skill_plus_unlocked(sel)
    if sel_skill_plus and plus_avail:
        panel_name  = GameConfig.SKILL_LABELS[sel] + "  ★+"
        panel_desc  = _SKILL_PLUS_DESC.get(sel, _SKILL_DESC[sel])
        panel_color = _SKILL_COLORS[sel]
    else:
        panel_name  = GameConfig.SKILL_LABELS[sel]
        panel_desc  = _SKILL_DESC[sel]
        panel_color = _SKILL_COLORS[sel]
    _right_panel(surf, big, font, panel_name, panel_color, panel_desc)

    if plus_avail:
        hint = "W/S   navegar        ESPAÇO   versão+        D · ENTER   confirmar        A · ESC   voltar"
    else:
        hint = "W/S   navegar        D · ENTER   confirmar        A · ESC   voltar"
    _mhint(surf, font, hint)


def render_menu_weapon(surf, big, font, sel: int, diff: int, boss: int, skill: int,
                        save=None, sel_weapon_plus: bool = False):
    _mbg(surf)
    _mheader(surf, big, font, 4,
             [GameConfig.DIFF_LABELS[diff], GameConfig.BOSS_LABELS[boss],
              GameConfig.SKILL_LABELS[skill]])
    ITEM_H, GAP = 94, 8
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))
    for i in range(N_WEAPONS):
        iy = center_y + (i - sel) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1: continue
        label = GameConfig.WEAPON_LABELS[i]
        if save is not None and save.is_weapon_plus_unlocked(i):
            label = label + " ★"
        _left_item(surf, font, iy, ITEM_H, label, _WEAPON_COLORS[i], i == sel)
    surf.set_clip(old_clip)

    plus_avail = save is not None and save.is_weapon_plus_unlocked(sel)
    if sel_weapon_plus and plus_avail:
        panel_name = GameConfig.WEAPON_LABELS[sel] + "  ★+"
        panel_desc = _WEAPON_PLUS_DESC.get(sel, _WEAPON_DESC[sel])
    else:
        panel_name = GameConfig.WEAPON_LABELS[sel]
        panel_desc = _WEAPON_DESC[sel]
    _right_panel(surf, big, font, panel_name, _WEAPON_COLORS[sel], panel_desc)

    if plus_avail:
        hint_extra = "        ESPAÇO versão+" if not sel_weapon_plus else "        ESPAÇO versão base"
    else:
        hint_extra = ""
    _mhint(surf, font, f"W/S   navegar        D · ENTER   confirmar        A · ESC   voltar{hint_extra}")


def render_menu_mutator(surf, big, font, selected: set, diff: int, boss: int,
                        skill: int, weapon: int, cursor: int = 0, save=None):
    _mbg(surf)
    _mheader(surf, big, font, 5,
             [GameConfig.DIFF_LABELS[diff], GameConfig.BOSS_LABELS[boss],
              GameConfig.SKILL_LABELS[skill], GameConfig.WEAPON_LABELS[weapon]])

    ITEM_H, GAP = 122, 10
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))

    for i in range(N_MUTATORS):
        iy = center_y + (i - cursor) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1:
            continue
        locked = save is not None and save.mutator_locked(i)
        if locked:
            badge = "[BLOQUEADO]"
            col   = (70, 70, 70)
        else:
            badge = "● ON " if i in selected else ""
            col   = _MUTATOR_COLORS[i]
        _left_item(surf, font, iy, ITEM_H,
                   GameConfig.MUTATOR_LABELS[i], col, i == cursor, badge)

    surf.set_clip(old_clip)

    _right_panel(surf, big, font,
                 GameConfig.MUTATOR_LABELS[cursor], _MUTATOR_COLORS[cursor], _MUTATOR_DESC[cursor])
    _mhint(surf, font,
           "W/S   navegar        ESPAÇO   toggle        D · ENTER   iniciar        A · ESC   voltar")


# ===========================================================================
# Developer cheat sequence  (W W S S A D A D — Konami WASD)
# ===========================================================================
_DEV_SEQ = (
    pygame.K_w, pygame.K_w,
    pygame.K_s, pygame.K_s,
    pygame.K_a, pygame.K_d,
    pygame.K_a, pygame.K_d,
)

_DEV_CMDS = [
    ("F9",  "Desbloquear tudo"),
    ("F10", "Apagar save"),
    ("F5",  "Matar boss [PLAYING]"),
    ("F6",  "God mode toggle"),
    ("F3",  "Boss HP → 50% [PLAYING]"),
    ("F4",  "Boss HP → 10% [PLAYING]"),
    ("F7",  "Avançar fase do boss [PLAYING]"),
]


def render_dev_overlay(surf: pygame.Surface, font: pygame.Font, dev_mode: bool,
                       godmode: bool, buf_progress: int, bal_flash: float = 0.0):
    """Corner overlay: badge always, command list only when dev_mode is on."""
    # Badge in top-right corner
    tag_col = (255, 60, 200) if dev_mode else (60, 60, 80)
    tag     = font.render("[ DEV ]", True, tag_col)
    surf.blit(tag, (SCREEN_W - tag.get_width() - 10, 44))

    # Balance reload notification
    if bal_flash > 0.0:
        alpha = min(255, int(bal_flash * 255))
        rl = font.render("⟳ BALANCE RELOADED", True, (80, 255, 160))
        rl.set_alpha(alpha)
        surf.blit(rl, (SCREEN_W - rl.get_width() - 10, 26))

    # Progress dots for sequence input (bottom-left)
    if 0 < buf_progress < len(_DEV_SEQ):
        for i in range(len(_DEV_SEQ)):
            col = (255, 220, 60) if i < buf_progress else (40, 40, 50)
            pygame.draw.circle(surf, col, (18 + i * 14, SCREEN_H - 14), 4)

    if not dev_mode:
        return

    # Command panel
    PW, PH = 260, len(_DEV_CMDS) * 26 + 18
    px, py = SCREEN_W - PW - 8, 64
    panel  = pygame.Surface((PW, PH), pygame.SRCALPHA)
    panel.fill((10, 10, 20, 200))
    surf.blit(panel, (px, py))
    pygame.draw.rect(surf, (255, 60, 200), (px, py, PW, PH), 1)
    for i, (key, desc) in enumerate(_DEV_CMDS):
        kc = (255, 220, 60)
        dc = (180, 180, 180) if i < 2 else ((0, 255, 160) if godmode and i == 3 else (140, 140, 160))
        kt = font.render(key,  True, kc)
        dt = font.render(desc, True, dc)
        y  = py + 9 + i * 26
        surf.blit(kt, (px + 8,  y))
        surf.blit(dt, (px + 50, y))


# ===========================================================================
# Navigation helpers (skip locked options)
# ===========================================================================
_DIFF_ORDER = [DIFF_EASY, DIFF_NORMAL, DIFF_HARD, DIFF_EXPERT, DIFF_ABISSAL]

def _nav_diff(cur: int, direction: int, save: SaveManager) -> int:
    idx = _DIFF_ORDER.index(cur) if cur in _DIFF_ORDER else 0
    for _ in range(len(_DIFF_ORDER)):
        idx = (idx + direction) % len(_DIFF_ORDER)
        d = _DIFF_ORDER[idx]
        if not save.diff_locked(d): return d
    return cur

def _nav_skill(cur: int, direction: int, save: SaveManager) -> int:
    n = len(GameConfig.SKILL_LABELS)
    for _ in range(n):
        cur = (cur + direction) % n
        if not save.skill_locked(cur): return cur
    return cur

def _nav_boss(cur: int, direction: int, save: SaveManager) -> int:
    ids = CLASSIC_BOSS_IDS
    idx = ids.index(cur) if cur in ids else 0
    for _ in range(len(ids)):
        idx = (idx + direction) % len(ids)
        cand = ids[idx]
        if cand != BOSS_OMEGA or save.omega_boss_unlocked: return cand
    return cur


# ===========================================================================
# Menu Principal
# ===========================================================================
_MAIN_ITEMS = ["INICIAR", "CONQUISTAS", "REGISTROS", "SISTEMA", "SAIR"]
_MAIN_COLS  = [(80, 220, 80), (255, 200, 40), (80, 200, 140), (100, 160, 255), (220, 50, 50)]


def render_main_menu(surf, big, font, sel: int, cheat_flash: float = 0.0,
                     cheat_msg: str = "CHEAT ATIVADO"):
    _mbg(surf)
    if cheat_flash > 0.0:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        a = min(80, int(cheat_flash * 80))
        s.fill((255, 220, 40, a))
        surf.blit(s, (0, 0))

    cx = SCREEN_W // 2
    sh = big.render("BULLET  HELL", True, (25, 25, 40))
    surf.blit(sh, (cx - sh.get_width()//2 + 2, 130))
    t  = big.render("BULLET  HELL", True, WHITE)
    surf.blit(t, (cx - t.get_width()//2, 128))

    ITEM_H, GAP = 72, 14
    total_h = len(_MAIN_ITEMS) * ITEM_H + (len(_MAIN_ITEMS)-1) * GAP
    iy = SCREEN_H // 2 - total_h // 2 + 40
    for i, name in enumerate(_MAIN_ITEMS):
        focused = i == sel
        col     = _MAIN_COLS[i]
        bg      = (22, 22, 40) if focused else (12, 12, 20)
        w       = 360
        rx      = cx - w // 2
        pygame.draw.rect(surf, bg, (rx, iy + i*(ITEM_H+GAP), w, ITEM_H))
        bar_col = col if focused else tuple(c//3 for c in col)
        pygame.draw.rect(surf, bar_col, (rx, iy + i*(ITEM_H+GAP), 4, ITEM_H))
        nc = WHITE if focused else (80, 80, 96)
        lbl = font.render(name, True, nc)
        surf.blit(lbl, (rx + 22, iy + i*(ITEM_H+GAP) + ITEM_H//2 - 9))
        if focused:
            pygame.draw.polygon(surf, col,
                [(rx+w+6, iy+i*(ITEM_H+GAP)+ITEM_H//2-7),
                 (rx+w+6, iy+i*(ITEM_H+GAP)+ITEM_H//2+7),
                 (rx+w+18, iy+i*(ITEM_H+GAP)+ITEM_H//2)])
        pygame.draw.line(surf, (20, 20, 36),
                         (rx, iy+i*(ITEM_H+GAP)+ITEM_H),
                         (rx+w, iy+i*(ITEM_H+GAP)+ITEM_H), 1)

    if cheat_flash > 0.0:
        ct  = font.render(cheat_msg, True, YELLOW)
        surf.blit(ct, (cx - ct.get_width()//2, SCREEN_H - 60))
    else:
        ht = font.render("W/S   navegar        ENTER   confirmar        F9 cheat        F10 wipe",
                         True, (35, 35, 50))
        surf.blit(ht, (cx - ht.get_width()//2, SCREEN_H - 40))


def render_records(surf, big, font, save: SaveManager):
    _mbg(surf)
    cx = SCREEN_W // 2
    t  = big.render("REGISTROS", True, YELLOW)
    surf.blit(t, (cx - t.get_width()//2, 80))
    pygame.draw.line(surf, (50, 50, 20), (180, 162), (SCREEN_W-180, 162), 1)

    st = save.stats
    m, s = divmod(int(st["best_survival_hard"]), 60)
    rows = [
        ("Mortes totais",           str(st["total_deaths"])),
        ("Melhor tempo (Hard)",     f"{m:02d}:{s:02d}"),
        ("Parries perfeitos",       str(st["total_parries"])),
        ("Dif. desbloqueada",
         GameConfig.DIFF_LABELS[save.highest_cleared_diff]),
        ("Skills desbloqueadas",
         "  ".join(GameConfig.SKILL_LABELS[sk] for sk in sorted(save.unlocked_skills))),
    ]
    for i, (label, value) in enumerate(rows):
        lbl = font.render(label, True, (120, 120, 140))
        val = font.render(value, True, WHITE)
        y   = 210 + i * 52
        surf.blit(lbl, (220, y))
        surf.blit(val, (SCREEN_W - 220 - val.get_width(), y))
        pygame.draw.line(surf, (24, 24, 36), (180, y+32), (SCREEN_W-180, y+32), 1)

    ht = font.render("ESC   voltar ao menu principal", True, (35, 35, 50))
    surf.blit(ht, (cx - ht.get_width()//2, SCREEN_H - 40))


# ===========================================================================
# Achievements
# ===========================================================================
ACHIEVEMENTS_DEF = [
    # ── Progressão de dificuldade ──────────────────────────────────────────
    {"id": "easy_win",    "name": "Iniciante",       "secret": False,
     "desc": "Complete a dificuldade Fácil.",         "reward": "Habilidade: PARRY"},
    {"id": "normal_win",  "name": "Veterano",         "secret": False,
     "desc": "Complete a dificuldade Normal.",        "reward": "Habilidade: FOCUS"},
    {"id": "hard_win",    "name": "Mestre",           "secret": False,
     "desc": "Complete a dificuldade Difícil.",       "reward": None},
    {"id": "grazes_100",  "name": "Esquivador",       "secret": False,
     "desc": "Acumule 100 Grazes no total.",          "reward": "Habilidade: EMP",
     "prog_max": 100, "prog_stat": "grazes"},
    {"id": "parries_50",  "name": "Espadachim",       "secret": False,
     "desc": "Deflecte 50 balas com Parry.",          "reward": "Habilidade: ESCUDO",
     "prog_max": 50,  "prog_stat": "parries"},
    {"id": "no_hit_win",  "name": "Perfecionista",    "secret": False,
     "desc": "Vença sem tomar nenhum dano.",          "reward": "Habilidade: BLINK"},
    {"id": "mutator_hard","name": "Risco Máximo",     "secret": False,
     "desc": "Vença Hard com 1+ Mutador ativo.",      "reward": "Habilidade: OVERCLOCK"},
    {"id": "omega_unlock","name": "Imparável",         "secret": False,
     "desc": "Vença Hard com 3 Mutadores simultaneamente.", "reward": "Boss: ÔMEGA ★"},
    # ── Bosses especiais ───────────────────────────────────────────────────
    {"id": "equilibrio_perfeito", "name": "Equilíbrio Perfeito", "secret": False,
     "desc": "Derrote os Gêmeos com menos de 3s entre as mortes.", "reward": "Habilidade: DILATAÇÃO"},
    {"id": "pacifista_elite",     "name": "Pacifista de Elite",   "secret": False,
     "desc": "Derrote o Invocador eliminando menos de 10 lacaios.", "reward": "Mutador: CLAUSTROFOBIA"},
    # ── Maestria de Habilidades (Skill+) ──────────────────────────────────
    {"id": "sp_dash",      "name": "Arrancada Espectral", "secret": False,
     "desc": f"Graze {MASTERY_DASH_GRAZES} vezes durante i-frames do Dash.",
     "reward": "DASH+"},
    {"id": "sp_parry",     "name": "Royal Guard",         "secret": False,
     "desc": f"Deflecte {MASTERY_PARRY_BURST}+ balas em uma única janela de Parry.",
     "reward": "PARRY+"},
    {"id": "sp_emp",       "name": "Sobrecarga Sináptica","secret": False,
     "desc": f"Destrua {MASTERY_EMP_BULLETS}+ balas em uma única ativação de EMP.",
     "reward": "EMP+"},
    {"id": "sp_blink",     "name": "Relâmpago Fantasma",  "secret": False,
     "desc": "Teleporte através do corpo do boss com o Blink.",
     "reward": "BLINK+"},
    {"id": "sp_overclock", "name": "Modo Berserk",        "secret": False,
     "desc": f"Cause {int(MASTERY_OC_DMG)}+ de dano em uma única janela de Overclock.",
     "reward": "OVERCLOCK+"},
    {"id": "sp_shield",    "name": "Muralha Elástica",    "secret": False,
     "desc": f"Execute {MASTERY_SHIELD_PERFECT} blocos perfeitos acumulados com o Escudo.",
     "reward": "ESCUDO+"},
    {"id": "sp_timedil",   "name": "Ruptura Temporal",    "secret": False,
     "desc": "Ative Dilatação com uma bala inimiga a ≤5px do jogador.",
     "reward": "DILATAÇÃO+"},
    # ── Maestria de Armas (Weapon+) ────────────────────────────────────────
    {"id": "wp_default",   "name": "Ricocheteiro",        "secret": False,
     "desc": f"Acumule {MASTERY_W_DEFAULT_HITS} acertos consecutivos com a PADRÃO sem errar.",
     "reward": "PADRÃO+"},
    {"id": "wp_spread",    "name": "Ponto-Cego",          "secret": False,
     "desc": f"Acerte o boss a <40px de distância {MASTERY_W_SPREAD_CLOSE} vezes com a SPREAD.",
     "reward": "SPREAD+"},
    {"id": "wp_needle",    "name": "Penetrante",          "secret": False,
     "desc": f"Complete uma fase do boss com a AGULHA cometendo ≤5 erros.",
     "reward": "AGULHA+"},
    {"id": "wp_charged",   "name": "Fragmentação",        "secret": False,
     "desc": f"Destrua ≥3 lacaios com um único tiro Carregado, {MASTERY_W_CHARGED_MULTI} vezes.",
     "reward": "CARREGADO+"},
    {"id": "wp_burst",     "name": "Minas de Atraso",     "secret": False,
     "desc": f"Acerte os {BURST_SHOTS} tiros da rajada BURST nos Gêmeos, {MASTERY_W_BURST_TWINS} vezes.",
     "reward": "BURST+"},
    {"id": "wp_homing",    "name": "Enxame Orbital",      "secret": False,
     "desc": f"Vença {MASTERY_W_HOMING_NOHIT} vezes sem tomar dano usando TELEGUIADO.",
     "reward": "TELEGUIADO+"},
    {"id": "wp_flak",      "name": "Detonador",           "secret": False,
     "desc": f"Destrua {MASTERY_W_FLAK_BULLETS} balas inimigas com estilhaços FLAK em uma run.",
     "reward": "FLAK+"},
    {"id": "wp_chakram",   "name": "Congelador",          "secret": False,
     "desc": f"Complete {MASTERY_W_CHAKRAM_ROUND} viagens de ida e volta com o CHAKRAM.",
     "reward": "CHAKRAM+"},
    {"id": "wp_plasma",    "name": "Rastro de Calor",     "secret": False,
     "desc": f"Mantenha contato de PLASMA com o boss por {MASTERY_W_PLASMA_CONT:.0f}s acumulados.",
     "reward": "PLASMA+"},
    {"id": "wp_orbit",     "name": "Interceptor",         "secret": False,
     "desc": f"Cause {int(MASTERY_W_ORBIT_DAMAGE)} de dano ao boss com as gemas SATÉLITE.",
     "reward": "SATÉLITE+"},
    # ── Conquistas secretas — sempre por último ────────────────────────────
    {"id": "parries_200", "name": "Senhor do Parry",  "secret": True,
     "desc": "Deflecte 200 balas no total.",          "reward": None,
     "prog_max": 200, "prog_stat": "parries"},
    {"id": "speed_hard",  "name": "Speed Runner",     "secret": True,
     "desc": "Vença Hard em menos de 3 minutos.",     "reward": None},
    {"id": "all_mutators","name": "Além do Limite",   "secret": True,
     "desc": "Vença com os 3 Mutadores ativos.",      "reward": None},
    {"id": "no_skill",    "name": "Intocável",        "secret": True,
     "desc": "Vença com habilidade NENHUMA.",         "reward": None},
    {"id": "omega_hard",  "name": "O Fim",            "secret": True,
     "desc": "Derrote o ÔMEGA na dificuldade Difícil.", "reward": None},
]


def _ach_progress(ach: dict, save) -> float | None:
    """Returns 0.0–1.0 progress fraction, or None if not applicable."""
    stat = ach.get("prog_stat")
    if stat is None:
        return None
    val = (save.achievements["total_grazes"] if stat == "grazes"
           else save.stats["total_parries"])
    return min(val / ach["prog_max"], 1.0)


def render_achievements(surf, big, font, save: SaveManager, cursor: int = 0):
    _mbg(surf)
    cx = SCREEN_W // 2
    t  = big.render("CONQUISTAS", True, (255, 200, 40))
    surf.blit(t, (cx - t.get_width()//2, 56))
    pygame.draw.line(surf, (60, 50, 15), (180, 138), (SCREEN_W - 180, 138), 1)

    ITEM_H, GAP = 36, 3
    STEP   = ITEM_H + GAP
    area_h = _MC_Y1 - _MC_Y0
    center_y = _MC_Y0 + (area_h - ITEM_H) // 2

    old_clip = surf.get_clip()
    surf.set_clip(pygame.Rect(_MLL_X, _MC_Y0, _MLL_W + 24, area_h))

    for i, ach in enumerate(ACHIEVEMENTS_DEF):
        iy = center_y + (i - cursor) * STEP
        if iy + ITEM_H <= _MC_Y0 or iy >= _MC_Y1:
            continue
        unlocked  = ach["id"] in save.achieved
        is_secret = ach["secret"] and not unlocked
        name      = "???" if is_secret else ach["name"]
        focused   = i == cursor

        col   = (255, 200, 40) if unlocked else ((50, 50, 72) if is_secret else (100, 130, 200))
        badge = "✓" if unlocked else ("???" if is_secret else "")
        _left_item(surf, font, iy, ITEM_H, name, col, focused, badge)

        # Progress bar for non-secret, non-unlocked counter achievements
        if not is_secret and not unlocked:
            prog = _ach_progress(ach, save)
            if prog is not None:
                bx  = _MLL_X + 18
                bby = iy + ITEM_H - 6
                bw  = _MLL_W - 32
                pygame.draw.rect(surf, (30, 30, 50), (bx, bby, bw, 3))
                pygame.draw.rect(surf, (80, 160, 80), (bx, bby, int(bw * prog), 3))

    surf.set_clip(old_clip)

    # Right panel — selected achievement details
    sel = ACHIEVEMENTS_DEF[cursor]
    unlocked  = sel["id"] in save.achieved
    is_secret = sel["secret"] and not unlocked
    disp_name  = "???" if is_secret else sel["name"]
    disp_col   = (255, 200, 40) if unlocked else ((70, 70, 90) if is_secret else (100, 130, 200))
    disp_desc  = ["Conquista secreta.",
                  "Descubra as condições para desbloquear."] if is_secret else [sel["desc"]]
    if not is_secret and sel.get("reward"):
        disp_desc.append(f"Recompensa: {sel['reward']}")

    # Status line
    if unlocked:
        disp_desc.append("[ DESBLOQUEADO ✓ ]")
    elif not is_secret:
        prog = _ach_progress(sel, save)
        if prog is not None:
            pct = int(prog * 100)
            current = (save.achievements["total_grazes"] if sel.get("prog_stat") == "grazes"
                       else save.stats["total_parries"])
            disp_desc.append(f"Progresso: {current}/{sel['prog_max']}  ({pct}%)")
        else:
            disp_desc.append("[ BLOQUEADO ]")

    _right_panel(surf, big, font, disp_name, disp_col, disp_desc)

    # Summary count at bottom
    total = len(ACHIEVEMENTS_DEF)
    done  = sum(1 for a in ACHIEVEMENTS_DEF if a["id"] in save.achieved)
    cnt_t = font.render(f"{done} / {total} conquistas desbloqueadas", True, (120, 120, 140))
    surf.blit(cnt_t, (cx - cnt_t.get_width() // 2, SCREEN_H - 68))

    _mhint(surf, font, "W/S   navegar        ESC   voltar ao menu")


def render_settings(surf, big, font, save: SaveManager, settings_sel: int):
    _mbg(surf)
    cx = SCREEN_W // 2
    t  = big.render("SISTEMA", True, (100, 160, 255))
    surf.blit(t, (cx - t.get_width()//2, 80))
    pygame.draw.line(surf, (30, 50, 80), (180, 162), (SCREEN_W-180, 162), 1)

    options = [
        ("Tela Cheia",    "LIGADO" if save.settings["fullscreen"]   else "DESLIGADO"),
        ("Screen Shake",  "LIGADO" if save.settings["screen_shake"] else "DESLIGADO"),
        ("Mostrar Hitbox","LIGADO" if save.settings["show_hitbox"]  else "DESLIGADO"),
    ]
    ITEM_H, GAP = 80, 12
    iy = 210
    for i, (label, value) in enumerate(options):
        focused = i == settings_sel
        bg  = (20, 28, 44) if focused else (12, 12, 20)
        col = (100, 160, 255) if focused else (40, 60, 100)
        pygame.draw.rect(surf, bg, (180, iy + i*(ITEM_H+GAP), SCREEN_W-360, ITEM_H))
        pygame.draw.rect(surf, col,(180, iy + i*(ITEM_H+GAP), 4, ITEM_H))
        lbl = font.render(label, True, WHITE if focused else (80, 80, 96))
        val_col = GREEN if value == "LIGADO" else RED_COL
        val = font.render(f"[ {value} ]", True, val_col)
        surf.blit(lbl, (210, iy + i*(ITEM_H+GAP) + ITEM_H//2 - 9))
        surf.blit(val, (SCREEN_W - 220 - val.get_width(), iy + i*(ITEM_H+GAP) + ITEM_H//2 - 9))

    ht = font.render("W/S   navegar        ENTER/D   toggle        ESC   voltar",
                     True, (35, 35, 50))
    surf.blit(ht, (cx - ht.get_width()//2, SCREEN_H - 40))


# ===========================================================================
# AudioManager — 16 canais pré-alocados, zero-GC durante gameplay
# ===========================================================================
AUDIO_CHANNELS = 16

class AudioManager:
    _GROUPS = {
        'player': list(range(0, 5)),
        'boss':   list(range(5, 11)),
        'ui':     list(range(11, 16)),
    }

    def __init__(self):
        try:
            pygame.mixer.set_num_channels(AUDIO_CHANNELS)
            self._channels = [pygame.mixer.Channel(i) for i in range(AUDIO_CHANNELS)]
            self._rr    = {g: 0 for g in self._GROUPS}
            self._sounds: dict = {}
            self._ok    = True
        except Exception:
            self._ok = False

    def load(self, sound_id: str, path: str, volume: float = 1.0) -> bool:
        if not self._ok: return False
        try:
            s = pygame.mixer.Sound(path)
            s.set_volume(volume)
            self._sounds[sound_id] = s
            return True
        except Exception:
            return False

    def play(self, sound_id: str, group: str = 'ui'):
        if not self._ok or sound_id not in self._sounds: return
        sound = self._sounds[sound_id]
        ids = self._GROUPS[group]
        n   = len(ids)
        for _ in range(n):
            ci = ids[self._rr[group] % n]
            self._rr[group] = (self._rr[group] + 1) % n
            if not self._channels[ci].get_busy():
                self._channels[ci].play(sound)
                return
        self._channels[ids[0]].play(sound)

    def stop_all(self):
        if not self._ok: return
        for ch in self._channels: ch.stop()


# ===========================================================================
# Factory
# ===========================================================================
def new_game(config: GameConfig):
    if config is None: config = GameConfig()
    pool     = BulletPool()
    pb_pool  = PlayerBulletPool()
    ep       = EmitterPool()
    lp       = LaserPool()
    pp       = ParticlePool()
    enm_pool = EnemyPool()
    if config.boss_type == BOSS_SWARM:
        boss = SwarmBoss(config)
    elif config.boss_type == BOSS_WALL:
        boss = WallBoss(config)
    elif config.boss_type == BOSS_OMEGA:
        boss = OmegaBoss(config)
    elif config.boss_type == BOSS_TWINS:
        boss = TwinsBoss(config)
    elif config.boss_type == BOSS_SUMMONER:
        boss = SummonerBoss(config)
        boss.enm_pool = enm_pool
    else:
        boss = Boss(config)
    player = Player(config)
    shash  = SpatialHash()
    diff   = Difficulty(config.diff)
    diff.speed_mult = config.speed_mult
    return (pool, pb_pool, ep, lp, pp, boss, player, shash, diff, enm_pool)


def _make_boss_of_type(boss_type: int, cfg, enm_pool):
    """Cria um boss do tipo especificado sem recriar os outros pools."""
    if boss_type == BOSS_SWARM:    return SwarmBoss(cfg)
    if boss_type == BOSS_WALL:     return WallBoss(cfg)
    if boss_type == BOSS_OMEGA:    return OmegaBoss(cfg)
    if boss_type == BOSS_TWINS:    return TwinsBoss(cfg)
    if boss_type == BOSS_SUMMONER:
        b = SummonerBoss(cfg); b.enm_pool = enm_pool; return b
    # Sete Pecados
    if boss_type == BOSS_PRIDE:    return PrideBoss(cfg)
    if boss_type == BOSS_SLOTH:
        b = SlothBoss(cfg); b.enm_pool = enm_pool; return b
    if boss_type == BOSS_ENVY:     return EnvyBoss(cfg)
    if boss_type == BOSS_GLUTTONY: return GluttonyBoss(cfg)
    if boss_type == BOSS_GREED:    return GreedBoss(cfg)
    if boss_type == BOSS_LUST:     return LustBoss(cfg)
    if boss_type == BOSS_WRATH:    return WrathBoss(cfg)
    if boss_type == BOSS_SIN:      return SinBoss(cfg)
    if boss_type == BOSS_DUMMY:    return DummyBoss()
    return Boss(cfg)


# ===========================================================================
# Loop principal
# ===========================================================================
def main():
    pygame.init()
    screen    = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    game_surf = pygame.Surface((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Bullet Hell — Boss Fight")
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("consolas", 18)
    big   = pygame.font.SysFont("consolas", 52, bold=True)

    bullet_surf        = pygame.Surface((6, 6)); bullet_surf.fill(ORANGE)
    parried_surf       = pygame.Surface((6, 6)); parried_surf.fill((180, 80, 255))
    bullet_surf_blue   = pygame.Surface((6, 6)); bullet_surf_blue.fill((80, 200, 255))
    bullet_surf_orange = pygame.Surface((6, 6)); bullet_surf_orange.fill((255, 100, 30))
    bullet_surf_purple = pygame.Surface((6, 6)); bullet_surf_purple.fill((200, 80, 255))

    save           = SaveManager()
    cheat_flash    = 0.0   # positive → show cheat feedback overlay
    cheat_wipe     = False # True → render "SAVE APAGADO" instead of "CHEAT ATIVADO"
    dev_mode         = False
    godmode          = False
    bal_reload_flash = 0.0   # shows "BALANCE RELOADED" briefly in dev overlay
    cheat_buf: deque = deque(maxlen=len(_DEV_SEQ))

    # ---- Shake & hit-stop -------------------------------------------------
    shake_timer  = 0.0
    shake_amount = 0.0
    shake_x = shake_y = 0

    def trigger_shake(amount: float, duration: float):
        nonlocal shake_timer, shake_amount
        if amount > shake_amount: shake_amount = amount
        shake_timer = max(shake_timer, duration)

    hitstop_frames = 0

    def trigger_hitstop(frames: int):
        nonlocal hitstop_frames
        hitstop_frames = max(hitstop_frames, frames)

    # ---- Menu / game state ------------------------------------------------
    state              = MAIN_MENU
    main_menu_sel      = 0
    settings_sel       = 0
    achievements_cursor = 0
    sel_diff      = DIFF_EASY
    sel_boss      = BOSS_CLASSIC
    sel_skill     = SKILL_NONE
    sel_skill_plus  = False
    sel_weapon      = WEAPON_DEFAULT
    sel_weapon_plus = False
    sel_mutators: set = set()
    sel_mut_cur      = 0
    sel_game_mode     = GAME_MODE_CLASSIC   # seleção no SELECT_GAME_MODE
    sel_rush_playlist = 0                   # 0=Clássico 1=7 Pecados
    config            = None

    # Game mode runtime state
    game_mode         = GAME_MODE_CLASSIC
    wave_mgr          = None
    boss_rush_idx     = 0
    boss_rush_pause_t = 0.0
    boss_rush_mgr: BossRushManager = None   # orquestrador de playlists
    # Wave Survival: flag para pausar brevemente após boss de onda
    _wave_boss_pause  = False

    pool = pb_pool = ep = lp = pp = boss = player = shash = diff = enm_pool = None
    hz_pool = HazardPool()
    audio   = AudioManager()
    recorder: ReplayRecorder  = None
    replay_frame_idx  = 0
    elapsed           = 0.0
    intro_timer       = 4.0
    unlock_notifs     = []
    glass_cannon      = False
    # Rastreamento de conquistas por sessão de batalha
    minion_kills      = 0        # SummonerBoss
    twins_no_dmg_t    = 0.0     # TwinsBoss, reset ao tomar dano
    # EXPERT — Segundo Fôlego
    second_wind_active  = False
    second_wind_timer   = 0.0
    second_wind_done    = False
    second_wind_spray_t = 0.0
    # Detecção de mudança de fase (Balas de Vingança)
    _prev_boss_phase    = -1

    # Apply persisted display settings immediately
    if save.settings["fullscreen"]:
        screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
        game_surf = pygame.Surface((SCREEN_W, SCREEN_H))

    def _start_game(cfg, seed_val):
        """Seed RNG first so boss __init__ is deterministic, then build game objects."""
        nonlocal pool, pb_pool, ep, lp, pp, boss, player, shash, diff, enm_pool
        nonlocal glass_cannon, elapsed, intro_timer, recorder
        nonlocal minion_kills, twins_no_dmg_t
        nonlocal game_mode, wave_mgr, boss_rush_idx, boss_rush_pause_t, boss_rush_mgr
        nonlocal _wave_boss_pause
        nonlocal second_wind_active, second_wind_timer, second_wind_done, second_wind_spray_t
        nonlocal _prev_boss_phase, godmode
        random.seed(seed_val)
        pool, pb_pool, ep, lp, pp, boss, player, shash, diff, enm_pool = new_game(cfg)
        hz_pool.clear()
        glass_cannon   = MUTATOR_GLASS_CANNON in cfg.mutators
        elapsed        = 0.0
        intro_timer    = 4.0
        recorder       = ReplayRecorder(seed_val)
        minion_kills   = 0
        twins_no_dmg_t = 0.0
        second_wind_active = False; second_wind_timer = 0.0
        second_wind_done = False;   second_wind_spray_t = 0.0
        _prev_boss_phase = -1
        pool._abissal = (cfg.diff == DIFF_ABISSAL)
        if cfg.diff == DIFF_TEST:
            godmode = True
        # Game mode setup
        game_mode = sel_game_mode
        _wave_boss_pause = False
        if game_mode == GAME_MODE_BOSS_RUSH:
            boss_rush_idx = 0; boss_rush_pause_t = 0.0
            _rc = BossRushConfig.CLASSIC if sel_rush_playlist == 0 else BossRushConfig.SINS
            boss_rush_mgr = BossRushManager(_rc, cfg)
            _stage_cfg = boss_rush_mgr.make_game_config_for_stage()
            boss = _make_boss_of_type(boss_rush_mgr.current_boss_id(), _stage_cfg, enm_pool)
            wave_mgr = None
        elif game_mode == GAME_MODE_WAVE_SURVIVAL:
            boss_rush_mgr = None
            boss = NullBoss()
            wave_mgr = WaveManager(_WAVE_DEFS)
            wave_mgr.start_wave()
            enm_pool.clear()
            boss_rush_idx = 0; boss_rush_pause_t = 0.0
        else:
            boss_rush_mgr = None
            wave_mgr = None
            boss_rush_idx = 0; boss_rush_pause_t = 0.0

    def _start_replay():
        nonlocal pool, pb_pool, ep, lp, pp, boss, player, shash, diff, enm_pool
        nonlocal glass_cannon, elapsed, intro_timer, replay_frame_idx
        nonlocal minion_kills, twins_no_dmg_t
        recorder.start_replay()
        pool, pb_pool, ep, lp, pp, boss, player, shash, diff, enm_pool = new_game(config)
        hz_pool.clear()
        glass_cannon     = MUTATOR_GLASS_CANNON in config.mutators
        elapsed          = 0.0
        intro_timer      = 0.0
        replay_frame_idx = 0
        minion_kills     = 0
        twins_no_dmg_t   = 0.0

    while True:
        # ---- EVENTOS ----------------------------------------------------------
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()

            if ev.type != pygame.KEYDOWN:
                continue
            k = ev.key

            # ---- Dev cheat sequence (W W S S A D A D) — works from any state
            cheat_buf.append(k)
            if tuple(cheat_buf) == _DEV_SEQ:
                dev_mode = not dev_mode
                cheat_flash = 1.8; cheat_wipe = False; cheat_buf.clear()

            if dev_mode:
                if k == pygame.K_F9:
                    save.cheat_unlock_all(); cheat_flash = 1.8; cheat_wipe = False
                elif k == pygame.K_F10:
                    save.wipe_save()
                    sel_diff = DIFF_EASY; sel_skill = SKILL_NONE; sel_skill_plus = False
                    sel_weapon = WEAPON_DEFAULT; sel_weapon_plus = False
                    cheat_flash = 1.8; cheat_wipe = True
                elif state == PLAYING and k == pygame.K_F5:
                    boss.hp = 0
                elif state == PLAYING and k == pygame.K_F3:
                    boss.hp = max(1.0, boss.max_hp * 0.50)
                    if hasattr(boss, 'diff'): diff.update(boss.hp, boss.max_hp)
                elif state == PLAYING and k == pygame.K_F4:
                    boss.hp = max(1.0, boss.max_hp * 0.10)
                    if hasattr(boss, 'diff'): diff.update(boss.hp, boss.max_hp)
                elif state == PLAYING and k == pygame.K_F7:
                    # Avança fase: reduce HP abaixo do próximo threshold de fase
                    if hasattr(boss, '_PHASE_HP') and hasattr(boss, '_phase'):
                        _ph = boss._phase
                        _thresholds = boss._PHASE_HP
                        if _ph < len(_thresholds):
                            # Define HP logo abaixo do threshold da próxima fase
                            boss.hp = max(1.0, boss.max_hp * (_thresholds[_ph] - 0.01))
                        else:
                            boss.hp = 1.0
                    elif hasattr(boss, '_phase_idx'):
                        # OmegaBoss
                        boss.hp = max(1.0, boss.hp * 0.25)
                    else:
                        # Boss sem fases (Clássico, Enxame, etc.): mata diretamente
                        boss.hp = 1.0
                elif k == pygame.K_F6:
                    godmode = not godmode
                elif k == pygame.K_F8:
                    # Sala do Dummy — DIFF_TEST, DummyBoss
                    _sv_gm = sel_game_mode; sel_game_mode = GAME_MODE_CLASSIC
                    _dc = GameConfig(DIFF_TEST, BOSS_DUMMY, SKILL_NONE, WEAPON_DEFAULT)
                    _ds = random.randrange(1 << 31)
                    _start_game(_dc, _ds)
                    config = _dc; sel_game_mode = _sv_gm
                    unlock_notifs = []; state = PLAYING

            # ----------------------------------------------------------------
            # Back / ESC
            if k in (pygame.K_a, pygame.K_ESCAPE):
                if   state == SELECT_MUTATOR:       state = SELECT_WEAPON
                elif state == SELECT_WEAPON:        state = SELECT_SKILL
                elif state == SELECT_SKILL:
                    state = SELECT_BOSS if sel_game_mode == GAME_MODE_CLASSIC else SELECT_DIFF
                elif state == SELECT_BOSS:          state = SELECT_DIFF
                elif state == SELECT_DIFF:
                    state = SELECT_RUSH_PLAYLIST if sel_game_mode == GAME_MODE_BOSS_RUSH else SELECT_GAME_MODE
                elif state == SELECT_RUSH_PLAYLIST: state = SELECT_GAME_MODE
                elif state == SELECT_GAME_MODE:     state = MAIN_MENU
                elif state in (RECORDS, SETTINGS, ACHIEVEMENTS): state = MAIN_MENU
                elif state == REPLAYING:        state = WIN if boss.hp <= 0 else GAMEOVER
                elif state in (WIN, GAMEOVER):  state = MAIN_MENU
                elif state == BOSS_RUSH_PAUSE:  state = MAIN_MENU
                elif state == MAIN_MENU:        pygame.quit(); sys.exit()

            # ----------------------------------------------------------------
            # SELECT_GAME_MODE
            elif state == SELECT_GAME_MODE:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_game_mode = (sel_game_mode - 1) % 3
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_game_mode = (sel_game_mode + 1) % 3
                elif k in (pygame.K_d, pygame.K_RETURN):
                    if sel_game_mode == GAME_MODE_BOSS_RUSH:
                        state = SELECT_RUSH_PLAYLIST
                    else:
                        state = SELECT_DIFF

            # SELECT_RUSH_PLAYLIST
            elif state == SELECT_RUSH_PLAYLIST:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_rush_playlist = (sel_rush_playlist - 1) % 2
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_rush_playlist = (sel_rush_playlist + 1) % 2
                elif k in (pygame.K_d, pygame.K_RETURN):
                    state = SELECT_DIFF

            # ----------------------------------------------------------------
            # MAIN MENU
            elif state == MAIN_MENU:
                if k in (pygame.K_w, pygame.K_UP):
                    main_menu_sel = (main_menu_sel - 1) % len(_MAIN_ITEMS)
                elif k in (pygame.K_s, pygame.K_DOWN):
                    main_menu_sel = (main_menu_sel + 1) % len(_MAIN_ITEMS)
                elif k in (pygame.K_d, pygame.K_RETURN):
                    if main_menu_sel == 0:        # INICIAR
                        if save.diff_locked(sel_diff):   sel_diff  = DIFF_EASY
                        if save.skill_locked(sel_skill): sel_skill = SKILL_NONE
                        state = SELECT_GAME_MODE
                    elif main_menu_sel == 1: state = ACHIEVEMENTS
                    elif main_menu_sel == 2: state = RECORDS
                    elif main_menu_sel == 3: state = SETTINGS
                    elif main_menu_sel == 4: pygame.quit(); sys.exit()
            # ----------------------------------------------------------------
            # ACHIEVEMENTS
            elif state == ACHIEVEMENTS:
                if k in (pygame.K_w, pygame.K_UP):
                    achievements_cursor = (achievements_cursor - 1) % len(ACHIEVEMENTS_DEF)
                elif k in (pygame.K_s, pygame.K_DOWN):
                    achievements_cursor = (achievements_cursor + 1) % len(ACHIEVEMENTS_DEF)

            # ----------------------------------------------------------------
            # RECORDS
            elif state == RECORDS:
                pass  # ESC handled above

            # ----------------------------------------------------------------
            # SETTINGS
            elif state == SETTINGS:
                if k in (pygame.K_w, pygame.K_UP):
                    settings_sel = (settings_sel - 1) % 3
                elif k in (pygame.K_s, pygame.K_DOWN):
                    settings_sel = (settings_sel + 1) % 3
                elif k in (pygame.K_d, pygame.K_RETURN, pygame.K_SPACE):
                    if settings_sel == 0:   # Tela Cheia
                        save.settings["fullscreen"] = not save.settings["fullscreen"]
                        if save.settings["fullscreen"]:
                            screen    = pygame.display.set_mode((SCREEN_W, SCREEN_H), pygame.FULLSCREEN)
                            game_surf = pygame.Surface((SCREEN_W, SCREEN_H))
                        else:
                            screen    = pygame.display.set_mode((SCREEN_W, SCREEN_H))
                            game_surf = pygame.Surface((SCREEN_W, SCREEN_H))
                    elif settings_sel == 1: # Screen Shake
                        save.settings["screen_shake"] = not save.settings["screen_shake"]
                    elif settings_sel == 2: # Mostrar Hitbox
                        save.settings["show_hitbox"] = not save.settings["show_hitbox"]
                    save.persist()

            # ----------------------------------------------------------------
            # SELECT_DIFF
            elif state == SELECT_DIFF:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_diff = _nav_diff(sel_diff, -1, save)
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_diff = _nav_diff(sel_diff, +1, save)
                elif k in (pygame.K_d, pygame.K_RETURN):
                    if sel_game_mode == GAME_MODE_CLASSIC:
                        state = SELECT_BOSS
                    else:
                        state = SELECT_SKILL

            # SELECT_BOSS
            elif state == SELECT_BOSS:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_boss = _nav_boss(sel_boss, -1, save)
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_boss = _nav_boss(sel_boss, +1, save)
                elif k in (pygame.K_d, pygame.K_RETURN):
                    state = SELECT_SKILL

            # SELECT_SKILL
            elif state == SELECT_SKILL:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_skill = _nav_skill(sel_skill, -1, save)
                    sel_skill_plus = False
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_skill = _nav_skill(sel_skill, +1, save)
                    sel_skill_plus = False
                elif k == pygame.K_SPACE:
                    if save.is_skill_plus_unlocked(sel_skill):
                        sel_skill_plus = not sel_skill_plus
                elif k in (pygame.K_d, pygame.K_RETURN):
                    state = SELECT_WEAPON

            # SELECT_WEAPON
            elif state == SELECT_WEAPON:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_weapon = (sel_weapon - 1) % N_WEAPONS
                    sel_weapon_plus = False
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_weapon = (sel_weapon + 1) % N_WEAPONS
                    sel_weapon_plus = False
                elif k == pygame.K_SPACE:
                    if save.is_weapon_plus_unlocked(sel_weapon):
                        sel_weapon_plus = not sel_weapon_plus
                elif k in (pygame.K_d, pygame.K_RETURN):
                    state = SELECT_MUTATOR

            # SELECT_MUTATOR
            elif state == SELECT_MUTATOR:
                if k in (pygame.K_w, pygame.K_UP):
                    sel_mut_cur = (sel_mut_cur - 1) % N_MUTATORS
                elif k in (pygame.K_s, pygame.K_DOWN):
                    sel_mut_cur = (sel_mut_cur + 1) % N_MUTATORS
                elif k == pygame.K_SPACE:
                    if not save.mutator_locked(sel_mut_cur):
                        sel_mutators.symmetric_difference_update({sel_mut_cur})
                elif k in (pygame.K_d, pygame.K_RETURN):
                    config    = GameConfig(sel_diff, sel_boss, sel_skill, sel_weapon,
                                          frozenset(sel_mutators),
                                          skill_plus=sel_skill_plus,
                                          weapon_plus=sel_weapon_plus)
                    seed      = random.randrange(1 << 31)
                    _start_game(config, seed)
                    unlock_notifs = []
                    state = PLAYING

            # ----------------------------------------------------------------
            # In-game hotkeys
            elif state == PLAYING and k == pygame.K_h:
                save.settings["show_hitbox"] = not save.settings["show_hitbox"]

            # ----------------------------------------------------------------
            # WIN / GAMEOVER actions
            elif state in (WIN, GAMEOVER):
                if k == pygame.K_r:           # back to full menu
                    sel_mutators = set(); state = MAIN_MENU
                elif k == pygame.K_t:         # quick retry — same config, new seed
                    seed = random.randrange(1 << 31)
                    _start_game(config, seed)
                    unlock_notifs = []; state = PLAYING
                elif k == pygame.K_w and recorder and recorder.frames:
                    _start_replay(); state = REPLAYING

        # ---- dt ---------------------------------------------------------------
        dt   = min(clock.tick(TARGET_FPS) / 1000.0, 0.05)
        keys = pygame.key.get_pressed()

        # Hot-reload balance.json when dev_mode is on
        if _poll_balance(dt, dev_mode):
            bal_reload_flash = 2.0

        # ---- UPDATE -----------------------------------------------------------
        if hitstop_frames > 0 and state == PLAYING:
            hitstop_frames -= 1

        elif state in (PLAYING, REPLAYING):
            if state == REPLAYING:
                frame_data = recorder.replay_frame(replay_frame_idx)
                if frame_data is None:
                    state = WIN if boss.hp <= 0 else GAMEOVER
                    dt = 0.0
                else:
                    keys, dt = frame_data
                    replay_frame_idx += 1

            if state in (PLAYING, REPLAYING):
                intro_timer = max(0.0, intro_timer - dt)
                # ABISSAL: efeito Matrix — jogador age 10% mais devagar que as balas
                _player_dt = dt * 0.9 if (config is not None and config.diff == DIFF_ABISSAL) else dt
                # HAZARD_SLOW: névoa da luxúria — reduz velocidade à metade enquanto dentro da zona
                if hz_pool.check_player(player.cx, player.cy) == HAZARD_SLOW:
                    _player_dt *= 0.5
                # OVERCLOCK+: 4× fire rate mas 25% mais lento
                if player.skill_plus and player.skill == SKILL_OVERCLOCK and player.is_overclocking:
                    _player_dt *= OVERCLOCK_PLUS_SPD_F
                # BTYPE_GRAVITY: puxa o jogador em direção a cada poço gravitacional
                _grav_m = pool.active & (pool.b_type == BTYPE_GRAVITY)
                if _grav_m.any():
                    for _gi in np.where(_grav_m)[0]:
                        _gdx = float(pool.bx[_gi]) - player.cx
                        _gdy = float(pool.by[_gi]) - player.cy
                        _gdist = math.sqrt(_gdx*_gdx + _gdy*_gdy) + 1e-6
                        if _gdist > BULLET_GRAVITY_MIN_DIST:
                            _gf = BULLET_GRAVITY_PULL * dt / _gdist
                            player.cx = max(8.0, min(float(SCREEN_W) - 8.0,
                                                     player.cx + _gdx * _gf))
                            player.cy = max(8.0, min(float(SCREEN_H) - 8.0,
                                                     player.cy + _gdy * _gf))

                player.controls_inverted = getattr(boss, 'controls_inverted', False)
                _was_timedilating = player.is_timedilating
                player.update(_player_dt, keys)
                # TIMEDILATION maestria close-call: bala a ≤5px quando ativou
                if not _was_timedilating and player.is_timedilating:
                    if not save.mastery["timedil_close"]:
                        _cldx = pool.bx - player.cx; _cldy = pool.by - player.cy
                        if (pool.active & ((_cldx*_cldx + _cldy*_cldy) <= 25.0)).any():
                            save.mastery["timedil_close"] = True
                            player._timedil_close_used    = True
                # SHIELD+: anel de balas ao absorver hit perfeito
                if player._shield_broke:
                    player._shield_broke = False
                    for _si in range(SHIELD_PLUS_RING_N):
                        _sang = _si * (TWO_PI / SHIELD_PLUS_RING_N)
                        _svx  = math.cos(_sang) * SHIELD_PLUS_RING_SPD
                        _svy  = math.sin(_sang) * SHIELD_PLUS_RING_SPD
                        _sidx = pb_pool.acquire(1.0, _svx, _svy)
                        if _sidx >= 0:
                            pb_pool.px[_sidx] = player.cx
                            pb_pool.py[_sidx] = player.cy
                # TIMEDILATION+: destrói balas em raio ao expirar
                if player._timedil_just_ended:
                    _tr_sq = TIMEDIL_PLUS_RADIUS * TIMEDIL_PLUS_RADIUS
                    _tdx   = pool.bx - player.cx
                    _tdy   = pool.by - player.cy
                    _tmask = pool.active & ((_tdx*_tdx + _tdy*_tdy) <= _tr_sq)
                    for _tidx in np.where(_tmask)[0]:
                        pool.release(int(_tidx))
                    if _tmask.any():
                        pp.emit(player.cx, player.cy, (180, 80, 255),
                                24, 100, 280, 0.2, 0.5, radius=3.5)
                # TEST: sem cooldown de skill
                if config is not None and config.diff == DIFF_TEST:
                    player.skill_cd = 0.0

                # BLINK+: EMP de raio 60px na posição de origem do teleporte
                if player.skill_plus and player.skill == SKILL_BLINK and player._blink_fired:
                    _br_sq  = BLINK_PLUS_EMP_R * BLINK_PLUS_EMP_R
                    _bdx    = pool.bx - player._blink_ox
                    _bdy    = pool.by - player._blink_oy
                    _bmask  = pool.active & ((_bdx*_bdx + _bdy*_bdy) <= _br_sq)
                    for _bidx in np.where(_bmask)[0]:
                        pool.release(int(_bidx))
                    if _bmask.any():
                        pp.emit(player._blink_ox, player._blink_oy, (100, 200, 255),
                                20, 120, 250, 0.2, 0.4, radius=3.0)

                # BLINK maestria: blink_boss_pass — detecta se a trajetória passou pelo boss
                if player.skill == SKILL_BLINK and player._blink_fired and not save.mastery["blink_boss_pass"]:
                    _baabb = boss.get_aabb_list() if hasattr(boss, 'get_aabb_list') else []
                    if _baabb:
                        _ox, _oy = player._blink_ox, player._blink_oy
                        _dx2     = player.cx - _ox;  _dy2 = player.cy - _oy
                        for _bt in (0.25, 0.5, 0.75):
                            _tx = _ox + _dx2 * _bt;  _ty = _oy + _dy2 * _bt
                            for (_ax0, _ay0, _ax1, _ay1) in _baabb:
                                if _ax0 <= _tx <= _ax1 and _ay0 <= _ty <= _ay1:
                                    save.mastery["blink_boss_pass"] = True
                                    break

                if player.emp_triggered:
                    dx  = pool.bx - player.cx;  dy = pool.by - player.cy
                    emp_mask = pool.active & ((dx*dx + dy*dy) <= EMP_RADIUS**2)
                    for idx in np.where(emp_mask)[0]: pool.release(int(idx))
                    if player.skill_plus and player.skill == SKILL_EMP:
                        _emp_n = int(emp_mask.sum())
                        player._emp_buff_timer   = EMP_PLUS_BUFF_DUR
                        player._emp_dmg_mult     = 1.0 + _emp_n * EMP_PLUS_DMG_PER_BULL
                        player._emp_max_session  = max(player._emp_max_session, _emp_n)
                    else:
                        boss.stun_timer = EMP_STUN

                eff_dt = dt * FOCUS_SLOW if player.is_focusing else dt

                _prev_fire_key = getattr(player, '_last_fire_key', False)
                fire_key = keys[pygame.K_SPACE] or keys[pygame.K_z]
                player._last_fire_key = fire_key
                _fire_released = _prev_fire_key and not fire_key  # edge: True→False

                # ---- Charged weapon -------------------------------------------
                if player.weapon == WEAPON_CHARGED:
                    if player.charge_cd > 0:
                        player.charge_cd -= dt
                    if fire_key and player.charge_cd <= 0:
                        player.charge_t    = min(player.charge_t + dt, PB_CHARGED_MAX_T)
                        player.is_charging = True
                    elif player.is_charging:
                        t_frac = player.charge_t / PB_CHARGED_MAX_T
                        dmg    = PB_CHARGED_MIN_DMG + (PB_CHARGED_MAX_DMG - PB_CHARGED_MIN_DMG) * t_frac
                        size   = PB_CHARGED_MIN_SIZE + (PB_CHARGED_MAX_SIZE - PB_CHARGED_MIN_SIZE) * t_frac
                        # CARREGADO+: tag shots at ≥85% charge with pb_state=2 for shrapnel on hit
                        _c_state = 2 if (player.weapon_plus and t_frac >= 0.85) else 0
                        idx = pb_pool.acquire(dmg, 0.0, -PB_SPEED, size=size, state=_c_state)
                        if idx >= 0:
                            pb_pool.px[idx] = player.cx;  pb_pool.py[idx] = player.y
                        player.charge_t    = 0.0
                        player.is_charging = False
                        player.charge_cd   = PB_CHARGED_CD

                # ---- Burst weapon ---------------------------------------------
                elif player.weapon == WEAPON_BURST:
                    if player.burst_cd > 0:
                        player.burst_cd = max(0.0, player.burst_cd - dt)
                    _burst_interval = _b("weapons", "burst_interval", BURST_INTERVAL)
                    _burst_cd       = _b("weapons", "burst_cd",       BURST_CD)
                    _burst_dmg      = _b("weapons", "burst_damage",   PB_BURST_DAMAGE)
                    if fire_key and player.burst_cd <= 0 and player.burst_q == 0:
                        player.burst_q     = BURST_SHOTS
                        player.burst_sub_t = 0.0
                    if player.burst_q > 0:
                        player.burst_sub_t += dt
                        while player.burst_sub_t >= _burst_interval and player.burst_q > 0:
                            player.burst_sub_t -= _burst_interval
                            player.burst_q     -= 1
                            if player.weapon_plus:
                                # BURST+: baixa velocidade inicial, acelera após BURST_PLUS_ARM_T
                                idx = pb_pool.acquire(_burst_dmg, 0.0, -BURST_PLUS_INIT_SPD,
                                                      timer=BURST_PLUS_ARM_T, state=0,
                                                      orbit_angle=-math.pi / 2.0)
                            else:
                                idx = pb_pool.acquire(_burst_dmg)
                            if idx >= 0:
                                pb_pool.px[idx] = player.cx;  pb_pool.py[idx] = player.y
                        if player.burst_q == 0:
                            player.burst_cd = _burst_cd

                # ---- Homing missile swarm ------------------------------------
                elif player.weapon == WEAPON_HOMING:
                    if player.homing_cd > 0:
                        player.homing_cd = max(0.0, player.homing_cd - dt)
                    if player.weapon_plus:
                        # TELEGUIADO+: segure = orbitar, solte = atacar juntos
                        if fire_key and player.homing_cd <= 0:
                            player.homing_cd = HOMING_PLUS_FIRE_RATE
                            _hh_count = int(np.sum(pb_pool.active & (pb_pool.pb_type == PB_HOMING_HELD)))
                            _h_ang = -math.pi / 2.0 + _hh_count * (TWO_PI / max(1, PB_HOMING_N))
                            _hidx = pb_pool.acquire(PB_HOMING_DMG, 0.0, 0.0, size=3.0,
                                                    pb_type=PB_HOMING_HELD, orbit_angle=_h_ang)
                            if _hidx >= 0:
                                pb_pool.px[_hidx] = player.cx + math.cos(_h_ang) * HOMING_PLUS_ORBIT_R
                                pb_pool.py[_hidx] = player.cy + math.sin(_h_ang) * HOMING_PLUS_ORBIT_R
                        # On release: convert all held missiles to active homing
                        if _fire_released:
                            _hh_m2 = pb_pool.active & (pb_pool.pb_type == PB_HOMING_HELD)
                            for _hhi in np.where(_hh_m2)[0]:
                                _hhi = int(_hhi)
                                _bdx = _hx - pb_pool.px[_hhi]
                                _bdy = _hy - pb_pool.py[_hhi]
                                _bdd = math.sqrt(_bdx*_bdx + _bdy*_bdy) + 1e-6
                                _hspd = PB_HOMING_SPD * random.uniform(0.85, 1.15)
                                pb_pool.pvx[_hhi]    = _bdx / _bdd * _hspd
                                pb_pool.pvy[_hhi]    = _bdy / _bdd * _hspd
                                pb_pool.pb_type[_hhi]   = PB_NORMAL
                                pb_pool.pb_homing[_hhi] = True
                                pb_pool.pb_home_t[_hhi] = PB_HOMING_HOME_T
                    else:
                        if fire_key and player.homing_cd <= 0:
                            player.homing_cd = PB_HOMING_FIRE_RATE
                            for _ in range(PB_HOMING_N):
                                _hang = -math.pi / 2 + random.uniform(-PB_HOMING_ARC, PB_HOMING_ARC)
                                _hspd = PB_HOMING_SPD * random.uniform(0.85, 1.15)
                                _hvx  = math.cos(_hang) * _hspd
                                _hvy  = math.sin(_hang) * _hspd
                                idx = pb_pool.acquire(PB_HOMING_DMG, _hvx, _hvy, size=3.0,
                                                      homing=True, home_t=PB_HOMING_HOME_T)
                                if idx >= 0:
                                    pb_pool.px[idx] = player.cx + random.uniform(-8, 8)
                                    pb_pool.py[idx] = player.y

                # ---- FLAK --------------------------------------------------
                elif player.weapon == WEAPON_FLAK:
                    if player.extra_cd > 0:
                        player.extra_cd = max(0.0, player.extra_cd - dt)
                    if player.weapon_plus:
                        # FLAK+: detonação remota — freeze timer while fire held
                        _flak_held_m = pb_pool.active & (pb_pool.pb_type == PB_FLAK)
                        if _flak_held_m.any():
                            if fire_key:
                                pb_pool.pb_timer[_flak_held_m] = FLAK_TIMER  # freeze
                            elif _fire_released:
                                pb_pool.pb_timer[_flak_held_m] = 0.0  # detonate
                        if fire_key and player.extra_cd <= 0:
                            player.extra_cd = FLAK_FIRE_RATE
                            _fi = pb_pool.acquire(0.0, 0.0, -FLAK_SPEED, size=FLAK_SIZE,
                                                 pb_type=PB_FLAK, timer=FLAK_TIMER)
                            if _fi >= 0:
                                pb_pool.px[_fi] = player.cx; pb_pool.py[_fi] = player.y
                    else:
                        if fire_key and player.extra_cd <= 0:
                            player.extra_cd = FLAK_FIRE_RATE
                            _fi = pb_pool.acquire(0.0, 0.0, -FLAK_SPEED, size=FLAK_SIZE,
                                                 pb_type=PB_FLAK, timer=FLAK_TIMER)
                            if _fi >= 0:
                                pb_pool.px[_fi] = player.cx; pb_pool.py[_fi] = player.y

                # ---- CHAKRAM -----------------------------------------------
                elif player.weapon == WEAPON_CHAKRAM:
                    if player.extra_cd > 0:
                        player.extra_cd = max(0.0, player.extra_cd - dt)
                    if fire_key and player.extra_cd <= 0:
                        player.extra_cd = CHAKRAM_FIRE_RATE
                        _ci2 = pb_pool.acquire(CHAKRAM_DMG, 0.0, -CHAKRAM_SPEED,
                                               size=CHAKRAM_SIZE, pb_type=PB_CHAKRAM)
                        if _ci2 >= 0:
                            pb_pool.px[_ci2] = player.cx; pb_pool.py[_ci2] = player.y
                    if player.weapon_plus:
                        # CHAKRAM+: freeze airborne chakram while fire held at reversal
                        _chk_m = pb_pool.active & (pb_pool.pb_type == PB_CHAKRAM)
                        if _chk_m.any():
                            _chi_all = np.where(_chk_m)[0]
                            # Reversal zone: velocity crossing zero (was going up, now stalled)
                            _near_stop = _chk_m & (np.abs(pb_pool.pvy) < CHAKRAM_SPEED * 0.25)
                            if fire_key and _near_stop.any():
                                pb_pool.pb_state[_near_stop] = 2  # freeze
                                # CHAKRAM+ DPS: apply unconditionally — chakram apex is mid-screen,
                                # far from boss AABB; requiring AABB overlap made this never fire.
                                _frz_cnt = int(_near_stop.sum())
                                if boss and boss.hp > 0:
                                    boss.take_damage(CHAKRAM_PLUS_DPS * _frz_cnt * dt * (3.0 if glass_cannon else 1.0), diff)
                            elif not fire_key:
                                # Release freeze on all frozen chakrams → resume return
                                frz_m = _chk_m & (pb_pool.pb_state == 2)
                                if frz_m.any():
                                    pb_pool.pb_state[frz_m] = 1  # return state

                # ---- PLASMA ------------------------------------------------
                elif player.weapon == WEAPON_PLASMA:
                    if player.extra_cd > 0:
                        player.extra_cd = max(0.0, player.extra_cd - dt)
                    if fire_key and player.extra_cd <= 0:
                        player.extra_cd = PLASMA_FIRE_RATE
                        # PLASMA+: pb_state=1 signals update() to spawn puddle on expire
                        _pl_state = 1 if player.weapon_plus else 0
                        _pli = pb_pool.acquire(0.0, 0.0, -PLASMA_SPEED, size=PLASMA_SIZE,
                                               pb_type=PB_PLASMA, timer=PLASMA_LIFESPAN,
                                               state=_pl_state)
                        if _pli >= 0:
                            pb_pool.px[_pli] = player.cx; pb_pool.py[_pli] = player.y

                # ---- SATÉLITE (ORBIT) ---------------------------------------
                elif player.weapon == WEAPON_ORBIT:
                    if player.extra_cd > 0:
                        player.extra_cd = max(0.0, player.extra_cd - dt)
                    _orb_cnt = int((pb_pool.active & (pb_pool.pb_type == PB_ORBIT)).sum())
                    if fire_key and player.extra_cd <= 0 and _orb_cnt < ORBIT_MAX:
                        player.extra_cd = ORBIT_FIRE_RATE
                        _oang = -math.pi / 2.0 + _orb_cnt * (TWO_PI / ORBIT_MAX)
                        _oidi = pb_pool.acquire(ORBIT_DMG, 0.0, 0.0, size=ORBIT_SIZE,
                                                pb_type=PB_ORBIT, orbit_angle=_oang)
                        if _oidi >= 0:
                            pb_pool.px[_oidi] = player.cx + math.cos(_oang) * ORBIT_RADIUS
                            pb_pool.py[_oidi] = player.cy + math.sin(_oang) * ORBIT_RADIUS
                    # SATÉLITE+: auto-launch nearest satellite toward boss when in aggro range
                    if player.weapon_plus and boss and boss.hp > 0:
                        if player._orbit_launch_cd > 0:
                            player._orbit_launch_cd = max(0.0, player._orbit_launch_cd - dt)
                        _boss_cx = boss.cx if hasattr(boss, 'cx') else getattr(boss, 'x', 0.0)
                        _boss_cy = boss.cy if hasattr(boss, 'cy') else getattr(boss, 'y', 0.0)
                        _boss_dist = math.sqrt((player.cx - _boss_cx)**2 + (player.cy - _boss_cy)**2)
                        if _boss_dist <= ORBIT_PLUS_AGGRO_R and player._orbit_launch_cd <= 0:
                            _orb_ids = np.where(pb_pool.active & (pb_pool.pb_type == PB_ORBIT))[0]
                            if len(_orb_ids) > 0:
                                # Find nearest satellite to boss
                                _sat_dx = pb_pool.px[_orb_ids] - _boss_cx
                                _sat_dy = pb_pool.py[_orb_ids] - _boss_cy
                                _sat_dist2 = _sat_dx*_sat_dx + _sat_dy*_sat_dy
                                _amin = int(np.argmin(_sat_dist2))
                                _nearest = int(_orb_ids[_amin])
                                # Convert to homing missile toward boss
                                _sd = math.sqrt(float(_sat_dist2[_amin])) + 1e-6
                                pb_pool.pvx[_nearest]       = -_sat_dx[_amin] / _sd * PB_HOMING_SPD
                                pb_pool.pvy[_nearest]       = -_sat_dy[_amin] / _sd * PB_HOMING_SPD
                                pb_pool.pb_type[_nearest]   = PB_NORMAL
                                pb_pool.pb_homing[_nearest] = True
                                pb_pool.pb_home_t[_nearest] = PB_HOMING_HOME_T
                                player._orbit_launch_cd     = ORBIT_PLUS_LAUNCH_CD

                # ---- Standard weapons (DEFAULT, SPREAD, NEEDLE) ---------------
                if player.weapon not in (WEAPON_CHARGED, WEAPON_BURST, WEAPON_HOMING,
                                           WEAPON_FLAK, WEAPON_CHAKRAM, WEAPON_PLASMA, WEAPON_ORBIT):
                    _fr_base  = _b("player", "fire_rate",        PLAYER_FIRE_RATE)
                    _fr_oc    = _b("player", "overclock_mult",   OVERCLOCK_FIRE_RATE_MULT)
                    _fr_needle= _b("player", "fire_rate_needle", PB_NEEDLE_FIRE_RATE)
                    # OVERCLOCK+: 4× cadência (mult 0.25 no intervalo)
                    _eff_oc_m = (OVERCLOCK_PLUS_FR_MULT if (player.skill_plus and player.skill == SKILL_OVERCLOCK)
                                 else _fr_oc)
                    _eff_fr   = _fr_base * (_eff_oc_m if player.is_overclocking else 1.0)
                    _ndl_fr   = _fr_needle * (_eff_oc_m if player.is_overclocking else 1.0)
                    weapon_rate = _ndl_fr if player.weapon == WEAPON_NEEDLE else _eff_fr
                    if fire_key:
                        player.shoot_acc += dt
                    else:
                        player.shoot_acc = 0.0
                    # AGULHA+: 20% slower fire rate
                    if player.weapon == WEAPON_NEEDLE and player.weapon_plus:
                        weapon_rate = weapon_rate * NEEDLE_PLUS_CD_MULT
                    while player.shoot_acc >= weapon_rate:
                        player.shoot_acc -= weapon_rate
                        if player.weapon == WEAPON_SPREAD:
                            _spd = _b("weapons", "spread_speed",  PB_SPREAD_SPEED)
                            _dmg = _b("weapons", "spread_damage", PB_SPREAD_DAMAGE)
                            if player.weapon_plus:
                                _dmg = SPREAD_PLUS_DMG
                                _range_t = SPREAD_PLUS_MAX_RANGE / _spd
                            else:
                                _range_t = 0.0
                            for off in (-WEAPON_SPREAD_ANGLE, 0.0, WEAPON_SPREAD_ANGLE):
                                vx = math.sin(off) * _spd
                                vy = -math.cos(off) * _spd
                                if player.weapon_plus:
                                    idx = pb_pool.acquire(_dmg, vx, vy, state=1,
                                                          timer=_range_t)
                                else:
                                    idx = pb_pool.acquire(_dmg, vx, vy)
                                if idx < 0: break
                                pb_pool.px[idx] = player.cx;  pb_pool.py[idx] = player.y
                            # SPREAD mastery: close events (<40px from boss center)
                            if boss and boss.hp > 0:
                                _bpx = boss.cx if hasattr(boss, 'cx') else getattr(boss, 'x', 0.0)
                                _bpy = boss.cy if hasattr(boss, 'cy') else getattr(boss, 'y', 0.0)
                                if ((player.cx - _bpx)**2 + (player.cy - _bpy)**2) < 1600.0:
                                    player._wm_close_events += 1
                        elif player.weapon == WEAPON_NEEDLE:
                            _nspd = _b("weapons", "needle_speed",  PB_NEEDLE_SPEED)
                            _ndmg = _b("weapons", "needle_damage", PB_NEEDLE_DAMAGE)
                            if player.weapon_plus:
                                idx = pb_pool.acquire(_ndmg, 0.0, -_nspd, pierce=True)
                            else:
                                idx = pb_pool.acquire(_ndmg, 0.0, -_nspd)
                            if idx >= 0:
                                pb_pool.px[idx] = player.cx;  pb_pool.py[idx] = player.y
                        else:
                            # WEAPON_DEFAULT — PADRÃO+: add bounces
                            if player.weapon_plus:
                                idx = pb_pool.acquire(_b("weapons", "default_damage", 1.0),
                                                      bounces=DEFAULT_PLUS_BOUNCES)
                            else:
                                idx = pb_pool.acquire(_b("weapons", "default_damage", 1.0))
                            if idx >= 0:
                                pb_pool.px[idx] = player.cx;  pb_pool.py[idx] = player.y

                # Compute homing target: nearest boss position to player
                _hx, _hy = 0.0, 0.0
                if boss:
                    if isinstance(boss, TwinsBoss) and boss._phase == 1:
                        _d2y = (boss.yin_x  - player.cx)**2 + (boss.yin_y  - player.cy)**2
                        _d2g = (boss.yang_x - player.cx)**2 + (boss.yang_y - player.cy)**2
                        _hx, _hy = (boss.yin_x, boss.yin_y) if _d2y < _d2g else (boss.yang_x, boss.yang_y)
                    elif isinstance(boss, TwinsBoss) and boss._scenario == 'yin':
                        _hx, _hy = boss.yin_x,  boss.yin_y
                    elif isinstance(boss, TwinsBoss):
                        _hx, _hy = boss.yang_x, boss.yang_y
                    elif hasattr(boss, 'cx'):
                        _hx, _hy = boss.cx, boss.cy
                    else:
                        _hx, _hy = getattr(boss, 'x', 0.0), getattr(boss, 'y', 0.0)
                pb_pool.update(dt, _hx, _hy)

                # ORBIT: reposiciona gemas em torno do jogador
                _orb_m = pb_pool.active & (pb_pool.pb_type == PB_ORBIT)
                if _orb_m.any():
                    pb_pool.pb_orbit_a[_orb_m] += ORBIT_ANG_SPD * dt
                    _oi = np.where(_orb_m)[0]
                    pb_pool.px[_oi] = player.cx + np.cos(pb_pool.pb_orbit_a[_oi]) * ORBIT_RADIUS
                    pb_pool.py[_oi] = player.cy + np.sin(pb_pool.pb_orbit_a[_oi]) * ORBIT_RADIUS

                # TELEGUIADO+: reposiciona mísseis em órbita enquanto segurados
                _hh_m = pb_pool.active & (pb_pool.pb_type == PB_HOMING_HELD)
                if _hh_m.any():
                    pb_pool.pb_orbit_a[_hh_m] += HOMING_PLUS_ORB_SPD * dt
                    _hhi_arr = np.where(_hh_m)[0]
                    pb_pool.px[_hhi_arr] = player.cx + np.cos(pb_pool.pb_orbit_a[_hhi_arr]) * HOMING_PLUS_ORBIT_R
                    pb_pool.py[_hhi_arr] = player.cy + np.sin(pb_pool.pb_orbit_a[_hhi_arr]) * HOMING_PLUS_ORBIT_R

                # CHAKRAM: captura quando retorna ao jogador
                _chk_ret_m = pb_pool.active & (pb_pool.pb_type == PB_CHAKRAM) & (pb_pool.pb_state == 1)
                if _chk_ret_m.any():
                    _cri = np.where(_chk_ret_m)[0]
                    _crdx = pb_pool.px[_cri] - player.cx
                    _crdy = pb_pool.py[_cri] - player.cy
                    _close_c = _cri[(_crdx*_crdx + _crdy*_crdy) <= CHAKRAM_CATCH_R**2]
                    for _cci in _close_c:
                        pb_pool.release(int(_cci))
                        pp.emit(player.cx, player.cy, (0, 220, 255), 8,
                                60, 160, 0.15, 0.35, radius=3.0)

                # OVERCLOCK+ damage tracking
                _oc_track = (player.skill_plus and player.skill == SKILL_OVERCLOCK
                             and player.is_overclocking)
                _boss_hp_pre = boss.hp if _oc_track else 0.0
                # EMP+: apply dmg mult while buff active
                _emp_plus_mult = (player._emp_dmg_mult
                                  if (player.skill_plus and player.skill == SKILL_EMP
                                      and player._emp_buff_timer > 0.0)
                                  else 1.0)
                pb_hits = check_boss_collision(pb_pool, boss, diff, glass_cannon,
                                              dmg_mult=_emp_plus_mult)
                if _oc_track and pb_hits:
                    player._oc_dmg_acc += max(0.0, _boss_hp_pre - boss.hp)
                if pb_hits:
                    bx_ref = boss.cx if hasattr(boss, 'cx') else boss.x
                    by_ref = boss.cy if hasattr(boss, 'cy') else boss.y
                    pp.emit(bx_ref, by_ref, (255, 140, 40), pb_hits * 3,
                            60, 180, 0.25, 0.55, radius=4.0)
                    # ORBIT mastery: accumulate damage from orbit satellites
                    if player.weapon == WEAPON_ORBIT:
                        player._wm_orbit_dmg += float(pb_hits) * ORBIT_DMG
                    # PADRÃO mastery: count consecutive hits
                    if player.weapon == WEAPON_DEFAULT:
                        player._wm_consec_hits += pb_hits
                elif player.weapon == WEAPON_DEFAULT and player.shoot_acc <= 0 and fire_key:
                    player._wm_consec_hits = 0  # reset on miss (no hit this fire cycle)

                # CARREGADO+: spawn estilhaços radiais em posições de hit
                if player.weapon == WEAPON_CHARGED and player.weapon_plus and pb_pool._hit_buf_n > 0:
                    for _hbi in range(pb_pool._hit_buf_n):
                        _hbx = float(pb_pool._hit_buf[_hbi, 0])
                        _hby = float(pb_pool._hit_buf[_hbi, 1])
                        for _fk in range(CHARGED_PLUS_FRAG_N):
                            _fang = _fk * (TWO_PI / CHARGED_PLUS_FRAG_N)
                            _fpi = pb_pool.acquire(CHARGED_PLUS_FRAG_DMG,
                                                   math.cos(_fang) * CHARGED_PLUS_FRAG_SPD,
                                                   math.sin(_fang) * CHARGED_PLUS_FRAG_SPD,
                                                   size=CHARGED_PLUS_FRAG_SZ)
                            if _fpi >= 0:
                                pb_pool.px[_fpi] = _hbx; pb_pool.py[_fpi] = _hby
                    pb_pool._hit_buf_n = 0

                # PLASMA: colisão por DPS (pierce — não libera balas)
                _plasma_hit = check_plasma_boss_collision(pb_pool, boss, diff, glass_cannon, dt)
                if _plasma_hit:
                    diff.update(boss.hp, boss.max_hp)
                    bx_ref = boss.cx if hasattr(boss, 'cx') else boss.x
                    by_ref = boss.cy if hasattr(boss, 'cy') else boss.y
                    pp.emit(bx_ref, by_ref, (160, 60, 255), 4, 40, 120, 0.1, 0.3, radius=3.0)
                    # PLASMA mastery: track continuous contact streak
                    if player.weapon == WEAPON_PLASMA:
                        player._wm_plasma_streak += dt
                        player._wm_plasma_contact = max(player._wm_plasma_contact,
                                                        player._wm_plasma_streak)
                elif player.weapon == WEAPON_PLASMA:
                    player._wm_plasma_streak = 0.0  # reset streak on no contact

                # OVERCLOCK+ window end detection
                if player._oc_was_active and not player.is_overclocking:
                    player._oc_dmg_max = max(player._oc_dmg_max, player._oc_dmg_acc)
                    player._oc_dmg_acc = 0.0
                player._oc_was_active = player.is_overclocking

                # EnemyPool — SummonerBoss minions + Wave Survival enemies
                _use_enm = enm_pool is not None and (isinstance(boss, (SummonerBoss, SlothBoss))
                                                     or game_mode == GAME_MODE_WAVE_SURVIVAL)
                if _use_enm:
                    e_kills = enm_pool.check_pb_hit(pb_pool, glass_cannon)
                    # Faíscas em hits não-letais
                    if enm_pool._hit_n > 0:
                        for _hi in range(enm_pool._hit_n):
                            pp.emit(float(enm_pool._hit_xs[_hi]),
                                    float(enm_pool._hit_ys[_hi]),
                                    WHITE, 5, 90, 200, 0.08, 0.22, radius=2.0)
                    if e_kills:
                        minion_kills += e_kills
                        for _ki in range(enm_pool._kill_n):
                            pp.emit(float(enm_pool._kill_xs[_ki]),
                                    float(enm_pool._kill_ys[_ki]),
                                    (220, 200, 60), 12,
                                    60, 200, 0.2, 0.55, radius=3.5)
                        # ABISSAL — Balas de Vingança: ring roxo de cada minion morto
                        if diff.revenge_bullets:
                            for _ki in range(enm_pool._kill_n):
                                _kx = float(enm_pool._kill_xs[_ki])
                                _ky = float(enm_pool._kill_ys[_ki])
                                for _ri in range(8):
                                    _ang = _ri * (TWO_PI / 8)
                                    _bidx = pool.acquire()
                                    if _bidx < 0: break
                                    pool.bx[_bidx] = _kx;  pool.by[_bidx] = _ky
                                    pool.bvx[_bidx] = math.cos(_ang) * 150.0
                                    pool.bvy[_bidx] = math.sin(_ang) * 150.0
                                    pool.b_type[_bidx]  = BTYPE_PURPLE
                                    pool.btimer[_bidx]  = TWIN_PURPLE_HOME_T

                boss.update(eff_dt, pool, ep, lp, player.cx, player.cy, diff,
                            player.vx, player.vy)

                # ABISSAL — Balas de Vingança na mudança de fase do boss
                _cur_phase = getattr(boss, '_phase', -1)
                if (diff.revenge_bullets and _cur_phase != _prev_boss_phase
                        and _prev_boss_phase >= 0):
                    _bx_r = boss.cx if hasattr(boss, 'cx') else boss.x
                    _by_r = boss.cy if hasattr(boss, 'cy') else boss.y
                    for _ri in range(8):
                        _ang = _ri * (TWO_PI / 8)
                        _bidx = pool.acquire()
                        if _bidx < 0: break
                        pool.bx[_bidx] = _bx_r;  pool.by[_bidx] = _by_r
                        pool.bvx[_bidx] = math.cos(_ang) * 160.0
                        pool.bvy[_bidx] = math.sin(_ang) * 160.0
                        pool.b_type[_bidx]  = BTYPE_PURPLE
                        pool.btimer[_bidx]  = TWIN_PURPLE_HOME_T
                _prev_boss_phase = _cur_phase

                # Forças externas do boss sobre o jogador (gravidade, magnetismo)
                if state == PLAYING:
                    _bf = getattr(boss, 'player_force', None)
                    if _bf is not None:
                        fx, fy = _bf
                        player.x = max(0.0, min(float(SCREEN_W - PLAYER_SIZE),
                                                player.x + fx * eff_dt))
                        player.y = max(0.0, min(float(SCREEN_H - PLAYER_SIZE),
                                                player.y + fy * eff_dt))

                    # EnvyBoss — penalidade de skill_cd
                    _sk_pen = getattr(boss, 'player_skill_penalty', 0.0)
                    if _sk_pen > 0.0 and player.skill_cd > 0.0:
                        player.skill_cd += _sk_pen * eff_dt

                    # WrathBoss P2 — corpo em chamas causa dano por contato
                    if (isinstance(boss, WrathBoss) and boss.body_dmg_active
                            and player.invuln == 0 and not godmode):
                        _bdx = player.cx - boss.body_x
                        _bdy = player.cy - boss.body_y
                        if _bdx*_bdx + _bdy*_bdy <= (boss.body_r + PLAYER_RADIUS) ** 2:
                            player.lives -= 1; player.total_hits += 1
                            player.invuln = INVULN_FRAMES
                            pp.emit(player.cx, player.cy, (220, 50, 20), 18,
                                    60, 200, 0.25, 0.6, radius=4.0)
                            trigger_shake(8.0, 0.25)

                    # GreedBoss P1 — moedas explodem quando atingidas por player bullets
                    if isinstance(boss, GreedBoss) and boss._phase == 1:
                        for _ci in range(boss.MAX_COINS):
                            if not boss.coin_active[_ci]: continue
                            _cx = float(boss.coin_x[_ci]); _cy = float(boss.coin_y[_ci])
                            _pm = pb_pool.active & (np.abs(pb_pool.px - _cx) < 12) & (np.abs(pb_pool.py - _cy) < 12)
                            _ph = np.where(_pm)[0]
                            if len(_ph):
                                boss.coin_explode(_ci, pool)
                                for _pi in _ph: pb_pool.release(int(_pi))
                                pp.emit(_cx, _cy, (200, 160, 0), 10, 80, 200, 0.2, 0.5)
                                break

                    # SinBoss — ativa/desativa screen wrap com a fase 1
                    if isinstance(boss, SinBoss):
                        pool._screen_wrap = (boss._phase == 1)

                    # LustBoss — névoa de feromônios (hz requests enfileirados no update)
                    if isinstance(boss, LustBoss) and boss._hz_n > 0:
                        for _lhi in range(boss._hz_n):
                            hz_pool.spawn(float(boss._hz_x[_lhi]), float(boss._hz_y[_lhi]),
                                          55.0, 6.0, HAZARD_SLOW)
                        boss._hz_n = 0

                # Pulso de Inversão — flash visual quando azul e laranja trocam
                if isinstance(boss, TwinsBoss) and boss.inversion_flash:
                    ix, iy = boss.yin_x, boss.yin_y
                    pp.emit(ix, iy, (80, 160, 255),  40, 160, 320, 0.25, 0.8, radius=4.0)
                    pp.emit(ix, iy, (255, 120, 30),  40, 160, 320, 0.25, 0.8, radius=4.0)
                    pp.emit(ix, iy, WHITE,            15, 100, 200, 0.2,  0.5, radius=2.5)
                    trigger_shake(6.0, 0.25)

                # Absorção do gêmeo morto → burst de partículas no local da morte
                if isinstance(boss, TwinsBoss) and boss.absorb_emit:
                    pp.emit(boss._absorb_x, boss._absorb_y,
                            (80, 200, 255) if boss._scenario == 'yang' else (255, 120, 30),
                            60, 140, 280, 0.5, 1.2, radius=5.0)
                    pp.emit(boss._absorb_x, boss._absorb_y, WHITE, 20, 80, 160, 0.3, 0.7)
                    trigger_shake(18.0, 0.6)

                # HazardPool — Boss Clássico (BLASTER) spawna poças de queimadura
                if isinstance(boss, Boss) and not boss.in_prep and boss.pattern == Boss.BLASTER:
                    _hz_prev = boss.phase_t - eff_dt
                    if int(boss.phase_t / 2.8) > int(_hz_prev / 2.8):
                        hz_pool.spawn(player.cx + random.uniform(-70, 70),
                                      player.cy + random.uniform(-50, 50),
                                      48.0, 5.0, HAZARD_BURN)
                hz_pool.update(eff_dt)

                # Dilatação Temporal: bullet pool congela enquanto ativa
                _bull_dt = 0.0 if player.is_timedilating else eff_dt
                pool.update(_bull_dt, player.cx, player.cy)
                ep.update(eff_dt, pool)
                lp.update(eff_dt)
                pp.update(dt)

                # EnemyPool movement (Invocador + Wave Survival)
                if enm_pool is not None and (isinstance(boss, (SummonerBoss, SlothBoss))
                                             or game_mode == GAME_MODE_WAVE_SURVIVAL):
                    enm_pool.update(eff_dt, pool, player.cx, player.cy, diff.speed_mult)

                # Wave Survival — spawn + wave progression
                if game_mode == GAME_MODE_WAVE_SURVIVAL and wave_mgr is not None:
                    if not wave_mgr.boss_wave and not isinstance(boss, NullBoss):
                        pass  # real boss active, skip spawning
                    elif not wave_mgr.boss_wave:
                        _wave_done = wave_mgr.update(eff_dt, enm_pool,
                                                     player.cx, player.cy)
                        if _wave_done:
                            wave_mgr.next_wave()
                            if wave_mgr.game_won:
                                pass  # handled in boss.hp <= 0 block below via forced win
                    if wave_mgr.boss_wave and isinstance(boss, NullBoss):
                        _wv_type = wave_mgr.boss_type
                        _wv_cfg  = GameConfig(config.diff, _wv_type, config.skill,
                                              config.weapon, config.mutators)
                        boss = _make_boss_of_type(_wv_type, _wv_cfg, enm_pool)
                        enm_pool.clear()
                        pool.clear(); ep.clear(); lp.clear(); hz_pool.clear()

                shash.build(pool)

                _parry_plus = player.skill_plus and player.skill == SKILL_PARRY
                if player.is_parrying:
                    _n_ref = shash.parry_player(player.cx, player.cy, pool,
                                                pb_pool=(pb_pool if _parry_plus else None),
                                                parry_plus=_parry_plus)
                    player._parry_burst_acc += _n_ref
                else:
                    if player._parry_burst_acc > 0:
                        player._parry_burst_max = max(player._parry_burst_max,
                                                      player._parry_burst_acc)
                        player._parry_burst_acc = 0
                parry_hits = check_parried_boss_collision(pool, boss, diff, glass_cannon)
                if parry_hits:
                    player.parry_count += parry_hits
                    bx_ref = boss.cx if hasattr(boss, 'cx') else boss.x
                    by_ref = boss.cy if hasattr(boss, 'cy') else boss.y
                    pp.emit(bx_ref, by_ref, (200, 80, 255), parry_hits * 6,
                            80, 260, 0.3, 0.7, radius=5.0)
                    trigger_shake(16.0, 0.50)
                    trigger_hitstop(4)

                g_new = check_graze(shash, pool, player)
                if g_new:
                    pp.emit(player.cx, player.cy, (0, 255, 200), g_new * 4,
                            40, 130, 0.15, 0.40, radius=3.0)
                    if player.skill_cd > 0:
                        player.skill_cd = max(0.0, player.skill_cd - 0.08 * g_new)
                    # DASH+: graze enquanto está em dash conta para maestria
                    if player.skill_plus and player.skill == SKILL_DASH and player.is_dashing:
                        player._graze_dash_acc += g_new

                if player.invuln == 0 and not godmode:
                    # Zonas de perigo (HAZARD_BURN) — dano periódico independente
                    if hz_pool.tick_burn(player.cx, player.cy):
                        player.lives     -= 1
                        player.total_hits += 1
                        player.invuln     = 30  # ~0.5s de graça
                        if isinstance(boss, TwinsBoss):
                            twins_no_dmg_t = 0.0
                        pp.emit(player.cx, player.cy, (220, 80, 20), 15,
                                50, 180, 0.25, 0.6, radius=3.5)
                        trigger_shake(6.0, 0.2)

                if player.invuln == 0 and not godmode:
                    # Kamikazes do Invocador / Wave Survival
                    _kami_hit = 0
                    if enm_pool is not None and (isinstance(boss, (SummonerBoss, SlothBoss))
                                                 or game_mode == GAME_MODE_WAVE_SURVIVAL):
                        _kami_hit = enm_pool.check_player_hit(player.cx, player.cy)

                    # Yang Fantasma — dano por contato com o corpo durante o dash
                    _phantom_hit = False
                    if isinstance(boss, TwinsBoss) and getattr(boss, '_yang_dashing', False):
                        _hs = TWIN_SIZE * boss._survivor_scale
                        _phantom_hit = (boss.yang_x - _hs <= player.cx <= boss.yang_x + _hs and
                                        boss.yang_y - _hs <= player.cy <= boss.yang_y + _hs)

                    hit = (_kami_hit > 0 or _phantom_hit
                           or shash.query_player(player.cx, player.cy, pool,
                                                 player.vx, player.vy)
                           or lp.check_player(player.cx, player.cy)
                           or pool.tether_check(player.cx, player.cy))
                    if hit:
                        if player.skill_plus and player.skill == SKILL_DASH and player._dash_iframe_t > 0:
                            pass  # DASH+: i-frames ativos, sem dano
                        elif player.try_absorb_hit():
                            player.invuln = 20
                            pp.emit(player.cx, player.cy, (80, 255, 140), 12,
                                    80, 180, 0.2, 0.5, radius=3.0)
                            trigger_shake(4.0, 0.15)
                        else:
                            player.invuln     = INVULN_FRAMES
                            player.lives     -= 1
                            player.total_hits += 1
                            # TwinsBoss — reseta timer de sobrevivência sem dano
                            if isinstance(boss, TwinsBoss):
                                twins_no_dmg_t = 0.0
                            pp.emit(player.cx, player.cy, (220, 60, 40), 22,
                                    70, 230, 0.3, 0.7, radius=4.5)
                            trigger_shake(10.0, 0.35)
                            trigger_hitstop(3)
                    elif isinstance(boss, TwinsBoss) and not boss.in_prep:
                        twins_no_dmg_t += dt

                elapsed += dt
                if state == PLAYING:
                    recorder.record(keys, dt)

                if boss.hp <= 0 and not isinstance(boss, NullBoss):
                    # EXPERT — Segundo Fôlego: intercepta morte na última fase
                    if (diff.second_wind and not second_wind_done
                            and not isinstance(boss, (DummyBoss, NullBoss))
                            and not getattr(boss, 'invulnerable', False)):
                        boss.hp            = 1.0
                        boss.invulnerable  = True
                        second_wind_active = True
                        second_wind_timer  = 3.0
                        second_wind_done   = True
                        second_wind_spray_t = 0.0
                        trigger_shake(14.0, 0.5)
                        _bx_sw = boss.cx if hasattr(boss, 'cx') else boss.x
                        _by_sw = boss.cy if hasattr(boss, 'cy') else boss.y
                        for _swi in range(32):
                            _ang = _swi * (TWO_PI / 32)
                            _bidx = pool.acquire()
                            if _bidx < 0: break
                            pool.bx[_bidx] = _bx_sw;  pool.by[_bidx] = _by_sw
                            pool.bvx[_bidx] = math.cos(_ang) * 230.0
                            pool.bvy[_bidx] = math.sin(_ang) * 230.0
                    elif not isinstance(boss, DummyBoss):
                        # Morte normal (DummyBoss nunca morre, tem HP infinito)
                        pool._screen_wrap = False
                        bx_ref = boss.cx if hasattr(boss, 'cx') else boss.x
                        by_ref = boss.cy if hasattr(boss, 'cy') else boss.y
                        _is_sin = isinstance(boss, SinBoss)
                        if _is_sin:
                            trigger_hitstop(90); trigger_shake(40.0, 1.5)
                        else:
                            trigger_shake(25.0, 1.0)
                        pp.emit(bx_ref, by_ref, (255, 220, 60), 80 + (40 if _is_sin else 0),
                                100, 420, 0.5, 1.4, radius=6.0)
                        pp.emit(bx_ref, by_ref, (255, 100, 30), 50,
                                60, 280, 0.4, 1.0, radius=4.0)
                        pool.clear(); ep.clear(); lp.clear(); hz_pool.clear()
                        if enm_pool is not None: enm_pool.clear()

                        if game_mode == GAME_MODE_BOSS_RUSH:
                            if player.lives < 5: player.lives += 1   # cura entre bosses
                            boss_rush_pause_t = 3.0
                            state = BOSS_RUSH_PAUSE

                        elif game_mode == GAME_MODE_WAVE_SURVIVAL and wave_mgr is not None:
                            boss = NullBoss()
                            boss_rush_pause_t = 2.5
                            _wave_boss_pause  = True
                            state = BOSS_RUSH_PAUSE   # reutiliza a tela de pausa

                        else:  # GAME_MODE_CLASSIC
                            if state == PLAYING:
                                _twins_delta = -1.0
                                if isinstance(boss, TwinsBoss):
                                    if boss.yin_death_time >= 0 and boss.yang_death_time >= 0:
                                        _twins_delta = abs(boss.yin_death_time - boss.yang_death_time)
                                unlock_notifs = save.on_win(
                                    config.diff, elapsed, player.parry_count,
                                    graze_count=player.graze_count,
                                    mutator_count=len(config.mutators),
                                    total_hits=player.total_hits,
                                    skill=config.skill,
                                    boss_type=config.boss_type,
                                    twins_delta=_twins_delta,
                                    minion_kills=minion_kills,
                                    twins_no_dmg_t=twins_no_dmg_t,
                                )
                                unlock_notifs += save.update_mastery(player)
                                unlock_notifs += save.update_weapon_mastery(player)
                            state = WIN

                # Wave Survival — vitória por ondas
                if (game_mode == GAME_MODE_WAVE_SURVIVAL and wave_mgr is not None
                        and wave_mgr.game_won and state == PLAYING):
                    unlock_notifs = []
                    state = WIN
                elif player.lives <= 0:
                    if state == PLAYING:
                        save.on_death()
                    state = GAMEOVER

        # ---- Screen shake update (respects settings) ----------------------
        if shake_timer > 0.0 and save.settings["screen_shake"]:
            shake_timer = max(0.0, shake_timer - dt)
            decay   = shake_timer / max(shake_timer + dt, 0.001)
            cur_amt = shake_amount * decay
            shake_x = random.randint(-int(cur_amt), int(cur_amt)) if cur_amt >= 1 else 0
            shake_y = random.randint(-int(cur_amt), int(cur_amt)) if cur_amt >= 1 else 0
            if shake_timer <= 0.0: shake_amount = 0.0; shake_x = shake_y = 0
        else:
            shake_x = shake_y = 0

        if cheat_flash    > 0.0: cheat_flash    = max(0.0, cheat_flash    - dt)
        if bal_reload_flash > 0.0: bal_reload_flash = max(0.0, bal_reload_flash - dt)

        # ---- EXPERT — Segundo Fôlego: ataque de desespero 3s ----------------
        if second_wind_active and state == PLAYING:
            second_wind_timer  -= dt
            second_wind_spray_t -= dt
            if second_wind_spray_t <= 0.0:
                second_wind_spray_t = 0.45
                _bx_sw = boss.cx if hasattr(boss, 'cx') else boss.x
                _by_sw = boss.cy if hasattr(boss, 'cy') else boss.y
                _sw_n = 18
                for _swi in range(_sw_n):
                    _ang = _swi * (TWO_PI / _sw_n) + second_wind_timer * 1.5
                    _bidx = pool.acquire()
                    if _bidx < 0: break
                    _spd = 190.0 + (_swi % 3) * 20.0
                    pool.bx[_bidx] = _bx_sw;  pool.by[_bidx] = _by_sw
                    pool.bvx[_bidx] = math.cos(_ang) * _spd
                    pool.bvy[_bidx] = math.sin(_ang) * _spd
            if second_wind_timer <= 0.0:
                second_wind_active = False
                boss.invulnerable  = False
                boss.hp            = 0.0

        # ---- BOSS_RUSH_PAUSE — countdown entre bosses / ondas -----------------
        if state == BOSS_RUSH_PAUSE:
            boss_rush_pause_t = max(0.0, boss_rush_pause_t - dt)
            if boss_rush_pause_t <= 0.0:
                if game_mode == GAME_MODE_WAVE_SURVIVAL and wave_mgr is not None:
                    wave_mgr.next_wave()   # avança da onda-boss para a próxima onda
                    _wave_boss_pause = False
                    boss = NullBoss()
                    if wave_mgr.game_won:
                        unlock_notifs = []
                        state = WIN
                    else:
                        state = PLAYING
                else:  # GAME_MODE_BOSS_RUSH — usa BossRushManager
                    if boss_rush_mgr is not None:
                        boss_rush_mgr.advance()
                        boss_rush_idx = boss_rush_mgr.stage_idx
                        if boss_rush_mgr.done:
                            unlock_notifs = save.on_win(
                                config.diff, elapsed, player.parry_count,
                                graze_count=player.graze_count,
                                mutator_count=len(config.mutators),
                                total_hits=player.total_hits,
                                skill=config.skill,
                                boss_type=config.boss_type,
                                twins_delta=-1.0, minion_kills=minion_kills,
                                twins_no_dmg_t=twins_no_dmg_t,
                                sins_rush=(sel_rush_playlist == 1),
                            )
                            unlock_notifs += save.update_mastery(player)
                            state = WIN
                        else:
                            _stage_cfg = boss_rush_mgr.make_game_config_for_stage()
                            _next_id   = boss_rush_mgr.current_boss_id()
                            boss = _make_boss_of_type(_next_id, _stage_cfg, enm_pool)
                            pool.clear(); ep.clear(); lp.clear(); hz_pool.clear()
                            if enm_pool is not None: enm_pool.clear()
                            pool._screen_wrap = False
                            state = PLAYING

        # ---- RENDER -----------------------------------------------------------
        if state == MAIN_MENU:
            msg = "SAVE APAGADO" if cheat_wipe else "CHEAT ATIVADO"
            render_main_menu(screen, big, font, main_menu_sel,
                             cheat_flash, msg)
            render_dev_overlay(screen, font, dev_mode, godmode, len(cheat_buf), bal_reload_flash)
            pygame.display.flip();  continue

        if state == ACHIEVEMENTS:
            render_achievements(screen, big, font, save, achievements_cursor)
            pygame.display.flip();  continue

        if state == RECORDS:
            render_records(screen, big, font, save)
            pygame.display.flip();  continue

        if state == SETTINGS:
            render_settings(screen, big, font, save, settings_sel)
            pygame.display.flip();  continue

        if state == SELECT_GAME_MODE:
            render_menu_game_mode(screen, big, font, sel_game_mode)
            pygame.display.flip();  continue

        if state == SELECT_RUSH_PLAYLIST:
            render_menu_rush_playlist(screen, big, font, sel_rush_playlist)
            pygame.display.flip();  continue

        if state == SELECT_DIFF:
            render_menu_diff(screen, big, font, sel_diff, save)
            pygame.display.flip();  continue

        if state == SELECT_BOSS:
            render_menu_boss(screen, big, font, sel_boss, sel_diff, save)
            pygame.display.flip();  continue

        if state == SELECT_SKILL:
            render_menu_skill(screen, big, font, sel_skill, sel_diff, sel_boss, save, sel_skill_plus)
            pygame.display.flip();  continue

        if state == SELECT_WEAPON:
            render_menu_weapon(screen, big, font, sel_weapon, sel_diff, sel_boss, sel_skill,
                               save=save, sel_weapon_plus=sel_weapon_plus)
            pygame.display.flip();  continue

        if state == SELECT_MUTATOR:
            render_menu_mutator(screen, big, font, sel_mutators,
                                sel_diff, sel_boss, sel_skill, sel_weapon, sel_mut_cur, save)
            pygame.display.flip();  continue

        # ---- In-game / end-screen render (via game_surf + shake) ----------
        game_surf.fill(BG_COLOR)

        show_hitbox = save.settings["show_hitbox"]
        if show_hitbox and state in (PLAYING, REPLAYING):
            for c in range(GRID_COLS+1):
                pygame.draw.line(game_surf, (26,26,26),
                                 (c*CELL_SIZE, 0), (c*CELL_SIZE, SCREEN_H))
            for r in range(GRID_ROWS+1):
                pygame.draw.line(game_surf, (26,26,26),
                                 (0, r*CELL_SIZE), (SCREEN_W, r*CELL_SIZE))

        # Arena border (MUTATOR_CLAUSTROFOBIA)
        if config and MUTATOR_CLAUSTROFOBIA in config.mutators:
            render_arena_border(game_surf, player)

        render_boss(game_surf, boss)
        render_boss_prep(game_surf, boss)
        render_hazards(game_surf, hz_pool)
        render_lasers(game_surf, lp)
        render_emitters(game_surf, ep)
        render_bullets(game_surf, pool, bullet_surf, parried_surf, boss,
                       config.mutators if config else frozenset(),
                       bullet_surf_blue, bullet_surf_orange, bullet_surf_purple,
                       player.cx if player else 0.0, player.cy if player else 0.0)
        render_player_bullets(game_surf, pb_pool)

        # Lacaios do Invocador + Wave Survival enemies
        if enm_pool is not None and (isinstance(boss, (SummonerBoss, SlothBoss))
                                     or game_mode == GAME_MODE_WAVE_SURVIVAL):
            render_enemies(game_surf, enm_pool)

        render_particles(game_surf, pp)

        if show_hitbox and state in (PLAYING, REPLAYING):
            render_hash_debug(game_surf, player)
            if boss is not None:
                for (_ax0, _ay0, _ax1, _ay1) in boss.get_aabb_list():
                    pygame.draw.rect(game_surf, (255, 80, 80),
                                     (int(_ax0), int(_ay0), int(_ax1-_ax0), int(_ay1-_ay0)), 1)

        render_player_trail(game_surf, player)
        render_player(game_surf, player)
        render_boss_hpbar(game_surf, font, boss, diff)
        render_lives(game_surf, player.lives)
        render_dev_hud(game_surf, font, clock.get_fps(), pool.active_count, show_hitbox)
        render_skill_hud(game_surf, font, player)

        # Wave Survival HUD — contador de onda
        if game_mode == GAME_MODE_WAVE_SURVIVAL and wave_mgr is not None:
            _wn = wave_mgr.wave_n + 1
            _wtxt = f"ONDA {_wn}/{WaveManager.WAVE_WIN}"
            if wave_mgr.boss_wave:
                _wtxt += "  [BOSS]"
            _wlbl = font.render(_wtxt, True, (80, 220, 100))
            game_surf.blit(_wlbl, (8, 36))

        # Boss Rush HUD — contador de boss (usa BossRushManager se disponível)
        if game_mode == GAME_MODE_BOSS_RUSH and state in (PLAYING, BOSS_RUSH_PAUSE):
            if boss_rush_mgr is not None:
                _brtxt = f"{boss_rush_mgr.label}  {boss_rush_mgr.stage_idx + 1}/{boss_rush_mgr.stage_count()}"
            else:
                _brtxt = f"BOSS RUSH  {boss_rush_idx + 1}/?"
            game_surf.blit(font.render(_brtxt, True, (255, 160, 40)), (8, 36))

        # SinBoss P3 — timer de sobrevivência
        if (state == PLAYING and isinstance(boss, SinBoss)
                and boss._phase == 3 and boss.invulnerable):
            _st = max(0, int(boss.survive_timer) + 1)
            _alarm = boss.survive_timer <= 5.0
            _sc = (255, 80, 30) if _alarm else (200, 100, 255)
            _stxt = f"SOBREVIVA!  {_st:02d}s"
            _slbl = big.render(_stxt, True, _sc)
            game_surf.blit(_slbl, (SCREEN_W // 2 - _slbl.get_width() // 2, SCREEN_H // 2 - 60))

        # EXPERT — Segundo Fôlego: countdown central
        if state == PLAYING and second_wind_active:
            _sw_secs = max(0, int(second_wind_timer) + 1)
            _sw_pulse = 0.5 + 0.5 * abs(math.sin(second_wind_timer * math.pi))
            _sw_r = int(255 * _sw_pulse); _sw_g = int(60 * _sw_pulse)
            _sw_lbl = big.render(f"SEGUNDO FÔLEGO  {_sw_secs}s", True, (_sw_r, _sw_g, 255))
            _sw_x = SCREEN_W // 2 - _sw_lbl.get_width() // 2
            game_surf.blit(_sw_lbl, (_sw_x, SCREEN_H // 2 - 80))

        # DummyBoss — números de dano flutuantes
        if isinstance(boss, DummyBoss):
            _fn_alive = [i for i in range(16) if boss._fn_active[i]]
            for _fni in _fn_alive:
                _fn_alpha = min(1.0, boss._fn_t[_fni] / 0.6)
                _fn_col = (255, int(220 * _fn_alpha), int(60 * _fn_alpha))
                _fn_lbl = font.render(f"{int(boss._fn_val[_fni])}", True, _fn_col)
                game_surf.blit(_fn_lbl, (int(boss._fn_x[_fni]) - _fn_lbl.get_width() // 2,
                                         int(boss._fn_y[_fni])))

        if state == PLAYING and intro_timer > 0:
            _bt = config.boss_type if config is not None else -1
            render_intro(game_surf, big, font, intro_timer, _bt)

        if state == REPLAYING:
            lbl = font.render("REPLAY", True, (255, 60, 60))
            game_surf.blit(lbl, (SCREEN_W - lbl.get_width() - 14, 14))

        screen.fill((0, 0, 0))
        screen.blit(game_surf, (shake_x, shake_y))

        if state == WIN:
            render_end_screen(screen, big, font, "BOSS DERROTADO!", GREEN,
                              elapsed, player.total_hits, player.graze_count,
                              has_replay=bool(recorder and recorder.frames),
                              unlocks=unlock_notifs,
                              multiplier=config.multiplier if config else 1.0)
        elif state == GAMEOVER:
            render_end_screen(screen, big, font, "GAME OVER", RED_COL,
                              elapsed, player.total_hits, player.graze_count,
                              has_replay=bool(recorder and recorder.frames))
        elif state == BOSS_RUSH_PAUSE:
            _total = boss_rush_mgr.stage_count() if boss_rush_mgr else 8
            _label = boss_rush_mgr.label if boss_rush_mgr else "BOSS RUSH"
            _render_boss_rush_pause(screen, big, font,
                                    boss_rush_idx, _total,
                                    boss_rush_pause_t,
                                    wave_mode=(game_mode == GAME_MODE_WAVE_SURVIVAL),
                                    rush_label=_label)

        render_dev_overlay(screen, font, dev_mode, godmode, len(cheat_buf), bal_reload_flash)
        pygame.display.flip()


if __name__ == "__main__":
    main()
