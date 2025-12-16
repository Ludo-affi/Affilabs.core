# Acquisition Methods Guide

## Overview

The system supports **two acquisition methods** that can be seamlessly switched between. Both methods produce identical results and support the same timing parameters.

## Method 1: CYCLE_SYNC (Default)

**Status:** ✅ Recommended for production use
**Firmware Required:** V2.4 with CYCLE_START support
**Performance:** 1.0s/cycle, 75% less USB traffic

### How It Works

1. Firmware sends **ONE** `CYCLE_START` event per cycle (when LED_A turns on)
2. Python uses **fixed timing offsets** from CYCLE_START to read each LED:
   - LED_A: Read at +60ms
   - LED_B: Read at +310ms (250ms LED timing + 60ms wait)
   - LED_C: Read at +560ms (500ms LED timing + 60ms wait)
   - LED_D: Read at +810ms (750ms LED timing + 60ms wait)
3. Firmware watchdog on separate Timer 1 (zero timing impact)
4. Python sends keepalive every 60 seconds

### Advantages

- **Fastest:** 1.0s/cycle deterministic timing
- **Lowest USB traffic:** 75% fewer events than EVENT_RANK
- **Most reliable:** Software timing offsets eliminate USB latency issues
- **Safest:** Hardware watchdog prevents runaway operation

### Use Cases

- Production data acquisition
- High-speed continuous monitoring
- Long-term stability testing
- Any application requiring deterministic timing

---

## Method 2: EVENT_RANK

**Status:** ✅ Available for debugging/validation
**Firmware Required:** Any firmware with RANKBATCH support
**Performance:** 1.0-1.1s/cycle, more USB traffic

### How It Works

1. Firmware sends **FOUR** `x:READY` events per cycle (one for each LED)
2. Python listens for each READY event and reads detector immediately:
   - `a:READY` → wait 60ms → read LED_A
   - `b:READY` → wait 60ms → read LED_B
   - `c:READY` → wait 60ms → read LED_C
   - `d:READY` → wait 60ms → read LED_D
3. Event-driven architecture with per-LED validation
4. Pre-arm optimization for global integration time

### Advantages

- **Event validation:** Confirms each LED event received
- **Per-LED diagnostics:** Track individual LED performance
- **Debugging friendly:** Clear event sequence in logs
- **Firmware compatibility:** Works with older firmware

### Use Cases

- Debugging timing issues
- Validating firmware event generation
- Per-LED performance analysis
- Development and testing

---

## Switching Between Methods

### Configuration

Edit `affilabs/core/data_acquisition_manager.py`:

```python
# Line 20
USE_CYCLE_SYNC = True   # CYCLE_SYNC (V2.4 firmware)
USE_CYCLE_SYNC = False  # EVENT_RANK (computer-level sync)
```

### No Other Changes Required

Both methods share:
- Same timing parameters (LED ON: 250ms, LED OFF: 0ms)
- Same detector wait time (60ms default, configurable in Advanced Settings)
- Same async processing pipeline
- Same spectrum validation
- Same LED intensity control

The switch is **completely transparent** to the rest of the system.

---

## Timing Parameters

Both methods use identical timing:

| Parameter | Value | Configurable? | Location |
|-----------|-------|---------------|----------|
| LED ON Time | 250ms | Yes | Advanced Settings |
| LED OFF Time | 0ms | Yes | Advanced Settings |
| Detector Wait | 60ms | Yes | Advanced Settings |
| Integration Time | Variable | Yes | Calibration data |
| Cycle Period | ~1000ms | No | Firmware controlled |

### Timing Diagram (Both Methods)

```
t=0ms:    LED_A ON   → firmware event (CYCLE_START or a:READY)
t=60ms:   Read A     → Python acquires spectrum
t=250ms:  LED_B ON   → firmware event (b:READY for EVENT_RANK)
t=310ms:  Read B     → Python acquires spectrum
t=500ms:  LED_C ON   → firmware event (c:READY for EVENT_RANK)
t=560ms:  Read C     → Python acquires spectrum
t=750ms:  LED_D ON   → firmware event (d:READY for EVENT_RANK)
t=810ms:  Read D     → Python acquires spectrum
t=1000ms: Next cycle → firmware event (CYCLE_START or a:READY)
```

---

## Performance Comparison

| Metric | CYCLE_SYNC | EVENT_RANK |
|--------|-----------|-----------|
| Cycle Time | 1.0s | 1.0-1.1s |
| USB Events/Cycle | 1 | 4 |
| CPU Usage | Lower | Higher |
| Timing Jitter | Minimal | Low |
| Firmware Version | V2.4+ | Any |
| Watchdog Support | Yes | No |
| Best For | Production | Debug |

---

## Implementation Details

### CYCLE_SYNC Implementation

**File:** `affilabs/core/data_acquisition_manager.py`
**Function:** `_acquire_all_channels_cycle_sync()`
**Lines:** 1833-1990

**Key Features:**
- Constants extracted (LED_ON_TIME_MS, LED_OFF_TIME_MS, RANKBATCH_CYCLES)
- Clear timing model with firmware offsets + software delays
- Spectrum validation (empty, all-zero detection)
- Watchdog keepalive after CYCLE_START (non-blocking)
- Section headers: INITIALIZATION → MAIN LOOP → cleanup

### EVENT_RANK Implementation

**File:** `affilabs/core/data_acquisition_manager.py`
**Function:** `_acquire_all_channels_via_rank()`
**Lines:** 1992-2250

**Key Features:**
- Constants extracted (RANKBATCH_CYCLES = 3600)
- Pre-arm optimization for global integration time
- Event-driven parsing of READY signals
- Multi-scan averaging support
- Statistics tracking (READY events, acquisitions, missed spectra)
- Section headers: INITIALIZATION → MAIN LOOP → CLEANUP

---

## Troubleshooting

### CYCLE_SYNC Issues

**Problem:** Wavelength spikes appearing
**Solution:** Verify watchdog keepalive timing is AFTER CYCLE_START
**Check:** Lines 1920-1927 in data_acquisition_manager.py

**Problem:** Firmware timeout
**Solution:** Ensure keepalive sent every 60s (check WATCHDOG_KEEPALIVE_INTERVAL)
**Check:** Line 32 in data_acquisition_manager.py

### EVENT_RANK Issues

**Problem:** Firmware stalled (no READY for 5s)
**Solution:** Check serial connection, verify firmware running
**Check:** Logs for "[EVENT-RANK] Firmware stalled" message

**Problem:** Many missed spectra
**Solution:** Reduce integration time or increase detector wait time
**Check:** Missed spectra breakdown in logs

---

## Future Development

Both methods will evolve together:

1. **UI Toggle:** Add runtime method selection in Advanced Settings
2. **Auto-Detection:** Automatically detect firmware capabilities
3. **Hybrid Mode:** Use CYCLE_SYNC with EVENT_RANK fallback
4. **Performance Tuning:** Per-method optimization based on use case

---

## Version History

- **V2.4.1** (2024-12-14): Both methods cleaned up and documented
  - CYCLE_SYNC: Added watchdog, spectrum validation, cleaner structure
  - EVENT_RANK: Simplified event parsing, better error handling
  - Seamless switching via USE_CYCLE_SYNC flag

- **V2.4.0** (2024-12): Initial CYCLE_SYNC implementation
  - Firmware CYCLE_START event support
  - Fixed timing offsets
  - Watchdog on separate Timer 1

- **V2.3** (2024-11): EVENT_RANK (formerly "RANK-EVENT")
  - Event-driven READY signal processing
  - Pre-arm optimization
  - Per-LED statistics tracking
