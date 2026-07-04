@echo off
:: ---------------------------------------------------------------------------
:: build.bat — compila com g++ (MinGW) + Raylib (Windows)
:: Ajuste RAYLIB_PATH para onde você extraiu o Raylib para Windows/MinGW.
:: Download: https://github.com/raysan5/raylib/releases
::   -> raylib-5.x_win64_mingw-w64.zip
:: ---------------------------------------------------------------------------

set RAYLIB_PATH=C:\raylib\raylib

g++ -std=c++17 -O2 -Wall ^
    -I"%RAYLIB_PATH%\src" ^
    src\main.cpp ^
    -L"%RAYLIB_PATH%\src" ^
    -lraylib -lopengl32 -lgdi32 -lwinmm ^
    -o bullet_hell.exe

if %errorlevel% == 0 (
    echo.
    echo  Build OK ^>^> bullet_hell.exe
    echo.
) else (
    echo.
    echo  ERRO no build. Verifique RAYLIB_PATH e a instalacao do MinGW.
    echo.
)
