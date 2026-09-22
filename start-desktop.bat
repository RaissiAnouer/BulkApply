@echo off
setlocal
cd /d "%~dp0"
echo ========================================================
echo   Launching AutoApply Desktop Application...
echo ========================================================
if exist "backend\venv\Scripts\python.exe" (
    backend\venv\Scripts\python.exe desktop_app.py
) else (
    python desktop_app.py
)
