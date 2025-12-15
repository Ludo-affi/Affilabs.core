"""Configuration constants for AffiLabs.core application."""

# === Data Acquisition Constants ===
LEAK_DETECTION_WINDOW = 5.0  # seconds - sliding window for intensity monitoring
LEAK_THRESHOLD_RATIO = 1.5  # intensity must be > dark_noise * ratio to be valid

# === Signal Processing Constants ===
WAVELENGTH_TO_RU_CONVERSION = 1000.0  # 1 nm wavelength shift ≈ 1000 RU (Response Units)

# === Filtering Defaults ===
DEFAULT_FILTER_ENABLED = True  # Filtering ON by default (matches old software)
DEFAULT_FILTER_STRENGTH = 1  # Strength 1 = window 3
DEFAULT_FILTER_METHOD = "median"  # Options: 'median', 'kalman', 'savgol'
DEFAULT_MED_FILT_WIN = 3  # Median filter window size

# === Kalman Filter Tuning ===
KALMAN_MEASUREMENT_NOISE = 0.05  # Measurement noise covariance (R)
KALMAN_PROCESS_NOISE = 0.001  # Process noise covariance (Q)

# === Graph Display Settings ===
GRAPH_SUBSAMPLE_THRESHOLD = 10000  # Start downsampling above this many points
GRAPH_SUBSAMPLE_TARGET = 5000  # Target number of points after downsampling

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
