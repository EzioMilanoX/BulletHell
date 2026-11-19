"""conftest.py — setup headless + fixtures compartilhadas da suíte pytest.

Tudo roda sem janela nem áudio: os testes do port ECS usam os backends
null da engine (NullRenderer/NullInputProvider) e, onde precisam de um
buffer de pixels de verdade, o PygameRenderer sob o driver SDL "dummy".
"""
import os
import sys
from pathlib import Path

# precisa vir ANTES do primeiro `import pygame` (direto ou via engine)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# raiz do repo importável (bullethell/, main_ecs.py) a partir de tests/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import bullethell  # noqa: E402,F401 — garante a engine no sys.path


@pytest.fixture(scope="session")
def data():
    """GameData carregado uma vez por sessão (data/*.json são só leitura
    nos testes — quem precisa recarregar usa `load_all()` direto)."""
    from bullethell.loaders import load_all
    return load_all()
