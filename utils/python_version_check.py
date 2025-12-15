"""Display a prominent warning banner if Python version is incorrect.
This module is imported early to catch version issues immediately.
"""

import sys


def check_python_version() -> None:
    """Check Python version and display prominent warning if incorrect."""
    required_major = 3
    required_minor = 12

    current_major = sys.version_info.major
    current_minor = sys.version_info.minor
    current_micro = sys.version_info.micro

    if current_major < required_major or (
        current_major == required_major and current_minor < required_minor
    ):
        # Terminal warning
        banner_char = "█"
        warning = f"""
{banner_char * 80}
{banner_char}                                                                              {banner_char}
{banner_char}  ⚠️  ⚠️  ⚠️   CRITICAL: WRONG PYTHON VERSION   ⚠️  ⚠️  ⚠️                     {banner_char}
{banner_char}                                                                              {banner_char}
{banner_char}  Current: Python {current_major}.{current_minor}.{current_micro}                                                      {banner_char}
{banner_char}  Required: Python {required_major}.{required_minor}+                                                     {banner_char}
{banner_char}                                                                              {banner_char}
{banner_char}  This WILL cause runtime errors with:                                       {banner_char}
{banner_char}  • Modern type hints (| unions)                                             {banner_char}
{banner_char}  • datetime.UTC                                                             {banner_char}
{banner_char}  • tuple[...] syntax                                                        {banner_char}
{banner_char}                                                                              {banner_char}
{banner_char}  SOLUTION:                                                                  {banner_char}
{banner_char}  1. Use launcher: run_app_312.bat or run_app_312.ps1                       {banner_char}
{banner_char}  2. Or manually: .venv312\\Scripts\\Activate.ps1                             {banner_char}
{banner_char}                                                                              {banner_char}
{banner_char}  Python path: {sys.executable:<60}{banner_char}
{banner_char}                                                                              {banner_char}
{banner_char * 80}
"""
        print(warning)
        return False

    return True


# Auto-check on import
if __name__ != "__main__":
    is_correct = check_python_version()
    if not is_correct:
        print("\n⚠️  Continuing with WRONG Python version - expect errors!\n")
