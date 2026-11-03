@echo off
rem Actualiza data.xlsx con el ultimo reporte recibido por correo y luego revisa las alertas.
rem Es el archivo que se programa en el Programador de tareas de Windows (una vez al dia,
rem despues de la hora en que suele llegar el correo del reporte).
cd /d "%~dp0"
rem 1) Trae los cambios del repositorio (codigo, creditos, unidades) para trabajar con lo ultimo.
git pull --rebase --autostash
rem 2) Actualiza data.xlsx desde el correo (y lo sube a GitHub si esta activado).
py actualizar_datos.py %*
if errorlevel 9009 python actualizar_datos.py %*
rem 3) Revisa umbrales y envia alertas y resumen semanal.
py alertas.py
if errorlevel 9009 python alertas.py
