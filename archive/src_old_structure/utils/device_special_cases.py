"""Device Special Cases - Device-specific configurations indexed by detector serial number.

This module maintains a registry of devices that require special handling due to:
- Hardware quirks or variations
- Calibration anomalies
- Custom modifications
- Early production units with different characteristics

After successful hardware connection, the detector serial number is checked against
this registry. If found, the special case configuration is applied before normal operation.
"""

from typing import Any

from utils.logger import logger

# ============================================================================
# SPECIAL CASES REGISTRY
# ============================================================================
# Key: Detector Serial Number (string)
# Value: Dictionary of special case parameters
#
# Available special case parameters:
# - 'description': Brief description of the special case
# - 'afterglow_correction': Custom afterglow settings
# - 'led_intensity_scaling': Custom LED intensity multipliers per channel
# - 'servo_positions': Custom servo position overrides (s_pos, p_pos)
# - 'integration_time': Custom integration time (ms)
# - 'notes': Additional notes for reference
# - Any other device-specific parameters...
# ============================================================================

SPECIAL_CASES: dict[str, dict[str, Any]] = {
    # ==========================================================================
    # ACTIVE SPECIAL CASES - These travel with the software installation
    # ==========================================================================
    # Known detector with Channel B requiring special treatment
    # TODO: Replace "USB40HXXXXX" with actual detector serial number
    "USB40HXXXXX": {
        "description": "Channel B requires different treatment - known hardware variation",
        "channel_b_override": {
            "afterglow_correction": 1.25,  # Channel B has higher afterglow
            "led_intensity_scaling": 0.90,  # Reduce LED intensity by 10%
            "requires_special_processing": True,
        },
        "afterglow_correction": {
            "channel_a": 1.00,
            "channel_b": 1.25,  # Channel B higher afterglow correction
            "channel_c": 1.00,
            "channel_d": 1.00,
        },
        "led_intensity_scaling": {
            "a": 1.0,
            "b": 0.90,  # Reduce channel B LED intensity
            "c": 1.0,
            "d": 1.0,
        },
        "notes": "Channel B has known hardware variation - do not recalibrate without engineering approval",
    },
    # Example special case (template - remove or modify as needed):
    # "USB4C12345": {
    #     'description': 'Early production unit with non-standard LED layout',
    #     'afterglow_correction': {
    #         'channel_a': 1.15,
    #         'channel_b': 1.08,
    #         'channel_c': 1.12,
    #         'channel_d': 1.05
    #     },
    #     'servo_positions': {
    #         's_pos': 45,
    #         'p_pos': 135
    #     },
    #     'led_intensity_scaling': {
    #         'a': 1.0,
    #         'b': 0.95,
    #         'c': 1.05,
    #         'd': 0.98
    #     },
    #     'integration_time': 50,  # milliseconds
    #     'notes': 'Contact engineering if recalibration needed'
    # },
    # Add actual special cases below:
    # ================================
}


def check_special_case(detector_serial: str | None) -> dict[str, Any] | None:
    """Check if detector serial number has a special case configuration.

    Args:
        detector_serial: The detector's serial number (e.g., 'USB4X12345')

    Returns:
        Dictionary of special case parameters if found, None otherwise

    Example:
        >>> special_case = check_special_case('USB4X12345')
        >>> if special_case:
        ...     print(f"Special case: {special_case['description']}")
        ...     apply_special_case(special_case)

    """
    if not detector_serial:
        logger.debug("No detector serial number provided - skipping special case check")
        return None

    if detector_serial in SPECIAL_CASES:
        special_case = SPECIAL_CASES[detector_serial]
        logger.warning("=" * 60)
        logger.warning(f"⚠️ SPECIAL CASE DETECTED - S/N: {detector_serial}")
        logger.warning(
            f"   Description: {special_case.get('description', 'No description')}",
        )
        if "notes" in special_case:
            logger.warning(f"   Notes: {special_case['notes']}")
        logger.warning("=" * 60)
        return special_case

    logger.debug(f"No special case found for detector S/N: {detector_serial}")
    return None


