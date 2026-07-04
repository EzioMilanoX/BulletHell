"""test_gameplay.py — Collision, damage pipeline, difficulty mechanic tests."""
import math
import pytest

from entities import (
    BulletPool, PlayerBulletPool, EnemyPool, EmitterPool, LaserPool,
    SpatialHash, check_boss_collision,
    Boss, DummyBoss, PrideBoss,
    Player, Difficulty,
    GameConfig,
    DIFF_NORMAL, DIFF_HARD, DIFF_EXPERT, DIFF_ABISSAL,
    BOSS_CLASSIC, BOSS_DUMMY, BOSS_PRIDE,
    SKILL_NONE, WEAPON_DEFAULT,
    ETYPE_KAMIKAZE, ENEMY_KAMIKAZE_HP,
    BTYPE_PURPLE, TWO_PI,
    SCREEN_W, SCREEN_H,
    MAX_LIVES, INVULN_FRAMES,
)

DT = 1 / 60


# ===========================================================================
# Bullet → player collision (SpatialHash.query_player)
# ===========================================================================
class TestBulletPlayerCollision:

    def test_bullet_at_player_position_registers_hit(self):
        pool = BulletPool()
        shash = SpatialHash()
        px, py = 640.0, 360.0
        idx = pool.acquire()
        pool.bx[idx] = px
        pool.by[idx] = py
        shash.build(pool)
        hits = shash.query_player(px, py, pool)
        assert hits >= 1, "Bullet on top of player must register a hit"

    def test_bullet_far_away_registers_no_hit(self):
        pool = BulletPool()
        shash = SpatialHash()
        px, py = 640.0, 360.0
        idx = pool.acquire()
        pool.bx[idx] = px + 500.0
        pool.by[idx] = py + 500.0
        shash.build(pool)
        hits = shash.query_player(px, py, pool)
        assert hits == 0

    def test_empty_pool_registers_no_hit(self):
        pool = BulletPool()
        shash = SpatialHash()
        shash.build(pool)
        hits = shash.query_player(640.0, 360.0, pool)
        assert hits == 0

    def test_hit_bullet_deactivated(self):
        pool = BulletPool()
        shash = SpatialHash()
        px, py = 640.0, 360.0
        idx = pool.acquire()
        pool.bx[idx] = px
        pool.by[idx] = py
        shash.build(pool)
        shash.query_player(px, py, pool)
        assert not pool.active[idx], "Bullet that hit player must be deactivated"


# ===========================================================================
# Player bullet → enemy collision (EnemyPool.check_pb_hit)
# ===========================================================================
class TestPlayerBulletEnemyCollision:

    def test_lethal_hit_kills_and_records(self):
        enm = EnemyPool()
        pb = PlayerBulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        pb_idx = pb.acquire(damage=ENEMY_KAMIKAZE_HP + 1.0)
        pb.px[pb_idx] = 400.0
        pb.py[pb_idx] = 300.0
        kills = enm.check_pb_hit(pb)
        assert kills == 1
        assert not enm.active[idx]
        assert enm._kill_n == 1

    def test_nonlethal_hit_preserves_enemy(self):
        enm = EnemyPool()
        pb = PlayerBulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        pb_idx = pb.acquire(damage=0.001)
        pb.px[pb_idx] = 400.0
        pb.py[pb_idx] = 300.0
        kills = enm.check_pb_hit(pb)
        assert kills == 0
        assert enm.active[idx]

    def test_miss_does_not_damage(self):
        enm = EnemyPool()
        pb = PlayerBulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        initial_hp = float(enm.ehp[idx])
        pb_idx = pb.acquire(damage=5.0)
        pb.px[pb_idx] = 900.0  # far away
        pb.py[pb_idx] = 600.0
        enm.check_pb_hit(pb)
        assert float(enm.ehp[idx]) == pytest.approx(initial_hp)


