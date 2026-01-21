/**
 * Copyright (c) 2022 Affinite Instruments
 * Written by Lucia Iannantuono
 *
 * Version: 2.3 (Ring Buffer Fix)
 * Changes: Ring buffer for READY events to prevent loss when printf blocks
 *
 * Based on code example repository:
 * Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 * SPDX-License-Identifier: BSD-3-Clause
 */


/********************************************************
*
* INCLUDES
*
*/

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "hardware/pwm.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "hardware/i2c.h"
#include "hardware/timer.h"
#include "hardware/irq.h"

/********************************************************
*
* DEVICE & FIRMWARE INFO
*
*/
const char* DEVICE = "P4SPR";
const char* VERSION = "V2.4";  // V2.4: CYCLE_START sync - ONE event per cycle (75% less USB traffic)

/********************************************************
*
* PINOUT DEFINITIONS (GPIO NUMBERING)
*
*/

// PICO DEBUG LED
const uint8_t BOARD_LED = PICO_DEFAULT_LED_PIN;

// SPR CORE I/O
const uint8_t SERVO_PIN = 0;
const uint8_t LED_A_CTRL = 28;
const uint8_t LED_B_CTRL = 27;
const uint8_t LED_C_CTRL = 22;  // CRITICAL: Must be GPIO 22 (Slice 3), NOT 26 (Slice 5 conflicts with LED_B)
const uint8_t LED_D_CTRL = 21;


// DEVICE I/O
const uint8_t DEV_OK = 19;

// I2C BUS 0
#define i2c0 (&i2c0_inst)
const uint8_t I2C0_SDA = 12;
const uint8_t I2C0_SCL = 13;

// FUTURE SPARE
const uint8_t PICO_SPARE_1 = 26;  // GPIO 26 now available (LED_C moved to GPIO 22)
const uint8_t PICO_SPARE_2 = 18;
const uint8_t POWER_BTN = 17;
const uint8_t PICO_SPARE_4 = 16;

/********************************************************
*
* CONSTANTS & VARIABLE DEFAULTS
*
*/
const uint8_t ACK = 6;
const uint8_t NAK = 1;

const uint8_t TEMP_ADDR = 0x48;
uint8_t temp_buffer[2];
float temp = 0.0;

const uint8_t EXP_ADDR = 0x20;
const uint8_t CONFIG_PORT_0 = 0x06;
const uint8_t OUTPUT_PORT_0 = 0x02;
uint8_t out_port_zero [2] = {OUTPUT_PORT_0, 0x00};
const uint8_t LED_1_G_MASK = 0x10;
const uint8_t LED_2_G_MASK = 0x40;

const uint8_t DEFAULT_S = 30;
const uint8_t DEFAULT_P = 120;
const uint8_t MIN_DEG = 5;
const uint8_t MAX_DEG = 175;
uint8_t curr_s;
uint8_t curr_p;

// Servo timing control
const uint16_t DEFAULT_SERVO_SPEED = 500;  // Default 500ms pulse
const uint16_t MIN_SERVO_SPEED = 200;      // Minimum 200ms (safety)
const uint16_t MAX_SERVO_SPEED = 2000;     // Maximum 2000ms (2 seconds)
uint16_t servo_pulse_duration = DEFAULT_SERVO_SPEED;

const uint8_t SERVO_FREQ = 50;
const uint8_t SERVO_PWM_DIV = 50;
const uint SERVO_SLICE = 0;
const uint SERVO_CH = 0;
const uint16_t SERVO_WRAP = (125000000/SERVO_PWM_DIV) / SERVO_FREQ;

const uint16_t LED_FREQ = 400;
const uint8_t LED_PWM_DIV = 10;
// NOTE: These slice numbers work despite seeming incorrect - DO NOT change them!
// gpio_set_function() handles the GPIO→slice mapping, these are used differently
const uint LED_A_SLICE = 6;
const uint LED_A_CH = 0;
const uint LED_B_SLICE = 5;
const uint LED_B_CH = 1;
const uint LED_C_SLICE = 3;
const uint LED_C_CH = 0;
const uint LED_D_SLICE = 2;
const uint LED_D_CH = 1;
const uint16_t LED_WRAP = (125000000/LED_PWM_DIV) / LED_FREQ;

uint16_t led_a_level = LED_WRAP;
uint16_t led_b_level = LED_WRAP;
uint16_t led_c_level = LED_WRAP;
uint16_t led_d_level = LED_WRAP;

const uint32_t FLASH_WRITE_OFFSET = (PICO_FLASH_SIZE_BYTES - FLASH_SECTOR_SIZE);
const uint8_t* FLASH_READ_ADDRESS = (const uint8_t *) (XIP_BASE + FLASH_WRITE_OFFSET);

/* DEBUG FLAG FOR DEVELOPMENT */
const bool debug = false;

/********************************************************
*
* V2.2: HARDWARE TIMER STATE STRUCTURES
*
*/

// Timer1: LED Sequencer State (runs at 1kHz in ISR)
volatile struct {
    bool active;                    // Is sequence running?
    uint8_t current_led;            // 0=A, 1=B, 2=C, 3=D
    uint16_t current_cycle;         // Current cycle number
    uint16_t total_cycles;          // Total cycles to run
    uint32_t timer_ms;              // Millisecond counter
    uint8_t intensities[4];         // Intensity for each LED (A, B, C, D)
    uint16_t settle_ms;             // LED settling time (default 245ms)
    uint16_t dark_ms;               // Dark period between LEDs (default 5ms)
    uint8_t phase;                  // 0=LED_ON, 1=SETTLE, 2=READY_SENT, 3=DARK
    uint32_t phase_start_ms;        // When current phase started
} led_sequencer = {
    .active = false,
    .current_led = 0,
    .current_cycle = 0,
    .total_cycles = 0,
    .timer_ms = 0,
    .intensities = {0, 0, 0, 0},
    .settle_ms = 245,
    .dark_ms = 5,
    .phase = 0,
    .phase_start_ms = 0
};

// LED name lookup for READY signals
const char led_names[4] = {'a', 'b', 'c', 'd'};

// Repeating timer handles
static struct repeating_timer led_timer;      // Timer 0: LED sequencer at 1kHz
static struct repeating_timer watchdog_timer; // Timer 1: Watchdog at 1Hz (every 1 second)

// Event queue for ISR-to-main communication (avoid printf in ISR)
// V2.4: Cycle synchronization - send ONE event per cycle instead of 4 READY events
volatile struct {
    bool cycle_start;        // Set by ISR when new cycle begins (LED_A turns on)
    uint32_t cycle_number;   // Current cycle number for verification
    bool batch_complete;     // Set when batch finishes
} isr_events = {false, 0, false};

