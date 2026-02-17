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
    """Create and initialize a detector - DETECTOR AGNOSTIC.

    Automatically scans for both Ocean Optics USB4000 and PhasePhotonics detectors.
    Priority: USB4000 first (legacy), then PhasePhotonics.

    Args:
        app: Application instance (for callbacks/error handling)
        config: Configuration dictionary (detector_type ignored for auto-detection)

    Returns:
        Initialized detector instance, or None if no detector found

    """
    logger.debug("Scanning for detectors (auto-detect: USB4000 → PhasePhotonics)...")

    # Pre-scan: if any USB4000/Ocean Optics device is present, do NOT try PhasePhotonics
    # This avoids redundant PhasePhotonics scans when an Ocean Optics spectrometer is connected
    try:
        import seabreeze

        seabreeze.use("pyseabreeze")
        from seabreeze.spectrometers import list_devices

        devices_present = False
        try:
            devs = list_devices()
            devices_present = len(devs) > 0
            logger.debug(f"Pre-scan found {len(devs)} Ocean Optics device(s)")
        except Exception as pre_scan_err:
            logger.debug(f"Ocean Optics pre-scan failed: {pre_scan_err}")
            devices_present = False
    except Exception:
        # If seabreeze not available, proceed with normal flow
        devices_present = False

    # Try Ocean Optics USB4000 FIRST (legacy detector)
    try:
        logger.debug("Attempting USB4000 (Ocean Optics)...")
        from affilabs.utils.usb4000_wrapper import USB4000

        detector = USB4000(app)
        if detector.open():
            logger.debug("USB4000 spectrometer connected")
            return detector
        if devices_present:
            # Ocean Optics device is present but open failed; skip PhasePhotonics per user requirement
            logger.warning("Ocean Optics device present but open failed; skipping PhasePhotonics scan")
            return None
        logger.debug("USB4000 not found, trying PhasePhotonics...")
    except Exception as e:
        logger.debug(f"USB4000 scan failed: {e}")
        # If Ocean Optics devices are present but USB4000.open() raised, skip PhasePhotonics
        if 'devices_present' in locals() and devices_present:
            logger.warning(
                "USB4000 present but open raised; skipping PhasePhotonics per policy",
            )
            return None

    # Try PhasePhotonics SECOND (only if no Ocean Optics devices detected)
    if 'devices_present' in locals() and devices_present:
        logger.info("Ocean Optics device detected; skipping PhasePhotonics scan")
        return None
    try:
        logger.debug("Attempting PhasePhotonics...")
        from affilabs.utils.phase_photonics_wrapper import PhasePhotonics

        detector = PhasePhotonics(app)
        if detector.open():
            logger.info("✓ PhasePhotonics spectrometer connected")
            return detector
        logger.debug("PhasePhotonics not found")
    except Exception as e:
        logger.debug(f"PhasePhotonics scan failed: {e}")

    # No detector found
    logger.warning("No detectors found (tried USB4000, PhasePhotonics)")
    return None


def get_supported_detectors() -> list[str]:
    """Return list of supported detector types.

    Returns:
        List of detector type strings

    """
    return ["USB4000", "PhasePhotonics"]
