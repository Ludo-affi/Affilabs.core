"""Add entry debug to rankbatch handler"""

from pathlib import Path

FIRMWARE_PATH = Path(
    r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\affinite_p4spr.c",
)

with open(FIRMWARE_PATH, encoding="utf-8") as f:
    content = f.read()

# Add debug right after entering rankbatch handler
old_text = """command[7] == 'c' && command[8] == 'h' && command[9] == ':'){
                    // Parse rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
                    char str_int_a[4] = {0};"""

new_text = """command[7] == 'c' && command[8] == 'h' && command[9] == ':'){
                    // Parse rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
                    if (debug){
                        printf("ENTER RANKBATCH HANDLER\\n");
                    }
                    char str_int_a[4] = {0};"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open(FIRMWARE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Added entry debug")
else:
    print("❌ Pattern not found")
