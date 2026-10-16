@echo off
REM Double-click to start the Hydrogel Diagram Maker (Windows).
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
python -m streamlit run app.py
pause
