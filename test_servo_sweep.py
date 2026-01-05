"""Test servo calibration sweep with V2.1 firmware"""
from affilabs.utils.controller import PicoP4PRO
import time

ctrl = PicoP4PRO()
ctrl.open()

print("Testing servo sweep with V2.1 firmware...")
print("Listen for servo movement at each position:\n")

test_pwm_values = [1, 30, 60, 90, 120, 150, 180, 210, 240]

for pwm in test_pwm_values:
    degrees = int(5 + (pwm / 255.0) * 170)
    print(f"PWM {pwm:3d} -> {degrees:3d}° ... ", end='', flush=True)
    
    result = ctrl.servo_move_raw_pwm(pwm)
    if result:
        print("✓ ACK")
    else:
        print("✗ NAK")
    
    time.sleep(1.5)  # Wait for servo to settle

ctrl.close()
print("\n✅ Servo sweep test complete!")
print("If you heard the servo moving through different positions, calibration will work.")
