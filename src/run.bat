@echo off
REM AffiLabs.core Beta Launcher
REM This launches the simplified main application

echo.
echo ========================================
echo  AffiLabs.core Beta
echo  Simplified Application Launcher
echo ========================================
echo.

REM Activate virtual environment if it exists
if exist "..\\.venv312\\Scripts\\activate.bat" (
    echo Activating Python virtual environment...
    call "..\\.venv312\\Scripts\\activate.bat"
)

REM Launch application
echo Starting AffiLabs.core...
python main_simplified.py

echo.
echo Application closed.
pause
