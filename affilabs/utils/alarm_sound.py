"""Alarm sound generator using winsound.Beep (Windows, no external dependencies).

Generates the ascending 3-tone alert that plays when the contact timer expires.
Runs in a background thread so it never blocks the UI.
"""

import sys
import threading
from typing import Optional
from affilabs.utils.logger import logger


class AlarmSound:
    """Alarm sound player using winsound.Beep on Windows."""

    def __init__(self):
        self._playing = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _play_ascending(self):
        """Play 3-tone ascending alert: 800 → 1000 → 1300 Hz."""
        try:
            import winsound
            winsound.Beep(800, 150)
            winsound.Beep(1000, 150)
            winsound.Beep(1300, 220)
        except Exception as e:
            logger.debug(f"winsound.Beep failed: {e}")

    def play_alarm(self, style: str = "ascending", repeats: int = 1) -> bool:
        """Play alarm tone in a background thread (non-blocking).

        Args:
            style: ignored (always ascending on Windows)
            repeats: 1 = once; -1 or 0 = ignored (loop managed externally by _start_alarm_loop)

        Returns:
            True always (fire-and-forget)
        """
        thread = threading.Thread(target=self._play_ascending, daemon=True, name="AlarmBeep")
        thread.start()
        return True

    def stop_alarm(self):
        """No-op — winsound.Beep is synchronous and completes on its own."""
        return True

    def _fallback_beep(self) -> bool:
        try:
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return True
            else:
                print('\a', flush=True)
                return True
        except Exception as e:
            logger.debug(f"Fallback beep failed: {e}")
            return False


# Module-level instance
_alarm_player: Optional[AlarmSound] = None


def get_alarm_player() -> AlarmSound:
    global _alarm_player
    if _alarm_player is None:
        _alarm_player = AlarmSound()
    return _alarm_player


def play_alarm(style: str = "ascending", repeats: int = 1) -> bool:
    return get_alarm_player().play_alarm(style=style, repeats=repeats)


def stop_alarm() -> bool:
    return get_alarm_player().stop_alarm()
