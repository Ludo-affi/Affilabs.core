import serial
import time

print("Testing watchdog 'ka' command...")

try:
    s = serial.Serial('COM5', 115200, timeout=1)
    time.sleep(0.1)

    # Clear any existing data
    s.reset_input_buffer()

    # Send watchdog keepalive
    s.write(b'ka\n')
    time.sleep(0.1)

    # Read response
    response = s.read(100)
    print(f"Raw response: {repr(response)}")

    # Check for ACK (0x06 or '6')
    response_str = response.decode('utf-8', errors='ignore')
    has_ack = chr(6) in response_str or '6' in response_str

    print(f"Watchdog handler present: {has_ack}")

    if has_ack:
        print("✅ Watchdog command handler is working!")
    else:
        print("❌ No ACK received - watchdog may not be flashed")

    s.close()

except Exception as e:
    print(f"Error: {e}")
