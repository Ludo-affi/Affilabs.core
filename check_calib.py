import json

with open('generated-files/calibration_history/calibration_history.jsonl', 'r') as f:
    lines = f.readlines()

print(f'Total calibrations: {len(lines)}')
print('\nLast 3 calibrations:')
print('='*80)

for line in lines[-3:]:
    d = json.loads(line)
    ts = d.get('timestamp', 'N/A')
    integ = d.get('integration_time_ms', 'N/A')
    leds = d.get('leds_calibrated', d.get('ref_intensity', {}))
    weakest = d.get('weakest_channel', 'N/A')

    print(f'\nTimestamp: {ts}')
    print(f'Integration: {integ}ms')
    print(f'LED Intensities: {leds}')
    print(f'Weakest channel: {weakest}')
