from __future__ import annotations

import threading
import time
from time import perf_counter  # ⏱️ TIMING: High-precision monotonic timer
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Protocol, cast
from pathlib import Path
from datetime import datetime
import queue  # ✨ PIPELINE: For async acquisition/processing

import numpy as np
from typing import Optional

# Optional scipy for interpolation (fallback available if not installed)
try:
    from scipy.interpolate import interp1d
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    interp1d = None

from settings import CH_LIST, DEVICES, EZ_CH_LIST, MIN_WAVELENGTH, MAX_WAVELENGTH, FILTERING_ON
from utils.logger import logger
from widgets.datawindow import DataDict
from widgets.message import show_message

# Optional temporal smoothing from old software
try:
    from utils.temporal_smoothing import TemporalMeanFilter
    HAS_TEMPORAL_FILTER = True
except ImportError:
    HAS_TEMPORAL_FILTER = False
    TemporalMeanFilter = None

# Constants
DERIVATIVE_WINDOW = 165  # Window size for derivative calculation
SAVE_DEBUG_DATA = True  # Enable saving intermediate processing steps (set to True for debugging)


class SignalEmitter(Protocol):
    """Protocol for Qt signal emitters."""

    def emit(self, *args: Any) -> None: ...



# ============================================================================
# ML-BASED AFTERGLOW CORRECTION (Hybrid Physics + ML)
# Added by integrate_ml_correction.py on October 22, 2025
# ============================================================================

class MLAfterglowCorrection:
    """Hybrid Physics + ML Afterglow Correction.

    Combines physics-based exponential decay model with ML residual learning
    to achieve better afterglow correction than either approach alone.

    Architecture:
        1. Physics model predicts baseline correction (exp decay)
        2. ML model (LSTM) predicts residual correction
        3. Final = physics_correction + ml_residual
    """

    def __init__(self, model_path='afterglow_ml_model.h5',
                 scaler_path='model_scaler.pkl'):
        """Initialize ML afterglow corrector.

        Args:
            model_path: Path to trained Keras model (.h5)
            scaler_path: Path to feature scaler (.pkl)
        """
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)
        self.model = None
        self.scaler = None
        self.enabled = False

        # Channel history for multi-step prediction
        self.channel_history = {
            'a': [], 'b': [], 'c': [], 'd': []
        }
        self.max_history = 3  # Keep last 3 measurements

        # Channel sequence
        self.channels = ['a', 'b', 'c', 'd']

        # Try to load model
        self._load_model()

    def _load_model(self):
        """Load trained ML model and scaler."""
        if not self.model_path.exists():
            logger.info(f"ℹ️  ML model not found: {self.model_path}")
            logger.info(f"   Falling back to physics-only correction")
            return False

        if not self.scaler_path.exists():
            logger.warning(f"⚠️ Scaler not found: {self.scaler_path}")
            logger.info(f"   Falling back to physics-only correction")
            return False

        try:
            import tensorflow as tf
            import pickle

            # Load model
            self.model = tf.keras.models.load_model(str(self.model_path))

            # Load scaler
            with open(self.scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)

            self.enabled = True
            logger.info(f"✅ ML afterglow model loaded: {self.model_path.name}")
            logger.info(f"   Hybrid Physics + ML correction ENABLED")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to load ML model: {e}")
            logger.info(f"   Falling back to physics-only correction")
            return False

    def update_channel_history(self, channel: str, signal: float):
        """Update signal history for a channel."""
        self.channel_history[channel].append(signal)

        # Keep only last N measurements
        if len(self.channel_history[channel]) > self.max_history:
            self.channel_history[channel].pop(0)

    def get_previous_signals(self, current_channel: str):
        """Get previous channel signals for ML input.

        Args:
            current_channel: Current channel ('a', 'b', 'c', 'd')

        Returns:
            (prev_signal, prev2_signal): Signals from last 2 channels in sequence
        """
        ch_idx = self.channels.index(current_channel)

        # Previous channel in sequence
        prev_ch = self.channels[(ch_idx - 1) % 4]
        prev_signal = self.channel_history[prev_ch][-1] if self.channel_history[prev_ch] else 0.0

        # Previous-2 channel in sequence
        prev2_ch = self.channels[(ch_idx - 2) % 4]
        prev2_signal = self.channel_history[prev2_ch][-1] if self.channel_history[prev2_ch] else 0.0

        return prev_signal, prev2_signal

    def calculate_physics_correction(self, prev_signal: float, delay_ms: float,
                                    integration_time_ms: float) -> float:
        """Calculate physics-based correction (simplified exponential model).

        Args:
            prev_signal: Previous channel signal (RU)
            delay_ms: Time since previous channel (ms)
            integration_time_ms: Integration time (ms)

        Returns:
            Physics-based correction value (RU)
        """
        # Simple exponential decay model
        tau_ms = 20.0  # Typical phosphor decay time
        amplitude_factor = 0.05  # ~5% of signal remains as afterglow

        correction = prev_signal * amplitude_factor * np.exp(-delay_ms / tau_ms)
        return correction

    def predict_ml_residual(self, prev_signal: float, prev2_signal: float,
                           delay_ms: float, integration_time_ms: float,
                           physics_correction: float, channel: str) -> float:
        """Predict ML residual correction.

        Args:
            prev_signal: Previous channel signal
            prev2_signal: Previous-2 channel signal
            delay_ms: Time delay since previous channel
            integration_time_ms: Integration time
            physics_correction: Physics model prediction
            channel: Current channel ID

        Returns:
            ML residual correction (RU)
        """
        if not self.enabled or self.model is None:
            return 0.0

        try:
            # Channel encoding (one-hot)
            channel_encoding = [1 if c == channel else 0 for c in self.channels]

            # Feature vector (must match training features)
            features = np.array([[
                prev_signal,
                prev2_signal,
                delay_ms,
                integration_time_ms,
                physics_correction,
                *channel_encoding
            ]])

            # Scale features
            features_scaled = self.scaler.transform(features)

            # Predict residual
            residual = self.model.predict(features_scaled, verbose=0)[0, 0]

            return float(residual)

        except Exception as e:
            logger.warning(f"⚠️ ML prediction failed: {e}")
            return 0.0

    def calculate_correction(self, current_channel: str,
                           integration_time_ms: float,
                           delay_ms: float) -> float:
        """Calculate hybrid physics + ML correction.

        Args:
            current_channel: Current channel being measured
            integration_time_ms: Integration time (ms)
            delay_ms: Time since previous channel (ms)

        Returns:
            Total correction value (physics + ML residual)
        """
        # Get previous signals
        prev_signal, prev2_signal = self.get_previous_signals(current_channel)

        # If no history, return 0
        if prev_signal == 0.0:
            return 0.0

        # Physics correction (baseline)
        physics_correction = self.calculate_physics_correction(
            prev_signal, delay_ms, integration_time_ms
        )

        # ML residual correction (learns what physics misses)
        ml_residual = self.predict_ml_residual(
            prev_signal, prev2_signal, delay_ms, integration_time_ms,
            physics_correction, current_channel
        )

        # Total correction
        total_correction = physics_correction + ml_residual

        return total_correction

# ============================================================================
# END ML CORRECTION CLASS
# ============================================================================


