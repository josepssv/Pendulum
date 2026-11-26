@echo off
cd /d "%~dp0"
title Pendulum Polyphony

:: Verificar si python esta en el PATH
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] No se encontro Python en el sistema.
    echo Asegurate de que Python este instalado y marcado en el PATH de Windows.
    pause
    exit /b
)

:: Intentar lanzar de forma limpia
where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw gui.py
    exit /b
)

:: Fallback si pythonw no esta
start "" python gui.py
exit /b
