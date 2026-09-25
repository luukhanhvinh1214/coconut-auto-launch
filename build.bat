@echo off
cd /d "%~dp0"
call npm --prefix frontend run build || exit /b 1
.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --icon NONE --name CoconutAutoLaunch ^
  --add-data "%~dp0frontend\dist;frontend\dist" ^
  --distpath "%~dp0." --workpath "%~dp0build" --specpath "%~dp0build" ^
  app.py || exit /b 1
