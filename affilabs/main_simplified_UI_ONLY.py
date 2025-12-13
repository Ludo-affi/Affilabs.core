"""UI-only launcher for main_simplified_CURRENT_BACKUP - just shows the interface without signal connections."""

import sys
import atexit
from pathlib import Path
import threading

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from LL_UI_v1_0_GIT_VERSION import MainWindowPrototype
from core.hardware_manager import HardwareManager
from core.data_acquisition_manager import DataAcquisitionManager
from core.recording_manager import RecordingManager
from core.kinetic_manager import KineticManager
from core.data_buffer_manager import DataBufferManager
from affilabs.utils.logger import logger
from affilabs.utils.session_quality_monitor import SessionQualityMonitor
from affilabs.utils.spr_signal_processing import calculate_transmission
from affilabs.utils.performance_profiler import get_profiler, measure
from settings import SW_VERSION, PROFILING_ENABLED, PROFILING_REPORT_INTERVAL
from config import (
    LEAK_DETECTION_WINDOW, LEAK_THRESHOLD_RATIO, WAVELENGTH_TO_RU_CONVERSION,
    DEFAULT_FILTER_ENABLED, DEFAULT_FILTER_STRENGTH,
    OPTICS_LEAK_DETECTION_TIME, OPTICS_LEAK_THRESHOLD,
    OPTICS_MAX_DETECTOR_COUNTS, OPTICS_MAINTENANCE_INTENSITY_THRESHOLD
)

# Import TIME_ZONE from settings
try:
    from settings import TIME_ZONE
except ImportError:
    # Fallback if TIME_ZONE not available
    import datetime
    try:
        TIME_ZONE = datetime.datetime.now(datetime.UTC).astimezone().tzinfo
    except AttributeError:
        from datetime import timezone
        TIME_ZONE = datetime.datetime.now(timezone.utc).astimezone().tzinfo

import datetime as dt
import numpy as np


