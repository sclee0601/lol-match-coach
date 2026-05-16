@echo off
echo Building LoL Match Coach Helper...
pip install pyinstaller httpx urllib3 --quiet
echo Running PyInstaller...
python -m PyInstaller --onefile --noconsole --name "LoL-Match-Coach-Helper" lcu_helper.py
echo.
echo Done! The .exe is in the "dist" folder.
pause
