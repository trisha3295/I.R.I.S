@echo off
cd /d "%~dp0"
title I.R.I.S. - Intelligent Real-time Interface System
echo =====================================================================
echo  Launching I.R.I.S. (Intelligent Real-time Interface System) Engine
echo =====================================================================
echo.
if exist "%~dp0venv\Scripts\python.exe" (
    echo Using Virtual Environment Python...
    "%~dp0venv\Scripts\python.exe" iris_app.py
) else (
    echo Using System Python...
    python iris_app.py
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application terminated with error code %ERRORLEVEL%.
    pause
)
