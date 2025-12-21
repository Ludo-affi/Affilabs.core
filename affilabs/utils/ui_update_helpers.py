"""UI Update Helper Utilities.

Provides UI update utility functions for:
- Cycle of interest graph updates
- Pending UI update processing
- Graph cursor updates
- Display refresh operations

These are pure utility functions extracted from the main Application class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main_simplified import Application  # type: ignore[import-not-found]

import numpy as np


# Wavelength to Response Unit conversion constant
WAVELENGTH_TO_RU_CONVERSION = 355.0


class UIUpdateHelpers:
    """UI update utility functions.

    Static methods for graph updates, UI refresh operations, and display management.
    """

    @staticmethod
    def update_cycle_of_interest_graph(app: Application) -> None:
        """Update the cycle of interest graph based on cursor positions.

        Timeframe Mode has been removed; this uses legacy cursor selection only.
        Also triggers autosave when cycle region changes significantly.

        Args:
            app: Application instance

        """
        from PySide6.QtCore import QTimer  # type: ignore[import-untyped]

        # Legacy cursor-based update
        # Safety checks - don't crash if cursors not initialized or no data yet
        try:
            if not hasattr(app.main_window.full_timeline_graph, "start_cursor"):
                return
            if not hasattr(app.main_window.full_timeline_graph, "stop_cursor"):
                return
            if app.main_window.full_timeline_graph.start_cursor is None:
                return
            if app.main_window.full_timeline_graph.stop_cursor is None:
                return

            # Additional safety - check if buffer manager is ready
            if not hasattr(app, "buffer_mgr") or app.buffer_mgr is None:
                return
            if not hasattr(app, "_channel_pairs") or not app._channel_pairs:
                return

            # Check if we have ANY data at all - if buffers are empty, skip update
            has_data = False
            for ch in ["a", "b", "c", "d"]:
                if len(app.buffer_mgr.timeline_data[ch].time) > 0:
                    has_data = True
                    break
            if not has_data:
                return  # No data yet, nothing to display

        except (AttributeError, RuntimeError):
            return

        try:
            # Get cursor positions from full timeline graph
            start_time = app.main_window.full_timeline_graph.start_cursor.value()
            stop_time = app.main_window.full_timeline_graph.stop_cursor.value()

            # Check if this is a new cycle region (for autosave)
            cycle_changed = False
            if (
                not hasattr(app, "_last_cycle_bounds")
                or app._last_cycle_bounds is None
            ):
                app._last_cycle_bounds = (start_time, stop_time)
                cycle_changed = True
            else:
                last_start, last_stop = app._last_cycle_bounds
                # Consider it a new cycle if boundaries moved significantly (>5% of duration)
                duration = stop_time - start_time
                if (
                    abs(start_time - last_start) > duration * 0.05
                    or abs(stop_time - last_stop) > duration * 0.05
                ):
                    cycle_changed = True
                    app._last_cycle_bounds = (start_time, stop_time)

            # Extract data within cursor range for each channel
            for ch_letter, ch_idx in app._channel_pairs:
                cycle_time, cycle_wavelength, cycle_timestamp = (
                    app.buffer_mgr.extract_cycle_region(
                        ch_letter,
                        start_time,
                        stop_time,
                    )
                )

                if len(cycle_wavelength) == 0:
                    continue

                # Data already has EMA filtering applied (if enabled) from buffer storage
                # Calculate ╬ö SPR (baseline is first point in cycle or calibrated baseline)
                baseline = app.buffer_mgr.baseline_wavelengths[ch_letter]
                if baseline is None and len(cycle_wavelength) > 0:
                    # Use first VALID wavelength (560-720nm range for SPR)
                    for wl in cycle_wavelength:
                        if 560.0 <= wl <= 720.0:
                            baseline = wl
                            break
                    else:
                        # No valid wavelengths - use first point anyway
                        baseline = cycle_wavelength[0]
                elif baseline is None:
                    baseline = 0

                # Convert wavelength shift to RU (Response Units)
                delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

                # Store in buffer manager (with timestamps)
                app.buffer_mgr.update_cycle_data(
                    ch_letter,
                    cycle_time,
                    cycle_wavelength,
                    delta_spr,
                    cycle_timestamp,
                )

            # Apply reference subtraction if enabled
            app._apply_reference_subtraction()

            # Update graph curves with potentially subtracted data
            max_cycle_time = 0
            for ch_letter, ch_idx in app._channel_pairs:
                cycle_time = app.buffer_mgr.cycle_data[ch_letter].time
                delta_spr = app.buffer_mgr.cycle_data[ch_letter].spr

                if len(cycle_time) == 0:
                    continue

                # Match Live Sensorgram behavior: skip first point and rebase to second sample
                if len(cycle_time) > 1:
                    first_time = cycle_time[1]
                    display_cycle_time = cycle_time[1:] - first_time
                    display_delta_spr = delta_spr[1:]

                    # Apply injection alignment time shift if set (Phase 2)
                    if hasattr(app, '_channel_time_shifts') and ch_letter in app._channel_time_shifts:
                        time_shift = app._channel_time_shifts[ch_letter]
                        if time_shift != 0.0:
                            display_cycle_time = display_cycle_time + time_shift

                    if len(display_cycle_time) > 0:
                        max_cycle_time = max(max_cycle_time, display_cycle_time[-1])
                else:
                    # Not enough points to form a segment; draw nothing for now
                    display_cycle_time = []
                    display_delta_spr = []

                # Update cycle of interest graph
                curve = app.main_window.cycle_of_interest_graph.curves[ch_idx]
                curve.setData(display_cycle_time, display_delta_spr)

            # Set X-axis range to show only the cursor region and disable auto-ranging
            if max_cycle_time > 0:
                app.main_window.cycle_of_interest_graph.setXRange(0, max_cycle_time, padding=0.02)
                app.main_window.cycle_of_interest_graph.enableAutoRange(axis="x", enable=False)

            # Update Δ SPR display with current cursor-based delta values
            app._update_delta_display()

        except (
            RuntimeError,
            KeyError,
            IndexError,
            ValueError,
            TypeError,
        ):
            # Silently handle any errors during cycle update (data not ready, buffers empty, etc.)
            # This prevents crashes while data is being populated
            pass

    @staticmethod
    def process_pending_ui_updates(app: Application) -> None:
        """Process queued graph updates at throttled rate (1 Hz).

        This prevents UI freezing from excessive redraws when data arrives
        at 40+ spectra per second across 4 channels.

        During LIVE acquisition: Shows all data with simple downsampling for performance.
        During POST-RUN: Full resolution available for detailed analysis.

        Note: Graph updates continue even when "Live Data" checkbox is unchecked.
        The checkbox only controls cursor auto-follow behavior.

        Args:
            app: Application instance

        """
        from affilabs.utils.profiling import measure

        with measure("ui_update_timer"):
            # Skip updates during tab transitions to prevent UI freezing
            if app._skip_graph_updates:
                return

            # Process all pending channel updates in one batch
            for channel, update_data in app._pending_graph_updates.items():
                if update_data is None:
                    continue

                try:
                    channel_idx = app._channel_to_idx[channel]
                    curve = app.main_window.full_timeline_graph.curves[channel_idx]

                    # Get raw timeline data
                    raw_time = app.buffer_mgr.timeline_data[channel].time
                    raw_wavelength = app.buffer_mgr.timeline_data[channel].wavelength

                    # Validation checks
                    if not isinstance(raw_time, np.ndarray) or not isinstance(
                        raw_wavelength,
                        np.ndarray,
                    ):
                        continue
                    if len(raw_time) == 0 or len(raw_wavelength) == 0:
                        continue
                    if len(raw_time) != len(raw_wavelength):
                        continue

                    # Display buffered data (already has EMA filtering applied if enabled)
                    display_wavelength = raw_wavelength

                    # DISABLED: Online smoothing (for peak tracking validation)
                    # if app._filter_enabled and len(raw_wavelength) > 2:
                    #     with measure('filtering.online_smoothing'):
                    #         display_wavelength = app._apply_online_smoothing(
                    #             raw_wavelength,
                    #             app._filter_strength,
                    #             channel
                    #         )
                    # else:
                    #     display_wavelength = raw_wavelength

                    # Simple downsampling DISABLED - show full-resolution data for troubleshooting
                    # MAX_PLOT_POINTS = 2000  # Sufficient for smooth rendering at 1 Hz
                    # if len(raw_time) > MAX_PLOT_POINTS:
                    #     step = len(raw_time) // MAX_PLOT_POINTS
                    #     display_time = raw_time[::step]
                    #     display_wavelength = display_wavelength[::step]
                    # else:
                    #     display_time = raw_time
                    display_time = raw_time
                    # Keep any filtering applied above; do not overwrite

                    # Skip first point and shift time axis so displayed data starts at t=0
                    if len(display_time) > 1:
                        first_time = display_time[1]
                        display_time = display_time[1:] - first_time
                        display_wavelength = display_wavelength[1:]

                    # Update graph
                    with measure("graph_update.setData"):
                        curve.setData(display_time, display_wavelength)

                except Exception as e:
                    # Log display errors for debugging
                    print(f"[PLOT-ERROR] Ch {channel.upper()}: {e}")
                    import traceback

                    print(traceback.format_exc())

            # Clear processed updates
            app._pending_graph_updates = {"a": None, "b": None, "c": None, "d": None}

            # === UPDATE CYCLE OF INTEREST GRAPH ===
            # Update at throttled rate (1 Hz) instead of on every data point (40+ FPS)
            # This prevents crashes from heavy processing (filtering, baseline calc, etc.)
            # Always update cycle of interest graph when data is flowing
            try:
                with measure("cycle_of_interest_update"):
                    app._update_cycle_of_interest_graph()
            except (
                AttributeError,
                RuntimeError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
            ) as e:
                # Log cycle update errors for debugging
                if (
                    app._sensorgram_update_counter <= 5
                    or app._sensorgram_update_counter % 20 == 0
                ):
                    print(f"[CYCLE-ERROR]: {type(e).__name__}: {e}")
