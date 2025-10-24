@echo off
REM =============================================================================
REM Full Device Dataset Collection - Batch Script
REM =============================================================================
REM
REM This script collects a comprehensive device-specific dataset including:
REM   1. S-mode spectral data (15 min/channel = 60 min)
REM   2. S-mode afterglow characterization (~45 min)
REM   3. P-mode spectral data (15 min/channel = 60 min)
REM   4. P-mode afterglow characterization (~45 min)
REM
REM Total runtime: ~3.5 hours
REM
REM Usage:
REM   collect_full_device_dataset.bat "DEVICE_SERIAL" "SENSOR_QUALITY"
REM
REM Example:
REM   collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
REM
REM =============================================================================

setlocal enabledelayedexpansion

REM Check arguments
if "%~1"=="" (
    echo Error: Device serial number required
    echo Usage: collect_full_device_dataset.bat "DEVICE_SERIAL" "SENSOR_QUALITY"
    echo Example: collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
    exit /b 1
)

if "%~2"=="" (
    echo Error: Sensor quality required
    echo Usage: collect_full_device_dataset.bat "DEVICE_SERIAL" "SENSOR_QUALITY"
    echo Example: collect_full_device_dataset.bat "demo P4SPR 2.0" "used"
    exit /b 1
)

set DEVICE_SERIAL=%~1
set SENSOR_QUALITY=%~2
set DURATION=120
set PYTHON_EXE=.\.venv312\Scripts\python.exe

echo.
echo ========================================================================
echo  FULL DEVICE DATASET COLLECTION (PROOF OF CONCEPT)
echo ========================================================================
echo.
echo  Device Serial: %DEVICE_SERIAL%
echo  Sensor Quality: %SENSOR_QUALITY%
echo  Spectral Duration: %DURATION%s (2 min per channel)
echo.
echo  Collection Sequence:
echo    1. S-mode spectral data (~8 min)
echo    2. S-mode afterglow characterization (~11 min FAST)
echo    3. P-mode spectral data (~8 min)
echo    4. P-mode afterglow characterization (~11 min FAST)
echo.
echo  Total Estimated Time: ~40 minutes
echo.
echo ========================================================================
echo.

REM Get start time
set START_TIME=%TIME%
echo [%TIME%] Starting full device dataset collection...
echo.

REM =============================================================================
REM STEP 1: S-mode Spectral Data Collection
REM =============================================================================
echo.
echo ========================================================================
echo  STEP 1/4: S-MODE SPECTRAL DATA COLLECTION
echo ========================================================================
echo.
echo  Duration: 2 min/channel = 8 min total
echo  Rate: 4 Hz (production-matched timing)
echo  Expected spectra: ~480 per channel
echo.

%PYTHON_EXE% collect_spectral_data.py --mode S --duration %DURATION% --device-serial "%DEVICE_SERIAL%" --sensor-quality "%SENSOR_QUALITY%"

if errorlevel 1 (
    echo.
    echo ERROR: S-mode spectral collection failed!
    echo Check the log output above for details.
    pause
    exit /b 1
)

echo.
echo [%TIME%] Step 1/4 complete: S-mode spectral data collected
echo.

REM =============================================================================
REM STEP 2: S-mode Afterglow Characterization
REM =============================================================================
echo.
echo ========================================================================
echo  STEP 2/4: S-MODE AFTERGLOW CHARACTERIZATION (FAST)
echo ========================================================================
echo.
echo  Duration: ~11 minutes
echo  Channels: A, B, C, D
echo  Integration times: 10, 100 ms (fast mode)
echo  Cycles per measurement: 3
echo.

%PYTHON_EXE% led_afterglow_integration_time_model.py --mode S --fast

if errorlevel 1 (
    echo.
    echo ERROR: S-mode afterglow characterization failed!
    echo Check the log output above for details.
    pause
    exit /b 1
)

echo.
echo [%TIME%] Step 2/4 complete: S-mode afterglow characterized
echo.

REM =============================================================================
REM STEP 3: P-mode Spectral Data Collection
REM =============================================================================
echo.
echo ========================================================================
echo  STEP 3/4: P-MODE SPECTRAL DATA COLLECTION
echo ========================================================================
echo.
echo  Duration: 2 min/channel = 8 min total
echo  Rate: 4 Hz (production-matched timing)
echo  Expected spectra: ~480 per channel
echo.

%PYTHON_EXE% collect_spectral_data.py --mode P --duration %DURATION% --device-serial "%DEVICE_SERIAL%" --sensor-quality "%SENSOR_QUALITY%"

if errorlevel 1 (
    echo.
    echo ERROR: P-mode spectral collection failed!
    echo Check the log output above for details.
    pause
    exit /b 1
)

echo.
echo [%TIME%] Step 3/4 complete: P-mode spectral data collected
echo.

REM =============================================================================
REM STEP 4: P-mode Afterglow Characterization
REM =============================================================================
echo.
echo ========================================================================
echo  STEP 4/4: P-MODE AFTERGLOW CHARACTERIZATION (FAST)
echo ========================================================================
echo.
echo  Duration: ~11 minutes
echo  Channels: A, B, C, D
echo  Integration times: 10, 100 ms (fast mode)
echo  Cycles per measurement: 3
echo.

%PYTHON_EXE% led_afterglow_integration_time_model.py --mode P --fast

if errorlevel 1 (
    echo.
    echo ERROR: P-mode afterglow characterization failed!
    echo Check the log output above for details.
    pause
    exit /b 1
)

echo.
echo [%TIME%] Step 4/4 complete: P-mode afterglow characterized
echo.

REM =============================================================================
REM COMPLETION SUMMARY
REM =============================================================================
set END_TIME=%TIME%

echo.
echo ========================================================================
echo  FULL DEVICE DATASET COLLECTION COMPLETE!
echo ========================================================================
echo.
echo  Device: %DEVICE_SERIAL%
echo  Sensor Quality: %SENSOR_QUALITY%
echo.
echo  Started: %START_TIME%
echo  Finished: %END_TIME%
echo.
echo  Data collected:
echo    - S-mode spectral data (4 channels, ~480 spectra each)
echo    - S-mode afterglow models (4 channels, 2 integration times - FAST)
echo    - P-mode spectral data (4 channels, ~480 spectra each)
echo    - P-mode afterglow models (4 channels, 2 integration times - FAST)
echo.
echo  Location: spectral_training_data\%DEVICE_SERIAL%\
echo.
echo  Next steps:
echo    1. Copy afterglow data into device folder structure
echo    2. Calculate offline physics (wavelength, transmittance, sensorgram)
echo    3. Test processing pipelines
echo    4. Train ML models on production-matched data
echo.
echo ========================================================================
echo.

pause
