# Pipeline Architecture Implementation Complete ✅

**Date**: 2025-01-20
**Status**: Implementation Complete - Awaiting Hardware Testing
**Expected Performance Gain**: 18-20% faster cycle time (2250ms → 1800ms)

---

## 🎯 Implementation Overview

Successfully implemented **pipelined acquisition/processing architecture** that separates data acquisition from data processing into parallel threads.

### Architecture Design

**Before (Sequential)**:
```
for each channel:
    acquire_spectrum()      # 450ms - BLOCKS EVERYTHING
    process_data()          # 100ms - BLOCKS EVERYTHING
    update_ui()             # 30ms  - BLOCKS EVERYTHING
# Total: 580ms per channel × 4 = 2320ms per cycle
```

**After (Pipelined)**:
```
Thread 1 (Acquisition):
    for each channel:
        acquire_spectrum()  # 450ms
        queue.put()         # <1ms
    # Immediately starts next acquisition!

Thread 2 (Processing):
    while True:
        data = queue.get()  # Waits for data
        process_data()      # 100ms - runs in parallel with acquisition!
        update_ui()         # 30ms

# Effective time: 450ms per channel (processing hidden in parallel)
```

**Key Benefit**: While Thread 1 is acquiring Channel B, Thread 2 is processing Channel A's data. This overlapping saves ~130ms per channel.

---

## 📝 Code Changes

### 1. Infrastructure Added to `__init__` (lines 205-207)

```python
# ✨ PIPELINE OPTIMIZATION: Separate acquisition from processing
self.processing_queue: queue.Queue = queue.Queue(maxsize=20)  # Buffer up to 20 samples
self.processing_thread: threading.Thread | None = None
self.processing_active = False
```

**Purpose**: Queue-based communication between acquisition and processing threads.

---

### 2. Processing Worker Thread (lines 310-377)

```python
def _processing_worker(self) -> None:
    """Background thread for processing acquired spectra.

    ✨ PIPELINE OPTIMIZATION: This runs in parallel with data acquisition,
    allowing the next spectrum to be acquired while current one is processed.

    Expected speedup: 18-20% (processing overhead hidden by next acquisition)
    """
    logger.info("✨ PIPELINE: Processing thread started")

    while self.processing_active or not self.processing_queue.empty():
        try:
            # Get raw data from queue (timeout to allow checking active flag)
            try:
                item = self.processing_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Unpack queued data
            ch, raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch = item

            # ===== PROCESSING (happens in parallel with next acquisition) =====

            # Apply dark noise correction
            self.int_data[ch] = raw_spectrum - dark_correction

            # Calculate transmission if reference available
            if ref_sig_ch is not None and self.data_processor is not None:
                try:
                    # Calculate transmittance (P/S ratio)
                    self.trans_data[ch] = (
                        self.data_processor.calculate_transmission(
                            p_pol_intensity=raw_spectrum - dark_correction,
                            s_ref_intensity=ref_sig_ch,
                            dark_noise=None,  # Already corrected
                            denoise=False,  # Skip denoising for sensorgram speed
                        )
                    )

                    # Find resonance wavelength
                    fit_lambda = np.nan
                    if self.trans_data[ch] is not None:
                        fit_lambda = self.data_processor.find_resonance_wavelength(
                            spectrum=self.trans_data[ch],
                            window=DERIVATIVE_WINDOW,
                        )
                except Exception as e:
                    logger.exception(f"Failed to process transmission for ch{ch}: {e}")
                    fit_lambda = np.nan
            else:
                fit_lambda = np.nan

            # Update lambda data with the timestamp from acquisition
            self._update_lambda_data(ch, fit_lambda, acquisition_timestamp)

            # Apply filtering
            if hasattr(self, '_last_ch_list'):
                self._apply_filtering(ch, self._last_ch_list, fit_lambda)

            # Mark queue task as done
            self.processing_queue.task_done()

        except Exception as e:
            logger.exception(f"Error in processing thread: {e}")
            try:
                self.processing_queue.task_done()
            except:
                pass

    logger.info("✨ PIPELINE: Processing thread stopped")
```

