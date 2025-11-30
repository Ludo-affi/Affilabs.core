import json
import threading
import time
from json import JSONDecodeError
from pathlib import Path
from platform import system
from shutil import copy
from typing import Final

import numpy
import serial
import serial.tools.list_ports

from settings import ARDUINO_VID, ARDUINO_PID, CP210X_PID, CP210X_VID, BAUD_RATE, ADAFRUIT_VID, \
    PICO_VID, PICO_PID
from utils.logger import logger

if system() == "Windows":
    from os import listdrives

CH_DICT = {'a': 1, 'b': 2, 'c': 3, 'd': 4}


class ControllerBase:
    """Abstract base class for all hardware controllers."""

    def __init__(self, name):
        self._ser = None
        self.name = name

    def open(self):
        pass

    def get_info(self):
        pass

    def turn_on_channel(self, ch='a'):
        pass

    def turn_off_channels(self):
        pass

    def set_mode(self, mode='s'):
        pass

    def stop(self):
        pass

    def close(self):
        """Close serial port connection."""
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception as e:
                # Log but don't raise - we want cleanup to continue
                import logging
                logging.getLogger(__name__).error(f"Error closing serial port: {e}")
            finally:
                self._ser = None

    # EEPROM Configuration Methods
    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        return False  # Override in subclass

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM.

        Returns dict with keys:
            led_pcb_model: 'luminus_cool_white' or 'osram_warm_white'
            controller_type: 'arduino', 'pico_p4spr', 'pico_ezspr'
            fiber_diameter_um: 100 or 200
            polarizer_type: 'barrel' or 'round'
            servo_s_position: 0-180
            servo_p_position: 0-180
            led_intensity_a: 0-255
            led_intensity_b: 0-255
            led_intensity_c: 0-255
            led_intensity_d: 0-255
            integration_time_ms: int
            num_scans: int

        Returns None if no valid config or firmware doesn't support.
        """
        return None  # Override in subclass

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM.

        Args:
            config: Dict with same keys as read_config_from_eeprom()

        Returns:
            True if successful, False otherwise
        """
        return False  # Override in subclass

    @staticmethod
    def _encode_led_model(model: str) -> int:
        """Convert LED model name to byte value."""
        mapping = {
            'luminus_cool_white': 0,
            'osram_warm_white': 1
        }
        return mapping.get(model.lower(), 255)

    @staticmethod
    def _decode_led_model(value: int) -> str:
        """Convert byte value to LED model name."""
        mapping = {0: 'luminus_cool_white', 1: 'osram_warm_white'}
        return mapping.get(value, None)

    @staticmethod
    def _encode_controller_type(controller_type: str) -> int:
        """Convert controller type to byte value."""
        mapping = {
            'arduino': 0,
            'pico_p4spr': 1,
            'pico_ezspr': 2
        }
        return mapping.get(controller_type.lower(), 255)

    @staticmethod
    def _decode_controller_type(value: int) -> str:
        """Convert byte value to controller type."""
        mapping = {0: 'arduino', 1: 'pico_p4spr', 2: 'pico_ezspr'}
        return mapping.get(value, None)

    @staticmethod
    def _encode_polarizer_type(polarizer: str) -> int:
        """Convert polarizer type to byte value."""
        mapping = {'barrel': 0, 'round': 1}
        return mapping.get(polarizer.lower(), 255)

    @staticmethod
    def _decode_polarizer_type(value: int) -> str:
        """Convert byte value to polarizer type."""
        mapping = {0: 'barrel', 1: 'round'}
        return mapping.get(value, None)

    @staticmethod
    def _calculate_checksum(data: bytes) -> int:
        """Calculate XOR checksum of first 16 bytes."""
        checksum = 0
        for byte in data[0:16]:
            checksum ^= byte
        return checksum

    def __del__(self):
        """Destructor to ensure serial port is closed."""
        try:
            if hasattr(self, '_ser') and self._ser is not None:
                self.close()
        except:
            pass


class StaticController(ControllerBase):
    """Base class for static-mode controllers (P4SPR family).

    Static controllers have detector/spectroscopy capabilities but no pumps or valves.
    They operate by having liquid statically incubate on the sensor surface.

    Hardware: ArduinoController (Gen 1), PicoP4SPR (Gen 2)
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Static controllers do not support flow mode."""
        return False


class FlowController(ControllerBase):
    """Base class for flow-mode controllers (P4PRO, KNX, ezSPR families).

    Flow controllers support liquid handling via pumps and valves for continuous
    flow-based SPR measurements.

    Hardware configurations:
    - P4PRO: P4SPR detector + KNX valves + external AffiPump
    - KNX: Standalone pump/valve unit (no detector)
    - ezSPR/P4PROPlus: P4SPR detector + integrated KNX pumps/valves
    """

    @property
    def supports_flow_mode(self) -> bool:
        """Flow controllers support flow mode."""
        return True


