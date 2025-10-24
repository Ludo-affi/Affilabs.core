# Phase Development Plan - Version 0.2.0 Implementation

## Overview

Phased implementation of consensus peak tracking and adaptive filtering system for SPR kinetics optimization. This approach allows incremental testing and validation at each stage.

---

## Phase 0: Baseline Measurement ✅ COMPLETE

**Goal**: Establish current performance baseline

**Status**: COMPLETE (from user observations)

**Baseline Performance** (Centroid method):
- Channel B: ~10 RU peak-to-peak (WORST)
- Channel C: ~5 RU peak-to-peak (MEDIUM)
- Channel D: ~2 RU peak-to-peak (BEST)

**Analysis**: 5× variation between channels suggests peak shape sensitivity in centroid method.

---

## Phase 1: Consensus Peak Tracking ✅ READY FOR TESTING

**Goal**: Implement consensus method (centroid + parabolic) with fixed filtering

**Status**: IMPLEMENTATION COMPLETE - READY FOR TESTING

### Implementation Tasks

- [x] Create `CentroidTracker` class with adaptive thresholding
- [x] Create `ParabolicTracker` class for sub-pixel precision
- [x] Create `ConsensusTracker` class combining both methods
- [x] Add outlier detection (MAD-based) with predicted replacement
- [x] Add confidence scoring based on method agreement
- [x] Integrate into `spr_data_processor.py`
- [x] Update `settings.py` to use consensus method
- [ ] Test for 2 minutes baseline
- [ ] Compare to Phase 0 baseline

### Expected Improvements

| Channel | Baseline (Phase 0) | Target (Phase 1) | Mechanism |
|---------|-------------------|------------------|-----------|
| B | 10 RU | ≤6 RU | Parabolic handles narrow peaks better |
| C | 5 RU | ≤3 RU | Adaptive threshold maintains stable pixel count |
| D | 2 RU | ≤1.5 RU | Outlier rejection reduces spikes |

### Files Created

- `utils/consensus_peak_tracker.py` - Core consensus implementation
  - `CentroidTracker`: Adaptive threshold centroid method
  - `ParabolicTracker`: 3-point parabolic fit
  - `ConsensusTracker`: Weighted combination (60/40)

### Key Features

1. **Adaptive Thresholding**
   - Maintains 15-20 pixels regardless of peak shape
   - Binary search to find optimal threshold
   - Prevents narrow peaks from using too few pixels

2. **Outlier Detection**
   - Median Absolute Deviation (MAD) based
   - 3σ threshold (configurable)
   - Linear extrapolation for replacement

3. **Confidence Scoring**
   - Based on centroid-parabolic agreement
   - Penalizes disagreement >0.3nm
   - Flags low pixel counts (<10)

### Configuration

```python
# settings/settings.py
PEAK_TRACKING_METHOD = 'consensus'
CONSENSUS_SAVGOL_WINDOW = 7
CONSENSUS_SAVGOL_POLYORDER = 3
CONSENSUS_TARGET_PIXELS = 20
CONSENSUS_OUTLIER_THRESHOLD = 3.0
```

### Testing Procedure

1. Update settings to use consensus method
2. Run app for 2 minutes (baseline measurement)
3. Monitor logger for:
   - Outlier detection messages
   - Confidence scores
   - Method agreement
4. Calculate peak-to-peak for each channel
5. Compare to Phase 0 baseline

### Success Criteria

- ✅ Channel B: ≤6 RU (40% improvement)
- ✅ Channel C: ≤3 RU (40% improvement)
- ✅ Channel D: ≤1.5 RU (25% improvement)
- ✅ No crashes or errors
- ✅ Outlier detection working (check logs)
- ✅ Confidence scores reported

### Rollback Plan

If Phase 1 fails:
```python
# settings/settings.py
PEAK_TRACKING_METHOD = 'centroid'  # Revert to original
```

---

## Phase 2: Adaptive Filtering Infrastructure (Planned)

**Goal**: Add phase detection and manual phase control

**Status**: NOT STARTED

### Implementation Tasks

- [ ] Create `MeasurementPhase` enum
- [ ] Create `FILTER_SETTINGS` dictionary (phase-specific parameters)
- [ ] Create `AdaptiveFilterManager` class
- [ ] Add manual phase control (test toolbar in GUI)
- [ ] Test phase transitions and parameter changes

### Expected Behavior

- BASELINE: Heavy smoothing (11-pixel window) → Low noise
- ASSOCIATION: Minimal smoothing (5-pixel window) → Fast response
- Manual phase switching works correctly
- Logger shows phase transitions

### Testing Procedure

1. Add test toolbar with phase dropdown
2. Start in BASELINE, run 30 seconds
3. Switch to ASSOCIATION, run 30 seconds
4. Compare noise levels
5. Verify parameter changes in logs

### Success Criteria

- ✅ BASELINE noise lower than Phase 1
- ✅ ASSOCIATION noise higher but fast response
- ✅ Phase transitions work smoothly
- ✅ No crashes during phase changes

---

## Phase 3: Event Integration & Automatic Detection (Planned)

**Goal**: Full user workflow integration with injection buttons

**Status**: NOT STARTED

### Implementation Tasks

- [ ] Add event registration to `AdaptiveFilterManager`
- [ ] Implement automatic phase determination logic
- [ ] Create injection buttons in GUI (Sample/Buffer/Regen)
- [ ] Add phase indicator to GUI
- [ ] Test automatic phase transitions (timing-based)
- [ ] Optional: Pump integration for auto-detection

### Expected Behavior

