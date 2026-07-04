"""conftest.py — Headless pygame setup + shared fixtures for the BulletHell test suite."""
import os, sys

# Must be set BEFORE pygame is imported for the first time.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Make project root importable from the tests/ subdirectory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
pygame.init()
pygame.font.init()

import pytest
from entities import (
    GameConfig, Difficulty,
    DIFF_NORMAL, DIFF_HARD, DIFF_EXPERT, DIFF_ABISSAL,
    BOSS_CLASSIC, BOSS_DUMMY, SKILL_NONE, WEAPON_DEFAULT,
    BulletPool, PlayerBulletPool, EnemyPool, EmitterPool, LaserPool,
)


# ---------------------------------------------------------------------------
# Session-scoped pygame teardown
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# GameConfig helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def cfg_normal():
    return GameConfig(DIFF_NORMAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)

@pytest.fixture
def cfg_hard():
    return GameConfig(DIFF_HARD, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)

@pytest.fixture
def cfg_expert():
    return GameConfig(DIFF_EXPERT, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)

@pytest.fixture
def cfg_abissal():
    return GameConfig(DIFF_ABISSAL, BOSS_CLASSIC, SKILL_NONE, WEAPON_DEFAULT)


# ---------------------------------------------------------------------------
# Difficulty singletons
# ---------------------------------------------------------------------------
@pytest.fixture
def diff_normal():
    return Difficulty(DIFF_NORMAL)

@pytest.fixture
def diff_expert():
    return Difficulty(DIFF_EXPERT)

@pytest.fixture
def diff_abissal():
    return Difficulty(DIFF_ABISSAL)


# ---------------------------------------------------------------------------
# Pool factories
# ---------------------------------------------------------------------------
@pytest.fixture
def pool():
    return BulletPool()

@pytest.fixture
def pb():
    return PlayerBulletPool()

@pytest.fixture
def enm():
    return EnemyPool()

@pytest.fixture
def ep():
    return EmitterPool()

@pytest.fixture
def lp():
    return LaserPool()
