"""Fix calibrate_led_channel signature by adding wave_min_index and wave_max_index parameters"""

def fix_led_calibration_signature():
    """Add missing parameters to calibrate_led_channel function"""

    filepath = r"c:\Users\ludol\ezControl-AI\Affilabs.core beta\utils\led_calibration.py"

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the function definition line
    for i, line in enumerate(lines):
        if line.strip().startswith('def calibrate_led_channel('):
            print(f"Found function at line {i+1}")

            # Find the closing parenthesis
            j = i
            while j < len(lines):
                if ') -> int:' in lines[j]:
                    # Insert new parameters before the closing )
                    indent = '    '
                    new_params = [
                        f"{indent}wave_min_index: int = None,  # ROI start for saturation checking\n",
                        f"{indent}wave_max_index: int = None,  # ROI end for saturation checking\n"
                    ]

                    # Replace the line with ) -> int: to include new params
                    lines[j] = lines[j].replace(') -> int:', f"{new_params[0]}{new_params[1]}) -> int:")

                    # Also update the docstring Args section
                    doc_start = j + 1
                    while doc_start < len(lines) and 'Args:' not in lines[doc_start]:
                        doc_start += 1

                    if doc_start < len(lines):
                        # Find the end of existing args
                        arg_end = doc_start + 1
                        while arg_end < len(lines) and (lines[arg_end].startswith('        ') or lines[arg_end].strip() == ''):
                            arg_end += 1

                        # Insert new arg docs before Returns: section
                        new_docs = [
                            "        wave_min_index: Start index of wavelength ROI for saturation checking (560nm)\n",
                            "        wave_max_index: End index of wavelength ROI for saturation checking (720nm)\n",
                            "\n"
                        ]
                        for doc in reversed(new_docs):
                            lines.insert(arg_end, doc)

                    break
                j += 1
            break

    # Write back
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print("✅ Signature updated successfully!")

    # Verify
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'wave_min_index: int = None' in content and 'wave_max_index: int = None' in content:
        print("✅ Verification passed - parameters are in the file")
        return True
    else:
        print("❌ Verification failed - parameters not found")
        return False

if __name__ == '__main__':
    success = fix_led_calibration_signature()
    exit(0 if success else 1)
