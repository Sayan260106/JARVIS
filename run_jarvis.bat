@echo off
setlocal enabledelayedexpansion

title J A R V I S — Autonomous AI Assistant
cd /d "%~dp0"

echo ====================================================================
echo  J A R V I S — Initializing System Environment
echo ====================================================================

:: Check Python virtual environment
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: Run JARVIS
"%PYTHON_EXE%" main.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [JARVIS Exited with code %ERRORLEVEL%]
    pause
)
