@echo off
REM Build V2.1 firmware with rankbatch command
echo ====================================
echo Building V2.1 Firmware
echo ====================================
echo.

REM Check if Git Bash exists
if exist "C:\Program Files\Git\bin\bash.exe" (
    set GITBASH="C:\Program Files\Git\bin\bash.exe"
) else if exist "C:\Program Files (x86)\Git\bin\bash.exe" (
    set GITBASH="C:\Program Files (x86)\Git\bin\bash.exe"
) else (
    echo Git Bash not found!
    echo Please install Git for Windows from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Using Git Bash: %GITBASH%
echo.

REM Build using Git Bash (clean and cmake only)
echo Cleaning build directory...
%GITBASH% -c "cd '/c/Users/lucia/OneDrive/Desktop/ezControl 2.0/Affilabs.core/pico-p4spr-firmware/build' && rm -rf *"

echo Running CMake...
cd "C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\build"
cmake -G "Unix Makefiles" ..

echo Building with make...
%GITBASH% -c "cd '/c/Users/lucia/OneDrive/Desktop/ezControl 2.0/Affilabs.core/pico-p4spr-firmware/build' && /c/Program\ Files\ \(x86\)/GnuWin32/bin/make.exe -j4"

if errorlevel 1 (
    echo.
    echo Build FAILED!
    pause
    exit /b 1
)

echo.
echo ====================================
echo Build SUCCESS! Converting to UF2...
echo ====================================
echo.

cd "C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI"
python bin_to_uf2.py "..\pico-p4spr-firmware\build\affinite_p4spr.bin" "firmware_v2.1\affinite_p4spr_v2.1.uf2"

if errorlevel 1 (
    echo.
    echo Conversion FAILED!
    pause
    exit /b 1
)

echo.
echo ====================================
echo SUCCESS! Firmware ready!
echo ====================================
echo.
echo Firmware location: firmware_v2.1\affinite_p4spr_v2.1.uf2
echo.
echo To flash:
echo 1. Hold BOOTSEL button on Pico
echo 2. Connect USB (keep holding)
echo 3. Release BOOTSEL when Pico drive appears
echo 4. Copy firmware_v2.1\affinite_p4spr_v2.1.uf2 to the Pico drive
echo.
pause
