@echo off
cd /d "%~dp0"
where python >nul 2>&1 && goto :run
py -3 -m pip install -q -r requirements.txt || goto :fail
py -3 -u app.py || pause
exit /b 0

:run
python -m pip install -q -r requirements.txt || goto :fail
python -u app.py || pause
exit /b 0

:fail
echo Failed to install Python dependencies.
pause
exit /b 1
