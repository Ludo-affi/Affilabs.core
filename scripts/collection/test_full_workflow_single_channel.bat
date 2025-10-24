@echo off
REM ========================================================================
REM FULL WORKFLOW TEST - SINGLE CHANNEL (A)
REM ========================================================================
REM
REM This is a test run of the complete workflow using only Channel A
REM to validate all steps work correctly before running all 4 channels.
REM
REM Estimated time: ~10 minutes
REM   - S-mode spectral (2 min, Channel A only)
REM   - S-mode afterglow (fast: ~3 min, Channel A only)
REM   - P-mode spectral (2 min, Channel A only)
REM   - P-mode afterglow (fast: ~3 min, Channel A only)
REM
REM ========================================================================

setlocal EnableDelayedExpansion

REM Get parameters
set DEVICE_SERIAL=%~1
set SENSOR_QUALITY=%~2

REM Validate inputs
if "%DEVICE_SERIAL%"=="" (
    echo ERROR: Device serial number required
    echo Usage: test_full_workflow_single_channel.bat "device_serial" "sensor_quality"
    echo Example: test_full_workflow_single_channel.bat "demo P4SPR 2.0" "used"
    exit /b 1
)

if "%SENSOR_QUALITY%"=="" (
    echo ERROR: Sensor quality required
    echo Usage: test_full_workflow_single_channel.bat "device_serial" "sensor_quality"
    echo Example: test_full_workflow_single_channel.bat "demo P4SPR 2.0" "used"
    exit /b 1
)

REM Configuration
set DURATION=120
set PYTHON_EXE=.\.venv312\Scripts\python.exe

echo ========================================================================
echo  FULL WORKFLOW TEST - SINGLE CHANNEL (A)
echo ========================================================================
echo.
echo  Device Serial: %DEVICE_SERIAL%
echo  Sensor Quality: %SENSOR_QUALITY%
echo  Test Channel: A only
echo  Spectral Duration: %DURATION%s (2 min)
echo.
echo  Collection Sequence:
echo    1. S-mode spectral data - Channel A only (~2 min)
echo    2. S-mode afterglow - Channel A only (~3 min FAST)
echo    3. P-mode spectral data - Channel A only (~2 min)
echo    4. P-mode afterglow - Channel A only (~3 min FAST)
echo.
echo  Total Estimated Time: ~10 minutes
echo.
echo ========================================================================
echo.

set START_TIME=%TIME%
echo [%TIME%] Starting single-channel workflow test...
echo.

REM ========================================================================
REM STEP 1: S-MODE SPECTRAL DATA (CHANNEL A ONLY)
REM ========================================================================

echo.
echo ========================================================================
echo  STEP 1/4: S-MODE SPECTRAL DATA - CHANNEL A
echo ========================================================================
echo.
echo  Duration: 2 min
echo  Rate: 4 Hz (production-matched timing)
echo  Expected spectra: ~480
echo.

%PYTHON_EXE% collect_spectral_data.py --mode S --duration %DURATION% --device-serial "%DEVICE_SERIAL%" --sensor-quality "%SENSOR_QUALITY%" --channels A

if errorlevel 1 (
    echo.
    echo ❌ ERROR: S-mode spectral collection failed!
    exit /b 1
)

echo [%TIME%] Step 1/4 complete: S-mode spectral data collected (Channel A)
echo.

REM ========================================================================
REM STEP 2: S-MODE AFTERGLOW (CHANNEL A ONLY)
REM ========================================================================

echo.
echo ========================================================================
echo  STEP 2/4: S-MODE AFTERGLOW - CHANNEL A
echo ========================================================================
echo.
echo  Duration: ~3 minutes
echo  Integration times: 10, 100 ms (fast mode)
echo  Cycles per measurement: 3
echo.

%PYTHON_EXE% led_afterglow_integration_time_model.py --mode S --fast --channels A

if errorlevel 1 (
    echo.
    echo ❌ ERROR: S-mode afterglow characterization failed!
    exit /b 1
)

echo [%TIME%] Step 2/4 complete: S-mode afterglow characterized (Channel A)
echo.

REM ========================================================================
REM STEP 3: P-MODE SPECTRAL DATA (CHANNEL A ONLY)
REM ========================================================================

echo.
echo ========================================================================
echo  STEP 3/4: P-MODE SPECTRAL DATA - CHANNEL A
echo ========================================================================
echo.
echo  Duration: 2 min
echo  Rate: 4 Hz (production-matched timing)
echo  Expected spectra: ~480
echo.

%PYTHON_EXE% collect_spectral_data.py --mode P --duration %DURATION% --device-serial "%DEVICE_SERIAL%" --sensor-quality "%SENSOR_QUALITY%" --channels A

if errorlevel 1 (
    echo.
    echo ❌ ERROR: P-mode spectral collection failed!
    exit /b 1
)

echo [%TIME%] Step 3/4 complete: P-mode spectral data collected (Channel A)
echo.

REM ========================================================================
REM STEP 4: P-MODE AFTERGLOW (CHANNEL A ONLY)
REM ========================================================================

echo.
echo ========================================================================
echo  STEP 4/4: P-MODE AFTERGLOW - CHANNEL A
echo ========================================================================
echo.
echo  Duration: ~3 minutes
echo  Integration times: 10, 100 ms (fast mode)
echo  Cycles per measurement: 3
echo.

%PYTHON_EXE% led_afterglow_integration_time_model.py --mode P --fast --channels A

if errorlevel 1 (
    echo.
    echo ❌ ERROR: P-mode afterglow characterization failed!
    exit /b 1
)

echo [%TIME%] Step 4/4 complete: P-mode afterglow characterized (Channel A)
echo.

REM ========================================================================
REM COMPLETION
REM ========================================================================

echo.
echo ========================================================================
echo  ✅ SINGLE-CHANNEL WORKFLOW TEST COMPLETE!
echo ========================================================================
echo.
echo  Start Time: %START_TIME%
echo  End Time:   %TIME%
echo.
echo  Data collected for Channel A:
echo    • S-mode spectral data (~480 spectra @ 4 Hz)
echo    • S-mode afterglow model (2 integration times)
echo    • P-mode spectral data (~480 spectra @ 4 Hz)
echo    • P-mode afterglow model (2 integration times)
echo.
echo  If this test was successful, you can now run the full workflow:
echo    .\collect_full_device_dataset.bat "%DEVICE_SERIAL%" "%SENSOR_QUALITY%"
echo.
echo ========================================================================
echo.

endlocal