class ArduinoController(StaticController):

    def __init__(self):
        super().__init__(name='p4spr')
        self._ser = None

    def open(self):
        """Open Arduino controller - STRICT VID/PID matching only to prevent hijacking."""
        # Only try VID/PID match - no fallback to prevent connecting to wrong devices
        for dev in serial.tools.list_ports.comports():
            if dev.pid == ARDUINO_PID and dev.vid == ARDUINO_VID:
                logger.info(f"Found Arduino with correct VID/PID - {dev.device}")
                # Try up to 3 times to connect to this device
                for attempt in range(3):
                    try:
                        logger.info(f"Trying Arduino on {dev.device} (attempt {attempt+1}/3)")
                        self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=0.5, write_timeout=0.5)

                        # Validate it's actually a P4SPR controller by testing basic commands
                        try:
                            self._ser.write(b'i')  # Turn off channels command
                            response = self._ser.read(1)
                            if response == b'i':
                                logger.info(f"Arduino P4SPR validated on {dev.device}")
                                return True
                            else:
                                logger.warning(f"Device on {dev.device} doesn't respond like P4SPR (got {response})")
                                self._ser.close()
                                self._ser = None
                                if attempt < 2:  # Don't sleep on last attempt
                                    time.sleep(0.2)
                        except Exception as val_err:
                            logger.warning(f"Failed to validate device on {dev.device}: {val_err}")
                            self._ser.close()
                            self._ser = None
                            if attempt < 2:  # Don't sleep on last attempt
                                time.sleep(0.2)

                    except Exception as e:
                        logger.error(f"Failed to open Arduino on {dev.device} (attempt {attempt+1}/3): {e}")
                        if self._ser is not None:
                            try:
                                self._ser.close()
                            except:
                                pass
                            self._ser = None
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(0.2)

        # STRICT: No fallback - only connect to devices with correct VID/PID AND validation
        logger.debug(f"No Arduino P4SPR found with VID:PID {hex(ARDUINO_VID)}:{hex(ARDUINO_PID)}")
        return False

    def turn_on_channel(self, ch='a'):
        if ch not in {'a', 'b', 'c', 'd'}:
            raise ValueError("Invalid Channel!")
        if self._ser is not None or self.open():
            self._ser.write(ch.encode())
            result = self._ser.read()
            return result == ch.encode()

    def turn_off_channels(self):
        if self._ser is not None or self.open():
            self._ser.write(b'i')
            return self._ser.read() == b'i'

    def set_intensity(self, ch='a', raw_val=1):
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError(f"Invalid Channel - {ch}")
            # error bounding: P4SPR LED intensity range is 0-255
            if raw_val > 255:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 255
            elif raw_val < 0:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 0
            if self.turn_on_channel(ch=ch):
                cmd = f"w{CH_DICT[ch]}{int(raw_val):03d}"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)  # Delay for device to process (50ms)
                    return self._ser.read() == b'w'
            else:
                logger.error(f"Failed to turn LED {ch.upper()} ON!")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
        return False

    def set_mode(self, mode='s'):
        try:
            if mode not in {'s', 'p'}:
                logger.debug(f"Invalid mode '{mode}' passed to set_mode")
                return False
            if self._ser is not None or self.open():
                # Flush any stale bytes to reduce false mismatches
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass
                self._ser.write(mode.encode())
                # Attempt up to 3 reads with short delays to capture echo
                expected = mode.encode()
                for attempt in range(3):
                    resp = self._ser.read(1)
                    if resp == expected:
                        if attempt > 0:
                            logger.debug(f"set_mode('{mode}') succeeded after retry {attempt}")
                        return True
                    if not resp:
                        # Delay slightly before next attempt
                        time.sleep(0.03)
                    else:
                        logger.debug(f"set_mode('{mode}') unexpected byte {resp} attempt {attempt}")
                # If controller stayed silent, assume success (common on older firmware) and warn once
                logger.warning(f"Controller response to set_mode('{mode}') silent after 3 attempts; assuming success")
                return True
            else:
                logger.error("Serial port unavailable in set_mode")
                return False
        except Exception as e:
            logger.error(f"set_mode('{mode}') failed: {e}")
            return False

    def servo_get(self):
        commands = {'s': 'r5', 'p': 'r6'}
        curr_pos = {'s': b'0000', 'p': b'0000'}
        if self._ser is not None or self.open():
            for pos in ['s', 'p']:
                self._ser.write(commands[pos].encode())
                curr_pos[pos] = self._ser.readline()
            logger.debug(f"Servo s, p: {curr_pos}")
        else:
            logger.error("serial communication failed - servo get")
        return curr_pos

    def servo_set(self, s=10, p=100):
        arduino_s_cmd = 5
        arduino_p_cmd = 6
        if (s < 0) or (p < 0) or (s > 180) or (p > 180):
            raise ValueError(f"Invalid polarizer position given: {s}, {p}")
        else:
            cmd_s = f"w{arduino_s_cmd}{s:03d}"
            cmd_p = f"w{arduino_p_cmd}{p:03d}"
            if self._ser is not None or self.open():
                for cmd in [cmd_s, cmd_p]:
                    self._ser.write(cmd.encode())
                    if self._ser.read() == b'w':
                        pass
                    else:
                        logger.error("servo position write failed")
                        break
            else:
                logger.error("serial communication failed - servo set")

    def flash(self):
        """Flash EEPROM to persist settings. Returns True if successful."""
        import time
        flash_cmd = 'f'
        try:
            if self._ser is not None or self.open():
                # Flush any pending data in input buffer
                try:
                    self._ser.reset_input_buffer()
                except Exception:
                    pass

                # Send flash command
                self._ser.write(flash_cmd.encode())

                # Wait for EEPROM write to complete
                time.sleep(0.15)

                # Try to read response
                response = self._ser.readline().strip()

                # If empty, try reading again
                if not response:
                    time.sleep(0.1)
                    response = self._ser.readline().strip()

                success = (response == flash_cmd.encode())
                if success:
                    logger.debug("EEPROM flash confirmed by controller")
                else:
                    logger.warning(f"EEPROM flash response mismatch: expected {flash_cmd.encode()}, got {response}")
                return success
            else:
                logger.error("Cannot flash EEPROM - serial port not open")
                return False
        except Exception as e:
            logger.error(f"EEPROM flash failed with exception: {e}")
            return False

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        import time
        try:
            if self._ser is not None or self.open():
                self._ser.reset_input_buffer()
                self._ser.write(b'cv\n')
                time.sleep(0.1)
                response = self._ser.read(1)
                return response == b'1'
            return False
        except Exception as e:
            logger.debug(f"EEPROM config check failed: {e}")
            return False

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM."""
        import time
        import struct
        try:
            if self._ser is not None or self.open():
                self._ser.reset_input_buffer()
                self._ser.write(b'rc\n')
                time.sleep(0.15)

                # Read 20 bytes
                data = self._ser.read(20)
                if len(data) != 20:
                    logger.warning(f"EEPROM read returned {len(data)} bytes, expected 20")
                    return None

                # Verify checksum
                calculated_checksum = self._calculate_checksum(data)
                stored_checksum = data[16]
                if calculated_checksum != stored_checksum:
                    logger.warning(f"EEPROM checksum mismatch: calc={calculated_checksum}, stored={stored_checksum}")
                    return None

                # Parse data
                version = data[0]
                if version != 1:
                    logger.warning(f"Unknown EEPROM config version: {version}")
                    return None

                led_model = self._decode_led_model(data[1])
                controller_type = self._decode_controller_type(data[2])
                fiber_diameter = data[3]
                polarizer_type = self._decode_polarizer_type(data[4])
                servo_s = struct.unpack('<H', data[5:7])[0]  # little-endian uint16
                servo_p = struct.unpack('<H', data[7:9])[0]
                led_a = data[9]
                led_b = data[10]
                led_c = data[11]
                led_d = data[12]
                integration_time = struct.unpack('<H', data[13:15])[0]
                num_scans = data[15]

                config = {
                    'led_pcb_model': led_model,
                    'controller_type': controller_type,
                    'fiber_diameter_um': fiber_diameter,
                    'polarizer_type': polarizer_type,
                    'servo_s_position': servo_s,
                    'servo_p_position': servo_p,
                    'led_intensity_a': led_a,
                    'led_intensity_b': led_b,
                    'led_intensity_c': led_c,
                    'led_intensity_d': led_d,
                    'integration_time_ms': integration_time,
                    'num_scans': num_scans
                }

                logger.info(f"✓ Loaded device config from EEPROM: {led_model}, {fiber_diameter}µm fiber")
                return config

        except Exception as e:
            logger.error(f"Failed to read EEPROM config: {e}")
            return None

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM."""
        import time
        import struct
        try:
            if self._ser is not None or self.open():
                # Build 20-byte config packet
                data = bytearray(20)
                data[0] = 1  # version
                data[1] = self._encode_led_model(config.get('led_pcb_model', 'luminus_cool_white'))
                data[2] = self._encode_controller_type(config.get('controller_type', 'arduino'))
                data[3] = config.get('fiber_diameter_um', 200)
                data[4] = self._encode_polarizer_type(config.get('polarizer_type', 'round'))

                # Servo positions (little-endian uint16)
                servo_s = config.get('servo_s_position', 10)
                servo_p = config.get('servo_p_position', 100)
                data[5:7] = struct.pack('<H', servo_s)
                data[7:9] = struct.pack('<H', servo_p)

                # LED intensities
                data[9] = config.get('led_intensity_a', 0)
                data[10] = config.get('led_intensity_b', 0)
                data[11] = config.get('led_intensity_c', 0)
                data[12] = config.get('led_intensity_d', 0)

                # Integration time and num scans
                integration_time = config.get('integration_time_ms', 100)
                data[13:15] = struct.pack('<H', integration_time)
                data[15] = config.get('num_scans', 3)

                # Calculate checksum
                data[16] = self._calculate_checksum(data)

                # Reserved bytes (17-19) already 0

                # Send to controller
                self._ser.reset_input_buffer()
                self._ser.write(b'wc')
                self._ser.write(bytes(data))
                self._ser.write(b'\n')

                time.sleep(0.2)  # Wait for EEPROM write

                response = self._ser.read(1)
                success = (response == b'1')

                if success:
                    logger.info("✓ Device config written to EEPROM")
                else:
                    logger.warning(f"EEPROM write failed, response: {response}")

                return success

        except Exception as e:
            logger.error(f"Failed to write EEPROM config: {e}")
            return False

    def clear_servo_positions_in_eeprom(self) -> bool:
        """Clear stored servo S/P positions in EEPROM by writing zeros.

        This does not alter other configuration fields. If EEPROM layout
        is unsupported, returns False.
        """
        try:
            # Read current EEPROM config (if available)
            current = self.read_config_from_eeprom()
            if current is None:
                # Build a minimal default packet with zeros for servos
                current = {
                    'led_pcb_model': 'osram_warm_white',
                    'controller_type': 'arduino',
                    'fiber_diameter_um': 200,
                    'polarizer_type': 'round',
                    'servo_s_position': 0,
                    'servo_p_position': 0,
                    'led_intensity_a': 0,
                    'led_intensity_b': 0,
                    'led_intensity_c': 0,
                    'led_intensity_d': 0,
                    'integration_time_ms': 100,
                    'num_scans': 3,
                }
            else:
                # Zero out only the servo positions
                current['servo_s_position'] = 0
                current['servo_p_position'] = 0

            ok = self.write_config_to_eeprom(current)
            if not ok:
                logger.warning("EEPROM write for servo clear failed")
            return ok
        except Exception as e:
            logger.error(f"Failed to clear servo positions in EEPROM: {e}")
            return False

    def __str__(self):
        return "Arduino Board"



