"""Progressão, gating, conquistas e registros (portado de smoke_gating.py
+ a intenção de TestSaveManagerDiffLock do legado): save novo começa
travado como o legado; vencer runs destrava dificuldade/skills/mutador/
boss/variantes '+' nas condições certas; masteries da run somam no save;
REGISTROS guarda o melhor tempo em DIFÍCIL+.
"""
import pytest

from ouroboros.interfaces.null.null_input_provider import NullInputProvider
from ouroboros.interfaces.null.null_renderer import NullRenderer

from bullethell.scenes import (ACHIEVEMENTS, BOSSES, DIFFS, MODES, MUTATORS,
                               SKILLS, TEST_BOSSES, GameApp)

DECALOGO_IDX = [m[0] for m in MODES].index("decalogo")


@pytest.fixture
def app_with(data):
    def _make(save: dict) -> GameApp:
        return GameApp(NullRenderer(), NullInputProvider(), None, data,
                       save_data=save)
    return _make


class TestSaveNovo:

    def test_so_facil_destravada(self, app_with):
        a = app_with({})
        assert a._diff_locked(0) is False
        for i in (1, 2, 3, 4):
            assert a._diff_locked(i) is True

    def test_decalogo_rush_travado(self, app_with):
        assert app_with({})._mode_locked(DECALOGO_IDX) is True

    def test_skills(self, app_with):
        a = app_with({})
        assert a._skill_locked("dash") is False
        assert a._skill_locked("parry") is True
        assert a._skill_locked("shield") is True

    def test_bosses_e_mutadores(self, app_with):
        a = app_with({})
        assert a._boss_locked("omega") is True
        assert a._boss_locked("classic") is False
        assert a._mutator_locked("claustro") is True
        assert a._mutator_locked("predador") is False

    def test_variantes_plus_travadas(self, app_with):
        a = app_with({})
        assert a._plus_unlocked("skill", "dash") is False
        assert a._plus_unlocked("weapon", "padrao") is False


def test_secao_de_teste_so_com_dev_mode(app_with):
    a = app_with({})
    assert "test" not in [i[0] for i in a._main_items()]
    a.dev_mode = True
    assert "test" in [i[0] for i in a._main_items()]
    nomes = [b[0] for b in TEST_BOSSES]
    # Mago do Tempo, 8 pecados e 10 do Decálogo; nada do menu clássico
    assert len(TEST_BOSSES) == 20
    assert {"timemage", "sin", "decalogue"} <= set(nomes)
    assert "omega" not in nomes


class TestVitorias:

    def test_vencer_facil(self, app_with):
        a = app_with({})
        a.sel["diff"] = "facil"
        a._apply_progression("win")
        assert a.save["highest_cleared_diff"] == 1
        assert a._diff_locked(1) is False
        assert "parry" in a.save["unlocked_skills"]
        assert "focus" not in a.save["unlocked_skills"]

    def test_derrota_nao_destrava_nada(self, app_with):
        a = app_with({})
        a._apply_progression("lose")
        assert a.save.get("highest_cleared_diff", 0) == 0

    def test_vencer_normal(self, app_with):
        a = app_with({"highest_cleared_diff": 1,
                      "unlocked_skills": ["none", "dash", "parry"]})
        a.sel["diff"] = "normal"
        a._apply_progression("win")
        assert a._diff_locked(2) is False
        assert "focus" in a.save["unlocked_skills"]

    def test_vencer_dificil_nao_destrava_plus_sozinho(self, app_with):
        a = app_with({"highest_cleared_diff": 2})
        a.sel["diff"] = "dificil"
        a._apply_progression("win")
        assert a._diff_locked(3) is False
        assert not a._plus_unlocked("skill", "dash")
        assert not a._plus_unlocked("weapon", "padrao")

    def test_vencer_com_flak_destrava_flak_plus(self, app_with):
        a = app_with({"highest_cleared_diff": 2})
        a.sel.update(diff="dificil", weapon="flak")
        a._apply_progression("win")
        assert a._plus_unlocked("weapon", "flak")

    def test_masteries_destravam_plus(self, app_with):
        a = app_with({})
        a.save["mastery_default_max"] = 150
        a.save["mastery_dash_graze"] = 50
        a._apply_progression("win")
        assert a._plus_unlocked("weapon", "padrao")
        assert a._plus_unlocked("skill", "dash")

    def test_abissal_exige_sins_rush(self, app_with):
        a = app_with({"highest_cleared_diff": 3})
        assert a._diff_locked(4) is True
        a.sel["mode"] = "sins"
        a.sel["diff"] = "expert"
        a._apply_progression("win")
        assert a._diff_locked(4) is False
        assert a._mode_locked(DECALOGO_IDX) is False
        assert a.save.get("decalogue_rush_cleared", False) is False

    def test_conquistas_destravam_emp_e_blink(self, app_with):
        a = app_with({})
        a.achieved = {"grazes_100", "no_hit_win"}
        a._apply_progression("win")
        assert "emp" in a.save["unlocked_skills"]
        assert "blink" in a.save["unlocked_skills"]

    def test_omega_e_claustrofobia(self, app_with):
        a = app_with({})
        a.achieved = {"omega_unlock"}
        a.sel["mode"], a.sel["boss"] = "classic", "summoner"
        a._apply_progression("win")
        assert a.save["omega_unlocked"] is True
        assert "claustro" in a.save["unlocked_mutators"]


