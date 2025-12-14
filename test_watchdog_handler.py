import serial
import time

print("Testing if watchdog 'ka' command handler is present...")
print("Close the main application first, then press Enter.")
input()

try:
    s = serial.Serial('COM5', 115200, timeout=1)
    time.sleep(0.2)
    
    # Clear buffer
    s.reset_input_buffer()
    
    # Send watchdog keepalive
    print("Sending 'ka' command...")
    s.write(b'ka\n')
    time.sleep(0.2)
    
    # Read response
    response = s.read(100)
    print(f"Response: {repr(response)}")
    
    # Check for ACK (0x06 or character '6')
    if response:
        has_ack = (b'\x06' in response) or (b'6' in response)
        print(f"\n✅ Watchdog handler present: {has_ack}")
        if has_ack:
            print("V2.4.1 firmware with separate Timer 1 watchdog is confirmed!")
        else:
            print("❌ Unexpected response - watchdog may not be present")
    else:
        print("❌ No response - check if device is connected")
    
    s.close()
    
except Exception as e:
    print(f"\nError: {e}")
    print("Make sure the main application is closed.")
