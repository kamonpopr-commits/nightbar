@echo off
setlocal
cd /d "%~dp0"
set "NIGHTBAR_PY=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if exist "%NIGHTBAR_PY%" goto run
set "NIGHTBAR_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%NIGHTBAR_PY%" goto run
py -3 tools\recover_manager.py
if errorlevel 1 pause
exit /b
:run
"%NIGHTBAR_PY%" tools\recover_manager.py
if errorlevel 1 pause
endlocal
