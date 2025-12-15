from .settings import *

# Timing synchronization constants (for calibration Step 6)
# These are also defined in root settings.py, but added here to resolve import conflicts
TIMING_ALIGNMENT_CYCLES = 8  # Number of cycles to verify consistency
TIMING_ALIGNMENT_TOLERANCE_MS = 10.0  # Max acceptable timing jitter (ms)
