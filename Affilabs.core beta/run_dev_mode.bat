@echo off
REM Launch ezControl in Developer Mode
REM This enables additional configuration prompts and debugging features

echo Starting ezControl in Developer Mode...
echo.

REM Activate virtual environment
call ..\.venv312\Scripts\Activate.ps1

REM Set dev mode environment variable
set AFFILABS_DEV=1

REM Run the application
python main_simplified.py

pause