class Application(QApplication):
    """Main application with UI only - no signal connections."""

    def __init__(self, argv):
        super().__init__(argv)

        logger.info("=" * 70)
        logger.info("AffiLabs.core - Surface Plasmon Resonance Analysis")
        logger.info(f"{SW_VERSION} | {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info("=" * 70)

        # Create managers
        logger.info("Creating hardware manager...")
        self.hw_mgr = HardwareManager()

        logger.info("Creating data acquisition manager...")
        self.data_mgr = DataAcquisitionManager(self.hw_mgr)

        logger.info("Creating recording manager...")
        self.recording_mgr = RecordingManager(self.data_mgr)

        logger.info("Creating kinetic operations manager...")
        self.kinetic_mgr = KineticManager(self.hw_mgr)

        logger.info("Creating session quality monitor...")
        self.quality_monitor = SessionQualityMonitor(device_serial="UI_ONLY_MODE")

        # Create main window UI
        logger.info("Creating main window...")
        self.main_window = MainWindowPrototype()

        # Store reference to app in window for easy access to managers
        self.main_window.app = self

        # Track selected axis for manual/auto scaling (default X)
        self._selected_axis = 'x'

        # Data buffer for storing time series
        self.buffer_mgr = DataBufferManager()

        # Active channel list
        self.active_channels = set()

        # Store calibration data (s_ref, dark, etc.) per channel
        self.calibration_data = {
            'a': {'s_ref': None, 'dark': None, 'wavelengths': None},
            'b': {'s_ref': None, 'dark': None, 'wavelengths': None},
            'c': {'s_ref': None, 'dark': None, 'wavelengths': None},
            'd': {'s_ref': None, 'dark': None, 'wavelengths': None},
        }

        # Track if calibration is loaded from config vs fresh
        self.calibration_loaded_from_config = False

        # Track last raw data to prevent redundant processing
        self._last_raw_data = {ch: None for ch in ['a', 'b', 'c', 'd']}

        # Recording state
        self.recording_active = False

        # Experiment start time
        self.experiment_start_time = None

        # Cycle tracking for autosave
        self._last_cycle_bounds = None
        self._session_cycles_dir = None

        # Pre-computed channel mappings (performance optimization)
        self._channel_to_idx = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
        self._idx_to_channel = ['a', 'b', 'c', 'd']
        self._channel_pairs = [('a', 0), ('b', 1), ('c', 2), ('d', 3)]

        # === PHASE 3: ACQUISITION/PROCESSING THREAD SEPARATION ===
        # Lock-free queue for spectrum data (acquisition → processing)
        from queue import Queue
        self._spectrum_queue = Queue(maxsize=200)
        self._processing_thread = None
        self._processing_active = False
        self._queue_stats = {'dropped': 0, 'processed': 0, 'max_size': 0}

        # Pre-cache attribute checks for performance
        self._has_stop_cursor = (hasattr(self.main_window.full_timeline_graph, 'stop_cursor') and
                                self.main_window.full_timeline_graph.stop_cursor is not None)

        # Start processing thread
        self._start_processing_thread()

        # UI update throttling - prevent excessive graph redraws
        from PySide6.QtCore import QTimer
        self._ui_update_timer = QTimer()
        self._ui_update_timer.timeout.connect(self._process_pending_ui_updates)
        self._ui_update_timer.setInterval(100)  # 100ms = 10 FPS
        self._pending_graph_updates = {'a': None, 'b': None, 'c': None, 'd': None}
        self._pending_transmission_updates = {'a': None, 'b': None, 'c': None, 'd': None}
        self._skip_graph_updates = False
        self._ui_update_timer.start()

        # Performance profiling setup
        self.profiler = get_profiler()
        if PROFILING_ENABLED and PROFILING_REPORT_INTERVAL > 0:
            self._profiling_timer = QTimer()
            self._profiling_timer.timeout.connect(self._print_profiling_stats)
            self._profiling_timer.setInterval(PROFILING_REPORT_INTERVAL * 1000)
            self._profiling_timer.start()
            logger.info(f"📊 Profiling enabled - stats will print every {PROFILING_REPORT_INTERVAL}s")

        # Connect tab change signals to prevent UI freezing during transitions
        if hasattr(self.main_window, 'tab_widget'):
            self.main_window.tab_widget.currentChanged.connect(self._on_tab_changing)
        if hasattr(self.main_window, 'sidebar') and hasattr(self.main_window.sidebar, 'tabs'):
            self.main_window.sidebar.tabs.currentChanged.connect(self._on_tab_changing)

        # Show window FIRST
        logger.info("🏠 Showing main window...")
        self.main_window.show()

        # Register cleanup handler
        atexit.register(self.cleanup)

        logger.info("[OK] Application initialized successfully")

    def _start_processing_thread(self):
        """Start background processing thread for spectrum data."""
        self._processing_active = True
        self._processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
        self._processing_thread.start()
        logger.info("[OK] Processing thread started (acquisition/processing separated)")

    def _processing_worker(self):
        """Background worker that processes spectrum data from the queue."""
        logger.info("🟢 Processing worker started")
        # Placeholder - actual processing would happen here
        pass

    def _on_tab_changing(self):
        """Prevent graph updates during tab transitions."""
        pass

    def _process_pending_ui_updates(self):
        """Process batched UI updates at controlled rate."""
        pass

    def _print_profiling_stats(self):
        """Print performance profiling statistics."""
        if PROFILING_ENABLED:
            self.profiler.print_stats()

    def cleanup(self):
        """Clean up resources before exit."""
        try:
            logger.warning("[WARN] Emergency cleanup triggered - forcing resource release")

            # Stop processing thread
            self._processing_active = False
            if self._processing_thread and self._processing_thread.is_alive():
                self._processing_thread.join(timeout=1.0)

            logger.info("[OK] Emergency cleanup completed")
        except Exception as e:
            logger.error(f"[ERROR] Error during emergency cleanup: {e}")


def main():
    """Entry point."""
    logger.info("🚀 Starting AffiLabs.core (UI Only Mode)...")

    # Create application
    app = Application(sys.argv)

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