class TestRegistros:

    def test_melhor_tempo_dificil_so_melhora(self, app_with):
        a = app_with({})
        a.sel["diff"] = "dificil"
        a.run_t = 200.0
        a._apply_progression("win")
        assert a.save["best_time_dificil"] == pytest.approx(200.0)
        a.run_t = 250.0                            # pior: não sobrescreve
        a._apply_progression("win")
        assert a.save["best_time_dificil"] == pytest.approx(200.0)
        a.run_t = 150.0
        a._apply_progression("win")
        assert a.save["best_time_dificil"] == pytest.approx(150.0)

    def test_normal_nao_conta_como_recorde(self, app_with):
        a = app_with({})
        a.sel["diff"] = "normal"
        a.run_t = 10.0
        a._apply_progression("win")
        assert a.save.get("best_time_dificil", 0.0) == 0.0


def test_tabelas_de_menu_integras():
    assert [d[0] for d in DIFFS] == ["facil", "normal", "dificil", "expert",
                                     "abissal"]
    assert any(s[0] == "shield" for s in SKILLS)
    assert any(m[0] == "claustro" for m in MUTATORS)
    assert any(b[0] == "omega" for b in BOSSES)


class TestConquistas:

    def test_tabela(self):
        ids = [a[0] for a in ACHIEVEMENTS]
        assert len(ids) == 21
        assert len(set(ids)) == len(ids)
        assert sum(1 for a in ACHIEVEMENTS if a[4]) == 5   # secretas

    def _fim(self, a, lives, graze=0, **sel):
        a.end_stats = (1, 0, 0)
        a.sel.update(**sel)
        a.totals["parries"] = a.totals["graze"] = 0
        a._check_achievements("win", lives=lives, graze=graze)

    def test_vitoria_dificil_com_3_mutadores(self, app_with):
        a = app_with({})
        a.run_t = 90.0
        self._fim(a, lives=0, mode="classic", diff="dificil", boss="omega",
                  skill="none", muts={"predador", "fantasma", "glass"})
        assert not ({"easy_win", "normal_win"} & a.achieved)
        assert {"hard_win", "mutator_hard", "omega_unlock", "speed_hard",
                "no_skill", "omega_hard", "glass_win", "all_mutators",
                "first_blood"} <= a.achieved

    def test_boss_rush_sem_hit(self, app_with):
        a = app_with({})
        a.run_t = 999.0
        self._fim(a, lives=3, mode="rush", diff="facil", boss="classic",
                  skill="dash", muts=set())
        assert {"boss_rush_win", "easy_win", "no_hit_win"} <= a.achieved
        assert not ({"hard_win", "speed_hard", "no_skill"} & a.achieved)

    def test_decalogo_rush(self, app_with):
        a = app_with({})
        a.run_t = 999.0
        self._fim(a, lives=3, mode="decalogo", diff="facil", boss="classic",
                  skill="dash", muts=set())
        assert {"decalogue_rush_win", "easy_win", "no_hit_win"} <= a.achieved

    def test_conquistas_novas_listadas_uma_vez(self, app_with):
        a = app_with({"achievements": ["first_blood"]})
        self._fim(a, lives=1, mode="classic", diff="facil", boss="classic",
                  skill="dash", muts=set())
        nomes_first_blood = [n for aid, n, *_ in ACHIEVEMENTS if aid == "first_blood"]
        assert nomes_first_blood[0] not in a.new_achievements
        assert "easy_win" in a.achieved


def test_partida_real_soma_mastery_no_save(data):
    """_finish_run puxa a pool `mastery` da run pro save (soma/máximo/OR)."""
    from helpers import follow_boss_and_step, make_app

    app, inp = make_app(data, save={"mastery_default_max": 3})
    app.sel.update(mode="classic", diff="facil", boss="classic",
                   skill="none", weapon="padrao")
    app.start_game()
    inp.set_action_held("fire", True)
    follow_boss_and_step(app.world, inp, 40.0, 90)
    app._finish_run("abandon")
    assert app.save["mastery_default_max"] >= 5
    assert app.totals["runs"] == 1
