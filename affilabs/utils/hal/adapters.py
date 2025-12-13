"""Adapters that implement HAL interfaces by delegating to existing objects."""

from __future__ import annotations

from typing import Optional, List, Dict, Any

import ctypes
import numpy as np
from affilabs.utils.phase_photonics_api import SENSOR_FRAME_T
from .interfaces import LEDController, LEDCommand, SpectrometerInfo, Spectrometer
from affilabs.utils.logger import logger


class CtrlLEDAdapter(LEDController):
    def __init__(self, ctrl) -> None:
        self._ctrl = ctrl
        self._controller_type = type(ctrl).__name__
        logger.debug(f"Initialized LED adapter for {self._controller_type}")

    def turn_on_channel(self, ch: str) -> None:  # type: ignore[override]
        self._ctrl.turn_on_channel(ch=ch)

    def turn_off_channels(self) -> None:  # type: ignore[override]
        self._ctrl.turn_off_channels()

    def set_intensity(self, ch: str, raw_val: int) -> None:  # type: ignore[override]
        self._ctrl.set_intensity(ch=ch, raw_val=raw_val)

    def set_mode(self, mode: str) -> None:  # type: ignore[override]
        self._ctrl.set_mode(mode)

    def execute_batch(self, commands: List[LEDCommand]) -> bool:  # type: ignore[override]
        """Execute batch LED commands with optimized protocol.

        For Pico controllers, uses batch command: lb<mode><intensity><ch_a><int_a>...
        For other controllers, falls back to sequential execution.
        """
        try:
            # Check if controller supports batch commands (Pico variants)
            supports_batch = 'Pico' in self._controller_type

            if not supports_batch:
                # Fall back to sequential execution
                for cmd in commands:
                    if cmd.action == 'on':
                        self.turn_on_channel(cmd.channel)
                    elif cmd.action == 'off':
                        self.turn_off_channels()
                    elif cmd.action == 'intensity':
                        self.set_intensity(cmd.channel, cmd.intensity)
                    elif cmd.action == 'mode':
                        self.set_mode(cmd.mode)
                return True

            # Analyze commands for batch optimization
            mode = None
            intensities = {}

            for cmd in commands:
                if cmd.action == 'mode':
                    mode = cmd.mode
                elif cmd.action == 'intensity':
                    intensities[cmd.channel] = cmd.intensity

            # Use batch command if we have mode + multiple intensities
            if mode and len(intensities) >= 2:
                # Build batch command: lb<mode><default_intensity><ch_a><int_a><ch_b><int_b>...
                batch_cmd = f"lb{mode}255"

                for ch in ['a', 'b', 'c', 'd']:
                    if ch in intensities:
                        batch_cmd += f"{ch}{intensities[ch]:03d}"

                batch_cmd += "\n"

                # Send via controller's serial interface
                # Use same pattern as controller methods: check _ser or call open()
                if hasattr(self._ctrl, '_ser') and hasattr(self._ctrl, 'open'):
                    if self._ctrl._ser is not None or self._ctrl.open():
                        if hasattr(self._ctrl, '_lock'):
                            with self._ctrl._lock:
                                self._ctrl._ser.write(batch_cmd.encode())
                                response = self._ctrl._ser.readline().strip()
                        else:
                            self._ctrl._ser.write(batch_cmd.encode())
                            response = self._ctrl._ser.readline().strip()

                        if response == b'1':
                            logger.debug(f"[OK] Batch LED command: {batch_cmd.strip()}")
                            return True
                        else:
                            logger.warning(f"[ERROR] Batch LED failed, response: {response}")
                            return False
                    else:
                        logger.error("Failed to open serial port for batch command")
                        return False
                else:
                    logger.error("Controller doesn't support serial batch commands")
                    return False
            else:
                # Not enough commands to justify batch, execute sequentially
                for cmd in commands:
                    if cmd.action == 'on':
                        self.turn_on_channel(cmd.channel)
                    elif cmd.action == 'off':
                        self.turn_off_channels()
                    elif cmd.action == 'intensity':
                        self.set_intensity(cmd.channel, cmd.intensity)
                    elif cmd.action == 'mode':
                        self.set_mode(cmd.mode)
                return True

        except Exception as e:
            logger.error(f"Batch command execution failed: {e}")
            return False

    def get_capabilities(self) -> Dict[str, Any]:  # type: ignore[override]
        """Return controller capabilities"""
        supports_batch = 'Pico' in self._controller_type
        return {
            'supports_batch': supports_batch,
            'controller_type': self._controller_type,
            'max_intensity': 255,
            'channels': ['a', 'b', 'c', 'd'],
            'modes': ['s', 'p'],
        }


