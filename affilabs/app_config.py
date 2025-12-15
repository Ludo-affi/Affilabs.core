"""Configuration constants for AffiLabs.core application."""

# === Data Acquisition Constants ===
LEAK_DETECTION_WINDOW = 5.0  # seconds - sliding window for intensity monitoring
LEAK_THRESHOLD_RATIO = 1.5  # intensity must be > dark_noise * ratio to be valid

# === Signal Processing Constants ===
WAVELENGTH_TO_RU_CONVERSION = 355.0  # 1 nm wavelength shift = 355 RU (Response Units)

# === Filtering Defaults ===
DEFAULT_FILTER_ENABLED = (
    False  # Disable filtering by default (SG filter already applied to transmission)
)
DEFAULT_FILTER_STRENGTH = (
    3  # Strength 1 = minimal smoothing, 10 = maximum smoothing (3 = light smoothing)
)
# Uses adaptive online filtering: windowed for live display, batch for cycle analysis

# === Graph Display Settings ===
GRAPH_SUBSAMPLE_THRESHOLD = 10000  # Start downsampling above this many points
GRAPH_SUBSAMPLE_TARGET = 5000  # Target number of points after downsampling

# === Memory Management Settings ===
# Live Sensorgram: Navigation tool for long experiments
# Requirement: 4 channels × 1 point/sec × 5 hours = 72,000 points total (18k per channel)
# Memory: 20k points × 4 channels × 16 bytes = 1.28 MB (negligible)
TIMELINE_MAX_DISPLAY_POINTS = 20000  # Display up to 5.5 hours (20k points at 1 Hz)
TIMELINE_MAX_MEMORY_POINTS = 100000  # Memory buffer: 27+ hours (practically unlimited)
TIMELINE_TRIM_TO_POINTS = 80000  # Trim threshold (22+ hours)

# Cycle of Interest: Full resolution detail view
# Requirement: Max 60 min × 4 channels × 1 point/sec = 3,600 points per channel
# Memory: 3,600 points × 4 channels × 16 bytes = 57.6 KB (trivial)
CYCLE_MAX_POINTS = 3600  # Full resolution for 60-minute cycles (no downsampling needed)

# Memory flushing: Keep recent data, older data available in CSV
ENABLE_MEMORY_TRIMMING = False  # Disabled - 1 Hz uses minimal memory, no need to trim
CSV_RELOAD_ENABLED = False  # Future feature: reload historical data from CSV on demand

# === Quality Monitoring ===
FWHM_WARNING_THRESHOLD = 2.0  # nm - warn if FWHM exceeds this
FWHM_CRITICAL_THRESHOLD = 5.0  # nm - critical if FWHM exceeds this

# === Optics Readiness Monitoring ===
OPTICS_LEAK_DETECTION_TIME = 3.0  # seconds - time window to detect intensity drop
OPTICS_LEAK_THRESHOLD = 0.10  # 10% of max detector counts
OPTICS_MAX_DETECTOR_COUNTS = 65535  # Maximum counts for USB4000 (16-bit)
OPTICS_MAINTENANCE_INTENSITY_THRESHOLD = 5000  # Minimum counts to pass calibration

# === Time Constants ===
ACQUISITION_INTERVAL_MS = 100  # milliseconds between spectrum acquisitions
CALIBRATION_TIMEOUT_S = 60  # seconds - maximum time for calibration

# === File Export Defaults ===
DEFAULT_EXPORT_DIRECTORY = "Documents"  # Relative to user's home directory
DEFAULT_FILE_PREFIX = "AffiLabs_data"  # Prefix for auto-generated filenames
DEFAULT_LOG_PREFIX = "AffiLabs_debug_log"  # Prefix for debug logs

# === Hardware Connection ===
HARDWARE_SCAN_TIMEOUT_S = 10  # seconds - timeout for hardware detection
CONTROLLER_RETRY_ATTEMPTS = 3  # Number of retries for controller connection

# === UI Update Intervals ===
STATUS_UPDATE_INTERVAL_MS = 100  # milliseconds between status bar updates
PROGRESS_BAR_UPDATE_MS = 100  # milliseconds between progress bar updates

# === Live Data Performance Settings ===
DEBUG_LOG_THROTTLE_FACTOR = (
    10  # Log debug messages every Nth acquisition (1=all, 10=every 10th)
)
TRANSMISSION_UPDATE_INTERVAL = (
    1.0  # seconds between transmission spectrum updates (QC graphs)
)
SENSORGRAM_DOWNSAMPLE_FACTOR = (
    1  # Show all points (1=all, 2=half) - no throttling for smooth 1 Hz updates
)

# Timeline graph (main sensorgram) is EVENT-DRIVEN via signal, not timer-based
# Cycle of interest graph (bottom graph) uses timer for smooth cursor following
CYCLE_OF_INTEREST_UPDATE_INTERVAL_MS = 33  # milliseconds = 30 Hz for bottom graph only
ENABLE_TRANSMISSION_UPDATES_DEFAULT = (
    True  # Enable transmission plot updates during live acquisition
)
ENABLE_RAW_SPECTRUM_UPDATES_DEFAULT = (
    True  # Enable raw spectrum plot updates during live acquisition
)

# === Advanced Performance (Experimental) ===
# ENABLE_OPENGL = False  # Set True to enable GPU acceleration (requires compatible drivers)
# PAUSE_UPDATES_DURING_INTERACTION = True  # Pause graph updates while zooming/panning
