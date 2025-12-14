"""Convert baseline results from nm to RU units

1 nm = 355 RU (refractive index units)
Target: 4 RU peak-to-peak
"""

# Conversion factor
NM_TO_RU = 355  # 1 nm = 355 RU

# Target
TARGET_RU = 4  # RU
TARGET_NM = TARGET_RU / NM_TO_RU

print(f"="*80)
print(f"BASELINE RESULTS IN RU (REFRACTIVE INDEX UNITS)")
print(f"="*80)
print(f"\nConversion: 1 nm = {NM_TO_RU} RU")
print(f"Target: {TARGET_RU} RU = {TARGET_NM:.6f} nm = {TARGET_NM*1000:.3f} pm")
print()

# Results from Channel A comparison
results = {
    'Batch Average (12pt)': 1.935561,
    'Moving Average (11pt)': 2.163140,
    'Median Filter (5pt)': 2.215424,
    'Moving Average (5pt)': 2.224505,
    'Dual SG (5,2)→(21,3) GOLD': 2.384163,
    'Savitzky-Golay (21,3)': 2.392193,
    'Raw (No Filtering)': 2.643836
}

print('Peak-to-Peak Results:')
print('='*80)
print(f"{'Method':<35} {'P2P (nm)':<12} {'P2P (RU)':<12} {'vs Target':<12}")
print('-'*80)

for method, p2p_nm in results.items():
    p2p_ru = p2p_nm * NM_TO_RU
    vs_target = p2p_ru / TARGET_RU
    print(f"{method:<35} {p2p_nm:<12.6f} {p2p_ru:<12.1f} {vs_target:<12.1f}x")

print()
print("="*80)
print("SUMMARY")
print("="*80)

best_nm = results['Batch Average (12pt)']
best_ru = best_nm * NM_TO_RU

print(f"Best result:      {best_ru:.1f} RU ({best_nm:.3f} nm)")
print(f"Target:           {TARGET_RU:.1f} RU ({TARGET_NM:.6f} nm)")
print(f"Gap:              {best_ru - TARGET_RU:.1f} RU")
print(f"Performance:      {best_ru / TARGET_RU:.1f}x worse than target")
print()

if best_ru <= TARGET_RU:
    print("✅ TARGET ACHIEVED!")
else:
    print(f"❌ Need {best_ru / TARGET_RU:.1f}x improvement to reach 4 RU target")
    print(f"   Current: {best_ru:.1f} RU")
    print(f"   Need:    {TARGET_RU:.1f} RU")
    print(f"   Missing: {best_ru - TARGET_RU:.1f} RU")
