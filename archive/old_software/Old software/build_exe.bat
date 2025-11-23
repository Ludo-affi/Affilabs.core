@echo off
REM Build ezControl executable using PyInstaller
REM This script packages the Old software into a standalone Windows executable

echo ========================================
echo ezControl-AI Build Script
echo ========================================
echo.

REM Check if we're in the correct directory
if not exist "main\main.py" (
    echo ERROR: main\main.py not found!
    echo Please run this script from the "Old software" directory
    pause
    exit /b 1
)

echo Step 1: Installing build dependencies...
echo ----------------------------------------
..\. venv312\Scripts\python.exe -m pip install --upgrade pip
..\. venv312\Scripts\python.exe -m pip install pyinstaller
..\.venv312\Scripts\python.exe -m pip install pyinstaller pillow

echo.
echo Step 2: Installing application dependencies...
echo -----------------------------------------------
..\.venv312\Scripts\python.exe -m pip install pyqtgraph pyserial PySide6 scipy numpy

echo.
echo Step 3: Attempting to install hardware controller packages...
echo -------------------------------------------------------------
echo Note: These may fail if not available, but build will continue
..\.venv312\Scripts\python.exe -m pip install pump-controller oceandirect ftd2xx 2>nul

echo.
echo Step 4: Cleaning previous build...
echo -----------------------------------
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo.
echo Step 5: Building executable with PyInstaller...
echo -----------------------------------------------
..\.venv312\Scripts\pyinstaller.exe main.spec

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo.
if exist "dist\ezControl v3.4\ezControl.exe" (
    echo SUCCESS: Executable created at: dist\ezControl v3.4\ezControl.exe
    echo.
    echo You can now copy the entire "dist\ezControl v3.4" folder to any Windows PC
    echo and run ezControl.exe to start the application.
) else (
    echo ERROR: Build failed! Check the output above for errors.
)
echo.
pause
