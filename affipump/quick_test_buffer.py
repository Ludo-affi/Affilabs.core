from affipump_controller import AffipumpController
import time

p = AffipumpController()
p.open()
p.initialize_pump(1)
time.sleep(5)

result = p.run_buffer(1, duration_minutes=2, flow_rate_ul_min=500)

print('\n=== FINAL RESULT ===')
print('Expected: 1000µL in 2.0 min')
print(f'Actual: {result["total_volume_delivered"]:.1f}µL in {result["elapsed_time_minutes"]:.2f} min')
print(f'Flow rate: {result["average_flow_rate"]:.1f} µL/min')
print(f'Cycles: {result["cycles_completed"]}')

p.close()
