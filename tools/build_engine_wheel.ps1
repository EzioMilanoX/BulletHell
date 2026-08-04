<#
.SYNOPSIS
    Builda o wheel da OuroborosEngine (repo-irmao) e deixa em wheels/,
    pinado a um commit conhecido.

.DESCRIPTION
    O port ECS (main_ecs.py) depende da OuroborosEngine, que nao esta no
    PyPI. Em dev isso e resolvido por um sys.path.insert direto pro
    repo-irmao (bullethell/__init__.py) ou por um "pip install -e"
    manual -- nenhum dos dois funciona bem com o PyInstaller: a analise
    estatica dele nao executa o sys.path.insert (so roda no processo ja
    vivo), e o editable install moderno do setuptools usa um finder de
    import (nao uma pasta de verdade), que o modulegraph do PyInstaller
    as vezes nao enxerga.

    A solucao: buildar um wheel de verdade (arquivos reais, sem finder)
    a partir de um commit conhecido do repo-irmao, e instalar ele
    NAO-editavel num venv limpo antes de rodar o PyInstaller
    (tools/build_exes.ps1 faz isso). O wheel gerado fica versionado em
    wheels/ pra o build ficar reproduzivel mesmo sem o repo-irmao no
    disco.

.PARAMETER EngineRoot
    Caminho pro repo da OuroborosEngine. Default: ../OuroborosEngine
    (repo-irmao, mesma convencao de bullethell/__init__.py).
#>
param(
    [string]$EngineRoot = (Join-Path $PSScriptRoot "..\..\OuroborosEngine")
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$wheelsDir = Join-Path $repoRoot "wheels"

$EngineRoot = (Resolve-Path $EngineRoot).Path
Write-Host "Engine: $EngineRoot"

Push-Location $EngineRoot
try {
    $dirty = git status --porcelain
    if ($dirty) {
        Write-Warning "OuroborosEngine tem mudancas nao commitadas -- o wheel vai refletir esse estado sujo, nao um commit rastreavel. Prefira commitar antes de buildar pra distribuicao."
        $commit = "dirty"
    } else {
        $commit = (git rev-parse --short HEAD).Trim()
    }

    New-Item -ItemType Directory -Force -Path $wheelsDir | Out-Null
    Get-ChildItem "$wheelsDir\ouroboros_engine-*.whl" -ErrorAction SilentlyContinue |
        Remove-Item -Force

    python -m pip wheel . --no-deps -w $wheelsDir
    if ($LASTEXITCODE -ne 0) { throw "pip wheel falhou (exit $LASTEXITCODE)" }

    $commit | Set-Content -Path (Join-Path $wheelsDir "ENGINE_COMMIT.txt") -NoNewline
    Write-Host "OK -- wheel gerado a partir do commit '$commit'. Ver wheels/."
}
finally {
    Pop-Location
}