class KineticController(FlowController):

    def __init__(self):
        super().__init__(name='KNX2')
        self._lock = threading.Lock()
        self.version = '1.0'

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == CP210X_PID and dev.vid == CP210X_VID:
                logger.info(f"Found a KNX2 board - {dev}, trying to connect...")
                try:
                    self._ser = serial.Serial(port=dev.device, baudrate=BAUD_RATE, timeout=3, write_timeout=1)
                    info = self.get_info()
                    if info is not None:
                        if info['fw ver'].startswith('KNX2'):
                            if info['fw ver'].startswith('KNX2 V1.1'):
                                self.version = '1.1'
                            return True
                        elif info['fw ver'].startswith('EZSPR'):
                            self.name = "EZSPR"
                            if info['fw ver'].startswith('EZSPR V1.1'):
                                self.version = '1.1'
                            return True
                        elif info['fw ver'].startswith('KNX1'):
                            self.name = "KNX"
                            self.version = '1.1'
                            return True
                        else:
                            logger.debug('dev is not KNX2')
                            self._ser.close()
                            return False
                    else:
                        logger.debug(f"Error during get info, returned: {info}")
                        self._ser.close()
                        return False
                except Exception as e:
                    logger.error(f"Failed to open KNX2 - {e}")
                    self._ser = None
                    return False

    def _send_command(self, cmd, parse_json=False, reply=True):
        if self._ser is not None or self.open():
            logger.debug(f"KNX2: Sending command - `{cmd}`")
            try:
                with self._lock:
                    self._ser.write(f"{cmd}\n".encode())
                    if reply:
                        buf = self._ser.readline().decode()
                        if parse_json:
                            try:
                                return json.loads(buf)
                            except JSONDecodeError:
                                logger.error(f"Failed to parse to JSON of {cmd} - {buf}")
                                return None
                        else:
                            data = buf.splitlines()
                            return data[0] if data else buf
            except Exception as e:
                logger.error(f"Failed to send command to {self.name} - {e}")
                self._ser = None

    def get_status(self):
        return self._send_command(cmd='get_status', parse_json=True)

    def get_info(self):
        return self._send_command(cmd='get_info', parse_json=True)

    def get_parameters(self):
        return self._send_command(cmd='get_parameters', parse_json=True)

    def read_wavelength(self, channel):
        data = self._send_command(cmd=f"read{channel}")
        if data:
            return numpy.asarray([int(v) for v in data.split(',')])

    def read_intensity(self):
        data = self._send_command(cmd='intensity')
        if data:
            return numpy.asarray([int(v) for v in data.split(',')])

    def stop(self):
        return self._send_command(cmd="stop")

    def turn_on_channel(self, ch='a'):
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def turn_off_channels(self):
        return self._send_command('led_off')

    # Equivalent to the Arduino function to turn on a channel LED at a given intensity
    def set_intensity(self, ch='a', raw_val=255):
        val = int((raw_val / 255) * 31) + 1
        self._send_command(f"led_intensity({CH_DICT[ch]},{val})")
        return self._send_command(f"led_on({CH_DICT[ch]})")

    def set_integration(self, int_ms):
        return self._send_command(f"set_integration({int_ms})")

    def set_mode(self, mode='s'):
        return self._send_command(f"servo_{mode}")

    def servo_set(self, s=10, p=100):
        return self._send_command(f"servo_set({s},{p})")

    def knx_stop(self, ch):
        return self._send_command(f"knx_stop_{ch}")

    def knx_start(self, rate, ch):
        return self._send_command(f"knx_start_{rate}_{ch}")

    def knx_three(self, state, ch):
        return self._send_command(f"knx_three_{state}_{ch}")

    def knx_six(self, state, ch):
        return self._send_command(f"knx_six_{state}_{ch}")

    def knx_led(self, led_state, ch):
        return self._send_command(f"knx_led_{led_state}_{ch}")

    def knx_status(self, ch):
        return self._send_command(cmd=f"knx_status_{ch}", parse_json=True)

    def stop_kinetic(self):
        self._send_command(f"knx_stop_all")

    def shutdown(self):
        self._send_command('shutdown')
        self.close()

    def __str__(self):
        return "KNX2 Board"