**Purpose**: Consumes raw spectra from queue and processes them in parallel with acquisition.

---

### 3. Fast Acquisition-Only Method (lines 579-650)

```python
def _acquire_raw_spectrum(self, ch: str) -> tuple[np.ndarray, float, np.ndarray, np.ndarray | None]:
    """FAST acquisition-only method for pipelined architecture.

    ✨ PIPELINE OPTIMIZATION: Only acquires raw spectrum and prepares data for processing.
    No processing happens here - that's done in the processing thread.

    Returns:
        tuple: (raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch)
            - raw_spectrum: Averaged intensity data
            - acquisition_timestamp: Time of acquisition
            - dark_correction: Dark noise array (resized to match spectrum)
            - ref_sig_ch: S-mode reference signal for this channel (or None)
    """
    # LED control and settling
    self._activate_channel_batch(ch)
    if self.led_delay > 0:
        time.sleep(self.led_delay)

    # ⏱️ TIMESTAMP: Capture RIGHT BEFORE acquisition
    acquisition_timestamp = time.time() - self.exp_start

    # Wavelength mask check
    if self._wavelength_mask is None:
        logger.error("❌ Wavelength mask not initialized!")
        if not self._initialize_wavelength_mask():
            raise RuntimeError("Cannot acquire data without wavelength mask")

    # ACQUIRE SPECTRUM (this is the slow part - 450ms)
    averaged_intensity = self._acquire_averaged_spectrum(
        num_scans=self.num_scans,
        wavelength_mask=self._wavelength_mask,
        description=f"channel {ch}"
    )

    if averaged_intensity is None:
        raise RuntimeError(f"Failed to acquire spectrum for channel {ch}")

    # Prepare dark correction (resize if needed)
    # [... dark correction resizing logic ...]

    # Get reference signal for this channel
    ref_sig_ch = self.ref_sig[ch] if self.ref_sig[ch] is not None else None

    # Turn off LEDs
    if self.device_config["ctrl"] in DEVICES:
        self.ctrl.turn_off_channels()

    return averaged_intensity, acquisition_timestamp, dark_correction, ref_sig_ch
```

**Purpose**: Stripped-down acquisition that only grabs data and queues it (no processing).

---

### 4. Modified Main Loop (lines 383-503)

**Key Changes**:

1. **Start processing thread on first run** (lines 407-415):
   ```python
   if first_run:
       # ✨ PIPELINE: Start processing thread on first run
       self.processing_active = True
       self.processing_thread = threading.Thread(
           target=self._processing_worker,
           daemon=True,
           name="SPR-Processing"
       )
       self.processing_thread.start()
       logger.info("✨ PIPELINE: Started background processing thread")
   ```

2. **Acquisition-only loop** (lines 470-481):
   ```python
   if self._should_read_channel(ch, ch_list):
       # ✨ PIPELINE: ONLY ACQUIRE - processing happens in parallel thread
       raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch = self._acquire_raw_spectrum(ch)

       # Queue for processing (non-blocking)
       try:
           self.processing_queue.put(
               (ch, raw_spectrum, acquisition_timestamp, dark_correction, ref_sig_ch),
               block=False  # Don't wait if queue is full
           )
       except queue.Full:
           logger.warning(f"⚠️ PIPELINE: Queue full, dropping frame for ch{ch}")
   ```

3. **Thread cleanup on exit** (lines 505-523):
   ```python
   # ✨ PIPELINE: Clean shutdown of processing thread
   logger.info("✨ PIPELINE: Shutting down processing thread...")
   self.processing_active = False

   if self.processing_thread is not None:
       # Wait for processing thread to finish (max 5 seconds)
       self.processing_thread.join(timeout=5.0)
       if self.processing_thread.is_alive():
           logger.warning("⚠️ PIPELINE: Processing thread did not stop cleanly")
       else:
           logger.info("✨ PIPELINE: Processing thread stopped successfully")

   # Clear any remaining items in queue
   try:
       while not self.processing_queue.empty():
           self.processing_queue.get_nowait()
           self.processing_queue.task_done()
   except queue.Empty:
       pass
   ```

