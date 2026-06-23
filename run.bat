@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   老旧小区适老化设施维护优先级评估系统
echo   启动中...
echo ============================================
echo.
echo   浏览器打开后请访问: http://127.0.0.1:5000
echo   按 Ctrl+C 可停止服务器
echo.
python app.py
pause
