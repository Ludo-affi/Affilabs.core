"""
Interactive Detector and LED Control Test

Shows live detector readings and provides control over:
- Individual LED intensities (A, B, C, D)
- Integration time
- Real-time spectrum display

Controls:
- a/A: LED A intensity (decrease/increase)
- b/B: LED B intensity (decrease/increase)
- c/C: LED C intensity (decrease/increase)
- d/D: LED D intensity (decrease/increase)
- t/T: Integration time (decrease/increase)
- 0: Turn all LEDs off
- r: Reset all LEDs to 50%
- q: Quit
"""

import time
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Add parent directory to path
sys.path.insert(0, ".")

from affilabs.core.hardware_manager import HardwareManager
from affilabs.utils.detector_factory import create_detector

print("=" * 80)
print("INTERACTIVE DETECTOR & LED CONTROL TEST")
print("=" * 80)
print()

# Initialize hardware
print("Initializing hardware...")
hw_mgr = HardwareManager()
hw_mgr._connect_controller()

if not hw_mgr._ctrl_raw:
    print("❌ Failed to connect to controller")
    sys.exit(1)

print(f"✓ Controller: {hw_mgr._ctrl_raw.name}")

# Connect to Phase Photonics detector using factory
print("Connecting to Phase Photonics detector...")
detector = create_detector(app=None, config={})
if detector is None:
    print("❌ Failed to connect to Phase Photonics detector")
    sys.exit(1)

detector_type = type(detector).__name__
print(f"✓ Detector: {detector_type}")
if hasattr(detector, 'serial_number'):
    print(f"  Serial: {detector.serial_number}")
print()

# Get references to controller
ctrl = hw_mgr.ctrl  # HAL-wrapped controller

# Enable all LED channels (CRITICAL: must do this before set_batch_intensities works)
print("Enabling LED channels...")
for channel in ['a', 'b', 'c', 'd']:
    ctrl.turn_on_channel(channel)
print("✓ All LED channels enabled")
print()

# Initial settings
led_intensities = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
integration_time = 10  # ms
running = True

def set_leds():
    """Apply current LED intensities"""
    ctrl.set_batch_intensities(
        led_intensities['A'], 
        led_intensities['B'], 
        led_intensities['C'], 
        led_intensities['D']
    )
    
def update_integration_time():
    """Apply current integration time"""
    detector.set_integration(integration_time)

def get_spectrum():
    """Get current detector reading"""
    try:
        spectrum = detector.read_intensity()
        if spectrum is not None and len(spectrum) > 0:
            return spectrum
    except:
        pass
    return None

def print_status():
    """Print current settings and detector reading"""
    spectrum = get_spectrum()
    
    print("\033[H\033[J")  # Clear screen
    print("=" * 80)
    print("DETECTOR & LED CONTROL - LIVE")
    print("=" * 80)
    print()
    
    print("LED INTENSITIES:")
    print(f"  A: {led_intensities['A']:3d}/255  {'█' * (led_intensities['A'] // 10)}")
    print(f"  B: {led_intensities['B']:3d}/255  {'█' * (led_intensities['B'] // 10)}")
    print(f"  C: {led_intensities['C']:3d}/255  {'█' * (led_intensities['C'] // 10)}")
    print(f"  D: {led_intensities['D']:3d}/255  {'█' * (led_intensities['D'] // 10)}")
    print()
    
    print(f"INTEGRATION TIME: {integration_time} ms")
    print()
    
    if spectrum is not None:
        max_val = np.max(spectrum)
        mean_val = np.mean(spectrum)
        print("DETECTOR READING:")
        print(f"  Max:  {max_val:6.0f} counts")
        print(f"  Mean: {mean_val:6.1f} counts")
        print(f"  Pixels: {len(spectrum)}")
        
        # Show saturation warning
        if max_val > 7500:
            print(f"  ⚠️  SATURATED ({max_val:.0f} counts)")
        elif max_val > 6000:
            print(f"  ⚠️  Near saturation ({max_val:.0f} counts)")
    else:
        print("DETECTOR READING: No data")
    
    print()
    print("-" * 80)
    print("CONTROLS:")
    print("  a/A: LED A -/+     b/B: LED B -/+     c/C: LED C -/+     d/D: LED D -/+")
    print("  t/T: IntTime -/+   0: All OFF         r: Reset to 50%    q: Quit")
    print("-" * 80)
    print()
    print("Command: ", end='', flush=True)

# Set initial state
set_leds()
update_integration_time()

# Interactive mode with matplotlib visualization and UI SLIDERS
from matplotlib.widgets import Slider, Button

# Create figure with more space for controls
fig = plt.figure(figsize=(14, 10))
gs = fig.add_gridspec(3, 2, height_ratios=[3, 2, 1], hspace=0.4, wspace=0.3)

