import time
from datetime import UTC, datetime


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(UTC)


def now_iso_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def now_utc_iso() -> str:
    """Alias for now_iso_utc() for compatibility."""
    return now_iso_utc()


def monotonic() -> float:
    return time.perf_counter()


def filename_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def for_filename(prefix: str = "", ext: str = "txt") -> str:
    """Generate a filename with timestamp.

    Args:
        prefix: Prefix for the filename (e.g., 'calibration_')
        ext: File extension without dot (e.g., 'log', 'json')

    Returns:
        Filename like 'calibration_20251201_143052.log'

    """
    timestamp = filename_timestamp()
    return f"{prefix}{timestamp}.{ext}"
