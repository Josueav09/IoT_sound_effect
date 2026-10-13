@echo off
rem Arranca la botonera en segundo plano (la primera vez abre el asistente).
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "%~dp0teclado_sonidos.py" %*
) else (
    start "" pythonw "%~dp0teclado_sonidos.py" %*
)
