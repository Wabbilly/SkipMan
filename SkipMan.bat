@echo off
REM == SkipMan for Windows -- double-click to run ==========================
REM First run sets up SkipMan's own Python packages (takes a minute).
REM After that, SkipMan updates itself from GitHub every time it starts.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto run

echo // SKIPMAN first-time setup...
set "PY="
for %%V in (313 312 311) do (
  if not defined PY if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" set PY="%LocalAppData%\Programs\Python\Python%%V\python.exe"
)
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY set "PY=python"

%PY% -m venv .venv || (echo Python 3.11+ is needed: https://www.python.org/downloads/ & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (echo Package install failed. & pause & exit /b 1)

:run
REM python.exe (not pythonw) -- pythonw is unreliable on some setups.
start "SkipMan" /min ".venv\Scripts\python.exe" "%~dp0main.py" %*
exit /b
