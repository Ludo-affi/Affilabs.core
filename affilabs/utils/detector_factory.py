"""Detector Factory - Hardware Abstraction Layer for Spectrometers.

This module provides a factory for creating detector instances, abstracting
the specific detector hardware (USB4000, PhasePhotonics, etc.) from the main application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from affilabs.utils.logger import logger

if TYPE_CHECKING:
    from typing import Any


def create_detector(app: Any, config: dict) -> Any | None:
    """Create and initialize a detector based on configuration.

    Args:
        app: Application instance (for callbacks/error handling)
        config: Configuration dictionary with detector settings

    Returns:
        Initialized detector instance, or None if initialization fails

    Configuration:
        detector_type: "USB4000" (default) or "PhasePhotonics"

    """
    detector_type = config.get("detector_type", "USB4000")

    try:
        if detector_type == "USB4000":
            logger.info("Initializing USB4000 (Ocean Optics) detector")
            from affilabs.utils.usb4000_wrapper import USB4000

            detector = USB4000(app)
            if detector.open():
                logger.info("USB4000 spectrometer connected successfully")
                return detector
            logger.warning("USB4000 spectrometer not found")
            return None

        if detector_type == "PhasePhotonics":
            logger.info("Initializing PhasePhotonics detector")
            from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

            detector = PhasePhotonics(app)
            if detector.open():
                logger.info("PhasePhotonics spectrometer connected successfully")
                return detector
            logger.warning("PhasePhotonics spectrometer not found")
            return None

        logger.error(f"Unknown detector type: {detector_type}")
        logger.info("Falling back to USB4000")
        from affilabs.utils.usb4000_wrapper import USB4000

        detector = USB4000(app)
        if detector.open():
            return detector
        return None

    except (FileNotFoundError, OSError, RuntimeError) as e:
        logger.error(f"Failed to initialize {detector_type} detector: {e}")
        return None
    except ImportError as e:
        logger.error(f"Detector module not found for {detector_type}: {e}")
        return None


def get_supported_detectors() -> list[str]:
    """Return list of supported detector types.

    Returns:
        List of detector type strings

    """
    return ["USB4000", "PhasePhotonics"]
