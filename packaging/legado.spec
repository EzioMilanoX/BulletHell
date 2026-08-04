# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec do jogo LEGADO (main.py, sem dependência da engine).

Uso (de dentro de .build_venv, ver tools/build_exes.ps1):
    pyinstaller packaging/legado.spec --noconfirm

balance.json/waves.json NÃO entram no bundle: main.py os abre por caminho
relativo ("balance.json"), resolvido contra o cwd do processo — não
contra o `__file__` do script nem contra sys._MEIPASS. Em --onefile isso
significa que embutir esses JSONs no bundle não ajudaria (ficariam na
pasta temp de extração, não no cwd). O build script copia os dois
arquivos para dist/ ao lado do .exe; ao clicar duas vezes no .exe o
Windows já usa a pasta do próprio .exe como cwd.
"""
from pathlib import Path

_root = Path(SPECPATH).parent

a = Analysis(
    [str(_root / "main.py")],
    pathex=[str(_root)],
    binaries=[],
    datas=[],
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
    name="BulletHellLegado",
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
