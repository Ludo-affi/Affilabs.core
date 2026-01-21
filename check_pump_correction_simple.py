"""
Simple script to read pump correction values from P4PROPLUS firmware
"""
import sys
import serial
import serial.tools.list_ports
import time

def find_p4pro_port():
    """Find P4PRO+ controller COM port"""
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "USB Serial Port" in port.description or "CH340" in port.description:
            return port.device
    return None

def read_pump_corrections():
    """Read pump correction values using pc command"""
    port = find_p4pro_port()
    if not port:
        print("❌ P4PROPLUS not found")
        return
    
    print(f"✅ Connected to {port}")
    
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        time.sleep(0.5)
        
        # Flush buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
        # Send pc command to read pump corrections
        print("\nSending 'pc' command to read pump corrections...")
        ser.write(b'pc\n')
        time.sleep(0.2)
        
        # Read response
        response = ser.read(100)
        print(f"Raw response: {response}")
        
        if len(response) >= 2:
            # Pump corrections are returned as 2 bytes
            pump1_correction = response[0]
            pump2_correction = response[1]
            
            print(f"\n📊 PUMP CORRECTIONS:")
            print(f"   Pump 1 correction: {pump1_correction}")
            print(f"   Pump 2 correction: {pump2_correction}")
            print(f"\nNote: Default correction is typically 10 (1.0x multiplier)")
            print(f"      Values scale flow rate: actual_flow = commanded_flow × (correction/10)")
        else:
            print(f"❌ Unexpected response length: {len(response)} bytes")
        
        ser.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    read_pump_corrections()