// V2.4.1: Watchdog timer to prevent runaway firmware
// If no keepalive received within timeout, rankbatch auto-stops
volatile struct {
    bool enabled;            // Watchdog active flag
    uint64_t last_keepalive; // Last keepalive timestamp (microseconds)
    uint64_t timeout_us;     // Timeout period in microseconds
} watchdog_state = {
    .enabled = false,
    .last_keepalive = 0,
    .timeout_us = 120000000  // 120 second default timeout
};

/********************************************************
*
* FUNCTION DECLARATIONS
*
*/


// SETUP FUNCTIONS
void affinite_setup (void);
bool check_flash (void);


// LED FUNCTIONS
void led_setup (void);
bool led_on (char ch_led);
bool led_rank_sequence(uint8_t intensity, uint16_t settling_ms, uint16_t dark_ms);
bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d,
                           uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles);
bool led_multi_on(const char* leds, uint8_t count);
uint8_t led_brightness (char ch_led, uint8_t brightness);

// V2.2: TIMER-BASED RANKBATCH FUNCTIONS
bool led_sequencer_callback(struct repeating_timer *t);
void rankbatch_start(uint8_t ia, uint8_t ib, uint8_t ic, uint8_t id, 
                     uint16_t settle_ms, uint16_t dark_ms, uint16_t n_cycles);
void rankbatch_stop(void);

// V2.4.1: WATCHDOG TIMER FUNCTIONS (separate hardware timer)
bool watchdog_timer_callback(struct repeating_timer *t);


// SERVO FUNCTIONS
void move_servo (double duty);
double get_servo_duty (uint8_t deg);
void pwm_servo_setup (void);
bool servo_flash (uint8_t s, uint8_t p);
void servo_read (void);


// DEVICE FUNCTIONS
void device_setup (void);
void device_on (void);
void device_off (void);

// I/O EXPANDER FUNCTIONS


/********************************************************
*
* MAIN CODE
*
*/

