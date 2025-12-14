# Main Application Refactoring Plan

## Current State Analysis

**File**: `Old software/main/main.py`
- **Size**: 165KB, 3,530 lines
- **Class**: `AffiniteApp` - monolithic class handling everything
- **Issues**:
  - Data processing logic mixed with UI control
  - Hardware management mixed with data acquisition
  - Long methods (>100 lines)
  - High cyclomatic complexity
  - Difficult to test individual components
  - Hard to add new processing pipelines

## Core Problem

The `_grab_data()` method (lines 1433-1593) does too much:
1. Channel management
2. Data acquisition (via AcquisitionService)
3. **Pipeline selection and execution**
4. Filtering and buffering
5. UI updates
6. Error handling

As you add more processing complexity (new pipelines, ML models, quality checks), this will become unmaintainable.

---

## Proposed Refactoring Strategy

### Phase 1: Extract Data Processing Service ✅ STARTED

**Goal**: Separate spectrum processing from main application logic

**Create**: `utils/spectrum_processor.py`

```python
class SpectrumProcessor:
    """Centralized spectrum processing with pluggable pipelines.
    
    Responsibilities:
    - Execute active pipeline to find resonance wavelength
    - Apply filtering (median, Kalman, etc.)
    - Handle processing errors with fallback
    - Track processing statistics
    - Emit quality warnings
    """
    
    def __init__(self, pipeline_registry, fourier_weights):
        self.registry = pipeline_registry
        self.fourier_weights = fourier_weights
        self.processing_stats = {}
        
    def process_spectrum(
        self,
        transmission: np.ndarray,
        wavelengths: np.ndarray,
        channel: str,
    ) -> dict:
        """Process transmission spectrum and return results.
        
        Returns:
            {
                'resonance_wavelength': float,
                'pipeline_used': str,
                'quality_score': float,
                'warnings': list[str],
                'fallback_used': bool
            }
        """
        # Implementation here
        
    def apply_temporal_filtering(
        self,
        raw_value: float,
        channel: str,
        filter_type: str = 'median'
    ) -> float:
        """Apply temporal filtering to resonance wavelength."""
        # Implementation here
```

**Benefits**:
- Main loop becomes cleaner
- Easy to add new processing steps
- Can unit test processing independently
- Processing config in one place

---

### Phase 2: Extract Channel Manager

**Goal**: Manage multi-channel acquisition logic

**Create**: `utils/channel_manager.py`

```python
class ChannelManager:
    """Manages channel iteration and data buffering.
    
    Responsibilities:
    - Determine active channels based on device type
    - Manage channel-specific buffers
    - Handle single-channel mode
    - Pad missing values
    - Emit per-channel events
    """
    
    def __init__(self, device_config):
        self.device_config = device_config
        self.lambda_values = {ch: np.array([]) for ch in CH_LIST}
        self.lambda_times = {ch: np.array([]) for ch in CH_LIST}
        self.filtered_lambda = {ch: np.array([]) for ch in CH_LIST}
        # ... other buffers
        
    def get_active_channels(self) -> list[str]:
        """Return list of channels to acquire based on mode."""
        
    def append_data_point(self, channel: str, wavelength: float, timestamp: float):
        """Add new data point with automatic buffer management."""
        
    def get_sensorgram_data(self) -> dict:
        """Export current state for UI display."""
```

---

### Phase 3: Extract Hardware State Machine

**Goal**: Separate hardware control from data processing

**Create**: `utils/hardware_coordinator.py`

```python
class HardwareCoordinator:
    """Coordinates all hardware devices (controller, spectrometer, kinetics).
    
    Responsibilities:
    - Device initialization sequences
    - Graceful connection/disconnection
    - Hardware health monitoring
    - Error recovery strategies
    - Temperature monitoring
    """
    
    def __init__(self):
        self.ctrl = None
        self.usb = None
        self.knx = None
        self.hw_state = HardwareStateManager()
        
    def connect_devices(self):
        """Thread-safe device connection."""
        
    def monitor_health(self) -> dict:
        """Check hardware status and return health report."""
```

