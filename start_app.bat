@echo off
REM Double-click this file to start the Hydrogel Diagram Maker (Windows).
title Hydrogel Diagram Maker
cd /d "%~dp0"

REM Find Python: the "py" launcher first, then "python".
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto nopython

echo Getting everything ready. The first time this takes a few minutes...
REM Everything is installed into a private .venv folder next to this file.
if not exist ".venv\Scripts\python.exe" (
    %PY% -m venv .venv
    if errorlevel 1 (
        echo Could not create the .venv folder - see the message above.
        pause
        exit /b 1
    )
)
set "PY=.venv\Scripts\python.exe"
%PY% -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo Something went wrong while installing - see the message above.
    pause
    exit /b 1
)
echo.
echo Starting. Your web browser will open in a moment.
echo KEEP THIS WINDOW OPEN while you use the app. Close it when you are done.
echo.
%PY% -m streamlit run app.py
pause
exit /b 0

:nopython
echo.
echo Python 3.10 or newer is needed but was not found.
echo  1. Download it from https://www.python.org/downloads/
echo  2. While installing, tick "Add python.exe to PATH"
echo  3. Double-click this file again.
echo.
pause
exit /b 1
