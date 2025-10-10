@echo off
REM Run the Affinite application with Python 3.12 virtual environment
REM This ensures we always use the correct Python version

echo Starting Affinite SPR System with Python 3.12...
echo ================================================

REM Set environment variables
set PYTHONPATH=.

REM Run with virtual environment Python
".\.venv\Scripts\python.exe" main\main.py

echo.
echo Application closed.
pause