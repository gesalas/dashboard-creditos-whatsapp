@echo off
REM Abre el dashboard en modo pruebas: sin inicio de sesion, con permisos del Equipo CRM.
REM Solo funciona en este computador; en el enlace publicado no existe.
cd /d "%~dp0"
py -m streamlit run app.py -- --pruebas
if errorlevel 9009 python -m streamlit run app.py -- --pruebas
pause
