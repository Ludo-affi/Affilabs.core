"""Resource path helper for PyInstaller compatibility.

This module provides functions to correctly locate resources in both
development and frozen (PyInstaller) environments.
"""

import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller.

    Args:
        relative_path: Path relative to project root (e.g., "affilabs/ui/img/icon.ico")

    Returns:
        Absolute path to the resource

    Example:
        >>> icon = get_resource_path("affilabs/ui/img/affinite2.ico")
        >>> pixmap = QPixmap(str(icon))
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)  # noqa: SLF001
    else:
        # Running in development
        base_path = Path(__file__).parent.parent.parent  # Go up to project root

    return base_path / relative_path


def get_affilabs_resource(relative_path: str) -> Path:
    """Get path to resource inside affilabs directory.

    Args:
        relative_path: Path relative to affilabs/ (e.g., "ui/img/icon.ico")

    Returns:
        Absolute path to the resource
    """
    return get_resource_path(f"affilabs/{relative_path}")
