@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"

echo Building EXE with uv...

uv run --locked --no-dev --group build pyinstaller ^
    --noconsole ^
    --onefile ^
    --clean ^
    --noconfirm ^
    --specpath "build\spec" ^
    --workpath "build\pyinstaller" ^
    --distpath "dist" ^
    --name "从旧版DC整合包迁移数据" ^
    --icon "%ROOT%assets\icon.ico" ^
    --add-data "%ROOT%data_migration_rules.conf;." ^
    --add-data "%ROOT%assets\icon.ico;assets" ^
    "main.py"

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo Build complete. The executable is in the 'dist' folder.
pause
