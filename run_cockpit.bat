@echo off
echo ===================================================
echo Starting Indian Market Decision & Screening Cockpit
echo ===================================================
cd /d "%~dp0"
python -m streamlit run app.py
pause
