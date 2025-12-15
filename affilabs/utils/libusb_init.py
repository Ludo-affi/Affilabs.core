"""Initialize libusb paths for Windows - OPTIONAL for Ocean Optics spectrometers.

This module provides libusb backend initialization for Ocean Optics spectrometers
on Windows. It's completely optional and the software will work without it for
other detector types.
"""

import os
import sys


def find_libusb_dll():
    """Find libusb-1.0.dll in the workspace or venv.

    Returns:
        str: Absolute path to libusb-1.0.dll, or None if not found

    """
    if sys.platform != "win32":
        return None

    # Get project root (2 levels up from this file: ezControl-AI/affilabs/utils/)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    search_paths = [
        # PyInstaller frozen exe - DLL is extracted to temp folder
        os.path.join(getattr(sys, "_MEIPASS", ""), "libusb-1.0.dll"),
        # PyInstaller alternate location
        os.path.join(getattr(sys, "_MEIPASS", ""), "affilabs", "libusb-1.0.dll"),
        os.path.join(project_root, "libusb-1.0.dll"),  # Project root
        os.path.join(sys.prefix, "Scripts", "libusb-1.0.dll"),  # venv Scripts
        os.path.join(sys.prefix, "libusb-1.0.dll"),  # venv root
        os.path.join(
            sys.prefix,
            "Lib",
            "site-packages",
            "libusb_package",
            "libusb-1.0.dll",
        ),
    ]

    # Also check user site-packages (for global pip install)
    try:
        import site

        user_site = site.getusersitepackages()
        if user_site:
            search_paths.append(
                os.path.join(user_site, "libusb_package", "libusb-1.0.dll"),
            )
    except:
        pass

    for path in search_paths:
        if os.path.exists(path):
            return path

    return None


def init_libusb_paths() -> None:
    """Add DLL search paths for libusb on Windows.

    This MUST be called before importing any USB libraries.
    Also performs early cleanup of stale USB device handles.
    """
    if sys.platform != "win32":
        return

    # EARLY CLEANUP: Force USB stack to forget any stale device handles
    # This prevents "device already opened" errors from ghost processes
    try:
        import usb.core

        # Just enumerate devices to force libusb to refresh its internal state
        # Don't actually open anything - just query basic info
        try:
            devs = usb.core.find(find_all=True)
            if devs:
                for dev in devs:
                    try:
                        # Access vendor ID to force device re-enumeration
                        _ = dev.idVendor
                    except Exception:
                        pass  # Device not accessible, that's fine
        except Exception:
            pass  # USB not available or no devices - that's OK
    except ImportError:
        pass  # pyusb not installed - OK for non-Ocean Optics systems

    # Get project root (where this file is located)
    project_root = os.path.dirname(os.path.dirname(__file__))

    dll_search_paths = [
        getattr(sys, "_MEIPASS", ""),  # PyInstaller temp extraction folder (CRITICAL)
        project_root,  # Project root (where libusb-1.0.dll is)
        os.path.join(sys.prefix, "Scripts"),  # venv Scripts folder
        sys.prefix,  # venv root
        os.path.join(
            sys.prefix,
            "Lib",
            "site-packages",
            "libusb_package",
        ),  # libusb-package location
    ]

    for path in dll_search_paths:
        if os.path.exists(path) and path:  # Check path is not empty string
            try:
                os.add_dll_directory(path)
            except (FileNotFoundError, OSError, AttributeError):
                pass  # Path already added or doesn't exist


def get_libusb_backend():
    """Get pyusb libusb backend with explicit DLL path.

    This is the most reliable way to get pyusb working on Windows for Ocean Optics
    spectrometers. Returns None if libusb isn't available, which is fine for other
    detector types.

    Returns:
        usb.backend.libusb1._LibUSB: Backend instance, or None if not available

    """
    dll_path = find_libusb_dll()
    if not dll_path:
        return None

    try:
        from usb.backend import libusb1

        return libusb1.get_backend(find_library=lambda x: dll_path)
    except Exception:
        return None


# Auto-initialize on import
init_libusb_paths()
