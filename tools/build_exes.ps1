<#
.SYNOPSIS
    Builda BulletHellLegado.exe e BulletHellECS.exe standalone (Windows).

.DESCRIPTION
    Cria um venv LIMPO em .build_venv (nunca reusa o venv de dev -- e
    exatamente o venv de dev que tem o problema de editable
    install/sys.path hack que confunde o PyInstaller, ver
    requirements-build.txt e packaging/ecs.spec), instala as
    dependencias pinadas + o wheel local da engine, e roda o
    PyInstaller pros dois specs em packaging/.

.PARAMETER SkipWheelRebuild
    Nao regera wheels/ouroboros_engine-*.whl -- usa o que ja esta
    versionado no repo. Use isto se o repo-irmao OuroborosEngine nao
    estiver presente no disco (o wheel commitado ja e suficiente).
#>
param(
    [switch]$SkipWheelRebuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not $SkipWheelRebuild) {
    $engineRoot = Join-Path $repoRoot "..\OuroborosEngine"
    if (Test-Path $engineRoot) {
        Write-Host "== Rebuildando wheel da engine =="
        & (Join-Path $PSScriptRoot "build_engine_wheel.ps1")
    } else {
        Write-Host "Repo-irmao OuroborosEngine nao encontrado em $engineRoot -- usando o wheel ja versionado em wheels/."
    }
}

$wheel = Get-ChildItem "$repoRoot\wheels\ouroboros_engine-*.whl" -ErrorAction SilentlyContinue |
    Select-Object -First 1
if (-not $wheel) {
    throw "Nenhum wheel em wheels/ -- rode tools\build_engine_wheel.ps1 primeiro (precisa do repo-irmao OuroborosEngine)."
}
Write-Host "Wheel: $($wheel.Name)"

Write-Host "== Recriando .build_venv =="
$venvDir = Join-Path $repoRoot ".build_venv"
if (Test-Path $venvDir) { Remove-Item -Recurse -Force $venvDir }
python -m venv $venvDir
if ($LASTEXITCODE -ne 0) { throw "venv falhou" }

$venvPy = Join-Path $venvDir "Scripts\python.exe"
& $venvPy -m pip install --quiet --upgrade pip
& $venvPy -m pip install --quiet -r (Join-Path $repoRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "pip install falhou (exit $LASTEXITCODE)" }

Write-Host "== PyInstaller: legado =="
& $venvPy -m PyInstaller (Join-Path $repoRoot "packaging\legado.spec") `
    --noconfirm --distpath (Join-Path $repoRoot "dist") `
    --workpath (Join-Path $repoRoot "build_pyinstaller")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (legado) falhou" }

Write-Host "== PyInstaller: ECS =="
& $venvPy -m PyInstaller (Join-Path $repoRoot "packaging\ecs.spec") `
    --noconfirm --distpath (Join-Path $repoRoot "dist") `
    --workpath (Join-Path $repoRoot "build_pyinstaller")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (ECS) falhou" }

# balance.json/waves.json: main.py os abre por caminho relativo ao cwd,
# nao da pra embutir no bundle onefile (ver packaging/legado.spec) --
# tem que ficar soltos ao lado do .exe.
Copy-Item (Join-Path $repoRoot "balance.json") (Join-Path $repoRoot "dist") -Force
Copy-Item (Join-Path $repoRoot "waves.json") (Join-Path $repoRoot "dist") -Force

Write-Host ""
Write-Host "OK -- dist\BulletHellLegado.exe + dist\BulletHellECS.exe"
Write-Host "(dist\balance.json e dist\waves.json precisam continuar ao lado do Legado.exe)"
