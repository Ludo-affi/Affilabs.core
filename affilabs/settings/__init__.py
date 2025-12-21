# MAIN SETTINGS FILE: affilabs/settings/settings.py
# This is the single source of truth for all settings
from .settings import *

# Timing synchronization constants (for calibration Step 6)
TIMING_ALIGNMENT_CYCLES = 8  # Number of cycles to verify consistency
TIMING_ALIGNMENT_TOLERANCE_MS = 10.0  # Max acceptable timing jitter (ms)
