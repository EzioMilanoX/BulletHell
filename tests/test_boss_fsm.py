"""test_boss_fsm.py — Boss FSM state machine, movement, and DummyBoss tests."""
import pytest

from entities import (
    Boss, DummyBoss, PrideBoss, LustBoss, WrathBoss, SlothBoss,
    GreedBoss, EnvyBoss, GluttonyBoss,
    BulletPool, EmitterPool, LaserPool,
    GameConfig, Difficulty,
    DIFF_NORMAL, DIFF_EXPERT,
    BOSS_CLASSIC, BOSS_DUMMY, BOSS_PRIDE, BOSS_LUST,
    BOSS_WRATH, BOSS_SLOTH, BOSS_GREED, BOSS_ENVY, BOSS_GLUTTONY,
    SKILL_NONE, WEAPON_DEFAULT,
    PREP_TIME,
)

DT = 1 / 60
PX, PY = 640.0, 400.0  # default player position (center-ish)


def _pools():
    return BulletPool(), EmitterPool(), LaserPool()


def _run_frames(boss, n, px=PX, py=PY, diff=None):
    pool, ep, lp = _pools()
    if diff is None:
        diff = Difficulty(DIFF_NORMAL)
    for _ in range(n):
        boss.update(DT, pool, ep, lp, px, py, diff)


def _skip_prep(boss, diff=None, px=PX, py=PY):
    """Advance boss past PREP_TIME plus a small buffer."""
    frames = int(PREP_TIME / DT) + 10
    _run_frames(boss, frames, px=px, py=py, diff=diff)


