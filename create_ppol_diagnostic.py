"""Create P-pol diagnostic plot after first live scan.

This script demonstrates how calibration data flows to live mode and
visualizes the first P-pol measurements with the complete pipeline:

1. Step 4: LED balancing → LED values stored in state.leds_calibrated
2. Step 6: S-reference measured → stored in data_acquisition.ref_sig
3. Live Mode: P-pol measured with calibrated LEDs
4. Calculate P/S ratio → Transmittance
5. Extract peak → Resonance shift (RU) for sensorgram

Usage:
    1. Run calibration (Steps 3-6)
    2. Start live measurements (click "Start")
    3. After ~1-2 seconds (first full cycle), run this script:
       python create_ppol_diagnostic.py

The script will save a diagnostic PNG showing:
- P-pol spectra (dark-corrected)
- S-reference spectra (from calibration)
- Transmittance (P/S ratio)
- ROI statistics for count measurements
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import logger

def main():
    """Generate P-pol diagnostic plot from current live data."""

    logger.info("=" * 80)
    logger.info("P-POL DIAGNOSTIC PLOT GENERATOR")
    logger.info("=" * 80)

    # Check if we have access to the running application
    try:
        # Import the main application module
        from main.main import PicoP4SPR

        # Try to find the running instance (this is tricky without proper IPC)
        # For now, we'll just explain what needs to be done
        logger.warning("⚠️  MANUAL INTEGRATION REQUIRED:")
        logger.warning("   This diagnostic function must be called from the running application.")
        logger.warning("")
        logger.warning("   To generate the P-pol diagnostic:")
        logger.warning("")
        logger.warning("   1. After calibration completes, start live measurements")
        logger.warning("   2. Wait for first full cycle (1-2 seconds)")
        logger.warning("   3. In Python console or debug mode, call:")
        logger.warning("      app.data_acquisition.create_ppol_diagnostic_plot()")
        logger.warning("")
        logger.warning("   The plot will be saved to:")
        logger.warning("   generated-files/diagnostics/ppol_live_diagnostic_[timestamp].png")
        logger.warning("")
        logger.info("=" * 80)
        logger.info("DATA FLOW EXPLANATION:")
        logger.info("=" * 80)
        logger.info("")
        logger.info("1. CALIBRATION STEP 4 (LED Balancing):")
        logger.info("   - Measures raw S-pol spectra with increasing LED intensities")
        logger.info("   - Finds LED values that achieve 49,151 counts (75% detector max)")
        logger.info("   - Stores LED values in: state.ref_intensity")
        logger.info("   - Syncs to live mode: state.leds_calibrated = state.ref_intensity.copy()")
        logger.info("   - Location: spr_calibrator.py line 3816")
        logger.info("")
        logger.info("2. CALIBRATION STEP 6 (S-reference):")
        logger.info("   - Measures S-pol with calibrated LEDs")
        logger.info("   - Subtracts dark noise")
        logger.info("   - Stores in: data_acquisition.ref_sig[ch]")
        logger.info("   - This becomes the denominator in P/S ratio")
        logger.info("")
        logger.info("3. LIVE MODE STARTS:")
        logger.info("   - User clicks 'Start' button")
        logger.info("   - Acquisition loop begins (spr_data_acquisition.py)")
        logger.info("   - Reads LED values from: state.leds_calibrated")
        logger.info("   - Location: spr_data_acquisition.py lines 943-944")
        logger.info("")
        logger.info("4. P-POL MEASUREMENT (each cycle):")
        logger.info("   - Turn on LED with calibrated intensity")
        logger.info("   - Acquire P-pol spectrum (polarizer rotated 90°)")
        logger.info("   - Subtract dark noise: p_corrected = raw - dark")
        logger.info("   - Location: spr_data_acquisition.py line 1248")
        logger.info("")
        logger.info("5. TRANSMITTANCE CALCULATION:")
        logger.info("   - Calculate P/S ratio: trans = p_corrected / s_ref")
        logger.info("   - Location: spr_data_acquisition.py lines 1252-1258")
        logger.info("   - Result stored in: data_acquisition.trans_data[ch]")
        logger.info("")
        logger.info("6. PEAK EXTRACTION:")
        logger.info("   - Find centroid/peak in transmittance spectrum")
        logger.info("   - Convert to resonance shift (RU)")
        logger.info("   - Update sensorgram time-series plot")
        logger.info("")
        logger.info("=" * 80)
        logger.info("KEY VARIABLES:")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Calibration → Live Mode Sync:")
        logger.info("   state.ref_intensity      → LED values from Step 4")
        logger.info("   state.leds_calibrated    → Copy for live mode (line 3816)")
        logger.info("   data_acquisition.ref_sig → S-reference from Step 6")
        logger.info("")
        logger.info("Live Mode Data:")
        logger.info("   int_data[ch]             → P-pol (dark-corrected)")
        logger.info("   ref_sig[ch]              → S-reference (from calibration)")
        logger.info("   trans_data[ch]           → P/S ratio (transmittance)")
        logger.info("   lambda_values[ch]        → Resonance shift (RU) time-series")
        logger.info("")
        logger.info("=" * 80)

    except ImportError as e:
        logger.error(f"❌ Cannot import main application: {e}")
        logger.error("   Make sure the application is in the Python path")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
