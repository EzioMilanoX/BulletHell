"""Versão do jogo coerente entre bullethell/__init__.py, CHANGELOG.md e o
script que o release.yml usa pra conferir a tag e extrair as notas."""
import importlib.util
from pathlib import Path

import pytest

import bullethell

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def release_notes():
    spec = importlib.util.spec_from_file_location(
        "release_notes", ROOT / "tools" / "release_notes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_versao_e_semver():
    partes = bullethell.__version__.split(".")
    assert len(partes) == 3 and all(p.isdigit() for p in partes)


def test_script_le_a_mesma_versao_do_pacote(release_notes):
    texto = (ROOT / "bullethell" / "__init__.py").read_text(encoding="utf-8")
    assert release_notes.versao_do_jogo(texto) == bullethell.__version__


def test_changelog_tem_secao_da_versao_atual(release_notes):
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    notas = release_notes.secao_do_changelog(changelog, bullethell.__version__)
    assert notas.strip()
    assert "## v" not in notas, "a seção para antes da próxima versão"


def test_secao_inexistente_falha(release_notes):
    with pytest.raises(ValueError):
        release_notes.secao_do_changelog("# Changelog\n\n## v1.0.0\n\nx\n", "9.9.9")


def test_main_recusa_tag_errada(release_notes, tmp_path):
    saida = tmp_path / "notas.md"
    assert release_notes.main(["x", "v0.0.1", str(saida)]) == 1
    assert not saida.exists()
    tag = f"v{bullethell.__version__}"
    assert release_notes.main(["x", tag, str(saida)]) == 0
    assert saida.read_text(encoding="utf-8").strip()
