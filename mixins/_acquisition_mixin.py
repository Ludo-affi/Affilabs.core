"""AcquisitionMixin — spectrum acquisition, recording and UI update handlers.

Extracted from Application (main.py) as part of the mixin refactor.
Handles signals from DataAcquisitionManager, RecordingManager, and related
UI state helpers.
"""
from __future__ import annotations

import logging
import time

import numpy as np
from PySide6.QtCore import QTimer

from affilabs.app_config import LEAK_DETECTION_WINDOW, LEAK_THRESHOLD_RATIO

logger = logging.getLogger(__name__)


class AcquisitionMixin:
    """Mixin providing spectrum acquisition, recording & UI-update signal handlers."""

    # ------------------------------------------------------------------ #
    # Spectrum acquisition                                                 #
    # ------------------------------------------------------------------ #

    def _start_processing_thread(self):
        """Start dedicated processing thread for spectrum data.

        Separates acquisition from processing to prevent jitter in acquisition
        timing. Acquisition thread only queues data; processing thread handles
        all analysis.
        """
        import threading
        logger.debug("Starting processing thread...")
        self._processing_active = True
        self._processing_thread = threading.Thread(
            target=self._processing_worker,
            name="SpectrumProcessing",
            daemon=True,
        )
        self._processing_thread.start()
        logger.debug(f"✓ Processing thread started: {self._processing_thread.name}")

    def _stop_processing_thread(self):
        """Stop processing thread gracefully."""
        if self._processing_thread and self._processing_active:
            self._processing_active = False
            try:
                self._spectrum_queue.put(None, timeout=0.1)
            except Exception:
                pass
            self._processing_thread.join(timeout=2.0)
            logger.info("[OK] Processing thread stopped")

    def _processing_worker(self):
        """Worker thread that drains the spectrum queue and processes data."""
        import queue
        logger.info("[WORKER-THREAD] Processing worker entered; thread is running...")

        while self._processing_active:
            try:
                data = self._spectrum_queue.get(timeout=0.5)
                if data is None:
                    break
                self._process_spectrum_data(data)
                self._queue_stats["processed"] += 1
                current_size = self._spectrum_queue.qsize()
                self._queue_stats["max_size"] = max(
                    self._queue_stats["max_size"], current_size
                )
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[X] Processing worker error: {e}", exc_info=True)

        logger.info(
            f"Processing worker stopped — Stats: "
            f"{self._queue_stats['processed']} processed, "
            f"{self._queue_stats['dropped']} dropped, "
            f"max queue: {self._queue_stats['max_size']}"
        )

    def _on_spectrum_acquired(self, data: dict):
        """Acquisition callback — minimal processing, queue for worker thread.

        Runs in the acquisition thread and must be FAST:
        only timestamps and queues — all processing in the worker thread.
        """
        try:
            self._acquisition_counter += 1

            if self.experiment_start_time is None:
                self.experiment_start_time = data["timestamp"]
                # Bridge to ExperimentClock so clock.raw_elapsed_now() works
                if hasattr(self, 'clock') and self.clock is not None:
                    self.clock.start_experiment(data["timestamp"])

            data["elapsed_time"] = data["timestamp"] - self.experiment_start_time
            data["_epoch"] = self._session_epoch

            if not self._safe_queue_put(data):
                self._queue_stats["dropped"] += 1
                if self._queue_stats["dropped"] % 10 == 1:
                    logger.warning(
                        f"[WARN] Spectrum queue full - "
                        f"{self._queue_stats['dropped']} frames dropped",
                    )

        except Exception as e:
            logger.exception(f"Spectrum acquisition error: {e}")

    def _safe_queue_put(self, data: dict) -> bool:
        """Put data in the processing queue (non-blocking).

        Returns:
            True if queued successfully, False otherwise.
        """
        try:
            if self._spectrum_queue is None:
                logger.error("Spectrum queue is None, cannot queue data")
                return False
            self._spectrum_queue.put_nowait(data)
            return True
        except AttributeError as e:
            logger.error(f"Queue attribute error: {e}")
            return False
        except Exception:
            return False  # Queue full — expected under load

    def _process_spectrum_data(self, data: dict):
        """Process spectrum data in dedicated worker thread."""
        try:
            from affilabs.utils.spectrum_helpers import SpectrumHelpers
            SpectrumHelpers.process_spectrum_data(self, data)
        except Exception as e:
            logger.error(f"[MAIN] Failed to process spectrum: {e}", exc_info=True)

    def _handle_intensity_monitoring(
        self, channel: str, data: dict, timestamp: float
    ):
        """Handle intensity monitoring and leak detection."""
        intensity = data.get("intensity", 0)

        self.buffer_mgr.append_intensity_point(channel, timestamp, intensity)

        if self.hardware_mgr._calibration_passed:
            self.hardware_mgr.update_led_intensity(channel, intensity, timestamp)

        cutoff_time = timestamp - LEAK_DETECTION_WINDOW
        self.buffer_mgr.trim_intensity_buffer(channel, cutoff_time)

        time_span = self.buffer_mgr.get_intensity_timespan(channel)
        if time_span and time_span >= LEAK_DETECTION_WINDOW:
            dark_noise = getattr(self.data_mgr, "dark_noise", None)
            if dark_noise is not None:
                avg_intensity = self.buffer_mgr.get_intensity_average(channel)
                dark_threshold = np.mean(dark_noise) * LEAK_THRESHOLD_RATIO
                if avg_intensity < dark_threshold:
                    logger.warning(
                        f"Possible optical leak detected in channel "
                        f"{channel.upper()}: avg intensity {avg_intensity:.0f} "
                        f"< threshold {dark_threshold:.0f}",
                    )

    def _queue_transmission_update(self, channel: str, data: dict):
        """Queue transmission spectrum update for batch processing."""
        from affilabs.utils.spectrum_helpers import SpectrumHelpers
        SpectrumHelpers.queue_transmission_update(self, channel, data)

    def _update_sensor_iq_display(self, channel: str, sensor_iq):
        """Queue Sensor IQ display update via AL_UIUpdateCoordinator."""
        if self.ui_updates:
            self.ui_updates.queue_sensor_iq_update(channel, sensor_iq)

    def _should_update_transmission(self) -> bool:
        """Check whether transmission plot updates are meaningful."""
        cd = getattr(self.data_mgr, "calibration_data", None)
        if not cd or not getattr(cd, "s_pol_ref", None):
            return False
        if getattr(cd, "wavelengths", None) is None:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Acquisition lifecycle                                                #
    # ------------------------------------------------------------------ #

    def _on_acquisition_error(self, error: str):
        """Data acquisition error."""
        self.acquisition_events.on_acquisition_error(error)

    def _on_acquisition_pause_requested(self, pause: bool):
        """Handle acquisition pause/resume request from UI."""
        if pause:
            logger.info("Pausing live acquisition...")
            self.data_mgr.pause_acquisition()
        else:
            logger.info("Resuming live acquisition...")
            self.data_mgr.resume_acquisition()

    def _on_acquisition_started(self):
        """Acquisition has started — enable record and pause buttons."""
        self.acquisition_events.on_acquisition_started()

        # Add pending "Recording Started" marker if recording was enabled before acquisition
        if hasattr(self, '_pending_recording_marker') and self._pending_recording_marker:
            try:
                if hasattr(self.main_window, 'add_event_marker'):
                    self.main_window.add_event_marker(0.0, "Recording Started", "#00C853")
                    logger.info("Added pending 'Recording Started' marker at t=0")
            except Exception as e:
                logger.error(f"Failed to add pending recording marker: {e}")
            finally:
                self._pending_recording_marker = False

        # Update Spectroscopy sidebar status
        if (
            hasattr(self.main_window, "sidebar")
            and hasattr(self.main_window.sidebar, "subunit_status")
            and "Spectroscopy" in self.main_window.sidebar.subunit_status
        ):
            indicator = self.main_window.sidebar.subunit_status["Spectroscopy"]["indicator"]
            status_label = self.main_window.sidebar.subunit_status["Spectroscopy"]["status_label"]
            indicator.setStyleSheet(
                "font-size: 10px; color: #34C759; background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )
            status_label.setText("Running")
            status_label.setStyleSheet(
                "font-size: 13px; color: #34C759; background: transparent;"
                "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
            )

        self.experiment_start_time = None
        logger.debug("Reset experiment_start_time for new acquisition")

        self.buffer_mgr.clear_all()
        logger.debug("Cleared all data buffers")

        # Clear pause markers from previous run (schedule in main thread)
        try:
            if hasattr(self.main_window, "pause_markers") and hasattr(
                self.main_window, "full_timeline_graph"
            ):
                def clear_markers():
                    try:
                        for marker in self.main_window.pause_markers:
                            if "line" in marker:
                                try:
                                    self.main_window.full_timeline_graph.removeItem(
                                        marker["line"]
                                    )
                                except RuntimeError:
                                    pass
                        self.main_window.pause_markers = []
                    except Exception as e:
                        logger.debug(f"Could not clear pause markers: {e}")

                QTimer.singleShot(200, clear_markers)
        except Exception as e:
            logger.debug(f"Pause marker cleanup error: {e}")

    def _on_acquisition_stopped(self):
        """Acquisition has stopped — disable record and pause buttons."""
        self.acquisition_events.on_acquisition_stopped()
        
        # Clear any pending recording marker (acquisition ended before it could be placed)
        if hasattr(self, '_pending_recording_marker'):
            self._pending_recording_marker = False
        
        self.main_window.record_btn.setToolTip(
            "Start Recording\n(Enabled after calibration)"
        )
        self.main_window.pause_btn.setToolTip(
            "Pause Live Acquisition\n(Enabled after calibration)"
        )

        if self.main_window.record_btn.isChecked():
            self.main_window.record_btn.setChecked(False)
        if self.main_window.pause_btn.isChecked():
            self.main_window.pause_btn.setChecked(False)

        if hasattr(self.main_window, "sidebar") and hasattr(
            self.main_window.sidebar, "subunit_status"
        ):
            if "Spectroscopy" in self.main_window.sidebar.subunit_status:
                status_label = self.main_window.sidebar.subunit_status["Spectroscopy"][
                    "status_label"
                ]
                status_label.setText("Stopped")
                status_label.setStyleSheet(
                    "font-size: 13px; color: #86868B; background: transparent;"
                    "font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                )

        if self.recording_mgr.is_recording:
            logger.info("Stopping recording due to acquisition stop...")
            self.recording_mgr.stop_recording()

    # ------------------------------------------------------------------ #
    # Recording callbacks                                                  #
    # ------------------------------------------------------------------ #

    def _on_recording_started(self, filename: str):
        """Recording started — export current experiment state to metadata."""
        self.recording_events.on_recording_started(filename)
        self.recording_mgr.log_event("Recording Started")

        if self.recording_mgr.is_recording:
            # device_id: prefer device_config, fall back to hardware_mgr attribute
            device_id = "Unknown"
            try:
                dc = getattr(self.hardware_mgr, "device_config", None)
                if dc and hasattr(dc, "config"):
                    device_id = dc.config.get("device_info", {}).get("device_id") or "Unknown"
            except Exception:
                pass
            if device_id == "Unknown":
                device_id = getattr(self.hardware_mgr, "device_id", "Unknown") or "Unknown"
            self.recording_mgr.update_metadata("device_id", device_id)

            # operator — current logged-in user
            try:
                operator = self._get_current_user() or "Unknown"
            except Exception:
                operator = "Unknown"
            self.recording_mgr.update_metadata("operator", operator)

            # method_name — from sidebar method name label
            try:
                method_label = self._sidebar_widget("method_name_label")
                method_name = method_label.text().strip() if method_label else "Untitled Method"
                method_name = method_name or "Untitled Method"
            except Exception:
                method_name = "Untitled Method"
            self.recording_mgr.update_metadata("method_name", method_name)

            # sensor_type — chip surface chemistry selected by operator
            try:
                chip_combo = getattr(
                    getattr(self.main_window, "sidebar", None), "sensor_chip_combo", None
                )
                sensor_type = chip_combo.currentText() if chip_combo else "Unknown"
            except Exception:
                sensor_type = "Unknown"
            self.recording_mgr.update_metadata("sensor_type", sensor_type)

            for cycle in self._completed_cycles:
                legacy_export_data = {
                    "cycle_num": cycle.cycle_num,
                    "type": cycle.type,
                    "name": cycle.name,
                    "start_time": cycle.sensorgram_time or "",
                    "end_time": cycle.end_time_sensorgram or "",
                    "duration_minutes": cycle.length_minutes,
                    "status": cycle.status,
                    "note": cycle.note,
                }
                self.recording_mgr.add_cycle(legacy_export_data)

            if hasattr(self, "_flag_markers"):
                for flag in self._flag_markers:
                    flag_export_data = {
                        "type": flag.get("type", ""),
                        "channel": flag.get("channel", ""),
                        "time": flag.get("time", ""),
                        "spr": flag.get("spr", ""),
                        "timestamp": time.time(),
                    }
                    self.recording_mgr.add_flag(flag_export_data)

            logger.info("Initial experiment state exported to recording")

    def _on_recording_stopped(self):
        """Recording stopped."""
        self.recording_events.on_recording_stopped()

    def _on_recording_error(self, error: str):
        """Recording error occurred."""
        self.recording_events.on_recording_error(error)

    def _on_event_logged(self, event: str, timestamp: float):
        """Event logged to recording — add a visual marker on the timeline."""
        logger.info(f"Event: {event}")

        if hasattr(self, "main_window") and hasattr(
            self.main_window, "full_timeline_graph"
        ):
            try:
                elapsed_time = None
                if hasattr(self, "get_elapsed_time"):
                    elapsed_time = self.get_elapsed_time()

                if elapsed_time is None:
                    # If acquisition not started yet and this is "Recording Started", queue it
                    if "Recording Started" in event:
                        if not hasattr(self, '_pending_recording_marker'):
                            self._pending_recording_marker = False
                        self._pending_recording_marker = True
                        logger.info(
                            "Recording marker pending - will appear at t=0 when acquisition starts"
                        )
                    else:
                        logger.warning(
                            f"Skipping event marker - acquisition not started yet: {event}"
                        )
                    return

                if "Recording Started" in event:
                    color = "#00C853"
                elif "Cycle Start" in event:
                    color = "#2979FF"
                else:
                    color = "#FF9800"

                self.main_window.add_event_marker(elapsed_time, event, color)
            except Exception as e:
                logger.error(f"Failed to add event marker to graph: {e}")

    # ------------------------------------------------------------------ #
    # UI update helpers                                                    #
    # ------------------------------------------------------------------ #

    def _on_page_changed(self, page_index: int):
        """Handle page changes — show/hide live data dialog for Live Data page."""
        if hasattr(self, "ui_control_events") and self.ui_control_events:
            self.ui_control_events.on_page_changed(page_index)

    def _on_tab_changing(self, index):
        """Temporarily pause graph updates during tab transition."""
        self._skip_graph_updates = True
        QTimer.singleShot(200, lambda: setattr(self, "_skip_graph_updates", False))

    def _process_pending_ui_updates(self):
        """Process queued graph updates at throttled rate (1 Hz)."""
        from affilabs.utils.ui_update_helpers import UIUpdateHelpers
        UIUpdateHelpers.process_pending_ui_updates(self)

    def _update_stop_cursor_position(self, elapsed_time: float):
        """Update stop cursor position (thread-safe, from processing thread via signal)."""
        try:
            if not getattr(self.main_window, "live_data_enabled", False):
                return
            stop_cursor = self.main_window.full_timeline_graph.stop_cursor
            if getattr(stop_cursor, "moving", False):
                return
            stop_cursor.setValue(elapsed_time)
        except (AttributeError, RuntimeError):
            pass

    def _update_cycle_of_interest_graph(self):
        """Update the cycle-of-interest graph based on cursor positions."""
        from affilabs.utils.ui_update_helpers import UIUpdateHelpers
        UIUpdateHelpers.update_cycle_of_interest_graph(self)

    def _update_delta_display(self):
        """Update the delta SPR display between start and stop cursors."""
        if self.main_window.cycle_of_interest_graph.delta_display is None:
            return

        start_time = self.main_window.full_timeline_graph.start_cursor.value()
        stop_time = self.main_window.full_timeline_graph.stop_cursor.value()

        delta_values = {}
        for ch in self._idx_to_channel:
            time_data = self.buffer_mgr.cycle_data[ch].time
            spr_data = self.buffer_mgr.cycle_data[ch].spr

            if len(time_data) > 0 and len(spr_data) > 0:
                start_idx = np.argmin(np.abs(time_data - start_time))
                stop_idx = np.argmin(np.abs(time_data - stop_time))

                def get_averaged_value(center_idx, data):
                    s = max(0, center_idx - 2)
                    e = min(len(data), center_idx + 3)
                    return np.mean(data[s:e])

                start_value = get_averaged_value(start_idx, spr_data)
                stop_value = get_averaged_value(stop_idx, spr_data)
                delta_values[ch] = stop_value - start_value
            else:
                delta_values[ch] = 0.0

        if hasattr(self.main_window, '_get_delta_spr_display_text'):
            html = self.main_window._get_delta_spr_display_text(delta_values)
        else:
            html = (
                f"<b>Δ SPR: Ch A: {delta_values['a']:+.1f} RU  |  "
                f"Ch B: {delta_values['b']:+.1f} RU  |  "
                f"Ch C: {delta_values['c']:+.1f} RU  |  "
                f"Ch D: {delta_values['d']:+.1f} RU</b>"
            )
        self.main_window.cycle_of_interest_graph.delta_display.setText(html)

    # ------------------------------------------------------------------ #
    # Polarizer                                                            #
    # ------------------------------------------------------------------ #

    def _on_polarizer_toggle_clicked(self):
        """Handle polarizer toggle button — switch servo between S and P positions."""
        self.ui_control_events.on_polarizer_toggle_clicked()

    # ------------------------------------------------------------------ #
    # Display signal handlers                                              #
    # ------------------------------------------------------------------ #

    def _on_channel_filter_changed(self, channel: str):
        """Channel filter combo changed — show/hide curves on cycle-of-interest graph."""
        graph = self.main_window.cycle_of_interest_graph
        if not hasattr(graph, 'curves') or not graph.curves:
            return
        channel_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        if channel == "All":
            for curve in graph.curves:
                curve.setVisible(True)
        else:
            selected_idx = channel_map.get(channel)
            for idx, curve in enumerate(graph.curves):
                curve.setVisible(idx == selected_idx)

    def _on_marker_style_changed(self, marker: str):
        """Marker style combo changed — update data point symbols."""
        import pyqtgraph as pg
        marker_map = {'Circle': 'o', 'Triangle': 't', 'Square': 's', 'Star': 'star'}
        symbol = marker_map.get(marker, 'o')
        graph = self.main_window.cycle_of_interest_graph
        if hasattr(graph, 'curves') and graph.curves:
            for curve in graph.curves:
                curve.setSymbol(symbol)
                curve.setSymbolSize(6)
                curve.setSymbolPen(pg.mkPen('w', width=1))

    def _on_reference_changed(self, text: str):
        """Reference channel changed — delegate to ui_control_events."""
        self.ui_control_events.on_reference_changed(text)

    def _apply_reference_subtraction(self):
        """Apply reference channel subtraction to all other channels."""
        from affilabs.utils.graph_helpers import GraphHelpers

        GraphHelpers.apply_reference_subtraction(self)
