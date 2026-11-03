@echo off
rem Ejecuta el script de alertas desde la carpeta del repositorio.
rem Es el archivo que se programa en el Programador de tareas de Windows.
cd /d "%~dp0"
py alertas.py %*
if errorlevel 9009 python alertas.py %*
