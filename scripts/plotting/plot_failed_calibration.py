"""Plot diagnostic information from failed calibration attempt.

This script shows what data was collected before calibration failed.
"""

import matplotlib.pyplot as plt
import numpy as np

# Error data from console output
error_info = {
    'old_s_pos': 120,
    'old_p_pos': 60,
    'error': 'Step 6 failed: Failed to set S-mode - controller did not confirm'
}

print("="*80)
print("FAILED CALIBRATION DIAGNOSTIC")
print("="*80)
print(f"Error: {error_info['error']}")
print(f"Old S position: {error_info['old_s_pos']}°")
print(f"Old P position: {error_info['old_p_pos']}°")
print("="*80)

# Create visualization
fig = plt.figure(figsize=(12, 8), facecolor='white')
fig.suptitle('Calibration Failure Diagnostic', fontsize=16, fontweight='bold', color='red')

# Plot 1: Servo positions comparison
ax1 = fig.add_subplot(2, 2, 1)
positions = ['Old S-pos', 'Old P-pos', 'New S-pos\n(device_config)', 'New P-pos\n(device_config)']
values = [error_info['old_s_pos'], error_info['old_p_pos'], 89, 179]
colors = ['red', 'red', 'green', 'green']
bars = ax1.bar(positions, values, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
ax1.set_ylabel('Servo Angle (degrees)', fontsize=11, fontweight='bold')
ax1.set_title('Servo Position Comparison', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')
ax1.set_ylim(0, 200)

for bar, val in zip(bars, values):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             f'{val}°', ha='center', va='bottom', fontweight='bold', fontsize=10)

# Add annotations
ax1.text(0.02, 0.98, '❌ OLD positions (before fix)',
         transform=ax1.transAxes, fontsize=9, color='red',
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax1.text(0.02, 0.88, '✅ NEW positions (device_config)',
         transform=ax1.transAxes, fontsize=9, color='green',
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

# Plot 2: Polarizer orientation issue
ax2 = fig.add_subplot(2, 2, 2)
modes = ['S-mode\n(Max Transmission)', 'P-mode\n(Min Transmission,\nStrongest SPR)']
old_positions = [120, 60]
new_positions = [89, 179]

x = np.arange(len(modes))
width = 0.35

bars1 = ax2.bar(x - width/2, old_positions, width, label='Old (INVERTED)',
                color='red', alpha=0.7, edgecolor='black', linewidth=2)
bars2 = ax2.bar(x + width/2, new_positions, width, label='New (CORRECT)',
                color='green', alpha=0.7, edgecolor='black', linewidth=2)

ax2.set_ylabel('Servo Angle (degrees)', fontsize=11, fontweight='bold')
ax2.set_title('Polarizer Orientation Correction', fontsize=12, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(modes, fontsize=9)
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3, axis='y')

for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, height + 5,
                f'{height}°', ha='center', va='bottom', fontweight='bold', fontsize=9)

# Plot 3: Error sequence
ax3 = fig.add_subplot(2, 2, 3)
ax3.axis('off')
ax3.set_xlim(0, 1)
ax3.set_ylim(0, 1)

error_text = f"""
CALIBRATION FAILURE SEQUENCE:

1. ⚠️  OLD servo positions detected:
   • S-position: {error_info['old_s_pos']}° (should be 89°)
   • P-position: {error_info['old_p_pos']}° (should be 179°)

2. 🔄 Calibration attempted restart
   • Detected inverted polarizer
   • Trying to recalibrate positions

3. ❌ Failure at Step 6:
   • Tried to set S-mode
   • Controller did not confirm movement
   • Possible causes:
     - Controller EEPROM still has old positions
     - Communication error with controller
     - Servo hardware issue

4. ✅ FIXES APPLIED:
   • Device config updated: S=89°, P=179°
   • Legacy EEPROM functions deleted
   • Startup EEPROM sync enabled
   • Validation logging enhanced
   • set_mode() error handling improved

5. 🔧 NEXT STEPS:
   • Run calibration again
   • Check for validation debug logs
   • Verify EEPROM sync at startup
   • Monitor controller responses
"""

ax3.text(0.05, 0.95, error_text, transform=ax3.transAxes,
         fontsize=9, verticalalignment='top', family='monospace',
         bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

# Plot 4: Expected vs Actual behavior
ax4 = fig.add_subplot(2, 2, 4)

categories = ['S-mode\nTransmission', 'P-mode\nTransmission', 'P/S Ratio']
expected = [100, 20, 0.2]  # Expected: S high, P low, ratio < 1
actual_old = [20, 100, 5.0]  # Old: inverted

x = np.arange(len(categories))
width = 0.35

bars1 = ax4.bar(x - width/2, expected, width, label='Expected (Correct)',
                color='green', alpha=0.7, edgecolor='black', linewidth=2)
bars2 = ax4.bar(x + width/2, actual_old, width, label='Old Positions (Inverted)',
                color='red', alpha=0.7, edgecolor='black', linewidth=2)

ax4.set_ylabel('Relative Value', fontsize=11, fontweight='bold')
ax4.set_title('Polarizer Behavior Comparison', fontsize=12, fontweight='bold')
ax4.set_xticks(x)
ax4.set_xticklabels(categories, fontsize=9)
ax4.legend(fontsize=9, loc='upper left')
ax4.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('calibration_failure_diagnostic.png', dpi=150, bbox_inches='tight')
print("\n✅ Diagnostic plot saved to: calibration_failure_diagnostic.png")
print("\nKEY FINDINGS:")
print("• Old positions were INVERTED (S=120°, P=60°)")
print("• Device config corrected (S=89°, P=179°)")
print("• Calibration failed trying to set S-mode")
print("• Controller did not confirm movement")
print("\nSOLUTION:")
print("• EEPROM sync at startup will update controller")
print("• Improved error handling allows continuation")
print("• Enhanced logging will show validation details")
print("\n🔧 Run calibration again to see improvements!")

plt.show()
