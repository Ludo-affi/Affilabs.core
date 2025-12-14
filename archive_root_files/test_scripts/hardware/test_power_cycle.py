"""
POWER CYCLE TEST - Check LED state at boot
"""
import serial
import time

port = 'COM4'

print("\n" + "="*70)
print("POWER CYCLE TEST")
print("="*70)
print("\n⚠️  INSTRUCTIONS:")
print("1. UNPLUG the USB cable from the Pico NOW")
print("2. Wait 3 seconds")
print("3. Visually check - are ALL LEDs OFF?")
print("4. Then PLUG IN the USB cable")

input("\nPress ENTER after you've plugged USB back in...")

print("\n🔌 Connecting to check boot state...")
try:
    ser = serial.Serial(port, 115200, timeout=1)
    time.sleep(2)

    print("\n👁️  VISUAL CHECK:")
    print("   Are ALL LEDs OFF after power-on?")
    result = input("   (y/n): ").strip().lower()

    if result == 'y':
        print("\n✅ GOOD: LEDs are OFF at boot (hardware is OK)")
        print("   The problem is only with firmware commands")
    else:
        print("\n❌ BAD: LEDs are ON at boot!")
        print("   This could be:")
        print("   1. Hardware problem (PCB issue)")
        print("   2. Firmware initialization bug")
        print("   3. Previous state not cleared from flash")

    # Try a simple lx command
    print("\n\n📤 Now sending 'lx' command (turn all OFF)...")
    ser.write(b"lx\n")
    time.sleep(0.1)
    response = ser.readline().decode().strip()
    print(f"📥 Response: {response}")

    print("\n👁️  Are ALL LEDs OFF now?")
    result2 = input("   (y/n): ").strip().lower()

    if result2 == 'y':
        print("\n✅ lx command works when LEDs are already OFF")
        print("   Problem only occurs AFTER turning LEDs ON")
    else:
        print("\n❌ lx command doesn't work even at boot")
        print("   This is a critical firmware bug!")

    ser.close()

except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*70)
