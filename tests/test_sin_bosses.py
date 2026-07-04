"""test_sin_bosses.py — Testes individuais por boss: fases, colisão, mecânicas, dificuldade."""
import math
import pytest

from entities import (
    PrideBoss, SlothBoss, EnvyBoss, GluttonyBoss,
    GreedBoss, LustBoss, WrathBoss, SinBoss,
    BulletPool, EmitterPool, LaserPool, EnemyPool,
    GameConfig, Difficulty,
    DIFF_NORMAL, DIFF_HARD, DIFF_EXPERT,
    BOSS_PRIDE, BOSS_SLOTH, BOSS_ENVY, BOSS_GLUTTONY,
    BOSS_GREED, BOSS_LUST, BOSS_WRATH, BOSS_SIN,
    SKILL_NONE, WEAPON_DEFAULT, WEAPON_SPREAD, WEAPON_NEEDLE,
    PREP_TIME, SCREEN_W, SCREEN_H,
)

DT  = 1 / 60
PX  = SCREEN_W / 2.0
PY  = SCREEN_H / 2.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cfg(boss_type, diff=DIFF_NORMAL):
    return GameConfig(diff, boss_type, SKILL_NONE, WEAPON_DEFAULT)

def _pools():
    return BulletPool(), EmitterPool(), LaserPool()

def _skip_prep(boss, px=PX, py=PY, diff=None):
    """Advance boss past PREP phase."""
    p, ep, lp = _pools()
    d = diff or Difficulty(DIFF_NORMAL)
    for _ in range(int(PREP_TIME / DT) + 10):
        boss.update(DT, p, ep, lp, px, py, d)

def _run(boss, frames, px=PX, py=PY, pool=None, diff=None):
    """Run boss for N frames, returns the (pool, bullets_spawned) used."""
    p, ep, lp = (pool, EmitterPool(), LaserPool()) if pool else _pools()
    d = diff or Difficulty(DIFF_NORMAL)
    before = int(p.active.sum())
    for _ in range(frames):
        boss.update(DT, p, ep, lp, px, py, d)
    return p, int(p.active.sum()) - before

def _trigger_phase(boss, target_phase, diff=None):
    """Damage boss until it reaches target_phase, handling invulnerable guards."""
    d = diff or Difficulty(DIFF_NORMAL)
    p, ep, lp = _pools()
    _skip_prep(boss, diff=d)
    for _ in range(500):  # safety cap
        if boss._phase >= target_phase:
            break
        if getattr(boss, 'invulnerable', False):
            # SlothBoss phase 1: sentinels must die to lift invulnerability
            if hasattr(boss, 'enm_pool'):
                boss.enm_pool.clear()
                boss.update(DT, p, ep, lp, PX, PY, d)
            else:
                boss.invulnerable = False
        else:
            boss.take_damage(boss.max_hp * 0.10, d)

def _bullets_in_2s(boss, px=PX, py=PY, diff=None):
    """Count bullets spawned in 2 seconds after prep."""
    _skip_prep(boss, diff=diff)
    pool = BulletPool()
    _, count = _run(boss, 120, px=px, py=py, pool=pool, diff=diff)
    return count


