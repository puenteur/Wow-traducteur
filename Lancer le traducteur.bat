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
where pyw >nul 2>&1 && (start "" pyw translator.py & exit /b)
where pythonw >nul 2>&1 && (start "" pythonw translator.py & exit /b)
if exist "%WINDIR%\pyw.exe" (start "" "%WINDIR%\pyw.exe" translator.py & exit /b)
rem Python installe mais pas dans le PATH (case "Add python.exe to PATH" non cochee, ou installe en administrateur) : dossiers habituels
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%ProgramFiles(x86)%\Python3*" "%SystemDrive%\Python3*" "%LocalAppData%\Python\pythoncore-3*") do if exist "%%D\pythonw.exe" (start "" "%%D\pythonw.exe" translator.py & exit /b)
rem installe depuis un autre compte Windows (ex. compte administrateur)
for /d %%U in ("%SystemDrive%\Users\*") do for /d %%D in ("%%U\AppData\Local\Programs\Python\Python3*") do if exist "%%D\pythonw.exe" (start "" "%%D\pythonw.exe" translator.py & exit /b)
echo Python est introuvable / Python not found. Installe-le / Install it: https://www.python.org/downloads/windows/
echo (coche "Add python.exe to PATH" / tick "Add python.exe to PATH")
pause
