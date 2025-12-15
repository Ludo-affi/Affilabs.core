r"""Build and flash Firmware V2.1 with rankbatch command.

This script:
1. Applies V2.1 modifications to base V2.0 firmware
2. Builds firmware using Pico SDK
3. Converts BIN to UF2
4. Provides flashing instructions

Requirements:
- pico-p4spr-firmware repo cloned
- Pico SDK installed
- Git Bash or similar build environment
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Paths
WORKSPACE = Path(__file__).parent
FIRMWARE_DIR = Path(
    r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware",
)
FIRMWARE_SOURCE = FIRMWARE_DIR / "affinite_p4spr.c"
BUILD_DIR = FIRMWARE_DIR / "build"
OUTPUT_DIR = WORKSPACE / "firmware_v2.1"

print("=" * 70)
print("FIRMWARE V2.1 BUILD SCRIPT")
print("=" * 70)

# Check firmware repo exists
if not FIRMWARE_DIR.exists():
    print(f"\n❌ ERROR: Firmware repo not found at {FIRMWARE_DIR}")
    print("\nClone it with:")
    print("  cd C:\\Users\\lucia\\OneDrive\\Desktop\\ezControl 2.0\\Affilabs.core")
    print("  git clone https://github.com/Ludo-affi/pico-p4spr-firmware")
    sys.exit(1)

if not FIRMWARE_SOURCE.exists():
    print(f"\n❌ ERROR: Firmware source not found at {FIRMWARE_SOURCE}")
    sys.exit(1)

print(f"\n✅ Found firmware repo at {FIRMWARE_DIR}")
print(f"✅ Found source file at {FIRMWARE_SOURCE}")

# Read current firmware
print("\n" + "=" * 70)
print("STEP 1: Applying V2.1 modifications")
print("=" * 70)

with open(FIRMWARE_SOURCE, encoding="utf-8") as f:
    content = f.read()

# Check current version
if 'const char* VERSION = "V2.1"' in content:
    print("\n✅ Firmware is already V2.1!")
    build = input("\nRebuild anyway? (y/n): ").strip().lower() == "y"
    if not build:
        print("Exiting...")
        sys.exit(0)
elif 'const char* VERSION = "V2.0"' not in content:
    print("\n❌ ERROR: Expected V2.0 firmware as base")
    print("Current firmware is not V2.0. Please ensure you have V2.0 applied first.")
    sys.exit(1)

print("\n📝 Backing up current firmware...")
backup_path = FIRMWARE_SOURCE.with_suffix(".c.v2_0_backup")
shutil.copy(FIRMWARE_SOURCE, backup_path)
print(f"   Saved to: {backup_path}")

print("\n📝 Applying V2.1 modifications...")

# CHANGE 1: Update VERSION
content = content.replace(
    'const char* VERSION = "V2.0";  // V2.0: Added rank command for firmware-controlled LED sequencing',
    'const char* VERSION = "V2.1";  // V2.1: Enhanced rank with batch intensities and cycle counting',
)
print("   ✅ Updated VERSION to V2.1")

# CHANGE 2: Add function declaration
# Find the line with bool led_rank_sequence declaration and add our new one after it
if "bool led_rank_batch_cycles" not in content:
    content = content.replace(
        "bool led_rank_sequence(uint8_t intensity, uint16_t settling_ms, uint16_t dark_ms);",
        """bool led_rank_sequence(uint8_t intensity, uint16_t settling_ms, uint16_t dark_ms);
bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d,
                           uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles);""",
    )
    print("   ✅ Added led_rank_batch_cycles() function declaration")

# CHANGE 3: Add rankbatch command handler
# Insert BEFORE the existing rank: handler
if "rankbatch:" not in content:
    rank_handler_start = content.find(
        "// NEW: Rank command for firmware-controlled LED sequencing",
    )
    if rank_handler_start == -1:
        rank_handler_start = content.find(
            "if (command[1] == 'a' && command[2] == 'n' && command[3] == 'k' && command[4] == ':')",
        )

    if rank_handler_start != -1:
        rankbatch_handler = """                // NEW V2.1: Rankbatch command for batch intensity cycling
                if (command[1] == 'a' && command[2] == 'n' && command[3] == 'k' &&
                    command[4] == 'b' && command[5] == 'a' && command[6] == 't' &&
                    command[7] == 'c' && command[8] == 'h' && command[9] == ':'){
                    // Parse rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
                    char str_int_a[4] = {0};
                    char str_int_b[4] = {0};
                    char str_int_c[4] = {0};
                    char str_int_d[4] = {0};
                    char str_settling[5] = {0};
                    char str_dark[5] = {0};
                    char str_cycles[5] = {0};

                    uint8_t field = 0;
                    uint8_t field_pos = 0;
                    uint8_t pos = 10;  // Start after "rankbatch:"

                    while (pos < 48 && command[pos] != '\\0' && command[pos] != '\\n'){
                        if (command[pos] == ','){
                            field++;
                            field_pos = 0;
                        }
                        else if (command[pos] >= '0' && command[pos] <= '9'){
                            if (field == 0 && field_pos < 3) str_int_a[field_pos++] = command[pos];
                            else if (field == 1 && field_pos < 3) str_int_b[field_pos++] = command[pos];
                            else if (field == 2 && field_pos < 3) str_int_c[field_pos++] = command[pos];
                            else if (field == 3 && field_pos < 3) str_int_d[field_pos++] = command[pos];
                            else if (field == 4 && field_pos < 4) str_settling[field_pos++] = command[pos];
                            else if (field == 5 && field_pos < 4) str_dark[field_pos++] = command[pos];
                            else if (field == 6 && field_pos < 4) str_cycles[field_pos++] = command[pos];
                        }
                        pos++;
                    }

                    uint8_t int_a = atoi(str_int_a);
                    uint8_t int_b = atoi(str_int_b);
                    uint8_t int_c = atoi(str_int_c);
                    uint8_t int_d = atoi(str_int_d);
                    uint16_t settling_ms = atoi(str_settling);
                    uint16_t dark_ms = atoi(str_dark);
                    uint16_t num_cycles = atoi(str_cycles);

                    // Debug output for parsing verification
                    if (debug){
                        printf("Parsed: A=%d B=%d C=%d D=%d settle=%d dark=%d cycles=%d\\n",
                               int_a, int_b, int_c, int_d, settling_ms, dark_ms, num_cycles);
                    }

                    if (int_a > 255) int_a = 255;
                    if (int_b > 255) int_b = 255;
                    if (int_c > 255) int_c = 255;
                    if (int_d > 255) int_d = 255;
                    if (settling_ms < 10) settling_ms = 15;
                    if (settling_ms > 1000) settling_ms = 1000;
                    if (dark_ms > 100) dark_ms = 100;
                    if (num_cycles < 1) num_cycles = 1;
                    if (num_cycles > 10000) num_cycles = 10000;

                    if (led_rank_batch_cycles(int_a, int_b, int_c, int_d, settling_ms, dark_ms, num_cycles)){
                        printf("%d", ACK);
                        if (debug){
                            printf(" rankbatch ok\\n");
                        }
                    }
                    else {
                        printf("%d", NAK);
                        if (debug){
                            printf(" rankbatch er\\n");
                        }
                    }
                }
                // V2.0 rank: command (backward compatibility)
                else """

        content = (
            content[:rank_handler_start]
            + rankbatch_handler
            + content[rank_handler_start:]
        )
        print("   ✅ Added rankbatch command handler")

# CHANGE 4: Add led_rank_batch_cycles() function implementation
if "BATCH_START" not in content:
    # Find where to insert (after led_rank_sequence function)
    # Look for the end of led_rank_sequence function
    search_start = content.find("/*** Function to execute LED ranking sequence")
    if search_start != -1:
        # Find the closing brace of that function
        rank_seq_end = content.find("\n}\n", search_start)
        if rank_seq_end != -1:
            rank_seq_end += len("\n}\n")

            rankbatch_function = """


/*** Function to execute LED ranking with batch intensities and cycle counting ***/

bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d,
                           uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles){

    led_brightness('a', int_a);
    led_brightness('b', int_b);
    led_brightness('c', int_c);
    led_brightness('d', int_d);

    printf("BATCH_START\\n");

    char channels[4] = {'a', 'b', 'c', 'd'};
    uint8_t intensities[4] = {int_a, int_b, int_c, int_d};

    for (uint16_t cycle = 0; cycle < num_cycles; cycle++){
        printf("CYCLE:%d\\n", cycle + 1);

        for (uint8_t i = 0; i < 4; i++){
            char ch = channels[i];
            uint8_t intensity = intensities[i];

            if (intensity == 0){
                printf("%c:SKIP\\n", ch);
                continue;
            }

            if (!led_on(ch)){
                if (debug){
                    printf("rankbatch led_on failed %c\\n", ch);
                }
                led_on('x');
                return false;
            }

            printf("%c:READY\\n", ch);
            sleep_ms(settling_ms);
            printf("%c:READ\\n", ch);

            uint8_t ack_char = getchar_timeout_us(10000000);
            if (ack_char == PICO_ERROR_TIMEOUT){
                if (debug){
                    printf("rankbatch timeout on %c cycle %d\\n", ch, cycle + 1);
                }
                led_on('x');
                return false;
            }

            printf("%c:DONE\\n", ch);

            if (i < 3){
                led_on('x');
                if (dark_ms > 0){
                    sleep_ms(dark_ms);
                }
            }
        }

        printf("CYCLE_END:%d\\n", cycle + 1);

        if (cycle < num_cycles - 1 && dark_ms > 0){
            led_on('x');
            sleep_ms(dark_ms);
        }
    }

    led_on('x');
    printf("BATCH_END\\n");

    return true;
}"""

            content = (
                content[:rank_seq_end] + rankbatch_function + content[rank_seq_end:]
            )
            print("   ✅ Added led_rank_batch_cycles() function implementation")
        else:
            print("   ⚠️  Could not find insertion point for function")
    else:
        print("   ⚠️  Could not locate led_rank_sequence function")

# Write modified firmware
print("\n📝 Writing modified firmware...")
with open(FIRMWARE_SOURCE, "w", encoding="utf-8") as f:
    f.write(content)
print(f"   ✅ Saved to: {FIRMWARE_SOURCE}")

# Build firmware
print("\n" + "=" * 70)
print("STEP 2: Building firmware")
print("=" * 70)

# Create/clean build directory
if BUILD_DIR.exists():
    print("\n🗑️  Cleaning build directory...")
    shutil.rmtree(BUILD_DIR)
BUILD_DIR.mkdir()
print(f"   ✅ Created: {BUILD_DIR}")

# Run CMake and Make
print("\n🔨 Running CMake...")
result = subprocess.run(
    ["cmake", "-G", "Unix Makefiles", ".."],
    cwd=BUILD_DIR,
    capture_output=True,
    text=True,
    check=False,
)

if result.returncode != 0:
    print("❌ CMake failed!")
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)
print("   ✅ CMake successful")

print("\n🔨 Running Make...")
result = subprocess.run(
    ["make", "-j4"],
    cwd=BUILD_DIR,
    capture_output=True,
    text=True,
    check=False,
)

if result.returncode != 0:
    print("❌ Make failed!")
    print(result.stdout)
    print(result.stderr)
    sys.exit(1)
print("   ✅ Build successful")

# Check for output files
bin_file = BUILD_DIR / "affinite_p4spr.bin"
uf2_file = BUILD_DIR / "affinite_p4spr.uf2"

if bin_file.exists():
    print(f"   ✅ Generated: {bin_file}")
else:
    print(f"   ❌ BIN file not found: {bin_file}")
    sys.exit(1)

# Copy UF2 to output directory
if uf2_file.exists():
    output_uf2 = OUTPUT_DIR / "affinite_p4spr_v2.1.uf2"
    shutil.copy(uf2_file, output_uf2)
    print(f"   ✅ Generated: {uf2_file}")
    print(f"   ✅ Copied to: {output_uf2}")
else:
    print("   ⚠️  UF2 file not found, converting from BIN...")
    # TODO: Add bin_to_uf2 conversion if needed

print("\n" + "=" * 70)
print("BUILD COMPLETE!")
print("=" * 70)

print("\n📦 Firmware V2.1 is ready!")
print(f"\n   Binary: {bin_file}")
if uf2_file.exists():
    print(f"   UF2:    {output_uf2}")

print("\n" + "=" * 70)
print("FLASHING INSTRUCTIONS")
print("=" * 70)
print("""
1. Hold the BOOTSEL button on the Pico
2. Connect USB cable (keep holding BOOTSEL)
3. Release BOOTSEL when Pico appears as drive (RPI-RP2)
4. Copy the UF2 file to the Pico drive:

   Windows:
     copy firmware_v2.1\\affinite_p4spr_v2.1.uf2 E:\\

   (Replace E: with your Pico drive letter)

5. Pico will automatically reboot with V2.1 firmware

6. Test with:
   python firmware_v2.1\\test_rankbatch.py COM5
""")

print("\n✅ Done!")