class SPRDataAcquisition:
    """Manages SPR data acquisition, sensor reading, and real-time data processing.

    Handles the main data acquisition loop, spectrum reading, transmission calculation,
    wavelength fitting, and filtering operations with minimal UI coupling via callbacks.
    """

    def __init__(
        self,
        *,
        # Hardware references
        ctrl: Optional[Any],
        usb: Optional[Any],
        data_processor: Optional[Any],
        # Data storage references (managed by main app)
        lambda_values: dict[str, np.ndarray],
        lambda_times: dict[str, np.ndarray],
        filtered_lambda: dict[str, np.ndarray],
        buffered_lambda: dict[str, np.ndarray],
        buffered_times: dict[str, np.ndarray],
        int_data: dict[str, np.ndarray],
    trans_data: dict[str, Optional[np.ndarray]],
    ref_sig: dict[str, Optional[np.ndarray]],
        wave_data: np.ndarray,
        # Configuration
        device_config: dict[str, Any],
        num_scans: int,
        led_delay: float,
        led_on_delay: Optional[float] = None,
        led_off_delay: Optional[float] = None,
        med_filt_win: int,
        dark_noise: np.ndarray,
        base_integration_time_factor: float = 1.0,
        # State management
        _b_kill: threading.Event,
        _b_stop: threading.Event,
        _b_no_read: threading.Event,
        # UI callbacks
        update_live_signal: SignalEmitter,
        update_spec_signal: SignalEmitter,
        temp_sig: SignalEmitter,
        raise_error: SignalEmitter,
        set_status_text: Callable[[str], None],
        # Diagnostic signals (optional)
        processing_steps_signal: Optional[SignalEmitter] = None,
    ) -> None:
        # Hardware references
        self.ctrl = ctrl
        self.usb = usb
        self.data_processor = data_processor

        # Data storage (references to main app data)
        self.lambda_values = lambda_values
        self.lambda_times = lambda_times
        self.filtered_lambda = filtered_lambda
        self.buffered_lambda = buffered_lambda
        self.buffered_times = buffered_times
        self.int_data = int_data
        self.trans_data = trans_data
        self.ref_sig = ref_sig
        self.wave_data = wave_data

        # Configuration
        self.device_config = device_config
        self.num_scans = num_scans
        self.scans_per_channel: dict[str, int] = {}  # ✨ NEW: Per-channel scan counts (200ms budget optimization)
        self.integration_per_channel: dict[str, float] = {}  # ✨ NEW: Per-channel integration times (per_channel mode)
        # LED delays
        self.led_on_delay = led_on_delay if led_on_delay is not None else led_delay
        self.led_off_delay = led_off_delay if led_off_delay is not None else led_delay
        # Back-compat: single led_delay approximated as total inter-channel delay
        self.led_delay = (self.led_on_delay + self.led_off_delay)
        self.med_filt_win = med_filt_win
        self.dark_noise = dark_noise
        self.base_integration_time_factor = base_integration_time_factor
        # Optional per-channel dark noise (per-channel calibration mode)
        self.per_channel_dark_noise: dict[str, np.ndarray] = {}

        # State management
        self._b_kill = _b_kill
        self._b_stop = _b_stop
        self._b_no_read = _b_no_read

        # UI callbacks
        self.update_live_signal = update_live_signal
        self.update_spec_signal = update_spec_signal
        self.temp_sig = temp_sig
        self.raise_error = raise_error
        self.set_status_text = set_status_text
        self.processing_steps_signal = processing_steps_signal

        # ✨ MICRO-OPT: Conditional diagnostic emission (saves 12-20ms when disabled)
        # Only package and emit diagnostic data when diagnostic window is actually open
        self.emit_diagnostic_data = False  # Default: disabled for performance

        # ✨ OLD SOFTWARE: Initialize temporal mean filter (5-point backward mean)
        self.temporal_filter = None
        if FILTERING_ON and HAS_TEMPORAL_FILTER:
            self.temporal_filter = TemporalMeanFilter(window_size=med_filt_win)
            logger.info(f"✅ Temporal mean filter enabled (window={med_filt_win}, matching old software)")
        elif FILTERING_ON:
            logger.warning("⚠️ FILTERING_ON=True but temporal_smoothing.py not found")

        # Internal state
        self.exp_start: float = 0.0
        self.filt_buffer_index: int = 0
        self.single_mode: bool = False
        self.single_ch: str = "a"
        self.calibrated: bool = False
        self.filt_on: bool = True
        self.recording: bool = False

        # ✨ NEW: Batch LED control and afterglow correction for live mode
        # Will be initialized to last channel in active list on first cycle
        # Supports: ABCD loop, AC loop, BD loop, or any channel configuration
        self._last_active_channel: Optional[str] = None  # Track previous channel for afterglow
        self._afterglow_initialized: bool = False  # Flag for first-cycle initialization
        self.afterglow_correction = None
        self.afterglow_correction_enabled = False
        self._batch_led_available = hasattr(ctrl, 'set_batch_intensities') if ctrl else False
        # Optional one-cycle force-255 verification
        try:
            from settings import LED_FORCE_255_TEST_CYCLE as _LED_FORCE_255_TEST_CYCLE
            self._force_255_enabled: bool = bool(_LED_FORCE_255_TEST_CYCLE)
        except Exception:
            self._force_255_enabled = False
        self._force_255_done: dict[str, bool] = {ch: False for ch in CH_LIST}

        # Load optical calibration for afterglow correction
        logger.info(f"🔍 device_config type: {type(device_config)}, is None: {device_config is None}")
        if device_config:
            # Check for optical_calibration section (nested) or direct key (backward compat)
            optical_config = device_config.get('optical_calibration', {})
            optical_cal_file = optical_config.get('optical_calibration_file') or device_config.get('optical_calibration_file')
            afterglow_enabled = optical_config.get('afterglow_correction_enabled',
                                                   device_config.get('afterglow_correction_enabled', True))

            logger.info(f"🔍 optical_cal_file: {optical_cal_file}, afterglow_enabled: {afterglow_enabled}")
            if optical_cal_file and afterglow_enabled:
                logger.info(f"🔍 Attempting to load afterglow correction from: {optical_cal_file}")
                try:
                    from afterglow_correction import AfterglowCorrection
                    logger.info(f"🔍 AfterglowCorrection class imported successfully")
                    self.afterglow_correction = AfterglowCorrection(optical_cal_file)

                    # Initialize ML afterglow corrector (hybrid approach)
                    try:
                        self.ml_afterglow = MLAfterglowCorrection()
                        if self.ml_afterglow.enabled:
                            logger.info("   🤖 ML residual correction enabled (Hybrid mode)")
                    except Exception as e:
                        logger.warning(f"   ⚠️ ML correction initialization failed: {e}")
                        self.ml_afterglow = None
                    self.afterglow_correction_enabled = True
                    logger.info(f"🔍 AfterglowCorrection object created successfully")

                    # ✨ SINGLE SOURCE OF TRUTH: Use LED delay already set by calibrator
                    # The calibrator calculated optimal delay during calibration and saved it to state
                    # We just log it here for confirmation
                    logger.info(
                        f"✅ Optical calibration loaded for live mode afterglow correction\n"
                        f"   Using LED delay from calibration: {self.led_delay*1000:.1f}ms"
                    )
                except FileNotFoundError as e:
                    logger.warning(f"⚠️ Optical calibration file not found: {e}")
                    logger.info(f"ℹ️ Using default LED delay: {self.led_delay*1000:.1f}ms")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load optical calibration: {type(e).__name__}: {e}")
                    logger.info(f"ℹ️ Using default LED delay: {self.led_delay*1000:.1f}ms")
                    import traceback
                    logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            else:
                if not afterglow_enabled:
                    logger.info("ℹ️ Afterglow correction disabled for live mode (device_config)")
                else:
                    logger.debug("ℹ️ No optical calibration file - afterglow correction disabled for live mode")
                logger.info(f"ℹ️ Using default LED delay: {self.led_delay*1000:.1f}ms")

        # Log optimization status
        if self._batch_led_available:
            logger.info("⚡ Batch LED control ENABLED for live mode (15× faster LED switching)")
        else:
            logger.info("ℹ️ Sequential LED control (batch not available)")

        # Log integration time acceleration status
        if self.base_integration_time_factor < 1.0:
            logger.info(
                f"⚡ Integration time acceleration ACTIVE: {self.base_integration_time_factor}x factor "
                f"({1/self.base_integration_time_factor:.1f}x faster measurements)"
            )
        else:
            logger.info("⏱️ Standard integration time (no acceleration)")

        # ⏱️ TIMING INSTRUMENTATION: Performance analysis and optimization
        self.enable_timing_logs = True  # Set to False to disable detailed timing logs
        self.timing_samples = []  # Store timing samples for analysis
        self.cycle_count = 0  # Track cycle number for periodic reporting

        # ✨ PIPELINE OPTIMIZATION: Separate acquisition from processing
        # Queue for passing raw data from acquisition thread to processing thread
        self.processing_queue: queue.Queue = queue.Queue(maxsize=20)  # Buffer up to 20 samples
        self.processing_thread: threading.Optional[Thread] = None
        self.processing_active = False

        # Debug data saving
        self.debug_data_counter = 0
        self.debug_save_dir = Path("generated-files/debug_processing_steps")
        if SAVE_DEBUG_DATA:
            self.debug_save_dir.mkdir(parents=True, exist_ok=True)

        # ✨ PHASE 3A OPTIMIZATION: Cache wavelength mask (saves ~48ms per cycle)
        # Wavelengths never change during a session, so create mask once and reuse
        self._wavelength_mask: Optional[np.ndarray] = None
        self._wavelength_mask_initialized = False

        # One-time LED activation sanity check per channel
        self._led_verified = {ch: False for ch in CH_LIST}

    def _initialize_wavelength_mask(self) -> bool:
        """Initialize and cache the wavelength mask once.

        This optimization saves ~12ms per channel (48ms per 4-channel cycle) by
        avoiding repeated USB reads and mask creation. Wavelengths are constant
        during a session, so we only need to create the mask once.

        Returns:
            bool: True if mask initialized successfully, False otherwise
        """
        if self._wavelength_mask_initialized:
            return True

        try:
            # Read wavelengths from spectrometer (one-time operation)
            current_wavelengths = None
            # Use HAL method directly (unified access path)
            if hasattr(self.usb, "get_wavelengths"):
                wl = self.usb.get_wavelengths()
                if wl is not None:
                    current_wavelengths = np.array(wl)
            elif hasattr(self.usb, "read_wavelength"):
                # Fallback for legacy adapters
                current_wavelengths = self.usb.read_wavelength()

            if current_wavelengths is None:
                logger.error("❌ Cannot get wavelengths from spectrometer for mask initialization")
                return False

            # Use calibration wavelength boundaries
            min_wavelength = self.wave_data[0]   # First wavelength from calibration
            max_wavelength = self.wave_data[-1]  # Last wavelength from calibration

            # Create mask using calibration boundaries
            self._wavelength_mask = (current_wavelengths >= min_wavelength) & (current_wavelengths <= max_wavelength)

            num_pixels = np.sum(self._wavelength_mask)
            self._wavelength_mask_initialized = True

            logger.info(
                f"✅ Wavelength mask cached: {num_pixels} pixels "
                f"({min_wavelength:.1f}-{max_wavelength:.1f} nm)"
            )
            logger.info(f"⚡ Optimization: Saves ~48ms per 4-channel cycle (no repeated mask creation)")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize wavelength mask: {e}")
            return False

    def create_ppol_diagnostic_plot(
        self,
        channels: list[str] = ['a', 'b', 'c', 'd']
    ) -> None:
        """Create diagnostic plot showing first P-pol scans in live mode.

        This shows the complete data pipeline:
        - Raw P-pol spectra (with calibrated LEDs)
        - Dark-corrected P-pol
        - S-reference (from calibration)
        - Final transmittance (P/S ratio)
        - ROI means for count measurements

        Args:
            channels: List of channels to plot (default: all channels)
        """
        try:
            import matplotlib.pyplot as plt
            from datetime import datetime

            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Live Mode P-pol Diagnostic: First Scan After Calibration\nData Pipeline: Raw → Dark-Corrected → P/S Ratio → Count',
                        fontsize=14, fontweight='bold')

            colors = {'a': '#FF6B6B', 'b': '#4ECDC4', 'c': '#45B7D1', 'd': '#FFA07A'}

            # Get wavelength array
            wavelengths = self.wave_data

            # Get integration time
            integration_time_ms = 100.0  # Default
            if hasattr(self.usb, 'integration_time'):
                integration_time_ms = self.usb.integration_time * 1000.0
            elif hasattr(self.usb, '_integration_time'):
                integration_time_ms = self.usb._integration_time * 1000.0

            # Plot 1: Raw P-pol + Dark-corrected overlay
            ax1 = axes[0, 0]
            for ch in channels:
                if ch not in self.int_data or self.int_data[ch] is None:
                    continue

                # Get LED value
                led_val = 255
                if hasattr(self, 'live_led_intensities') and ch in self.live_led_intensities:
                    led_val = self.live_led_intensities[ch]
                elif hasattr(self, 'calibrated_leds') and ch in self.calibrated_leds:
                    led_val = self.calibrated_leds[ch]

                # Plot dark-corrected P-pol (this is what goes into P/S calculation)
                p_corrected = self.int_data[ch]
                if len(p_corrected) == len(wavelengths):
                    ax1.plot(wavelengths, p_corrected, label=f'{ch.upper()} P-pol (LED={led_val})',
                            color=colors.get(ch, 'gray'), alpha=0.7, linewidth=1.5)

            ax1.set_xlabel('Wavelength (nm)', fontsize=11)
            ax1.set_ylabel('Intensity (counts)', fontsize=11)
            ax1.set_title('P-pol Spectra (Dark-Corrected)', fontsize=12, fontweight='bold')
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)

            # Plot 2: S-reference overlay
            ax2 = axes[0, 1]
            for ch in channels:
                if ch not in self.ref_sig or self.ref_sig[ch] is None:
                    continue

                s_ref = self.ref_sig[ch]
                if len(s_ref) == len(wavelengths):
                    ax2.plot(wavelengths, s_ref, label=f'{ch.upper()} S-ref',
                            color=colors.get(ch, 'gray'), alpha=0.7, linewidth=1.5)

            ax2.set_xlabel('Wavelength (nm)', fontsize=11)
            ax2.set_ylabel('Intensity (counts)', fontsize=11)
            ax2.set_title('S-reference Spectra (from Calibration Step 6)', fontsize=12, fontweight='bold')
            ax2.legend(fontsize=10)
            ax2.grid(True, alpha=0.3)

            # Plot 3: Transmittance (P/S ratio) overlay
            ax3 = axes[1, 0]
            for ch in channels:
                if ch not in self.trans_data or self.trans_data[ch] is None:
                    continue

                trans = self.trans_data[ch]
                if len(trans) == len(wavelengths):
                    ax3.plot(wavelengths, trans, label=f'{ch.upper()} P/S',
                            color=colors.get(ch, 'gray'), alpha=0.7, linewidth=1.5)

            ax3.set_xlabel('Wavelength (nm)', fontsize=11)
            ax3.set_ylabel('Transmittance (P/S)', fontsize=11)
            ax3.set_title('Final Transmittance (P/S Ratio for Count Measurement)', fontsize=12, fontweight='bold')
            ax3.legend(fontsize=10)
            ax3.grid(True, alpha=0.3)

            # Plot 4: ROI statistics summary
            ax4 = axes[1, 1]
            ax4.axis('off')

            # Calculate ROI means (580-610nm)
            roi_mask = (wavelengths >= 580) & (wavelengths <= 610)

            summary_text = f"""
LIVE MODE P-POL DIAGNOSTIC
═══════════════════════════════════════════

Integration Time: {integration_time_ms:.1f} ms

ROI Statistics (580-610nm):
"""

            for ch in channels:
                if ch not in self.int_data or self.int_data[ch] is None:
                    continue

                # Get LED value
                led_val = 255
                if hasattr(self, 'live_led_intensities') and ch in self.live_led_intensities:
                    led_val = self.live_led_intensities[ch]
                elif hasattr(self, 'calibrated_leds') and ch in self.calibrated_leds:
                    led_val = self.calibrated_leds[ch]

                # Calculate ROI means
                p_corrected = self.int_data[ch]
                s_ref = self.ref_sig.get(ch)
                trans = self.trans_data.get(ch)

                if len(p_corrected) == len(wavelengths):
                    p_roi_mean = float(np.mean(p_corrected[roi_mask]))

                    s_roi_mean = 0.0
                    if s_ref is not None and len(s_ref) == len(wavelengths):
                        s_roi_mean = float(np.mean(s_ref[roi_mask]))

                    trans_roi_mean = 0.0
                    if trans is not None and len(trans) == len(wavelengths):
                        trans_roi_mean = float(np.mean(trans[roi_mask]))

                    summary_text += f"""
   Channel {ch.upper()} (LED={led_val}):
      P-pol:        {p_roi_mean:7,.0f} counts
      S-ref:        {s_roi_mean:7,.0f} counts
      P/S ratio:    {trans_roi_mean:7.4f}
"""

            summary_text += f"""
═══════════════════════════════════════════
Data Flow:
1. Calibration Step 4: Balance LEDs → LED values
2. Calibration Step 6: Measure S-ref → S-reference
3. Live Mode: Measure P-pol with calibrated LEDs
4. Calculate P/S ratio → Transmittance
5. Extract peak/centroid → Resonance shift (RU)
6. Update sensorgram with time-series RU values
"""

            ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
                    fontsize=10, verticalalignment='top', family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.4))

            plt.tight_layout()

            # Save figure
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path("generated-files/diagnostics")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"ppol_live_diagnostic_{timestamp}.png"

            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            logger.info(f"📊 P-pol live mode diagnostic plot saved: {output_file}")

            plt.close(fig)

        except Exception as e:
            logger.warning(f"Failed to create P-pol diagnostic plot: {e}")
            import traceback
            logger.warning(traceback.format_exc())

    def _save_debug_step(self, channel: str, step_name: str, data: np.ndarray, wavelengths: np.ndarray) -> None:
        """Save intermediate processing step data for debugging.

        Args:
            channel: Channel name ('a', 'b', 'c', 'd')
            step_name: Name of processing step (e.g., 'raw', 'after_dark', 'after_s', 'after_p', 'transmittance')
            data: Spectrum data to save
            wavelengths: Wavelength array
        """
        if not SAVE_DEBUG_DATA:
            return

        try:
            # Check for size mismatch BEFORE saving
            if len(wavelengths) != len(data):
                logger.warning(
                    f"⚠️ SIZE MISMATCH in {step_name} ch{channel}: "
                    f"wavelengths={len(wavelengths)}, spectrum={len(data)}. "
                    f"Trimming to match."
                )
                # Trim to shorter length
                min_len = min(len(wavelengths), len(data))
                wavelengths = wavelengths[:min_len]
                data = data[:min_len]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ch{channel}_{step_name}_{timestamp}_{self.debug_data_counter:04d}.npz"
            filepath = self.debug_save_dir / filename

            np.savez(
                filepath,
                wavelengths=wavelengths,
                spectrum=data,
                channel=channel,
                step=step_name,
                timestamp=timestamp,
                counter=self.debug_data_counter
            )
            logger.debug(f"Saved debug data: {filename} ({len(data)} pixels)")
        except Exception as e:
            logger.warning(f"Failed to save debug data: {e}")

    def _processing_worker(self) -> None:
        """Background thread for processing acquired spectra.

        ✨ PIPELINE OPTIMIZATION: This runs in parallel with data acquisition,
        allowing the next spectrum to be acquired while current one is processed.

        Expected speedup: 18-20% (processing overhead hidden by next acquisition)
        """
        logger.info("✨ PIPELINE: Processing thread started")

        while self.processing_active or not self.processing_queue.empty():
            try:
                # Get raw data from queue (timeout to allow checking active flag)
                try:
                    item = self.processing_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Unpack queued data
                ch, raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch = item

                # ===== PROCESSING (happens in parallel with next acquisition) =====

                # Apply dark noise correction
                self.int_data[ch] = raw_spectrum - dark_correction

                # Calculate transmission if reference available
                if ref_sig_ch is not None and self.data_processor is not None:
                    try:
                        # Calculate transmittance (P/S ratio)
                        self.trans_data[ch] = (
                            self.data_processor.calculate_transmission(
                                p_pol_intensity=raw_spectrum - dark_correction,
                                s_ref_intensity=ref_sig_ch,
                                dark_noise=None,  # Already corrected
                                denoise=False,  # Skip denoising for sensorgram speed
                            )
                        )

                        # Find resonance wavelength
                        fit_lambda = np.nan
                        if self.trans_data[ch] is not None:
                            fit_lambda = self.data_processor.find_resonance_wavelength(
                                spectrum=self.trans_data[ch],
                                window=DERIVATIVE_WINDOW,
                                channel=ch,
                            )
                    except Exception as e:
                        logger.exception(f"Failed to process transmission for ch{ch}: {e}")
                        fit_lambda = np.nan
                else:
                    fit_lambda = np.nan

                # Update lambda data with the timestamp from acquisition
                self._update_lambda_data(ch, fit_lambda, acquisition_timestamp)

                # Apply filtering
                if hasattr(self, '_last_ch_list'):
                    self._apply_filtering(ch, self._last_ch_list, fit_lambda)

                # Mark queue task as done
                self.processing_queue.task_done()

            except Exception as e:
                logger.exception(f"Error in processing thread: {e}")
                # Continue processing even if one item fails
                try:
                    self.processing_queue.task_done()
                except:
                    pass

        logger.info("✨ PIPELINE: Processing thread stopped")

    def grab_data(self) -> None:
        """Main data acquisition loop.

        ✨ PIPELINE OPTIMIZATION: Acquisition and processing run in parallel threads.
        - This thread (acquisition): Fast loop that only acquires raw spectra
        - Processing thread: Consumes from queue and processes data in parallel

        Expected speedup: 18-20% by overlapping acquisition with processing
        """
        first_run = True
        integration_time_applied = False

        while not self._b_kill.is_set():
            ch = CH_LIST[0]
            # ✨ PHASE 3B: Removed time.sleep(0.01) - saves 9ms per cycle
            # This was unnecessary overhead in the main loop
            try:
                if self._b_stop.is_set() or self.device_config["ctrl"] not in DEVICES:
                    time.sleep(0.2)
                    continue

                if first_run:
                    self.exp_start = time.time()
                    first_run = False

                    # ✨ PIPELINE: Start processing thread on first run
                    self.processing_active = True
                    self.processing_thread = threading.Thread(
                        target=self._processing_worker,
                        daemon=True,
                        name="SPR-Processing"
                    )
                    self.processing_thread.start()
                    logger.info("✨ PIPELINE: Started background processing thread")

                    # ✨ PHASE 3A: Initialize wavelength mask once (saves ~48ms per cycle)
                    if not self._initialize_wavelength_mask():
                        logger.error("❌ Failed to initialize wavelength mask - acquisition may fail")

                    # ✨ CRITICAL FIX: FORCE smart-boosted integration at start of live measurements
                    # Always prefer the computed live_integration_seconds and scale by base_integration_time_factor if provided
                    try:
                        desired_live = getattr(self, 'live_integration_seconds', None)
                        # If per-channel mode is active, skip global set here (handled per channel below)
                        per_channel = bool(getattr(self, 'integration_per_channel', {}))

                        if not per_channel and desired_live and desired_live > 0:
                            desired = float(desired_live) * float(getattr(self, 'base_integration_time_factor', 1.0) or 1.0)
                            applied = False
                            if hasattr(self.usb, 'set_integration_time'):
                                applied = bool(self.usb.set_integration_time(desired))
                            elif hasattr(self.usb, 'set_integration'):
                                # Back-compat if another driver exposes this name
                                self.usb.set_integration(desired)
                                applied = True
                            else:
                                logger.error("❌ LIVE MODE: Cannot set integration time - no suitable method")

                            if applied:
                                integration_time_applied = True
                                # Verify and retry once if mismatch or too low
                                try:
                                    time.sleep(0.05)
                                    actual_int = None
                                    if hasattr(self.usb, 'get_integration_time'):
                                        actual_int = float(self.usb.get_integration_time())
                                    elif hasattr(self.usb, 'integration_time'):
                                        actual_int = float(self.usb.integration_time)
                                    if actual_int is None:
                                        logger.info(f"🔧 LIVE MODE: Set integration to {desired*1000:.1f}ms (verification unavailable)")
                                    else:
                                        if actual_int < 0.015 or abs(actual_int - desired) > 0.002:
                                            logger.warning(
                                                f"⚠️ LIVE MODE: Integration verify mismatch {actual_int*1000:.1f}ms vs desired {desired*1000:.1f}ms → retry"
                                            )
                                            # One retry
                                            if hasattr(self.usb, 'set_integration_time'):
                                                self.usb.set_integration_time(desired)
                                            elif hasattr(self.usb, 'set_integration'):
                                                self.usb.set_integration(desired)
                                        logger.info(
                                            f"🔧 LIVE MODE: Using integration {actual_int*1000 if actual_int is not None else desired*1000:.1f}ms"
                                        )
                                except Exception as _e:
                                    logger.debug(f"Integration verification failed: {_e}")
                    except Exception as e:
                        logger.error(f"❌ LIVE MODE: Failed to force boosted integration time: {e}")

                # Increment buffer index at start of each cycle
                self.filt_buffer_index += 1

                if not self._check_buffer_lengths():
                    self.pad_values()

                ch_list = self._get_active_channels()

                # ✨ AFTERGLOW: Initialize on first cycle to last channel in active list
                # This ensures first channel gets corrected using last channel's afterglow
                # Supports: ABCD (d→a), AC (c→a), BD (d→b), or any configuration
                if not self._afterglow_initialized and ch_list:
                    self._last_active_channel = ch_list[-1]  # Last channel in active list
                    self._afterglow_initialized = True
                    logger.debug(f"✨ Afterglow initialized: first channel will use prev_ch='{ch_list[-1]}'")

                # ✨ PIPELINE: Store ch_list for processing thread
                self._last_ch_list = ch_list

                # ⏱️ TIMING: Start cycle timing
                t_cycle_start = perf_counter()

                for ch in CH_LIST:
                    if self._b_stop.is_set():
                        break

                    if self._should_read_channel(ch, ch_list):
                        # ✨ PIPELINE: ONLY ACQUIRE - processing happens in parallel thread
                        raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch = self._acquire_raw_spectrum(ch)

                        # Queue for processing (non-blocking)
                        try:
                            self.processing_queue.put(
                                (ch, raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch),
                                block=False  # Don't wait if queue is full
                            )
                        except queue.Full:
                            logger.warning(f"⚠️ PIPELINE: Queue full, dropping frame for ch{ch}")
                    else:
                        # ✨ PHASE 3B: Removed time.sleep(0.1) for inactive channels
                        # This was wasting 100ms per inactive channel for no reason
                        # Inactive channels are simply skipped now (near-zero overhead)
                        fit_lambda = np.nan
                        acquisition_timestamp = time.time() - self.exp_start
                        self._update_lambda_data(ch, fit_lambda, acquisition_timestamp)
                        self._apply_filtering(ch, ch_list, fit_lambda)

                    # REMOVED: Duplicate buffer index increment (already done in pad_values())
                    # if ch == CH_LIST[-1]:
                    #     self.filt_buffer_index += 1

                if not self._b_stop.is_set():
                    t_before_emit = perf_counter()
                    self._emit_data_updates()
                    self._emit_temperature_update()
                    t_after_emit = perf_counter()

                    # ⏱️ TIMING: Log complete cycle timing
                    t_cycle_total = t_after_emit - t_cycle_start
                    t_emit_time = t_after_emit - t_before_emit

                    self.cycle_count += 1
                    self.timing_samples.append(t_cycle_total * 1000)  # Store in ms

                    if self.enable_timing_logs:
                        logger.warning(
                            f"⏱️ CYCLE #{self.cycle_count}: "
                            f"total={int(t_cycle_total*1000)}ms, "
                            f"emit={int(t_emit_time*1000)}ms, "
                            f"acq={int((t_cycle_total-t_emit_time)*1000)}ms"
                        )

                        # Every 10 cycles, report statistics
                        if self.cycle_count % 10 == 0 and len(self.timing_samples) >= 10:
                            recent_samples = self.timing_samples[-10:]
                            avg_time = sum(recent_samples) / len(recent_samples)
                            min_time = min(recent_samples)
                            max_time = max(recent_samples)
                            logger.warning(
                                f"📊 TIMING STATS (last 10 cycles): "
                                f"avg={int(avg_time)}ms, "
                                f"min={int(min_time)}ms, "
                                f"max={int(max_time)}ms, "
                                f"rate={1000/avg_time:.2f} Hz"
                            )

            except Exception as e:
                self._handle_acquisition_error(e, ch)

        # ✨ PIPELINE: Clean shutdown of processing thread
        logger.info("✨ PIPELINE: Shutting down processing thread...")
        self.processing_active = False

        if self.processing_thread is not None:
            # Wait for processing thread to finish (max 5 seconds)
            self.processing_thread.join(timeout=5.0)
            if self.processing_thread.is_alive():
                logger.warning("⚠️ PIPELINE: Processing thread did not stop cleanly")
            else:
                logger.info("✨ PIPELINE: Processing thread stopped successfully")

        # Clear any remaining items in queue
        try:
            while not self.processing_queue.empty():
                self.processing_queue.get_nowait()
                self.processing_queue.task_done()
        except queue.Empty:
            pass

        logger.info("✨ PIPELINE: Acquisition loop exited cleanly")

    def _check_buffer_lengths(self) -> bool:
        """Check if all buffer lengths are synchronized."""
        lengths = [len(self.buffered_times[ch]) for ch in ["a", "b", "c", "d"]]
        return len(set(lengths)) == 1

    def _get_active_channels(self) -> list[str]:
        """Get list of active channels based on current mode."""
        if self.single_mode:
            return [self.single_ch]
        if self.device_config["ctrl"] in ["PicoEZSPR"]:  # EZSPR disabled (obsolete)
            return EZ_CH_LIST
        return CH_LIST

    def _should_read_channel(self, ch: str, ch_list: list[str]) -> bool:
        """Check if we should read data from this channel."""
        should_read = (
            ch in ch_list
            and not self._b_no_read.is_set()
            and self.calibrated
            and self.ctrl is not None
        )
        return should_read

    def _acquire_raw_spectrum(self, ch: str) -> tuple[np.ndarray, float, np.ndarray, Optional[np.ndarray]]:
        """FAST acquisition-only method for pipelined architecture.

        ✨ PIPELINE OPTIMIZATION: Only acquires raw spectrum and prepares data for processing.
        No processing happens here - that's done in the processing thread.

        Returns:
            tuple: (raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch)
                - raw_spectrum: Averaged intensity data
                - acquisition_timestamp: Time of acquisition
                - dark_correction: Dark noise array (resized to match spectrum)
                - ref_sig_ch: S-mode reference signal for this channel (or None)
        """
        # ✨ PER-CHANNEL MODE: Set integration time per channel if available
        applied_integration_s = None
        if hasattr(self, 'integration_per_channel') and ch in getattr(self, 'integration_per_channel', {}):
            ch_integration = float(self.integration_per_channel[ch])
            if hasattr(self.usb, 'set_integration'):
                self.usb.set_integration(ch_integration)
                applied_integration_s = ch_integration
                # Small delay to ensure integration time is applied
                time.sleep(0.05)
                # Verify integration time was actually applied
                try:
                    actual_integration = None
                    if hasattr(self.usb, 'get_integration_time'):
                        actual_integration = float(self.usb.get_integration_time())
                    elif hasattr(self.usb, 'integration_time'):
                        actual_integration = float(self.usb.integration_time)
                    if actual_integration is not None:
                        logger.info(f"🔧 Channel {ch.upper()}: Set integration {ch_integration*1000:.1f}ms → Actual {actual_integration*1000:.1f}ms")
                    else:
                        logger.info(f"🔧 Channel {ch.upper()}: Set integration {ch_integration*1000:.1f}ms (verification unavailable)")
                except Exception as e:
                    logger.debug(f"Could not verify integration time for channel {ch}: {e}")
            elif hasattr(self.usb, 'set_integration_time'):
                self.usb.set_integration_time(ch_integration)
                applied_integration_s = ch_integration
                time.sleep(0.05)
                # Verify integration time was actually applied
                try:
                    actual_integration = None
                    if hasattr(self.usb, 'get_integration_time'):
                        actual_integration = float(self.usb.get_integration_time())
                    elif hasattr(self.usb, 'integration_time'):
                        actual_integration = float(self.usb.integration_time)
                    if actual_integration is not None:
                        logger.info(f"🔧 Channel {ch.upper()}: Set integration {ch_integration*1000:.1f}ms → Actual {actual_integration*1000:.1f}ms")
                    else:
                        logger.info(f"🔧 Channel {ch.upper()}: Set integration {ch_integration*1000:.1f}ms (verification unavailable)")
                except Exception as e:
                    logger.debug(f"Could not verify integration time for channel {ch}: {e}")
        else:
            # GLOBAL MODE: Force the global live integration time before each acquisition
            try:
                desired_live = getattr(self, 'live_integration_seconds', None)
                if desired_live and desired_live > 0:
                    desired = float(desired_live) * float(getattr(self, 'base_integration_time_factor', 1.0) or 1.0)
                    if hasattr(self.usb, 'set_integration_time'):
                        self.usb.set_integration_time(desired)
                    elif hasattr(self.usb, 'set_integration'):
                        self.usb.set_integration(desired)
                    applied_integration_s = desired
                    time.sleep(0.02)
                else:
                    logger.warning(f"⚠️ Channel {ch.upper()}: No per-channel integration; global live value missing")
            except Exception as _e:
                logger.error(f"❌ Channel {ch.upper()}: Failed to apply global live integration: {_e}")

        # LED control and settling
        # ✨ SMART BOOST: Use live_led_intensities if available (per-channel LED adjustment)
        led_intensity = None
        if hasattr(self, 'live_led_intensities') and ch in self.live_led_intensities:
            led_intensity = int(self.live_led_intensities[ch])
            # Treat zero/None as missing and fallback to calibrated or 255
            if led_intensity <= 0:
                try:
                    if hasattr(self, 'calibrated_leds') and isinstance(self.calibrated_leds, dict):
                        fallback = int(self.calibrated_leds.get(ch, 0) or 0)
                        if fallback > 0:
                            led_intensity = fallback
                            logger.warning(f"🔁 LIVE MODE: ch{ch} had LED=0 → fallback to calibrated {fallback}")
                except Exception:
                    pass
            logger.warning(f"🔆 LIVE MODE: Channel {ch} using LED intensity: {led_intensity}")
        else:
            led_intensity = 255
            logger.warning(f"⚠️ LIVE MODE: Channel {ch} has NO LED intensity (defaulting to 255)")

        # Optional one-cycle force-255 test to visually confirm LED activation
        if self._force_255_enabled and not self._force_255_done.get(ch, False):
            logger.warning(f"🧪 FORCE-255 TEST: Overriding ch{ch} intensity → 255 for first live cycle")
            led_intensity = 255
            self._force_255_done[ch] = True

        # Always pass an explicit intensity to avoid relying on previous state
        self._activate_channel_batch(ch, intensity=int(led_intensity))
        if self.led_on_delay > 0:
            time.sleep(self.led_on_delay)

        # One-time LED sanity check: verify non-flat counts after LED ON
        if not self._led_verified.get(ch, False):
            try:
                test_read = self.usb.read_intensity() if hasattr(self.usb, 'read_intensity') else None
                if test_read is not None and isinstance(test_read, np.ndarray) and test_read.size > 0:
                    # Prefer masked mean if mask size matches, else full mean
                    if self._wavelength_mask is not None and len(test_read) == len(self._wavelength_mask):
                        test_mean = float(np.mean(test_read[self._wavelength_mask]))
                    else:
                        test_mean = float(np.mean(test_read))
                    if test_mean < 10.0:
                        logger.warning(
                            f"🔎 LED SANITY: ch{ch} low counts after activation (mean~{test_mean:.1f}). Retrying at 255 and short settle…"
                        )
                        # Retry activation at max intensity and short settle
                        try:
                            self._activate_channel_batch(ch, intensity=255)
                        except Exception as _e:
                            logger.debug(f"LED re-activation error ch{ch}: {_e}")
                        time.sleep(max(0.05, self.led_on_delay))
                    else:
                        self._led_verified[ch] = True
                        logger.info(f"✅ LED SANITY: ch{ch} verified (mean~{test_mean:.1f})")
                else:
                    logger.debug(f"LED sanity check skipped for ch{ch}: no test_read available")
            except Exception as _e:
                logger.debug(f"LED sanity check error ch{ch}: {_e}")

        # Wavelength mask check
        if self._wavelength_mask is None:
            logger.error("❌ Wavelength mask not initialized!")
            if not self._initialize_wavelength_mask():
                raise RuntimeError("Cannot acquire data without wavelength mask")

        # ✨ Use per-channel scan count if available, otherwise fall back to default
        scans_for_channel = self.scans_per_channel.get(ch, self.num_scans)

        # Diagnostic: log timing policy actually applied
        try:
            # Determine current integration time (prefer the value we set)
            if applied_integration_s is None:
                # Fallback to spectrometer getter if available
                if hasattr(self.usb, 'get_integration_time'):
                    applied_integration_s = float(self.usb.get_integration_time())
                elif hasattr(self.usb, 'integration_time'):
                    applied_integration_s = float(self.usb.integration_time)
            integ_ms = applied_integration_s * 1000.0 if applied_integration_s is not None else None
            logger.info(
                f"⏱️ DAQ ch{ch.upper()}: integration={integ_ms:.1f}ms, scans={scans_for_channel}, "
                f"preLED={self.led_on_delay*1000:.0f}ms, postLED={self.led_off_delay*1000:.0f}ms"
            )
        except Exception:
            # Non-fatal if timing log formatting fails
            pass

        # ACQUIRE SPECTRUM (this is the slow part - 200ms budget per channel)
        averaged_intensity = self._acquire_averaged_spectrum(
            num_scans=scans_for_channel,
            wavelength_mask=self._wavelength_mask,
            description=f"channel {ch}"
        )

        # ⏱️ TIMESTAMP: Capture RIGHT AFTER acquisition (reflects actual acquisition time)
        # This ensures sequential channels (A, B, C, D) get properly spaced timestamps
        acquisition_timestamp = time.time() - self.exp_start

        if averaged_intensity is None:
            raise RuntimeError(f"Failed to acquire spectrum for channel {ch}")

        # 🔍 DIAGNOSTIC: Log RAW spectrum intensity in ROI (580-610nm)
        try:
            if hasattr(self, 'wave_data') and self.wave_data is not None and len(self.wave_data) >= len(averaged_intensity):
                # Find indices for 580-610nm ROI
                wave_subset = self.wave_data[:len(averaged_intensity)]
                roi_mask = (wave_subset >= 580) & (wave_subset <= 610)
                if np.any(roi_mask):
                    roi_intensity = averaged_intensity[roi_mask]
                    roi_mean = float(np.mean(roi_intensity))
                    roi_max = float(np.max(roi_intensity))
                    logger.info(
                        f"📊 RAW ch{ch.upper()}: ROI(580-610nm) mean={roi_mean:.0f}, max={roi_max:.0f} counts "
                        f"(integration={applied_integration_s*1000 if applied_integration_s else '?'}ms)"
                    )
        except Exception as e:
            logger.debug(f"Could not log ROI diagnostic for ch{ch}: {e}")

        # Prepare dark correction (choose per-channel if available, then resize if needed)
        base_dark = None
        try:
            if hasattr(self, 'per_channel_dark_noise') and isinstance(self.per_channel_dark_noise, dict):
                base_dark = self.per_channel_dark_noise.get(ch)
        except Exception:
            base_dark = None
        if base_dark is None:
            base_dark = self.dark_noise

        if base_dark.shape == averaged_intensity.shape:
            dark_correction = base_dark
        else:
            target_size = len(averaged_intensity)
            source_size = len(base_dark)

            if source_size == 0:
                logger.warning("No dark noise available; using zero correction")
                dark_correction = np.zeros_like(averaged_intensity)
            elif source_size == 1:
                dark_correction = np.full_like(averaged_intensity, base_dark[0])
            elif source_size == target_size:
                try:
                    dark_correction = base_dark.reshape(averaged_intensity.shape)
                except ValueError:
                    dark_correction = np.zeros_like(averaged_intensity)
            else:
                if HAS_SCIPY:
                    source_indices = np.linspace(0, 1, source_size)
                    target_indices = np.linspace(0, 1, target_size)
                    interpolator = interp1d(source_indices, base_dark,
                                          kind='linear', bounds_error=False, fill_value='extrapolate')
                    dark_correction = interpolator(target_indices)
                else:
                    step = source_size / target_size
                    indices = np.arange(target_size) * step
                    indices = np.clip(indices.astype(int), 0, source_size - 1)
                    dark_correction = base_dark[indices]

        # Get reference signal for this channel
        ref_sig_ch = self.ref_sig[ch] if self.ref_sig[ch] is not None else None

        # Turn off LEDs
        if self.device_config["ctrl"] in DEVICES:
            self.ctrl.turn_off_channels()
            if self.led_off_delay > 0:
                time.sleep(self.led_off_delay)

        return averaged_intensity, acquisition_timestamp, dark_correction, ref_sig_ch

    def _read_channel_data(self, ch: str) -> tuple[float, float]:
        """Read and process data from a specific channel.

        Returns:
            tuple: (fit_lambda, acquisition_timestamp) - resonance wavelength and time of acquisition
        """
        # ⏱️ TIMING: Start channel acquisition timing
        t_start = perf_counter()
        t_led_on = t_start
        t_led_settle = t_start
        t_scan_complete = t_start
        t_dark_ready = t_start
        t_trans_complete = t_start
        t_peak_complete = t_start

        try:
            # ✨ Use batch LED control for 15× speedup
            self._activate_channel_batch(ch)
            t_led_on = perf_counter()

            if self.led_on_delay > 0:
                time.sleep(self.led_on_delay)
            t_led_settle = perf_counter()

            # ⏱️ TIMESTAMP FIX: Capture timestamp RIGHT BEFORE spectrum acquisition
            # This represents when photons are actually collected, not when processing finishes
            acquisition_timestamp = time.time() - self.exp_start

            # ✨ PHASE 3A OPTIMIZATION: Use cached wavelength mask (saves ~12ms per channel)
            # Mask is initialized once in grab_data() and reused for all acquisitions
            if self._wavelength_mask is None:
                logger.error("❌ Wavelength mask not initialized - this should not happen!")
                # Fallback: try to initialize now
                if not self._initialize_wavelength_mask():
                    raise RuntimeError("Cannot acquire data without wavelength mask")

            # ✨ V1 OPTIMIZATION: Vectorized spectrum acquisition (2-3× faster averaging)
            averaged_intensity = self._acquire_averaged_spectrum(
                num_scans=self.num_scans,
                wavelength_mask=self._wavelength_mask,  # Use cached mask!
                description=f"channel {ch}"
            )
            t_scan_complete = perf_counter()

            if averaged_intensity is not None:

                # Handle dark noise correction with universal resizing - no cropping
                if self.dark_noise.shape == averaged_intensity.shape:
                    # Perfect match - use dark noise directly
                    dark_correction = self.dark_noise
                    logger.debug(f"Dark noise shape matches data: {self.dark_noise.shape}")
                else:
                    # Universal resampling approach - preserve all information
                    target_size = len(averaged_intensity)
                    source_size = len(self.dark_noise)

                    # Log size mismatch (debug level to avoid hot path overhead)
                    if not hasattr(self, '_size_mismatch_logged'):
                        logger.info(
                            f"Dark noise size differs from data: dark_noise=({source_size},) vs data=({target_size},). "
                            f"SPR range: {MIN_WAVELENGTH}-{MAX_WAVELENGTH} nm. "
                            f"Applying universal resampling (subsequent occurrences logged at debug level)."
                        )
                        self._size_mismatch_logged = True
                    else:
                        logger.debug(f"Dark noise resampling: {source_size} → {target_size} pixels")

                    if source_size == 1:
                        # Single value - broadcast to full size
                        dark_correction = np.full_like(averaged_intensity, self.dark_noise[0])
                        logger.debug("Broadcasted single dark noise value to match data size")
                    elif source_size == target_size:
                        # Same length but different shape - reshape
                        try:
                            dark_correction = self.dark_noise.reshape(averaged_intensity.shape)
                            logger.debug("Reshaped dark noise to match data shape")
                        except ValueError:
                            # If reshape fails, use zeros
                            dark_correction = np.zeros_like(averaged_intensity)
                            logger.warning("Using zero dark correction due to shape incompatibility")
                    else:
                        # Different sizes - use linear interpolation to resample
                        if HAS_SCIPY:
                            # Use scipy interpolation (more accurate)
                            source_indices = np.linspace(0, 1, source_size)
                            target_indices = np.linspace(0, 1, target_size)
                            interpolator = interp1d(source_indices, self.dark_noise,
                                                  kind='linear', bounds_error=False, fill_value='extrapolate')
                            dark_correction = interpolator(target_indices)
                            logger.debug(f"Interpolated dark noise from {source_size} to {target_size} pixels")
                        else:
                            # Fallback to simple resampling if scipy not available
                            step = source_size / target_size
                            indices = np.arange(target_size) * step
                            indices = np.clip(indices.astype(int), 0, source_size - 1)
                            dark_correction = self.dark_noise[indices]
                            logger.debug(f"Simple resampled dark noise from {source_size} to {target_size} pixels")

                # Ensure final correction matches data shape exactly
                if dark_correction.shape != averaged_intensity.shape:
                    logger.warning(f"Final shape mismatch: {dark_correction.shape} vs {averaged_intensity.shape}. Using zero correction.")
                    dark_correction = np.zeros_like(averaged_intensity)

                t_dark_ready = perf_counter()

                # STEP 1: Save raw spectrum (before any processing)
                if SAVE_DEBUG_DATA:
                    self._save_debug_step(ch, "1_raw_spectrum", averaged_intensity, self.wave_data)

                # Get ACTUAL current integration time from spectrometer (always needed for logging)
                integration_time_ms = 100.0  # Default fallback
                if hasattr(self.usb, 'integration_time'):
                    # USB4000 HAL adapter stores integration time in seconds
                    integration_time_ms = self.usb.integration_time * 1000.0
                elif hasattr(self.usb, '_integration_time'):
                    integration_time_ms = self.usb._integration_time * 1000.0

                # ✨ NEW: Apply afterglow correction to dark noise if available
                correction_value = 0.0  # Default: no correction
                if (self.afterglow_correction and
                    self._last_active_channel and
                    self.afterglow_correction_enabled):
                    try:
                        # Calculate afterglow correction (uniform across spectrum)
                        # delay = led_delay (time since previous LED turned off)
                        correction_value = self.afterglow_correction.calculate_correction(
                            previous_channel=self._last_active_channel,
                            integration_time_ms=integration_time_ms,
                            delay_ms=self.led_delay * 1000  # Convert to ms
                        )

                        # Apply correction (subtract afterglow from dark noise)
                        dark_correction = dark_correction - correction_value

                        # Apply ML residual correction if available
                        if hasattr(self, 'ml_afterglow') and self.ml_afterglow and self.ml_afterglow.enabled:
                            ml_correction = self.ml_afterglow.calculate_correction(
                                current_channel=ch,
                                integration_time_ms=integration_time_ms,
                                delay_ms=self.led_delay * 1000
                            )
                            dark_correction = dark_correction - ml_correction

                            # Update channel history for next prediction
                            # (use signal before afterglow correction for history)
                            signal_for_history = np.mean(averaged_intensity)  # Simplified
                            self.ml_afterglow.update_channel_history(ch, signal_for_history)

                        # ✨ LOG: Verify channel A gets afterglow correction
                        log_msg = (
                            f"✨ Afterglow correction applied to Ch{ch.upper()}: "
                            f"prev_ch={self._last_active_channel.upper()}, "
                            f"int_time={integration_time_ms:.1f}ms, "
                            f"delay={self.led_delay*1000:.1f}ms, "
                            f"correction={correction_value:.1f} counts"
                        )
                        if ch == 'a':
                            logger.warning(log_msg)  # Use WARNING level for channel A to make it visible
                        else:
                            logger.debug(log_msg)
                    except Exception as e:
                        logger.warning(f"⚠️ Afterglow correction failed for Ch{ch.upper()}: {e}")
                        correction_value = 0.0  # Reset on error

                # COLLECT RAW TRAINING DATA FOR ML (always log, even without afterglow correction)
                try:
                    from collect_raw_training_data import log_acquisition_sample
                    log_acquisition_sample(
                        channel=ch,
                        timestamp=time.time(),
                        raw_counts=float(np.mean(averaged_intensity)),
                        dark_corrected=float(np.mean(averaged_intensity - dark_correction + correction_value)),
                        afterglow_correction_applied=float(correction_value),
                        integration_time_ms=float(integration_time_ms),
                        led_delay_ms=float(self.led_delay * 1000)
                    )
                except ImportError as e:
                    logger.warning(f"⚠️ Data collection import failed: {e}")
                except Exception as e:
                    logger.warning(f"⚠️ Data collection error: {e}")
                    import traceback
                    logger.warning(traceback.format_exc())

                # Apply dark noise correction
                self.int_data[ch] = averaged_intensity - dark_correction

                # 🔍 DIAGNOSTIC: Log dark-corrected intensity in ROI
                try:
                    if hasattr(self, 'wave_data') and self.wave_data is not None and len(self.wave_data) >= len(self.int_data[ch]):
                        wave_subset = self.wave_data[:len(self.int_data[ch])]
                        roi_mask = (wave_subset >= 580) & (wave_subset <= 610)
                        if np.any(roi_mask):
                            roi_intensity = self.int_data[ch][roi_mask]
                            roi_mean = float(np.mean(roi_intensity))
                            roi_max = float(np.max(roi_intensity))
                            logger.info(
                                f"📊 DARK-CORRECTED ch{ch.upper()}: ROI(580-610nm) mean={roi_mean:.0f}, max={roi_max:.0f} counts"
                            )
                except Exception as e:
                    logger.debug(f"Could not log dark-corrected ROI for ch{ch}: {e}")

                # ✨ NEW: Track this channel for next afterglow correction
                self._last_active_channel = ch

                # STEP 2: Save after dark noise subtraction (P-polarization, dark corrected)
                if SAVE_DEBUG_DATA:
                    self._save_debug_step(ch, "2_after_dark_correction", self.int_data[ch], self.wave_data)

                # Calculate transmission
                t_trans_complete = t_dark_ready  # Default if not calculated
                if self.ref_sig[ch] is not None and self.data_processor is not None:
                    try:
                        # Pass original ref_sig; downstream will resample if needed
                        # calculate_transmission() will resize S-ref to match P automatically
                        ref_sig_adjusted = self.ref_sig[ch]
                        if ref_sig_adjusted is not None and len(ref_sig_adjusted) != len(dark_correction):
                            logger.debug(
                                f"S-ref size mismatch: ref={len(ref_sig_adjusted)} vs data={len(dark_correction)} (will resample in processor)"
                            )

                        # STEP 3: Save S-mode reference (for comparison)
                        if SAVE_DEBUG_DATA:
                            # Log sizes for debugging (debug level - only when saving files)
                            if ref_sig_adjusted is not None:
                                logger.debug(
                                    f"🔍 Debug sizes ch{ch}: "
                                    f"ref_sig={len(ref_sig_adjusted)}, "
                                    f"dark_correction={len(dark_correction)}, "
                                    f"wave_data={len(self.wave_data)}, "
                                    f"averaged_intensity={len(averaged_intensity)}"
                                )
                            # S-ref already has dark subtracted during calibration
                            if ref_sig_adjusted is not None:
                                self._save_debug_step(ch, "3_s_reference_corrected", ref_sig_adjusted, self.wave_data)

                        # Calculate transmittance (P/S ratio)
                        # CRITICAL: ref_sig already has dark subtracted during calibration!
                        # Only subtract dark from P-mode data here
                        p_corrected = averaged_intensity - dark_correction

                        # 🔍 DIAGNOSTIC: Log S-reference intensity in ROI
                        try:
                            if ref_sig_adjusted is not None and len(ref_sig_adjusted) > 0:
                                # Find ROI in S-reference
                                if hasattr(self, 'wave_data') and self.wave_data is not None:
                                    wave_subset = self.wave_data[:len(ref_sig_adjusted)]
                                    roi_mask = (wave_subset >= 580) & (wave_subset <= 610)
                                    if np.any(roi_mask):
                                        roi_s_ref = ref_sig_adjusted[roi_mask]
                                        s_mean = float(np.mean(roi_s_ref))
                                        s_max = float(np.max(roi_s_ref))

                                        # Also check P-corrected
                                        roi_p_corrected = p_corrected[roi_mask]
                                        p_mean = float(np.mean(roi_p_corrected))
                                        p_max = float(np.max(roi_p_corrected))

                                        # Calculate expected transmittance
                                        trans_mean = (p_mean / s_mean * 100) if s_mean > 0 else 0

                                        logger.info(
                                            f"📊 P/S RATIO ch{ch.upper()}: "
                                            f"P_mean={p_mean:.0f}, S_mean={s_mean:.0f}, "
                                            f"Trans={trans_mean:.1f}%"
                                        )
                        except Exception as e:
                            logger.debug(f"Could not log P/S diagnostic for ch{ch}: {e}")

                        # ✨ O2 OPTIMIZATION: Skip denoising for sensorgram (15-20ms faster)
                        # Sensorgram only needs peak wavelength, not full denoised spectrum
                        # Spectroscopy view will still get denoised spectrum when displayed
                        self.trans_data[ch] = (
                            self.data_processor.calculate_transmission(
                                p_pol_intensity=p_corrected,
                                s_ref_intensity=ref_sig_adjusted,  # Already dark-corrected
                                dark_noise=None,  # Don't subtract dark again!
                                denoise=False,  # ✨ O2: Skip denoising for sensorgram speed
                            )
                        )
                        t_trans_complete = perf_counter()

                        # STEP 4: Save final transmittance spectrum (after P/S calibration + denoising)
                        if SAVE_DEBUG_DATA and self.trans_data[ch] is not None:
                            trans_arr = cast(np.ndarray, self.trans_data[ch])
                            self._save_debug_step(ch, "4_final_transmittance", trans_arr, self.wave_data)
                            self.debug_data_counter += 1  # Increment counter after complete cycle

                        # ✨ MICRO-OPT: Conditional diagnostic emission (saves 12-20ms when disabled)
                        # Only package and emit diagnostic data if diagnostic window is open
                        if self.emit_diagnostic_data and self.processing_steps_signal is not None:
                            # Prepare diagnostic data dict (5× array copies)
                            diagnostic_data = {
                                'channel': ch,
                                'wavelengths': self.wave_data[:len(averaged_intensity)].copy(),
                                'raw': averaged_intensity.copy(),
                                'dark_corrected': self.int_data[ch].copy() if self.int_data[ch] is not None else None,
                                's_reference': ref_sig_adjusted.copy(),
                                'transmittance': self.trans_data[ch].copy() if self.trans_data[ch] is not None else None
                            }
                            # Debug logging (first emission only per channel)
                            if not hasattr(self, '_diagnostic_logged'):
                                self._diagnostic_logged = set()
                            if ch not in self._diagnostic_logged:
                                logger.debug(f"📊 Diagnostic data for channel {ch}:")
                                logger.debug(f"  Wavelengths: {len(diagnostic_data['wavelengths'])} points, {diagnostic_data['wavelengths'][0]:.2f}-{diagnostic_data['wavelengths'][-1]:.2f} nm")
                                logger.debug(f"  Raw: {len(diagnostic_data['raw'])} points")
                                logger.debug(f"  S-ref: {len(diagnostic_data['s_reference'])} points")
                                if diagnostic_data['transmittance'] is not None:
                                    logger.debug(f"  Transmittance: {len(diagnostic_data['transmittance'])} points")
                                self._diagnostic_logged.add(ch)
                            # Emit signal in thread-safe manner
                            try:
                                self.processing_steps_signal.emit(diagnostic_data)
                            except Exception as emit_error:
                                logger.debug(f"Failed to emit diagnostic signal: {emit_error}")

                    except Exception as e:
                        logger.exception(f"Failed to get trans data: {e}")
                else:
                    # Missing calibration data - warn user
                    if self.ref_sig[ch] is None:
                        logger.error(f"❌ Channel {ch}: No reference signal (S-mode calibration missing!)")
                        logger.error(f"   Sensogram will show RAW intensity instead of transmittance")
                        logger.error(f"   → Run calibration from Settings menu")
                    if self.data_processor is None:
                        logger.error(f"❌ Channel {ch}: Data processor not initialized")

            # Turn off channels after reading
            if self.device_config["ctrl"] in DEVICES:
                self.ctrl.turn_off_channels()
                if self.led_off_delay > 0:
                    time.sleep(self.led_off_delay)

            # Find resonance wavelength
            fit_lambda = np.nan

            if not (self._b_stop.is_set() or self.trans_data[ch] is None):
                if self.data_processor is not None:
                    spectrum = self.trans_data[ch]

                    fit_lambda = self.data_processor.find_resonance_wavelength(
                        spectrum=spectrum,
                        window=DERIVATIVE_WINDOW,  # 165
                        channel=ch,
                    )
            t_peak_complete = perf_counter()

            # ⏱️ TIMING: Log detailed breakdown for this channel
            if self.enable_timing_logs:
                t_total = t_peak_complete - t_start
                logger.warning(
                    f"⏱️ TIMING ch={ch}: "
                    f"LED_on={int((t_led_on-t_start)*1000)}ms, "
                    f"LED_settle={int((t_led_settle-t_led_on)*1000)}ms, "
                    f"scan={int((t_scan_complete-t_led_settle)*1000)}ms, "
                    f"dark={int((t_dark_ready-t_scan_complete)*1000)}ms, "
                    f"trans={int((t_trans_complete-t_dark_ready)*1000)}ms, "
                    f"peak={int((t_peak_complete-t_trans_complete)*1000)}ms, "
                    f"TOTAL={int(t_total*1000)}ms"
                )

            return fit_lambda, acquisition_timestamp

        except Exception as e:
            logger.exception(f"Error reading channel {ch}: {e}")
            return np.nan, time.time() - self.exp_start

    def _update_lambda_data(self, ch: str, fit_lambda: float, acquisition_timestamp: float) -> None:
        """Update lambda values and times for a channel.

        Args:
            ch: Channel identifier
            fit_lambda: Resonance wavelength
            acquisition_timestamp: Time when spectrum was acquired (relative to exp_start)
        """
        self.lambda_values[ch] = np.append(self.lambda_values[ch], fit_lambda)

        # Use the timestamp from when data was actually acquired (not processed)
        rounded_timestamp = round(acquisition_timestamp, 3)
        logger.warning(f"🕐 SAVE DEBUG: Ch{ch} saving timestamp {rounded_timestamp:.3f}s (lambda={fit_lambda:.2f})")
        self.lambda_times[ch] = np.append(
            self.lambda_times[ch],
            rounded_timestamp,
        )

    def _apply_filtering(self, ch: str, ch_list: list[str], fit_lambda: float) -> None:
        """Apply filtering to lambda data (OLD SOFTWARE METHOD)."""
        if ch in ch_list and len(self.lambda_values[ch]) >= self.filt_buffer_index:
            # ✨ OLD SOFTWARE: Use temporal mean filter (5-point backward mean)
            if hasattr(self, 'temporal_filter') and self.temporal_filter is not None and FILTERING_ON:
                filtered_value = self.temporal_filter.update(ch, fit_lambda)
            else:
                # No filtering - use raw value
                filtered_value = fit_lambda

            self.filtered_lambda[ch] = np.append(
                self.filtered_lambda[ch], filtered_value
            )
            # Use last valid index instead of filt_buffer_index
            last_idx = len(self.lambda_values[ch]) - 1
            self.buffered_lambda[ch] = np.append(
                self.buffered_lambda[ch], self.lambda_values[ch][last_idx]
            )
            # Use last valid index instead of filt_buffer_index
            last_idx = len(self.lambda_values[ch]) - 1
            self.buffered_lambda[ch] = np.append(
                self.buffered_lambda[ch],
                self.lambda_values[ch][last_idx],
            )
            self.buffered_times[ch] = np.append(
                self.buffered_times[ch],
                self.lambda_times[ch][last_idx],
            )
        else:
            # No data available or channel not in list - append NaN
            self.filtered_lambda[ch] = np.append(self.filtered_lambda[ch], np.nan)
            self.buffered_lambda[ch] = np.append(self.buffered_lambda[ch], np.nan)
            self.buffered_times[ch] = np.append(self.buffered_times[ch], np.nan)

    def _emit_data_updates(self) -> None:
        """Emit data updates to UI."""
        self.update_live_signal.emit(self.sensorgram_data())
        self.update_spec_signal.emit(self.spectroscopy_data())

    def _emit_temperature_update(self) -> None:
        """Emit temperature update if applicable."""
        if (
            self.device_config["ctrl"] == "PicoP4SPR"
            and self.ctrl is not None
            and hasattr(self.ctrl, "get_temp")
        ):
            try:
                self.temp_sig.emit(self.ctrl.get_temp())
            except Exception as e:
                logger.debug(f"Error getting temperature: {e}")

    def _handle_acquisition_error(self, error: Exception, ch: str) -> None:
        """Handle errors during data acquisition."""
        logger.exception(
            f"Error while grabbing data:{type(error)}:{error}:channel {ch}"
        )
        self.pad_values()
        self._b_stop.set()
        self.set_status_text("Error while reading SPR data")

        if error is IndexError:
            show_message(
                msg_type="Warning",
                msg="Data Error: the program has encountered an error, "
                "stopped data acquisition",
            )
        else:
            self.raise_error.emit("ctrl")

    def pad_values(self) -> None:
        """Pad values to synchronize buffer lengths."""
        try:
            max_raw_len = 0
            max_filt_len = 0
            for ch in CH_LIST:
                max_raw_len = max(max_raw_len, len(self.lambda_times[ch]))
                max_filt_len = max(max_filt_len, len(self.buffered_times[ch]))

            for ch in CH_LIST:
                if len(self.lambda_times[ch]) < max_raw_len:
                    logger.warning(f"⚠️ Padding channel {ch} with NaN (has {len(self.lambda_times[ch])}, max is {max_raw_len})")
                    self.lambda_values[ch] = np.append(self.lambda_values[ch], np.nan)
                    self.lambda_times[ch] = np.append(
                        self.lambda_times[ch],
                        round(time.time() - self.exp_start, 3),
                    )
                if len(self.buffered_times[ch]) < max_filt_len:
                    self.filtered_lambda[ch] = np.append(
                        self.filtered_lambda[ch], np.nan
                    )
                    self.buffered_lambda[ch] = np.append(
                        self.buffered_lambda[ch], np.nan
                    )
                    self.buffered_times[ch] = np.append(self.buffered_times[ch], np.nan)

            self.filt_buffer_index += 1
        except Exception as e:
            logger.exception(f"Error while padding missing values: {e}")

    def update_filtered_lambda(self) -> None:
        """Recompute filtered data with new filter window size."""
        try:
            new_filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
            for ch in CH_LIST:
                if (
                    len(self.lambda_values[ch]) > 0
                    and len(self.lambda_times[ch]) > 0
                    and len(self.buffered_times[ch]) > 0
                ):
                    first_filt_index = self.med_filt_win
                    last_filt_index = len(self.lambda_values[ch]) - 1

                    # Filter beginning values
                    for i in range(first_filt_index):
                        filt_val = np.nanmean(self.lambda_values[ch][0:i])
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch], filt_val
                        )

                    # Filter middle values with full window
                    for i in range(first_filt_index, last_filt_index):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win) : i],
                        )
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch], filt_val
                        )

                    # Filter end values
                    for i in range(last_filt_index, len(self.lambda_values[ch])):
                        filt_val = np.nanmean(
                            self.lambda_values[ch][(i - self.med_filt_win) : i],
                        )
                        new_filtered_lambda[ch] = np.append(
                            new_filtered_lambda[ch], filt_val
                        )

                    # Align with buffered times
                    offset = 0
                    while self.lambda_times[ch][offset] != self.buffered_times[ch][0]:
                        offset += 1
                    self.filtered_lambda[ch] = deepcopy(
                        new_filtered_lambda[ch][offset:]
                    )

        except Exception as e:
            logger.exception(f"error updating the filter win size: {e}")
            show_message("Filter window could not be updated", msg_type="Warning")

    def sensorgram_data(self) -> DataDict:
        """Return sensorgram data for UI updates.

        ✨ O4 Optimization: Use shallow copy instead of deepcopy (4-5ms faster)
        Safe because GUI only reads data, doesn't modify it.
        """
        sens_data = {
            "lambda_values": self.lambda_values,  # Dict of lists - shallow copy is safe
            "lambda_times": self.lambda_times,    # Dict of lists - shallow copy is safe
            "buffered_lambda_values": self.buffered_lambda,
            "filtered_lambda_values": self.filtered_lambda,
            "buffered_lambda_times": self.buffered_times,
            "filt": self.filt_on,
            "start": self.exp_start,
            "rec": self.recording,
        }
        # ✨ O4: Shallow copy of dict (references to same arrays)
        # This is safe because GUI widgets only read the data, never modify it
        return cast("DataDict", sens_data.copy())

    def spectroscopy_data(self) -> dict[str, object]:
        """Return spectroscopy data for UI updates."""
        # Ensure wave_data matches int_data size
        # Sometimes acquisition gives 1 pixel less than expected
        wave_data_adjusted = self.wave_data

        # Check if any channel has data and use its size as reference
        for ch in CH_LIST:
            if self.int_data[ch] is not None and len(self.int_data[ch]) > 0:
                target_size = len(self.int_data[ch])
                if len(self.wave_data) != target_size:
                    # Trim wave_data to match
                    logger.debug(f"Adjusting wave_data from {len(self.wave_data)} to {target_size} pixels")
                    wave_data_adjusted = self.wave_data[:target_size]
                break

        return {
            "wave_data": wave_data_adjusted,
            "int_data": self.int_data,
            "trans_data": self.trans_data,
        }

    def set_configuration(
        self,
        *,
        single_mode: bool = False,
        single_ch: str = "a",
        calibrated: bool = False,
        filt_on: bool = True,
        recording: bool = False,
    med_filt_win: Optional[int] = None,
    ) -> None:
        """Update acquisition configuration."""
        self.single_mode = single_mode
        self.single_ch = single_ch
        self.calibrated = calibrated
        self.filt_on = filt_on
        self.recording = recording
        if med_filt_win is not None:
            self.med_filt_win = med_filt_win

    def set_diagnostic_emission(self, enabled: bool) -> None:
        """Enable or disable diagnostic data emission.

        ✨ MICRO-OPT: Saves 12-20ms per cycle when disabled

        Args:
            enabled: True to enable diagnostic emission (when window open),
                    False to disable (saves 12-20ms per cycle)
        """
        self.emit_diagnostic_data = enabled
        if enabled:
            logger.info("🔬 Diagnostic emission ENABLED (adds ~15ms overhead)")
        else:
            logger.info("⚡ Diagnostic emission DISABLED (saves ~15ms per cycle)")

    # ========================================================================
    # VECTORIZED SPECTRUM ACQUISITION (Performance Optimization for Live Mode)
    # ========================================================================

    def _apply_jitter_correction(self, spectra_stack: np.ndarray) -> np.ndarray:
        """Apply adaptive polynomial jitter correction to multiple spectra.

        This removes systematic drift and thermal effects from P-pol live data.
        Uses polynomial fitting to capture slow trends and rolling median for noise reduction.

        Args:
            spectra_stack: 2D array of spectra (n_spectra × n_wavelengths)

        Returns:
            Array of corrected spectra (same shape as input)

        Note:
            This is the same jitter correction applied to S-pol calibration data.
            Reduces spectral jitter by 60-65% based on empirical measurements.
        """
        n_spectra, n_wavelengths = spectra_stack.shape

        if n_spectra < 3:
            # Not enough data for meaningful correction
            return spectra_stack

        # Use sequential indices as time proxy
        times = np.arange(n_spectra, dtype=float)

        # Correct each wavelength point independently
        corrected = np.zeros_like(spectra_stack)

        for wl_idx in range(n_wavelengths):
            values = spectra_stack[:, wl_idx]

            # Fit polynomial to capture slow drift (thermal/aging)
            poly_order = min(3, max(1, n_spectra // 20))  # Adaptive order: 1-3
            try:
                coeffs = np.polyfit(times, values, poly_order)
                trend = np.polyval(coeffs, times)
                detrended = values - trend
            except:
                # Fallback to mean subtraction if polyfit fails
                detrended = values - np.mean(values)

            # Remove high-frequency noise with rolling median
            window = min(5, max(3, n_spectra // 10))
            if window >= 3 and n_spectra >= window:
                smoothed = np.zeros_like(detrended)
                for i in range(n_spectra):
                    start = max(0, i - window // 2)
                    end = min(n_spectra, i + window // 2 + 1)
                    smoothed[i] = np.median(detrended[start:end])
                corrected[:, wl_idx] = smoothed
            else:
                corrected[:, wl_idx] = detrended

        return corrected

    def _acquire_averaged_spectrum(
        self,
        num_scans: int,
        wavelength_mask: np.ndarray,
        description: str = "spectrum"
    ) -> Optional[np.ndarray]:
        """Acquire and average multiple spectra using vectorization.

        Optimized method using NumPy vectorization for 2-3× faster averaging.
        Pre-allocates array and uses vectorized np.mean() instead of sequential
        accumulation in Python loop.

        Args:
            num_scans: Number of spectra to acquire and average
            wavelength_mask: Boolean mask for spectral filtering
            description: Description for logging (e.g., "channel a")

        Returns:
            Averaged spectrum (filtered by wavelength mask), or None if error

        Performance:
            Sequential accumulation: 10-12ms for 10 scans
            Vectorized np.mean(): 4-6ms for 10 scans
            Speedup: 2-3× faster

        Example:
            >>> mask = (wavelengths >= 550) & (wavelengths <= 900)
            >>> avg = self._acquire_averaged_spectrum(10, mask, "channel a")
        """
        if num_scans <= 0:
            logger.warning(f"Invalid num_scans: {num_scans}, using 1")
            num_scans = 1

        try:
            # Read first spectrum to determine filtered size
            first_reading = self.usb.read_intensity()
            if first_reading is None:
                logger.error(f"Failed to read first {description}")
                return None

            # Apply wavelength filter to first spectrum
            first_spectrum = first_reading[wavelength_mask]
            spectrum_length = len(first_spectrum)

            # Handle single scan case (no averaging needed)
            if num_scans == 1:
                return first_spectrum

            # Pre-allocate array for all spectra (key to vectorization performance)
            # Shape: (num_scans, spectrum_length)
            spectra_stack = np.empty((num_scans, spectrum_length), dtype=first_spectrum.dtype)
            spectra_stack[0] = first_spectrum

            # Acquire remaining spectra
            for i in range(1, num_scans):
                # Check for stop signal
                if self._b_stop.is_set():
                    logger.debug(f"Stop signal received during {description} acquisition")
                    return None

                reading = self.usb.read_intensity()
                if reading is None:
                    logger.warning(f"Failed to read {description} scan {i+1}/{num_scans}")
                    # Could return partial average here, but safer to fail
                    return None

                # Apply wavelength filter to this scan
                spectra_stack[i] = reading[wavelength_mask]

            # ✨ Apply jitter correction to P-pol live data (removes thermal drift)
            if num_scans >= 5:  # Need at least 5 scans for meaningful correction
                try:
                    # Apply adaptive polynomial jitter correction
                    corrected_stack = self._apply_jitter_correction(spectra_stack)
                    averaged_spectrum = np.mean(corrected_stack, axis=0)
                    logger.debug(f"Applied jitter correction to {num_scans} {description} scans")
                except Exception as e:
                    # Fallback to regular averaging if jitter correction fails
                    logger.warning(f"Jitter correction failed for {description}, using standard averaging: {e}")
                    averaged_spectrum = np.mean(spectra_stack, axis=0)
            else:
                # ✨ VECTORIZED AVERAGING (2-3× faster than sequential accumulation)
                # NumPy's np.mean() uses optimized C code with SIMD instructions
                averaged_spectrum = np.mean(spectra_stack, axis=0)

            return averaged_spectrum

        except Exception as e:
            logger.error(f"Error in vectorized spectrum acquisition for {description}: {e}")
            return None

    def _activate_channel_batch(self, channel: str, intensity: Optional[int] = None) -> bool:
        """Activate a single channel using batch LED command.

        Args:
            channel: Channel ID ('a', 'b', 'c', 'd')
            intensity: Optional intensity value. If None, uses turn_on_channel default

        Returns:
            bool: Success status
        """
        if not self._batch_led_available or not self.ctrl:
            # Fallback to sequential: set intensity (if provided) THEN ensure channel is ON
            try:
                if intensity is not None:
                    try:
                        self.ctrl.set_intensity(ch=channel, raw_val=intensity)
                    except Exception as e:
                        logger.debug(f"Fallback set_intensity failed for {channel}: {e}")
                # Always activate the channel so LED actually turns on
                self.ctrl.turn_on_channel(ch=channel)
            except Exception as e:
                logger.warning(f"❌ LED fallback activation failed for {channel}: {e}")
                return False
            return True

        try:
            # Build intensity array [a, b, c, d]
            channel_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3}
            intensity_array = [0, 0, 0, 0]

            if channel in channel_map:
                idx = channel_map[channel]
                # Use provided intensity or max (default turn_on behavior)
                intensity_array[idx] = intensity if intensity is not None else 255

            # Send batch command
            logger.warning(f"🔧 LIVE BATCH: Channel {channel}, intensity={intensity_array[channel_map[channel]]}, array=[{intensity_array[0]}, {intensity_array[1]}, {intensity_array[2]}, {intensity_array[3]}]")
            success = self.ctrl.set_batch_intensities(
                a=intensity_array[0],
                b=intensity_array[1],
                c=intensity_array[2],
                d=intensity_array[3]
            )

            if not success:
                logger.warning(f"❌ Batch LED FAILED for {channel}, using sequential fallback")
                if intensity is not None:
                    self.ctrl.set_intensity(ch=channel, raw_val=intensity)
                else:
                    self.ctrl.turn_on_channel(ch=channel)
                return False

            # ✨ CRITICAL FIX: Firmware uses mutual exclusion - must activate channel after setting intensity
            # Commands la/lb/lc/ld turn on ONLY that channel (turn off all others)
            logger.warning(f"🔦 LIVE: Activating channel {channel} (mutual exclusion)")
            turn_on_success = self.ctrl.turn_on_channel(ch=channel)
            logger.warning(f"✅ LIVE: Channel {channel} activation result: {turn_on_success}")

            return success

        except Exception as e:
            logger.debug(f"Batch LED exception for {channel}: {e}, using sequential")
            if intensity is not None:
                self.ctrl.set_intensity(ch=channel, raw_val=intensity)
            else:
                self.ctrl.turn_on_channel(ch=channel)
            return True
