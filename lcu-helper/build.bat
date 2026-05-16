@echo off
echo Building LoL Match Coach Helper...
pip install pyinstaller httpx urllib3 --quiet
pyinstaller --onefile --name "LoL-Match-Coach-Helper" --icon=NONE lcu_helper.py
echo.
echo Done! The .exe is in the "dist" folder.
pause
