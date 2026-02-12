"""Sample Information Parser - Extract sample details from cycle metadata.

This module provides utilities to parse sample information from cycle name and notes
for manual injection workflows. When P4SPR hardware is detected, users need to manually
inject samples via syringe, and this parser extracts relevant sample information to
display in the manual injection dialog.

USAGE:
    from affilabs.utils.sample_parser import parse_sample_info
    from affilabs.domain.cycle import Cycle

    cycle = Cycle(
        type="Association",
        name="Association - Sample A",
        length_minutes=5.0,
        concentration_value=100.0,
        concentration_units="nM",
        channels="AC"
    )

    info = parse_sample_info(cycle)
    # Returns:
    # {
    #     "sample_id": "Sample A",
    #     "display_name": "Association - Sample A",
    #     "concentration": 100.0,
    #     "units": "nM",
    #     "channels": "AC"
    # }
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from affilabs.domain.cycle import Cycle


def parse_sample_info(cycle: Cycle) -> dict[str, Any]:
    """Parse sample information from cycle name and notes.

    Extracts sample identification from cycle metadata using multiple
    pattern matching strategies. Provides graceful fallback to cycle
    number if no sample info is found.

    Args:
        cycle: Cycle object with name, note, and metadata fields

    Returns:
        Dictionary with keys:
            - sample_id: Extracted sample identifier (str)
            - display_name: Full cycle name for context (str)
            - concentration: Concentration value if available (float or None)
            - units: Concentration units (str, default "nM")
            - channels: Target SPR channels (str, default "AC")

    Examples:
        >>> cycle = Cycle(type="Association", name="Sample A - Association", length_minutes=5.0)
        >>> info = parse_sample_info(cycle)
        >>> info["sample_id"]
        "Sample A"

        >>> cycle = Cycle(type="Wash", name="Wash Cycle", note="Sample: ABC-123", length_minutes=2.0)
        >>> info = parse_sample_info(cycle)
        >>> info["sample_id"]
        "ABC-123"

        >>> cycle = Cycle(type="Baseline", name="Baseline", length_minutes=3.0, cycle_num=5)
        >>> info = parse_sample_info(cycle)
        >>> info["sample_id"]
        "Cycle 5"
    """
    # Initialize result dictionary with defaults
    info = {
        "sample_id": None,
        "display_name": cycle.name or cycle.type,
        "concentration": cycle.concentration_value,
        "units": cycle.concentration_units or "nM",
        "channels": cycle.channels or "AC",
    }

    # Try parsing sample ID from cycle name
    # Common patterns in lab workflows:
    # - "Association - Sample A"
    # - "Sample ABC-123"
    # - "Conc Series - XYZ-456"
    # - "ABC-123 - Association"
    name_patterns = [
        r'Sample\s+([A-Za-z0-9\-_]+)',          # "Sample A", "Sample ABC-123"
        r'([A-Za-z0-9\-_]+)\s*-\s*(?:Association|Dissociation|Wash|Blocking)',  # "ABC-123 - Association"
        r'-\s*([A-Za-z0-9\-_]+)$',               # Trailing " - ABC"
        r'^([A-Za-z0-9\-_]+)\s*-',               # Leading "ABC - "
    ]

    for pattern in name_patterns:
        if match := re.search(pattern, cycle.name, re.IGNORECASE):
            sample_id_candidate = match.group(1).strip()
            # Filter out common cycle type keywords
            if sample_id_candidate.lower() not in ["association", "dissociation", "wash",
                                                     "baseline", "blocking", "regeneration",
                                                     "concentration", "custom"]:
                info["sample_id"] = sample_id_candidate
                break

    # Fallback: check notes field if no sample ID found in name
    if not info["sample_id"] and cycle.note:
        # Patterns in notes: "Sample: XYZ", "ID: ABC-123", "sample XYZ"
        note_patterns = [
            r'(?:sample|id)[\s:]+([A-Za-z0-9\-_]+)',  # "Sample: XYZ", "ID: ABC-123"
            r'Sample\s+([A-Za-z0-9\-_]+)',             # "Sample XYZ"
        ]

        for pattern in note_patterns:
            if match := re.search(pattern, cycle.note, re.IGNORECASE):
                info["sample_id"] = match.group(1).strip()
                break

    # Final fallback: use cycle number if available
    if not info["sample_id"]:
        if cycle.cycle_num > 0:
            info["sample_id"] = f"Cycle {cycle.cycle_num}"
        else:
            info["sample_id"] = "Unknown Sample"

    return info


def format_sample_display(sample_info: dict[str, Any]) -> str:
    """Format sample information for display in UI.

    Creates a human-readable string summarizing the sample information
    for display in dialogs, logs, or UI elements.

    Args:
        sample_info: Dictionary from parse_sample_info()

    Returns:
        Formatted string (e.g., "Sample A (100.0 nM) → Channels AC")

    Example:
        >>> info = {"sample_id": "Sample A", "concentration": 100.0, "units": "nM", "channels": "AC"}
        >>> format_sample_display(info)
        "Sample A (100.0 nM) → Channels AC"
    """
    parts = [sample_info["sample_id"]]

    # Add concentration if available
    if sample_info.get("concentration") is not None:
        conc = sample_info["concentration"]
        units = sample_info.get("units", "nM")
        parts.append(f"({conc} {units})")

    # Add channels
    channels = sample_info.get("channels", "AC")
    parts.append(f"→ Channels {channels}")

    return " ".join(parts)
