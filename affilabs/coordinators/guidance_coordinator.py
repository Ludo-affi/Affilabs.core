"""GuidanceCoordinator — Adaptive per-stage UI guidance based on user experience level.

Phase 6 of the Sidebar Redesign Plan (SIDEBAR_REDESIGN_PLAN.md / ADAPTIVE_GUIDANCE_PLAN.md).

Guides Novice/Operator users through each experiment stage with inline hints.
Experienced users (Specialist+) see a clean, hint-free UI.

Pass A: Foundation — signal wiring, hint-level logic, user-change callback.
Pass B: Widget calls — inline labels, badges, panel nudges for each stage.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # avoid circular; app reference typed as Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hint keys — one per experiment stage
# ---------------------------------------------------------------------------
HINT_CONNECT = "hint_connect_shown"
HINT_CALIBRATE = "hint_calibrate_shown"
HINT_ACQUIRE = "hint_acquire_shown"
HINT_INJECT = "hint_inject_shown"
HINT_RECORD = "hint_record_shown"
HINT_EXPORT = "hint_export_shown"


class GuidanceCoordinator:
    """Coordinates per-stage adaptive guidance based on user experience level.

    Listens to app lifecycle signals and shows/hides inline hint elements
    according to the current user's guidance level:

        full     → Novice (0–4 experiments)   — every stage has a hint
        standard → Operator (5–19)            — hints suppressed after first dismissal
        minimal  → Specialist / Expert / Master — no hints; clean UI

    This is a plain Python object (not QObject) — signal wiring is done in
    main.py via lambda wrappers.  Avoiding QObject inheritance keeps
    UserProfileManager free of Qt dependencies.
    """

    def __init__(self, app) -> None:
        """Initialise coordinator and register user-change callback.

        Args:
            app: AffilabsApp instance (provides .user_profile_manager, .main_window)
        """
        self._app = app
        self._um = app.user_profile_manager

        # Evaluate guidance level once at launch; frozen for the session.
        self._guidance_level: str = "minimal"
        self._refresh_guidance_level()

        # Register callback so level refreshes when the active user changes.
        # UserProfileManager.set_current_user() calls this after saving.
        self._um.on_user_changed = self._on_user_changed

        logger.debug(
            f"GuidanceCoordinator: guidance_level={self._guidance_level!r}  "
            f"user={self._um.get_current_user()!r}"
        )

    # ------------------------------------------------------------------
    # Guidance level
    # ------------------------------------------------------------------

    def _refresh_guidance_level(self) -> None:
        self._guidance_level = self._um.get_guidance_level()

    def _on_user_changed(self, username: str) -> None:
        """Called by UserProfileManager immediately after a user switch."""
        self._refresh_guidance_level()
        logger.debug(
            f"GuidanceCoordinator: user changed → {username!r}  "
            f"level={self._guidance_level!r}"
        )

        # Sync user profile card (Export tab) and user_combo selection.
        try:
            sidebar = self._app.main_window.sidebar
            # Refresh XP / title display
            sb = getattr(sidebar, "_settings_builder", None)
            if sb is not None and hasattr(sb, "_update_progression_display"):
                sb._update_progression_display()
            # Sync Switch-User dropdown without re-triggering the signal
            uc = getattr(sidebar, "user_combo", None)
            if uc is not None:
                idx = uc.findText(username)
                if idx >= 0 and uc.currentIndex() != idx:
                    uc.blockSignals(True)
                    uc.setCurrentIndex(idx)
                    uc.blockSignals(False)
        except Exception as exc:
            logger.debug(f"GuidanceCoordinator._on_user_changed UI sync: {exc}")

    # ------------------------------------------------------------------
    # Public entry points — called from signal wrappers in main.py
    # ------------------------------------------------------------------

    def on_hardware_connected(self, *_args) -> None:
        """Fired when hardware connects successfully."""
        if self._should_show(HINT_CONNECT):
            logger.debug("GuidanceCoordinator: → connect hint")
            self._apply_hint(HINT_CONNECT)

    def on_calibration_complete(self, *_args) -> None:
        """Fired when calibration finishes."""
        if self._should_show(HINT_CALIBRATE):
            logger.debug("GuidanceCoordinator: → calibrate hint")
            self._apply_hint(HINT_CALIBRATE)

    def on_acquisition_started(self, *_args) -> None:
        """Fired when data acquisition loop starts."""
        if self._should_show(HINT_ACQUIRE):
            logger.debug("GuidanceCoordinator: → acquire hint")
            self._apply_hint(HINT_ACQUIRE)

    def on_injection_flag(self, *_args) -> None:
        """Fired when an injection flag is placed (injection_flag_requested signal)."""
        if self._should_show(HINT_INJECT):
            logger.debug("GuidanceCoordinator: → inject hint")
            self._apply_hint(HINT_INJECT)

    def on_recording_started(self, *_args) -> None:
        """Fired when Excel recording begins."""
        if self._should_show(HINT_RECORD):
            logger.debug("GuidanceCoordinator: → record hint")
            self._apply_hint(HINT_RECORD)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _should_show(self, hint_key: str) -> bool:
        """Return True if the hint should be shown for the current user/level.

        Rules:
        - minimal → never show any hint
        - standard → skip connect and calibrate hints only; others shown once
        - full → show all hints until each is dismissed
        """
        if self._guidance_level == "minimal":
            return False
        if self._guidance_level == "standard" and hint_key in (
            HINT_CONNECT,
            HINT_CALIBRATE,
        ):
            return False
        return not self._um.is_hint_shown(hint_key)

    def _apply_hint(self, hint_key: str) -> None:
        """Show the hint element for this key and mark it as shown.

        Pass A: logging only — no widget manipulation.
        Pass B: will call the appropriate widget show method per hint_key.
        """
        # TODO (Pass B): route to inline label / badge / panel nudge per hint_key
        logger.info(
            f"[Guidance] hint={hint_key!r}  level={self._guidance_level!r}"
            f"  user={self._um.get_current_user()!r}"
        )
        # Mark shown immediately so it won't re-fire this session.
        self._um.mark_hint_shown(hint_key)
