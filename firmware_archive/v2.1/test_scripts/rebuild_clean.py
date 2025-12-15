#!/usr/bin/env python3
"""Rebuild clean firmware with all debug output removed."""

import os
import struct
import subprocess
import sys


def rebuild_firmware():
    """Rebuild the firmware with clean (no debug) output."""
    print("🔨 Rebuilding clean firmware...")

    # Build directory
    build_dir = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\build"
    make_exe = r"C:\Program Files (x86)\GnuWin32\bin\make.exe"

    # Change to build directory and run make
    os.chdir(build_dir)

    result = subprocess.run(
        [make_exe, "-j4"],
        capture_output=True,
        text=True,
        check=False,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Convert .bin to .uf2
    bin_path = os.path.join(build_dir, "affinite_p4spr.bin")
    uf2_path = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\ezControl-AI\affinite_CLEAN_v2.uf2"

    if not os.path.exists(bin_path):
        print(f"❌ Binary file not found: {bin_path}")
        return False

    # UF2 format constants
    UF2_MAGIC_START0 = 0x0A324655
    UF2_MAGIC_START1 = 0x9E5D5157
    UF2_MAGIC_END = 0x0AB16F30
    UF2_FLAG_FAMILY_ID_PRESENT = 0x00002000
    RP2040_FAMILY_ID = 0xE48BFF56

    with open(bin_path, "rb") as f:
        data = f.read()

    total_size = len(data)
    block_size = 256
    num_blocks = (total_size + block_size - 1) // block_size

    with open(uf2_path, "wb") as f:
        for block_num in range(num_blocks):
            offset = block_num * block_size
            chunk = data[offset : offset + block_size]
            if len(chunk) < block_size:
                chunk += b"\x00" * (block_size - len(chunk))

            uf2_block = struct.pack(
                "<IIIIIIII",
                UF2_MAGIC_START0,
                UF2_MAGIC_START1,
                UF2_FLAG_FAMILY_ID_PRESENT,
                0x10000000 + offset,
                block_size,
                block_num,
                num_blocks,
                RP2040_FAMILY_ID,
            )
            uf2_block += chunk
            uf2_block += b"\x00" * (512 - 32 - block_size - 4)
            uf2_block += struct.pack("<I", UF2_MAGIC_END)

            f.write(uf2_block)

    uf2_size = os.path.getsize(uf2_path)
    print(f"\n✅ Created {uf2_path}")
    print(f"   Binary: {total_size} bytes")
    print(f"   UF2: {uf2_size} bytes ({num_blocks} blocks)")
    print("\n✨ Clean firmware ready - enter bootloader mode and flash!")

    return True


if __name__ == "__main__":
    success = rebuild_firmware()
    sys.exit(0 if success else 1)
