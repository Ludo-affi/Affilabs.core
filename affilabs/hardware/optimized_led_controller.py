"""Optimized LED Controller - Fast atomic LED operations

This wrapper provides atomic LED operations for calibration measurements.
Requires firmware V1.9+ for multi-LED batch commands.
"""

import time


class OptimizedLEDController:
    """Wrapper for atomic LED control during calibration."""

    def __init__(self, controller):
        """Args:
        controller: PicoP4SPR controller instance

        """
        self.ctrl = controller
        self._calibration_mode = False

    def get_info(self):
        """Get controller information."""
        return {
            "name": self.ctrl.name if hasattr(self.ctrl, "name") else "Unknown",
            "firmware_version": getattr(self.ctrl, "firmware_version", "Unknown"),
            "supports_batch": True,  # V1.9+ firmware
        }

    def enter_calibration_mode(self):
        """Enter calibration mode (enables batch LED commands)."""
        try:
            # Enable batch mode for all 4 LEDs
            self.ctrl._ser.write(b"lm:A,B,C,D\n")
            time.sleep(0.1)
            self._calibration_mode = True
            return True
        except Exception as e:
            print(f"Error entering calibration mode: {e}")
            return False

    def exit_calibration_mode(self):
        """Exit calibration mode."""
        try:
            self.turn_off_all_leds()
            # Disable batch mode
            self.ctrl._ser.write(b"lx\n")
            time.sleep(0.1)
            self._calibration_mode = False
            return True
        except Exception:
            return False

    def configure_led_atomic(self, channel, intensity):
        """Set LED intensity atomically (single operation).

        Args:
            channel: LED channel ('A', 'B', 'C', 'D')
            intensity: LED intensity (0-255)

        """
        self.ctrl.set_intensity(channel.lower(), intensity)
        time.sleep(0.05)  # Small delay for LED stability

    def turn_off_all_leds(self):
        """Turn off all LEDs."""
        try:
            self.ctrl.leds_off()
            time.sleep(0.05)
        except Exception:
            pass


def create_optimized_controller(controller):
    """Create an optimized LED controller wrapper.

    Args:
        controller: PicoP4SPR controller instance

    Returns:
        OptimizedLEDController instance

    """
    return OptimizedLEDController(controller)