# ===========================================================================
# Classic Boss FSM
# ===========================================================================
class TestClassicBossFSM:

    def test_starts_in_prep(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        assert boss.in_prep

    def test_exits_prep_after_prep_time(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        _skip_prep(boss)
        assert not boss.in_prep

    def test_moves_during_prep(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        x0, y0 = boss.x, boss.y
        # Run only half of PREP so we're still inside the window
        _run_frames(boss, int(PREP_TIME * 0.4 / DT))
        assert boss.in_prep
        dist = ((boss.x - x0)**2 + (boss.y - y0)**2) ** 0.5
        assert dist > 1.0, "Classic Boss must move during PREP"

    def test_expert_prep_ends_faster(self):
        diff_expert = Difficulty(DIFF_EXPERT)
        assert diff_expert.prep_scale == pytest.approx(0.5)
        # EXPERT prep = PREP_TIME * 0.5 — advance just beyond that
        cfg = GameConfig(DIFF_EXPERT, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        half_prep_frames = int(PREP_TIME * 0.5 / DT) + 5
        _run_frames(boss, half_prep_frames, diff=diff_expert)
        assert not boss.in_prep

    def test_re_enters_prep_after_attack(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        _skip_prep(boss)
        assert not boss.in_prep
        # Detect the FIRST moment prep becomes True again (SPREAD duration = 3.5s = ~210 frames)
        pool, ep, lp = _pools()
        diff = Difficulty(DIFF_NORMAL)
        saw_prep = False
        for _ in range(400):
            boss.update(DT, pool, ep, lp, PX, PY, diff)
            if boss.in_prep:
                saw_prep = True
                break
        assert saw_prep, "Boss must cycle back to PREP after attack"


# ===========================================================================
# DummyBoss
# ===========================================================================
class TestDummyBoss:

    def test_hp_never_decreases(self):
        dummy = DummyBoss()
        initial_hp = dummy.hp
        diff = Difficulty(DIFF_NORMAL)
        dummy.take_damage(9999.0, diff)
        assert dummy.hp == pytest.approx(initial_hp)

    def test_total_damage_accumulates(self):
        dummy = DummyBoss()
        diff = Difficulty(DIFF_NORMAL)
        dummy.take_damage(100.0, diff)
        dummy.take_damage(50.0, diff)
        assert dummy.total_damage == pytest.approx(150.0)

    def test_flash_frames_set_on_hit(self):
        dummy = DummyBoss()
        diff = Difficulty(DIFF_NORMAL)
        dummy.take_damage(1.0, diff)
        assert dummy.flash_frames > 0

    def test_floating_numbers_preallocated(self):
        dummy = DummyBoss()
        assert dummy._fn_val.shape[0] == 16
        assert dummy._fn_active.sum() == 0

    def test_floating_number_shown_on_hit(self):
        dummy = DummyBoss()
        diff = Difficulty(DIFF_NORMAL)
        dummy.take_damage(50.0, diff)
        assert dummy._fn_active.sum() == 1

    def test_zero_damage_does_not_accumulate(self):
        dummy = DummyBoss()
        diff = Difficulty(DIFF_NORMAL)
        dummy.take_damage(0.0, diff)
        assert dummy.total_damage == pytest.approx(0.0)


# ===========================================================================
# PrideBoss spotlight vulnerability
# ===========================================================================
class TestPrideBossSpotlight:

    def _make(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_PRIDE, SKILL_NONE, WEAPON_DEFAULT)
        return PrideBoss(cfg)

    def test_starts_invulnerable(self):
        boss = self._make()
        assert boss.invulnerable

    def test_vulnerable_when_player_inside_spotlight(self):
        boss = self._make()
        _skip_prep(boss, px=boss.spot_x, py=400.0)
        # Advance one more frame with player inside spotlight
        pool, ep, lp = _pools()
        diff = Difficulty(DIFF_NORMAL)
        boss.update(DT, pool, ep, lp, boss.spot_x, 400.0, diff)
        assert not boss.invulnerable

    def test_invulnerable_outside_spotlight(self):
        boss = self._make()
        _skip_prep(boss)
        pool, ep, lp = _pools()
        diff = Difficulty(DIFF_NORMAL)
        far_x = boss.spot_x + boss._SPOT_W * 2 + 50.0
        boss.update(DT, pool, ep, lp, far_x, 400.0, diff)
        assert boss.invulnerable


# ===========================================================================
# LustBoss controls_inverted
# ===========================================================================
class TestLustBossControlsInverted:

    def _make(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_LUST, SKILL_NONE, WEAPON_DEFAULT)
        return LustBoss(cfg)

    def test_not_inverted_when_in_prep(self):
        boss = self._make()
        assert boss.in_prep
        assert not boss.controls_inverted

    def test_not_inverted_in_phase_0(self):
        boss = self._make()
        boss.in_prep = False
        boss._phase = 0
        assert not boss.controls_inverted

    def test_inverted_in_phase_1_not_prep(self):
        boss = self._make()
        boss.in_prep = False
        boss._phase = 1
        assert boss.controls_inverted

    def test_not_inverted_in_phase_2(self):
        boss = self._make()
        boss.in_prep = False
        boss._phase = 2
        assert not boss.controls_inverted


# ===========================================================================
# SinBoss horizontal tracking (regression: bosses were stationary)
# ===========================================================================
class TestSinBossMovement:

    @pytest.mark.parametrize("BossCls,boss_type", [
        (GreedBoss,   BOSS_GREED),
        (EnvyBoss,    BOSS_ENVY),
        (GluttonyBoss, BOSS_GLUTTONY),
        (LustBoss,    BOSS_LUST),
        (PrideBoss,   BOSS_PRIDE),
    ])
    def test_boss_tracks_player_x(self, BossCls, boss_type):
        cfg = GameConfig(DIFF_NORMAL, boss_type, SKILL_NONE, WEAPON_DEFAULT)
        boss = BossCls(cfg)
        # Skip prep with player at default center
        _skip_prep(boss)
        x_after_prep = boss.x
        # Now pull player far to the left for 2 seconds
        _run_frames(boss, 120, px=50.0, py=400.0)
        assert boss.x < x_after_prep, f"{BossCls.__name__} must move toward player X=50"

    def test_wrath_boss_already_tracked(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_WRATH, SKILL_NONE, WEAPON_DEFAULT)
        boss = WrathBoss(cfg)
        _skip_prep(boss)
        x_center = boss.x
        _run_frames(boss, 60, px=50.0, py=400.0)
        assert boss.x < x_center, "WrathBoss must track player leftward"

    def test_sloth_boss_drifts(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_SLOTH, SKILL_NONE, WEAPON_DEFAULT)
        boss = SlothBoss(cfg)
        _skip_prep(boss)
        x0, y0 = boss.x, boss.y
        _run_frames(boss, 300)  # 5 seconds — covers drift update
        dist = ((boss.x - x0)**2 + (boss.y - y0)**2) ** 0.5
        assert dist > 0.1, "SlothBoss must drift away from initial position"