class UsbSpectrometerInfoAdapter(SpectrometerInfo):
    def __init__(self, usb) -> None:
        self._usb = usb

    @property
    def serial_number(self) -> Optional[str]:  # type: ignore[override]
        return getattr(self._usb, "serial_number", None)


class OceanSpectrometerAdapter(Spectrometer):
    """Adapter exposing spectrometer via HAL interface.

    Wraps detector objects (USB4000, PhasePhotonics, etc.) and provides an
    optimized ROI reader. Works with any detector that implements:
    - read_intensity() -> ndarray
    - read_wavelength() -> ndarray
    - set_integration(ms: float)
    - serial_number property
    - min_integration property

    For SeaBreeze-based detectors (USB4000), uses direct intensity reads.
    For DLL-based detectors (PhasePhotonics), uses fast path via sensor frames.
    """

    def __init__(self, usb) -> None:
        self._usb = usb

    def read_roi(self, wave_min_index: int, wave_max_index: int, num_scans: int = 1):  # type: ignore[override]
        try:
            if getattr(self._usb, "use_seabreeze", False):
                if num_scans == 1:
                    full = self._usb.read_intensity()
                    return full[wave_min_index:wave_max_index].astype('u4') if full is not None else None
                else:
                    spectrum_length = wave_max_index - wave_min_index
                    stack = np.empty((num_scans, spectrum_length), dtype='u2')
                    for i in range(num_scans):
                        full = self._usb.read_intensity()
                        if full is None:
                            return None
                        stack[i] = full[wave_min_index:wave_max_index]
                    return np.mean(stack, axis=0).astype('u4')
            else:
                # DLL backend fast path
                offset = wave_min_index * 2
                num = wave_max_index - wave_min_index
                usb_read_image = self._usb.api.sensor_t_dll.usb_read_image
                usb_read_image.argtypes = [ctypes.c_void_p, ctypes.POINTER(SENSOR_FRAME_T)]
                usb_read_image.restype = ctypes.c_int32
                sensor_frame_t = SENSOR_FRAME_T()
                sensor_frame_t_ref = ctypes.byref(sensor_frame_t)
                spec = self._usb.spec
                if num_scans == 1:
                    usb_read_image(spec, sensor_frame_t_ref)
                    return np.frombuffer(sensor_frame_t.pixels, 'u2', num, offset).astype('u4')
                else:
                    stack = np.empty((num_scans, num), dtype='u2')
                    for i in range(num_scans):
                        usb_read_image(spec, sensor_frame_t_ref)
                        stack[i] = np.frombuffer(sensor_frame_t.pixels, 'u2', num, offset)
                    return np.mean(stack, axis=0).astype('u4')
        except Exception:
            return None

    def read_wavelength(self) -> np.ndarray:  # type: ignore[override]
        return self._usb.read_wavelength()

    def set_integration(self, integration_ms: int) -> None:  # type: ignore[override]
        self._usb.set_integration(integration_ms)

    @property
    def min_integration(self) -> float:  # type: ignore[override]
        return getattr(self._usb, "min_integration", 0.0)

    @property
    def serial_number(self) -> Optional[str]:  # type: ignore[override]
        return getattr(self._usb, "serial_number", None)
