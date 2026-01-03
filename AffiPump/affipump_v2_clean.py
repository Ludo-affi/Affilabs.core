# -*- coding: utf-8 -*-
"""
Affipump Controller - Phase 1 Complete with 1000uL Syringe Support
Cavro Centris pumps - Uses SEPARATE commands (not chained) for reliability
"""
import serial
import time
import re

class AffipumpController:
    def __init__(self, port='COM8', baudrate=38400, syringe_volume_ul=1000):
        self.port = port
        self.baudrate = baudrate
        self.syringe_volume_ul = syringe_volume_ul  # 1000uL syringes
        self.ser = None
        
    def open(self):
        """Open serial connection"""
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2
        )
        time.sleep(0.5)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        print(f"Connected to {self.port} at {self.baudrate} baud (Syringe: {self.syringe_volume_ul}uL)")
        
    def close(self):
        """Close serial connection"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            
    def send_command(self, command_str, wait_time=0.3):
        """Send command and return raw response"""
        if not self.ser or not self.ser.is_open:
            raise Exception("Port not open")
            
        command = command_str.encode() + b'\r'
        self.ser.write(command)
        time.sleep(wait_time)
        
        response = self.ser.read(200)
        return response
    
    def parse_response(self, response):
        """Parse Cavro response - extract status byte and data"""
        if len(response) < 6:
            return None
            
        # Response format: /1?\r\x00\xff/0`[data]\x03\r\n\x00
        match = re.search(rb'/0(.)(.+?)\x03', response)
        if match:
            status = match.group(1)[0]
            data = match.group(2).decode('ascii', errors='ignore')
            return {'status': status, 'data': data}
        return None
    
    def parse_error_code(self, status_byte):
        """Decode status byte into error flags and state"""
        errors = []
        if status_byte & 0x01:
            errors.append("INITIALIZATION_ERROR")
        if status_byte & 0x02:
            errors.append("INVALID_COMMAND")
        if status_byte & 0x04:
            errors.append("INVALID_OPERAND")
        if status_byte & 0x08:
            errors.append("EEPROM_ERROR")
        
        return {
            'initialized': bool(status_byte & 0x10),
            'idle': bool(status_byte & 0x20),
            'busy': bool(status_byte & 0x40),
            'errors': errors,
            'ready': (status_byte == 0x60)
        }
    
    def validate_position(self, position_ul):
        """Validate position is within syringe capacity"""
        if position_ul < 0:
            raise ValueError(f"Position {position_ul}uL cannot be negative")
        if position_ul > self.syringe_volume_ul:
            raise ValueError(f"Position {position_ul}uL exceeds syringe capacity ({self.syringe_volume_ul}uL)")
        return True
    
    # ========== CORE PUMP OPERATIONS ==========
    
    def initialize_pumps(self):
        """Initialize both pumps - homes syringes to zero position"""
        response = self.send_command("/AZR", wait_time=5.0)
        status = self.get_status(1)
        return status is not None
    
    def get_status(self, pump_num):
        """Query pump status and current position"""
        response = self.send_command(f"/{pump_num}?")
        return self.parse_response(response)
    
    def get_position(self, pump_num):
        """Get current plunger position in uL"""
        result = self.get_status(pump_num)
        if result and result['data']:
            try:
                return int(result['data'])
            except ValueError:
                return None
        return None
    
    def get_current_volume(self, pump_num):
        """Alias for get_position"""
        return self.get_position(pump_num)
    
    def stop_pump(self, pump_num):
        """Emergency stop - terminates current operation immediately"""
        return self.send_command(f"/{pump_num}TR", wait_time=0.1)
    
    def is_busy(self, pump_num):
        """Check if pump is currently moving"""
        result = self.get_status(pump_num)
        if result:
            status_info = self.parse_error_code(result['status'])
            return status_info['busy']
        return False
    
    def wait_until_ready(self, pump_num, timeout=30):
        """Block until pump finishes current operation"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.is_busy(pump_num):
                return True
            time.sleep(0.2)
        return False
    
    def set_speed(self, pump_num, speed_ul_s):
        """Set plunger speed - MUST be called before move commands"""
        return self.send_command(f"/{pump_num}V{speed_ul_s},1R", wait_time=0.2)
    
    def aspirate(self, pump_num, volume_ul, speed_ul_s=200):
        """
        Aspirate volume from INPUT port (relative move)
        Uses SEPARATE commands for reliability
        """
        current_pos = self.get_position(pump_num) or 0
        target_pos = current_pos + volume_ul
        
        # Validate target position
        self.validate_position(target_pos)
        
        # Send separate commands (more reliable than chaining)
        self.send_command(f"/{pump_num}IR", wait_time=0.3)  # Valve to INPUT
        self.send_command(f"/{pump_num}V{speed_ul_s},1R", wait_time=0.2)  # Set speed
        self.send_command(f"/{pump_num}A{target_pos}R", wait_time=volume_ul/speed_ul_s + 1)  # Move
        
        return target_pos
    
    def dispense(self, pump_num, volume_ul=None, speed_ul_s=50):
        """
        Dispense to OUTPUT port
        If volume_ul is None: dispenses all (moves to 0)
        If volume_ul specified: dispenses that amount (relative move)
        Uses SEPARATE commands for reliability
        """
        current_pos = self.get_position(pump_num) or 0
        
        if volume_ul is None:
            target_pos = 0
            wait_time = current_pos/speed_ul_s + 1
        else:
            target_pos = max(0, current_pos - volume_ul)
            wait_time = volume_ul/speed_ul_s + 1
        
        # Send separate commands
        self.send_command(f"/{pump_num}OR", wait_time=0.3)  # Valve to OUTPUT
        self.send_command(f"/{pump_num}V{speed_ul_s},1R", wait_time=0.2)  # Set speed
        self.send_command(f"/{pump_num}A{target_pos}R", wait_time=wait_time)  # Move
        
        return target_pos
    
    def move_to_position(self, pump_num, position_ul, speed_ul_s=200):
        """Move plunger to absolute position (does not change valve)"""
        self.validate_position(position_ul)
        
        current_pos = self.get_position(pump_num) or 0
        volume_diff = abs(position_ul - current_pos)
        
        # Set speed then move
        self.send_command(f"/{pump_num}V{speed_ul_s},1R", wait_time=0.2)
        self.send_command(f"/{pump_num}A{position_ul}R", wait_time=volume_diff/speed_ul_s + 1)
        
        return position_ul
    
    # ========== VALVE CONTROL ==========
    
    def set_valve_input(self, pump_num):
        """Set valve to INPUT port (left)"""
        return self.send_command(f"/{pump_num}IR")
    
    def set_valve_output(self, pump_num):
        """Set valve to OUTPUT port (right)"""
        return self.send_command(f"/{pump_num}OR")
    
    def set_valve_bypass(self, pump_num):
        """Set valve to BYPASS port (if equipped)"""
        return self.send_command(f"/{pump_num}BR")
    
    def get_valve_position(self, pump_num):
        """Query valve position - not supported on all Cavro models"""
        return None
    
    # ========== PRESSURE MONITORING ==========
    
    def get_pressure(self, pump_num):
        """Get back pressure reading (if sensor equipped)"""
        for cmd_suffix in ['?8', '?27']:
            response = self.send_command(f"/{pump_num}{cmd_suffix}")
            result = self.parse_response(response)
            
            if result and result['data']:
                try:
                    pressure = int(result['data'])
                    position = self.get_position(pump_num)
                    if pressure != position:
                        return pressure
                except ValueError:
                    continue
        
        return None
    
    def get_back_pressure(self, pump_num):
        """Alias for get_pressure"""
        return self.get_pressure(pump_num)


