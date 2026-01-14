# -*- coding: utf-8 -*-
"""
AffiPump Controller - With Step-to-uL Conversion
Zero offset = 1600 steps, 1000uL syringe capacity

Error codes based on Cavro Centris protocol:
- ASCII character indicates error type
- Uppercase = busy, lowercase = idle
"""
import serial
import time
import re
import logging
import threading
import queue
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class AffipumpController:
    # Max achievable with Centris: ~5 mL/s = 5000 µL/s = ~908,000 steps/s for 1mL syringe
    # Use high top speed and let the pump's V/v/c/L parameters control actual motion
    MAX_TOP_SPEED_PPS = 48000  # Centris can handle very high pulse rates
    _V_STEPS_PER_SEC_PER_CODE = 95
    # Cavro Centris Error Code Dictionary
    # Based on https://github.com/vstadnytskyi/syringe-pump
    ERROR_CODES = {
        b'`': {'busy': False, 'error': 'No Error'},
        b'@': {'busy': True, 'error': 'No Error'},
        b'a': {'busy': False, 'error': 'Initialization Error'},
        b'A': {'busy': True, 'error': 'Initialization Error'},
        b'b': {'busy': False, 'error': 'Invalid Command'},
        b'B': {'busy': True, 'error': 'Invalid Command'},
        b'c': {'busy': False, 'error': 'Invalid Operand'},
        b'C': {'busy': True, 'error': 'Invalid Operand'},
        b'd': {'busy': False, 'error': 'Invalid Command Sequence'},
        b'D': {'busy': True, 'error': 'Invalid Command Sequence'},
        b'g': {'busy': False, 'error': 'Device Not Initialized'},
        b'G': {'busy': True, 'error': 'Device Not Initialized'},
        b'i': {'busy': False, 'error': 'Plunger Overload'},
        b'I': {'busy': True, 'error': 'Plunger Overload'},
        b'j': {'busy': False, 'error': 'Valve Overload'},
        b'J': {'busy': True, 'error': 'Valve Overload'},
        b'k': {'busy': False, 'error': 'Plunger Move Not Allowed'},
        b'K': {'busy': True, 'error': 'Plunger Move Not Allowed'},
        b'o': {'busy': False, 'error': 'Command Buffer Overflow'},
        b'O': {'busy': True, 'error': 'Command Buffer Overflow'},
    }

    class PumpError(Exception):
        """Exception raised for pump errors"""
        def __init__(self, error_code, error_msg):
            self.error_code = error_code
            self.error_msg = error_msg
            super().__init__(f"Pump Error [{error_code}]: {error_msg}")
    def __init__(self, port='COM8', baudrate=38400, syringe_volume_ul=1000, auto_recovery=True):
        self.port = port
        self.baudrate = baudrate
        self.syringe_volume_ul = syringe_volume_ul
        self.step_offset = 1600  # Cavro Centris zero position in steps
        self.full_stroke_steps = 181490  # Maximum usable plunger travel
        self.ul_to_steps = self.full_stroke_steps / syringe_volume_ul  # 181.49 steps/uL for 1000uL syringe
        self.ser = None
        self.auto_recovery = auto_recovery  # Auto-recover from overload errors
        self.last_command = None  # Track last command for recovery

        # Thread-safe serial communication with timing enforcement
        self._serial_lock = threading.RLock()  # Reentrant lock for nested calls
        self._min_command_interval = 0.05  # 50ms minimum between commands (hardware requirement)
        self._last_command_time = 0.0  # Timestamp of last command

        # Per-pump calibration corrections (multiply by these to get actual volume)
        # Default 1.0 = no correction. Adjust if one pump consistently reads low/high
        # Example: If pump 1 reads 995µL when actual is 1000µL, set pump1_correction = 1.005
        self.pump_corrections = {
            1: 1.0,  # Pump 1 correction factor
            2: 1.0   # Pump 2 correction factor
        }

    def _format_velocity_for_v_command(self, speed_ul_s):
        """Format velocity for V{value},1R command

        Per Cavro manual: Parameter 1 means microliters
        V{µL/s},1R = velocity in µL/s
        V{steps/s}R = velocity in steps/s (no parameter)

        Old software uses V{µL/s},1R format with parameter 1

        Example: 500 µL/min = 8.333 µL/s → V8.333,1R
        """
        return speed_ul_s  # Already in µL/s, use directly with ,1 parameter

    def open(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,  # Fast timeout for status queries - pump responds in ~20-50ms
            write_timeout=2.0  # 2 second write timeout to detect serial port blockage
        )
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        print(f"Connected to {self.port} @ {self.baudrate} baud (Syringe: {self.syringe_volume_ul}uL)")
        
        # CRITICAL: Immediately stop any stuck operations from improper shutdown
        # Send terminate command to both pumps in case they were left running
        logger.info("[PUMP INIT] Sending emergency stop to clear stuck state...")
        try:
            self.send_command("/1TR")  # Terminate pump 1
            time.sleep(0.05)
            self.send_command("/2TR")  # Terminate pump 2
            time.sleep(0.05)
            logger.info("[PUMP INIT] Emergency stop commands sent")
        except Exception as e:
            logger.warning(f"[PUMP INIT] Could not send emergency stop (non-critical): {e}")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_command(self, cmd, wait_time=None, retry_on_timeout=True):
        if not self.ser or not self.ser.is_open:
            raise Exception("Port not open")
        self.last_command = cmd

        # Use lock to prevent concurrent serial access from multiple threads
        with self._serial_lock:
            try:
                # CRITICAL: Enforce minimum time between commands
                # Hardware requires 50ms minimum - prevents command collisions
                elapsed = time.time() - self._last_command_time
                if elapsed < self._min_command_interval:
                    sleep_time = self._min_command_interval - elapsed
                    time.sleep(sleep_time)
                    
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

                self.ser.write((cmd + '\r').encode())
                self._last_command_time = time.time()  # Record command time

                if wait_time is not None:
                    time.sleep(float(wait_time))

                deadline = time.time() + (self.ser.timeout or 0.1)
                buf = bytearray()
                while time.time() < deadline and len(buf) < 4096:
                    chunk = self.ser.read(256)
                    if chunk:
                        buf.extend(chunk)
                        if b'\x03' in buf:
                            break
                    else:
                        break

                return bytes(buf)

            except serial.SerialTimeoutException as e:
                if retry_on_timeout:
                    logger.warning(f"[SERIAL] Write timeout on command '{cmd}' - attempting recovery...")
                    try:
                        # Reset serial buffers
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                        time.sleep(0.5)

                        # Close and reopen serial port
                        port = self.ser.port
                        baudrate = self.ser.baudrate
                        self.ser.close()
                        time.sleep(1.0)

                        self.ser = serial.Serial(
                            port,
                            baudrate,
                            bytesize=serial.EIGHTBITS,
                            parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE,
                            timeout=0.1,
                            write_timeout=2.0
                        )
                        time.sleep(0.5)
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()

                        logger.info("[SERIAL] Serial port recovered - retrying command...")
                        # Retry command once (recursive call with retry disabled)
                        return self.send_command(cmd, wait_time, retry_on_timeout=False)

                    except Exception as recovery_error:
                        logger.error(f"[SERIAL] Recovery failed: {recovery_error}")
                        raise e  # Re-raise original timeout error
                else:
                    raise  # Don't retry if already retried once

    def parse_response(self, response):
        """Parse pump response and extract status + error information"""
        if len(response) < 6:
            return None
        match = re.search(rb'/0(.)(.+?)\x03', response)
        if match:
            status_char = match.group(1)  # ASCII character (e.g., b'`', b'i')
            data = match.group(2).decode('ascii', errors='ignore')

            # Decode error from ASCII character
            error_info = self.ERROR_CODES.get(status_char,
                                              {'busy': None, 'error': f'Unknown error code: {status_char}'})

            # Legacy bit-based status (for compatibility)
            status_byte = status_char[0]

            return {
                'status': status_byte,
                'status_char': status_char,
                'data': data,
                'initialized': bool(status_byte & 0x80),
                'busy': error_info['busy'],  # Use decoded busy state
                'idle': bool(status_byte & 0x20),
                'error': error_info['error'] != 'No Error',
                'error_msg': error_info['error'],
                'raw_response': response
            }
        return None

    def get_status(self, pump_num):
        return self.parse_response(self.send_command(f"/{pump_num}?"))

    def get_error_code(self, pump_num):
        """Query last error code (?4) - returns parsed error info"""
        response = self.send_command(f"/{pump_num}?4")
        parsed = self.parse_response(response)
        if parsed:
            return {
                'error_code': parsed['status_char'].decode('ascii', errors='ignore'),
                'error_msg': parsed['error_msg'],
                'busy': parsed['busy'],
                'data': parsed['data']
            }
        return None

    def clear_errors(self, pump_num):
        """Clear error state (W command)"""
        response = self.send_command(f"/{pump_num}WR")
        print(f"Pump {pump_num}: Errors cleared")
        return self.parse_response(response)

    @contextmanager
    def error_recovery(self, pump_num):
        """Context manager for automatic error recovery on overload"""
        try:
            yield
        except self.PumpError as e:
            if self.auto_recovery and e.error_code in ['i', 'I', 'g', 'G']:
                print(f"Auto-recovery triggered for error: {e.error_msg}")
                # Clear errors
                self.clear_errors(pump_num)
                time.sleep(0.5)
                # Re-initialize if needed
                if e.error_code in ['g', 'G', 'i', 'I']:
                    print(f"Re-initializing pump {pump_num}...")
                    self.initialize_pump(pump_num)
                    time.sleep(2)
                # Retry last command if available
                if self.last_command:
                    print(f"Retrying last command: {self.last_command}")
                    self.send_command(self.last_command)
            else:
                raise

    def get_position(self, pump_num):
        """Get position in uL - converts from steps"""
        result = self.get_status(pump_num)
        if result:
            # Check for errors
            if result['error']:
                if self.auto_recovery:
                    with self.error_recovery(pump_num):
                        raise self.PumpError(result['status_char'].decode('ascii', errors='ignore'),
                                           result['error_msg'])
            if result['data']:
                try:
                    steps = int(result['data'])
                    # Convert steps to uL: (steps - offset) / (steps_per_uL)
                    ul = (steps - self.step_offset) / self.ul_to_steps
                    # Apply per-pump calibration correction
                    ul = ul * self.pump_corrections.get(pump_num, 1.0)
                    ul = round(ul, 2)
                    if ul < 0:
                        return 0.0
                    if ul > self.syringe_volume_ul:
                        return float(self.syringe_volume_ul)
                    return ul
                except ValueError:
                    return None
        return None

    def get_current_volume(self, pump_num):
        return self.get_position(pump_num)

    def is_at_home(self, pump_num):
        """Check if pump is at home position (0 µL)"""
        pos = self.get_position(pump_num)
        if pos is None:
            return False
        return abs(pos) < 1.0  # Within 1 µL of zero

    def is_at_full(self, pump_num):
        """Check if pump is at full position (1000 µL for 1mL syringe)"""
        pos = self.get_position(pump_num)
        if pos is None:
            return False
        return abs(pos - self.syringe_volume_ul) < 1.0  # Within 1 µL of full

    def wait_until_ready(self, pump_num, timeout=30.0, poll_interval=0.1):
        """Wait for pump to become ready (not busy).
        
        Args:
            pump_num: Pump number (1 or 2)
            timeout: Maximum wait time in seconds (default: 30)
            poll_interval: Time between status checks in seconds (default: 0.1)
            
        Returns:
            tuple: (ready: bool, elapsed_time: float, error_msg: str or None)
        """
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed >= timeout:
                return (False, elapsed, f"Timeout after {timeout}s")
            
            # Get status
            try:
                result = self.get_status(pump_num)
                if result:
                    # Check for errors
                    if result['error'] and result['error_msg'] != 'No Error':
                        return (False, elapsed, f"Pump error: {result['error_msg']}")
                    
                    # Check if ready (not busy)
                    if result['busy'] is False:  # Explicitly check False (not just falsy)
                        return (True, elapsed, None)
                else:
                    # Failed to get status
                    return (False, elapsed, "Failed to get pump status")
                    
            except Exception as e:
                return (False, elapsed, f"Status check exception: {e}")
            
            # Wait before next poll
            time.sleep(poll_interval)
    
    def is_idle(self, pump_num):
        """Check if pump is idle (not busy)"""
        result = self.get_status(pump_num)
        if result:
            return not result['busy']  # True if not busy
        return False

    def wait_until_idle(self, pump_num, timeout=180, check_interval=0.5):
        """Wait until pump stops moving

        Args:
            pump_num: Pump number
            timeout: Max seconds to wait
            check_interval: Seconds between status checks

        Returns:
            True if pump became idle, False if timeout
        """
        start = time.time()
        while (time.time() - start) < timeout:
            if self.is_idle(pump_num):
                return True
            time.sleep(check_interval)
        return False

    def validate_position(self, position_ul):
        if position_ul < 0:
            raise ValueError(f"Position {position_ul}uL < 0")
        if position_ul > self.syringe_volume_ul:
            raise ValueError(f"Position {position_ul}uL > {self.syringe_volume_ul}uL")
        return True

    def initialize_pumps(self):
        """Initialize both pumps to zero position (broadcast)"""
        logger.info("[PUMP INIT] Terminating any running commands...")
        # Send TR (terminate with execute) command to each pump
        self.send_command("/1TR")
        time.sleep(0.1)
        self.send_command("/2TR")
        time.sleep(0.1)

        # Wait for both pumps to become idle after termination
        logger.info("[PUMP INIT] Waiting for pumps to stop...")
        timeout = 10.0
        start = time.time()
        while time.time() - start < timeout:
            status1 = self.get_status(1)
            status2 = self.get_status(2)

            # Log detailed status for both pumps
            if status1:
                error1 = status1.get('error', False)
                busy1 = status1.get('busy', True)
                msg1 = status1.get('error_msg', 'OK') if error1 else 'OK'
                logger.info(f"[PUMP1] busy={busy1}, error={error1}, msg={msg1}")
            else:
                busy1 = True
                logger.warning("[PUMP1] No status response")

            if status2:
                error2 = status2.get('error', False)
                busy2 = status2.get('busy', True)
                msg2 = status2.get('error_msg', 'OK') if error2 else 'OK'
                logger.info(f"[PUMP2] busy={busy2}, error={error2}, msg={msg2}")
            else:
                busy2 = True
                logger.warning("[PUMP2] No status response")

            # Check for errors during termination
            if status1 and status1.get('error', False):
                logger.error(f"[PUMP1] Error during termination: {status1.get('error_msg')}")
            if status2 and status2.get('error', False):
                logger.error(f"[PUMP2] Error during termination: {status2.get('error_msg')}")

            if not busy1 and not busy2:
                logger.info(f"[PUMP INIT] Both pumps idle after {time.time() - start:.1f}s")
                break
            time.sleep(0.5)
        else:
            logger.warning(f"[PUMP INIT] Pumps still busy after {timeout}s, proceeding anyway...")

        logger.info("[PUMP INIT] Broadcasting initialize command /AZR...")
        response = self.send_command("/AZR")
        logger.info(f"[PUMP INIT] Broadcast response: {response}")
        
        # Wait for initialization to complete (pumps physically move to P0)
        logger.info("[PUMP INIT] Waiting for initialization to complete (5s)...")
        time.sleep(5.0)
        
        # Verify both pumps are idle after initialization
        logger.info("[PUMP INIT] Verifying pumps are ready...")
        timeout = 5.0
        start = time.time()
        while time.time() - start < timeout:
            status1 = self.get_status(1)
            status2 = self.get_status(2)
            
            busy1 = status1.get('busy', True) if status1 else True
            busy2 = status2.get('busy', True) if status2 else True
            
            if not busy1 and not busy2:
                logger.info(f"[PUMP INIT] ✅ Both pumps ready after {time.time() - start + 5.0:.1f}s")
                break
            time.sleep(0.2)
        else:
            logger.warning("[PUMP INIT] ⚠️  Pumps still busy after 10s total, proceeding anyway...")
        
        return True

    def initialize_pump(self, pump_num):
        """Initialize specific pump to zero position"""
        print(f"Initializing pump {pump_num} to zero...", flush=True)

        try:
            self.terminate_move(pump_num)
            time.sleep(0.2)
        except Exception:
            pass

        # Home (move to limit switch and set as zero)
        self.send_command(f"/{pump_num}YR")
        time.sleep(8.0)

        speed_ul_s = 200
        current_pos = self.get_position(pump_num)
        self.move_to_position(pump_num, 0, speed_ul_s=speed_ul_s)

        if current_pos is None:
            time.sleep(2.0)
        else:
            time.sleep(abs(current_pos - 0) / speed_ul_s + 1.0)

        return True

    def set_speed(self, pump_num, speed_ul_s):
        return self.send_command(f"/{pump_num}V{speed_ul_s:.3f},1R")

    def set_speed_on_the_fly(self, pump_num, speed_ul_s):
        """Change pump speed while it's moving (on-the-fly).
        Uses F suffix instead of R to modify speed during motion.
        """
        return self.send_command(f"/{pump_num}V{speed_ul_s:.3f},1F")

    def aspirate(self, pump_num, volume_ul, speed_ul_s=200, wait=False):
        """Aspirate using V{µL/s},1R format per engineer notes

        Args:
            volume_ul: Volume to aspirate in µL
            speed_ul_s: Speed in µL/s
            wait: If True, wait until move completes before returning
        """
        if volume_ul > self.syringe_volume_ul:
            raise ValueError(f"Cannot aspirate {volume_ul}µL > syringe capacity {self.syringe_volume_ul}µL")

        velocity_ul_s = self._format_velocity_for_v_command(speed_ul_s)

        self.send_command(f"/{pump_num}IR")  # Inlet valve
        self.send_command(f"/{pump_num}V{velocity_ul_s:.3f},1R")
        time.sleep(0.1)
        self.send_command(f"/{pump_num}P{volume_ul:.3f},1R")  # P with µL and parameter 1

        if wait:
            expected_time = volume_ul / speed_ul_s
            self.wait_until_idle(pump_num, timeout=expected_time + 30)

        return volume_ul

    def dispense(self, pump_num, volume_ul=None, speed_ul_s=50, top_speed_pps=6000, wait=False):
        """Dispense using V{mL/min},1R format like old software

        Args:
            wait: If True, wait until move completes before returning
        """
        current_pos = self.get_position(pump_num) or 0
        if volume_ul is None:
            dispense_amount = current_pos
            target_pos_ul = 0
        else:
            dispense_amount = min(volume_ul, current_pos)
            target_pos_ul = current_pos - dispense_amount

        velocity_ul_s = self._format_velocity_for_v_command(speed_ul_s)

        self.send_command(f"/{pump_num}OR")  # Outlet valve
        self.send_command(f"/{pump_num}V{velocity_ul_s:.3f},1R")
        time.sleep(0.1)
        self.send_command(f"/{pump_num}D{dispense_amount:.3f},1R")  # D with µL and parameter 1

        if wait:
            expected_time = dispense_amount / speed_ul_s
            self.wait_until_idle(pump_num, timeout=expected_time + 30)

        return target_pos_ul

    def move_to_position(self, pump_num, position_ul, speed_ul_s=200):
        self.validate_position(position_ul)
        current_pos = self.get_position(pump_num) or 0
        delta_ul = position_ul - current_pos

        if abs(delta_ul) < 0.01:  # Already at position
            return position_ul

        travel_time = abs(delta_ul) / speed_ul_s + 1

        self.send_command(f"/{pump_num}V{speed_ul_s:.3f},1R")
        time.sleep(0.1)

        if delta_ul > 0:
            # Need to aspirate (move forward)
            self.send_command(f"/{pump_num}P{abs(delta_ul):.3f},1R")
        else:
            # Need to dispense (move backward)
            self.send_command(f"/{pump_num}D{abs(delta_ul):.3f},1R")

        return position_ul

    # ============ Synchronized Dual-Pump Operations ============

    def aspirate_both(self, volume_ul, speed_ul_s=400):
        """Aspirate relative volume from both pumps simultaneously.
        
        Args:
            volume_ul: Volume to aspirate in µL (relative movement)
            speed_ul_s: Speed in µL/s
            
        Returns:
            volume_ul: The volume aspirated
        """
        if volume_ul > self.syringe_volume_ul:
            raise ValueError(f"Cannot aspirate {volume_ul}µL > syringe capacity {self.syringe_volume_ul}µL")
        
        velocity_ul_s = self._format_velocity_for_v_command(speed_ul_s)
        
        # Switch valves to INPUT position (buffer reservoir)
        self.send_command("/1IR")
        time.sleep(0.1)
        self.send_command("/2IR")
        time.sleep(1.0)  # Give valves time to physically switch
        
        # Set velocity for broadcast
        self.send_command(f"/AV{velocity_ul_s:.3f},1R")
        time.sleep(0.1)
        
        # Use broadcast Pickup (relative aspirate) command with µL and parameter 1
        self.send_command(f"/AP{volume_ul:.3f},1R")
        
        return volume_ul

    def aspirate_both_to_position(self, target_position_ul=1000, speed_ul_s=400):
        """Aspirate both pumps to absolute position (default P1000)"""
        target_steps = int(target_position_ul * self.ul_to_steps)

        # Switch valves to INPUT position (buffer reservoir)
        # After initialization, valves default to INPUT, but after dispense they're at OUTPUT
        # So we need to switch them back to INPUT before aspirating
        self.send_command("/1IR")
        time.sleep(0.1)
        self.send_command("/2IR")
        time.sleep(1.0)  # Give valves time to physically switch
        
        # Set velocity and move to absolute position
        self.send_command(f"/AV{speed_ul_s:.3f},1R")
        time.sleep(0.1)
        self.send_command(f"/AP{target_steps}R")  # Absolute position
        return target_position_ul

    def dispense_both(self, volume_ul, speed_ul_s=50):
        """Dispense same volume from both pumps simultaneously"""
        steps = int(volume_ul * self.ul_to_steps)

        # Switch valves to OUTPUT position (chip - opposite of home position)
        logger.info(f"[DISPENSE] Setting valves to OUTPUT position (OR command) - chip")
        self.send_command("/1OR")
        time.sleep(0.1)
        self.send_command("/2OR")
        time.sleep(1.0)  # Give valves time to physically switch

        # Set velocity and dispense
        self.send_command(f"/AV{speed_ul_s:.3f},1R")
        time.sleep(0.1)
        self.send_command(f"/AD{steps}R")
        return volume_ul

    def get_both_positions(self):
        """Get positions of both pumps"""
        pos1 = self.get_position(1)
        pos2 = self.get_position(2)
        return {'pump1': pos1, 'pump2': pos2}

    def set_pump_correction(self, pump_num, correction_factor):
        """Set calibration correction factor for a specific pump.

        Args:
            pump_num: 1 or 2
            correction_factor: Multiplier to adjust reported volume
                             >1.0 if pump reads low (e.g., 1.005 adds 0.5%)
                             <1.0 if pump reads high (e.g., 0.995 subtracts 0.5%)

        Example:
            If pump 1 consistently shows 995µL when it should be 1000µL:
            set_pump_correction(1, 1.005)  # 995 * 1.005 ≈ 1000
        """
        if pump_num not in [1, 2]:
            raise ValueError("pump_num must be 1 or 2")
        if not 0.9 <= correction_factor <= 1.1:
            raise ValueError("correction_factor should be between 0.9 and 1.1")
        self.pump_corrections[pump_num] = correction_factor
        print(f"Pump {pump_num} correction factor set to {correction_factor:.4f}")

    def get_pump_corrections(self):
        """Get current correction factors for both pumps"""
        return self.pump_corrections.copy()

    # ============ Status and Monitoring ============

    def terminate_move(self, pump_num):
        return self.send_command(f"/{pump_num}TR")

    def is_busy(self, pump_num):
        result = self.get_status(pump_num)
        return bool(result and (result['status'] & 0x40))

    def wait_until_ready(self, pump_num, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            if not self.is_busy(pump_num):
                return True
            time.sleep(0.2)
        return False

    def wait_until_both_ready(self, timeout=30, auto_recover=True, min_expected_time=0.5, check_position_change=True, allow_early_termination=False):
        """Wait until BOTH pumps are ready (efficient parallel checking).

        Checks both pumps' status in each iteration for faster detection.
        Returns (pump1_ready, pump2_ready, elapsed_time, pump1_time, pump2_time).

        pump1_time and pump2_time are individual completion times (seconds).
        If a pump times out or has an unrecoverable error, its ready flag will be False.

        Args:
            timeout: Maximum wait time in seconds
            auto_recover: If True, attempt to recover unresponsive pumps
            min_expected_time: Minimum time a real movement should take (detect jammed pumps)
            check_position_change: If True, verify position actually changed (False for initialization)
            allow_early_termination: If True, don't treat quick completion as jam (pump may have been terminated)
        """
        start = time.time()
        pump1_ready = False
        pump2_ready = False
        pump1_finish_time = None
        pump2_finish_time = None
        pump1_recovered = False
        pump2_recovered = False
        pump1_failed = False  # Track permanent failures
        pump2_failed = False

        # Record starting positions to verify actual movement (only if checking position)
        pos1_start = self.get_position(1) if check_position_change else None
        pos2_start = self.get_position(2) if check_position_change else None

        # Give pumps sufficient time to START being busy (avoid race condition with broadcast commands)
        time.sleep(0.25)

        while time.time() - start < timeout:
            # Check pump 1
            if not pump1_ready and not pump1_failed:
                status1 = self.get_status(1)
                if status1:
                    # Check for error conditions FIRST (before checking busy state)
                    if status1.get('error', False):
                        error_msg = status1.get('error_msg', 'Unknown')
                        logger.error(f"[PUMP1] ERROR: {error_msg} (status: {status1.get('status_char', 'Unknown')})")

                        if auto_recover and not pump1_recovered:
                            logger.warning("[PUMP1] Attempting automatic recovery...")
                            try:
                                self.send_command("/1TR")  # Terminate
                                time.sleep(0.5)
                                self.clear_errors(1)
                                time.sleep(0.5)

                                # Verify error is cleared
                                verify_status = self.get_status(1)
                                if verify_status and verify_status.get('error', False):
                                    logger.error(f"[PUMP1] Recovery failed - error persists: {verify_status.get('error_msg')}")
                                    pump1_failed = True
                                else:
                                    pump1_recovered = True
                                    logger.info("[PUMP1] Recovery successful - error cleared")
                            except Exception as e:
                                logger.error(f"[PUMP1] Recovery exception: {e}")
                                pump1_failed = True
                        else:
                            # No auto-recovery or already tried - mark as failed
                            pump1_failed = True
                            logger.error(f"[PUMP1] FAILED - no recovery possible")

                    # Only mark ready if NO error AND not busy
                    elif not status1.get('busy', True):
                        pump1_finish_time = time.time() - start

                        # CRITICAL: Detect impossibly fast completion (jammed pump)
                        # BUT: Allow fast completion if pump was externally terminated (stop/home button)
                        if pump1_finish_time < min_expected_time and not allow_early_termination:
                            logger.error(f"[PUMP1] JAMMED - completed in {pump1_finish_time:.3f}s (< {min_expected_time}s minimum)")
                            logger.error(f"[PUMP1] Pump reports 'not busy' but completion time is physically impossible")
                            pump1_failed = True
                        elif check_position_change and not allow_early_termination:
                            # Verify actual position change (only for aspirate/dispense, NOT initialization)
                            # Skip this check if allow_early_termination=True (pump may have been stopped)
                            pos1_end = self.get_position(1)
                            if pos1_start is not None and pos1_end is not None:
                                pos_change = abs(pos1_end - pos1_start)
                                if pos_change < 10.0:  # Less than 10µL movement
                                    # Check if pump was already at/near a reasonable target position
                                    # Common targets: 0 (home), 300 (flush), 1000 (buffer/prime)
                                    # If completed very fast AND position is at a sensible target, it's not a jam
                                    is_at_common_target = (
                                        abs(pos1_start) < 10.0 or  # At home (0 µL)
                                        abs(pos1_start - 300.0) < 20.0 or  # Near flush volume
                                        abs(pos1_start - 1000.0) < 20.0  # Near buffer/prime volume
                                    )
                                    
                                    if is_at_common_target and pump1_finish_time < 1.0:
                                        logger.debug(f"[PUMP1] Already at/near target position ({pos1_start:.1f} µL) - no movement needed")
                                        pump1_ready = True
                                    else:
                                        logger.error(f"[PUMP1] JAMMED - position barely changed ({pos1_start:.1f} → {pos1_end:.1f} µL)")
                                        logger.error(f"[PUMP1] Pump may be physically stuck")
                                        pump1_failed = True
                                else:
                                    pump1_ready = True
                                    logger.debug(f"[PUMP1] Ready after {pump1_finish_time:.1f}s (moved {pos_change:.1f}µL)")
                            else:
                                # Can't verify position, rely on timing only
                                pump1_ready = True
                                logger.debug(f"[PUMP1] Ready after {pump1_finish_time:.1f}s")
                        else:
                            # Not checking position (initialization) - verify pump is at zero position
                            # The 'initialized' bit flag is unreliable on Cavro Centris firmware
                            # Instead, check if pump is at the zero offset position (1600 steps)
                            pos1_end = self.get_position(1)
                            if pos1_end is not None and abs(pos1_end) < 5.0:
                                # Pump is at zero position (within 5µL tolerance)
                                pump1_ready = True
                                logger.debug(f"[PUMP1] Initialized after {pump1_finish_time:.1f}s (at zero: {pos1_end:.1f}µL)")
                            else:
                                logger.error(f"[PUMP1] NOT AT ZERO - initialization failed (position: {pos1_end}µL)")
                                logger.error(f"[PUMP1] Expected position near 0µL after initialization")
                                pump1_failed = True
                else:
                    logger.warning("[PUMP1] No status response received")

            # Check pump 2
            if not pump2_ready and not pump2_failed:
                status2 = self.get_status(2)
                if status2:
                    # Check for error conditions FIRST (before checking busy state)
                    if status2.get('error', False):
                        error_msg = status2.get('error_msg', 'Unknown')
                        logger.error(f"[PUMP2] ERROR: {error_msg} (status: {status2.get('status_char', 'Unknown')})")

                        if auto_recover and not pump2_recovered:
                            logger.warning("[PUMP2] Attempting automatic recovery...")
                            try:
                                self.send_command("/2TR")  # Terminate
                                time.sleep(0.5)
                                self.clear_errors(2)
                                time.sleep(0.5)

                                # Verify error is cleared
                                verify_status = self.get_status(2)
                                if verify_status and verify_status.get('error', False):
                                    logger.error(f"[PUMP2] Recovery failed - error persists: {verify_status.get('error_msg')}")
                                    pump2_failed = True
                                else:
                                    pump2_recovered = True
                                    logger.info("[PUMP2] Recovery successful - error cleared")
                            except Exception as e:
                                logger.error(f"[PUMP2] Recovery exception: {e}")
                                pump2_failed = True
                        else:
                            # No auto-recovery or already tried - mark as failed
                            pump2_failed = True
                            logger.error(f"[PUMP2] FAILED - no recovery possible")

                    # Only mark ready if NO error AND not busy
                    elif not status2.get('busy', True):
                        pump2_finish_time = time.time() - start

                        # CRITICAL: Detect impossibly fast completion (jammed pump)
                        # BUT: Allow fast completion if pump was externally terminated (stop/home button)
                        if pump2_finish_time < min_expected_time and not allow_early_termination:
                            logger.error(f"[PUMP2] JAMMED - completed in {pump2_finish_time:.3f}s (< {min_expected_time}s minimum)")
                            logger.error(f"[PUMP2] Pump reports 'not busy' but completion time is physically impossible")
                            pump2_failed = True
                        elif check_position_change and not allow_early_termination:
                            # Verify actual position change (only for aspirate/dispense, NOT initialization)
                            # Skip this check if allow_early_termination=True (pump may have been stopped)
                            pos2_end = self.get_position(2)
                            if pos2_start is not None and pos2_end is not None:
                                pos_change = abs(pos2_end - pos2_start)
                                if pos_change < 10.0:  # Less than 10µL movement
                                    # Check if pump was already at/near a reasonable target position
                                    # Common targets: 0 (home), 300 (flush), 1000 (buffer/prime)
                                    # If completed very fast AND position is at a sensible target, it's not a jam
                                    is_at_common_target = (
                                        abs(pos2_start) < 10.0 or  # At home (0 µL)
                                        abs(pos2_start - 300.0) < 20.0 or  # Near flush volume
                                        abs(pos2_start - 1000.0) < 20.0  # Near buffer/prime volume
                                    )
                                    
                                    if is_at_common_target and pump2_finish_time < 1.0:
                                        logger.debug(f"[PUMP2] Already at/near target position ({pos2_start:.1f} µL) - no movement needed")
                                        pump2_ready = True
                                    else:
                                        logger.error(f"[PUMP2] JAMMED - position barely changed ({pos2_start:.1f} → {pos2_end:.1f} µL)")
                                        logger.error(f"[PUMP2] Pump may be physically stuck")
                                        pump2_failed = True
                                else:
                                    pump2_ready = True
                                    logger.debug(f"[PUMP2] Ready after {pump2_finish_time:.1f}s (moved {pos_change:.1f}µL)")
                            else:
                                # Can't verify position, rely on timing only
                                pump2_ready = True
                                logger.debug(f"[PUMP2] Ready after {pump2_finish_time:.1f}s")
                        else:
                            # Not checking position (initialization) - verify pump is at zero position
                            # The 'initialized' bit flag is unreliable on Cavro Centris firmware
                            # Instead, check if pump is at the zero offset position (1600 steps)
                            pos2_end = self.get_position(2)
                            if pos2_end is not None and abs(pos2_end) < 5.0:
                                # Pump is at zero position (within 5µL tolerance)
                                pump2_ready = True
                                logger.debug(f"[PUMP2] Initialized after {pump2_finish_time:.1f}s (at zero: {pos2_end:.1f}µL)")
                            else:
                                logger.error(f"[PUMP2] NOT AT ZERO - initialization failed (position: {pos2_end}µL)")
                                logger.error(f"[PUMP2] Expected position near 0µL after initialization")
                                pump2_failed = True
                else:
                    logger.warning("[PUMP2] No status response received")

            # Return success if both are ready
            if pump1_ready and pump2_ready:
                logger.info(f"[OK] Both pumps ready after {time.time() - start:.1f}s")
                return (True, True, time.time() - start, pump1_finish_time, pump2_finish_time)

            # Return failure if either pump permanently failed
            if pump1_failed or pump2_failed:
                logger.error(f"[FAIL] Pump failure detected (P1={pump1_failed}, P2={pump2_failed})")
                return (not pump1_failed, not pump2_failed, time.time() - start, pump1_finish_time, pump2_finish_time)

            time.sleep(0.5)  # Poll at 2Hz for faster error detection

        # Timeout - return current state
        logger.warning(f"[TIMEOUT] Pumps not ready after {timeout}s (P1={pump1_ready}, P2={pump2_ready})")
        return (pump1_ready, pump2_ready, time.time() - start, pump1_finish_time, pump2_finish_time)

    def set_valve_input(self, pump_num):
        return self.send_command(f"/{pump_num}IR")

    def set_valve_output(self, pump_num):
        return self.send_command(f"/{pump_num}OR")

    def set_valve_bypass(self, pump_num):
        return self.send_command(f"/{pump_num}BR")

    def get_valve_position(self, pump_num):
        """Query current valve position - ?6"""
        response = self.send_command(f"/{pump_num}?6")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                # Returns valve port number (I, O, B, or port number)
                return parsed['data']
            except ValueError:
                return None
        return None

    # ============ Configuration Queries ============

    def get_syringe_volume(self, pump_num):
        """Get configured syringe volume - Query ?17"""
        response = self.send_command(f"/{pump_num}?17")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None

    def get_start_speed(self, pump_num):
        """Get start speed - Query ?1"""
        response = self.send_command(f"/{pump_num}?1")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None

    def get_top_speed(self, pump_num):
        """Get top speed - Query ?2"""
        response = self.send_command(f"/{pump_num}?2")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return float(parsed['data'])
            except ValueError:
                return None
        return None

    def get_cutoff_speed(self, pump_num):
        """Get cutoff speed - Query ?3"""
        response = self.send_command(f"/{pump_num}?3")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None

    def get_backlash(self, pump_num):
        """Get backlash compensation setting - Query ?26"""
        response = self.send_command(f"/{pump_num}?26")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None

    def get_firmware_version(self, pump_num):
        """Get firmware version - Query ?23"""
        response = self.send_command(f"/{pump_num}?23")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            return parsed['data']
        return None

    def get_plunger_position_raw(self, pump_num):
        """Get raw plunger position in steps (not µL)"""
        response = self.send_command(f"/{pump_num}?")
        parsed = self.parse_response(response)
        if parsed and parsed['data']:
            try:
                return int(parsed['data'])
            except ValueError:
                return None
        return None

    # ============ Speed Control ============

    def set_start_speed(self, pump_num, pulses_per_sec):
        """Set start speed (v command) - Range: 50-1000 pulses/sec"""
        if not 50 <= pulses_per_sec <= 1000:
            raise ValueError("Start speed must be 50-1000 pulses/sec")
        return self.send_command(f"/{pump_num}v{pulses_per_sec}R")

    def set_top_speed(self, pump_num, pulses_per_sec):
        """Set top speed (V command) - Range: 5-48000 pulses/sec (Centris)"""
        if not 5 <= pulses_per_sec <= 48000:
            raise ValueError("Top speed must be 5-48000 pulses/sec")
        return self.send_command(f"/{pump_num}V{int(pulses_per_sec)}R")

    def set_cutoff_speed(self, pump_num, pulses_per_sec):
        """Set cutoff speed (c command) - Range: 50-2700 pulses/sec"""
        if not 50 <= pulses_per_sec <= 2700:
            raise ValueError("Cutoff speed must be 50-2700 pulses/sec")
        return self.send_command(f"/{pump_num}c{pulses_per_sec}R")

    def set_slope(self, pump_num, slope_code):
        """Set acceleration slope (L command) - Range: 1-20"""
        if not 1 <= slope_code <= 20:
            raise ValueError("Slope code must be 1-20")
        return self.send_command(f"/{pump_num}L{slope_code}R")

    def set_backlash(self, pump_num, steps):
        """Set backlash compensation (K command)"""
        return self.send_command(f"/{pump_num}K{steps}R")

    # ============ Pressure Monitoring ============

    def get_pressure(self, pump_num):
        """Get pressure reading (if sensor available) - Query ?24
        Returns 0 if no sensor installed"""
        response = self.send_command(f"/{pump_num}?24")
        match = re.search(r'`([^`\x03]+)', response.decode('ascii', errors='ignore'))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def get_pressure_limit(self, pump_num):
        """Get pressure limit setting - Query ?25"""
        response = self.send_command(f"/{pump_num}?25")
        match = re.search(r'`([^`\x03]+)', response.decode('ascii', errors='ignore'))
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def get_back_pressure(self, pump_num):
        """Alias for get_pressure"""
        return self.get_pressure(pump_num)

    def dispense_with_pressure_monitoring(self, pump_num, volume_ul,
                                         step_size_ul=20, speed_ul_s=50,
                                         max_pressure=None, callback=None):
        """
        Dispense in small increments with pressure monitoring between steps.
        Workaround for BUSY status preventing queries during movement.

        Args:
            pump_num: Pump number (1 or 2)
            volume_ul: Total volume to dispense
            step_size_ul: Volume per step (smaller = more measurements)
            speed_ul_s: Dispense speed
            max_pressure: Stop if pressure exceeds this (None = no limit)
            callback: Optional function(step, volume, pressure, position)

        Returns:
            dict with pressure_history, volume_dispensed, stopped_early, max_pressure_reached
        """
        pressure_history = []
        volume_dispensed = 0
        stopped_early = False

        self.send_command(f"/{pump_num}OR")
        self.send_command(f"/{pump_num}V{speed_ul_s:.3f},1R")
        time.sleep(0.1)

        num_increments = int(volume_ul / step_size_ul)
        remaining = volume_ul % step_size_ul

        for i in range(num_increments):
            self.send_command(f"/{pump_num}D{step_size_ul:.3f},1R",
                            wait_time=(step_size_ul / speed_ul_s) + 0.5)
            time.sleep(0.3)

            pressure = self.get_pressure(pump_num)
            position = self.get_position(pump_num)
            volume_dispensed += step_size_ul

            reading = {
                'step': i + 1,
                'volume_dispensed': volume_dispensed,
                'pressure': pressure,
                'position': position
            }
            pressure_history.append(reading)

            if callback:
                callback(i + 1, volume_dispensed, pressure, position)

            if max_pressure and pressure and pressure > max_pressure:
                stopped_early = True
                break

        if remaining > 0 and not stopped_early:
            self.send_command(f"/{pump_num}D{remaining:.3f},1R",
                            wait_time=(remaining / speed_ul_s) + 0.5)
            time.sleep(0.3)

            pressure = self.get_pressure(pump_num)
            position = self.get_position(pump_num)
            volume_dispensed += remaining

            pressure_history.append({
                'step': num_increments + 1,
                'volume_dispensed': volume_dispensed,
                'pressure': pressure,
                'position': position
            })

            if callback:
                callback(num_increments + 1, volume_dispensed, pressure, position)

        pressures = [r['pressure'] for r in pressure_history if r['pressure'] is not None]
        max_pressure_reached = max(pressures) if pressures else None

        return {
            'pressure_history': pressure_history,
            'volume_dispensed': volume_dispensed,
            'stopped_early': stopped_early,
            'max_pressure_reached': max_pressure_reached
        }

    # ============ Advanced Operations ============

    def get_remaining_volume(self, pump_num):
        """Get remaining volume that can be aspirated"""
        current_pos = self.get_position(pump_num) or 0
        return self.syringe_volume_ul - current_pos

    def check_volume_available(self, pump_num, volume_ul):
        """Check if enough volume available to dispense"""
        current_pos = self.get_position(pump_num) or 0
        return current_pos >= volume_ul

    def prime_lines(self, pump_num, cycles=3, volume_ul=None, speed_ul_s=200):
        """Prime by filling and emptying repeatedly

        Args:
            pump_num: Pump number
            cycles: Number of fill/empty cycles
            volume_ul: Volume per cycle (None = full syringe)
            speed_ul_s: Speed for operations
        """
        if volume_ul is None:
            volume_ul = self.syringe_volume_ul

        print(f"Priming pump {pump_num}: {cycles} cycles of {volume_ul}µL")

        for i in range(cycles):
            print(f"  Cycle {i+1}/{cycles}: Aspirating...")
            self.set_valve_input(pump_num)
            time.sleep(0.3)
            self.aspirate(pump_num, volume_ul, speed_ul_s)
            time.sleep(0.5)

            print(f"  Cycle {i+1}/{cycles}: Dispensing...")
            self.set_valve_output(pump_num)
            time.sleep(0.3)
            self.dispense(pump_num, volume_ul, speed_ul_s)
            time.sleep(0.5)

        print(f"Priming complete")

    def flush(self, pump_num, cycles=5, speed_ul_s=500):
        """Flush syringe with fast fill/empty cycles"""
        print(f"Flushing pump {pump_num}: {cycles} cycles")
        self.prime_lines(pump_num, cycles=cycles, speed_ul_s=speed_ul_s)

    def extract_to_waste(self, pump_num, source_volume_ul, waste_port='O',
                        input_port='I', speed_ul_s=200):
        """Extract from input port and dispense to waste

        Common pattern: aspirate from source, switch valve, dispense to waste.
        Useful for extracting without returning to same port.

        Args:
            pump_num: Pump number
            source_volume_ul: Volume to extract
            waste_port: Valve position for waste ('O' = output, 'B' = bypass)
            input_port: Valve position for source ('I' = input)
            speed_ul_s: Speed for operations
        """
        # Set to input port and aspirate
        if input_port == 'I':
            self.set_valve_input(pump_num)
        elif input_port == 'O':
            self.set_valve_output(pump_num)
        elif input_port == 'B':
            self.set_valve_bypass(pump_num)
        time.sleep(0.3)

        self.aspirate(pump_num, source_volume_ul, speed_ul_s)
        time.sleep(0.5)

        # Switch to waste port and dispense
        if waste_port == 'O':
            self.set_valve_output(pump_num)
        elif waste_port == 'B':
            self.set_valve_bypass(pump_num)
        elif waste_port == 'I':
            self.set_valve_input(pump_num)
        time.sleep(0.3)

        self.dispense(pump_num, source_volume_ul, speed_ul_s)
        time.sleep(0.5)

        # Return to input port
        if input_port == 'I':
            self.set_valve_input(pump_num)
        elif input_port == 'O':
            self.set_valve_output(pump_num)
        elif input_port == 'B':
            self.set_valve_bypass(pump_num)

    def transfer(self, from_pump, to_pump, volume_ul, speed_ul_s=100):
        """Transfer volume from one pump to another

        Args:
            from_pump: Source pump number (1 or 2)
            to_pump: Destination pump number (1 or 2)
            volume_ul: Volume to transfer
            speed_ul_s: Speed for operations

        Note: Assumes pumps are connected via tubing
        """
        # Check source has volume
        if not self.check_volume_available(from_pump, volume_ul):
            raise ValueError(f"Pump {from_pump} doesn't have {volume_ul}µL available")

        # Check destination has space
        remaining = self.get_remaining_volume(to_pump)
        if remaining < volume_ul:
            raise ValueError(f"Pump {to_pump} only has {remaining}µL space remaining")

        print(f"Transferring {volume_ul}µL from pump {from_pump} to pump {to_pump}")

        # Set valves
        self.set_valve_output(from_pump)
        self.set_valve_input(to_pump)
        time.sleep(0.3)

        # Dispense from source while aspirating to destination
        # Use synchronized commands for simultaneous operation

        # Set speeds
        self.send_command(f"/{from_pump}V{speed_ul_s:.3f},1R")
        self.send_command(f"/{to_pump}V{speed_ul_s:.3f},1R")
        time.sleep(0.1)

        # Dispense from source
        self.send_command(f"/{from_pump}D{volume_ul:.3f},1R")
        # Aspirate to destination
        self.send_command(f"/{to_pump}P{volume_ul:.3f},1R")

        print(f"Transfer complete")

    def dilute(self, pump_num, diluent_volume_ul, sample_volume_ul,
              diluent_port='I', sample_port='O', output_port='B', speed_ul_s=100):
        """Mix diluent and sample at specified ratio

        Args:
            pump_num: Pump to use for mixing
            diluent_volume_ul: Volume of diluent
            sample_volume_ul: Volume of sample
            diluent_port: Valve position for diluent
            sample_port: Valve position for sample
            output_port: Valve position for mixed output
            speed_ul_s: Speed for operations
        """
        total_volume = diluent_volume_ul + sample_volume_ul
        if total_volume > self.syringe_volume_ul:
            raise ValueError(f"Total volume {total_volume}µL exceeds syringe capacity")

        ratio = diluent_volume_ul / sample_volume_ul
        print(f"Diluting: {diluent_volume_ul}µL diluent + {sample_volume_ul}µL sample (ratio {ratio:.2f}:1)")

        # Aspirate diluent
        if diluent_port == 'I':
            self.set_valve_input(pump_num)
        elif diluent_port == 'O':
            self.set_valve_output(pump_num)
        elif diluent_port == 'B':
            self.set_valve_bypass(pump_num)
        time.sleep(0.3)
        self.aspirate(pump_num, diluent_volume_ul, speed_ul_s)
        time.sleep(0.5)

        # Aspirate sample
        if sample_port == 'I':
            self.set_valve_input(pump_num)
        elif sample_port == 'O':
            self.set_valve_output(pump_num)
        elif sample_port == 'B':
            self.set_valve_bypass(pump_num)
        time.sleep(0.3)
        self.aspirate(pump_num, sample_volume_ul, speed_ul_s)
        time.sleep(0.5)

        # Dispense mixed solution
        if output_port == 'I':
            self.set_valve_input(pump_num)
        elif output_port == 'O':
            self.set_valve_output(pump_num)
        elif output_port == 'B':
            self.set_valve_bypass(pump_num)
        time.sleep(0.3)
        self.dispense(pump_num, total_volume, speed_ul_s)

        print(f"Dilution complete")

    def abort(self, pump_num):
        """Emergency stop - terminates current command immediately (T command)
        Alias for terminate_move for clarity
        """
        return self.terminate_move(pump_num)

    def run_buffer(self, pump_num, duration_minutes, flow_rate_ul_min,
                   reservoir_port='I', output_port='O',
                   refill_speed_ul_s=500, callback=None, stop_flag=None):
        """Continuous buffer delivery with automatic refill

        Delivers buffer at constant flow rate for specified duration.
        Automatically refills from reservoir when syringe empties.

        Args:
            pump_num: Pump number (1 or 2)
            duration_minutes: Total run time in minutes
            flow_rate_ul_min: Flow rate in µL/min
            reservoir_port: Valve position for buffer reservoir (default 'I')
            output_port: Valve position for delivery (default 'O')
            refill_speed_ul_s: Speed for refill operations (default 500 µL/s)
            callback: Optional function(cycle, volume_delivered, elapsed_time, status)
            stop_flag: Optional threading.Event() or object with is_set() to stop early

        Returns:
            dict with total_volume_delivered, cycles_completed, elapsed_time, stopped_early

        Example:
            # Run buffer at 50µL/min for 30 minutes
            pump.run_buffer(1, duration_minutes=30, flow_rate_ul_min=50)

            # With progress callback
            def progress(cycle, volume, elapsed, status):
                print(f"Cycle {cycle}: {volume}µL delivered, {elapsed:.1f}min elapsed - {status}")

            pump.run_buffer(1, 30, 50, callback=progress)
        """
        # Note: do not rely on status "busy" gating here; some devices report busy on query.

        # Convert flow rate to µL/s
        flow_rate_ul_s = flow_rate_ul_min / 60.0

        # Calculate total volume needed
        total_volume_needed = flow_rate_ul_min * duration_minutes

        # Always refill to maximum capacity
        refill_volume = self.syringe_volume_ul  # Full 1000µL per cycle

        # Estimate number of cycles needed
        estimated_cycles = int(total_volume_needed / refill_volume) + 1

        print(f"="*60)
        print(f"RUN-BUFFER OPERATION")
        print(f"="*60)
        print(f"Duration: {duration_minutes} minutes")
        print(f"Flow Rate: {flow_rate_ul_min} µL/min ({flow_rate_ul_s:.2f} µL/s)")
        print(f"Total Volume: {total_volume_needed} µL")
        print(f"Estimated Cycles: {estimated_cycles}")
        print(f"Refill Volume: {refill_volume} µL")
        print(f"="*60)

        # Initialize tracking
        cycle_count = 0
        stopped_early = False

        # Track total runtime separately; start the control timer after initial refill
        overall_start_time = time.time()
        total_delivered = 0

        # Initial refill
        print(f"\nInitial refill from reservoir...")
        self._set_valve_by_name(pump_num, reservoir_port)
        time.sleep(0.3)
        self.aspirate(pump_num, refill_volume, refill_speed_ul_s)
        # Wait for refill to complete
        refill_time = refill_volume / refill_speed_ul_s
        time.sleep(refill_time + 0.5)

        # Start timing AFTER initial refill so requested duration maps to dispense time
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        # Main delivery loop - run until time expires
        while True:
            # Check stop flag
            if stop_flag and hasattr(stop_flag, 'is_set') and stop_flag.is_set():
                print("\nStop flag detected - terminating buffer run")
                stopped_early = True
                break

            cycle_count += 1
            elapsed_minutes = (time.time() - start_time) / 60.0
            time_remaining_seconds = end_time - time.time()

            # If time is up, stop
            if time_remaining_seconds <= 0:
                print(f"\nTime limit reached ({duration_minutes} minutes)")
                break

            # Dispense only what we still need (and only what we still have time for)
            remaining_volume_needed = total_volume_needed - total_delivered
            if remaining_volume_needed <= 0:
                break

            # Limit by time remaining so we don't overshoot the requested duration
            max_volume_by_time = max(0.0, time_remaining_seconds * flow_rate_ul_s)
            dispense_volume = min(refill_volume, remaining_volume_needed, max_volume_by_time)
            if dispense_volume <= 0:
                break

            # Calculate actual dispense time at target flow rate
            dispense_time = dispense_volume / flow_rate_ul_s

            print(f"\nCycle {cycle_count}:")
            print(f"  Time: {elapsed_minutes:.1f}/{duration_minutes} min ({time_remaining_seconds:.1f}s remaining)")
            print(f"  Dispensing: {dispense_volume:.1f} µL at {flow_rate_ul_min} µL/min")
            print(f"  Dispense duration: {dispense_time:.1f} seconds")

            # Switch to output and dispense
            self._set_valve_by_name(pump_num, output_port)
            time.sleep(0.3)

            # Dispense at target flow rate using µL/s and µL units
            self.send_command(f"/{pump_num}V{flow_rate_ul_s:.3f},1R")
            time.sleep(0.1)  # Stability delay

            # Send dispense command - don't wait for entire duration in send_command
            self.send_command(f"/{pump_num}D{dispense_volume:.3f},1R")

            # Now wait for the dispense to complete, checking status periodically
            dispense_start = time.time()
            while (time.time() - dispense_start) < dispense_time:
                time.sleep(min(2.0, dispense_time * 0.1))  # Check every 2s or 10% of dispense time
                # Could add status check here if needed
                if stop_flag and hasattr(stop_flag, 'is_set') and stop_flag.is_set():
                    self.terminate_move(pump_num)
                    stopped_early = True
                    break

            if stopped_early:
                break

            total_delivered += dispense_volume

            # Callback after dispensing
            if callback:
                callback(cycle_count, total_delivered, elapsed_minutes, "dispensing")

            # Check if we've used up all the time
            time_remaining_seconds = end_time - time.time()
            if time_remaining_seconds <= 0:
                print(f"\nTime limit reached after dispensing")
                break

            # Check if we need to refill for another cycle
            # Calculate time needed for refill + minimum dispense
            refill_time_estimate = (refill_volume / refill_speed_ul_s) + 2  # +2s for valve switches
            min_dispense_time = 5  # Minimum 5 seconds of dispense time worth doing

            if time_remaining_seconds < (refill_time_estimate + min_dispense_time):
                print(f"\nInsufficient time for another full cycle ({time_remaining_seconds:.1f}s remaining)")
                break

            # Refill for next cycle
            print(f"  Refilling {refill_volume}µL from reservoir...")
            self._set_valve_by_name(pump_num, reservoir_port)
            time.sleep(0.3)

            self.aspirate(pump_num, refill_volume, refill_speed_ul_s)
            time.sleep(0.5)

            if callback:
                callback(cycle_count, total_delivered, elapsed_minutes, "refilled")

        # Final stats
        elapsed_total = (time.time() - start_time) / 60.0

        print(f"\n" + "="*60)
        print(f"RUN-BUFFER COMPLETE")
        print(f"="*60)
        print(f"Cycles Completed: {cycle_count}")
        print(f"Volume Delivered: {total_delivered:.1f} µL")
        print(f"Total Elapsed Time: {elapsed_total:.1f} minutes")
        print(f"Dispense Flow Rate: {flow_rate_ul_min:.1f} µL/min (as requested)")
        print(f"Stopped Early: {stopped_early}")
        print(f"="*60)

        return {
            'total_volume_delivered': total_delivered,
            'cycles_completed': cycle_count,
            'elapsed_time_minutes': elapsed_total,
            'stopped_early': stopped_early,
            'average_flow_rate': total_delivered / elapsed_total if elapsed_total > 0 else 0
        }

    def _set_valve_by_name(self, pump_num, port_name):
        """Helper to set valve by name"""
        if port_name.upper() == 'I':
            self.set_valve_input(pump_num)
        elif port_name.upper() == 'O':
            self.set_valve_output(pump_num)
        elif port_name.upper() == 'B':
            self.set_valve_bypass(pump_num)
        else:
            raise ValueError(f"Invalid port name: {port_name}")

    def get_all_diagnostics(self, pump_num):
        """Comprehensive diagnostic information

        Returns:
            dict with all available pump information
        """
        print(f"Running diagnostics on pump {pump_num}...")

        diagnostics = {
            'pump_number': pump_num,
            'timestamp': time.time(),
        }

        # Status
        status = self.get_status(pump_num)
        if status:
            diagnostics['status'] = status

        # Position
        diagnostics['position_ul'] = self.get_position(pump_num)
        diagnostics['position_steps'] = self.get_plunger_position_raw(pump_num)
        diagnostics['remaining_volume_ul'] = self.get_remaining_volume(pump_num)

        # Valve
        diagnostics['valve_position'] = self.get_valve_position(pump_num)

        # Configuration
        diagnostics['syringe_volume_ul'] = self.get_syringe_volume(pump_num)
        diagnostics['backlash'] = self.get_backlash(pump_num)
        diagnostics['firmware_version'] = self.get_firmware_version(pump_num)

        # Speeds
        diagnostics['start_speed'] = self.get_start_speed(pump_num)
        diagnostics['top_speed'] = self.get_top_speed(pump_num)
        diagnostics['cutoff_speed'] = self.get_cutoff_speed(pump_num)

        # Pressure (if available)
        diagnostics['pressure'] = self.get_pressure(pump_num)
        diagnostics['pressure_limit'] = self.get_pressure_limit(pump_num)

        # Error status
        diagnostics['error_info'] = self.get_error_code(pump_num)

        return diagnostics

    def print_diagnostics(self, pump_num):
        """Print formatted diagnostic report"""
        diag = self.get_all_diagnostics(pump_num)

        print("\n" + "="*60)
        print(f"PUMP {pump_num} DIAGNOSTICS")
        print("="*60)

        print(f"\nStatus:")
        if diag.get('status'):
            print(f"  Busy: {diag['status'].get('busy')}")
            print(f"  Error: {diag['status'].get('error_msg')}")
            print(f"  Initialized: {diag['status'].get('initialized')}")

        print(f"\nPosition:")
        print(f"  Current: {diag.get('position_ul')} µL ({diag.get('position_steps')} steps)")
        print(f"  Remaining: {diag.get('remaining_volume_ul')} µL")
        print(f"  Valve: {diag.get('valve_position')}")

        print(f"\nConfiguration:")
        print(f"  Syringe Volume: {diag.get('syringe_volume_ul')} µL")
        print(f"  Backlash: {diag.get('backlash')} steps")
        print(f"  Firmware: {diag.get('firmware_version')}")

        print(f"\nSpeed Settings:")
        print(f"  Start Speed: {diag.get('start_speed')} pulses/sec")
        print(f"  Top Speed: {diag.get('top_speed')} pulses/sec")
        print(f"  Cutoff Speed: {diag.get('cutoff_speed')} pulses/sec")

        print(f"\nPressure:")
        print(f"  Current: {diag.get('pressure')}")
        print(f"  Limit: {diag.get('pressure_limit')}")

        if diag.get('error_info'):
            print(f"\nError Info:")
            print(f"  Code: {diag['error_info'].get('error_code')}")
            print(f"  Message: {diag['error_info'].get('error_msg')}")

        print("="*60 + "\n")

        return diag

if __name__ == "__main__":
    print("="*60)
    print("AffiPump Test - Step-to-uL Conversion")
    print("="*60)

    pump = AffipumpController()
    try:
        pump.open()

        print("\n1. Initialize to zero")
        pump.initialize_pumps()
        time.sleep(5)
        pos = pump.get_position(1)
        print(f"   Position: {pos}uL (should be 0)")

        print("\n2. Aspirate 300uL")
        pump.aspirate(1, 300, 150)
        time.sleep(3)
        pos = pump.get_position(1)
        print(f"   Position: {pos}uL (should be 300)")

        print("\n3. Dispense 150uL")
        pump.dispense(1, 150, 75)
        time.sleep(3)
        pos = pump.get_position(1)
        print(f"   Position: {pos}uL (should be 150)")

        print("\n4. Move to 500uL")
        pump.move_to_position(1, 500, 200)
        time.sleep(3)
        pos = pump.get_position(1)
        print(f"   Position: {pos}uL (should be 500)")

        print("\n5. Move to 0uL")
        pump.move_to_position(1, 0, 200)
        time.sleep(3)
        pos = pump.get_position(1)
        print(f"   Position: {pos}uL (should be 0)")

        print("\n" + "="*60)
        print("PHASE 1 COMPLETE!")
        print("="*60)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pump.close()
