@echo off
setlocal
cd /d "%~dp0"

REM Use python.exe (pythonw.exe is broken on this system).
REM start /min keeps the console out of the way.
set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not exist "%PY%" set "PY=python.exe"

start "SkipMan" /min "%PY%" "%~dp0skipman.pyw"
exit /b
