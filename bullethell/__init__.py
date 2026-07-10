"""BulletHell sobre a OuroborosEngine.

Importar este pacote garante que a engine (repositório irmão
`PersonalProjects/OuroborosEngine`) esteja no sys.path — sem exigir
`pip install -e` durante o desenvolvimento.
"""
import sys
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[2] / "OuroborosEngine"
if _ENGINE_ROOT.is_dir() and str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))
