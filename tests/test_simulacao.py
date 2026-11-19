"""Partidas headless de ponta a ponta (portado de smoke_ecs.py).

Cada caso roda centenas de frames com um "piloto" simples (ver
`helpers.simulate`) e confere o mínimo que uma partida jogável precisa:
o boss atira (padrões disparam) e toma dano (armas acertam). Modos com
fila (Boss Rush, Decálogo Rush, Waves) e as dificuldades EXPERT/ABISSAL
precisam fechar o ciclo de morte do boss.
"""
import pytest

from helpers import simulate, step

from bullethell.composition import build_headless


def _assert_jogavel(r: dict) -> None:
    assert r["enemy_bullets_peak"] > 0, f"boss nunca atirou: {r}"
    assert r["boss_damage"] > 0, f"boss nunca tomou dano: {r}"


# (boss, arma, aproximar) — spread+ derrete o classic → estende p/ alcançar
# a fase 3 (lasers)
ARMAS = [
    ("classic", "padrao", False), ("classic", "padrao+", False),
    ("classic", "spread", False), ("classic", "spread+", True),
    ("classic", "agulha", False), ("classic", "agulha+", False),
    ("classic", "teleguiado", False), ("classic", "teleguiado+", False),
    ("classic", "plasma", True),
    ("classic", "carregado", True), ("classic", "carregado+", True),
    ("classic", "burst", False), ("classic", "burst+", False),
    ("classic", "flak", False), ("classic", "flak+", False),
    ("classic", "chakram", True), ("classic", "chakram+", True),
    ("classic", "satelite", True), ("classic", "satelite+", True),
    ("timemage", "padrao", False), ("timemage", "spread+", True),
    ("wall", "padrao", False), ("swarm", "spread", False),
    ("twins", "teleguiado", False),
]


@pytest.mark.parametrize("boss,weapon,approach", ARMAS,
                         ids=[f"{b}-{w}" for b, w, _ in ARMAS])
def test_arma_acerta_e_boss_atira(boss, weapon, approach):
    frames = 1600 if (boss, weapon) == ("classic", "spread+") else 900
    _assert_jogavel(simulate(boss, weapon, frames=frames, approach=approach))


SKILLS = ["dash", "dash+", "parry", "parry+", "focus", "emp", "emp+",
          "blink", "blink+", "overclock", "overclock+", "shield",
          "shield+", "timedil", "timedil+"]


@pytest.mark.parametrize("skill", SKILLS)
def test_habilidade_nao_quebra_a_partida(skill):
    boss = "timemage" if skill.startswith("timedil") else "classic"
    _assert_jogavel(simulate(boss, "padrao", skill=skill))


MUTADORES = [("predador",), ("fantasma",), ("glass",), ("claustro",),
             ("horde",), ("berserker",), ("predador", "fantasma", "glass")]


@pytest.mark.parametrize("muts", MUTADORES, ids=["+".join(m) for m in MUTADORES])
def test_mutador_nao_quebra_a_partida(muts):
    _assert_jogavel(simulate("classic", "padrao", mutators=frozenset(muts)))


# bosses das fases 6-8 (Invocador, Ômega, os 8 pecados) e do Decálogo que
# são danificáveis por mira ingênua (raiz sem invuln escondendo nada).
# Icon fica de fora de propósito: a mira ingênua nunca acerta os clones
# (é um boss de "ache o alvo certo") — coberto em test_decalogo.py.
BOSSES = [
    ("summoner", "spread", False, 900), ("omega", "spread+", True, 1600),
    ("pride", "spread", False, 1600), ("gluttony", "spread", False, 900),
    ("sloth", "spread+", True, 1600), ("envy", "spread", False, 900),
    ("greed", "spread", False, 900), ("lust", "spread", False, 900),
    ("wrath", "spread+", True, 1600), ("sin", "spread+", True, 1600),
    ("monolith", "padrao", False, 1600), ("lineage", "padrao", False, 1600),
    ("truth", "padrao", False, 1600), ("silence", "padrao", False, 1600),
    ("sabbath", "padrao", False, 1600), ("ascetic", "padrao", False, 1600),
    ("purity", "padrao", False, 1600), ("restitution", "padrao", False, 1600),
    ("mercy", "padrao", False, 1600), ("decalogue", "padrao", False, 1600),
]


@pytest.mark.parametrize("boss,weapon,approach,frames", BOSSES,
                         ids=[b[0] for b in BOSSES])
def test_boss_atira_e_toma_dano(boss, weapon, approach, frames):
    _assert_jogavel(simulate(boss, weapon, frames=frames, approach=approach))


@pytest.mark.parametrize("diff", ["expert", "abissal"])
def test_expert_abissal_fecham_o_ciclo_de_morte(diff):
    """DDA + Segundo Fôlego + Fragmentação: spread+ derrete o classic; o
    Segundo Fôlego "sobrevive" com 1 HP antes de cair de vez (kills>=1 só
    acontece depois do timer de 3s esgotar)."""
    r = simulate("classic", "spread+", frames=3600, approach=True,
                 difficulty=diff)
    assert r["kills"] >= 1, r


@pytest.mark.parametrize("mode", ["rush", "decalogo"])
def test_rush_avanca_para_o_proximo_boss(mode):
    """Boss Rush (classic→swarm) e Decálogo Rush (monolith→icon)."""
    r = simulate("classic", "spread+", frames=2400, approach=True, mode=mode)
    assert r["kills"] >= 1, r


def test_waves_limpa_ondas_e_avanca():
    r = simulate("classic", "spread", frames=2400, mode="waves")
    assert r["wave"] >= 2, r


def test_sins_rush_escala_hp_por_estagio(data):
    """SINS RUSH: HP +15%/stage (legado, spec menus §11) — o 2º boss da
    fila tem mais HP máximo que o 1º só pelo estágio."""
    from bullethell.game_systems import SINS_RUSH_HP_SCALE

    world, inp = build_headless(mode="sins")
    bv = world.get_pool("boss").active_view()
    hp0 = float(bv["max_hp"][0])
    # precisa estar na ÚLTIMA fase para hp<=0 valer como morte de verdade
    # (senão BossPhaseSystem só pina em 1.0 e avança de fase)
    bv["phase_idx"][0] = len(data.bosses[int(bv["boss_id"][0])].phases) - 1
    bv["hp"][0] = 0.0
    step(world, inp)
    bv = world.get_pool("boss").active_view()
    assert float(bv["max_hp"][0]) == pytest.approx(hp0 * SINS_RUSH_HP_SCALE,
                                                  abs=1e-3)
