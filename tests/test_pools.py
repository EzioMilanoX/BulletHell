"""test_pools.py — Zero-GC SoA pool integrity tests."""
import numpy as np
import pytest

from entities import (
    BulletPool, PlayerBulletPool, EnemyPool,
    MAX_BULLETS, MAX_ENEMIES, MAX_PB,
    ETYPE_KAMIKAZE, ETYPE_SENTINEL,
    ENEMY_KAMIKAZE_HP,
)

DT = 1 / 60


# ===========================================================================
# BulletPool
# ===========================================================================
class TestBulletPool:

    def test_acquire_activates_slot(self):
        bp = BulletPool()
        idx = bp.acquire()
        assert idx >= 0
        assert bp.active[idx]

    def test_acquire_fills_to_max(self):
        bp = BulletPool()
        for _ in range(MAX_BULLETS):
            assert bp.acquire() >= 0
        assert int(bp.active.sum()) == MAX_BULLETS

    def test_overflow_returns_minus_one(self):
        bp = BulletPool()
        for _ in range(MAX_BULLETS):
            bp.acquire()
        assert bp.acquire() == -1
        assert int(bp.active.sum()) == MAX_BULLETS

    def test_release_frees_slot_for_reuse(self):
        bp = BulletPool()
        idx = bp.acquire()
        bp.release(idx)
        assert not bp.active[idx]
        idx2 = bp.acquire()
        assert idx2 == idx

    def test_clear_deactivates_all(self):
        bp = BulletPool()
        for _ in range(20):
            bp.acquire()
        bp.clear()
        assert bp.active.sum() == 0

    def test_soa_bool_defaults_after_acquire(self):
        bp = BulletPool()
        idx = bp.acquire()
        assert not bp.b_fragment[idx]
        assert not bp.b_ricochet[idx]
        assert not bp.b_invisible[idx]

    def test_abissal_flag_default_false(self):
        bp = BulletPool()
        assert bp._abissal == False

    def test_fragment_flag_settable(self):
        bp = BulletPool()
        idx = bp.acquire()
        bp.b_fragment[idx] = True
        assert bp.b_fragment[idx]


# ===========================================================================
# PlayerBulletPool
# ===========================================================================
class TestPlayerBulletPool:

    def test_acquire_with_default_damage(self):
        pb = PlayerBulletPool()
        idx = pb.acquire()
        assert pb.active[idx]
        assert pb.damage[idx] == pytest.approx(1.0)

    def test_acquire_with_custom_damage(self):
        pb = PlayerBulletPool()
        idx = pb.acquire(damage=7.5)
        assert pb.damage[idx] == pytest.approx(7.5)

    def test_overflow_returns_minus_one(self):
        pb = PlayerBulletPool()
        for _ in range(MAX_PB):
            pb.acquire()
        assert pb.acquire() == -1
        assert int(pb.active.sum()) == MAX_PB

    def test_release_and_reuse(self):
        pb = PlayerBulletPool()
        idx = pb.acquire(damage=3.0)
        pb.release(idx)
        assert not pb.active[idx]
        idx2 = pb.acquire(damage=9.0)
        assert idx2 == idx
        assert pb.damage[idx2] == pytest.approx(9.0)

    def test_px_py_attributes_exist(self):
        pb = PlayerBulletPool()
        assert hasattr(pb, 'px') and hasattr(pb, 'py')
        assert len(pb.px) == MAX_PB


# ===========================================================================
# EnemyPool
# ===========================================================================
class TestEnemyPool:

    def test_acquire_sets_position_and_type(self):
        enm = EnemyPool()
        idx = enm.acquire(100.0, 200.0, ETYPE_KAMIKAZE)
        assert enm.active[idx]
        assert enm.ex[idx] == pytest.approx(100.0)
        assert enm.ey[idx] == pytest.approx(200.0)
        assert enm.etype[idx] == ETYPE_KAMIKAZE

    def test_acquire_sets_positive_hp(self):
        enm = EnemyPool()
        idx = enm.acquire(0.0, 0.0, ETYPE_KAMIKAZE)
        assert enm.ehp[idx] > 0

    def test_overflow_at_max_enemies(self):
        enm = EnemyPool()
        acquired = [enm.acquire(float(i), 0.0, ETYPE_KAMIKAZE) for i in range(MAX_ENEMIES)]
        assert all(i >= 0 for i in acquired)
        assert enm.acquire(0.0, 0.0, ETYPE_KAMIKAZE) == -1

    def test_hit_flash_default_zero(self):
        enm = EnemyPool()
        idx = enm.acquire(0.0, 0.0, ETYPE_KAMIKAZE)
        assert enm.e_hit_flash[idx] == 0

    def test_hit_flash_decrements_each_frame(self):
        enm = EnemyPool()
        bp = BulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        enm.e_hit_flash[idx] = 4
        enm.update(DT, bp, 400.0, 300.0, 1.0)
        assert enm.e_hit_flash[idx] == 3

    def test_hit_flash_does_not_go_negative(self):
        enm = EnemyPool()
        bp = BulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        enm.e_hit_flash[idx] = 0
        for _ in range(5):
            enm.update(DT, bp, 400.0, 300.0, 1.0)
        assert enm.e_hit_flash[idx] == 0

    def test_lethal_hit_kills_enemy_and_writes_kill_buffer(self):
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
        assert enm._kill_xs[0] == pytest.approx(400.0)
        assert enm._kill_ys[0] == pytest.approx(300.0)

    def test_nonlethal_hit_sets_flash_and_writes_hit_buffer(self):
        enm = EnemyPool()
        pb = PlayerBulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        # Tiny damage — won't kill
        pb_idx = pb.acquire(damage=0.001)
        pb.px[pb_idx] = 400.0
        pb.py[pb_idx] = 300.0
        kills = enm.check_pb_hit(pb)
        assert kills == 0
        assert enm.active[idx]
        assert enm.e_hit_flash[idx] == 4
        assert enm._hit_n == 1

    def test_clear_resets_flash_array(self):
        enm = EnemyPool()
        idx = enm.acquire(0.0, 0.0, ETYPE_KAMIKAZE)
        enm.e_hit_flash[idx] = 4
        enm.clear()
        assert enm.e_hit_flash.sum() == 0

    def test_kill_n_reset_each_check(self):
        enm = EnemyPool()
        pb = PlayerBulletPool()
        idx = enm.acquire(400.0, 300.0, ETYPE_KAMIKAZE)
        pb_idx = pb.acquire(damage=ENEMY_KAMIKAZE_HP + 1.0)
        pb.px[pb_idx] = 400.0
        pb.py[pb_idx] = 300.0
        enm.check_pb_hit(pb)
        assert enm._kill_n == 1
        # Second call with empty pb — kill_n must reset to 0
        pb2 = PlayerBulletPool()
        enm.check_pb_hit(pb2)
        assert enm._kill_n == 0
