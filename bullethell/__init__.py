"""BulletHell sobre a OuroborosEngine.

Importar este pacote garante que a engine (repositório irmão
`PersonalProjects/OuroborosEngine`) esteja no sys.path — sem exigir
`pip install -e` durante o desenvolvimento.
"""
import sys
from pathlib import Path

# versão do jogo — fonte única: título da janela, CHANGELOG.md (seção
# "## vX.Y.Z") e a tag de release (release.yml confere via
# tools/release_notes.py que a tag empurrada bate com isto)
__version__ = "2.1.0"

_ENGINE_ROOT = Path(__file__).resolve().parents[2] / "OuroborosEngine"
if _ENGINE_ROOT.is_dir() and str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))
