"""Padrões de tiro e integridade dos dados (a intenção dos testes de
padrão do legado — "fase X dispara Y" — generalizada pro port, onde tudo
é data-driven): toda referência entre os JSONs resolve, todo `emit` usado
em patterns.json tem implementação, e TODA fase de TODO boss produz
ameaça (balas, lasers, lacaios ou névoa) logo depois de entrar.
"""
import inspect
import json

from helpers import boss_pos, boss_view, player_prow, player_view, step

from bullethell.composition import build_headless
from bullethell.game_systems import EmitterSystem
from bullethell.ids import sid
from bullethell.loaders import DATA_DIR


def _json(nome):
    return json.loads((DATA_DIR / nome).read_text(encoding="utf-8"))


def test_patterns_referenciam_arquetipos_existentes():
    arquetipos = {a["name"] for a in _json("bullet_archetypes.json")["archetypes"]}
    for p in _json("patterns.json")["patterns"]:
        assert p["bullet"] in arquetipos, p["name"]


def test_bosses_referenciam_patterns_existentes():
    padroes = {p["name"] for p in _json("patterns.json")["patterns"]}
    for b in _json("bosses.json")["bosses"]:
        for i, ph in enumerate(b["phases"]):
            for em in ph["emitters"]:
                assert em["pattern"] in padroes, f'{b["name"]} fase {i}'


def test_nomes_sem_colisao_de_hash():
    """Tudo é indexado por crc32 do nome — colisão sobrescreveria um def."""
    for arquivo, chave in (("patterns.json", "patterns"),
                           ("bosses.json", "bosses"),
                           ("bullet_archetypes.json", "archetypes")):
        nomes = [e["name"] for e in _json(arquivo)[chave]]
        assert len(set(nomes)) == len(nomes), arquivo
        assert len({sid(n) for n in nomes}) == len(nomes), arquivo


def test_thresholds_de_fase_decrescentes(data):
    for bdef in data.bosses.values():
        limites = [ph.hp_above for ph in bdef.phases]
        assert limites == sorted(limites, reverse=True), bdef.name
        assert limites[-1] == 0.0, bdef.name


def test_todo_emit_tem_implementacao():
    fonte = inspect.getsource(EmitterSystem)
    for emit in {p["emit"] for p in _json("patterns.json")["patterns"]}:
        assert f'"{emit}"' in fonte, emit


def test_armas_do_menu_existem_nos_dados(data):
    from bullethell.scenes import WEAPONS
    nomes = {w.name for w in data.weapons.values()}
    assert len(WEAPONS) == 10
    for w in WEAPONS:
        assert w[0] in nomes, w[0]


def test_arma_sem_variante_plus_cai_na_base(data):
    """PLASMA não tem bloco `plus` em weapons.json, mas a mastery dela
    destrava o toggle — start_game() precisa cair na arma base em vez de
    montar um jogador com arma inexistente (que nunca atira)."""
    from helpers import make_app

    assert sid("plasma+") not in data.weapons
    app, _ = make_app(data, save={"weapon_plus_unlocked": ["plasma"]})
    app.sel.update(weapon="plasma", weapon_plus=True)
    app.start_game()
    pv = app.world.get_pool("player").active_view()
    assert int(pv["weapon_id"][0]) == sid("plasma")


# todos os bosses jogáveis (twins/lineage são pares de raízes)
BOSSES = ["classic", "timemage", "wall", "swarm", "twins", "summoner",
          "omega", "pride", "gluttony", "sloth", "envy", "greed", "lust",
          "wrath", "sin", "monolith", "icon", "lineage", "truth", "silence",
          "sabbath", "ascetic", "purity", "restitution", "mercy", "decalogue",
          "bastion"]


def _ameaca(world) -> int:
    return sum(world.get_pool(p).count
               for p in ("enemy_bullet", "laser", "minion", "hazard"))


def _casos(data_):
    casos = []
    for nome in BOSSES:
        world, _ = build_headless(boss_name=nome)
        bdef = data_.bosses[int(boss_view(world)["boss_id"][0])]
        casos += [(nome, i) for i in range(len(bdef.phases))]
    return casos


def pytest_generate_tests(metafunc):
    if "boss_fase" in metafunc.fixturenames:
        from bullethell.loaders import load_all
        casos = _casos(load_all())
        metafunc.parametrize("boss_fase", casos,
                             ids=[f"{b}-fase{i}" for b, i in casos])


def test_toda_fase_produz_ameaca(boss_fase, data):
    nome, fase = boss_fase
    world, inp = build_headless(boss_name=nome)
    player_view(world)["invuln_t"][player_prow(world)] = 1e6
    bp = world.get_pool("boss")
    if fase > 0:
        bv = boss_view(world)
        for k in range(bp.count):
            bdef = data.bosses[int(bv["boss_id"][k])]
            bv["phase_idx"][k] = fase - 1
            bv["hp"][k] = bv["max_hp"][k] * bdef.phases[fase - 1].hp_above - 1.0
        step(world, inp)
        assert int(boss_view(world)["phase_idx"][0]) == fase
    if data.bosses[int(boss_view(world)["boss_id"][0])].phases[fase].gimmick             == "berserk_body":
        # Ira fase 2: sem emitters — a ameaça é o próprio corpo ricocheteando
        x0 = boss_pos(world)[0]
        step(world, inp, 30)
        assert abs(boss_pos(world)[0] - x0) > 50.0
        return
    pico = 0
    for _ in range(4 * 60):
        step(world, inp)
        pico = max(pico, _ameaca(world))
        if pico:
            break
    assert pico > 0, f"{nome} fase {fase} não produziu nada em 4s"


def _balas_em_6s(diff: str) -> int:
    world, inp = build_headless(difficulty=diff)
    player_view(world)["invuln_t"][player_prow(world)] = 1e6
    eb = world.get_pool("enemy_bullet")
    total = 0
    for _ in range(6 * 60):
        step(world, inp)
        total += eb.count
    return total


def test_dda_abissal_dispara_mais_que_facil():
    """Mais dificuldade → mais balas em tela no mesmo intervalo (velocidade
    e densidade escalam com DIFFICULTIES/DDA)."""
    assert _balas_em_6s("abissal") > _balas_em_6s("facil")
