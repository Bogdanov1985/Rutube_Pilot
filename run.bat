@echo off
chcp 65001 >nul
title RuTube Viewer Pro
color 0A

echo ============================================
echo     RuTube Viewer Pro - Запускатель
echo ============================================
echo.

REM Проверяем наличие Python
REM python --V

REM pip install -r requirements.txt

python Script\rutube_viewer_cycles.py --file videos.txt  --no-gui --cycles 0 --time 310 --delay-between-cycles 20
pause