int main () {
	bool power_button_held = false;

    // init stdio
    stdio_init_all();
    sleep_ms(500);  // Give USB time to enumerate
    printf("=== P4SPR V2.2 BOOT ===\n");

    // run gpio setup and flash for user
    printf("Running affinite_setup...\n");
    affinite_setup();
    printf("Setup complete\n");

    gpio_put(BOARD_LED, 1);
    sleep_ms(500);
    gpio_put(BOARD_LED, 0);
    sleep_ms(500);

    // check flash is initialized and flash for user
    bool already_initialized = check_flash();
    if (already_initialized){
        if (debug){
            printf("servo values ok\n");
        }
        gpio_put(BOARD_LED, 1);
        sleep_ms(500);
        gpio_put(BOARD_LED, 0);
        sleep_ms(500);
    }

    else {
        if (debug){
            printf("flashed servo defaults\n");
        }
        gpio_put(BOARD_LED, 1);
        sleep_ms(2000);
        gpio_put(BOARD_LED, 0);
        sleep_ms(2000);
    }

    // V2.2: Initialize hardware timer for LED sequencing at 1kHz
    printf("=== TIMER INIT START ===\n");
    
    // Prevent debugger from pausing timers
    timer_hw->dbgpause = 0;
    printf("Timer dbgpause cleared\n");
    
    // Timer 0: LED sequencer at 1kHz
    bool timer_ok = add_repeating_timer_ms(-1, led_sequencer_callback, NULL, &led_timer);
    printf("=== LED TIMER: %s ===\n", timer_ok ? "SUCCESS" : "FAILED");
    
    if (timer_ok) {
        printf("LED sequencer registered at 1kHz\n");
    } else {
        printf("ERROR: LED timer init failed!\n");
    }
    
    // V2.4.1: Timer 1: Watchdog at 1Hz (checks every 1 second)
    bool watchdog_ok = add_repeating_timer_ms(-1000, watchdog_timer_callback, NULL, &watchdog_timer);
    printf("=== WATCHDOG TIMER: %s ===\n", watchdog_ok ? "SUCCESS" : "FAILED");
    
    if (watchdog_ok) {
        printf("Watchdog timer registered at 1Hz (separate hardware timer)\n");
    } else {
        printf("ERROR: Watchdog timer init failed!\n");
    }

    while (true) {
        while (true)
        {
            // get incoming command
            char command[64] = {0};  // Increased for rankbatch command - initialize to null bytes
            uint8_t i = 0;
            while (i < 64){
                uint8_t cmd_char = getchar_timeout_us(0);
                if (cmd_char != PICO_ERROR_TIMEOUT){
                    if (cmd_char == '\n'){
                        // Debug removed: printf("cmd %s\n", command);
                        break;
                    }
                    else if (cmd_char < 128){
                        command[i] = cmd_char;
                        i++;
                    }
                }

                // check power button
                if (power_button_held)	// wait for power button release
                {
                    if (!gpio_get(POWER_BTN))
                    {
                        power_button_held = false;	// button release
                        sleep_ms(250);	// short time for debounce
                    }
                }
                else if (gpio_get(POWER_BTN))	// power button just pressed, toggle state
                {
                    if (!gpio_get_out_level(DEV_OK)) {
                        device_on();
                        if(debug){
                            printf(" power on");
                        }
                    }
                    else {
                        device_off();
                        if(debug){
                            printf(" power off");
                        }
                    }
                    power_button_held = true;
                    sleep_ms(250);	// short time for debounce
                }
                
                // V2.4: Process ISR events while waiting for command input
                // Only ONE CYCLE_START event per cycle (75% less USB traffic than V2.3)
                if (isr_events.cycle_start) {
                    printf("CYCLE_START:%lu\n", isr_events.cycle_number);
                    isr_events.cycle_start = false;  // Clear event
                }
                
                if (isr_events.batch_complete) {
                    printf("BATCH_COMPLETE\n");
                    isr_events.batch_complete = false;
                }
            }

            switch (command[0]){

                // Device information
                case 'i':
                    if (command[1] == 'd'){
                        printf("%s %s\n", DEVICE, VERSION);
                        device_on();
                    }
                    else if (command[1] == 'v'){
                        printf("%s\n", VERSION);
                    }
                    else if (command[1] == 't'){
                        printf("%.2f\n", temp);
                        i2c_read_blocking(i2c0, TEMP_ADDR, temp_buffer, 2, false);
                        temp = temp_buffer[0] + ((temp_buffer[1] >> 5) * 0.125);
                    }
                    else if (command[1] == 'b'){
                        // Reboot to BOOTSEL mode for firmware updates
                        printf("%d", ACK);
                        if (debug){
                            printf(" rebooting to bootloader...\n");
                        }
                        sleep_ms(100);  // Give time for response to be sent
                        reset_usb_boot(0, 0);  // Reboot into BOOTSEL mode
                    }
                    else if (command[1] == 'x'){
                        // Debug: ISR event counter
                        printf("%d\n", ACK);
                        printf("CYCLE:%lu ACTIVE:%d\n", isr_events.cycle_number, led_sequencer.active);
                    }

                    else {
                        if (debug){
                            printf(" er\n");
                        }
                    }

                    break;

                // V2.4.1: Keepalive command for watchdog
                case 'k':
                    if (command[1] == 'a') {
                        // Update watchdog timestamp
                        watchdog_state.last_keepalive = time_us_64();
                        printf("%d", ACK);
                        if (debug) {
                            printf(" keepalive ok\n");
                        }
                    }
                    else {
                        printf("%d", NAK);
                        if (debug) {
                            printf(" er\n");
                        }
                    }
                    break;

                // Device control
                case 'd':
                    if (command[1] == 'o'){
                        device_off();
                        printf("%d", ACK);
                        if (debug){
                            printf(" fluidic stop & power off\n");
                        }
                    }
                    else if (command[1] == 'u') {
                        reset_usb_boot(0, 0);
                    }

                    else {
                        printf("%d", NAK);
                        if (debug){
                            printf(" er\n");
                        }
                    }
                    break;


                // LED on/off commands
                case 'l':
                    // Check for multi-LED command: lm:A,B,C,D
                    if (command[1] == 'm' && command[2] == ':'){
                        // Parse LED list from command
                        char led_list[8] = {0};  // Max 4 LEDs + separators
                        uint8_t led_count = 0;
                        uint8_t pos = 3;  // Start after "lm:"

                        while (pos < 32 && command[pos] != '\0' && command[pos] != '\n' && led_count < 8){
                            char ch = command[pos];
                            // Accept A, B, C, D (case insensitive) and commas
                            if (ch == 'A' || ch == 'a' || ch == 'B' || ch == 'b' ||
                                ch == 'C' || ch == 'c' || ch == 'D' || ch == 'd' || ch == ','){
                                led_list[led_count++] = ch;
                            }
                            // Debug removed: printf("pos=%d ch=%c\n", pos, command[pos]);

                            pos++;
                        }

                        if (led_multi_on(led_list, led_count)){
                            printf("%d", ACK);
                            if (debug){
                                printf(" multi led ok\n");
                            }
                        }
                        else {
                            printf("%d", NAK);
                            if (debug){
                                printf(" multi led er\n");
                            }
                        }
                    }
                    // Single LED command
                    else if (led_on(command[1])){
                        printf("%d", ACK);
                        if (debug){
                            printf(" ok\n");
                        }
                    }
                    else {
                        printf("%d", NAK);
                        if (debug){
                            printf(" er\n");
                        }
                    }
                    break;


                // LED brightness commands
                case 'b':
                    if (((command[2] > 47) && (command[2] < 58)) && ((command[3] > 47) && (command[3] < 58)) && ((command[4] > 47) && (command[4] < 58))){
                        char str_bright[3] = {command[2], command[3], command[4]};
                        uint8_t brightness = atoi(str_bright);
                        // Debug removed: printf("brightness val %c %d\n", command[1], brightness);
                        if (brightness > 255){
                            brightness = 255;
                        }
                        // Allow 0 to turn off LED
                        // Debug removed: printf("brightness led %c %d\n", command[1], brightness);
                        if (led_brightness(command[1], brightness) == brightness){
                            printf("%d", ACK);
                            if (debug){
                                printf(" ok\n");
                            }
                        }
                        else {
                            printf("%d", NAK);
                            if (debug){
                                printf(" er\n");
                            }
                        }
                    }
                    else if (command[1] == 'a' && command[2] == 't' && command[3] == 'c' && command[4] == 'h' && command[5] == ':'){
                        // Batch command: batch:AAA,BBB,CCC,DDD
                        // Parse all 4 LED values from CSV format
                        char str_a[4] = {0};
                        char str_b[4] = {0};
                        char str_c[4] = {0};
                        char str_d[4] = {0};

                        // Find comma positions
                        uint8_t pos = 6;  // Start after "batch:"
                        uint8_t field = 0;
                        uint8_t field_pos = 0;

                        while (pos < 32 && field < 4){
                            if (command[pos] == ',' || command[pos] == '\0' || command[pos] == '\n'){
                                field++;
                                field_pos = 0;
                                // Debug removed: printf("pos=%d ch=%c\n", pos, command[pos]);

                                pos++;
                            }
                            else if (command[pos] >= '0' && command[pos] <= '9'){
                                if (field == 0 && field_pos < 3) str_a[field_pos++] = command[pos];
                                else if (field == 1 && field_pos < 3) str_b[field_pos++] = command[pos];
                                else if (field == 2 && field_pos < 3) str_c[field_pos++] = command[pos];
                                else if (field == 3 && field_pos < 3) str_d[field_pos++] = command[pos];
                                // Debug removed: printf("pos=%d ch=%c\n", pos, command[pos]);

                                pos++;
                            }
                            else {
                                // Debug removed: printf("pos=%d ch=%c\n", pos, command[pos]);

                                pos++;
                            }
                        }

                        // Parse and apply all LED values
                        uint8_t val_a = atoi(str_a);
                        uint8_t val_b = atoi(str_b);
                        uint8_t val_c = atoi(str_c);
                        uint8_t val_d = atoi(str_d);

                        // Clamp to valid range
                        if (val_a > 255) val_a = 255;
                        if (val_b > 255) val_b = 255;
                        if (val_c > 255) val_c = 255;
                        if (val_d > 255) val_d = 255;

                        // Optimization: if all zeros, use fast turn-off path
                        if (val_a == 0 && val_b == 0 && val_c == 0 && val_d == 0){
                            led_on('x');  // Fast turn-off (just disable PWM)
                        }
                        else {
                            // Apply LED brightness values (all LEDs use independent PWM slices)
                            led_brightness('a', val_a);
                            led_brightness('b', val_b);
                            led_brightness('c', val_c);
                            led_brightness('d', val_d);
                        }

                        printf("%d", ACK);
                        if (debug){
                            printf(" batch ok\n");
                        }
                    }
                    break;
                // Rank LED sequence command
                case 'r':
                                    // NEW V2.1: Rankbatch command for batch intensity cycling
                if (command[1] == 'a' && command[2] == 'n' && command[3] == 'k' &&
                    command[4] == 'b' && command[5] == 'a' && command[6] == 't' &&
                    command[7] == 'c' && command[8] == 'h' && command[9] == ':'){
                    // Parse rankbatch:A,B,C,D,SETTLE,DARK,CYCLES
                    // Debug removed: printf("ENTER RANKBATCH HANDLER\n");
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

                    while (pos < 48 && command[pos] != '\0' && command[pos] != '\n'){
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

                    // Debug removed: printf("DEBUG: str_a='%s' str_b='%s' str_c='%s' str_d='%s'\n", ...);
                    // Debug removed: printf("DEBUG: str_settle='%s' str_dark='%s' str_cycles='%s'\n", ...);
                    // Debug removed: printf("PARSED: A=%d B=%d C=%d D=%d settle=%d dark=%d cycles=%d\n", ...);

                    if (int_a > 255) int_a = 255;
                    if (int_b > 255) int_b = 255;
                    if (int_c > 255) int_c = 255;
                    if (int_d > 255) int_d = 255;
                    if (settling_ms < 10) settling_ms = 15;
                    if (settling_ms > 1000) settling_ms = 1000;
                    if (dark_ms > 100) dark_ms = 100;
                    if (num_cycles < 1) num_cycles = 1;
                    if (num_cycles > 10000) num_cycles = 10000;

                    // V2.2: Use timer-based sequencer
                    rankbatch_start(int_a, int_b, int_c, int_d, settling_ms, dark_ms, num_cycles);
                    printf("%d", ACK);
                    if (debug){
                        printf(" rankbatch ok (timer-based)\n");
                    }
                }
                // V2.0 rank: command (backward compatibility)
                else if (command[1] == 'a' && command[2] == 'n' && command[3] == 'k' && command[4] == ':'){
                        char str_intensity[4] = {0};
                        char str_settling[5] = {0};
                        char str_dark[5] = {0};
                        uint8_t field = 0;
                        uint8_t field_pos = 0;
                        uint8_t pos = 5;
                        while (pos < 32 && command[pos] != '\0' && command[pos] != '\n'){
                            if (command[pos] == ','){
                                field++;
                                field_pos = 0;
                            }
                            else if (command[pos] >= '0' && command[pos] <= '9'){
                                if (field == 0 && field_pos < 3) str_intensity[field_pos++] = command[pos];
                                else if (field == 1 && field_pos < 4) str_settling[field_pos++] = command[pos];
                                else if (field == 2 && field_pos < 4) str_dark[field_pos++] = command[pos];
                            }
                            // Debug removed: printf("pos=%d ch=%c\n", pos, command[pos]);

                            pos++;
                        }
                        uint8_t intensity = atoi(str_intensity);
                        uint16_t settling_ms = atoi(str_settling);
                        uint16_t dark_ms = atoi(str_dark);
                        if (intensity > 255) intensity = 255;
                        if (settling_ms == 0) settling_ms = 35;
                        if (settling_ms > 1000) settling_ms = 1000;
                        if (dark_ms == 0) dark_ms = 5;
                        if (dark_ms > 100) dark_ms = 100;
                          bool result = led_rank_sequence(intensity, settling_ms, dark_ms);
                          if (result){
                            printf("%d", ACK);
                            if (debug){
                                printf(" rank ok\\n");
                            }
                          }
                        else {
                            printf("%d", NAK);
                            if (debug){
                                printf(" rank er\\n");
                            }
                        }
                    }
                    break;




                // Servo commands
                case 's':

                    if (command[1] == 's'){
                        move_servo(get_servo_duty(curr_s));
                        if (debug){
                            printf("s pos\n");
                        }
                        printf("%d", ACK);
                    }

                    else if (command[1] == 'p'){
                        move_servo(get_servo_duty(curr_p));
                        if (debug){
                            printf("p pos\n");
                        }
                        printf("%d", ACK);
                    }

                    else if (command[1] == 'e' && command[2] == 'r' && command[3] == 'v' && command[4] == 'o' && command[5] == '_' && command[6] == 's' && command[7] == 'p' && command[8] == 'e' && command[9] == 'e' && command[10] == 'd' && command[11] == ':'){
                        // Servo speed command: servo_speed:####
                        char str_speed[5] = {0};
                        uint8_t pos = 12;
                        uint8_t idx = 0;

                        while (pos < 32 && idx < 4 && command[pos] >= '0' && command[pos] <= '9'){
                            str_speed[idx++] = command[pos++];
                        }

                        uint16_t speed = atoi(str_speed);

                        // Clamp to safe range
                        if (speed < MIN_SERVO_SPEED) speed = MIN_SERVO_SPEED;
                        if (speed > MAX_SERVO_SPEED) speed = MAX_SERVO_SPEED;

                        servo_pulse_duration = speed;
                        printf("%d", ACK);
                        if (debug){
                            printf(" servo speed set to %d ms\n", servo_pulse_duration);
                        }
                    }

                    else if (command[1] == 'v'){
                        char str_s[3] = {command[2], command[3], command[4]};
                        curr_s = atoi(str_s);
                        char str_p[3] = {command[5], command[6], command[7]};
                        curr_p = atoi(str_p);
                        printf("%d", ACK);
                        if (debug){
                            printf("s/p set\n");
                        }
                    }

                    else if (command[1] == 'f'){
                        if (servo_flash(curr_s, curr_p)){
                            printf("%d", ACK);
                            if (debug){
                                printf("flashed\n");
                            }
                        }
                        else{
                            printf("%d", NAK);
                            if (debug){
                                printf(" er\n");
                            }
                        }

                    }

                    else if (command[1] == 'r'){
                        servo_read();
                    }
                    
                    // V2.2: Stop command - halt rankbatch sequence
                    else if (command[1] == 't' && command[2] == 'o' && command[3] == 'p'){
                        rankbatch_stop();
                        printf("%d", ACK);
                        if (debug){
                            printf(" stop ok\n");
                        }
                    }

                    else{
                        printf("%d", NAK);
                        if (debug){
                            printf(" er\n");
                        }

                    }

                    break;
            }
        }
        
        // V2.4: Process ISR events (safe printf from main loop, not ISR)
        // Only ONE CYCLE_START event per cycle (75% less USB traffic than V2.3)
        if (isr_events.cycle_start) {
            printf("CYCLE_START:%lu\n", isr_events.cycle_number);
            isr_events.cycle_start = false;  // Clear event
        }
        
        if (isr_events.batch_complete) {
            printf("BATCH_COMPLETE\n");
            isr_events.batch_complete = false;  // Clear event
        }
        
        // V2.2: Make main loop non-blocking - allows timer ISR to work smoothly
        sleep_us(100);
    }

    return 0;
}


/********************************************************
*
* SETUP FUNCTIONS
*
*/


/*** Function to set up all the GPIO ***/

void affinite_setup (void){

    // PICO DEBUG LED
    gpio_init(BOARD_LED);
    gpio_set_dir(BOARD_LED, GPIO_OUT);

    // SERVO PWM
    pwm_servo_setup();

    // LED PWM SETUP
    led_setup();

    // I2C BUS 0 SETUP
    i2c_init(i2c0, 100 * 1000);
    gpio_set_function(I2C0_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C0_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C0_SDA);
    gpio_pull_up(I2C0_SCL);

    // DEVICE SETUP
    device_setup();

}


/*** Function to ensure s and p values saved in flash ***/

bool check_flash (void){

    // read the current flash values

    curr_s = *(FLASH_READ_ADDRESS);
    curr_p = *(FLASH_READ_ADDRESS + 1);
    uint8_t curr_servo [2] = {curr_s, curr_p};

    servo_read();

    bool values_ok = true;

    for (uint8_t i = 0; i < 2; i++){
        if ((curr_servo[i] > MAX_DEG) || (curr_servo[i] < MIN_DEG)){
            values_ok = false;
        }
    }
    if (abs(curr_s - curr_p) != 90)
        values_ok = false;

    if (!values_ok){
        curr_s = DEFAULT_S;
        curr_p = DEFAULT_P;
        servo_flash(DEFAULT_S, DEFAULT_P);
    }

    return values_ok;

}


/********************************************************
*
* LED FUNCTIONS
*
*/

/*** Function to set up pwm for servo motor ***/

void led_setup (void){

    // Get actual hardware PWM slices from GPIOs
    uint slice_a = pwm_gpio_to_slice_num(LED_A_CTRL);
    uint slice_b = pwm_gpio_to_slice_num(LED_B_CTRL);
    uint slice_c = pwm_gpio_to_slice_num(LED_C_CTRL);
    uint slice_d = pwm_gpio_to_slice_num(LED_D_CTRL);

    gpio_set_function(LED_A_CTRL, GPIO_FUNC_PWM);
    pwm_set_clkdiv(slice_a, LED_PWM_DIV);
    pwm_set_phase_correct(slice_a, false);
    pwm_set_wrap(slice_a, LED_WRAP);

    gpio_set_function(LED_B_CTRL, GPIO_FUNC_PWM);
    pwm_set_clkdiv(slice_b, LED_PWM_DIV);
    pwm_set_phase_correct(slice_b, false);
    pwm_set_wrap(slice_b, LED_WRAP);

    gpio_set_function(LED_C_CTRL, GPIO_FUNC_PWM);
    pwm_set_clkdiv(slice_c, LED_PWM_DIV);
    pwm_set_phase_correct(slice_c, false);
    pwm_set_wrap(slice_c, LED_WRAP);

    gpio_set_function(LED_D_CTRL, GPIO_FUNC_PWM);
    pwm_set_clkdiv(slice_d, LED_PWM_DIV);
    pwm_set_phase_correct(slice_d, false);
    pwm_set_wrap(slice_d, LED_WRAP);

    // Initialize all LEDs to OFF state to prevent startup bug
    pwm_set_chan_level(slice_a, pwm_gpio_to_channel(LED_A_CTRL), 0);
    pwm_set_chan_level(slice_b, pwm_gpio_to_channel(LED_B_CTRL), 0);
    pwm_set_chan_level(slice_c, pwm_gpio_to_channel(LED_C_CTRL), 0);
    pwm_set_chan_level(slice_d, pwm_gpio_to_channel(LED_D_CTRL), 0);

}

/*** Function to turn on/off LED based on command ***/

bool led_on (char ch_led){

    bool result = false;

    // Get actual hardware PWM slices from GPIOs
    uint slice_a = pwm_gpio_to_slice_num(LED_A_CTRL);
    uint slice_b = pwm_gpio_to_slice_num(LED_B_CTRL);
    uint slice_c = pwm_gpio_to_slice_num(LED_C_CTRL);
    uint slice_d = pwm_gpio_to_slice_num(LED_D_CTRL);
    uint chan_a = pwm_gpio_to_channel(LED_A_CTRL);
    uint chan_b = pwm_gpio_to_channel(LED_B_CTRL);
    uint chan_c = pwm_gpio_to_channel(LED_C_CTRL);
    uint chan_d = pwm_gpio_to_channel(LED_D_CTRL);

    // Disable all LEDs first (V1.0 behavior)
    pwm_set_chan_level(slice_a, chan_a, 0);
    pwm_set_chan_level(slice_b, chan_b, 0);
    pwm_set_chan_level(slice_c, chan_c, 0);
    pwm_set_chan_level(slice_d, chan_d, 0);
    sleep_ms(3);
    pwm_set_enabled(slice_a, false);
    pwm_set_enabled(slice_b, false);
    pwm_set_enabled(slice_c, false);
    pwm_set_enabled(slice_d, false);

    // Then turn on the requested LED
    switch (ch_led){

        case 'a':
            pwm_set_chan_level(slice_a, chan_a, led_a_level);
            pwm_set_enabled(slice_a, true);

            if (debug){
                printf("led a on\n");
            }
            result = true;
            break;

        case 'b':
            pwm_set_chan_level(slice_b, chan_b, led_b_level);
            pwm_set_enabled(slice_b, true);

            if (debug){
                printf("led b on\n");
            }
            result = true;
            break;

        case 'c':
            pwm_set_chan_level(slice_c, chan_c, led_c_level);
            pwm_set_enabled(slice_c, true);

            if (debug){
                printf("led c on\n");
            }
            result = true;
            break;

        case 'd':
            pwm_set_chan_level(slice_d, chan_d, led_d_level);
            pwm_set_enabled(slice_d, true);

            if (debug){
                printf("led d on\n");
            }
            result = true;
            break;

        case 'x':
            // Turn off all LEDs (all slices are now independent)
            pwm_set_chan_level(slice_a, chan_a, 0);
            pwm_set_enabled(slice_a, false);

            pwm_set_chan_level(slice_b, chan_b, 0);
            pwm_set_enabled(slice_b, false);

            pwm_set_chan_level(slice_c, chan_c, 0);
            pwm_set_enabled(slice_c, false);

            pwm_set_chan_level(slice_d, chan_d, 0);
            pwm_set_enabled(slice_d, false);

            if (debug){
                printf("leds off\n");
            }
            result = true;
            break;

        //if command not recognized, all off

        default:
            if (debug){
                printf("bad cmd\n");
            }
            break;
    }

    return result;
}


/*** Function to turn on multiple LEDs simultaneously ***/

bool led_multi_on(const char* leds, uint8_t count){

    bool result = false;

    // Get actual hardware PWM slices from GPIOs
    uint slice_a = pwm_gpio_to_slice_num(LED_A_CTRL);
    uint slice_b = pwm_gpio_to_slice_num(LED_B_CTRL);
    uint slice_c = pwm_gpio_to_slice_num(LED_C_CTRL);
    uint slice_d = pwm_gpio_to_slice_num(LED_D_CTRL);
    uint chan_a = pwm_gpio_to_channel(LED_A_CTRL);
    uint chan_b = pwm_gpio_to_channel(LED_B_CTRL);
    uint chan_c = pwm_gpio_to_channel(LED_C_CTRL);
    uint chan_d = pwm_gpio_to_channel(LED_D_CTRL);

    // Disable all LEDs first for clean start
    pwm_set_chan_level(slice_a, chan_a, 0);
    pwm_set_chan_level(slice_b, chan_b, 0);
    pwm_set_chan_level(slice_c, chan_c, 0);
    pwm_set_chan_level(slice_d, chan_d, 0);
    sleep_ms(3);
    pwm_set_enabled(slice_a, false);
    pwm_set_enabled(slice_b, false);
    pwm_set_enabled(slice_c, false);
    pwm_set_enabled(slice_d, false);

    // Turn on requested LEDs (each on independent slice)
    for (uint8_t i = 0; i < count; i++){
        switch (leds[i]){
            case 'A':
            case 'a':
                pwm_set_chan_level(slice_a, chan_a, led_a_level);
                pwm_set_enabled(slice_a, true);
                result = true;
                if (debug){
                    printf("multi led a on\n");
                }
                break;

            case 'B':
            case 'b':
                pwm_set_chan_level(slice_b, chan_b, led_b_level);
                pwm_set_enabled(slice_b, true);
                result = true;
                if (debug){
                    printf("multi led b on\n");
                }
                break;

            case 'C':
            case 'c':
                pwm_set_chan_level(slice_c, chan_c, led_c_level);
                pwm_set_enabled(slice_c, true);
                result = true;
                if (debug){
                    printf("multi led c on\n");
                }
                break;

            case 'D':
            case 'd':
                pwm_set_chan_level(slice_d, chan_d, led_d_level);
                pwm_set_enabled(slice_d, true);
                result = true;
                if (debug){
                    printf("multi led d on\n");
                }
                break;

            default:
                // Skip invalid characters (like commas)
                break;
        }
    }

    return result;
}


/*** Function to set LED brightness on channel ***/

uint8_t led_brightness (char ch_led, uint8_t set_bright){

    // convert intensity 0-255 brightness to duty cycle and wrap
    float duty = set_bright / 255.0;
    uint16_t level = (uint16_t)(duty * LED_WRAP);
    // Debug removed: printf("level = %d\n", level);
    uint8_t current_brightness = 0;

    // Get actual hardware PWM slices from GPIOs
    uint slice_a = pwm_gpio_to_slice_num(LED_A_CTRL);
    uint slice_b = pwm_gpio_to_slice_num(LED_B_CTRL);
    uint slice_c = pwm_gpio_to_slice_num(LED_C_CTRL);
    uint slice_d = pwm_gpio_to_slice_num(LED_D_CTRL);
    uint chan_a = pwm_gpio_to_channel(LED_A_CTRL);
    uint chan_b = pwm_gpio_to_channel(LED_B_CTRL);
    uint chan_c = pwm_gpio_to_channel(LED_C_CTRL);
    uint chan_d = pwm_gpio_to_channel(LED_D_CTRL);

    switch (ch_led){

        case 'a':
            led_a_level = level;
            pwm_set_chan_level(slice_a, chan_a, led_a_level);
            current_brightness = set_bright;
            break;

        case 'b':
            led_b_level = level;
            pwm_set_chan_level(slice_b, chan_b, led_b_level);
            current_brightness = set_bright;
            break;

        case 'c':
            led_c_level = level;
            pwm_set_chan_level(slice_c, chan_c, led_c_level);
            current_brightness = set_bright;
            break;

        case 'd':
            led_d_level = level;
            pwm_set_chan_level(slice_d, chan_d, led_d_level);
            current_brightness = set_bright;
            break;

        //if no valid channel

        default:
            break;
    }

    return current_brightness;
}


/********************************************************
*
* SERVO FUNCTIONS
*
*/

/*** Function to set up pwm for servo motor ***/

void pwm_servo_setup (void){

    gpio_set_function(SERVO_PIN, GPIO_FUNC_PWM);
    pwm_set_clkdiv(SERVO_SLICE, SERVO_PWM_DIV);
    pwm_set_phase_correct(SERVO_SLICE, false);
    pwm_set_wrap(SERVO_SLICE, SERVO_WRAP);

}


/*** Function to run pwm and move servo given duty cycle ***/

void move_servo(double duty){

    uint16_t level = (uint16_t)(duty * SERVO_WRAP);
    pwm_set_chan_level(SERVO_SLICE, SERVO_CH, level);
    pwm_set_enabled(SERVO_SLICE, true);
    sleep_ms(servo_pulse_duration);  // Variable duration for calibration sweeps
    pwm_set_chan_level(SERVO_SLICE, SERVO_CH, 0);
    sleep_ms(100);
    pwm_set_enabled(SERVO_SLICE, false);
}


/*** Function to convert servo degrees to duty cycle ***/

double get_servo_duty (uint8_t deg){
    uint8_t duty = 0;
    if (deg < MIN_DEG)
        deg = MIN_DEG;
    if (deg > MAX_DEG)
        deg = MAX_DEG;
    duty = (((double)deg / 180.0) * (11.5-3.0)) + 3.0;
    return (double) (duty * 0.01);
}


/*** Function to write s and p values to flash ***/

bool servo_flash (uint8_t s, uint8_t p){

    // set up default value buffer

    uint8_t default_buf [FLASH_PAGE_SIZE];
    default_buf[0] = s;
    default_buf[1] = p;

    uint32_t ints = 0;

    // erase and reprogram the flash sector with default values

    ints = save_and_disable_interrupts();
    flash_range_erase(FLASH_WRITE_OFFSET, FLASH_SECTOR_SIZE);
    flash_range_program(FLASH_WRITE_OFFSET, (uint8_t *)default_buf, FLASH_PAGE_SIZE);
    restore_interrupts(ints);

    // check values match
    return ((*(FLASH_READ_ADDRESS) == s) && (*(FLASH_READ_ADDRESS + 1) == p));

}

/*** Function to get saved s and p values from flash ***/

void servo_read (void){

    printf("%03d,%03d\n", *(FLASH_READ_ADDRESS), *(FLASH_READ_ADDRESS + 1));

}


/********************************************************
*
* DEVICE FUNCTIONS
*
*/

/*** Function to set up device GPIO ***/

void device_setup (void){

    gpio_init(DEV_OK);
    gpio_set_dir(DEV_OK, GPIO_OUT);
	// power button
    gpio_init(POWER_BTN);
    gpio_set_dir(POWER_BTN, GPIO_IN);

    // TEMP SENSOR SETUP BUS 0
    i2c_read_blocking(i2c0, TEMP_ADDR, temp_buffer, 2, false); // Perform first read to start sensor
    i2c_read_blocking(i2c0, TEMP_ADDR, temp_buffer, 2, false); // Load second read to temp buffer
    temp = temp_buffer[0] + ((temp_buffer[1] >> 5) * 0.125);

    // Set up I/O expander output port 0
    uint8_t exp_config[2] = {CONFIG_PORT_0, 0x00};
    i2c_write_blocking(i2c0, EXP_ADDR, exp_config, 2, false);
    i2c_write_blocking(i2c0, EXP_ADDR, out_port_zero, 2, false);
}


/*** Function to handle enables at power on ***/

void device_on (void){
    gpio_put (DEV_OK, 1);
}


/*** Function to handle disables at power off ***/

void device_off (void){
    led_on('x');
    gpio_put (DEV_OK, 0);
}

bool led_rank_sequence(uint8_t intensity, uint16_t settling_ms, uint16_t dark_ms) {
    printf("START\n");

    // LED A
    led_brightness('a', intensity);
    led_on('a');
    sleep_ms(settling_ms);
    led_on('x');
    sleep_ms(dark_ms);

    // LED B
    led_brightness('b', intensity);
    led_on('b');
    sleep_ms(settling_ms);
    led_on('x');
    sleep_ms(dark_ms);

    // LED C
    led_brightness('c', intensity);
    led_on('c');
    sleep_ms(settling_ms);
    led_on('x');
    sleep_ms(dark_ms);

    // LED D
    led_brightness('d', intensity);
    led_on('d');
    sleep_ms(settling_ms);
    led_on('x');

    printf("END\n");
}










/********************************************************
*
* V2.4.1: WATCHDOG TIMER CALLBACK (Runs at 1Hz on separate timer)
*
*/

bool watchdog_timer_callback(struct repeating_timer *t) {
    // This runs on Timer 1 at 1Hz (every 1 second)
    // Completely independent from LED sequencer (Timer 0)
    // Zero timing impact on LED operations
    
    if (!watchdog_state.enabled || !led_sequencer.active) {
        return true;  // Keep timer running
    }
    
    // Check if keepalive timeout exceeded
    uint64_t now = time_us_64();
    if ((now - watchdog_state.last_keepalive) > watchdog_state.timeout_us) {
        // Timeout - turn off all LEDs by setting intensities to zero
        // ISR will naturally apply these on next cycle
        led_sequencer.intensities[0] = 0;
        led_sequencer.intensities[1] = 0;
        led_sequencer.intensities[2] = 0;
        led_sequencer.intensities[3] = 0;
        
        watchdog_state.enabled = false;  // Disable further checks
        
        // Safe to printf from this timer since it's slow (1Hz) and independent
        printf("WATCHDOG_TIMEOUT\n");
    }
    
    return true;  // Keep timer running
}


/********************************************************
*
* V2.2: HARDWARE TIMER ISR CALLBACK (Runs at 1kHz)
*
*/

bool led_sequencer_callback(struct repeating_timer *t) {
    static uint32_t isr_call_count = 0;
    isr_call_count++;
    
    // REMOVED: Debug marker 0xFF can interfere with event processing
    // Main loop now handles empty event queue gracefully
    
    if (!led_sequencer.active) {
        return true;  // Keep timer running
    }
    
    // CRITICAL: Increment timer ONCE per ISR call to prevent wrapping issues
    // Cached locally to ensure consistent value throughout this ISR execution
    led_sequencer.timer_ms++;
    uint32_t current_time = led_sequencer.timer_ms;
    
    // ROBUST: Handle timer wraparound (49.7 days) gracefully
    // Use safe subtraction that works across wraparound boundary
    uint32_t elapsed = current_time - led_sequencer.phase_start_ms;
    
    switch (led_sequencer.phase) {
        case 0:  // LED_ON - Turn on LED at t=1ms, send READY at t=50ms
            // CRITICAL FIX: Use >= instead of == to handle ISR delays robustly
            // If ISR gets interrupted (flash write, etc), elapsed could jump 0→2, missing == 1
            if (elapsed >= 1) {  // Turn on LED on first millisecond after phase start (or later if delayed)
                // CRITICAL: Skip LED if intensity is 0 (prevents PWM glitch and wasted READY signal)
                uint8_t intensity = led_sequencer.intensities[led_sequencer.current_led];
                
                if (intensity > 0) {
                    // Direct PWM control (ISR-safe, no sleep_ms)
                    const uint8_t led_pins[4] = {LED_A_CTRL, LED_B_CTRL, LED_C_CTRL, LED_D_CTRL};
                    uint8_t pin = led_pins[led_sequencer.current_led];
                    uint slice = pwm_gpio_to_slice_num(pin);
                    uint chan = pwm_gpio_to_channel(pin);
                    uint16_t level = (intensity * LED_WRAP) / 255;
                    pwm_set_chan_level(slice, chan, level);
                    pwm_set_enabled(slice, true);
                    
                    // V2.4: Send CYCLE_START only for LED_A (first LED of cycle)
                    // Python will use fixed timing offsets from this event
                    if (led_sequencer.current_led == 0) {
                        isr_events.cycle_start = true;
                        isr_events.cycle_number = led_sequencer.current_cycle;
                    }
                    
                    // LED is now ON - transition to SETTLE phase
                    // ATOMIC: Update phase_start_ms BEFORE phase to prevent race
                    led_sequencer.phase_start_ms = current_time;
                    led_sequencer.phase = 1;
                }
                else {
                    // Intensity=0, skip to next LED immediately
                    led_sequencer.phase_start_ms = current_time;
                    led_sequencer.phase = 3;  // Skip to NEXT_LED phase
                }
            }
            break;
            
        case 1:  // SETTLE - Wait for settle time (250ms is sufficient, proven by single-command mode)
            if (elapsed >= led_sequencer.settle_ms) {
                // Turn off LED using correct GPIO pins
                const uint8_t led_pins[4] = {LED_A_CTRL, LED_B_CTRL, LED_C_CTRL, LED_D_CTRL};
                pwm_set_gpio_level(led_pins[led_sequencer.current_led], 0);
                
                // ATOMIC: Update phase_start_ms BEFORE phase
                led_sequencer.phase_start_ms = current_time;
                led_sequencer.phase = 2;
            }
            break;
            
        case 2:  // DARK - Wait for dark period
            if (elapsed >= led_sequencer.dark_ms) {
                // Move to next LED
                led_sequencer.current_led++;
                if (led_sequencer.current_led >= 4) {
                    led_sequencer.current_led = 0;
                    led_sequencer.current_cycle++;
                    
                    // CRITICAL: Check completion BEFORE signaling to main loop
                    // Prevents race where main reads cycle_num but batch isn't done yet
                    if (led_sequencer.current_cycle >= led_sequencer.total_cycles) {
                        // ATOMIC: Set batch_complete BEFORE deactivating
                        // Main loop will see batch_complete and know it's truly finished
                        isr_events.batch_complete = true;
                        led_sequencer.active = false;
                        return true;
                    }
                    
                    // Only signal cycle_number if batch continues (not on final cycle)
                    isr_events.cycle_number = led_sequencer.current_cycle;
                }
                
                // ATOMIC: Update phase_start_ms BEFORE phase
                led_sequencer.phase_start_ms = current_time;
                led_sequencer.phase = 0;
            }
            break;
    }
    
    return true;  // Keep timer running
}

/*** V2.2: Start timer-based rankbatch sequence ***/
void rankbatch_start(uint8_t ia, uint8_t ib, uint8_t ic, uint8_t id, 
                     uint16_t settle_ms, uint16_t dark_ms, uint16_t n_cycles) {
    // Debug removed: printf("DEBUG: rankbatch_start called\n");
    
    // CRITICAL: If already running, stop first to prevent state corruption
    if (led_sequencer.active) {
        rankbatch_stop();
        sleep_ms(5);  // Allow ISR to complete current cycle
    }
    
    // CRITICAL SECTION: Disable interrupts while configuring sequencer
    // Prevents ISR from reading partially-updated state
    uint32_t ints = save_and_disable_interrupts();
    
    // V2.4: Clear event flags to prevent stale events from previous batch
    isr_events.cycle_start = false;
    isr_events.cycle_number = 0;
    isr_events.batch_complete = false;
    
    // Configure sequencer
    led_sequencer.intensities[0] = ia;
    led_sequencer.intensities[1] = ib;
    led_sequencer.intensities[2] = ic;
    led_sequencer.intensities[3] = id;
    led_sequencer.settle_ms = settle_ms;
    led_sequencer.dark_ms = dark_ms;
    led_sequencer.total_cycles = n_cycles;
    led_sequencer.current_cycle = 0;
    led_sequencer.current_led = 0;
    led_sequencer.timer_ms = 0;
    led_sequencer.phase = 0;
    led_sequencer.phase_start_ms = 0;
    
    // Note: LED brightness set dynamically in ISR based on intensities array
    
    // CRITICAL: Activate sequencer LAST (atomic write to single bool)
    // Once active=true, ISR can start processing immediately
    led_sequencer.active = true;
    
    restore_interrupts(ints);
    
    // V2.4.1: Enable watchdog (runs on separate Timer 1)
    watchdog_state.enabled = true;
    watchdog_state.last_keepalive = time_us_64();
    
    printf("BATCH_START\n");
    // gpio_put(BOARD_LED, 1);  // Skip board LED - causes crashes
    // Debug removed: printf("DEBUG: active=%d timer_ms=%lu\n", led_sequencer.active, led_sequencer.timer_ms);
    // Debug removed: printf("DEBUG: rankbatch_start complete\n");
}

/*** V2.2: Stop rankbatch sequence ***/
void rankbatch_stop(void) {
    // CRITICAL SECTION: Ensure clean shutdown
    uint32_t ints = save_and_disable_interrupts();
    
    led_sequencer.active = false;
    
    // Turn off all LEDs
    pwm_set_gpio_level(LED_A_CTRL, 0);
    pwm_set_gpio_level(LED_B_CTRL, 0);
    pwm_set_gpio_level(LED_C_CTRL, 0);
    pwm_set_gpio_level(LED_D_CTRL, 0);
    
    restore_interrupts(ints);
    
    // V2.4.1: Disable watchdog
    watchdog_state.enabled = false;
    
    printf("BATCH_STOPPED\n");
}

/*** Function to execute LED ranking with batch intensities and cycle counting ***/

bool led_rank_batch_cycles(uint8_t int_a, uint8_t int_b, uint8_t int_c, uint8_t int_d,
                           uint16_t settling_ms, uint16_t dark_ms, uint16_t num_cycles){

    led_brightness('a', int_a);
    led_brightness('b', int_b);
    led_brightness('c', int_c);
    led_brightness('d', int_d);

    printf("BATCH_START\n");

    char channels[4] = {'a', 'b', 'c', 'd'};
    uint8_t intensities[4] = {int_a, int_b, int_c, int_d};

    for (uint16_t cycle = 0; cycle < num_cycles; cycle++){
        printf("CYCLE:%d\n", cycle + 1);

        for (uint8_t i = 0; i < 4; i++){
            char ch = channels[i];
            uint8_t intensity = intensities[i];

            if (intensity == 0){
                printf("%c:SKIP\n", ch);
                continue;
            }

            if (!led_on(ch)){
                if (debug){
                    printf("rankbatch led_on failed %c\n", ch);
                }
                led_on('x');
                return false;
            }

            printf("%c:READY\n", ch);
            sleep_ms(settling_ms);
            printf("%c:READ\n", ch);
            printf("%c:DONE\n", ch);

            if (i < 3){
                led_on('x');
                if (dark_ms > 0){
                    sleep_ms(dark_ms);
                }
            }
        }

        printf("CYCLE_END:%d\n", cycle + 1);

        if (cycle < num_cycles - 1 && dark_ms > 0){
            led_on('x');
            sleep_ms(dark_ms);
        }
    }

    led_on('x');
    printf("BATCH_END\n");

    return true;
}