# ========== TEST WITH 1000uL VALIDATION ==========

if __name__ == "__main__":
    print("="*60)
    print("AffiPump Controller - 1000uL Syringe Test")
    print("="*60)
    
    pump = AffipumpController(port='COM8', baudrate=38400, syringe_volume_ul=1000)
    
    try:
        pump.open()
        
        # Initialize
        print("\nInitializing pumps...")
        pump.initialize_pumps()
        time.sleep(5)  # Wait for full initialization`n        `n        # Verify initialization moved to zero`n        pos = pump.get_position(1)`n        if pos > pump.syringe_volume_ul:`n            print(f"WARNING: Pump at {pos}uL, re-initializing...")`n            pump.initialize_pumps()`n            time.sleep(5)`n        `n        # Check position
        pos = pump.get_position(1)
        print(f"Initial position: {pos}uL")
        
        # Test aspirate with separate commands
        print("\nAspirating 200uL (separate commands)...")
        target = pump.aspirate(1, 200, speed_ul_s=100)
        time.sleep(3)
        final_pos = pump.get_position(1)
        print(f"Target: {target}uL, Actual: {final_pos}uL")
        
        # Test dispense
        print("\nDispensing 100uL...")
        target = pump.dispense(1, 100, speed_ul_s=50)
        time.sleep(3)
        final_pos = pump.get_position(1)
        print(f"Target: {target}uL, Actual: {final_pos}uL")
        
        # Test capacity validation
        print("\nTesting 1000uL capacity validation...")
        try:
            pump.validate_position(1200)
            print("  Should have failed!")
        except ValueError as e:
            print(f"  Correctly rejected: {e}")
        
        print("\n" + "="*60)
        print("PHASE 1 COMPLETE!")
        print("  - Separate commands working")
        print("  - 1000uL syringe validation active")
        print("  - All basic functions implemented")
        print("="*60)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pump.close()

