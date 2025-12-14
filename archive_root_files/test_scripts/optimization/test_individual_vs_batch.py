"""Test individual LED commands vs batch commands."""
import sys
import time
sys.path.insert(0, 'src')

from utils.controller import PicoP4SPR

def test_individual_vs_batch():
    """Compare individual LED commands vs batch commands."""
    print("Connecting to Pico...")
    pico = PicoP4SPR()

    if not pico.open():
        print("❌ Failed to connect")
        return

    print("✅ Connected\n")

    # Test 1: Individual LED command
    print("=" * 60)
    print("TEST 1: Individual LED command (LED A)")
    print("=" * 60)
    print(">>> LED A should LIGHT UP for 2 seconds <<<")
    pico.set_intensity('a', 255)
    time.sleep(2)
    pico.set_intensity('a', 0)
    print("LED A turned OFF\n")
    time.sleep(1)

    # Test 2: Batch command WITHOUT pre-enabling
    print("=" * 60)
    print("TEST 2: Batch command WITHOUT pre-enabling (LED B)")
    print("=" * 60)
    print(">>> LED B should light up? <<<")
    pico.set_batch_intensities(a=0, b=255, c=0, d=0)
    time.sleep(2)
    pico.set_batch_intensities(0, 0, 0, 0)
    print("LED B turned OFF\n")
    time.sleep(1)

    # Test 3: Pre-enable all channels, then batch command
    print("=" * 60)
    print("TEST 3: Pre-enable channel C, then batch command")
    print("=" * 60)
    print("Manually enabling channel C...")
    pico._ser.write(b"lc\n")
    time.sleep(0.05)
    response = pico._ser.read(50)
    print(f"Enable response: {response}")

    print(">>> LED C should LIGHT UP for 2 seconds <<<")
    pico.set_batch_intensities(a=0, b=0, c=255, d=0)
    time.sleep(2)
    pico.set_batch_intensities(0, 0, 0, 0)
    print("LED C turned OFF\n")
    time.sleep(1)

    # Test 4: Use individual command on channel D
    print("=" * 60)
    print("TEST 4: Individual command on LED D")
    print("=" * 60)
    print(">>> LED D should LIGHT UP for 2 seconds <<<")
    pico.set_intensity('d', 255)
    time.sleep(2)
    pico.set_intensity('d', 0)
    print("LED D turned OFF\n")

    print("=" * 60)
    print("Test complete!")
    print("=" * 60)
    print("\nResults:")
    print("- If LED A and D lit up: Individual commands work")
    print("- If LED B lit up: Batch commands work without pre-enable")
    print("- If LED C lit up: Batch commands need pre-enabled channels")

    pico.close()

if __name__ == "__main__":
    test_individual_vs_batch()
