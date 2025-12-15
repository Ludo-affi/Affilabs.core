"""Quick fix: Add missing led_rank_batch_cycles function to firmware"""

firmware_path = r"C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\pico-p4spr-firmware\affinite_p4spr.c"

# The complete function implementation
function_impl = """

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
}
"""

print("Adding led_rank_batch_cycles function...")

with open(firmware_path, encoding="utf-8") as f:
    content = f.read()

if "BATCH_START" in content:
    print("✅ Function already exists!")
else:
    # Append AFTER the file ends (not inside any function)
    content = content + "\n" + function_impl

    with open(firmware_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Function added successfully!")
    print("   Added at end of file (after main function)")

print("\nRebuild with:")
print("  python build_v2_1_firmware.py")
