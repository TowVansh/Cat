@echo off
rem Open Miso's home. If she is already out on the desktop this starts a
rem second copy, so close the first one before using this.
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" pet.py --home
