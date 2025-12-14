"""
Simple test for rankbatch command:
- LEDs A, B, C, D at different intensities
- 250ms settle (on time)
- 250ms dark time
- 10 cycles total
"""

import serial
import time
import sys

def test_rankbatch_simple(port_name="COM5"):
    """Test rankbatch with 10 cycles, 4 LEDs at different intensities."""
    
    print("=" * 60)
    print("RANKBATCH SIMPLE TEST")
    print("=" * 60)
    print(f"Configuration:")
    print(f"  LED A: 100 intensity")
    print(f"  LED B: 150 intensity")
    print(f"  LED C: 200 intensity")
    print(f"  LED D: 250 intensity")
    print(f"  Settle: 250ms")
    print(f"  Dark: 250ms")
    print(f"  Cycles: 10")
    print(f"  Expected time per cycle: ~2 seconds")
    print(f"  Total expected time: ~20 seconds")
    print("=" * 60)
    print()
    
    try:
        # Connect to Pico
        print(f"📡 Connecting to {port_name}...")
        ser = serial.Serial(port_name, 115200, timeout=2)
        time.sleep(2)  # Wait for connection to stabilize
        
        # Clear any pending data
        ser.reset_input_buffer()
        
        # Check firmware version
        print("🔍 Checking firmware version...")
        ser.write(b"iv\n")
        time.sleep(0.5)
        response = ser.read_all().decode('utf-8', errors='ignore').strip()
        print(f"   {response}")
        
        if "V2.1" not in response:
            print("⚠️  Warning: Firmware V2.1 not detected!")
            print("   This test requires V2.1 firmware with rankbatch command")
        
        print()
        
        # Send rankbatch command
        # Format: rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
        command = "rankbatch:100,150,200,250,250,250,10\n"
        print(f"📤 Sending command: {command.strip()}")
        print()
        
        start_time = time.time()
        ser.write(command.encode())
        
        cycle_count = 0
        last_cycle = None
        
        # Monitor output
        print("📊 Monitoring output:")
        print("-" * 60)
        
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line:
                    # Track cycle progress
                    if line.startswith("CYCLE:"):
                        cycle_num = int(line.split(":")[1])
                        if cycle_num != last_cycle:
                            elapsed = time.time() - start_time
                            print(f"\n⏱️  CYCLE {cycle_num}/10 (elapsed: {elapsed:.1f}s)")
                            last_cycle = cycle_num
                            cycle_count = cycle_num
                    
                    elif line.startswith("BATCH_START"):
                        print(f"🚀 {line}")
                    
                    elif line.startswith("BATCH_END"):
                        elapsed = time.time() - start_time
                        print(f"\n✅ {line}")
                        print(f"\n⏱️  Total time: {elapsed:.2f}s")
                        print(f"📊 Cycles completed: {cycle_count}")
                        print(f"⚡ Average time per cycle: {elapsed/cycle_count:.2f}s")
                        break
                    
                    elif "READY" in line or "READ" in line or "DONE" in line:
                        # Show channel activity with simple indicator
                        channel = line.split(":")[0]
                        status = line.split(":")[1]
                        
                        if status == "READY":
                            print(f"   {channel.upper()}: ", end="", flush=True)
                        elif status == "READ":
                            # Send ACK
                            ser.write(b"ack\n")
                            print("📸", end="", flush=True)
                        elif status == "DONE":
                            print(" ✓", end="", flush=True)
                    
                    elif line.startswith("CYCLE_END"):
                        print()  # New line after cycle ends
            
            # Timeout after 30 seconds
            if time.time() - start_time > 30:
                print("\n⏱️  Timeout after 30 seconds")
                break
        
        print("-" * 60)
        print()
        ser.close()
        print("📡 Disconnected")
        
    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        ser.close()
        print("📡 Disconnected")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM5"
    test_rankbatch_simple(port)
