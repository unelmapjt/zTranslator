@echo off
cd /d "%~dp0"
title zTranzlator - EXE Build Tool
echo ============================================================
echo   zTranzlator Standalone EXE Builder
echo   Project Zomboid Build 42 Translation Tool
echo ============================================================
echo.
echo [1/3] ビルド用ライブラリを確認中...
pip install pyinstaller pillow customtkinter darkdetect
echo.
echo [2/3] zTranzlator.exe をビルド中 (Modern Single-folder Portable)...
pyinstaller --noconfirm --onedir --windowed ^
    --name "zTranzlator" ^
    --add-data "vanilla_dict.json;." ^
    --add-data "SPECIFICATION.md;." ^
    --collect-all customtkinter ^
    app_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [Error] ビルドに失敗しました。
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo [3/3] ビルド完了！
echo 出力フォルダ: dist\zTranzlator\zTranzlator.exe
echo ============================================================
pause
