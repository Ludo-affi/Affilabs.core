"""Cross-platform alarm sound generator using pygame.

Generates professional-sounding alert tones without needing external sound files.

FEATURES:
- Cross-platform (Windows, Mac, Linux)
- Uses pygame for reliable audio playback
- Generates alarm using numpy (no external files)
- Graceful fallback to system beep
- Multiple alarm styles available
"""

import sys
import numpy as np
from typing import Optional
from affilabs.utils.logger import logger


class AlarmSound:
    """Alarm sound player using pygame with synthesized tones."""

    def __init__(self):
        """Initialize pygame mixer for audio playback."""
        self._pygame_available = False
        self._mixer = None
        self._last_sound = None

        try:
            import pygame
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._pygame_available = True
            self._mixer = pygame.mixer
            logger.debug("✓ Pygame mixer initialized for alarm sound")
        except Exception as e:
            logger.debug(f"Pygame not available for alarm: {e}. Fallback to system beep.")

    def generate_alert_tone(
        self,
        duration_ms: int = 500,
        style: str = "ascending"
    ) -> Optional[object]:
        """Generate synthesized alarm tone without external files.

        Args:
            duration_ms: Duration in milliseconds
            style: "ascending" (classic alert), "buzzer" (harsh), "bell" (chime)

        Returns:
            pygame.mixer.Sound object or None if generation failed
        """
        try:
            sample_rate = 22050
            duration_sec = duration_ms / 1000.0
            num_samples = int(sample_rate * duration_sec)
            t = np.linspace(0, duration_sec, num_samples)

            if style == "ascending":
                # 3-tone ascending alert (like notification) - very professional
                # Tone 1: 800 Hz (0.15s)
                # Tone 2: 900 Hz (0.15s)
                # Tone 3: 1100 Hz (0.2s)
                samples1 = np.sin(2.0 * np.pi * 800 * t[:int(0.15 * sample_rate)]) * 0.3
                samples2 = np.sin(2.0 * np.pi * 900 * t[:int(0.15 * sample_rate)]) * 0.3
                samples3 = np.sin(2.0 * np.pi * 1100 * t[:int(0.2 * sample_rate)]) * 0.3
                samples = np.concatenate([samples1, samples2, samples3])

            elif style == "buzzer":
                # Harsh buzzer (500Hz + 600Hz combined)
                samples = (
                    np.sin(2.0 * np.pi * 500 * t) +
                    np.sin(2.0 * np.pi * 600 * t)
                ) * 0.25

            elif style == "bell":
                # Pleasant bell chime (decreasing)
                freq_start = 1200
                freq_end = 300
                freq = np.linspace(freq_start, freq_end, num_samples)
                # Amplitude envelope (fade out)
                envelope = np.exp(-3 * t / duration_sec)
                samples = np.sin(2.0 * np.pi * freq * t) * envelope * 0.3
            else:
                # Default: ascending
                samples = np.sin(2.0 * np.pi * 800 * t) * 0.3

            # Normalize to prevent clipping
            max_val = np.max(np.abs(samples))
            if max_val > 0:
                samples = samples / max_val * 0.8

            # Convert to 16-bit PCM
            samples_int16 = np.int16(samples * 32767)

            # Create stereo (duplicate for both channels)
            stereo_samples = np.zeros((len(samples_int16), 2), dtype=np.int16)
            stereo_samples[:, 0] = samples_int16
            stereo_samples[:, 1] = samples_int16

            # Create pygame Sound object
            if self._pygame_available:
                sound = self._mixer.Sound(stereo_samples.tobytes())
                return sound
            return None

        except Exception as e:
            logger.debug(f"Could not generate alarm tone: {e}")
            return None

    def play_alarm(self, style: str = "ascending", repeats: int = 1) -> bool:
        """Play alarm sound.

        Args:
            style: "ascending" (default), "buzzer", "bell"
            repeats: Number of times to repeat (1 = once, -1 = infinite loop)

        Returns:
            True if playback started, False otherwise
        """
        try:
            if not self._pygame_available:
                return self._fallback_beep()

            sound = self.generate_alert_tone(duration_ms=500, style=style)
            if sound:
                self._last_sound = sound
                # -1 means infinite loop, otherwise play repeats times
                sound.play(loops=repeats - 1 if repeats > 0 else -1)
                return True
            return self._fallback_beep()

        except Exception as e:
            logger.debug(f"Could not play alarm: {e}")
            return self._fallback_beep()

    def stop_alarm(self):
        """Stop current alarm playback."""
        try:
            if self._pygame_available and self._mixer:
                self._mixer.stop()
                self._last_sound = None
                return True
        except Exception as e:
            logger.debug(f"Could not stop alarm: {e}")
        return False

    def _fallback_beep(self) -> bool:
        """Fallback to system beep on platforms without pygame."""
        try:
            if sys.platform == "win32":
                import winsound
                # Use MB_ICONEXCLAMATION for a better beep than MB_ICONASTERISK
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return True
            else:
                # Unix/Linux/Mac terminal bell
                print('\a', flush=True)
                return True
        except Exception as e:
            logger.debug(f"Fallback beep failed: {e}")
            return False


# Module-level instance for easy access
_alarm_player: Optional[AlarmSound] = None


def get_alarm_player() -> AlarmSound:
    """Get or create the module-level alarm player instance."""
    global _alarm_player
    if _alarm_player is None:
        _alarm_player = AlarmSound()
    return _alarm_player


def play_alarm(style: str = "ascending", repeats: int = 1) -> bool:
    """Convenience function to play alarm.

    Args:
        style: "ascending" (default), "buzzer", "bell"
        repeats: Number of times to repeat (1 = once, -1 = infinite loop)

    Returns:
        True if playback started, False otherwise
    """
    return get_alarm_player().play_alarm(style=style, repeats=repeats)


def stop_alarm() -> bool:
    """Convenience function to stop alarm playback."""
    return get_alarm_player().stop_alarm()
