@echo off
:: run.bat - abre o jogo (port ECS, main_ecs.py) a partir do codigo-fonte.
:: Argumentos sao repassados (ex.: run.bat --play --boss decalogue).
:: Usa o "python" do PATH; sem ele, cai no launcher "py" do Windows.
:: Precisa de requirements.txt instalado e do repo-irmao OuroborosEngine
:: (ou do wheel em wheels\) - ver README.md.
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python main_ecs.py %*
) else (
    py -3 main_ecs.py %*
)
exit /b %errorlevel%
