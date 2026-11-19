"""Confere a tag de release e extrai as notas dela do CHANGELOG.md.

Uso (release.yml, ao empurrar uma tag):
    python tools/release_notes.py v2.0.0 release_notes.md

Falha (exit 1) se a tag não bater com `bullethell.__version__` ou se o
CHANGELOG.md não tiver a seção "## vX.Y.Z" correspondente — melhor a
Release não sair do que sair com a versão errada no título da janela ou
sem notas. Lê os arquivos como texto (não importa o pacote `bullethell`,
que mexeria no sys.path).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def versao_do_jogo(init_text: str) -> str:
    m = re.search(r'^__version__ = "([^"]+)"', init_text, re.MULTILINE)
    if not m:
        raise ValueError("__version__ não encontrado em bullethell/__init__.py")
    return m.group(1)


def secao_do_changelog(changelog: str, versao: str) -> str:
    """Corpo da seção "## v<versao>" até a próxima "## " (sem o título)."""
    m = re.search(rf"^## v{re.escape(versao)}[^\n]*\n(.*?)(?=^## |\Z)",
                  changelog, re.MULTILINE | re.DOTALL)
    if not m or not m.group(1).strip():
        raise ValueError(f"CHANGELOG.md sem seção '## v{versao}'")
    return m.group(1).strip() + "\n"


def main(argv: list) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    tag, saida = argv[1], argv[2]
    versao = versao_do_jogo((ROOT / "bullethell" / "__init__.py")
                            .read_text(encoding="utf-8"))
    if tag != f"v{versao}":
        print(f"tag {tag} != v{versao} (bullethell/__init__.py)")
        return 1
    try:
        notas = secao_do_changelog((ROOT / "CHANGELOG.md")
                                   .read_text(encoding="utf-8"), versao)
    except ValueError as e:
        print(e)
        return 1
    Path(saida).write_text(notas, encoding="utf-8")
    print(f"notas da {tag}: {len(notas.splitlines())} linhas -> {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