# Spectrum plot
ax_spectrum = fig.add_subplot(gs[0, :])
line1, = ax_spectrum.plot([], [], 'b-', linewidth=0.5)
ax_spectrum.set_xlabel('Pixel')
ax_spectrum.set_ylabel('Intensity (counts)')
ax_spectrum.set_title('Live Spectrum from Phase Photonics Detector (13-bit: 0-8192)', fontsize=14, fontweight='bold')
ax_spectrum.grid(True, alpha=0.3)
ax_spectrum.set_ylim(0, 8192)
# Add horizontal line at saturation threshold (8000 counts)
ax_spectrum.axhline(y=8000, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Saturation (~8000)')

# LED bars
ax_bars = fig.add_subplot(gs[1, :])
bar_positions = np.arange(4)
bars = ax_bars.bar(bar_positions, [0, 0, 0, 0], color=['red', 'green', 'blue', 'yellow'], width=0.6)
ax_bars.set_xticks(bar_positions)
ax_bars.set_xticklabels(['LED A', 'LED B', 'LED C', 'LED D'])
ax_bars.set_ylabel('Intensity (0-255)')
ax_bars.set_title('LED Intensities')
ax_bars.set_ylim(0, 255)
ax_bars.grid(True, alpha=0.3, axis='y')

# Stats text
stats_text = ax_spectrum.text(0.02, 0.98, '', transform=ax_spectrum.transAxes, 
                              verticalalignment='top', fontfamily='monospace', fontsize=10,
                              bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Create sliders for LED control
slider_color = 'lightgoldenrodyellow'
ax_slider_a = plt.axes([0.15, 0.18, 0.35, 0.03], facecolor=slider_color)
ax_slider_b = plt.axes([0.15, 0.13, 0.35, 0.03], facecolor=slider_color)
ax_slider_c = plt.axes([0.15, 0.08, 0.35, 0.03], facecolor=slider_color)
ax_slider_d = plt.axes([0.15, 0.03, 0.35, 0.03], facecolor=slider_color)
ax_slider_int = plt.axes([0.65, 0.13, 0.25, 0.03], facecolor=slider_color)

slider_a = Slider(ax_slider_a, 'LED A', 0, 255, valinit=0, valstep=1, color='red')
slider_b = Slider(ax_slider_b, 'LED B', 0, 255, valinit=0, valstep=1, color='green')
slider_c = Slider(ax_slider_c, 'LED C', 0, 255, valinit=0, valstep=1, color='blue')
slider_d = Slider(ax_slider_d, 'LED D', 0, 255, valinit=0, valstep=1, color='orange')
slider_int_time = Slider(ax_slider_int, 'Int Time (ms)', 1, 100, valinit=10, valstep=1)

# Buttons
ax_btn_off = plt.axes([0.65, 0.08, 0.1, 0.04])
ax_btn_50 = plt.axes([0.76, 0.08, 0.1, 0.04])
ax_btn_max = plt.axes([0.65, 0.03, 0.1, 0.04])
ax_btn_quit = plt.axes([0.76, 0.03, 0.1, 0.04])

btn_off = Button(ax_btn_off, 'All OFF', color='lightcoral')
btn_50 = Button(ax_btn_50, '50%', color='lightgreen')
btn_max = Button(ax_btn_max, 'MAX', color='yellow')
btn_quit = Button(ax_btn_quit, 'QUIT', color='lightgray')

# Slider callbacks
def on_slider_a(val):
    led_intensities['A'] = int(val)
    set_leds()

def on_slider_b(val):
    led_intensities['B'] = int(val)
    set_leds()

def on_slider_c(val):
    led_intensities['C'] = int(val)
    set_leds()

def on_slider_d(val):
    led_intensities['D'] = int(val)
    set_leds()

def on_slider_int_time(val):
    global integration_time
    integration_time = int(val)
    update_integration_time()

slider_a.on_changed(on_slider_a)
slider_b.on_changed(on_slider_b)
slider_c.on_changed(on_slider_c)
slider_d.on_changed(on_slider_d)
slider_int_time.on_changed(on_slider_int_time)

# Button callbacks
def on_btn_off(event):
    slider_a.set_val(0)
    slider_b.set_val(0)
    slider_c.set_val(0)
    slider_d.set_val(0)

def on_btn_50(event):
    slider_a.set_val(127)
    slider_b.set_val(127)
    slider_c.set_val(127)
    slider_d.set_val(127)

def on_btn_max(event):
    slider_a.set_val(255)
    slider_b.set_val(255)
    slider_c.set_val(255)
    slider_d.set_val(255)

def on_btn_quit(event):
    global running
    running = False
    plt.close('all')

btn_off.on_clicked(on_btn_off)
btn_50.on_clicked(on_btn_50)
btn_max.on_clicked(on_btn_max)
btn_quit.on_clicked(on_btn_quit)

def update_plot(frame):
    """Update plot with current data"""
    global running
    
    if not running:
        return
    
    # Get spectrum
    spectrum = get_spectrum()
    
    if spectrum is not None:
        # Update spectrum plot
        x_data = np.arange(len(spectrum))
        line1.set_data(x_data, spectrum)
        ax_spectrum.set_xlim(0, len(spectrum))
        
        # Update stats text
        max_val = np.max(spectrum)
        mean_val = np.mean(spectrum)
        stats = f'Max: {max_val:.0f} counts\nMean: {mean_val:.1f} counts\nInt Time: {integration_time} ms'
        if max_val > 8000:
            stats += '\n⚠️ SATURATED'
        elif max_val < 100:
            stats += '\n(Dark - LEDs off?)'
        stats_text.set_text(stats)
    
    # Update LED bars
    led_values = [led_intensities['A'], led_intensities['B'], 
                  led_intensities['C'], led_intensities['D']]
    for bar, height in zip(bars, led_values):
        bar.set_height(height)
    
    return line1, bars, stats_text

print()
print("=" * 80)
print("✓ STARTING INTERACTIVE LED CONTROL")
print("=" * 80)
print()
print("USE THE SLIDERS to control LED intensities and integration time")
print("USE THE BUTTONS:")
print("  - All OFF: Turn all LEDs off")
print("  - 50%: Set all LEDs to 50%")
print("  - MAX: Set all LEDs to maximum")
print("  - QUIT: Close the application")
print()
print("The spectrum plot will update in real-time!")
print("=" * 80)
print()

ani = FuncAnimation(fig, update_plot, interval=200, blit=False, cache_frame_data=False)
plt.show()

# Cleanup
print()
print("Cleaning up...")
ctrl.set_batch_intensities(0, 0, 0, 0)
print("✓ LEDs turned off")
print("✓ Done")
