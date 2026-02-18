"""Emergency script to stop pumps and send them home."""
import serial
import serial.tools.list_ports
import time

# Find the pump COM port
ports = list(serial.tools.list_ports.comports())
pump_port = None

for port in ports:
    if 'CH340' in port.description or 'USB-SERIAL' in port.description or 'USB Serial' in port.description:
        pump_port = port.device
        print(f"Found pump port: {port.device} - {port.description}")
        break

if not pump_port:
    print("No pump port found. Available ports:")
    for port in ports:
        print(f"  {port.device}: {port.description}")
    exit(1)

# Connect to pump
try:
    ser = serial.Serial(pump_port, 38400, timeout=1)
    print(f"Connected to pump on {pump_port}")

    # Terminate both pumps
    print("Terminating pump 1...")
    ser.write(b"/1TR\r")
    time.sleep(0.1)

    print("Terminating pump 2...")
    ser.write(b"/2TR\r")
    time.sleep(0.5)

    # Check status to confirm stopped
    ser.write(b"/1Q\r")
    time.sleep(0.1)
    response = ser.read(100)
    print(f"Pump 1 status: {response}")

    # Initialize both pumps to home
    print("Homing both pumps...")
    ser.write(b"/AZR\r")
    time.sleep(2.0)

    print("✓ Pumps stopped and sent home successfully!")

    ser.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
