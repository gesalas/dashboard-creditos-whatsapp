@echo off
rem Actualiza data.xlsx con el ultimo reporte recibido por correo y luego revisa las alertas.
rem Es el archivo que se programa en el Programador de tareas de Windows (una vez al dia,
rem despues de la hora en que suele llegar el correo del reporte).
cd /d "%~dp0"
py actualizar_datos.py %*
if errorlevel 9009 python actualizar_datos.py %*
py alertas.py
if errorlevel 9009 python alertas.py
