@echo off
cd /d "%~dp0"
title Pendulum Polyphony (Modo Consola)
echo ============================================================
echo   Lanzando Pendulum Polyphony con consola de depuracion...
echo ============================================================
python main.py
if %errorlevel% neq 0 (
    echo.
    echo La aplicacion se ha cerrado con error (%errorlevel%).
    pause
)
