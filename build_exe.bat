@echo off
cd /d "%~dp0"
python -m pip install pyinstaller
python -m PyInstaller --noconsole --onefile --name DigiPet --add-data "sprites;sprites" digipet.py
echo.
echo Done: dist\DigiPet.exe
pause
