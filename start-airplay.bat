@echo off
cd /d "%~dp0"
where python >nul 2>&1 && goto :run
py -3 -u airplay.py || pause
exit /b 0

:run
python -u airplay.py || pause
