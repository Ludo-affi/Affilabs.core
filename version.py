"""Affilabs SPR Control System - Version Information"""

__version__ = "1.0.5"
__version_name__ = "Affilabs-Core v1.0.5"
__release_date__ = "2026-01-29"
__status__ = "Release"


def get_version_info() -> dict:
    """Get complete version information.

    Returns:
        Dictionary with version details

    """
    return {
        "version": __version__,
        "version_name": __version_name__,
        "release_date": __release_date__,
        "status": __status__,
        "full_title": f"Affilabs {__version__} - {__version_name__}",
    }


def get_version_string() -> str:
    """Get formatted version string for display.

    Returns:
        Formatted version string

    """
    return f"Affilabs {__version__} '{__version_name__}' ({__release_date__})"


if __name__ == "__main__":
    info = get_version_info()
    print(f"\n{'='*60}")
    print(f"  {info['full_title']}")
    print(f"{'='*60}")
    print(f"  Release Date: {info['release_date']}")
    print(f"  Status:       {info['status']}")
    print(f"{'='*60}\n")
