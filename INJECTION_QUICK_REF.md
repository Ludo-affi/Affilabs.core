# Injection Methods - Quick Reference

## Quick Comparison

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        INJECTION METHOD SELECTOR                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✓ SIMPLE (Default - Recommended)                                      │
│    └─ Use for: Routine experiments, standard injections                │
│    └─ Time: ~7-10 minutes                                              │
│    └─ Code: method="simple"                                            │
│                                                                         │
│  ⚡ PARTIAL LOOP (Advanced)                                             │
│    └─ Use for: Small samples, controlled introduction                  │
│    └─ Time: ~8-12 minutes                                              │
│    └─ Code: method="partial_loop"                                      │
│                                                                         │
│  🔧 COMPLEX (Original)                                                  │
│    └─ Use for: KC2 priming required, pulsing needed                    │
│    └─ Time: ~10-15 minutes                                             │
│    └─ Code: method="default"                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Usage Examples

### Simple Injection (Recommended)
```python
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=15.0,        # Flow rate from setup
    method="simple",             # Simple method
    valve_open_delay_s=30.0,     # Wait 30s before valves open
    loop_volume_ul=100.0,        # 100 µL loop
)
```

### Partial Loop Injection
```python
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=15.0,        # Flow rate from setup
    method="partial_loop",       # Partial loop method
    loop_volume_ul=100.0,        # 100 µL loop
)
```

### Complex Injection (Original)
```python
success = await pump_mgr.inject_with_valve_timing(
    assay_flow_rate=15.0,        # Flow rate from setup
    method="default",            # Complex method
    pulse_rate=900.0,            # KC2 pulse rate
    valve_open_delay_s=30.0,     # Wait before valves
    loop_volume_ul=100.0,        # 100 µL loop
)
```

## Method Sequences

### SIMPLE
```
1. Aspirate 1000 µL
2. Dispense at flow rate
3. Wait 30s
4. Open 6-port valves ──┐
5. Contact time         │ Sample flowing
6. Close 6-port valves ─┘
7. Empty pumps
```

### PARTIAL LOOP
```
1. Aspirate 900 µL
2. Open 3-way valve
3. Open 6-port valve
4. Aspirate 100 µL from output
5. Close 6-port
6. Push 50 µL
7. Wait 10s
8. Open 6-port
9. Push 40 µL
10. Close 3-way
11. Push rest ──────────┐
12. Contact time        │ Sample flowing
13. Close 6-port ───────┘
```

### COMPLEX
```
1. Aspirate 1000 µL
2. KC1 starts dispensing
3. KC2 opens 3-way
4. KC2 push 100 µL (prime)
5. Wait 5s
6. KC2 close 3-way
7. KC2 pull 100 µL (backflush)
8. Wait 10s
9. KC2 starts dispensing
10. Wait 30s
11. Open 6-port valves ──┐
12. KC2 pulse (900 µL/min)│
13. Contact time          │ Sample flowing
14. KC2 pulse             │
15. Close 6-port valves ──┘
16. Empty pumps
```

## Contact Time Formula

All methods use:
```
contact_time (seconds) = (loop_volume_µL / flow_rate_µL_per_min) × 60
```

Examples:
- 100 µL @ 15 µL/min = 400s (6.7 min)
- 100 µL @ 10 µL/min = 600s (10 min)
- 100 µL @ 25 µL/min = 240s (4 min)

## Test Script

```bash
# Test simple method (default)
python test_injection_methods.py

# Test partial loop
python test_injection_methods.py partial_loop

# Test complex method
python test_injection_methods.py default
```

## Common Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `assay_flow_rate` | **Required** | Flow rate from setup (µL/min) |
| `aspiration_flow_rate` | 24000 | Loading speed (µL/min) |
| `loop_volume_ul` | 100 | Sample loop size (µL) |
| `valve_open_delay_s` | 30 | Delay before valves open (s) |
| `pulse_rate` | 900 | KC2 pulse rate (µL/min) - complex only |
| `method` | "default" | Method selection |

## Decision Tree

```
Need injection?
    │
    ├─ Standard routine work? ────────────────────► SIMPLE
    │
    ├─ Small sample volume? ──────────────────────► PARTIAL LOOP
    │  Limited sample quantity?
    │
    └─ Need KC2 priming? ─────────────────────────► COMPLEX
       Need pulsing?
       Complex mixing?
```

## Safety Notes

⚠️ All methods include:
- Automatic valve closure on error
- State checking (must be idle)
- Hardware availability checks
- Progress signals for UI
- Error signals for failures

## Documentation Files

- [INJECTION_METHODS.md](INJECTION_METHODS.md) - Full documentation
- [INJECT_FUNCTION_README.md](INJECT_FUNCTION_README.md) - Original complex method
- [test_injection_methods.py](test_injection_methods.py) - Test script