# ===========================================================================
# Player bullet → boss collision (check_boss_collision)
# ===========================================================================
class TestBossCollision:

    def _place_pb_on_boss(self, pb, boss):
        """Place a player bullet at the boss's first AABB center."""
        x0, y0, x1, y1 = boss.get_aabb_list()[0]
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        idx = pb.acquire(damage=10.0)
        pb.px[idx] = cx
        pb.py[idx] = cy
        return idx

    def test_bullet_on_boss_deals_damage(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        initial_hp = boss.hp
        self._place_pb_on_boss(pb, boss)
        hits = check_boss_collision(pb, boss, diff)
        assert hits >= 1
        assert boss.hp < initial_hp
        assert boss.hp == pytest.approx(initial_hp - 10.0)

    def test_glass_cannon_triples_damage(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        initial_hp = boss.hp
        self._place_pb_on_boss(pb, boss)
        check_boss_collision(pb, boss, diff, glass_cannon=True)
        assert boss.hp == pytest.approx(initial_hp - 30.0)

    def test_miss_deals_no_damage(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        initial_hp = boss.hp
        # Place bullet far off-screen
        idx = pb.acquire(damage=10.0)
        pb.px[idx] = -500.0
        pb.py[idx] = -500.0
        hits = check_boss_collision(pb, boss, diff)
        assert hits == 0
        assert boss.hp == pytest.approx(initial_hp)

    def test_invulnerable_boss_takes_no_damage(self):
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        boss.invulnerable = True
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        initial_hp = boss.hp
        self._place_pb_on_boss(pb, boss)
        hits = check_boss_collision(pb, boss, diff)
        assert hits == 0
        assert boss.hp == pytest.approx(initial_hp)

    def test_dummy_boss_hp_stays_constant(self):
        dummy = DummyBoss()
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        initial_hp = dummy.hp
        x0, y0, x1, y1 = dummy.get_aabb_list()[0]
        idx = pb.acquire(damage=5.0)
        pb.px[idx] = (x0 + x1) / 2.0
        pb.py[idx] = (y0 + y1) / 2.0
        check_boss_collision(pb, dummy, diff)
        assert dummy.hp == pytest.approx(initial_hp)

    def test_dummy_boss_records_total_damage(self):
        dummy = DummyBoss()
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_NORMAL)
        x0, y0, x1, y1 = dummy.get_aabb_list()[0]
        idx = pb.acquire(damage=5.0)
        pb.px[idx] = (x0 + x1) / 2.0
        pb.py[idx] = (y0 + y1) / 2.0
        check_boss_collision(pb, dummy, diff)
        assert dummy.total_damage == pytest.approx(5.0)


# ===========================================================================
# Kamikaze → player collision (EnemyPool.check_player_hit)
# ===========================================================================
class TestKamikazePlayerCollision:

    def test_kamikaze_at_player_explodes(self):
        enm = EnemyPool()
        idx = enm.acquire(640.0, 360.0, ETYPE_KAMIKAZE)
        hits = enm.check_player_hit(640.0, 360.0)
        assert hits == 1
        assert not enm.active[idx]

    def test_kamikaze_far_away_does_not_explode(self):
        enm = EnemyPool()
        idx = enm.acquire(0.0, 0.0, ETYPE_KAMIKAZE)
        hits = enm.check_player_hit(640.0, 360.0)
        assert hits == 0
        assert enm.active[idx]


# ===========================================================================
# Difficulty mechanic flags
# ===========================================================================
class TestDifficultyFlags:

    def test_normal_no_second_wind(self):
        assert not Difficulty(DIFF_NORMAL).second_wind

    def test_expert_has_second_wind(self):
        assert Difficulty(DIFF_EXPERT).second_wind

    def test_abissal_has_second_wind(self):
        assert Difficulty(DIFF_ABISSAL).second_wind

    def test_normal_no_revenge_bullets(self):
        assert not Difficulty(DIFF_NORMAL).revenge_bullets

    def test_expert_no_revenge_bullets(self):
        assert not Difficulty(DIFF_EXPERT).revenge_bullets

    def test_abissal_has_revenge_bullets(self):
        assert Difficulty(DIFF_ABISSAL).revenge_bullets

    def test_normal_prep_scale_one(self):
        assert Difficulty(DIFF_NORMAL).prep_scale == pytest.approx(1.0)

    def test_expert_prep_scale_half(self):
        assert Difficulty(DIFF_EXPERT).prep_scale == pytest.approx(0.5)

    def test_abissal_prep_scale_half(self):
        assert Difficulty(DIFF_ABISSAL).prep_scale == pytest.approx(0.5)


# ===========================================================================
# Revenge bullets — game loop logic replication
# ===========================================================================
class TestRevengeBullets:

    def test_8_bullet_ring_spawned_on_kill(self):
        """Killing a minion at ABISSAL spawns an 8-bullet ring in BulletPool."""
        enm = EnemyPool()
        bp = BulletPool()
        pb = PlayerBulletPool()
        diff = Difficulty(DIFF_ABISSAL)
        assert diff.revenge_bullets

        enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        pb_idx = pb.acquire(damage=ENEMY_KAMIKAZE_HP + 1.0)
        pb.px[pb_idx] = 400.0
        pb.py[pb_idx] = 300.0
        enm.check_pb_hit(pb)

        bullets_before = int(bp.active.sum())
        # Replicate game loop: spawn 8-bullet ring for each kill
        for ki in range(enm._kill_n):
            kx = float(enm._kill_xs[ki])
            ky = float(enm._kill_ys[ki])
            for ri in range(8):
                ang = ri * (TWO_PI / 8)
                bidx = bp.acquire()
                if bidx < 0:
                    break
                bp.bx[bidx] = kx
                bp.by[bidx] = ky
                bp.bvx[bidx] = math.cos(ang) * 150.0
                bp.bvy[bidx] = math.sin(ang) * 150.0
                bp.b_type[bidx] = BTYPE_PURPLE

        assert int(bp.active.sum()) == bullets_before + 8


# ===========================================================================
# Second Wind — boss HP intercept
# ===========================================================================
class TestSecondWind:

    def test_second_wind_flag_on_expert(self):
        diff = Difficulty(DIFF_EXPERT)
        assert diff.second_wind

    def test_intercept_freezes_hp_at_one(self):
        """Simulate the game loop intercept: hp <= 0 on EXPERT → freeze at 1."""
        cfg = GameConfig(DIFF_EXPERT, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        diff = Difficulty(DIFF_EXPERT)
        boss.hp = 2.0
        boss.take_damage(10.0, diff)
        # Game loop intercept logic (replicated)
        if boss.hp <= 0 and diff.second_wind:
            boss.hp = 1.0
            boss.invulnerable = True
        assert boss.hp == pytest.approx(1.0)
        assert boss.invulnerable

    def test_no_intercept_on_normal(self):
        """On NORMAL, the boss actually dies (hp goes <= 0)."""
        cfg = GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)
        boss = Boss(cfg)
        diff = Difficulty(DIFF_NORMAL)
        boss.hp = 2.0
        boss.take_damage(10.0, diff)
        assert boss.hp <= 0


# ===========================================================================
# SaveManager diff lock
# ===========================================================================
class TestSaveManagerDiffLock:

    def test_abissal_locked_without_sins_rush(self):
        from entities import SaveManager, DIFF_ABISSAL
        save = SaveManager.__new__(SaveManager)
        save.sins_rush_cleared = False
        assert save.diff_locked(DIFF_ABISSAL)

    def test_abissal_unlocked_after_sins_rush(self):
        from entities import SaveManager, DIFF_ABISSAL
        save = SaveManager.__new__(SaveManager)
        save.sins_rush_cleared = True
        assert not save.diff_locked(DIFF_ABISSAL)
