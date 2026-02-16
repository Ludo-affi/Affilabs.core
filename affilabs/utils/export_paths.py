"""Export Path Utilities - Standardized export directory management.

Provides consistent default paths for all export operations:
- Export button exports
- Recording saves
- Autosaves
- Quick exports

This eliminates the inconsistency where different export paths use
different default directories.
"""

from __future__ import annotations

from pathlib import Path


class ExportPaths:
    """Standardized export path management for consistent file organization."""

    @staticmethod
    def get_default_export_dir(username: str | None = None) -> Path:
        """Get standardized export directory for Export button.

        Creates: ~/Documents/Affilabs Data/<username>/exports/
        or:      ~/Documents/Affilabs Data/exports/ (if no username)

        Args:
            username: Current user's username (optional)

        Returns:
            Path to export directory (created if it doesn't exist)
        """
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            export_dir = base / username / "exports"
        else:
            export_dir = base / "exports"

        export_dir.mkdir(parents=True, exist_ok=True)
        return export_dir

    @staticmethod
    def get_recording_dir(username: str | None = None) -> Path:
        """Get recording directory for Record button saves.

        Creates: ~/Documents/Affilabs Data/<username>/recordings/
        or:      ~/Documents/Affilabs Data/recordings/ (if no username)

        Args:
            username: Current user's username (optional)

        Returns:
            Path to recording directory (created if it doesn't exist)
        """
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            recording_dir = base / username / "recordings"
        else:
            recording_dir = base / "recordings"

        recording_dir.mkdir(parents=True, exist_ok=True)
        return recording_dir

    @staticmethod
    def get_autosave_dir(username: str | None = None) -> Path:
        """Get autosave directory for automatic cycle saves.

        Creates: ~/Documents/Affilabs Data/<username>/autosave/
        or:      ~/Documents/Affilabs Data/autosave/ (if no username)

        Args:
            username: Current user's username (optional)

        Returns:
            Path to autosave directory (created if it doesn't exist)
        """
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            autosave_dir = base / username / "autosave"
        else:
            autosave_dir = base / "autosave"

        autosave_dir.mkdir(parents=True, exist_ok=True)
        return autosave_dir

    @staticmethod
    def get_spr_data_dir(username: str | None = None) -> Path:
        """Get SPR data directory (legacy path for backward compatibility).

        Creates: ~/Documents/Affilabs Data/<username>/SPR_data/
        or:      ~/Documents/Affilabs Data/SPR_data/ (if no username)

        This is kept for backward compatibility with existing code that
        references SPR_data folder.

        Args:
            username: Current user's username (optional)

        Returns:
            Path to SPR data directory (created if it doesn't exist)
        """
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            spr_dir = base / username / "SPR_data"
        else:
            spr_dir = base / "SPR_data"

        spr_dir.mkdir(parents=True, exist_ok=True)
        return spr_dir

    @staticmethod
    def get_session_dir(username: str | None = None, session_name: str | None = None) -> Path:
        """Get session-specific directory for grouping related files.

        Creates: ~/Documents/Affilabs Data/<username>/sessions/<session_name>/
        or:      ~/Documents/Affilabs Data/sessions/<session_name>/

        Args:
            username: Current user's username (optional)
            session_name: Session identifier (optional, uses timestamp if None)

        Returns:
            Path to session directory (created if it doesn't exist)
        """
        from datetime import datetime

        base = Path.home() / "Documents" / "Affilabs Data"

        if username:
            sessions_base = base / username / "sessions"
        else:
            sessions_base = base / "sessions"

        # Use timestamp if no session name provided
        if session_name is None:
            session_name = datetime.now().strftime("%Y%m%d_%H%M%S")

        session_dir = sessions_base / session_name
        session_dir.mkdir(parents=True, exist_ok=True)

        return session_dir

    @staticmethod
    def get_base_data_dir(username: str | None = None) -> Path:
        """Get base Affilabs Data directory for user.

        Creates: ~/Documents/Affilabs Data/<username>/
        or:      ~/Documents/Affilabs Data/ (if no username)

        Args:
            username: Current user's username (optional)

        Returns:
            Path to base directory (created if it doesn't exist)
        """
        base = Path.home() / "Documents" / "Affilabs Data"
        if username:
            user_dir = base / username
        else:
            user_dir = base

        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir


# Convenience functions for backward compatibility
def get_default_export_path(username: str | None = None) -> Path:
    """Deprecated: Use ExportPaths.get_default_export_dir() instead."""
    return ExportPaths.get_default_export_dir(username)


def get_user_data_path(username: str | None = None) -> Path:
    """Deprecated: Use ExportPaths.get_base_data_dir() instead."""
    return ExportPaths.get_base_data_dir(username)
