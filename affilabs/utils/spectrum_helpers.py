"""Spectrum Processing Helper Utilities.

Provides helper functions for:
- Spectrum data processing (filtering, monitoring)
- Transmission spectrum updates and queueing
- Buffer management
- Recording integration

These are utility functions extracted from the main Application class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]


class SpectrumHelpers:
    """Spectrum processing utility functions.

    Static methods for spectrum data processing and updates.
    """

    @staticmethod
    def process_spectrum_data(app: Application, data: dict) -> None:
        """Process spectrum data in dedicated worker thread (Phase 3 optimization).

        All the actual processing happens here, not in acquisition callback.
        This includes: intensity monitoring, transmission updates, buffer updates, etc.

        Args:
            app: Application instance
            data: Spectrum data dictionary

        """
        from affilabs.utils.logger import logger

        try:
            # Skip data from old sessions (before most recent clear)
            if data.get("_epoch", 0) < app._session_epoch:
                return  # Silently discard - stale data from previous session

            channel = data["channel"]
            intensity = data.get("intensity", 0)
            timestamp = data["timestamp"]
            elapsed_time = data["elapsed_time"]
            is_preview = data.get("is_preview", False)

            # Get pipeline-calculated peak from app state (set by ViewModel via signal)
            wavelength = app._latest_peaks.get(channel) if hasattr(app, '_latest_peaks') else None

            # Append to timeline data buffers
            # Skip if wavelength is None (first frame before ViewModel calculates peak)
            if wavelength is not None:
                try:
                    # Pass EMA state and alpha for live display filtering
                    app.buffer_mgr.append_timeline_point(
                        channel,
                        elapsed_time,
                        wavelength,
                        timestamp,
                        ema_state=app._ema_state,
                        ema_alpha=app._display_filter_alpha,
                    )
                except Exception:
                    pass  # Silently skip - buffer append is non-critical
            # Queue transmission spectrum update for sidebar (QC/diagnostic display)
            # ALWAYS UPDATE: Sidebar is a QC tool and should show all available data
            has_raw_data = data.get("raw_spectrum") is not None
            has_transmission = data.get("transmission_spectrum") is not None

            # QC POLICY: Always update sidebar if we have ANY data (raw or transmission)
            # Sidebar is a diagnostic tool and must show data regardless of processing issues
            if has_raw_data or has_transmission:
                try:
                    SpectrumHelpers.queue_transmission_update(app, channel, data)

                    # Update Sensor IQ display if available
                    if "sensor_iq" in data:
                        app._update_sensor_iq_display(channel, data["sensor_iq"])

                except Exception as e:
                    logger.error(f"[QUEUE] Ch {channel}: FAILED to queue update: {e}", exc_info=True)

            # Update cursor position (via signal to main thread)
            # Apply display offset to match graph shift (graph skips first point)
            try:
                display_elapsed = elapsed_time - app._display_time_offset
                app.cursor_update_signal.emit(display_elapsed)
            except Exception:
                pass

        except Exception as e:
            # TOP-LEVEL CATCH: Prevent any exception from killing the processing thread
            # Log critical processing errors only
            if not hasattr(app, "_processing_error_count"):
                app._processing_error_count = 0
            app._processing_error_count += 1
            if app._processing_error_count <= 10:  # Log first 10 errors
                import logging
                import traceback
                channel_str = data.get('channel', 'UNKNOWN') if 'data' in locals() else 'UNKNOWN'
                logging.error(f"[PROCESS ERROR] Ch {channel_str}: Spectrum processing error: {e}")
                logging.error(f"[PROCESS ERROR] Traceback: {traceback.format_exc()}")

        # Queue graph update instead of immediate update (throttled by timer)
        # DOWNSAMPLED: Only queue every Nth update
        app._sensorgram_update_counter += 1
        from affilabs.app_config import SENSORGRAM_DOWNSAMPLE_FACTOR
        should_update_graph = app._sensorgram_update_counter % SENSORGRAM_DOWNSAMPLE_FACTOR == 0

        if should_update_graph:
            try:
                # Queue the update (main thread will check if live data is enabled)
                app._pending_graph_updates[channel] = {
                    "elapsed_time": elapsed_time,
                    "channel": channel,
                }
            except Exception:
                pass  # Silently skip graph update errors

        # Record data point if recording is active
        try:
            if app.recording_mgr.is_recording:
                # Adjust time to be relative to recording start (t=0 when recording started)
                relative_time = elapsed_time - app.recording_mgr.recording_start_offset

                # Record this channel's measurement immediately (simple sequential format)
                app.recording_mgr.record_data_point({
                    'time': relative_time,  # Time relative to recording start (t=0)
                    'channel': channel,
                    'value': wavelength
                })
        except Exception:
            pass  # Silently skip recording errors

        # Update cycle of interest graph (bottom graph) - handled by UI refresh timer

    @staticmethod
    def queue_transmission_update(app: Application, channel: str, data: dict) -> None:
        """Queue transmission spectrum update for batch processing (Phase 2 optimization).

        Instead of updating plots immediately in acquisition thread, queue the data
        for batch processing in the UI timer. This prevents blocking.

        Args:
            app: Application instance
            channel: Channel letter ('a', 'b', 'c', 'd')
            data: Spectrum data dictionary containing transmission_spectrum and raw_spectrum

        """
        from affilabs.utils.logger import logger

        # Check if updates are disabled (if coordinator exists)
        if hasattr(app, 'ui_updates') and app.ui_updates is not None:
            if (
                not app.ui_updates._transmission_updates_enabled
                and not app.ui_updates._raw_spectrum_updates_enabled
            ):
                return

        transmission = data.get("transmission_spectrum")
        # Get raw spectrum using unified field name
        raw_spectrum = data.get("raw_spectrum")

        # Fallback: calculate transmission if not provided
        if transmission is None and raw_spectrum is not None and len(raw_spectrum) > 0:
            if app.data_mgr.calibration_data and app.data_mgr.calibration_data.s_pol_ref:
                ref_spectrum = app.data_mgr.calibration_data.s_pol_ref[channel]

                # Get LED intensities for this channel
                p_led = app.data_mgr.calibration_data.p_mode_intensities.get(channel)
                s_led = app.data_mgr.calibration_data.s_mode_intensities.get(channel)

                # Use SpectrumViewModel if available (Phase 1.3 integration)
                if app.spectrum_viewmodels and channel in app.spectrum_viewmodels:
                    # Get wavelengths
                    wavelengths = data.get("wavelengths", app.data_mgr.wave_data)
                    if wavelengths is None and not data.get("simulated", False):
                        pass  # Skip update if no wavelength data
                        return

                    # Get P-mode dark reference from calibration data
                    dark_ref = None
                    if app.data_mgr.calibration_data and app.data_mgr.calibration_data.dark_p:
                        dark_ref = app.data_mgr.calibration_data.dark_p.get(channel)
                        if dark_ref is None:
                            logger.warning(f"[{channel.upper()}] No P-mode dark reference in calibration data!")

                    # Process through ViewModel (handles services pipeline)
                    app.spectrum_viewmodels[channel].process_raw_spectrum(
                        channel=channel,
                        wavelengths=wavelengths,
                        p_spectrum=raw_spectrum,
                        s_reference=ref_spectrum,
                        p_led_intensity=p_led,
                        s_led_intensity=s_led,
                        dark_ref=dark_ref,
                    )
                    return  # ViewModel handles all processing and UI updates via signals

                # If ViewModel not available, skip processing - ViewModels should always be present
                logger.warning(f"ViewModel not available for channel {channel} - skipping transmission calculation")
                return

        # Queue for batch update if we have valid data
        if transmission is not None and len(transmission) > 0:
            # Unified wavelength source-of-truth: data_mgr.wave_data (set after calibration)
            wavelengths = app.data_mgr.wave_data
            if wavelengths is None:
                cd = getattr(app.data_mgr, "calibration_data", None)
                wavelengths = getattr(cd, "wavelengths", None) if cd is not None else None

            if wavelengths is None:
                # Silently skip - calibration not loaded yet
                pass
                return

            # Queue for batch processing via AL_UIUpdateCoordinator
            app.ui_updates.queue_transmission_update(
                channel, wavelengths, transmission, raw_spectrum
            )

            # === PHASE 1.1 INTEGRATION: Create domain models for type safety ===
            # Create domain models (for future use)
            raw_spectrum_model = app._dict_to_raw_spectrum(channel, data)
            processed_spectrum_model = app._dict_to_processed_spectrum(
                channel, data, transmission
            )
