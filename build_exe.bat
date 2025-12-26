@echo off
echo Installing requirements...
python -m pip install -r requirements.txt

set "ROOT=%~dp0"

echo Building EXE...
if not exist "spec" mkdir "spec"

pyinstaller --noconsole --onefile --clean --noconfirm --specpath "spec" --name "dc_data_migration" --icon "%ROOT%assets\icon.ico" --add-data "%ROOT%data_migration_rules.conf;." --add-data "%ROOT%assets\icon.ico;assets" main.py

echo Build complete. The executable is in the 'dist' folder.
pause
