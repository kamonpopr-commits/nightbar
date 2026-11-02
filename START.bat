@echo off
setlocal
set "NIGHTBAR_PORT=8765"
cd /d "%~dp0"
set "NIGHTBAR_PY=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if exist "%NIGHTBAR_PY%" goto bundled
set "NIGHTBAR_PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if exist "%NIGHTBAR_PY%" goto bundled
set "NIGHTBAR_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%NIGHTBAR_PY%" goto bundled
py -3 --version >nul 2>&1
if not errorlevel 1 goto launcher
python --version >nul 2>&1
if not errorlevel 1 goto standard
echo Python 3.11 or newer was not found. Please install Python and try again.
pause
exit /b 1
:bundled
"%NIGHTBAR_PY%" "%~dp0app.py" --open
goto finished
:launcher
py -3 "%~dp0app.py" --open
goto finished
:standard
python "%~dp0app.py" --open
:finished
if errorlevel 1 pause
endlocal
