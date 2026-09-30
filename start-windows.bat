@echo off
cd /d "%~dp0"
echo CapitalForge opens at http://127.0.0.1:8787/app
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 app.py --open-browser
) else (
  python app.py --open-browser
)
pause
