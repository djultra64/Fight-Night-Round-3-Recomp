@echo off
rem Work: djultra64.
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0install.py" %*
goto finished
:use_python
python "%~dp0install.py" %*
:finished
if errorlevel 1 (
  echo Installation did not finish. Install Python 3 if it is missing, then try again.
  pause
  exit /b 1
)
pause
