cmake_minimum_required(VERSION 3.13)

# Include Pico SDK
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

# Project name
project(affinite_p4spr C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Skip picotool (not needed for .uf2 creation)
set(PICO_NO_PICOTOOL 1)

# Initialize the Pico SDK
pico_sdk_init()

if (TARGET tinyusb_device)
    add_executable(affinite_p4spr
            affinite_p4spr.c
            )

    # pull in common dependencies
    target_link_libraries(affinite_p4spr pico_stdlib hardware_gpio hardware_pwm hardware_i2c)

    # enable usb output, disable uart output
    pico_enable_stdio_usb(affinite_p4spr 1)
    pico_enable_stdio_uart(affinite_p4spr 0)

    # create map/bin/hex/uf2 file etc.
    pico_add_extra_outputs(affinite_p4spr)

elseif(PICO_ON_DEVICE)
    message(WARNING "not building affinite because TinyUSB submodule is not initialized in the SDK")
endif()
