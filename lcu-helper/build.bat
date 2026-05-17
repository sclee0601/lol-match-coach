@echo off
echo Building LoL Match Coach Helper...

SET SHARED_FOLDER=C:\Users\seung\OneDrive\LoLCoach

echo Running PyInstaller...
python -m PyInstaller --onefile --noconsole --name "LoL-Match-Coach-Helper" --distpath "%SHARED_FOLDER%" --add-data "matchup_data.py;." lcu_helper.py
echo.
echo Done! The .exe is in: %SHARED_FOLDER%
pause
