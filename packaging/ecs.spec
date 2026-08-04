# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec do port ECS (main_ecs.py, sobre a OuroborosEngine).

Uso (de dentro de .build_venv, ver tools/build_exes.ps1):
    pyinstaller packaging/ecs.spec --noconfirm

A engine deve estar instalada NO INTERPRETADOR QUE RODA O PYINSTALLER —
via `pip install wheels/ouroboros_engine-*.whl` num venv limpo (ver
tools/build_engine_wheel.ps1 + requirements-build.txt). Rodar isto com
o Python de desenvolvimento (que só vê a engine via editable install
ou via o sys.path.insert de bullethell/__init__.py) NÃO é suportado —
pip install -e usa um finder de import que o modulegraph do PyInstaller
não enxerga como uma pasta normal, e o pacote pode ficar de fora do
bundle silenciosamente.

`pathex` abaixo aponta pro repo-irmão OuroborosEngine como reforço
("belt-and-suspenders"): se por algum motivo o pacote não estiver
instalado no venv de build mas o código-fonte do repo-irmão existir no
disco, o PyInstaller ainda o encontra por busca direta em disco (uma
pasta de verdade, sem o finder de editable install no caminho).
"""
from pathlib import Path

_root = Path(SPECPATH).parent
_engine_root = _root.parent / "OuroborosEngine"
_pathex = [str(_root)]
if _engine_root.is_dir():
    _pathex.append(str(_engine_root))

a = Analysis(
    [str(_root / "main_ecs.py")],
    pathex=_pathex,
    binaries=[],
    datas=[
        (str(_root / "bullethell" / "data"), "bullethell/data"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BulletHellECS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
