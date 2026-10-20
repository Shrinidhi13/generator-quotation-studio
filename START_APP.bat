@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto run
if exist "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" (
  "%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m venv .venv
  goto install
)
where py >nul 2>nul
if %errorlevel% equ 0 (py -3 -m venv .venv) else (python -m venv .venv)
:install
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
:run
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Could not start the app. Check that Python 3.11 or newer is installed.
echo If setup was interrupted, run .venv\Scripts\python.exe -m pip install -r requirements.txt and try again.
pause
exit /b 1