- User clicks "Inject Sample" → INJECTION phase
- After 2s → ASSOCIATION phase (automatic)
- After 30s → EQUILIBRIUM phase (automatic)
- User clicks "Inject Buffer" → DISSOCIATION phase
- Phase indicator updates in real-time

### Testing Procedure

1. Click "Inject Sample" button
2. Monitor phase transitions:
   - T=0s: INJECTION
   - T=2s: ASSOCIATION
   - T=30s: EQUILIBRIUM
3. Click "Inject Buffer" button
4. Monitor dissociation phases
5. Verify noise levels match expectations

### Success Criteria

- ✅ User workflow intuitive (simple buttons)
- ✅ Automatic transitions work correctly
- ✅ No temporal lag during kinetics
- ✅ Phase indicator accurate
- ✅ Logger shows all transitions

---

## Phase 4: Dual Data Output & Temporal Smoothing (Planned)

**Goal**: Add Kalman filtering and raw+processed data streams

**Status**: NOT STARTED

### Implementation Tasks

- [ ] Create `SimpleKalmanFilter` class
- [ ] Integrate Kalman into `AdaptiveFilterManager`
- [ ] Add raw data output (no temporal smoothing)
- [ ] Add processed data output (with temporal smoothing)
- [ ] Update data export to include both streams
- [ ] Test Kalman convergence

### Expected Behavior

- BASELINE: Processed data smoother than raw
- ASSOCIATION: Processed = raw (no temporal smoothing)
- Data export contains both raw and processed columns
- Kalman converges within 5 seconds

### Testing Procedure

1. Run in BASELINE mode
2. Compare raw vs processed peaks → processed should be smoother
3. Click "Inject Sample"
4. Verify processed = raw during association
5. Export data and check CSV columns

### Success Criteria

- ✅ BASELINE: Temporal smoothing reduces noise further
- ✅ ASSOCIATION: No temporal smoothing (processed = raw)
- ✅ Data export working correctly
- ✅ Kalman filter stable

---

## Phase 5: Documentation & Integration (Planned)

**Goal**: Complete documentation and merge to master

**Status**: NOT STARTED

### Implementation Tasks

- [ ] Update `VERSION.md` with v0.2.0 release notes
- [ ] Create `ADAPTIVE_FILTERING_SYSTEM.md`
- [ ] Create `PEAK_TRACKING_OPTIMIZATION.md`
- [ ] Update `settings.py` with all parameters
- [ ] Remove Phase 2 test toolbar
- [ ] Final integration testing
- [ ] Git commit and push

### Documentation Files

1. **VERSION.md** - Complete v0.2.0 changelog
2. **ADAPTIVE_FILTERING_SYSTEM.md** - System design and usage
3. **PEAK_TRACKING_OPTIMIZATION.md** - Algorithm details
4. **PHASE_DEVELOPMENT_PLAN.md** - This file (development record)

### Success Criteria

- ✅ All documentation complete and accurate
- ✅ Version 0.2.0 ready for release
- ✅ Code pushed to GitHub
- ✅ No test/debug code in production

---

## Overall Timeline

| Phase | Implementation | Testing | Total | Status |
|-------|---------------|---------|-------|--------|
| 0 | - | 5 min | 5 min | ✅ COMPLETE |
| 1 | 30 min | 5 min | 35 min | 🚧 IN PROGRESS |
| 2 | 45 min | 10 min | 55 min | ⏸️ PLANNED |
| 3 | 60 min | 10 min | 70 min | ⏸️ PLANNED |
| 4 | 45 min | 10 min | 55 min | ⏸️ PLANNED |
| 5 | 60 min | - | 60 min | ⏸️ PLANNED |
| **Total** | **240 min** | **40 min** | **280 min (4.5 hrs)** | |

---

## Final Success Criteria (Version 0.2.0)

### Performance Targets

**Baseline Mode** (with full smoothing):
- Channel B: ≤4 RU peak-to-peak
- Channel C: ≤2 RU peak-to-peak
- Channel D: ≤1 RU peak-to-peak

**Kinetics Mode** (minimal smoothing):
- Channel B: ≤5 RU peak-to-peak
- Channel C: ≤3 RU peak-to-peak
- Channel D: ≤2 RU peak-to-peak
- No temporal lag during association/dissociation

### User Experience

- ✅ Simple workflow (3 buttons: Sample/Buffer/Regen)
- ✅ Clear phase indicator in GUI
- ✅ Both raw and processed data available
- ✅ No manual configuration needed

### Technical Requirements

- ✅ No crashes or errors
- ✅ <2ms computational overhead per channel
- ✅ Acquisition rate maintained (~1.2 Hz)
- ✅ Backward compatible with v0.1.0 data

---

## Development Notes

### 2025-10-21: Phase 1 Implementation Started

**Problem identified**: Enhanced method (FFT + polynomial derivative) caused binary/stepped signal due to discrete root-finding.

**Solution**: Consensus method using only continuous algorithms:
- Centroid: Weighted average (continuous)
- Parabolic: Analytical vertex (continuous)
- No discrete root-finding operations

**Key insight**: Peak shape sensitivity in centroid method is root cause of inter-channel variation (B: 10 RU vs D: 2 RU). Narrow peaks use fewer pixels → less noise averaging.

**Design decision**: Adaptive thresholding maintains consistent pixel count (15-20) across all peak shapes for uniform noise characteristics.

---

## References

- Original discussion: Peak-to-peak optimization for SPR kinetics
- Enhanced method rejection: Binary signal from derivative root-finding
- Consensus method design: Complementary error patterns
- Adaptive filtering rationale: Context-aware smoothing for kinetics

---

**Last Updated**: 2025-10-21
**Current Phase**: Phase 1 (Consensus Peak Tracking)
**Status**: Implementation in progress
