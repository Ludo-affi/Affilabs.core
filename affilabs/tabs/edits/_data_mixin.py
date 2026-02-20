"""DataMixin — pure data-utility methods extracted from EditsTab.

Contains 8 methods:
    _edits_flags (property + setter)
    _parse_delta_spr
    _format_flags_display
    _get_save_path
    _collect_channel_data_from_cycle
    _get_user_export_dir
    _ensure_experiment_folder
    _calculate_actual_duration
"""

import ast
from pathlib import Path

import pandas as pd

from affilabs.utils.logger import logger


class DataMixin:
    """Mixin providing data-utility helpers for EditsTab."""

    # ── Flags property (backward-compatible delegation to FlagManager) ──────

    @property
    def _edits_flags(self):
        """Backward-compatible property: delegates to FlagManager if available."""
        try:
            app = self.main_window.app
            if hasattr(app, 'flag_mgr') and app.flag_mgr:
                return app.flag_mgr.get_edits_flags()
        except (AttributeError, RuntimeError):
            pass
        return self._edits_flags_fallback

    @_edits_flags.setter
    def _edits_flags(self, value):
        """Setter for backward compatibility (legacy code may assign directly)."""
        self._edits_flags_fallback = value

    # ── Helper methods ───────────────────────────────────────────────────────

    def _parse_delta_spr(self, cycle: dict) -> dict:
        """Parse delta_spr_by_channel from cycle dict, handling string-to-dict conversion.

        Args:
            cycle: Cycle dictionary containing 'delta_spr_by_channel' key

        Returns:
            Dictionary mapping channel letters (A, B, C, D) to delta SPR values.
            Returns empty dict if parsing fails or key doesn't exist.
        """
        delta_by_ch = cycle.get('delta_spr_by_channel', {})
        if isinstance(delta_by_ch, str):
            try:
                delta_by_ch = ast.literal_eval(delta_by_ch)
            except Exception:
                delta_by_ch = {}
        return delta_by_ch if isinstance(delta_by_ch, dict) else {}

    def _format_flags_display(self, cycle: dict) -> str:
        """Format flag_data for table display with icons.

        Args:
            cycle: Cycle dictionary containing 'flag_data' key
                   (list of dicts with 'type' and 'time' fields)

        Returns:
            Formatted string for display (e.g., "▲120s ■240s ◆360s"),
            or empty string if no flag_data present.
        """
        FLAG_ICONS = {'injection': '▲', 'wash': '■', 'spike': '◆'}

        flag_data = cycle.get('flag_data', [])
        if not flag_data:
            return ''

        parts = []
        for f in flag_data:
            icon = FLAG_ICONS.get(f.get('type', ''), '●')
            parts.append(f"{icon}{f.get('time', 0):.0f}s")
        return " ".join(parts)

    def _get_save_path(self, title: str, file_filter: str = "Excel Files (*.xlsx)", subfolder: str = "Analysis") -> str:
        """Get save file path with consistent dialog and default location.

        Args:
            title: Dialog title
            file_filter: File type filter (default: Excel files)
            subfolder: Subfolder within experiment/user directory

        Returns:
            Selected file path, or empty string if cancelled
        """
        from PySide6.QtWidgets import QFileDialog

        # Get default save location
        exp_folder = self._ensure_experiment_folder()
        if exp_folder:
            default_folder = self.main_window.app.experiment_folder_mgr.get_subfolder_path(exp_folder, subfolder)
        else:
            default_folder = self._get_user_export_dir(subfolder)

        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            title,
            str(default_folder),
            file_filter
        )
        return file_path or ""

    def _collect_channel_data_from_cycle(self, cycle: dict, fields: dict) -> dict:
        """Collect channel-specific data from a cycle dict.

        Args:
            cycle: Cycle dictionary
            fields: Dict mapping result keys to field patterns, e.g.:
                   {'delta': 'delta_ch{num}', 'time': 'time_ch{num}'}

        Returns:
            Dict with channel letters as keys, containing requested field data
        """
        result = {ch: {} for ch in self.CHANNELS}

        # First try delta_spr_by_channel format
        if 'delta' in fields:
            delta_by_ch = self._parse_delta_spr(cycle)
            for ch in self.CHANNELS:
                if ch in delta_by_ch:
                    result[ch]['delta'] = delta_by_ch[ch]

        # Then try numbered fields (delta_ch1, etc.)
        for field_name, pattern in fields.items():
            for i, ch in enumerate(self.CHANNELS, 1):
                if field_name not in result[ch]:
                    field_key = pattern.format(num=i, ch=ch)
                    value = cycle.get(field_key, '')
                    if value and pd.notna(value):
                        result[ch][field_name] = value

        return result

    # ── Directory & folder management ────────────────────────────────────────

    def _get_user_export_dir(self, subfolder: str = "SPR_data") -> Path:
        """Get user-specific default export directory.

        Creates: Documents/Affilabs Data/<username>/<subfolder>/

        Args:
            subfolder: Subfolder within user directory (default: 'SPR_data')

        Returns:
            Path to user-specific export directory
        """
        username = "Default"
        if self.user_manager:
            username = self.user_manager.get_current_user() or "Default"
        elif hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'user_profile_manager'):
            self.user_manager = self.main_window.app.user_profile_manager
            username = self.user_manager.get_current_user() or "Default"

        user_dir = Path.home() / "Documents" / "Affilabs Data" / username / subfolder
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _ensure_experiment_folder(self):
        """Ensure an experiment folder exists, creating one if needed.

        Returns:
            Path to experiment folder, or None if user cancels
        """
        from PySide6.QtWidgets import QInputDialog, QMessageBox

        # Check if we already have an active experiment folder
        if (hasattr(self.main_window, 'app') and
                hasattr(self.main_window.app, 'current_experiment_folder') and
                self.main_window.app.current_experiment_folder):
            return self.main_window.app.current_experiment_folder

        # Prompt user for experiment name
        experiment_name, ok = QInputDialog.getText(
            self.main_window,
            "Create Experiment Folder",
            "Enter experiment name:",
            text="Experiment"
        )

        if not ok or not experiment_name.strip():
            logger.info("User cancelled experiment folder creation")
            return None

        # Get user profile
        if not self.user_manager:
            if hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'user_profile_manager'):
                self.user_manager = self.main_window.app.user_profile_manager

        if self.user_manager:
            user_name = self.user_manager.get_current_user()
        else:
            from affilabs.services.user_profile_manager import UserProfileManager
            user_name = UserProfileManager().get_current_user()

        # Get device ID
        device_id = "Unknown"
        if hasattr(self.main_window, 'app') and hasattr(self.main_window.app, 'device_config'):
            device_id = self.main_window.app.device_config.device_serial

        # Create experiment folder
        try:
            exp_folder = self.main_window.app.experiment_folder_mgr.create_experiment_folder(
                experiment_name=experiment_name.strip(),
                user_name=user_name,
                device_id=device_id,
                sensor_type="",
                description=""
            )
            self.main_window.app.current_experiment_folder = exp_folder
            logger.info(f"✓ Created experiment folder: {exp_folder.name}")
            return exp_folder

        except Exception as e:
            logger.error(f"Failed to create experiment folder: {e}")
            QMessageBox.warning(
                self.main_window,
                "Folder Creation Failed",
                f"Could not create experiment folder:\n{str(e)}"
            )
            return None

    # ── Duration calculation ─────────────────────────────────────────────────

    def _calculate_actual_duration(self, cycle_idx, cycle, all_cycles):
        """Get actual cycle duration from export data or calculate if missing.

        Strategy (optimized to avoid redundant calculation):
        1. Use pre-calculated duration_minutes from Cycle.to_export_dict()
        2. Else if next cycle exists: calculate from spacing (next_start - current_start) / 60
        3. Else: fall back to planned duration (length_minutes)

        Args:
            cycle_idx: Index of current cycle in all_cycles list
            cycle: Current cycle dict from Cycle.to_export_dict()
            all_cycles: Complete list of all cycles

        Returns:
            float: Actual duration in minutes
        """
        # Strategy 1: Use pre-calculated duration_minutes
        duration_minutes = cycle.get('duration_minutes')
        if pd.notna(duration_minutes) and duration_minutes > 0:
            logger.debug(f"Cycle {cycle_idx + 1}: Using pre-calculated duration → {duration_minutes:.2f} min")
            return duration_minutes

        # Strategy 2: Calculate from spacing to next cycle
        start_time = cycle.get('start_time_sensorgram')
        if cycle_idx < len(all_cycles) - 1:
            next_cycle = all_cycles[cycle_idx + 1]
            next_start = next_cycle.get('start_time_sensorgram')
            if pd.notna(next_start) and pd.notna(start_time):
                actual_duration = (next_start - start_time) / 60.0
                logger.debug(f"Cycle {cycle_idx + 1}: Calculated from spacing → {actual_duration:.2f} min")
                return actual_duration

        # Strategy 3: Fall back to planned duration
        planned_duration = cycle.get('length_minutes', 0)
        logger.debug(f"Cycle {cycle_idx + 1}: Using planned duration → {planned_duration:.2f} min")
        return planned_duration