class PicoP4SPR(StaticController):

    def __init__(self):
        super().__init__(name='pico_p4spr')
        self._ser = None
        self.version = ''
        self._lock = threading.Lock()
        self._channels_enabled = set()  # Track which LED channels have been enabled

    def open(self):
        # Close existing connection if any
        if self._ser is not None:
            try:
                self._ser.close()
            except:
                pass
            self._ser = None

        # Reset channel tracking on new connection
        self._channels_enabled = set()

        # Try VID/PID match first (preferred method)
        logger.info(f"PicoP4SPR.open() - Looking for VID={hex(PICO_VID)} PID={hex(PICO_PID)}")
        for dev in serial.tools.list_ports.comports():
            logger.debug(f"  Found port: {dev.device} VID={hex(dev.vid) if dev.vid else 'None'} PID={hex(dev.pid) if dev.pid else 'None'}")
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    logger.info(f"MATCH! Trying PicoP4SPR on {dev.device}")
                    self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=0.05, write_timeout=1)
                    # Flush any stale data
                    self._ser.reset_input_buffer()
                    self._ser.reset_output_buffer()

                    cmd = f"id\n"
                    self._ser.write(cmd.encode())
                    import time
                    time.sleep(0.1)  # Increased delay for Pico to respond
                    reply = self._ser.readline()[0:5].decode()
                    logger.info(f"Pico P4SPR ID reply: '{reply}'")
                    if reply == 'P4SPR':
                        cmd = f"iv\n"
                        self._ser.write(cmd.encode())
                        time.sleep(0.1)
                        self.version = self._ser.readline()[0:4].decode()
                        logger.info(f"Pico P4SPR Fw version: {self.version}")
                        return True
                    else:
                        logger.warning(f"ID mismatch - expected 'P4SPR', got '{reply}'")
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(f"Error closing port after ID mismatch: {close_err}")
                        finally:
                            self._ser = None
                except Exception as e:
                    logger.error(f"Failed to open Pico on {dev.device}: {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(f"Error closing port after exception: {close_err}")
                        finally:
                            self._ser = None

        logger.warning("No PicoP4SPR found with VID/PID match")

        # FALLBACK: If VID/PID enumeration failed, try all COM ports blindly
        # This fixes Device Manager detection issues on Windows
        # BUT: Skip ports that might be Arduino boards to prevent hijacking
        logger.info("VID/PID match failed - trying fallback COM port scan (Arduino excluded)...")

        # Build exclusion list: ports with Arduino VID/PID
        excluded_ports = set()
        for dev in serial.tools.list_ports.comports():
            if dev.pid == ARDUINO_PID and dev.vid == ARDUINO_VID:
                excluded_ports.add(dev.device)
                logger.debug(f"Excluding {dev.device} (Arduino detected)")

        for dev in serial.tools.list_ports.comports():
            # Skip excluded ports
            if dev.device in excluded_ports:
                continue

            try:
                logger.info(f"Trying PicoP4SPR fallback on {dev.device}")
                self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=0.3, write_timeout=0.5)
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                cmd = f"id\n"
                self._ser.write(cmd.encode())
                import time
                time.sleep(0.05)  # Reduced from 0.15s
                reply = self._ser.readline()[0:5].decode()

                if reply == 'P4SPR':
                    logger.info(f"Found Pico P4SPR on {dev.device} (fallback method)")
                    cmd = f"iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.1)
                    self.version = self._ser.readline()[0:4].decode()
                    logger.debug(f" Pico P4SPR Fw: {self.version}")
                    return True
                else:
                    self._ser.close()
                    self._ser = None
            except Exception as e:
                logger.debug(f"   {dev.device} not a Pico P4SPR: {e}")
                if self._ser is not None:
                    try:
                        self._ser.close()
                    except:
                        pass
                    self._ser = None

        return False

    def turn_on_channel(self, ch='a'):
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError("Invalid Channel!")

            # Skip if already enabled (optimization)
            if ch in self._channels_enabled:
                logger.debug(f"LED {ch.upper()} already enabled - skipping command")
                return True

            cmd = f"l{ch}\n"
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()  # Clear any leftover data
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)  # Wait for response
                    response = self._ser.read(1)  # Read 1 byte (firmware sends '1')
                    success = response == b'1'
                    if success:
                        self._channels_enabled.add(ch)
                        logger.debug(f"✅ LED {ch.upper()} enabled via 'l{ch}' command")
                    else:
                        logger.warning(f"❌ LED {ch.upper()} enable failed - no '1' response (got: {response})")
                    return success
        except Exception as e:
            logger.error(f"Error turning on channel {ch}: {e}")
            return False

    def get_temp(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = f"it\n"
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception:
            temp = -1
            # Silently ignore temp read errors - not critical
        return temp

    def get_led_intensity(self, ch='a'):
        """Query current LED intensity from firmware (V1.1+).

        Args:
            ch: LED channel ('a', 'b', 'c', or 'd')

        Returns:
            int: Current intensity (0-255), or -1 on error
        """
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
                logger.error(f"Invalid channel: {ch}")
                return -1

            if self._ser is not None or self.open():
                with self._lock:
                    # Clear any stale data
                    self._ser.reset_input_buffer()
                    time.sleep(0.01)

                    # Send query command
                    cmd = f"i{ch}\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)

                    # Read response - firmware should respond with single line containing intensity
                    response_bytes = self._ser.readline()
                    response = response_bytes.decode('utf-8', errors='ignore').strip()

                    # Debug: log what we got
                    logger.debug(f"LED {ch} query response: '{response}'")

                    # Try to parse as integer
                    try:
                        intensity = int(response)
                        return intensity
                    except ValueError:
                        # If response is non-numeric, it's likely an echo or error
                        # Try reading one more line in case response was delayed
                        time.sleep(0.02)
                        if self._ser.in_waiting > 0:
                            response2_bytes = self._ser.readline()
                            response2 = response2_bytes.decode('utf-8', errors='ignore').strip()
                            logger.debug(f"LED {ch} second response: '{response2}'")
                            try:
                                intensity = int(response2)
                                return intensity
                            except ValueError:
                                pass

                        logger.error(f"Invalid intensity response for {ch}: {response}")
                        return -1
        except Exception as e:
            logger.debug(f"Error reading LED intensity: {e}")
            return -1

    def get_all_led_intensities(self):
        """Query all LED intensities (V1.1+).

        NOTE: Channel D query is disabled due to firmware bug where 'id'
        command conflicts with device identification command.

        Returns:
            dict: {'a': int, 'b': int, 'c': int, 'd': int} or None on error
                  Channel D will return -1 due to firmware limitation
        """
        intensities = {}
        for ch in ['a', 'b', 'c']:  # Skip 'd' due to firmware 'id' command conflict
            intensity = self.get_led_intensity(ch)
            if intensity < 0:
                return None
            intensities[ch] = intensity

        # Channel D cannot be queried due to firmware bug (id = identify device)
        intensities['d'] = -1

        return intensities

    def verify_led_state(self, expected: dict, tolerance: int = 5) -> bool:
        """Verify LEDs are in expected state (V1.1+).

        Args:
            expected: Dictionary of channel->expected_intensity
            tolerance: Acceptable deviation (default 5)

        Returns:
            bool: True if all LEDs within tolerance, False otherwise
        """
        try:
            actual = self.get_all_led_intensities()
            if actual is None:
                return False

            for ch, expected_val in expected.items():
                actual_val = actual.get(ch, -1)
                if abs(actual_val - expected_val) > tolerance:
                    logger.warning(f"LED {ch.upper()} mismatch: expected={expected_val}, actual={actual_val}")
                    return False
            return True
        except Exception as e:
            logger.error(f"Error verifying LED state: {e}")
            return False

    def emergency_shutdown(self):
        """Turn off all LEDs immediately (V1.1+).

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = "i0\n"
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.02)
                    response = self._ser.read(10)
                    success = b'1' in response
                    if success:
                        # Clear enabled channels tracking
                        self._channels_enabled.clear()
                        logger.info("Emergency shutdown executed - all LEDs off")
                    return success
        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}")
            return False

    def turn_off_channels(self):
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    cmd = f"lx\n"
                    self._ser.write(cmd.encode())
                    success = self._ser.read() == b'1'
                    if success:
                        self._channels_enabled.clear()
                        logger.debug("✅ All LED channels turned OFF via 'lx' command")
                    else:
                        logger.warning("⚠️ Turn off channels command may have failed")
                    return success
        except Exception as e:
            logger.error(f"Error turning off channels: {e}")
            return False

    def set_intensity(self, ch='a', raw_val=1):
        try:
            if ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError(f"Invalid Channel - {ch}")
            # error bounding: P4SPR LED intensity range is 0-255
            if raw_val > 255:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 255
            elif raw_val < 0:
                logger.debug(f"Invalid Intensity value - {raw_val}")
                raw_val = 0

            # CRITICAL FIX: If intensity is 0, we need to DISABLE the channel, not just set to 0
            # This prevents the channel from staying enabled with residual light
            if raw_val == 0:
                # Use the disable command (lx disables all, but we need individual disable)
                # Send command to turn off this specific channel
                cmd = f"b{ch}000\n"  # Set intensity to 0
                if self._ser is not None or self.open():
                    with self._lock:
                        try:
                            self._ser.reset_output_buffer()
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)
                        ok = self._ser.read() == b'1'
                    if ok:
                        # Remove from enabled channels set
                        self._channels_enabled.discard(ch)
                        logger.debug(f"✅ LED {ch.upper()} disabled (intensity=0)")
                    return ok
                return False

            cmd = f"b{ch}{int(raw_val):03d}\n"
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if self._ser is None and not self.open():
                        logger.error(f"pico failed to open port for LED {ch}")
                        return False

                    # Clear any pending I/O to reduce contention
                    try:
                        self._ser.reset_output_buffer()
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    # CRITICAL: Enable channel FIRST, then set intensity
                    # Firmware only applies PWM if channel is enabled (led_x_enabled=true)
                    self.turn_on_channel(ch=ch)

                    with self._lock:
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)  # device processing
                        ok = self._ser.read() == b'1'

                    if ok:
                        logger.debug(f"✅ LED {ch.upper()} intensity set to {raw_val}")
                    else:
                        logger.warning(f"⚠️ LED {ch.upper()} intensity command may have failed")

                    return ok
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.debug(f"LED write timeout (ch {ch}, attempt {attempt+1}/{max_retries}): {e}")
                        time.sleep(0.05)
                        continue
                    logger.error(f"error while setting led intensity {e}")
                    return False
            return False
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0):
        """Set all LED intensities in a single batch command (V1.1+).

        V1.1 firmware properly handles channel enable/disable in the batch command,
        making this much simpler and more reliable than sequential individual commands.

        Args:
            a: Intensity for LED A (0-255)
            b: Intensity for LED B (0-255)
            c: Intensity for LED C (0-255)
            d: Intensity for LED D (0-255)

        Returns:
            bool: True if command succeeded, False otherwise

        Example:
            # Turn on LED A at full brightness, others off
            controller.set_batch_intensities(a=255, b=0, c=0, d=0)

            # Set custom pattern
            controller.set_batch_intensities(a=128, b=64, c=192, d=255)

        Performance:
            Sequential commands: ~12ms for 4 LEDs
            Batch command: ~0.8ms for 4 LEDs
            Speedup: 15x faster

        Note:
            V1.1 firmware handles channel on/off automatically:
            - Non-zero intensity: Turns channel ON and sets intensity
            - Zero intensity: Turns channel OFF (disables PWM)
        """
        try:
            # Clamp values to valid range (0-255)
            a = max(0, min(255, int(a)))
            b = max(0, min(255, int(b)))
            c = max(0, min(255, int(c)))
            d = max(0, min(255, int(d)))

            # Format: batch:A,B,C,D\n
            cmd = f"batch:{a},{b},{c},{d}\n"

            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.05)  # Wait for firmware to process all 4 channels
                    response = self._ser.read(1)  # Read 1 byte (firmware sends '1')
                    success = response == b'1'

                if success:
                    # Update enabled channels tracking
                    self._channels_enabled.clear()
                    for ch, intensity in [('a', a), ('b', b), ('c', c), ('d', d)]:
                        if intensity > 0:
                            self._channels_enabled.add(ch)
                    logger.debug(f"Batch LED command successful: A={a}, B={b}, C={c}, D={d}")
                    return True
                else:
                    logger.warning(f"Batch LED command failed - response: {response}")
                    return False
            else:
                logger.error(f"pico serial port not valid for batch command")
                return False

        except Exception as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            return False

    def led_rank_sequence(self, test_intensity=128, settling_ms=45, dark_ms=5, timeout_s=10.0):
        """Execute firmware-side LED ranking sequence for fast calibration (V1.2+).

        This command triggers the firmware to sequence through all 4 LEDs automatically,
        with precise timing control. Python reads spectra when signaled by firmware.

        Protocol:
            1. Send: "rank:XXX,SSSS,DDD\n" where XXX=intensity, SSSS=settling_ms, DDD=dark_ms
            2. Firmware responds: "START\n"
            3. For each channel (a, b, c, d):
               - Firmware: "X:READY\n" (LED turning on)
               - Firmware: wait settling_ms
               - Firmware: "X:READ\n" (signal Python to read spectrum NOW)
               - Python: Read spectrum while LED is on
               - Firmware: Turn off LED, wait dark_ms
               - Firmware: "X:DONE\n" (measurement complete)
            4. Firmware responds: "END\n"

        Args:
            test_intensity: LED test brightness (0-255, default 128 = 50%)
            settling_ms: LED settling time in ms (default 45ms)
            dark_ms: Dark time between channels in ms (default 5ms)
            timeout_s: Maximum time to wait for sequence (default 10s)

        Yields:
            tuple: (channel, signal) where signal is 'READY', 'READ', or 'DONE'

        Returns:
            Generator that yields (channel, signal) tuples

        Example:
            ```python
            channel_data = {}

            for ch, signal in ctrl.led_rank_sequence(test_intensity=128):
                if signal == 'READ':
                    # Firmware has LED on and stable - read spectrum NOW
                    spectrum = usb.read_spectrum()
                    channel_data[ch] = analyze_spectrum(spectrum)
                elif signal == 'DONE':
                    # Measurement complete for this channel
                    logger.info(f"Channel {ch} complete")

            # All 4 channels measured, rank them
            ranked = rank_channels(channel_data)
            ```

        Performance:
            Old method (Python control): ~600ms (4 channels × 150ms each)
            New method (firmware control): ~220ms (4 channels × 55ms each)
            Speedup: 2.7x faster, more deterministic timing
        """
        try:
            # Clamp values
            test_intensity = max(0, min(255, int(test_intensity)))
            settling_ms = max(0, min(1000, int(settling_ms)))
            dark_ms = max(0, min(100, int(dark_ms)))

            # Format: rank:XXX,SSSS,DDD\n
            cmd = f"rank:{test_intensity},{settling_ms},{dark_ms}\n"

            if self._ser is None and not self.open():
                logger.error("Serial port not available for rank command")
                return

            with self._lock:
                self._ser.reset_input_buffer()
                self._ser.write(cmd.encode())
                time.sleep(0.01)

                # Wait for START signal
                start_time = time.time()
                while time.time() - start_time < timeout_s:
                    line = self._ser.readline().decode().strip()
                    if line == "START":
                        logger.debug("Rank sequence started")
                        break
                    if time.time() - start_time > 1.0:
                        logger.error(f"Timeout waiting for START, got: {line}")
                        return

                # Process channel signals
                while time.time() - start_time < timeout_s:
                    line = self._ser.readline().decode().strip()

                    if line == "END":
                        logger.debug("Rank sequence complete")
                        break

                    # Parse channel signal: "a:READY", "b:READ", etc.
                    if ':' in line:
                        ch, signal = line.split(':', 1)
                        if ch in ['a', 'b', 'c', 'd'] and signal in ['READY', 'READ', 'DONE']:
                            yield (ch, signal)
                        else:
                            logger.warning(f"Unexpected signal format: {line}")
                    elif line:
                        logger.debug(f"Firmware message: {line}")

                if time.time() - start_time >= timeout_s:
                    logger.error("Rank sequence timeout!")

        except Exception as e:
            logger.error(f"Error in LED rank sequence: {e}")
            return

    def set_mode(self, mode='s'):
        """Switch polarizer between S and P modes (PicoP4SPR).

        ========================================================================
        CRITICAL RULE: NEVER USE EEPROM FOR SERVO POSITIONS - ALWAYS DEVICE_CONFIG
        ========================================================================
        POSITIONS ARE IMMUTABLE - SINGLE SOURCE OF TRUTH IS device_config.json

        This function sends 'ss' or 'sp' command to controller firmware.
        The controller reads servo positions from its EEPROM memory.

        EEPROM positions are:
        - Written from device_config.json at application startup ONLY
        - NEVER read or modified during runtime
        - Controller firmware uses these stored positions when 'ss'/'sp' received

        This is the ONLY correct architecture:
        device_config.json → EEPROM (once at startup) → firmware uses for 'ss'/'sp'

        Legacy servo_set()/servo_get()/flash() operations are FORBIDDEN and DELETED.
        ========================================================================
        """
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    # Flush input buffer to clear any stale data
                    try:
                        self._ser.reset_input_buffer()
                    except Exception:
                        pass

                    if mode == 's':
                        cmd = f"ss\n"
                    else:
                        cmd = f"sp\n"

                    self._ser.write(cmd.encode())
                    # Increased wait time for servo movement; some firmware emits no ack
                    time.sleep(0.12)

                    # Try reading response multiple times (servo might be slow)
                    response = b''
                    attempts = 0
                    for attempts in range(3):
                        response = self._ser.readline().strip()
                        if response:
                            break
                        time.sleep(0.05)

                    # Log what we got back
                    mode_name = 'S-mode' if mode == 's' else 'P-mode'
                    # Reduce noise: treat empty responses as normal on V1.1 firmware
                    if response:
                        logger.info(f"📡 Controller response to set_mode('{mode}'): {response} (after {attempts+1} attempts)")
                    else:
                        logger.debug(f"📡 Controller response to set_mode('{mode}'): <empty> (after {attempts} attempts)")

                    # Check if response indicates success
                    success = (response == b'1') or (response == b'')

                    if success:
                        # Only log success loudly if we received explicit ack; keep empty ack as quiet success
                        if response:
                            logger.info(f"✅ Controller confirmed: {mode_name} servo moved to position from device_config")
                        else:
                            logger.debug(f"✅ {mode_name} set with empty ack (accepted on firmware V1.1)")
                    else:
                        # Non-empty, non-'1' byte: log once at warning, but continue
                        logger.warning(f"⚠️ Controller response unexpected for {mode_name}: expected b'1', got {response}")
                        logger.warning(f"⚠️ Proceeding; servo likely moved correctly (device_config→EEPROM→firmware)")
                        return True

                    return success
        except Exception as e:
            logger.error(f"❌ Exception during set_mode('{mode}'): {e}")
            return False

    # =========================================================================
    # LEGACY EEPROM FUNCTIONS DELETED - DO NOT USE FOR SERVO POSITIONS
    # =========================================================================
    # servo_get() - DELETED - reads positions from EEPROM (DANGEROUS)
    # servo_set() - DELETED - writes positions to EEPROM (DANGEROUS)
    # flash() - DELETED - writes to EEPROM (DANGEROUS)
    #
    # Servo positions come ONLY from device_config.json
    # They are loaded at startup via write_config_to_eeprom()
    # NEVER changed at runtime
    # =========================================================================

    def servo_move_calibration_only(self, s=10, p=100):
        """CALIBRATION ONLY: Move servo to test positions.

        ========================================================================
        FOR SERVO CALIBRATION WORKFLOW ONLY
        ========================================================================
        This function is ONLY for the servo calibration workflow where we scan
        different angles to FIND optimal S and P positions.

        Results are saved to device_config.json (NOT EEPROM).
        After calibration, application restart writes device_config to EEPROM.

        DO NOT use this for runtime position changes.
        DO NOT use this during normal acquisition.
        ========================================================================
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                    raise ValueError(f"Invalid polarizer position: {s}, {p}")

                # Convert degrees (0-180) to servo PWM range (0-255)
                s_servo = int(s * 255 / 180)
                p_servo = int(p * 255 / 180)

                cmd = f"sv{s_servo:03d}{p_servo:03d}\n"
                if self._ser is not None or self.open():
                    with self._lock:
                        try:
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass

                        self._ser.write(cmd.encode())
                        time.sleep(0.05)

                        response = self._ser.readline().strip()
                        if not response:
                            time.sleep(0.05)
                            response = self._ser.readline().strip()

                        return response == b'1'
                else:
                    logger.error("Cannot move servo - port not open")
                    return False
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                else:
                    logger.warning(f"Servo calibration move failed: {e}")
                    return False
        return False

    def is_config_valid_in_eeprom(self) -> bool:
        """Check if valid configuration exists in EEPROM."""
        import time
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(b'cv\n')
                    time.sleep(0.1)
                    response = self._ser.read(1)
                    return response == b'1'
            return False
        except Exception as e:
            logger.debug(f"PicoP4SPR EEPROM config check failed: {e}")
            return False

    def read_config_from_eeprom(self) -> dict:
        """Read device configuration from controller EEPROM."""
        import time
        import struct
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    self._ser.reset_input_buffer()
                    self._ser.write(b'rc\n')
                    time.sleep(0.15)

                    # Read 20 bytes
                    data = self._ser.read(20)
                    if len(data) != 20:
                        logger.warning(f"PicoP4SPR EEPROM read returned {len(data)} bytes, expected 20")
                        return None

                    # Verify checksum
                    calculated_checksum = self._calculate_checksum(data)
                    stored_checksum = data[16]
                    if calculated_checksum != stored_checksum:
                        logger.warning(f"PicoP4SPR EEPROM checksum mismatch: calc={calculated_checksum}, stored={stored_checksum}")
                        return None

                    # Parse data (same format as Arduino)
                    version = data[0]
                    if version != 1:
                        logger.warning(f"Unknown PicoP4SPR EEPROM config version: {version}")
                        return None

                    led_model = self._decode_led_model(data[1])
                    controller_type = self._decode_controller_type(data[2])
                    fiber_diameter = data[3]
                    polarizer_type = self._decode_polarizer_type(data[4])
                    servo_s = struct.unpack('<H', data[5:7])[0]
                    servo_p = struct.unpack('<H', data[7:9])[0]
                    led_a = data[9]
                    led_b = data[10]
                    led_c = data[11]
                    led_d = data[12]
                    integration_time = struct.unpack('<H', data[13:15])[0]
                    num_scans = data[15]

                    config = {
                        'led_pcb_model': led_model,
                        'controller_type': controller_type,
                        'fiber_diameter_um': fiber_diameter,
                        'polarizer_type': polarizer_type,
                        'servo_s_position': servo_s,
                        'servo_p_position': servo_p,
                        'led_intensity_a': led_a,
                        'led_intensity_b': led_b,
                        'led_intensity_c': led_c,
                        'led_intensity_d': led_d,
                        'integration_time_ms': integration_time,
                        'num_scans': num_scans
                    }

                    logger.info(f"✓ Loaded device config from PicoP4SPR EEPROM: {led_model}, {fiber_diameter}µm fiber")
                    return config

        except Exception as e:
            logger.error(f"Failed to read PicoP4SPR EEPROM config: {e}")
            return None

    def write_config_to_eeprom(self, config: dict) -> bool:
        """Write device configuration to controller EEPROM."""
        import time
        import struct
        try:
            if self._ser is not None or self.open():
                with self._lock:
                    # Build 20-byte config packet (same as Arduino)
                    data = bytearray(20)
                    data[0] = 1  # version
                    data[1] = self._encode_led_model(config.get('led_pcb_model', 'luminus_cool_white'))
                    data[2] = self._encode_controller_type(config.get('controller_type', 'pico_p4spr'))
                    data[3] = config.get('fiber_diameter_um', 200)
                    data[4] = self._encode_polarizer_type(config.get('polarizer_type', 'round'))

                    servo_s = config.get('servo_s_position', 10)
                    servo_p = config.get('servo_p_position', 100)
                    data[5:7] = struct.pack('<H', servo_s)
                    data[7:9] = struct.pack('<H', servo_p)

                    data[9] = config.get('led_intensity_a', 0)
                    data[10] = config.get('led_intensity_b', 0)
                    data[11] = config.get('led_intensity_c', 0)
                    data[12] = config.get('led_intensity_d', 0)

                    integration_time = config.get('integration_time_ms', 100)
                    data[13:15] = struct.pack('<H', integration_time)
                    data[15] = config.get('num_scans', 3)

                    data[16] = self._calculate_checksum(data)

                    # Send to controller
                    self._ser.reset_input_buffer()
                    self._ser.write(b'wc')
                    self._ser.write(bytes(data))
                    self._ser.write(b'\n')

                    time.sleep(0.2)

                    response = self._ser.read(1)
                    success = (response == b'1')

                    if success:
                        logger.info("✓ Device config written to PicoP4SPR EEPROM")
                    else:
                        logger.warning(f"PicoP4SPR EEPROM write failed, response: {response}")

                    return success

        except Exception as e:
            logger.error(f"Failed to write PicoP4SPR EEPROM config: {e}")
            return False

    def stop(self):
        self.turn_off_channels()

    def __str__(self):
        return "Pico Mini Board"


class PicoKNX2(FlowController):

    def __init__(self):
        super().__init__(name='pico_knx2')
        self._ser = None
        self.version = ''

    def open(self):
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                # Try up to 3 times to connect to this device
                for attempt in range(3):
                    try:
                        self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=1, write_timeout=3)
                        cmd = f"id\n"
                        self._ser.write(cmd.encode())
                        reply = self._ser.readline()[0:4].decode()
                        logger.debug(f"Pico KNX2 reply - {reply} (attempt {attempt+1}/3)")
                        if reply == 'KNX2':
                            cmd = f"iv\n"
                            self._ser.write(cmd.encode())
                            self.version = self._ser.readline()[0:4].decode()
                            return True
                        else:
                            try:
                                self._ser.close()
                            except Exception as close_err:
                                logger.error(f"Error closing port after ID mismatch: {close_err}")
                            finally:
                                self._ser = None
                            if attempt < 2:  # Don't sleep on last attempt
                                time.sleep(0.2)
                    except Exception as e:
                        logger.error(f"Failed to open Pico KNX2 (attempt {attempt+1}/3) - {e}")
                        if self._ser is not None:
                            try:
                                self._ser.close()
                            except Exception as close_err:
                                logger.error(f"Error closing port after exception: {close_err}")
                            finally:
                                self._ser = None
                        if attempt < 2:  # Don't sleep on last attempt
                            time.sleep(0.2)
        return False

    def get_status(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                cmd = f"it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception as e:
            logger.debug(f"temp value not readable {e}")
        return temp

    def knx_status(self, ch):
        status = {'flow': 0, 'temp': 0, '6P': 0, '3W': 0}
        try:
            cmd = f"ks{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                data = self._ser.readline().decode()[0:-2]
                data = data.split(',')
                if len(data) > 3:
                    status['flow'] = float(data[0])
                    status['temp'] = float(data[1])
                    status['3W'] = float(data[2])
                    status['6P'] = float(data[3])
            else:
                logger.error(f"failed to send cmd knx_status")
            return status
        except Exception as e:
            logger.error(f"Error during knx_status {e}")

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_stop")
            return False
        except Exception as e:
            logger.error(f"Error during knx_stop {e}")

    def knx_start(self, rate, ch):
        try:
            cmd = f"pr{ch}{rate:3d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")

    def knx_three(self, state, ch):
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return True
            else:
                logger.error(f"failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return True
            else:
                logger.error(f"failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")

    def knx_led(self, led_state, ch):
        pass  # Green indicator LED for each ch controlled in FW

    def stop_kinetic(self):
        try:
            cmds = ["ps3\n", "v330\n", "v630\n"]
            if self._ser is not None or self.open():
                er = False
                for cmd in cmds:
                    self._ser.write(cmd.encode())
                    if not (self._ser.read() == b'1'):
                        er = True
                if er:
                    logger.error(f"pico failed to confirm kinetics off")
            else:
                logger.error(f"pico failed to turn kinetics off")
        except Exception as e:
            logger.error(f"error while shutting down kinetics {e}")

    def shutdown(self):
        try:
            cmd = "do\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if not (self._ser.read() == b'1'):
                    logger.error(f"pico failed to confirm device off")
            else:
                logger.error(f"pico failed to turn device off")
        except Exception as e:
            logger.error(f"error while shutting down device {e}")

    def get_info(self):
        return self.name

    def __str__(self):
        return "Pico Carrier Board"


class PicoEZSPR(FlowController):

    UPDATABLE_VERSIONS: Final[set] = {"V1.3", "V1.4"}
    VERSIONS_WITH_PUMP_CORRECTION: Final[set] = {"V1.4", "V1.5"}
    PUMP_CORRECTION_MULTIPLIER: Final[int] = 100

    def __init__(self):
        super().__init__(name='pico_ezspr')
        self._ser = None
        self.version = ''

    def valid(self):
        return self._ser is not None and self._ser.is_open or self.open()

    def open(self):
        """Open Pico EZSPR controller with VID/PID match + fallback to blind enumeration."""
        # Try VID/PID match first (preferred method)
        for dev in serial.tools.list_ports.comports():
            if dev.pid == PICO_PID and dev.vid == PICO_VID:
                try:
                    self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=5, write_timeout=5)
                    cmd = f"id\n"
                    self._ser.write(cmd.encode())
                    reply = self._ser.readline()[0:5].decode()
                    logger.debug(f"Pico EZSPR reply - {reply}")
                    if reply == 'EZSPR':
                        cmd = f"iv\n"
                        self._ser.write(cmd.encode())
                        self.version = self._ser.readline()[0:4].decode()
                        return True
                    else:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(f"Error closing port after ID mismatch: {close_err}")
                        finally:
                            self._ser = None
                except Exception as e:
                    logger.error(f"Failed to open Pico via VID/PID - {e}")
                    if self._ser is not None:
                        try:
                            self._ser.close()
                        except Exception as close_err:
                            logger.error(f"Error closing port after exception: {close_err}")
                        finally:
                            self._ser = None

        # FALLBACK: Try all COM ports if VID/PID match failed
        logger.info("🔧 Pico EZSPR VID/PID match failed - trying all COM ports...")
        for dev in serial.tools.list_ports.comports():
            try:
                logger.debug(f"   Trying {dev.device}...")
                self._ser = serial.Serial(port=dev.device, baudrate=115200, timeout=1, write_timeout=2)
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()

                cmd = f"id\n"
                self._ser.write(cmd.encode())
                import time
                time.sleep(0.15)
                reply = self._ser.readline()[0:5].decode()

                if reply == 'EZSPR':
                    logger.info(f"✅ Found Pico EZSPR on {dev.device} (fallback method)")
                    cmd = f"iv\n"
                    self._ser.write(cmd.encode())
                    time.sleep(0.1)
                    self.version = self._ser.readline()[0:4].decode()
                    return True
                else:
                    self._ser.close()
                    self._ser = None
            except Exception as e:
                logger.debug(f"   {dev.device} not a Pico EZSPR: {e}")
                if self._ser is not None:
                    try:
                        self._ser.close()
                    except:
                        pass
                    self._ser = None

        return False

    def update_firmware(self, firmware):
        if not (self.valid() and self.version in self.UPDATABLE_VERSIONS):
            return False

        self._ser.write(b"du\n")
        self.close()

        now = time.monotonic_ns()
        timeout = now + 5_000_000_000
        while now <= timeout:
            try:
                pico_drive = next(d for d in listdrives() if (Path(d) / "INFO_UF2.TXT").exists())
                break
            except StopIteration:
                time.sleep(0)
                now = time.monotonic_ns()
        else:
            return False

        copy(firmware, pico_drive)

        now = time.monotonic_ns()
        timeout = now + 5_000_000_000
        while now <= timeout:
            if self.open():
                return True
            time.sleep(0)
            now = time.monotonic_ns()

        return False

    def get_pump_corrections(self):
        if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
            return None
        self._ser.write(b"pc\n")
        reply = self._ser.readline()
        return tuple(x / self.PUMP_CORRECTION_MULTIPLIER for x in reply[:2])

    def set_pump_corrections(self, pump_1_correction, pump_2_correction):
        if not (self.valid() and self.version in self.VERSIONS_WITH_PUMP_CORRECTION):
            return False
        corrections = pump_1_correction, pump_2_correction
        try:
            corrrection_bytes = bytes(round(x * self.PUMP_CORRECTION_MULTIPLIER) for x in corrections)
        except ValueError:
            return False
        self._ser.write(b"pf" + corrrection_bytes + b"\n")
        return True

    def turn_on_channel(self, ch='a'):
        try:
            if ch in {"a", "b", "c", "d"}:
                cmd = f"l{ch}\n"
                if self._ser is not None or self.open():
                    self._ser.write(cmd.encode())
                    return self._ser.read() == b"1"
            elif ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError("Invalid Channel!")
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def turn_off_channels(self):
        """Turn off all LED channels.

        Uses batch command to set all LEDs to 0 intensity, which is more
        reliable than the 'lx' command especially after set_batch_intensities().
        """
        try:
            if self._ser is not None or self.open():
                # Use batch command to ensure all LEDs are at 0 intensity
                # This is more reliable than 'lx' after using set_batch_intensities()
                cmd = f"batch:0,0,0,0\n"
                self._ser.write(cmd.encode())
                time.sleep(0.02)
                logger.debug(f"  All LED channels turned OFF via batch command")
                return True
        except Exception as e:
            logger.debug(f"error turning off channels {e}")
            return False

    def set_intensity(self, ch='a', raw_val=1):
        try:
            if ch in {"a", "b", "c", "d"}:
                # error bounding: P4SPR LED intensity range is 0-255
                if raw_val > 255:
                    logger.debug(f"Invalid Intensity value - {raw_val}")
                    raw_val = 255
                elif raw_val < 0:
                    logger.debug(f"Invalid Intensity value - {raw_val}")
                    raw_val = 0

                cmd = f"b{ch}{int(raw_val):03d}\n"
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if self._ser is None and not self.open():
                            logger.error(f"pico failed to open port for LED {ch}")
                            return False
                        try:
                            self._ser.reset_output_buffer()
                            self._ser.reset_input_buffer()
                        except Exception:
                            pass
                        self._ser.write(cmd.encode())
                        time.sleep(0.05)
                        reply = self._ser.read() == b"1"
                        self.turn_on_channel(ch=ch)
                        return reply
                    except Exception as e:
                        if attempt < max_retries - 1:
                            logger.debug(f"LED write timeout (EZSPR ch {ch}, attempt {attempt+1}/{max_retries}): {e}")
                            time.sleep(0.05)
                            continue
                        logger.error(f"error while setting led intensity {e}")
                        return False
                return False
            elif ch not in {'a', 'b', 'c', 'd'}:
                raise ValueError(f"Invalid Channel - {ch}")
        except Exception as e:
            logger.error(f"error while setting led intensity {e}")
            return False

    def set_batch_intensities(self, a=0, b=0, c=0, d=0):
        """Set all LED intensities in a single batch command.

        This method uses the Pico's batch command format to set all 4 LED
        intensities simultaneously, providing ~15x speedup over sequential
        individual commands.

        Args:
            a: Intensity for LED A (0-255)
            b: Intensity for LED B (0-255)
            c: Intensity for LED C (0-255)
            d: Intensity for LED D (0-255)

        Returns:
            bool: True if command succeeded, False otherwise

        Example:
            # Turn on LED A at full brightness, others off
            controller.set_batch_intensities(a=255, b=0, c=0, d=0)

            # Set custom pattern
            controller.set_batch_intensities(a=128, b=64, c=192, d=255)

        Performance:
            Sequential commands: ~12ms for 4 LEDs
            Batch command: ~0.8ms for 4 LEDs
            Speedup: 15x faster
        """
        try:
            # Clamp values to valid range (0-255)
            a = max(0, min(255, int(a)))
            b = max(0, min(255, int(b)))
            c = max(0, min(255, int(c)))
            d = max(0, min(255, int(d)))

            # CRITICAL: Enable LED channels before setting intensity (EZSPR)
            # The Pico firmware requires channels to be turned ON before they respond to intensity commands
            for ch, intensity in [('a', a), ('b', b), ('c', c), ('d', d)]:
                if intensity > 0:  # Only enable channels that will be used
                    self.turn_on_channel(ch=ch)

            # Format: batch:A,B,C,D\n
            cmd = f"batch:{a},{b},{c},{d}\n"

            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                time.sleep(0.02)  # Small delay for processing
                # Batch command executes successfully even with minimal response
                logger.debug(f"Batch LED command sent: {cmd.strip()}")
                return True
            else:
                logger.error(f"pico serial port not valid for batch command")
                return False

        except Exception as e:
            logger.error(f"error while setting batch LED intensities: {e}")
            return False

    def set_mode(self, mode='s'):
        try:
            if self._ser is not None or self.open():
                if mode == 's':
                    cmd = f"ss\n"
                else:
                    cmd = f"sp\n"
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
        except Exception as e:
            logger.debug(f"error moving polarizer {e}")
            return False

    def servo_get(self):
        cmd = f"sr\n"
        curr_pos = {'s': b'0000', 'p': b'0000'}
        max_retries = 3

        for attempt in range(max_retries):
            try:
                if self._ser is not None or self.open():
                    import time
                    self._ser.reset_input_buffer()
                    self._ser.write(cmd.encode())
                    time.sleep(0.15)  # Increased wait time for Pico to respond

                    servo_reading = self._ser.readline()
                    logger.debug(f"servo reading pico {servo_reading} (attempt {attempt + 1}/{max_retries})")

                    # If response is just "1\r\n", read again for actual positions
                    if servo_reading.strip() == b'1':
                        time.sleep(0.05)
                        servo_reading = self._ser.readline()
                        logger.debug(f"servo reading pico (second read) {servo_reading}")

                    # Parse comma-separated format: "s,p\r\n"
                    try:
                        response_str = servo_reading.decode('utf-8').strip()
                        if not response_str:
                            logger.warning(f"Empty servo response on attempt {attempt + 1} - servo may not be initialized")
                            if attempt < max_retries - 1:
                                time.sleep(0.2)
                                continue
                            return curr_pos

                        if ',' in response_str:
                            parts = response_str.split(',')
                            if len(parts) == 2:
                                # Validate that parts contain numeric values
                                try:
                                    s_val = int(parts[0])
                                    p_val = int(parts[1])
                                    curr_pos['s'] = parts[0].encode()
                                    curr_pos['p'] = parts[1].encode()
                                    logger.debug(f"Servo s, p: {curr_pos} (parsed as {s_val}, {p_val})")
                                    return curr_pos  # Success - return immediately
                                except ValueError as ve:
                                    logger.warning(f"Non-numeric servo values: {parts} - {ve}")
                                    if attempt < max_retries - 1:
                                        time.sleep(0.2)
                                        continue
                            else:
                                logger.warning(f"Invalid servo response format (expected 2 parts): {servo_reading}")
                                if attempt < max_retries - 1:
                                    time.sleep(0.2)
                                    continue
                        else:
                            logger.warning(f"Invalid servo response (no comma): {servo_reading}")
                            if attempt < max_retries - 1:
                                time.sleep(0.2)
                                continue
                    except Exception as parse_error:
                        logger.warning(f"Error parsing servo response {servo_reading}: {parse_error}")
                        if attempt < max_retries - 1:
                            time.sleep(0.2)
                            continue
                else:
                    logger.error("serial communication failed - servo get")
                    if attempt < max_retries - 1:
                        time.sleep(0.2)
                        continue
            except Exception as e:
                logger.debug(f"error getting servo pos on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.2)
                    continue

        return curr_pos

    def servo_set(self, s=10, p=100):
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if (s < 0) or (p < 0) or (s > 180) or (p > 180):
                    raise ValueError(f"Invalid polarizer position given: {s}, {p}")
                else:
                    cmd = f"sv{s:03d}{p:03d}\n"
                    if self._ser is not None or self.open():
                        self._ser.write(cmd.encode())
                        return self._ser.read() == b'1'
                    else:
                        logger.error("unable to update servo positions")
                        return False
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Servo write timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                    continue
                else:
                    logger.warning(f"Servo write failed after {max_retries} attempts: {e}")
                    return False
        return False

    def flash(self):
        try:
            flash_cmd = 'sf\n'
            if self._ser is not None or self.open():
                self._ser.write(flash_cmd.encode())
                return self._ser.read() == b'1'
            else:
                return False
        except Exception as e:
            logger.debug(f"error flashing pico {e}")
            return False

    def stop(self):
        self.turn_off_channels()

    def get_status(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                cmd = f"it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception as e:
            logger.debug(f"temp value not readable {e}")
        return temp

    def knx_status(self, ch):
        status = {'flow': 0, 'temp': 0, '6P': 0, '3W': 0}
        try:
            cmd = f"ks{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                data = self._ser.readline().decode()[0:-2]
                data = data.split(',')
                if len(data) > 3:
                    status['flow'] = float(data[0])
                    status['temp'] = float(data[1])
                    status['3W'] = float(data[2])
                    status['6P'] = float(data[3])
            else:
                logger.error(f"failed to send cmd knx_status")
            return status
        except Exception as e:
            logger.error(f"Error during knx_status {e}")

    def knx_stop(self, ch):
        try:
            cmd = f"ps{ch}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_stop")
            return False
        except Exception as e:
            logger.error(f"Error during knx_stop {e}")

    def knx_start(self, rate, ch):
        try:
            if (c := self.get_pump_corrections()) is not None:
                if str(ch) == "1":
                    rate *= c[0]
                elif str(ch) == "2":
                    rate *= c[1]
                elif str(ch) == "3" and c[0] == c[1]:
                    rate *= c[0]
                elif str(ch) == "3":
                    self._ser.write(f"pr1{round(rate * c[0]):3d}\n".encode())
                    self._ser.write(f"pr2{round(rate * c[1]):3d}\n".encode())
                    return self._ser.read(2) == b"11"
            cmd = f"pr{ch}{round(rate):3d}\n"
            if self.valid():
                self._ser.write(cmd.encode())
                if self._ser.read() == b'1':
                    return True
            else:
                logger.error(f"failed to send cmd knx_start")
            return False
        except Exception as e:
            logger.error(f"Error during knx_start {e}")

    def knx_three(self, state, ch):
        try:
            cmd = f"v3{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            else:
                logger.error(f"failed to send cmd knx_three")
            return False
        except Exception as e:
            logger.error(f"Error during knx_three {e}")

    def knx_six(self, state, ch):
        try:
            cmd = f"v6{ch}{state:1d}\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                return self._ser.read() == b"1"
            else:
                logger.error(f"failed to send cmd knx_six")
            return False
        except Exception as e:
            logger.error(f"Error during knx_six {e}")

    def knx_led(self, led_state, ch):
        pass  # Green indicator LED for each ch controlled in FW

    def stop_kinetic(self):
        try:
            cmds = ["ps3\n", "v330\n", "v630\n"]
            if self._ser is not None or self.open():
                er = False
                for cmd in cmds:
                    self._ser.write(cmd.encode())
                    if not (self._ser.read() == b'1'):
                        er = True
                if er:
                    logger.error(f"pico failed to confirm kinetics off")
            else:
                logger.error(f"pico failed to turn kinetics off")
        except Exception as e:
            logger.error(f"error while shutting down kinetics {e}")

    def shutdown(self):
        try:
            cmd = "do\n"
            if self._ser is not None or self.open():
                self._ser.write(cmd.encode())
                if not (self._ser.read() == b'1'):
                    logger.error(f"pico failed to confirm device off")
            else:
                logger.error(f"pico failed to turn device off")
        except Exception as e:
            logger.error(f"error while shutting down device {e}")

    def get_info(self):
        return self.name

    def get_temp(self):
        temp = 0
        try:
            if self._ser is not None or self.open():
                cmd = f"it\n"
                self._ser.write(cmd.encode())
                temp = self._ser.readline().decode()
                if len(temp) > 5:
                    temp = temp[0:5]
                temp = float(temp)
        except Exception as e:
            temp = -1
            logger.debug(f"temp value not readable {e}")
        return temp

    def __str__(self):
        return "Pico Carrier Board"

