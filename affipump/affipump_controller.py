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
from contextlib import contextmanager

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
            timeout=0.1  # Fast timeout for status queries - pump responds in ~20-50ms
        )
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        print(f"Connected to {self.port} @ {self.baudrate} baud (Syringe: {self.syringe_volume_ul}uL)")
        
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            
    def send_command(self, cmd, wait_time=None):
        if not self.ser or not self.ser.is_open:
            raise Exception("Port not open")
        self.last_command = cmd
        try:
            self.ser.reset_input_buffer()
        except Exception:
            pass
        self.ser.write((cmd + '\r').encode())

        if wait_time is not None:
            time.sleep(float(wait_time))

        deadline = time.time() + (self.ser.timeout or 0.1)  # Use 0.1s default timeout
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
        print("Initializing both pumps to zero...")
        self.send_command("/AZR")
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
    
    def aspirate_both(self, volume_ul, speed_ul_s=200):
        """Aspirate same volume on both pumps simultaneously"""
        steps = int(volume_ul * self.ul_to_steps)
        
        # Switch valves to inlet
        self.send_command("/1IR")
        self.send_command("/2IR")
        time.sleep(0.5)
        
        # Set velocity and aspirate
        self.send_command(f"/AV{speed_ul_s:.3f},1R")
        time.sleep(0.1)
        self.send_command(f"/AP{steps}R")
        return volume_ul
    
    def dispense_both(self, volume_ul, speed_ul_s=50):
        """Dispense same volume from both pumps simultaneously"""
        steps = int(volume_ul * self.ul_to_steps)
        
        # Switch valves to outlet
        self.send_command("/1OR")
        self.send_command("/2OR")
        time.sleep(0.5)
        
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
    
    def wait_until_both_ready(self, timeout=30):
        """Wait until BOTH pumps are ready (efficient parallel checking).
        
        Checks both pumps' status in each iteration for faster detection.
        Returns (pump1_ready, pump2_ready, elapsed_time, pump1_time, pump2_time).
        
        pump1_time and pump2_time are individual completion times (seconds).
        If a pump times out, its time will be None.
        """
        start = time.time()
        pump1_ready = False
        pump2_ready = False
        pump1_finish_time = None
        pump2_finish_time = None
        
        # Give pumps sufficient time to START being busy (avoid race condition with broadcast commands)
        time.sleep(0.25)
        
        while time.time() - start < timeout:
            # Check both pumps in parallel
            if not pump1_ready:
                status1 = self.get_status(1)
                if status1 and not status1.get('busy', True):
                    pump1_ready = True
                    pump1_finish_time = time.time() - start
            
            if not pump2_ready:
                status2 = self.get_status(2)
                if status2 and not status2.get('busy', True):
                    pump2_ready = True
                    pump2_finish_time = time.time() - start
            
            # Return as soon as both are ready
            if pump1_ready and pump2_ready:
                return (True, True, time.time() - start, pump1_finish_time, pump2_finish_time)
            
            time.sleep(1.0)  # Poll at 1Hz
        
        # Timeout - return what we got
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
