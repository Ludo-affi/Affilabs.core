"""Add multi-intensity support to rank command - careful line-by-line replacement"""

firmware_path = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\affinite_p4spr.c"

with open(firmware_path, encoding="utf-8") as f:
    lines = f.readlines()

# Find and update specific lines
for i, line in enumerate(lines):
    # 1. Update function declaration (around line 146)
    if "bool led_rank_sequence(uint8_t intensity" in line:
        lines[i] = (
            "bool led_rank_sequence(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d, uint16_t settling_ms, uint16_t dark_ms);\n"
        )
        print(f"Line {i+1}: Updated function declaration")

    # 2. Update function definition (around line 962)
    elif (
        line.strip().startswith("bool led_rank_sequence(uint8_t intensity")
        and "uint16_t settling_ms" in line
    ):
        lines[i] = (
            "bool led_rank_sequence(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d, uint16_t settling_ms, uint16_t dark_ms){\n"
        )
        print(f"Line {i+1}: Updated function definition")

    # 3. str_intensity variable declaration
    elif "char str_intensity[4]" in line:
        indent = line[: len(line) - len(line.lstrip())]
        lines[i] = f"{indent}char str_int_a[4] = {{0}};\n"
        lines.insert(i + 1, f"{indent}char str_int_b[4] = {{0}};\n")
        lines.insert(i + 2, f"{indent}char str_int_c[4] = {{0}};\n")
        lines.insert(i + 3, f"{indent}char str_int_d[4] = {{0}};\n")
        print(f"Line {i+1}: Added 4 intensity buffers")
        break

# Second pass for parsing logic
with open(firmware_path, "w", encoding="utf-8") as f:
    f.writelines(lines)

with open(firmware_path, encoding="utf-8") as f:
    content = f.read()

# Update field parsing
content = content.replace(
    "if (field == 0 && field_pos < 3) str_intensity[field_pos++] = command[pos];",
    """if (field == 0 && field_pos < 3) str_int_a[field_pos++] = command[pos];
                                if (field == 1 && field_pos < 3) str_int_b[field_pos++] = command[pos];
                                if (field == 2 && field_pos < 3) str_int_c[field_pos++] = command[pos];
                                if (field == 3 && field_pos < 3) str_int_d[field_pos++] = command[pos];""",
)
content = content.replace(
    "if (field == 1 && field_pos < 4) str_settling",
    "if (field == 4 && field_pos < 4) str_settling",
)
content = content.replace(
    "if (field == 2 && field_pos < 4) str_dark",
    "if (field == 5 && field_pos < 4) str_dark",
)

# Update atoi calls
content = content.replace(
    "uint8_t intensity = atoi(str_intensity);",
    """uint8_t int_a = atoi(str_int_a);
                        uint8_t int_b = atoi(str_int_b);
                        uint8_t int_c = atoi(str_int_c);
                        uint8_t int_d = atoi(str_int_d);""",
)

# Update bounds checking
content = content.replace(
    "if (intensity > 255) intensity = 255;",
    """if (int_a > 255) int_a = 255;
                        if (int_b > 255) int_b = 255;
                        if (int_c > 255) int_c = 255;
                        if (int_d > 255) int_d = 255;""",
)

# Update function call
content = content.replace(
    "if (led_rank_sequence(intensity, settling_ms, dark_ms)){",
    "if (led_rank_sequence(int_a, int_b, int_c, int_d, settling_ms, dark_ms)){",
)

# Update level calculation in function body
content = content.replace(
    "uint16_t level = intensity * 255;",
    """uint16_t level_a = int_a * 255;
    uint16_t level_b = int_b * 255;
    uint16_t level_c = int_c * 255;
    uint16_t level_d = int_d * 255;""",
)

# Update PWM level settings
content = content.replace(
    "pwm_set_chan_level(slice_a, chan_a, level);",
    "pwm_set_chan_level(slice_a, chan_a, level_a);",
)
content = content.replace(
    "pwm_set_chan_level(slice_b, chan_b, level);",
    "pwm_set_chan_level(slice_b, chan_b, level_b);",
)
content = content.replace(
    "pwm_set_chan_level(slice_c, chan_c, level);",
    "pwm_set_chan_level(slice_c, chan_c, level_c);",
)
content = content.replace(
    "pwm_set_chan_level(slice_d, chan_d, level);",
    "pwm_set_chan_level(slice_d, chan_d, level_d);",
)

with open(firmware_path, "w", encoding="utf-8") as f:
    f.write(content)

print("\n✅ Multi-intensity support added!")
print("   Protocol: rank:int_a,int_b,int_c,int_d,settling_ms,dark_ms")