---

### Phase 4: Refactor Main Loop

**Goal**: Reduce `_grab_data()` to orchestration only

**Before** (160 lines):
```python
def _grab_data(self):
    while not self._b_kill.is_set():
        # 100+ lines of mixed logic
        # - channel management
        # - acquisition
        # - processing
        # - filtering
        # - UI updates
        # - error handling
```

**After** (30 lines):
```python
def _grab_data(self):
    """Main acquisition loop - orchestration only."""
    while not self._b_kill.is_set():
        if self._should_pause():
            time.sleep(0.2)
            continue
            
        # Get active channels
        channels = self.channel_mgr.get_active_channels()
        
        # Acquire and process each channel
        for ch in channels:
            if self._b_stop.is_set():
                break
                
            # Acquire spectrum
            result = self.acq_service.acquire_channel(ch, ...)
            if result is None:
                continue
                
            # Process spectrum
            processed = self.spectrum_processor.process_spectrum(
                result.transmission,
                self.wave_data,
                ch
            )
            
            # Buffer data
            self.channel_mgr.append_data_point(
                ch,
                processed['resonance_wavelength'],
                result.timestamp
            )
        
        # Update UI
        self.emit_ui_updates()
```

---

## Implementation Order

### ✅ Already Done
1. Pipeline registry system (`utils/processing_pipeline.py`)
2. Pipeline selector UI widget
3. AcquisitionService for vectorized spectrum acquisition
4. Baseline tracking with drift-aware Kalman

### 🎯 Next Steps (Priority Order)

#### Step 1: Create SpectrumProcessor (HIGH PRIORITY)
- Extract lines 1500-1525 from `_grab_data()`
- Move pipeline selection and fallback logic
- Add quality metrics and warnings
- **Impact**: Makes adding new processing algorithms trivial

#### Step 2: Create ChannelManager (MEDIUM PRIORITY)
- Extract channel loop logic (lines 1457-1582)
- Move all buffer management
- Centralize padding logic
- **Impact**: Simplifies multi-channel handling

#### Step 3: Refactor _grab_data() (HIGH PRIORITY)
- Use new SpectrumProcessor and ChannelManager
- Reduce to ~50 lines of orchestration
- **Impact**: Main loop becomes readable and maintainable

#### Step 4: Extract Hardware Coordinator (LOWER PRIORITY)
- Move device connection logic
- Centralize hardware error handling
- **Impact**: Better separation of concerns

---

## Migration Strategy (Zero Downtime)

### Approach: Gradual Extraction

```python
# Week 1: Add SpectrumProcessor alongside existing code
class AffiniteApp:
    def __init__(self):
        # ... existing code ...
        self.spectrum_processor = SpectrumProcessor(...)  # NEW
        
    def _grab_data(self):
        # ... existing code ...
        
        # NEW: Try new processor, fall back to old code
        try:
            processed = self.spectrum_processor.process_spectrum(...)
            fit_lambda = processed['resonance_wavelength']
        except Exception as e:
            logger.warning(f"New processor failed, using legacy: {e}")
            # OLD CODE: Keep existing pipeline logic as fallback
            fit_lambda = active_pipeline.find_resonance_wavelength(...)
```

```python
# Week 2: Verify new processor works, remove old code
class AffiniteApp:
    def _grab_data(self):
        # ... existing code ...
        
        # OLD CODE REMOVED
        # NEW: Direct use of processor
        processed = self.spectrum_processor.process_spectrum(...)
        fit_lambda = processed['resonance_wavelength']
```

---

## Benefits of Refactoring

### For Development
- **Easier to add features**: New pipelines just register themselves
- **Easier to test**: Small, focused components
- **Easier to debug**: Clear responsibility boundaries
- **Easier to optimize**: Profile individual components

