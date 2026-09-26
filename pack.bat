@echo off
chcp 65001 >nul
cd /d "%~dp0"

python3 -m PyInstaller --onefile --windowed --icon=chess.ico --name 象棋打谱 xiangqi2.py

echo.
echo ========================================
echo 打包完成，成品在 dist\象棋打谱.exe
echo ========================================
pause