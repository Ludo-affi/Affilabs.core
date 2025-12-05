"""Spectrometer Hardware Adapter

Wraps existing spectrometer implementations (USB4000, PhasePhotonics)
behind the ISpectrometer interface for consistent access.
"""

from typing import Optional
import numpy as np
from .device_interface import (
    ISpectrometer,
    DeviceInfo,
    SpectrometerCapabilities,
    ConnectionError as HWConnectionError,
    CommandError
)

# Import existing spectrometer classes
from src.utils.usb4000_wrapper import USB4000

try:
    from src.utils.phase_photonics_wrapper import PhasePhotonics
    PHASE_PHOTONICS_AVAILABLE = True
except ImportError:
    PHASE_PHOTONICS_AVAILABLE = False


class USB4000Adapter(ISpectrometer):
    """Adapter for Ocean Optics USB4000/FLAME-T spectrometer.

    Wraps existing USB4000 implementation behind ISpectrometer interface.
    """

    def __init__(self, spectrometer: Optional[USB4000] = None):
        """Initialize adapter.

        Args:
            spectrometer: Existing USB4000 instance, or None to create new
        """
        self._spectrometer = spectrometer or USB4000()
        self._connected = False

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, **kwargs) -> bool:
        """Connect to spectrometer.

        Args:
            **kwargs: Optional serial_number, timeout
        """
        try:
            success = self._spectrometer.open()
            if success:
                self._connected = True
            return success
        except Exception as e:
            raise HWConnectionError(f"Spectrometer connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from spectrometer."""
        try:
            if hasattr(self._spectrometer, 'close'):
                self._spectrometer.close()
        except Exception:
            pass  # Never raise on disconnect
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """Check if spectrometer is connected."""
        return self._connected and getattr(self._spectrometer, 'opened', False)

    def get_info(self) -> DeviceInfo:
        """Get device identification."""
        serial = getattr(self._spectrometer, 'serial_number', None)

        # Determine model
        model = "USB4000"
        if hasattr(self._spectrometer, '_device') and self._spectrometer._device:
            try:
                model = self._spectrometer._device.model
            except:
                pass

        return DeviceInfo(
            device_type="spectrometer",
            model=model,
            serial_number=serial,
            firmware_version=None,
            hardware_version=None,
            port=None
        )

    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get spectrometer capabilities."""
        # Get device-specific values
        num_pixels = getattr(self._spectrometer, '_num_pixels', 3648)
        max_counts = getattr(self._spectrometer, '_max_counts', 65535)

        return SpectrometerCapabilities(
            wavelength_range=(200.0, 1100.0),
            wavelength_resolution=0.3,
            num_pixels=num_pixels,
            min_integration_time=1.0,  # ms
            max_integration_time=10000.0,  # ms
            bit_depth=16,
            max_counts=max_counts,
            supports_dark_correction=True,
            supports_averaging=True,
            max_averages=100,
            backend="seabreeze",
            supports_reconnect=True,
            supports_firmware_update=False,
            requires_calibration=False
        )

    # ========================================================================
    # WAVELENGTH CALIBRATION
    # ========================================================================

    def get_wavelengths(self) -> np.ndarray:
        """Get wavelength calibration array."""
        try:
            # wavelengths is a property, not a method
            wl = self._spectrometer.wavelengths
            if wl is None:
                raise CommandError("Wavelength calibration not available")
            return np.array(wl)
        except Exception as e:
            raise CommandError(f"Failed to get wavelengths: {e}")

    # ========================================================================
    # INTEGRATION TIME
    # ========================================================================

    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time in milliseconds."""
        if time_ms < 1.0 or time_ms > 10000.0:
            raise ValueError(f"Integration time must be 1-10000 ms, got {time_ms}")

        try:
            if hasattr(self._spectrometer, 'set_integration'):
                self._spectrometer.set_integration(time_ms)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to set integration time: {e}")

    def get_integration_time(self) -> float:
        """Get current integration time in milliseconds."""
        try:
            return getattr(self._spectrometer, '_integration_time', 100.0)
        except Exception:
            return 100.0

    # ========================================================================
    # ACQUISITION
    # ========================================================================

    def read_spectrum(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Capture and return spectrum."""
        if num_scans < 1:
            raise ValueError(f"num_scans must be >= 1, got {num_scans}")

        try:
            # USB4000 uses read_intensity() method
            if hasattr(self._spectrometer, 'read_intensity'):
                intensities = self._spectrometer.read_intensity()
                if intensities is None:
                    return None
                return np.array(intensities)
            return None
        except Exception as e:
            raise CommandError(f"Failed to read spectrum: {e}")

    def read_intensities(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Alias for read_spectrum() for compatibility."""
        return self.read_spectrum(num_scans)


class PhasePhotonicsAdapter(ISpectrometer):
    """Adapter for Phase Photonics spectrometer.

    Wraps PhasePhotonics implementation behind ISpectrometer interface.
    """

    def __init__(self, spectrometer=None):
        """Initialize adapter.

        Args:
            spectrometer: Existing PhasePhotonics instance, or None to create new
        """
        if not PHASE_PHOTONICS_AVAILABLE:
            raise ImportError("PhasePhotonics driver not available")

        self._spectrometer = spectrometer or PhasePhotonics()
        self._connected = False

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    def connect(self, **kwargs) -> bool:
        """Connect to Phase Photonics spectrometer."""
        try:
            success = self._spectrometer.open()
            if success:
                self._connected = True
            return success
        except Exception as e:
            raise HWConnectionError(f"Phase Photonics connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from spectrometer."""
        try:
            if hasattr(self._spectrometer, 'close'):
                self._spectrometer.close()
        except Exception:
            pass
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """Check if spectrometer is connected."""
        return self._connected and getattr(self._spectrometer, 'opened', False)

    def get_info(self) -> DeviceInfo:
        """Get device identification."""
        return DeviceInfo(
            device_type="spectrometer",
            model="PhasePhotonics",
            serial_number=None,
            firmware_version=None,
            hardware_version=None,
            port=None
        )

    def get_capabilities(self) -> SpectrometerCapabilities:
        """Get spectrometer capabilities."""
        return SpectrometerCapabilities(
            wavelength_range=(200.0, 1100.0),
            wavelength_resolution=0.1,  # Higher resolution than USB4000
            num_pixels=4096,
            min_integration_time=1.0,
            max_integration_time=10000.0,
            bit_depth=16,
            max_counts=65535,
            supports_dark_correction=True,
            supports_averaging=True,
            max_averages=100,
            backend="phase_photonics",
            supports_reconnect=True,
            supports_firmware_update=False,
            requires_calibration=False
        )

    # ========================================================================
    # WAVELENGTH CALIBRATION
    # ========================================================================

    def get_wavelengths(self) -> np.ndarray:
        """Get wavelength calibration array."""
        try:
            # wavelengths is a property, not a method
            wl = self._spectrometer.wavelengths
            if wl is None:
                raise CommandError("Wavelength calibration not available")
            return np.array(wl)
        except Exception as e:
            raise CommandError(f"Failed to get wavelengths: {e}")

    # ========================================================================
    # INTEGRATION TIME
    # ========================================================================

    def set_integration_time(self, time_ms: float) -> bool:
        """Set integration time in milliseconds."""
        try:
            if hasattr(self._spectrometer, 'set_integration'):
                self._spectrometer.set_integration(time_ms)
                return True
            return False
        except Exception as e:
            raise CommandError(f"Failed to set integration time: {e}")

    def get_integration_time(self) -> float:
        """Get current integration time in milliseconds."""
        return getattr(self._spectrometer, '_integration_time', 100.0)

    # ========================================================================
    # ACQUISITION
    # ========================================================================

    def read_spectrum(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Capture and return spectrum."""
        try:
            intensities = self._spectrometer.intensities(num_scans)
            if intensities is None:
                return None
            return np.array(intensities)
        except Exception as e:
            raise CommandError(f"Failed to read spectrum: {e}")

    def read_intensities(self, num_scans: int = 1) -> Optional[np.ndarray]:
        """Alias for read_spectrum()."""
        return self.read_spectrum(num_scans)


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_spectrometer_adapter(
    spectrometer_type: str = "usb4000",
    **kwargs
) -> ISpectrometer:
    """Factory function to create spectrometer adapter by type.

    Args:
        spectrometer_type: 'usb4000' or 'phase_photonics'
        **kwargs: Additional parameters

    Returns:
        ISpectrometer implementation

    Raises:
        ValueError: If spectrometer_type is unknown
    """
    spec_type = spectrometer_type.lower()

    if spec_type == "usb4000":
        return USB4000Adapter()
    elif spec_type == "phase_photonics":
        if not PHASE_PHOTONICS_AVAILABLE:
            raise ValueError("Phase Photonics driver not available")
        return PhasePhotonicsAdapter()
    else:
        raise ValueError(
            f"Unknown spectrometer type '{spectrometer_type}'. "
            f"Valid types: ['usb4000', 'phase_photonics']"
        )


def wrap_existing_spectrometer(spectrometer) -> ISpectrometer:
    """Wrap an existing spectrometer instance in an adapter.

    Args:
        spectrometer: Existing USB4000 or PhasePhotonics instance

    Returns:
        ISpectrometer adapter
    """
    if isinstance(spectrometer, USB4000):
        return USB4000Adapter(spectrometer)
    elif PHASE_PHOTONICS_AVAILABLE and isinstance(spectrometer, PhasePhotonics):
        return PhasePhotonicsAdapter(spectrometer)
    else:
        raise ValueError(f"Unknown spectrometer type: {type(spectrometer)}")
