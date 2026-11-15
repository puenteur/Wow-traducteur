@echo off
rem Lance WoW Traducteur sans fenetre de console
cd /d "%~dp0"
rem Lance depuis le zip sans l'avoir decompresse : Windows n'extrait que ce fichier, translator.py manque
if not exist "translator.py" (
  echo Decompresse d'abord le zip : clic droit sur le zip ^> Extraire tout, puis lance ce fichier depuis le dossier extrait.
  echo Unzip first: right-click the zip ^> Extract All, then run this file from the extracted folder.
  pause
  exit /b
)
call :find
if defined PYW goto run

rem Python absent : on propose de l'installer tout seul avec winget (outil d'installation de Windows 10 / 11)
echo Python est introuvable. WoW Traducteur en a besoin.
echo Python not found. WoW Traducteur needs it.
echo.
where winget >nul 2>&1 || goto manual
set "ANS="
set /p ANS=Installer Python automatiquement maintenant ? / Install Python automatically now? (O/N) : 
if /i "%ANS%"=="O" goto install
if /i "%ANS%"=="Y" goto install
goto manual

:install
echo.
echo Installation de Python, patiente une minute... / Installing Python, please wait a minute...
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :find
if defined PYW goto run
echo.
echo L'installation automatique n'a pas abouti. / Automatic install did not work.
goto manual

:run
start "" "%PYW%" translator.py
exit /b

:manual
echo.
echo Installe Python ici / Install Python here: https://www.python.org/downloads/windows/
echo (coche "Add python.exe to PATH" / tick "Add python.exe to PATH"), puis relance ce fichier / then run this file again.
pause
exit /b

rem Cherche pythonw (sans fenetre noire) : PATH, lanceur py, dossiers habituels (case PATH non cochee,
rem installation en administrateur), et les dossiers Python des autres comptes Windows
:find
set "PYW="
for /f "delims=" %%P in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%P"
if not defined PYW for /f "delims=" %%P in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%P"
if not defined PYW if exist "%WINDIR%\pyw.exe" set "PYW=%WINDIR%\pyw.exe"
if not defined PYW for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*" "%SystemDrive%\Python3*" "%LocalAppData%\Python\pythoncore-3*") do if not defined PYW if exist "%%D\pythonw.exe" set "PYW=%%D\pythonw.exe"
if not defined PYW for /d %%U in ("%SystemDrive%\Users\*") do for /d %%D in ("%%U\AppData\Local\Programs\Python\Python3*") do if not defined PYW if exist "%%D\pythonw.exe" set "PYW=%%D\pythonw.exe"
exit /b
