"""
Debug script to analyze Cavro response format
"""
import serial
import time

def analyze_response(command_str):
    """Send command and show detailed response analysis"""
    ser = serial.Serial(port='COM8', baudrate=38400, timeout=2)
    time.sleep(0.3)

    command = command_str.encode() + b'\r'
    ser.write(command)
    time.sleep(0.3)

    response = ser.read(200)

    print(f"\nCommand: {command_str}")
    print(f"Response length: {len(response)} bytes")
    print(f"Raw bytes: {response}")
    print(f"Hex: {' '.join(f'{b:02X}' for b in response)}")

    # Try to decode readable parts
    try:
        readable = response.decode('ascii', errors='replace')
        print(f"ASCII: {repr(readable)}")
    except:
        pass

    ser.close()
    return response

print("="*60)
print("Analyzing Cavro Response Format")
print("="*60)

# Test basic queries
analyze_response("/1?")      # Status/position
analyze_response("/1?4")     # Position query
analyze_response("/1?6")     # Valve position
analyze_response("/2?")      # Pump 2 status
analyze_response("/1?8")     # Pressure (attempt 1)
analyze_response("/1?27")    # Pressure (attempt 2)
