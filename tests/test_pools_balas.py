"""Armazenamento de balas e pools (a intenção de test_pools.py do legado,
contra as ComponentPools da engine): capacidade fixa pré-alocada, spawn
escrevendo todas as colunas, destruição diferida até o fim do step,
cull fora da tela e reuso de slot sem crescer a pool.
"""
import pytest

from helpers import step

from bullethell.composition import ENTITY_CAPACITY, build_headless
from bullethell.game_systems import (CULL_MARGIN, spawn_enemy_bullet,
                                     spawn_player_bullet)
from bullethell.schemas import (GAME_POOL_CAPACITY, SCREEN_H, SCREEN_W,
                                TETHER_NONE)


@pytest.fixture
def mundo():
    """Mundo do Clássico com os emitters desligados (pools só com o que o
    teste spawnar) e o jogador num canto, longe das balas de teste."""
    world, inp = build_headless()
    em = world.get_pool("emitter")
    for h in em.active_view()["self"][:em.count]:
        world.destroy_entity(int(h))
    step(world, inp)
    return world, inp


def _bala_em(world, x, y, vx=0.0, vy=0.0, **kw):
    return spawn_enemy_bullet(world, world, x, y, vx, vy, **kw)


def test_capacidades_fixas_das_pools():
    world, _ = build_headless()
    for nome, cap in GAME_POOL_CAPACITY.items():
        assert world.get_pool(nome).capacity == cap, nome
    assert world.get_pool("enemy_bullet").capacity == 5000
    assert world.get_pool("transform").capacity == ENTITY_CAPACITY


def test_spawn_escreve_as_colunas(mundo):
    world, _ = mundo
    eb = world.get_pool("enemy_bullet")
    n0 = eb.count
    packed = _bala_em(world, 300.0, 200.0, 10.0, 20.0, color=3, radius=6.0,
                      bounces=2, homing_t=1.5)
    assert packed >= 0
    assert eb.count == n0 + 1
    idx = packed & 0xFFFFFFFF
    ev = eb.active_view()
    row = eb.dense_row_of(idx)
    assert int(ev["self"][row]) == packed
    assert int(ev["color"][row]) == 3
    assert float(ev["radius"][row]) == pytest.approx(6.0)
    assert int(ev["bounces"][row]) == 2
    assert float(ev["homing_t"][row]) == pytest.approx(1.5)
    assert ev["tether"][row] == TETHER_NONE
    assert int(ev["grazed"][row]) == 0 and int(ev["fragment"][row]) == 0
    tp = world.get_pool("transform")
    trow = tp.dense_row_of(idx)
    assert float(tp.active_view()["position_x"][trow]) == pytest.approx(300.0)
    vel = world.get_pool("velocity")
    assert float(vel.active_view()["linear_y"][vel.dense_row_of(idx)]) == pytest.approx(20.0)


def test_pool_cheia_recusa_sem_crescer(mundo):
    world, _ = mundo
    eb = world.get_pool("enemy_bullet")
    while eb.count < eb.capacity - 1:
        assert _bala_em(world, 100.0, 100.0) >= 0
    assert _bala_em(world, 100.0, 100.0) == -1
    assert eb.count == eb.capacity - 1
    assert eb.capacity == 5000


def test_pool_de_bala_do_jogador_cheia_recusa(mundo):
    world, _ = mundo
    pb = world.get_pool("pb_core")
    while pb.count < pb.capacity:
        assert spawn_player_bullet(world, world, "pb_padrao", 100.0, 100.0,
                                   0.0, 0.0, 1.0, 3.0) >= 0
    assert spawn_player_bullet(world, world, "pb_padrao", 100.0, 100.0,
                               0.0, 0.0, 1.0, 3.0) == -1


def test_destroy_e_diferido_ate_o_fim_do_step(mundo):
    world, inp = mundo
    eb = world.get_pool("enemy_bullet")
    packed = _bala_em(world, 200.0, 200.0)
    n = eb.count
    world.destroy_entity(packed)
    assert eb.count == n, "linhas densas continuam válidas durante o frame"
    step(world, inp)
    assert eb.dense_row_of(packed & 0xFFFFFFFF) < 0


def test_cull_fora_da_tela(mundo):
    world, inp = mundo
    eb = world.get_pool("enemy_bullet")
    dentro = _bala_em(world, SCREEN_W / 2, SCREEN_H / 2) & 0xFFFFFFFF
    fora = [_bala_em(world, -CULL_MARGIN - 10.0, 100.0),
            _bala_em(world, SCREEN_W + CULL_MARGIN + 10.0, 100.0),
            _bala_em(world, 100.0, SCREEN_H + CULL_MARGIN + 10.0)]
    step(world, inp, 2)
    assert eb.dense_row_of(dentro) >= 0
    for p in fora:
        assert eb.dense_row_of(p & 0xFFFFFFFF) < 0


def test_bala_em_movimento_sai_da_tela_e_some(mundo):
    world, inp = mundo
    eb = world.get_pool("enemy_bullet")
    p = _bala_em(world, SCREEN_W / 2, 100.0, 0.0, -600.0) & 0xFFFFFFFF
    step(world, inp, 30)
    assert eb.dense_row_of(p) < 0


def test_reuso_de_slots_nao_vaza(mundo):
    """Spawn/cull em ciclos: a contagem volta ao zero e nunca estoura."""
    world, inp = mundo
    eb = world.get_pool("enemy_bullet")
    base = eb.count
    for _ in range(5):
        for j in range(1000):
            _bala_em(world, -CULL_MARGIN - 50.0, float(j % SCREEN_H))
        step(world, inp)
        assert eb.count == base
