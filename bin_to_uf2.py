"""Convert .bin to .uf2 format for RP2040"""
import struct
import sys

UF2_MAGIC_START0 = 0x0A324655
UF2_MAGIC_START1 = 0x9E5D5157
UF2_MAGIC_END    = 0x0AB16F30
UF2_FLAG_FAMILY_ID_PRESENT = 0x2000
RP2040_FAMILY_ID = 0xe48bff56

def convert_to_uf2(bin_path, uf2_path):
    with open(bin_path, 'rb') as f:
        data = f.read()

    FLASH_START = 0x10000000
    PAGE_SIZE = 256
    BLOCK_SIZE = 512 - 32  # 480 bytes of data per block

    num_blocks = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE

    with open(uf2_path, 'wb') as out:
        for i in range(num_blocks):
            offset = i * BLOCK_SIZE
            chunk = data[offset:offset + BLOCK_SIZE]
            chunk_len = len(chunk)

            # Pad to 476 bytes (UF2 data section size)
            chunk += b'\x00' * (476 - chunk_len)

            # Build UF2 block
            block = struct.pack('<IIIIIIII',
                UF2_MAGIC_START0,
                UF2_MAGIC_START1,
                UF2_FLAG_FAMILY_ID_PRESENT,
                FLASH_START + offset,
                476,  # Payload size
                i,    # Block number
                num_blocks,
                RP2040_FAMILY_ID
            )
            block += chunk
            block += struct.pack('<I', UF2_MAGIC_END)

            out.write(block)

    print(f"✅ Converted: {bin_path} -> {uf2_path}")
    print(f"   Total blocks: {num_blocks}")
    print(f"   Binary size: {len(data)} bytes")

if __name__ == "__main__":
    import os
    bin_path = r"C:\Users\ludol\ezControl-AI\firmware\pico_p4spr\build\affinite_p4spr.bin"
    uf2_path = r"C:\Users\ludol\ezControl-AI\firmware\pico_p4spr\build\affinite_p4spr.uf2"

    if not os.path.exists(bin_path):
        print(f"❌ Error: {bin_path} not found!")
        sys.exit(1)

    convert_to_uf2(bin_path, uf2_path)
