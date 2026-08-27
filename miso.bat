@echo off
rem Let Miso out onto the desktop.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" pet.py %*
