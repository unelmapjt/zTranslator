@echo off
cd /d "%~dp0"
title zTranzlator
echo [zTranzlator] Starting application...
python app_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] Application terminated with code %ERRORLEVEL%.
    pause
)
