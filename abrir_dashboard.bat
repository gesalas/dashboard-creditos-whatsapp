@echo off
REM Abre el dashboard en modo produccion (pide iniciar sesion).
cd /d "%~dp0"
py -m streamlit run app.py
if errorlevel 9009 python -m streamlit run app.py
pause