### For Maintenance
- **Less code duplication**: Shared processing logic
- **Clear data flow**: Input → Processor → Output
- **Better error handling**: Centralized, consistent
- **Better logging**: Structured, component-specific

### For Future Features
- **ML integration**: Easy to add ML-based pipelines
- **Real-time QC**: Processor can emit quality warnings
- **Batch processing**: Use same processor for offline analysis
- **Multi-threading**: Easier to parallelize processing
- **Configuration**: Centralized processing parameters

---

## Code Size Reduction Estimate

### Current
- `main.py`: 3,530 lines
- `AffiniteApp` class: ~3,200 lines
- `_grab_data()`: 160 lines

### After Refactoring
- `main.py`: ~2,500 lines (-1,030 lines, -29%)
- `utils/spectrum_processor.py`: 300 lines (NEW)
- `utils/channel_manager.py`: 200 lines (NEW)
- `utils/hardware_coordinator.py`: 400 lines (NEW)
- `_grab_data()`: 50 lines (-110 lines, -69%)

**Net change**: +870 lines distributed across 3 new focused modules
**Maintainability**: Dramatically improved
**Testability**: Vastly improved

---

## Backwards Compatibility

All refactoring maintains:
- ✅ Same public API
- ✅ Same signal emissions
- ✅ Same UI behavior
- ✅ Same data formats
- ✅ Same configuration files

Zero user-facing changes - purely internal improvements.

---

## Testing Strategy

### Unit Tests (NEW)
```python
def test_spectrum_processor_fourier():
    processor = SpectrumProcessor(...)
    result = processor.process_spectrum(
        transmission=test_spectrum,
        wavelengths=test_wavelengths,
        channel='a'
    )
    assert 600 < result['resonance_wavelength'] < 800
    assert result['pipeline_used'] == 'fourier'

def test_spectrum_processor_fallback():
    processor = SpectrumProcessor(...)
    # Inject pipeline that raises exception
    processor.registry._pipelines['test'] = FailingPipeline()
    result = processor.process_spectrum(...)
    assert result['fallback_used'] == True
```

### Integration Tests (EXISTING)
- Keep all current manual testing procedures
- Software should behave identically
- Can add automated integration tests later

---

## Timeline Estimate

- **Step 1 (SpectrumProcessor)**: 4-6 hours
- **Step 2 (ChannelManager)**: 3-4 hours
- **Step 3 (Refactor _grab_data)**: 2-3 hours
- **Step 4 (Hardware Coordinator)**: 6-8 hours (optional)

**Total for Steps 1-3**: 9-13 hours of focused development

---

## Decision Points

### Do This Now If:
- ✅ You plan to add more processing algorithms
- ✅ You want to add ML-based peak detection
- ✅ You need better error handling and diagnostics
- ✅ You want to add real-time quality checks
- ✅ Testing is becoming painful

### Wait If:
- ❌ Software is stable and no new features needed
- ❌ No bandwidth for refactoring right now
- ❌ Only one person working on codebase (less collision risk)

---

## Recommendation

**Priority**: HIGH

Start with **Step 1 (SpectrumProcessor)** because:
1. Smallest scope, fastest value
2. Directly addresses "adding processing complexity"
3. Zero risk - can be added alongside existing code
4. Enables all future processing enhancements
5. Makes ML integration straightforward

After SpectrumProcessor is stable, reassess whether Steps 2-3 are needed based on:
- How much cleaner the code feels
- Whether you're still adding processing features
- Team feedback on maintainability

---

## Next Actions

1. **Review this plan** - Does this match your vision?
2. **Approve Step 1** - Create SpectrumProcessor?
3. **Define scope** - What processing features are coming next?
4. **Set timeline** - When should this happen?

Would you like me to start implementing Step 1 (SpectrumProcessor)?
