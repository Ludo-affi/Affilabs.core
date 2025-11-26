"""Cycle Coordinator - Manages cycle tracking and autosave.

This coordinator handles:
- Cycle boundary detection
- Cycle region extraction
- Autosave of cycle data
- Cycle queue management
- Cycle flagging and annotation

Extracted from main_simplified.py to improve modularity and testability.
"""

from PySide6.QtCore import QObject
from utils.logger import logger
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Any
import datetime as dt


class CycleCoordinator(QObject):
    """Manages cycle tracking, extraction, and autosave operations."""

    def __init__(self, app):
        """Initialize cycle coordinator.

        Args:
            app: Reference to main Application instance
        """
        super().__init__()
        self.app = app

        # Cycle tracking
        self._last_cycle_bounds: Optional[Tuple[float, float]] = None
        self._session_cycles_dir: Optional[Path] = None

        # Flagging system
        self._selected_channel: Optional[int] = None  # 0-3 for A-D
        self._flag_data: List[Dict[str, Any]] = []  # List of {channel, time, annotation} dicts

    def check_cycle_changed(self, start_time: float, stop_time: float) -> bool:
        """Check if cycle region has changed significantly.

        Args:
            start_time: Start cursor position
            stop_time: Stop cursor position

        Returns:
            True if cycle changed significantly, False otherwise
        """
        if self._last_cycle_bounds is None:
            self._last_cycle_bounds = (start_time, stop_time)
            return True

        last_start, last_stop = self._last_cycle_bounds
        duration = stop_time - start_time

        # Consider it a new cycle if boundaries moved >5% of duration
        if (abs(start_time - last_start) > duration * 0.05 or
            abs(stop_time - last_stop) > duration * 0.05):
            self._last_cycle_bounds = (start_time, stop_time)
            return True

        return False

    def autosave_cycle_data(self, start_time: float, stop_time: float) -> None:
        """Autosave cycle data when boundaries change.

        Args:
            start_time: Start cursor position
            stop_time: Stop cursor position
        """
        if len(self.app.buffer_mgr.cycle_data['a'].time) < 10:
            return  # Not enough data points

        # Create session directory if needed
        if self._session_cycles_dir is None:
            self._create_session_cycles_dir()

        if self._session_cycles_dir is None:
            return  # Failed to create directory

        # Generate filename with timestamp
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self._session_cycles_dir / f"cycle_{timestamp}.csv"

        try:
            import pandas as pd

            # Build dataframe with all channel data
            cycle_dict = {'time': self.app.buffer_mgr.cycle_data['a'].time}

            for ch in self.app._idx_to_channel:
                spr_data = self.app.buffer_mgr.cycle_data[ch].spr
                if len(spr_data) == len(cycle_dict['time']):
                    cycle_dict[f'channel_{ch}_spr'] = spr_data

            df = pd.DataFrame(cycle_dict)
            df.to_csv(filename, index=False)

            logger.info(f"💾 Autosaved cycle data: {filename.name}")

        except Exception as e:
            logger.error(f"Failed to autosave cycle data: {e}")

    def _create_session_cycles_dir(self) -> None:
        """Create cycles directory for current session."""
        try:
            from config import DATA_DIR
            import datetime as dt

            # Create session-specific directory
            session_timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            self._session_cycles_dir = Path(DATA_DIR) / "cycles" / f"session_{session_timestamp}"
            self._session_cycles_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"📁 Created cycles directory: {self._session_cycles_dir}")

        except Exception as e:
            logger.error(f"Failed to create cycles directory: {e}")
            self._session_cycles_dir = None

    def on_graph_clicked(self, event) -> None:
        """Handle mouse click on cycle graph for channel selection and flagging.

        Args:
            event: Mouse click event
        """
        if event.button() != 1:  # Only left click
            return

        # Get click position
        pos = event.scenePos()
        view_box = self.app.main_window.cycle_of_interest_graph.getViewBox()

        if view_box.sceneBoundingRect().contains(pos):
            mouse_point = view_box.mapSceneToView(pos)
            click_time = mouse_point.x()
            click_spr = mouse_point.y()

            # Find nearest channel curve
            nearest_channel = self._find_nearest_channel(click_time, click_spr)

            if nearest_channel is not None:
                self._selected_channel = nearest_channel
                logger.info(f"Selected channel {self.app._idx_to_channel[nearest_channel].upper()} at t={click_time:.2f}s")

                # TODO: Visual feedback for selected channel
                # Could highlight the curve or show marker

    def _find_nearest_channel(self, click_time: float, click_spr: float) -> Optional[int]:
        """Find channel curve nearest to click position.

        Args:
            click_time: Time coordinate of click
            click_spr: SPR coordinate of click

        Returns:
            Channel index (0-3) or None
        """
        import numpy as np

        min_distance = float('inf')
        nearest_channel = None

        for ch_idx, ch_letter in enumerate(self.app._idx_to_channel):
            time_data = self.app.buffer_mgr.cycle_data[ch_letter].time
            spr_data = self.app.buffer_mgr.cycle_data[ch_letter].spr

            if len(time_data) == 0:
                continue

            # Find nearest point in time
            time_idx = np.argmin(np.abs(time_data - click_time))
            nearest_time = time_data[time_idx]
            nearest_spr = spr_data[time_idx]

            # Calculate distance (normalized to avoid scale issues)
            time_range = time_data[-1] - time_data[0] if len(time_data) > 1 else 1
            spr_range = np.ptp(spr_data) if len(spr_data) > 0 else 1

            norm_time_dist = (click_time - nearest_time) / max(time_range, 0.1)
            norm_spr_dist = (click_spr - nearest_spr) / max(spr_range, 1)

            distance = np.sqrt(norm_time_dist**2 + norm_spr_dist**2)

            if distance < min_distance:
                min_distance = distance
                nearest_channel = ch_idx

        # Only select if click is reasonably close (threshold = 0.1 normalized units)
        if min_distance < 0.1:
            return nearest_channel

        return None

    def add_flag(self, channel: int, time: float, annotation: str = "") -> None:
        """Add a flag marker to cycle data.

        Args:
            channel: Channel index (0-3)
            time: Time position for flag
            annotation: Optional annotation text
        """
        flag = {
            'channel': channel,
            'time': time,
            'annotation': annotation
        }
        self._flag_data.append(flag)

        ch_letter = self.app._idx_to_channel[channel]
        logger.info(f"🚩 Added flag: Ch {ch_letter.upper()} at t={time:.2f}s")

        # TODO: Visual representation of flag on graph

    def get_flags_for_channel(self, channel: int) -> List[Dict[str, Any]]:
        """Get all flags for a specific channel.

        Args:
            channel: Channel index (0-3)

        Returns:
            List of flag dictionaries
        """
        return [f for f in self._flag_data if f['channel'] == channel]

    def clear_flags(self) -> None:
        """Clear all flags."""
        self._flag_data.clear()
        logger.info("🚩 Cleared all flags")

    def export_flags_to_csv(self, filename: Path) -> None:
        """Export flags to CSV file.

        Args:
            filename: Output file path
        """
        if len(self._flag_data) == 0:
            logger.warning("No flags to export")
            return

        try:
            import pandas as pd

            # Convert to dataframe
            df = pd.DataFrame(self._flag_data)
            df['channel_letter'] = df['channel'].apply(lambda x: self.app._idx_to_channel[x].upper())

            # Reorder columns
            df = df[['channel_letter', 'time', 'annotation']]

            # Save to CSV
            df.to_csv(filename, index=False)
            logger.info(f"💾 Exported {len(self._flag_data)} flags to {filename}")

        except Exception as e:
            logger.error(f"Failed to export flags: {e}")

    def get_cycle_bounds(self) -> Optional[Tuple[float, float]]:
        """Get current cycle bounds.

        Returns:
            Tuple of (start_time, stop_time) or None
        """
        return self._last_cycle_bounds

    def reset_cycle_tracking(self) -> None:
        """Reset cycle tracking state."""
        self._last_cycle_bounds = None
        logger.info("Reset cycle tracking")