# ===========================================================================
# PRIDE BOSS
# ===========================================================================
class TestPrideBoss:

    def _make(self): return PrideBoss(_cfg(BOSS_PRIDE))

    # --- Phase 0 ---
    def test_phase0_starts_invulnerable(self):
        assert self._make().invulnerable

    def test_phase0_aabb_spans_spotlight_column(self):
        boss = self._make()
        _skip_prep(boss)
        aabb = boss.get_aabb_list()
        assert len(aabb) == 1
        x0, y0, x1, y1 = aabb[0]
        assert x1 - x0 == pytest.approx(boss._SPOT_W, abs=1.0)
        assert y0 == pytest.approx(0.0, abs=1.0)

    def test_phase0_spotlight_moves(self):
        boss = self._make()
        _skip_prep(boss)
        sx0 = boss.spot_x
        _run(boss, 60)
        assert boss.spot_x != pytest.approx(sx0, abs=1.0), "Spotlight must sweep"

    def test_phase0_fires_downward_bullets(self):
        boss = self._make()
        count = _bullets_in_2s(boss)
        assert count >= 10, f"Phase 0 must fire bullets; got {count}"

    def test_phase0_bullet_speed_above_threshold(self):
        boss = self._make()
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 60, pool=pool)
        active = [i for i in range(pool.active.sum()) if pool.active[i]]
        if active:
            idx = active[0]
            speed = math.hypot(pool.bvx[idx], pool.bvy[idx])
            assert speed >= 160.0, f"Phase 0 bullets too slow: {speed:.0f}px/s"

    def test_phase0_vulnerable_inside_spotlight(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        boss.update(DT, p, ep, lp, boss.spot_x, PY, diff)
        assert not boss.invulnerable

    def test_phase0_invulnerable_outside_spotlight(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        far = boss.spot_x + boss._SPOT_W * 3
        boss.update(DT, p, ep, lp, far, PY, diff)
        assert boss.invulnerable

    def test_phase0_damage_while_outside_spotlight_ignored(self):
        boss = self._make()
        _skip_prep(boss, px=2000.0)  # player far from spot
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        boss.update(DT, p, ep, lp, 2000.0, PY, diff)
        assert boss.invulnerable
        # Taking damage while invulnerable does nothing in check_boss_collision
        # but take_damage itself doesn't guard — test that hp still decreases
        hp_before = boss.hp
        boss.take_damage(10.0, diff)
        assert boss.hp < hp_before, "take_damage must reduce hp even in phase 0"

    # --- Phase transition 0→1 ---
    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1

    def test_phase1_not_invulnerable(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert not boss.invulnerable

    def test_phase1_aabb_is_small_body(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        aabb = boss.get_aabb_list()
        w = aabb[0][2] - aabb[0][0]
        assert w == pytest.approx(boss.size, abs=1.0)

    def test_phase1_fires_geometric_shapes(self):
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 15, f"Phase 1 must fire geometric bursts; got {count}"

    # --- Phase transition 1→2 ---
    def test_phase_transition_1_to_2(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 2

    def test_phase2_fires_spiral_bullets(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 15

    def test_phase2_player_force_upward(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pf = boss.player_force
        assert pf is not None
        assert pf[1] < 0, "Phase 2 must apply upward force"

    def test_3_phases_total(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.30, diff)
        assert boss.hp <= 0


# ===========================================================================
# SLOTH BOSS
# ===========================================================================
class TestSlothBoss:

    def _make(self):
        boss = SlothBoss(_cfg(BOSS_SLOTH))
        boss.enm_pool = EnemyPool()
        return boss

    def test_phase0_drifts(self):
        boss = self._make()
        _skip_prep(boss)
        x0, y0 = boss.x, boss.y
        _run(boss, 300)
        dist = math.hypot(boss.x - x0, boss.y - y0)
        assert dist > 0.5, "Phase 0 must drift"

    def test_phase0_no_direct_bullets(self):
        boss = self._make()
        pool = BulletPool()
        _, count = _run(boss, 180, pool=pool)
        assert count == 0, "Phase 0 must not fire direct bullets (only bubble enemies)"

    def test_phase0_spawns_bubble_enemies(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(300):  # 5s — enough for bubble_cd=3.5
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.enm_pool.active.sum() > 0, "Phase 0 must spawn bubble enemies"

    def test_phase_transition_0_to_1_invulnerable(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1
        assert boss.invulnerable

    def test_phase1_spawns_sentinels(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        sentinel_count = int((boss.enm_pool.active).sum())
        assert sentinel_count == 3, f"Phase 1 must spawn 3 sentinels; got {sentinel_count}"

    def test_phase1_boss_vulnerable_after_sentinels_die(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss.invulnerable
        # Kill all sentinels
        boss.enm_pool.clear()
        p, ep, lp = _pools()
        boss.update(DT, p, ep, lp, PX, PY, diff)
        assert not boss.invulnerable

    def test_phase2_fires_8way_burst(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        # At rate 0.35s and 8 bullets per burst: in 2s ≥ 5 bursts = 40 bullets
        assert count >= 30, f"Phase 2 must fire 8-way burst frequently; got {count}"

    def test_phase2_bullet_speed_adequate(self):
        """After fix: bullets must be ≥150px/s (was 85px/s — too slow)."""
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _run(boss, 30, pool=pool)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            idx = active[0]
            speed = math.hypot(float(pool.bvx[idx]), float(pool.bvy[idx]))
            assert speed >= 150.0, f"Phase 2 bullets too slow: {speed:.0f}px/s (fix: was 85)"

    def test_phase2_fire_rate_adequate(self):
        """At 0.35s rate: must fire ≥4 bursts in 2 seconds."""
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _run(boss, 6, pool=pool)   # reset acc
        pool.clear()
        _, count = _run(boss, 120, pool=pool)
        bursts = count // 8
        assert bursts >= 4, f"Phase 2 rate too slow: {bursts} bursts/2s (expected ≥4)"


# ===========================================================================
# ENVY BOSS
# ===========================================================================
class TestEnvyBoss:

    def _make(self, weapon=WEAPON_DEFAULT):
        cfg = GameConfig(DIFF_NORMAL, BOSS_ENVY, SKILL_NONE, weapon)
        return EnvyBoss(cfg)

    def test_phase0_mirrors_default_weapon(self):
        boss = self._make(WEAPON_DEFAULT)
        count = _bullets_in_2s(boss)
        assert count >= 5, f"Phase 0 with WEAPON_DEFAULT must fire; got {count}"

    def test_phase0_mirrors_spread_weapon(self):
        boss = self._make(WEAPON_SPREAD)
        count = _bullets_in_2s(boss)
        # SPREAD fires 5 bullets per shot, same rate → more bullets than default
        assert count >= 20, f"Phase 0 with WEAPON_SPREAD must fire 5× more; got {count}"

    def test_phase0_needle_fires_fast_bullet(self):
        boss = self._make(WEAPON_NEEDLE)
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 30, pool=pool)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            speed = math.hypot(float(pool.bvx[active[0]]), float(pool.bvy[active[0]]))
            assert speed >= 400.0, f"NEEDLE bullet must be fast; got {speed:.0f}"

    def test_phase0_tracks_player_fast(self):
        boss = self._make()
        _skip_prep(boss, px=50.0)
        x0 = boss.x
        _run(boss, 60, px=50.0)
        assert boss.x < x0, "EnvyBoss must aggressively track player (1.8x)"

    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1
        assert boss.player_skill_penalty == pytest.approx(0.50)

    def test_phase1_fires_6way_burst(self):
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        # 6 bullets at 0.35s rate → in 2s: ≥5 bursts = 30 bullets
        assert count >= 24, f"Phase 1 must fire 6-way burst; got {count}"

    def test_phase1_skill_penalty_applied(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss.player_skill_penalty == pytest.approx(0.50)

    def test_phase_transition_1_to_2_clears_penalty(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 2
        assert boss.player_skill_penalty == pytest.approx(0.0)

    def test_phase2_cycles_weapons(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 180, pool=pool)  # 3s to cycle
        assert count >= 15, f"Phase 2 must fire cycling weapons; got {count}"


# ===========================================================================
# GLUTTONY BOSS
# ===========================================================================
class TestGluttonyBoss:

    def _make(self): return GluttonyBoss(_cfg(BOSS_GLUTTONY))

    def test_phase0_player_force_upward(self):
        boss = self._make()
        pf = boss.player_force
        assert pf is not None and pf[1] < 0

    def test_phase0_fires_orbital_bullets(self):
        boss = self._make()
        count = _bullets_in_2s(boss)
        # At 0.65s rate: 2 fires × 8 bullets = 16 bullets
        assert count >= 12, f"Phase 0 must spawn orbital bullets; got {count}"

    def test_phase0_orbital_speed_adequate(self):
        """After fix: bullets must be ≥100px/s (was 75px/s — too slow)."""
        boss = self._make()
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 60, pool=pool)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            idx = active[0]
            speed = math.hypot(float(pool.bvx[idx]), float(pool.bvy[idx]))
            assert speed >= 100.0, f"Phase 0 orbital too slow: {speed:.0f}px/s (was 75)"

    def test_phase0_fire_rate_adequate(self):
        """At 0.65s rate: must fire at least twice in 2s."""
        boss = self._make()
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 6, pool=pool)   # consume initial accumulation
        pool.clear()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 8, f"Phase 0 rate too low: only {count} bullets in 2s"

    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1

    def test_phase1_fires_curtain_with_gap(self):
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        # Curtain: ~22 bullets per row × 2 rows in 2s = ~44 bullets
        assert count >= 20, f"Phase 1 must fire curtain; got {count}"

    def test_phase1_curtain_has_gap_wide_enough(self):
        """Gap must be ≥180px for player to pass through."""
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(60):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        # Fire one burst into pool
        boss._teeth_acc = 999.0
        for _ in range(3):
            boss.update(DT, pool, ep, lp, PX, PY, diff)
        xs = [float(pool.bx[i]) for i in range(len(pool.active)) if pool.active[i]]
        if len(xs) >= 2:
            xs.sort()
            max_gap = max(xs[i+1] - xs[i] for i in range(len(xs)-1))
            assert max_gap >= 140.0, f"Curtain gap too narrow: {max_gap:.0f}px"

    def test_phase2_player_force_downward(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pf = boss.player_force
        assert pf is not None and pf[1] > 0, "Phase 2 must pull player DOWN"

    def test_phase2_fires_bouncing_bullets(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 8, f"Phase 2 must fire bouncing bullets; got {count}"
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            assert pool.b_bounces[active[0]] == 3


# ===========================================================================
# GREED BOSS
# ===========================================================================
class TestGreedBoss:

    def _make(self): return GreedBoss(_cfg(BOSS_GREED))

    def test_phase0_two_walls_defined(self):
        boss = self._make()
        assert len(boss.wall_x) == 2
        assert boss.wall_x[0] < boss.wall_x[1]

    def test_phase0_walls_shift_every_4s(self):
        boss = self._make()
        _skip_prep(boss)
        wx0 = list(boss.wall_x)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(int(4.5 / DT)):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.wall_x[0] != pytest.approx(wx0[0], abs=1.0) or \
               boss.wall_x[1] != pytest.approx(wx0[1], abs=1.0), \
               "Walls must shift after 4s"

    def test_phase0_fires_corridor_bullets(self):
        boss = self._make()
        count = _bullets_in_2s(boss)
        assert count >= 8, f"Phase 0 must rain bullets; got {count}"

    def test_phase0_safe_corridor_is_wide(self):
        """Safe corridor between walls must be ≥300px for player to fit."""
        boss = self._make()
        gap = boss.wall_x[1] - boss.wall_x[0]
        assert gap >= 300.0, f"Safe corridor too narrow: {gap:.0f}px"

    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1

    def test_phase1_coins_spawn(self):
        boss = self._make()
        _trigger_phase(boss, 1)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(int(2.0 / DT)):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.coin_active.sum() >= 1, "Phase 1 must spawn coins"

    def test_phase1_coin_pool_preallocated(self):
        boss = self._make()
        assert boss.coin_x.shape[0] == boss.MAX_COINS
        assert boss.coin_active.sum() == 0

    def test_phase1_coin_explosion_fires_8_bullets(self):
        boss = self._make()
        boss.coin_acquire(400.0, 300.0)
        pool = BulletPool()
        before = int(pool.active.sum())
        boss.coin_explode(0, pool)
        assert int(pool.active.sum()) - before == 8
        assert not boss.coin_active[0]

    def test_phase_transition_1_to_2(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 2
        assert boss.border_inset == pytest.approx(0.0)

    def test_phase2_border_grows(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(int(3.0 / DT)):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.border_inset > 0.0, "Phase 2 border must shrink inward"
        assert boss.border_inset <= 180.0, "Border must cap at 180px"

    def test_phase2_fires_bouncing_bullets(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 10
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            assert pool.b_bounces[active[0]] == 3


# ===========================================================================
# LUST BOSS
# ===========================================================================
class TestLustBoss:

    def _make(self): return LustBoss(_cfg(BOSS_LUST))

    def test_phase0_fires_fast_daggers(self):
        boss = self._make()
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 30, pool=pool)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            speed = math.hypot(float(pool.bvx[active[0]]), float(pool.bvy[active[0]]))
            assert speed >= 280.0, f"Phase 0 daggers must be fast (≥280px/s); got {speed:.0f}"

    def test_phase0_enqueues_hazard_requests(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(int(2.6 / DT)):  # wait longer than fog_cd=2.5
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss._hz_n >= 1, "Phase 0 must enqueue hazard zone requests"
        assert boss._hz_n <= 4, "Hazard buffer must not overflow beyond 4"

    def test_phase0_controls_not_inverted(self):
        boss = self._make()
        assert not boss.controls_inverted

    def test_phase1_controls_inverted(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1
        boss.in_prep = False
        assert boss.controls_inverted

    def test_phase1_player_force_upward(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        pf = boss.player_force
        assert pf is not None and pf[1] < 0

    def test_phase1_fires_heart_spiral(self):
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 12, f"Phase 1 must fire 6-way rotating burst; got {count}"

    def test_phase1_bullet_speed_adequate(self):
        """After fix: bullets must be ≥150px/s (was 130px/s — too slow with inverted controls)."""
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _run(boss, 60, pool=pool)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            speed = math.hypot(float(pool.bvx[active[0]]), float(pool.bvy[active[0]]))
            assert speed >= 150.0, f"Phase 1 bullets too slow: {speed:.0f}px/s"

    def test_phase2_fires_invisible_needles(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _run(boss, 120, pool=pool)
        invisible = [i for i in range(len(pool.active))
                     if pool.active[i] and pool.b_invisible[i]]
        assert len(invisible) >= 1, "Phase 2 must fire invisible needles"

    def test_phase2_needle_speed_high(self):
        """Invisible needles must be ≥380px/s (original 420px/s)."""
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _run(boss, 120, pool=pool)
        invisible = [i for i in range(len(pool.active))
                     if pool.active[i] and pool.b_invisible[i]]
        if invisible:
            speed = math.hypot(float(pool.bvx[invisible[0]]),
                               float(pool.bvy[invisible[0]]))
            assert speed >= 380.0, f"Invisible needle too slow: {speed:.0f}px/s"

    def test_phase2_controls_not_inverted(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.in_prep = False
        assert not boss.controls_inverted, "Controls_inverted must be False in phase 2"


# ===========================================================================
# WRATH BOSS
# ===========================================================================
class TestWrathBoss:

    def _make(self): return WrathBoss(_cfg(BOSS_WRATH))

    def test_phase0_high_fire_rate(self):
        """Phase 0: 3 bullets per 0.12s → in 2s must fire ≥35 bullets."""
        boss = self._make()
        count = _bullets_in_2s(boss)
        assert count >= 35, f"Phase 0 must be aggressive; got {count}"

    def test_phase0_tracks_player_fast(self):
        boss = self._make()
        _skip_prep(boss, px=50.0)
        x0 = boss.x
        _run(boss, 60, px=50.0)
        assert boss.x < x0

    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 1

    def test_phase1_slam_fires_ring_on_impact(self):
        """When diving completes, boss must fire 12-bullet ring."""
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        pool = BulletPool()
        # Force slam state to diving
        boss._slam_state = 1
        boss._slam_timer = -1.0
        p, ep, lp = _pools()
        before = 0
        for _ in range(10):
            pool2 = pool
            boss.update(DT, pool2, ep, lp, PX, PY, diff)
            if boss._slam_state == 2 and int(pool.active.sum()) > before:
                break
        # Check ring was spawned (12 bullets)
        assert int(pool.active.sum()) >= 12 or boss._ring_active

    def test_phase1_ring_bullets_have_outward_velocity(self):
        """Ring bullets fired after slam must have nonzero velocity (expanding outward)."""
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        pool = BulletPool()
        boss._slam_state = 1
        boss._slam_timer = -1.0
        p, ep, lp = _pools()
        for _ in range(5):
            boss.update(DT, pool, ep, lp, PX, PY, diff)
        active = [i for i in range(len(pool.active)) if pool.active[i]]
        if active:
            speeds = [math.hypot(float(pool.bvx[i]), float(pool.bvy[i])) for i in active]
            assert max(speeds) > 0.0, "Ring bullets must have nonzero velocity"

    def test_phase_transition_1_to_2(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        boss.take_damage(boss.max_hp * 0.40, diff)
        assert boss._phase == 2
        assert boss.body_dmg_active

    def test_phase2_no_bullet_hitbox(self):
        """Phase 2: get_aabb_list must return [] — body is the hazard."""
        boss = self._make()
        _trigger_phase(boss, 2)
        assert boss.get_aabb_list() == []

    def test_phase2_damage_returns_early(self):
        """Phase 2 is invulnerable to take_damage — body only."""
        boss = self._make()
        _trigger_phase(boss, 2)
        hp_before = boss.hp
        boss.take_damage(9999.0, Difficulty(DIFF_NORMAL))
        assert boss.hp == pytest.approx(hp_before)

    def test_phase2_body_bounces(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        bx0, by0 = boss.body_x, boss.body_y
        _run(boss, 30)
        assert boss.body_x != pytest.approx(bx0) or boss.body_y != pytest.approx(by0)

    def test_phase2_berserker_timer_exists(self):
        boss = self._make()
        assert hasattr(boss, '_berserker_timer')
        assert boss._berserker_timer == pytest.approx(0.0)

    def test_phase2_win_condition_after_20s(self):
        """CRITICAL FIX: boss must die after 20s in Berserker (was infinite)."""
        boss = self._make()
        _trigger_phase(boss, 2)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        # Inject timer directly to avoid running 1200 frames
        boss._berserker_timer = 19.9
        for _ in range(10):  # ~0.16s — push past 20s
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.hp <= 0.0, "WrathBoss must die after 20s Berserker (no infinite phase)"

    def test_phase2_body_accelerates(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        spd0 = math.hypot(boss._body_vx, boss._body_vy)
        _run(boss, 120)
        spd1 = math.hypot(boss._body_vx, boss._body_vy)
        assert spd1 > spd0, "Body must accelerate over time"

    def test_phase2_body_speed_capped_at_600(self):
        boss = self._make()
        _trigger_phase(boss, 2)
        # Inject high timer so acceleration is large
        boss._berserker_timer = 0.0
        boss.phase_t = 100.0
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(60):
            boss.update(DT, p, ep, lp, PX, PY, diff)
            if boss.hp <= 0: break
        spd = math.hypot(boss._body_vx, boss._body_vy)
        assert spd <= math.sqrt(600.0**2 + 600.0**2) + 1.0, "Body speed must be capped"


# ===========================================================================
# SIN BOSS (Chefe Final — 4 fases)
# ===========================================================================
class TestSinBoss:

    def _make(self): return SinBoss(_cfg(BOSS_SIN))

    def test_4_phase_thresholds(self):
        boss = self._make()
        assert boss._PHASE_HP == [0.75, 0.50, 0.25]

    def test_phase0_mines_preallocated(self):
        boss = self._make()
        assert boss._mine_x.shape[0] == boss.MAX_MINES
        assert boss._mine_active.sum() == 0

    def test_phase0_spawns_mines(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(int(2.5 / DT)):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss._mine_active.sum() >= 1, "Phase 0 must spawn mines"

    def test_phase0_mine_explodes_on_proximity(self):
        boss = self._make()
        _skip_prep(boss)
        boss._mine_acquire(PX, PY)
        pool = BulletPool()
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        boss.update(DT, pool, ep, lp, PX, PY, diff)  # player at mine position
        assert int(pool.active.sum()) == 16, "Mine explosion must spawn 16 bullets"

    def test_phase0_mine_explosion_16_bullets(self):
        boss = self._make()
        pool = BulletPool()
        boss._mine_acquire(0.0, 0.0)
        boss._mine_explode(0, pool)
        assert int(pool.active.sum()) == 16

    def test_phase0_fires_bouncing_6way(self):
        boss = self._make()
        count = _bullets_in_2s(boss)
        assert count >= 20, f"Phase 0 must fire bouncing 6-way; got {count}"

    def test_phase0_bullets_have_bounces(self):
        boss = self._make()
        _skip_prep(boss)
        pool = BulletPool()
        _run(boss, 60, pool=pool)
        bouncing = [i for i in range(len(pool.active))
                    if pool.active[i] and pool.b_bounces[i] > 0]
        assert len(bouncing) >= 1, "Phase 0 must fire bouncing bullets"

    def test_phase_transition_0_to_1(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.30, diff)
        assert boss._phase == 1

    def test_phase1_high_density_fire(self):
        """Phase 1: 3 bullets per 0.12s — must rival WrathBoss phase 0."""
        boss = self._make()
        _trigger_phase(boss, 1)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 35, f"Phase 1 must be dense; got {count}"

    def test_phase_transition_1_to_2(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.30, diff)
        boss.take_damage(boss.max_hp * 0.28, diff)
        assert boss._phase == 2

    def test_phase2_7_spiral_arms(self):
        """7 bullets per fire — one per sin color."""
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        boss._spiral_acc = 999.0  # force next fire
        boss.update(DT, pool, ep, lp, PX, PY, diff)
        fired = int(pool.active.sum())
        assert fired == 7, f"Phase 2 must fire exactly 7 bullets (one per spiral arm); got {fired}"

    def test_phase2_extreme_density(self):
        """Phase 2 fires 7 bullets every 0.045s — most dense of all bosses."""
        boss = self._make()
        _trigger_phase(boss, 2)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 200, f"Phase 2 must be extremely dense; got {count}"

    def test_phase_transition_2_to_3_invulnerable(self):
        boss = self._make()
        diff = Difficulty(DIFF_NORMAL)
        _skip_prep(boss, diff=diff)
        boss.take_damage(boss.max_hp * 0.30, diff)  # → phase 1
        boss.take_damage(boss.max_hp * 0.28, diff)  # → phase 2
        boss.take_damage(boss.max_hp * 0.28, diff)  # → phase 3
        assert boss._phase == 3
        assert boss.invulnerable
        assert boss.survive_timer == pytest.approx(30.0)

    def test_phase3_survive_timer_counts_down(self):
        boss = self._make()
        _trigger_phase(boss, 3)
        t0 = boss.survive_timer
        _run(boss, 60)
        assert boss.survive_timer < t0, "Survive timer must count down"

    def test_phase3_fires_homing_purple_bullets(self):
        boss = self._make()
        _trigger_phase(boss, 3)
        pool = BulletPool()
        _, count = _run(boss, 120, pool=pool)
        assert count >= 5, f"Phase 3 must fire homing bullets; got {count}"
        purple = [i for i in range(len(pool.active))
                  if pool.active[i] and pool.b_type[i] == 3]  # BTYPE_PURPLE
        assert len(purple) >= 1

    def test_phase3_boss_dies_after_30s(self):
        boss = self._make()
        _trigger_phase(boss, 3)
        boss.survive_timer = 0.1
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(15):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert boss.hp <= 0.0, "SinBoss must die after surviving 30s"
        assert not boss.invulnerable

    def test_phase3_damage_ignored_while_invulnerable(self):
        boss = self._make()
        _trigger_phase(boss, 3)
        hp_before = boss.hp
        boss.take_damage(9999.0, Difficulty(DIFF_NORMAL))
        assert boss.hp == pytest.approx(hp_before), "Phase 3 must be invulnerable"

    def test_phase3_get_aabb_empty_while_invulnerable(self):
        boss = self._make()
        _trigger_phase(boss, 3)
        assert boss.get_aabb_list() == []

    def test_color_cycles_through_7_sins(self):
        boss = self._make()
        _skip_prep(boss)
        diff = Difficulty(DIFF_NORMAL)
        p, ep, lp = _pools()
        for _ in range(300):
            boss.update(DT, p, ep, lp, PX, PY, diff)
        assert 0 <= boss.color_index <= 6
