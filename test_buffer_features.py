"""Explore USB4000 buffering capabilities for batch spectrum acquisition."""
import seabreeze
seabreeze.use('cseabreeze')

from seabreeze.spectrometers import Spectrometer, list_devices
import time
import numpy as np

# Connect
spec = Spectrometer(list_devices()[0])
print(f"Connected to: {spec.model}\n")

# Explore data_buffer feature
print("=== DATA BUFFER FEATURE ===")
if spec.features.get('data_buffer'):
    data_buffers = spec.features['data_buffer']
    print(f"Number of data buffer instances: {len(data_buffers)}")

    if data_buffers:
        buffer = data_buffers[0]
        print(f"Buffer type: {type(buffer)}")
        print(f"Buffer methods: {[m for m in dir(buffer) if not m.startswith('_')]}")

        # Try to get buffer info
        try:
            if hasattr(buffer, 'get_buffer_capacity'):
                capacity = buffer.get_buffer_capacity()
                print(f"  Buffer capacity: {capacity}")
        except Exception as e:
            print(f"  Could not get capacity: {e}")

        try:
            if hasattr(buffer, 'get_number_of_elements'):
                elements = buffer.get_number_of_elements()
                print(f"  Number of elements: {elements}")
        except Exception as e:
            print(f"  Could not get elements: {e}")

# Explore fast_buffer feature
print("\n=== FAST BUFFER FEATURE ===")
if spec.features.get('fast_buffer'):
    fast_buffers = spec.features['fast_buffer']
    print(f"Number of fast buffer instances: {len(fast_buffers)}")

    if fast_buffers:
        fast_buffer = fast_buffers[0]
        print(f"Fast buffer type: {type(fast_buffer)}")
        print(f"Fast buffer methods: {[m for m in dir(fast_buffer) if not m.startswith('_')]}")

# Explore continuous_strobe (may relate to continuous acquisition)
print("\n=== CONTINUOUS STROBE FEATURE ===")
if spec.features.get('continuous_strobe'):
    cont_strobes = spec.features['continuous_strobe']
    print(f"Number of continuous strobe instances: {len(cont_strobes)}")
    if cont_strobes:
        print(f"Type: {type(cont_strobes[0])}")
        print(f"Methods: {[m for m in dir(cont_strobes[0]) if not m.startswith('_')]}")

# Explore acquisition_delay
print("\n=== ACQUISITION DELAY FEATURE ===")
if spec.features.get('acquisition_delay'):
    acq_delays = spec.features['acquisition_delay']
    print(f"Number of acquisition delay instances: {len(acq_delays)}")
    if acq_delays:
        delay = acq_delays[0]
        print(f"Type: {type(delay)}")
        print(f"Methods: {[m for m in dir(delay) if not m.startswith('_')]}")

        try:
            if hasattr(delay, 'get_acquisition_delay_micros'):
                current_delay = delay.get_acquisition_delay_micros()
                print(f"  Current delay: {current_delay}μs")
        except Exception as e:
            print(f"  Could not get delay: {e}")

# Check raw USB access (might allow custom bulk transfers)
print("\n=== RAW USB ACCESS ===")
if spec.features.get('raw_usb_bus_access'):
    usb_access = spec.features['raw_usb_bus_access']
    print(f"Number of USB access instances: {len(usb_access)}")
    if usb_access:
        print(f"Type: {type(usb_access[0])}")
        print(f"Methods: {[m for m in dir(usb_access[0]) if not m.startswith('_')]}")

# Test continuous acquisition if available
print("\n=== TESTING BUFFERED ACQUISITION ===")

# Set short integration time
spec.integration_time_micros(1000)  # 1ms
time.sleep(0.1)

# Try to use buffer if available
if spec.features.get('data_buffer') and spec.features['data_buffer']:
    buffer = spec.features['data_buffer'][0]
    print("\nAttempting buffered acquisition...")

    # Try different buffer methods
    for method_name in ['clear', 'enable', 'start', 'get_buffering_enable',
                        'set_buffering_enable', 'get_consecutive_sample_count']:
        if hasattr(buffer, method_name):
            print(f"  Found method: {method_name}()")
            try:
                # Try calling getter methods
                if method_name.startswith('get'):
                    result = getattr(buffer, method_name)()
                    print(f"    Result: {result}")
            except Exception as e:
                print(f"    Error calling: {e}")

spec.close()
print("\n=== Exploration Complete ===")
