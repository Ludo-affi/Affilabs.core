import serial
import time

print("Opening COM5 to check boot messages...")
print("Unplug and replug the USB cable now to see boot output...")
print("-" * 60)

try:
    s = serial.Serial('COM5', 115200, timeout=0.1)
    
    # Read for 10 seconds
    start_time = time.time()
    while time.time() - start_time < 10:
        if s.in_waiting > 0:
            data = s.read(s.in_waiting)
            print(data.decode('utf-8', errors='ignore'), end='')
        time.sleep(0.1)
    
    print("\n" + "-" * 60)
    print("Done reading boot messages.")
    s.close()
    
except Exception as e:
    print(f"Error: {e}")
    print("\nMake sure no other application is using COM5.")
