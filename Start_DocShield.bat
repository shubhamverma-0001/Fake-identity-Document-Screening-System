@echo off
title DocShield AI Launcher
color 0A
echo ============================================================
echo   DocShield AI -- Document Forensics System Launcher
echo ============================================================
echo.
echo Starting server and opening browser...
echo.

cd /d "%~dp0"
python run_app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error: Could not run python script. Please ensure Python is installed.
    pause
)
