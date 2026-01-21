"""Quick script to query P4SPR firmware version."""

import serial
import serial.tools.list_ports
import time

# Pico USB VID/PID
PICO_VID = 0x2E8A
PICO_PID = 0x000A

print("Searching for Pico P4SPR controller...")

for dev in serial.tools.list_ports.comports():
    if dev.pid == PICO_PID and dev.vid == PICO_VID:
        print(f"Found Pico on {dev.device}")
        try:
            ser = serial.Serial(
                port=dev.device,
                baudrate=115200,
                timeout=0.5,
                write_timeout=1,
            )
            
            # Flush buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            
            # Send firmware version query
            print("Sending 'iv' command...")
            ser.write(b"iv\n")
            time.sleep(0.1)
            
            # Read response
            response = ser.readline().decode().strip()
            print(f"Firmware Version: {response}")
            
            ser.close()
            break
            
        except Exception as e:
            print(f"Error: {e}")
else:
    print("No Pico P4SPR found!")
