"""UI Control Event Coordinator.

Manages UI control events including:
- Page/tab navigation
- Polarizer toggle controls
- Filter strength adjustments
- Reference channel selection
- Unit display changes (RU/nm)

This coordinator handles UI control state changes and updates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from main_simplified import Application

from affilabs.utils.logger import logger


class UIControlEventCoordinator:
    """Coordinates UI control events and state updates.

    Handles:
    - Page navigation and dialog visibility
    - Polarizer toggle operations
    - Filter strength adjustments
    - Reference channel selection
    - Display unit toggles (RU/nm)

    This is a pure coordinator - it routes events and updates UI,
    but does not contain business logic.
    """

    def __init__(self, app: Application):
        """Initialize UI control event coordinator.

        Args:
            app: Main application instance for accessing managers and UI

        """
        self.app = app

    # =========================================================================
    # PAGE NAVIGATION
    # =========================================================================

    def on_page_changed(self, page_index: int):
        """Handle page changes - show/hide live data dialog for Live Data page.

        Args:
            page_index: Index of the page being switched to (0 = Live Data)

        """
        # Page 0 is Live Data (sensorgram)
        if page_index == 0:
            # Show live data dialog if acquisition is running
            if (
                self.app.data_mgr
                and self.app.data_mgr._acquiring
                and self.app._live_data_dialog is not None
            ):
                self.app._live_data_dialog.show()
                self.app._live_data_dialog.raise_()
        # Hide dialog when switching away from Live Data page
        elif self.app._live_data_dialog is not None:
            self.app._live_data_dialog.hide()

    # =========================================================================
    # POLARIZER CONTROL
    # =========================================================================

    def on_polarizer_toggle_clicked(self):
        """Handle polarizer toggle button click - switch servo between S and P positions."""
        try:
            logger.info("🔄 Polarizer toggle button clicked")

            # Get current position from UI
            current_position = self.app.main_window.sidebar.current_polarizer_position
            logger.info(f"   Current position: {current_position}")

            # Toggle to opposite position
            new_position = "P" if current_position == "S" else "S"

            # Send command to hardware using servo_move_1_then worker function
            if self.app.hardware_mgr.ctrl is not None:
                logger.info(
                    f"🔧 Toggling polarizer: {current_position} → {new_position}",
                )

                # Import servo worker function
                from affilabs.core.calibration_workflow import (
                    resolve_device_config_for_detector,
                    servo_move_1_then,
                )

                # Get device config (reads updated UI positions)
                device_config_det = None
                if (
                    hasattr(self.app.main_window, "device_config")
                    and self.app.main_window.device_config
                ):
                    device_config_det = self.app.main_window.device_config.config
                else:
                    # Fallback: try to resolve from USB
                    try:
                        if hasattr(self.app.hardware_mgr, "usb") and self.app.hardware_mgr.usb:
                            device_config_det = resolve_device_config_for_detector(
                                self.app.hardware_mgr.usb,
                            )
                    except Exception:
                        pass

                if device_config_det:
                    # Use servo worker function - it reads positions from device_config
                    # and moves only if current != target
                    success = servo_move_1_then(
                        self.app.hardware_mgr.ctrl,
                        device_config_det,
                        current_mode=current_position.lower(),
                        target_mode=new_position.lower(),
                    )

                    if success:
                        # Lock the new mode via firmware command
                        mode_success = self.app.hardware_mgr.ctrl.set_mode(
                            new_position.lower(),
                        )

                        if mode_success:
                            # Update UI to reflect new position
                            self.app.main_window.sidebar.set_polarizer_position(
                                new_position,
                            )
                            logger.info(
                                f"[OK] Polarizer moved to position {new_position}",
                            )
                        else:
                            logger.warning(
                                f"⚠️ Servo moved but mode lock failed for {new_position}",
                            )
                            # Still update UI since servo physically moved
                            self.app.main_window.sidebar.set_polarizer_position(
                                new_position,
                            )
                    else:
                        logger.error(
                            f"[X] Failed to move polarizer to position {new_position}",
                        )
                        from affilabs.widgets.message import show_message

                        show_message(
                            f"Failed to move polarizer to position {new_position}\n\nCheck hardware connection.",
                        )
                else:
                    logger.error("[X] No device_config available for servo positions")
                    from affilabs.widgets.message import show_message

                    show_message(
                        "Cannot move polarizer - device configuration not loaded.",
                    )

            else:
                logger.warning(
                    "⚠️ Controller not connected - cannot move polarizer",
                )
                from affilabs.widgets.message import show_message

                show_message(
                    "Controller not connected.\n\nPlease connect hardware first.",
                )

        except Exception as e:
            logger.error(f"[X] Error toggling polarizer: {e}")
            import traceback

            traceback.print_exc()
            from affilabs.widgets.message import show_message

            show_message(f"Error toggling polarizer: {e!s}")

    # =========================================================================
    # FILTER CONTROLS
    # =========================================================================

    def on_filter_strength_changed(self, value: int):
        """Handle filter strength slider changes.

        Args:
            value: Filter strength value (1-10)

        """
        self.app._filter_strength = value
        logger.info(f"Filter strength set to: {value}")

        # Redraw if filtering is enabled
        if self.app._filter_enabled:
            self.app._redraw_timeline_graph()

    # =========================================================================
    # REFERENCE CHANNEL SELECTION
    # =========================================================================

    def on_reference_changed(self, text: str):
        """Handle reference channel selection changes.

        Args:
            text: Selected reference channel text ("None", "Channel A", etc.)

        """
        import pyqtgraph as pg

        # Map selection to channel letter
        channel_map = {
            "None": None,
            "Channel A": "a",
            "Channel B": "b",
            "Channel C": "c",
            "Channel D": "d",
        }

        old_ref = self.app._reference_channel
        self.app._reference_channel = channel_map.get(text)

        if self.app._reference_channel:
            logger.info(f"Reference channel set to: {self.app._reference_channel.upper()}")
        else:
            logger.info("Reference channel disabled")

        # Reset old reference channel styling
        if old_ref is not None:
            ch_idx = {"a": 0, "b": 1, "c": 2, "d": 3}[old_ref]
            self.app._reset_channel_style(ch_idx)

        # Apply new reference channel styling
        if self.app._reference_channel is not None:
            ch_idx = {"a": 0, "b": 1, "c": 2, "d": 3}[self.app._reference_channel]
            # Purple color with transparency and dashed line
            self.app.main_window.cycle_of_interest_graph.curves[ch_idx].setPen(
                pg.mkPen(
                    color=(153, 102, 255, 150),
                    width=2,
                    style=pg.QtCore.Qt.PenStyle.DashLine,
                ),
            )

        # Recompute cycle data with new reference
        self.app._update_cycle_of_interest_graph()

    # =========================================================================
    # UNIT DISPLAY CONTROLS
    # =========================================================================

    def on_unit_changed(self, checked: bool):
        """Toggle between RU and nm units for display.

        Args:
            checked: Radio button checked state

        """
        if not checked:
            return

        if self.app.main_window.ru_btn.isChecked():
            unit = "RU"
        else:
            unit = "nm"

        logger.info(f"Display unit changed to: {unit}")

        # Update graph labels
        if unit == "RU":
            self.app.main_window.cycle_of_interest_graph.setLabel(
                "left",
                "Δ SPR (RU)",
                color="#86868B",
                size="11pt",
            )
        else:
            self.app.main_window.cycle_of_interest_graph.setLabel(
                "left",
                "Δλ (nm)",
                color="#86868B",
                size="11pt",
            )

        # TODO: Trigger data conversion and redraw
        # The conversion factor is approximately: 1 RU ≈ 0.1 nm
        # This should be implemented in the data processing pipeline
