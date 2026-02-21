"""UI Update Coordinator

Manages all UI update operations with throttling and batching.
Separates UI update logic from Application class.

Responsibilities:
- Queue UI updates from acquisition/processing threads
- Batch updates at controlled rates:
  * Settings sidebar graphs (transmission/raw): 1 Hz
  * Live data sensorgram: 10 Hz (handled by main_simplified)
- Update transmission spectrum curves (via SpectroscopyPresenter)
- Update Sensor IQ diagnostic displays
- Prevent UI blocking from excessive updates
"""

from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QObject, QTimer

logger = logging.getLogger(__name__)

# Update rate constants (milliseconds)
SETTINGS_SIDEBAR_UPDATE_RATE = 500  # 2 Hz for Settings tab (balance between smoothness and performance)
LIVE_DATA_UPDATE_RATE = 500  # 2 Hz for live sensorgram (handled by main_simplified)


class AL_UIUpdateCoordinator(QObject):
    """Coordinates throttled UI updates for live data display."""

    def __init__(self, app, main_window):
        """Initialize UI update coordinator.

        Args:
            app: Application instance
            main_window: Main window instance with UI widgets

        """
        super().__init__()
        self.app = app
        self.main_window = main_window

        # Initialize SpectroscopyPresenter for transmission/raw spectrum updates
        from affilabs.presenters import SpectroscopyPresenter

        self.spectroscopy_presenter = SpectroscopyPresenter(main_window)

        # Pending transmission updates (queued from acquisition thread)
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

        # Pending sensor IQ updates
        self._pending_sensor_iq_updates = {}

        # Pending stability badge state (True = stable, False = not stable, None = unknown)
        self._pending_stability_update: bool | None = None

        # Colorblind mode flag — updated by set_colorblind_mode()
        self._colorblind_mode: bool = False

        # Setup throttled update timer for Settings sidebar graphs (1 Hz = 1000ms)
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self.process_pending_updates)
        self._update_timer.start(
            SETTINGS_SIDEBAR_UPDATE_RATE,
        )  # 1 Hz for Settings sidebar transmission/raw graphs

        # Update flags
        self._transmission_updates_enabled = True
        self._raw_spectrum_updates_enabled = True

        logger.info(
            f"[OK] AL_UIUpdateCoordinator initialized (Settings sidebar: {1000//SETTINGS_SIDEBAR_UPDATE_RATE} Hz, Live data: {1000//LIVE_DATA_UPDATE_RATE} Hz handled by main_simplified)",
        )
        logger.info(f"[TIMER-INIT] Update timer started: active={self._update_timer.isActive()}, interval={self._update_timer.interval()}ms")

    def queue_transmission_update(
        self,
        channel: str,
        wavelengths: np.ndarray,
        transmission: np.ndarray,
        raw_spectrum: np.ndarray | None = None,
    ):
        """Queue transmission curve update for batch processing.

        Args:
            channel: Channel identifier ('a', 'b', 'c', 'd')
            wavelengths: Wavelength array (nm)
            transmission: Transmission spectrum (%)
            raw_spectrum: Optional raw intensity data

        """
        logger.debug(f"[COORDINATOR-QUEUE] *** Queuing update for ch={channel}: trans={'YES' if transmission is not None else 'NO'}, raw={'YES' if raw_spectrum is not None else 'NO'}, {len(wavelengths)} pts ***")
        self._pending_transmission_updates[channel] = {
            "wavelengths": wavelengths,
            "transmission": transmission,
            "raw_spectrum": raw_spectrum,
        }

    def queue_sensor_iq_update(self, channel: str, sensor_iq):
        """Queue Sensor IQ diagnostic display update.

        Args:
            channel: Channel identifier
            sensor_iq: SensorIQMetrics object

        """
        self._pending_sensor_iq_updates[channel] = sensor_iq

    def process_pending_updates(self):
        """Process all queued UI updates in batch (called by timer)."""
        try:
            # Log EVERY timer tick to verify timer is running
            pending_count = sum(1 for v in self._pending_transmission_updates.values() if v is not None)
            if pending_count > 0:
                logger.debug(f"[COORDINATOR-TIMER] *** TICK - {pending_count} pending updates (transmission_enabled={self._transmission_updates_enabled}, raw_enabled={self._raw_spectrum_updates_enabled}) ***")
            else:
                logger.debug(f"[COORDINATOR-TIMER] TICK - {pending_count} pending updates (transmission_enabled={self._transmission_updates_enabled}, raw_enabled={self._raw_spectrum_updates_enabled})")

            # Process transmission curve updates
            if self._transmission_updates_enabled:
                self._update_transmission_curves()

            # Process Sensor IQ diagnostic updates
            self._update_sensor_iq_displays()

            # Process stability badge update
            if self._pending_stability_update is not None:
                self._update_stability_badge(self._pending_stability_update)
                self._pending_stability_update = None

        except Exception as e:
            logger.exception(f"Error in UI update coordinator: {e}")

    def _update_transmission_curves(self):
        """Update transmission spectrum curves from pending queue (via SpectroscopyPresenter)."""
        # Check if plots are available (one-time check)
        if not self.spectroscopy_presenter._plots_check_logged:
            self.spectroscopy_presenter.check_plots_available()

        # Process pending updates (no logging needed - happens every 100ms)
        for channel, update_data in self._pending_transmission_updates.items():
            if update_data is None:
                continue

            try:
                wavelengths = update_data["wavelengths"]
                transmission = update_data.get("transmission")
                raw_spectrum = update_data.get("raw_spectrum")

                # Update transmission curve via presenter (only if available)
                if self._transmission_updates_enabled and transmission is not None:
                    logger.debug(f"[COORDINATOR] *** Calling spectroscopy_presenter.update_transmission for ch={channel} ***")
                    self.spectroscopy_presenter.update_transmission(
                        channel,
                        wavelengths,
                        transmission,
                    )
                    logger.debug(f"[COORDINATOR] *** update_transmission returned for ch={channel} ***")
                else:
                    if transmission is None:
                        logger.warning(f"[COORDINATOR] Skipping ch={channel}: transmission is None")
                    if not self._transmission_updates_enabled:
                        logger.warning(f"[COORDINATOR] Skipping ch={channel}: updates disabled")

                # Update raw spectrum curve via presenter (independent of transmission)
                if self._raw_spectrum_updates_enabled and raw_spectrum is not None:
                    logger.debug(f"[RAW-UPDATE] Calling presenter.update_raw_spectrum for {channel}: {len(raw_spectrum)} points, {wavelengths[0]:.1f}-{wavelengths[-1]:.1f}nm")
                    self.spectroscopy_presenter.update_raw_spectrum(
                        channel,
                        wavelengths,
                        raw_spectrum,
                    )
                else:
                    if raw_spectrum is None:
                        logger.debug(f"[RAW-UPDATE] Skipping {channel}: raw_spectrum is None")
                    if not self._raw_spectrum_updates_enabled:
                        logger.debug(f"[RAW-UPDATE] Skipping {channel}: updates disabled")

                # *** LIVE DATA DIALOG UPDATE ***
                # Update live data dialog if it exists and is visible
                live_dialog = None
                if hasattr(self.app, 'acquisition_events') and hasattr(self.app.acquisition_events, '_live_data_dialog'):
                    live_dialog = self.app.acquisition_events._live_data_dialog

                if live_dialog is not None and live_dialog.isVisible():
                    try:
                        # Update transmission plot
                        if self._transmission_updates_enabled:
                            live_dialog.update_transmission_plot(channel, wavelengths, transmission)

                        # Update raw data plot
                        if self._raw_spectrum_updates_enabled and raw_spectrum is not None:
                            live_dialog.update_raw_data_plot(channel, wavelengths, raw_spectrum)
                    except Exception:
                        # Silently ignore dialog update errors (dialog may be closing)
                        pass

            except Exception as e:
                logger.warning(f"Failed to update curves for channel {channel}: {e}")

        # Clear processed updates
        self._pending_transmission_updates = {
            "a": None,
            "b": None,
            "c": None,
            "d": None,
        }

    # Short status word per IQ level — shown inside each pill
    _IQ_PILL_LABELS = {
        "excellent": "Good",
        "good":      "Good",
        "questionable": "Weak",
        "poor":      "Poor",
        "critical":  "ERROR",
    }
    # Pill background / border colors per IQ level
    _IQ_PILL_BG = {
        "excellent":    ("rgba(52,199,89,0.15)",  "#34C759"),
        "good":         ("rgba(52,199,89,0.15)",  "#34C759"),
        "questionable": ("rgba(255,149,0,0.15)",  "#FF9500"),
        "poor":         ("rgba(255,59,48,0.15)",  "#FF3B30"),
        "critical":     ("rgba(255,59,48,0.22)",  "#FF3B30"),
    }
    # Channel letter colors for pill text — standard palette
    _CH_COLORS = {"a": "#1D1D1F", "b": "#FF3B30", "c": "#007AFF", "d": "#34C759"}
    # Channel letter colors — colorblind palette (matches CHANNEL_COLORS_COLORBLIND)
    _CH_COLORS_CB = {"a": "#e66101", "b": "#fdb863", "c": "#b2abd2", "d": "#5e3c99"}

    def set_colorblind_mode(self, enabled: bool) -> None:
        """Switch pill text channel colors to match the active palette."""
        self._colorblind_mode = enabled

    def _update_sensor_iq_displays(self):
        """Update Sensor IQ displays: signal quality pills + Δ SPR bar (interactive legend shows channel state)."""
        if not self._pending_sensor_iq_updates:
            return

        try:
            from affilabs.utils.sensor_iq import SENSOR_IQ_COLORS

            ch_color_map = self._CH_COLORS_CB if self._colorblind_mode else self._CH_COLORS

            for channel, sensor_iq in self._pending_sensor_iq_updates.items():
                iq_key = sensor_iq.iq_level.value
                color = SENSOR_IQ_COLORS.get(iq_key, "#C7C7CC")
                ch_upper = channel.upper()

                # ── Build shared tooltip ───────────────────────────────────
                fwhm_text = f"{sensor_iq.fwhm:.1f}nm" if sensor_iq.fwhm else "N/A"
                depth_text = f"{sensor_iq.dip_depth*100:.0f}%" if sensor_iq.dip_depth is not None else "N/A"
                tooltip_text = (
                    f"Channel {ch_upper} — {iq_key.upper()}\n"
                    f"λ: {sensor_iq.wavelength:.1f} nm  |  FWHM: {fwhm_text}  |  Dip: {depth_text}"
                )
                if sensor_iq.warning_message:
                    tooltip_text += f"\n⚠  {sensor_iq.warning_message}"
                if sensor_iq.recommendation:
                    tooltip_text += f"\n→  {sensor_iq.recommendation}"

                # ── 1. Signal quality pill ─────────────────────────────────
                pills = getattr(self.main_window, 'signal_quality_pills', {})
                pill = pills.get(ch_upper)
                if pill is not None:
                    bg, border = self._IQ_PILL_BG.get(iq_key, ("#F2F2F7", "#E5E5EA"))
                    status = self._IQ_PILL_LABELS.get(iq_key, "—")
                    ch_color = ch_color_map.get(channel, "#1D1D1F")
                    pill.setText(
                        f"<b style='color:{ch_color};'>{ch_upper}</b>"
                        f" <span style='color:{border};'>{status}</span>"
                    )
                    pill.setToolTip(tooltip_text)
                    pill.setStyleSheet(
                        f"QLabel {{"
                        f"  background: {bg};"
                        f"  border-radius: 5px;"
                        f"  border: 1px solid {border};"
                        f"  padding: 0px 6px;"
                        f"  font-size: 10px;"
                        f"  font-weight: 600;"
                        f"  font-family: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif;"
                        f"}}"
                    )

                # ── 3. Mirror color to Δ SPR bar dict ─────────────────────
                if hasattr(self.main_window, 'sensor_iq_colors'):
                    self.main_window.sensor_iq_colors[ch_upper] = color

                # ── 4. Update interactive legend IQ dot (color + shape) ───
                graph = getattr(self.main_window, 'cycle_of_interest_graph', None)
                legend = getattr(graph, 'interactive_spr_legend', None)
                if legend is not None:
                    legend.set_iq_state(ch_upper, color, iq_key)

            # ── 5. Update footer signal science panel ─────────────────────
            # Only send data for the currently selected timing channel so
            # the footer always reflects the channel the scientist is watching.
            graph = getattr(self.main_window, 'cycle_of_interest_graph', None)
            footer = getattr(graph, 'intelligence_footer', None)
            if footer is not None:
                sel_letter = getattr(self.main_window, 'selected_channel_letter', 'A')
                sel_lower = sel_letter.lower()
                sel_iq = self._pending_sensor_iq_updates.get(sel_lower)
                if sel_iq is not None:
                    # p2p is computed from Active Cycle sensorgram data (per channel),
                    # not from the global SensorIQ history — matches exactly what is
                    # plotted in the Active Cycle graph window.
                    p2p_val = None
                    try:
                        import numpy as np
                        buf = getattr(self.app, 'buffer_mgr', None)
                        if buf is not None:
                            spr_data = buf.cycle_data[sel_lower].spr
                            if len(spr_data) >= 2:
                                p2p_val = float(np.max(spr_data) - np.min(spr_data))
                    except Exception:
                        pass
                    stable = (p2p_val < 5.0) if p2p_val is not None else None
                    footer.update_signal_metrics(
                        channel=sel_lower,
                        wavelength=sel_iq.wavelength,
                        fwhm=sel_iq.fwhm,
                        p2p=p2p_val,
                        stable=stable,
                    )

        except Exception as e:
            logger.debug(f"Sensor IQ display update failed: {e}")

        self._pending_sensor_iq_updates.clear()

    def queue_stability_update(self, stable: bool) -> None:
        """Queue a baseline stability badge state change."""
        self._pending_stability_update = stable

    def _update_stability_badge(self, stable: bool) -> None:
        """Apply the stability badge state to the main window widget."""
        badge = getattr(self.main_window, "stability_badge", None)
        if badge is None:
            return
        try:
            if stable:
                badge.setText("Ready to inject \u2713")
                badge.setStyleSheet(
                    "QLabel {"
                    "  background: rgba(52, 199, 89, 0.15);"
                    "  color: #1A7F37;"
                    "  font-size: 11px;"
                    "  font-weight: 700;"
                    "  border-radius: 5px;"
                    "  border: 1px solid rgba(52, 199, 89, 0.4);"
                    "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                )
                badge.setToolTip(
                    "Baseline is stable — safe to inject\n"
                    "All active channels within \u00b10.075 nm for the last ~30 s"
                )
            else:
                badge.setText("Stabilizing\u2026")
                badge.setStyleSheet(
                    "QLabel {"
                    "  background: rgba(0,0,0,0.06);"
                    "  color: #86868B;"
                    "  font-size: 11px;"
                    "  font-weight: 600;"
                    "  border-radius: 5px;"
                    "  font-family: -apple-system, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;"
                    "}"
                )
                badge.setToolTip(
                    "Baseline still drifting — wait for green before injecting"
                )
            badge.setVisible(True)
        except Exception as e:
            logger.debug(f"Stability badge update failed: {e}")

    def set_transmission_updates_enabled(self, enabled: bool):
        """Enable/disable transmission curve updates."""
        self._transmission_updates_enabled = enabled
        logger.info(f"Transmission updates: {'enabled' if enabled else 'disabled'}")

    def set_raw_spectrum_updates_enabled(self, enabled: bool):
        """Enable/disable raw spectrum curve updates."""
        self._raw_spectrum_updates_enabled = enabled
        logger.info(f"Raw spectrum updates: {'enabled' if enabled else 'disabled'}")

    def cleanup(self):
        """Stop timer and cleanup resources."""
        if self._update_timer:
            self._update_timer.stop()
        logger.info("AL_UIUpdateCoordinator cleaned up")
