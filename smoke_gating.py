"""
Smoke test da progressao/gating (PARITY_PLAN.md P0-1): confere que o save
novo comeca travado como o legado (SaveManager, entities.py:5035-5495) e
que vencer runs destrava dificuldade/skills/mutador/boss/variantes '+' nas
condicoes certas. Não sobe janela nem World — só testa GameApp.save/sel.

Uso: python smoke_gating.py
"""
import bullethell  # noqa: F401 — engine no sys.path
from ouroboros.interfaces.null.null_renderer import NullRenderer
from ouroboros.interfaces.null.null_input_provider import NullInputProvider
from bullethell.loaders import load_all
from bullethell.scenes import BOSSES, DIFFS, GameApp, MUTATORS, SKILLS

DATA = load_all()


def app_with(save: dict) -> GameApp:
    return GameApp(NullRenderer(), NullInputProvider(), None, DATA,
                  save_data=save)


def check(label: str, cond: bool) -> bool:
    print(f"[{'OK ' if cond else 'FAIL'}] {label}")
    return cond


if __name__ == "__main__":
    ok = True

    a = app_with({})
    ok &= check("save novo: FACIL destravada", a._diff_locked(0) is False)
    ok &= check("save novo: NORMAL travada", a._diff_locked(1) is True)
    ok &= check("save novo: DIFICIL travada", a._diff_locked(2) is True)
    ok &= check("save novo: EXPERT travada", a._diff_locked(3) is True)
    ok &= check("save novo: ABISSAL travada (exige SINS RUSH)",
               a._diff_locked(4) is True)
    ok &= check("save novo: DASH destravada", a._skill_locked("dash") is False)
    ok &= check("save novo: PARRY travada", a._skill_locked("parry") is True)
    ok &= check("save novo: ESCUDO travada", a._skill_locked("shield") is True)
    ok &= check("save novo: boss OMEGA travado", a._boss_locked("omega") is True)
    ok &= check("save novo: boss CLASSICO destravado",
               a._boss_locked("classic") is False)
    ok &= check("save novo: mutador CLAUSTROFOBIA travado",
               a._mutator_locked("claustro") is True)
    ok &= check("save novo: mutador PREDADOR destravado",
               a._mutator_locked("predador") is False)
    ok &= check("save novo: variantes '+' travadas",
               a._plus_unlocked("skill") is False)

    a = app_with({})
    a.sel["diff"] = "facil"
    a._apply_progression("win")
    ok &= check("vencer FACIL -> highest_cleared_diff=1",
               a.save["highest_cleared_diff"] == 1)
    ok &= check("vencer FACIL -> NORMAL destrava", a._diff_locked(1) is False)
    ok &= check("vencer FACIL -> PARRY destrava",
               "parry" in a.save["unlocked_skills"])
    ok &= check("vencer FACIL -> FOCO ainda travada",
               "focus" not in a.save["unlocked_skills"])

    a = app_with({"highest_cleared_diff": 1,
                 "unlocked_skills": ["none", "dash", "parry"]})
    a.sel["diff"] = "normal"
    a._apply_progression("win")
    ok &= check("vencer NORMAL -> DIFICIL destrava", a._diff_locked(2) is False)
    ok &= check("vencer NORMAL -> FOCO destrava",
               "focus" in a.save["unlocked_skills"])

    a = app_with({"highest_cleared_diff": 2})
    a.sel["diff"] = "dificil"
    a._apply_progression("win")
    ok &= check("vencer DIFICIL -> EXPERT destrava", a._diff_locked(3) is False)
    ok &= check("vencer DIFICIL -> variantes '+' destravam",
               a._plus_unlocked("skill") and a._plus_unlocked("weapon"))

    a = app_with({"highest_cleared_diff": 3})
    ok &= check("ABISSAL não destrava só por tier (sem SINS RUSH)",
               a._diff_locked(4) is True)
    a.sel["mode"] = "sins"
    a.sel["diff"] = "expert"
    a._apply_progression("win")
    ok &= check("vencer o SINS RUSH -> ABISSAL destrava",
               a._diff_locked(4) is False)

    a = app_with({})
    a.achieved = {"esquivador", "perfeccionista"}
    a._apply_progression("win")
    ok &= check("conquista esquivador -> EMP destrava",
               "emp" in a.save["unlocked_skills"])
    ok &= check("conquista perfeccionista -> BLINK destrava",
               "blink" in a.save["unlocked_skills"])

    a = app_with({})
    a.achieved = {"alem_limite"}
    a.sel["mode"], a.sel["boss"] = "classic", "summoner"
    a._apply_progression("win")
    ok &= check("conquista alem_limite -> boss OMEGA destrava",
               a.save["omega_unlocked"] is True)
    ok &= check("vencer o Invocador -> mutador CLAUSTROFOBIA destrava",
               "claustro" in a.save["unlocked_mutators"])

    ok &= check("tabelas de menu íntegras",
               [d[0] for d in DIFFS] == ["facil", "normal", "dificil",
                                        "expert", "abissal"]
               and any(s[0] == "shield" for s in SKILLS)
               and any(m[0] == "claustro" for m in MUTATORS)
               and any(b[0] == "omega" for b in BOSSES))

    raise SystemExit(0 if ok else 1)