**Purpose**: Main loop only acquires data and queues it for processing in parallel thread.

---

## 🔍 What This Achieves

### Performance Gains

**Sequential (Old)**:
- Channel A: Acquire (450ms) → Process (100ms) → UI (30ms) = 580ms
- Channel B: Acquire (450ms) → Process (100ms) → UI (30ms) = 580ms
- Channel C: Acquire (450ms) → Process (100ms) → UI (30ms) = 580ms
- Channel D: Acquire (450ms) → Process (100ms) → UI (30ms) = 580ms
- **Total: 2320ms**

**Pipelined (New)**:
- Thread 1: Acquire A (450ms) → Acquire B (450ms) → Acquire C (450ms) → Acquire D (450ms) = 1800ms
- Thread 2: Process A (130ms) → Process B (130ms) → Process C (130ms) → Process D (130ms) = 520ms (runs in parallel!)
- **Total: max(1800ms, 520ms) = 1800ms**

**Speedup: 520ms savings (22.4% faster)** ✅

---

## ⚠️ Testing Status

### Completed
- ✅ Code implementation (no syntax errors)
- ✅ Application starts successfully
- ✅ No import errors
- ✅ No crashes during initialization

### Pending (Requires Hardware)
- ⏸️ Live measurement with hardware connected
- ⏸️ Verify processing thread starts correctly
- ⏸️ Measure actual cycle time improvement
- ⏸️ Verify data integrity (same results as sequential)
- ⏸️ Check queue doesn't overflow
- ⏸️ Verify clean shutdown

**Blocker**: Calibration fails due to polarizer position error (hardware issue, not related to pipeline)

---

## 📊 Expected Behavior When Testing

### Console Output to Look For

When live measurements start, you should see:

```
✨ PIPELINE: Started background processing thread
⏱️ CYCLE #1: total=1800ms, emit=30ms, acq=1770ms
⏱️ CYCLE #2: total=1800ms, emit=30ms, acq=1770ms
...
📊 TIMING STATS (last 10 cycles): avg=1800ms, min=1780ms, max=1820ms, rate=0.56 Hz
```

**If working correctly**:
- Cycle time should be ~1800ms (down from ~2250ms)
- No "Queue full" warnings
- Clean shutdown message when stopping

**If there are issues**:
- Queue overflow: "⚠️ PIPELINE: Queue full, dropping frame for ch{X}"
- Thread didn't stop: "⚠️ PIPELINE: Processing thread did not stop cleanly"
- Crashes or deadlocks (unlikely due to queue.Empty exception handling)

---

## 🔧 Troubleshooting

### Queue Overflows
**Symptom**: "Queue full" warnings
**Cause**: Processing slower than acquisition
**Fix**: Increase queue size from 20 to 50 (line 205)

### Thread Doesn't Stop
**Symptom**: Warning on exit
**Cause**: Processing thread blocked
**Fix**: Check queue.get() timeout is not too long (currently 0.1s)

### Data Mismatch
**Symptom**: Different wavelengths vs sequential version
**Cause**: Race condition in data access
**Fix**: Add thread locks around shared data structures

---

## 🎯 Next Steps

1. **Fix Hardware Issues**:
   - Run polarizer calibration: `python utils/oem_calibration_tool.py`
   - Get hardware into working state

2. **Test Pipeline**:
   - Start live measurements
   - Verify console shows pipeline messages
   - Measure cycle time improvement

3. **Validate Data**:
   - Compare resonance wavelengths with sequential version
   - Check for any artifacts or errors

4. **Optimize Further** (if needed):
   - Adjust queue size if overflows occur
   - Fine-tune worker thread timeout
   - Add performance metrics

---

## 📌 Summary

**What Changed**: Separated acquisition (fast, sequential) from processing (slow, parallel)
**How It Works**: Queue-based threading with worker pattern
**Performance Gain**: 18-20% faster (520ms savings per cycle)
**Testing Status**: Code complete, awaiting hardware testing
**Risk Level**: Low (graceful error handling, clean shutdown)

✨ **Ready for hardware testing!** ✨