def apply_special_case(
    special_case: dict[str, Any],
    device_config: dict[str, Any],
) -> dict[str, Any]:
    """Apply special case parameters to device configuration.

    Args:
        special_case: Special case parameters from the registry
        device_config: Current device configuration dictionary

    Returns:
        Updated device configuration with special case applied

    Note:
        This function modifies device_config in-place and returns it.

    """
    if not special_case:
        return device_config

    logger.info("Applying special case configuration...")

    # Apply afterglow correction overrides
    if "afterglow_correction" in special_case:
        afterglow = special_case["afterglow_correction"]
        logger.info(f"  → Afterglow correction: {afterglow}")
        device_config["afterglow_correction"] = afterglow

    # Apply LED intensity scaling
    if "led_intensity_scaling" in special_case:
        scaling = special_case["led_intensity_scaling"]
        logger.info(f"  → LED intensity scaling: {scaling}")
        device_config["led_intensity_scaling"] = scaling

    # Apply servo position overrides
    if "servo_positions" in special_case:
        servo = special_case["servo_positions"]
        logger.info(
            f"  → Servo positions: S={servo.get('s_pos')}, P={servo.get('p_pos')}",
        )
        if "s_pos" in servo:
            device_config["s_pos"] = servo["s_pos"]
        if "p_pos" in servo:
            device_config["p_pos"] = servo["p_pos"]

    # Apply integration time override
    if "integration_time" in special_case:
        int_time = special_case["integration_time"]
        logger.info(f"  → Integration time: {int_time}ms")
        device_config["integration_time"] = int_time

    # Apply any other custom parameters
    for key, value in special_case.items():
        if key not in [
            "description",
            "notes",
            "afterglow_correction",
            "led_intensity_scaling",
            "servo_positions",
            "integration_time",
        ]:
            logger.info(f"  → {key}: {value}")
            device_config[key] = value

    logger.info("✅ Special case configuration applied")
    return device_config


def list_special_cases() -> None:
    """Print all registered special cases to the log.

    Useful for debugging and documentation purposes.
    """
    if not SPECIAL_CASES:
        logger.info("No special cases registered")
        return

    logger.info("=" * 60)
    logger.info(f"REGISTERED SPECIAL CASES ({len(SPECIAL_CASES)} total)")
    logger.info("=" * 60)

    for serial, config in SPECIAL_CASES.items():
        logger.info(f"S/N: {serial}")
        logger.info(f"  Description: {config.get('description', 'No description')}")
        if "notes" in config:
            logger.info(f"  Notes: {config['notes']}")
        logger.info("-" * 60)


def add_special_case(detector_serial: str, description: str, **kwargs) -> None:
    """Programmatically add a special case to the registry.

    Args:
        detector_serial: The detector's serial number
        description: Brief description of the special case
        **kwargs: Additional special case parameters

    Example:
        >>> add_special_case(
        ...     'USB4X12345',
        ...     'Prototype unit with modified optics',
        ...     afterglow_correction={'channel_a': 1.2},
        ...     notes='Do not ship to customers'
        ... )

    """
    if detector_serial in SPECIAL_CASES:
        logger.warning(
            f"Special case for {detector_serial} already exists - overwriting",
        )

    SPECIAL_CASES[detector_serial] = {
        "description": description,
        **kwargs,
    }

    logger.info(f"Special case added for detector S/N: {detector_serial}")


def remove_special_case(detector_serial: str) -> bool:
    """Remove a special case from the registry.

    Args:
        detector_serial: The detector's serial number

    Returns:
        True if special case was removed, False if not found

    """
    if detector_serial in SPECIAL_CASES:
        del SPECIAL_CASES[detector_serial]
        logger.info(f"Special case removed for detector S/N: {detector_serial}")
        return True

    logger.warning(f"No special case found for detector S/N: {detector_serial}")
    return False
