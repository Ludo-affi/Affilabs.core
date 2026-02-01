"""Presenters Package

Presenter classes that handle UI updates for the main window.
Follows the Presenter Pattern to separate UI update logic from the main window class.

Contains:
- SensogramPresenter: Handles graph/plot updates for timeline and cycle views
- StatusPresenter: Handles hardware status and control state updates
- SpectroscopyPresenter: Handles transmission and raw spectrum plot updates
- BaselineRecordingPresenter: Handles baseline recording UI state and interactions
- NavigationPresenter: Handles navigation bar creation and page switching
- QueuePresenter: Handles queue management with undo/redo support (NEW)
"""

# Import QueuePresenter separately (no UI dependencies)
from .queue_presenter import QueuePresenter

# Import UI-dependent presenters conditionally
try:
    from .baseline_recording_presenter import BaselineRecordingPresenter
    from .navigation_presenter import NavigationPresenter
    from .sensogram_presenter import SensogramPresenter
    from .spectroscopy_presenter import SpectroscopyPresenter
    from .status_presenter import StatusPresenter

    __all__ = [
        "SensogramPresenter",
        "StatusPresenter",
        "SpectroscopyPresenter",
        "BaselineRecordingPresenter",
        "NavigationPresenter",
        "QueuePresenter",
    ]
except ImportError:
    # UI dependencies not available (e.g., in tests)
    __all__ = ["QueuePresenter"]
