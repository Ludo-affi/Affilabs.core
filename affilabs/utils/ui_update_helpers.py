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
            # Get cursor positions from full timeline graph (in DISPLAY coordinates)
            start_time_display = app.main_window.full_timeline_graph.start_cursor.value()
            stop_time_display = app.main_window.full_timeline_graph.stop_cursor.value()

            # CRITICAL: Convert display coordinates → raw buffer coordinates
            # Cursors live on the display plot; buffer.time stores raw elapsed.
            from affilabs.core.experiment_clock import TimeBase
            start_time_raw = app.clock.convert(start_time_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED)
            stop_time_raw = app.clock.convert(stop_time_display, TimeBase.DISPLAY, TimeBase.RAW_ELAPSED)

            # Check if this is a new cycle region (for autosave)
            cycle_changed = False
            if (
                not hasattr(app, "_last_cycle_bounds")
                or app._last_cycle_bounds is None
            ):
                app._last_cycle_bounds = (start_time_display, stop_time_display)
                cycle_changed = True
            else:
                last_start, last_stop = app._last_cycle_bounds
                # Consider it a new cycle if the START cursor moved significantly (>5% of duration).
                # Only the start cursor matters — the stop cursor naturally advances during
                # live acquisition (~1 s per update) and must NOT trigger a cycle change,
                # otherwise per-channel nudge offsets get wiped on every point update.
                duration = stop_time_display - start_time_display
                start_moved = abs(start_time_display - last_start) > max(duration * 0.05, 1.0)
                if start_moved:
                    cycle_changed = True
                    app._last_cycle_bounds = (start_time_display, stop_time_display)
                    # New cycle region — reset zoom and per-channel nudge offsets
                    graph = app.main_window.cycle_of_interest_graph
                    graph._user_zoomed = False
                    if hasattr(app.main_window, "reset_channel_time_offsets"):
                        app.main_window.reset_channel_time_offsets()
                else:
                    # Update stored stop so it tracks live growth without triggering reset
                    app._last_cycle_bounds = (last_start, stop_time_display)

            # Extract data within cursor range for each channel
            for ch_letter, ch_idx in app._channel_pairs:
                cycle_time, cycle_wavelength, cycle_timestamp, cycle_transmittance = (
                    app.buffer_mgr.extract_cycle_region(
                        ch_letter,
                        start_time_raw,
                        stop_time_raw,
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
                    # Persist so that moving the cursor doesn't shift the baseline
                    app.buffer_mgr.baseline_wavelengths[ch_letter] = baseline
                elif baseline is None:
                    baseline = 0

                # Convert wavelength shift to RU (Response Units)
                delta_spr = (cycle_wavelength - baseline) * WAVELENGTH_TO_RU_CONVERSION

                # Store in buffer manager (with timestamps and transmittance)
                app.buffer_mgr.update_cycle_data(
                    ch_letter,
                    cycle_time,
                    cycle_wavelength,
                    delta_spr,
                    cycle_timestamp,
                    cycle_transmittance if len(cycle_transmittance) > 0 else None,
                )

            # Collect reference channel display data for plot-time subtraction (display only)
            ref_ch = getattr(app, "_reference_channel", None)
            ref_display_time = None
            ref_display_spr = None
            if ref_ch is not None:
                ref_cd = app.buffer_mgr.cycle_data.get(ref_ch)
                if ref_cd is not None and len(ref_cd.time) > 0:
                    _ref_t = ref_cd.time
                    _ref_spr = ref_cd.spr
                    _display_offset = app.clock.display_offset
                    ref_display_time = _ref_t - _display_offset - start_time_display
                    if len(_ref_spr) > 0:
                        ref_display_spr = _ref_spr - _ref_spr[0]
                    else:
                        ref_display_spr = _ref_spr

            # Update graph curves
            max_cycle_time = 0
            for ch_letter, ch_idx in app._channel_pairs:
                cycle_time = app.buffer_mgr.cycle_data[ch_letter].time
                delta_spr = app.buffer_mgr.cycle_data[ch_letter].spr

                if len(cycle_time) == 0:
                    continue

                # Convert raw times to display coords, rebase to start cursor (t=0)
                if len(cycle_time) > 0:
                    display_offset = app.clock.display_offset
                    cycle_time_display = cycle_time - display_offset
                    display_cycle_time = cycle_time_display - start_time_display

                    # Rebase SPR delta so start cursor = 0
                    if len(delta_spr) > 0:
                        display_delta_spr = delta_spr - delta_spr[0]
                    else:
                        display_delta_spr = delta_spr

                    # Reference subtraction — display only, never touches buffer_mgr
                    if (
                        ref_ch is not None
                        and ch_letter.lower() != ref_ch.lower()
                        and ref_display_time is not None
                        and ref_display_spr is not None
                    ):
                        from affilabs.utils.graph_helpers import GraphHelpers
                        display_delta_spr = GraphHelpers.subtract_reference(
                            display_cycle_time, display_delta_spr,
                            ref_display_time, ref_display_spr,
                        )

                    if len(display_cycle_time) > 0:
                        max_cycle_time = max(max_cycle_time, display_cycle_time[-1])
                else:
                    # No data points; draw nothing
                    display_cycle_time = []
                    display_delta_spr = []

                # Apply per-channel time nudge offset (display only — set by left/right arrow in legend)
                time_offsets = getattr(app.main_window, "_channel_time_offsets", None)
                if time_offsets and len(display_cycle_time) > 0:
                    nudge = time_offsets.get(ch_letter.lower(), 0.0)
                    if nudge != 0.0:
                        import numpy as _np
                        display_cycle_time = _np.asarray(display_cycle_time) + nudge

                # Update cycle of interest graph
                curve = app.main_window.cycle_of_interest_graph.curves[ch_idx]
                curve.setData(display_cycle_time, display_delta_spr)

            # Auto-range when user hasn't manually zoomed — let pyqtgraph handle it
            graph = app.main_window.cycle_of_interest_graph
            if not getattr(graph, '_user_zoomed', False):
                graph.getPlotItem().enableAutoRange()

            # Re-assert focus on the legend so arrow-key nudge keeps working.
            # Only if user has previously clicked a channel (avoids stealing focus on startup).
            legend = getattr(graph, 'interactive_spr_legend', None)
            if legend is not None and getattr(legend, '_user_has_selected', False):
                legend.setFocus()

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
        from affilabs.utils.performance_profiler import measure

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
                    display_time = raw_time

                    # Skip first point and shift time axis so displayed data starts at t=0
                    if len(display_time) > 1:
                        first_time = display_time[1]
                        # Lock display offset on first valid frame (frozen after this)
                        app.clock.lock_display_offset(first_time)
                        offset = app.clock.display_offset
                        display_time = display_time[1:] - offset
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
            ) as _graph_err:
                pass
