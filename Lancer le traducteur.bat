@echo off
rem Lance WoW Traducteur sans fenetre de console
cd /d "%~dp0"
where pyw >nul 2>&1 && (start "" pyw translator.py & exit /b)
where pythonw >nul 2>&1 && (start "" pythonw translator.py & exit /b)
echo Python est introuvable / Python not found. Installe-le / Install it: https://www.python.org/downloads/windows/
pause
