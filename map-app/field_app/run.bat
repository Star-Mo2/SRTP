@echo off
REM 本地运行 point-map field app
cd /d "%~dp0"
set PORT=5001
set FLASK_DEBUG=1
python app.py
