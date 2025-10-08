# Phase 4: Calibration Profile Management Refactoring

**Status**: Ready to implement  
**Priority**: HIGH (Quick win, high impact)  
**Estimated Effort**: 1-2 hours  
**Line Reduction**: ~200 lines from main.py  
**Risk Level**: LOW

---

## Executive Summary

Three calibration-related methods currently live in `main.py` that belong in the `SPRCalibrator` module:
1. **`save_calibration_profile()`** - 62 lines (lines 1859-1920)
2. **`load_calibration_profile()`** - 97 lines (lines 1921-2017)
3. **`auto_polarization()`** - 40 lines (lines 1408-1447)

**Total**: ~199 lines that should be moved to `utils/spr_calibrator.py`

These methods are pure calibration business logic that don't belong in the main application orchestration layer.

---

## Current State Analysis

### 1. save_calibration_profile() - 62 lines

**Location**: `main.py` lines 1859-1920

**Purpose**: Saves current calibration settings to a JSON profile file

**Current Implementation**:
```python
def save_calibration_profile(self, profile_name: str | None = None) -> bool:
    """Save current calibration settings to a profile file."""
    try:
        if profile_name is None:
            # Prompts user with QInputDialog
            ...
        
        # Create profiles directory
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        profiles_dir.mkdir(exist_ok=True)
        
        # Build calibration data dictionary
        calibration_data = {
            "profile_name": profile_name,
            "device_type": self.device_config["ctrl"],
            "timestamp": time.time(),
            "integration": self.integration,
            "num_scans": self.num_scans,
            "ref_intensity": self.ref_intensity.copy(),
            "leds_calibrated": self.leds_calibrated.copy(),
            "wave_min_index": self.wave_min_index,
            "wave_max_index": self.wave_max_index,
            "led_delay": self.led_delay,
            "med_filt_win": self.med_filt_win,
        }
        
        # Save to JSON file
        profile_path = profiles_dir / f"{profile_name}.json"
        with profile_path.open('w') as f:
            json.dump(calibration_data, f, indent=2)
        
        logger.info(f"Calibration profile saved: {profile_path}")
        show_message(...)
        return True
        
    except Exception as e:
        logger.exception(...)
        return False
```

**Data Dependencies**:
- Reads from: `self.integration`, `self.num_scans`, `self.ref_intensity`, `self.leds_calibrated`, `self.wave_min_index`, `self.wave_max_index`, `self.led_delay`, `self.med_filt_win`
- All of these already exist in `CalibrationState` class in `spr_calibrator.py`!

**UI Dependencies**:
- `QInputDialog.getText()` for profile name prompt
- `show_message()` for user feedback

---

### 2. load_calibration_profile() - 97 lines

**Location**: `main.py` lines 1921-2017

**Purpose**: Loads calibration settings from a JSON profile file

**Current Implementation**:
```python
def load_calibration_profile(self, profile_name: str | None = None) -> bool:
    """Load calibration settings from a profile file."""
    try:
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        
        if not profiles_dir.exists():
            show_message("No calibration profiles found.")
            return False
        
        if profile_name is None:
            # List available profiles
            profiles = [p.stem for p in profiles_dir.glob("*.json")]
            # Prompts user with QInputDialog.getItem()
            ...
        
        # Load from JSON file
        profile_path = profiles_dir / f"{profile_name}.json"
        with profile_path.open('r') as f:
            calibration_data = json.load(f)
        
        # Verify device type matches
        if calibration_data.get("device_type") != self.device_config["ctrl"]:
            if not show_message(..., yes_no=True):
                return False
        
        # Apply calibration data
        self.integration = calibration_data.get("integration", MIN_INTEGRATION)
        self.num_scans = calibration_data.get("num_scans", 1)
        self.ref_intensity = calibration_data.get("ref_intensity", ...)
        self.leds_calibrated = calibration_data.get("leds_calibrated", ...)
        self.wave_min_index = calibration_data.get("wave_min_index", 0)
        self.wave_max_index = calibration_data.get("wave_max_index", 0)
        self.led_delay = calibration_data.get("led_delay", LED_DELAY)
        self.med_filt_win = calibration_data.get("med_filt_win", 11)
        
        # Apply to device if connected
        if self.ctrl is not None and self.usb is not None:
            self.usb.set_integration(self.integration)
            for ch in CH_LIST:
                if ch in self.leds_calibrated:
                    self.ctrl.set_intensity(ch=ch, raw_val=self.leds_calibrated[ch])
        
        logger.info(...)
        show_message(...)
        return True
        
    except Exception as e:
        logger.exception(...)
        return False
```

**Data Dependencies**:
- Writes to: Same calibration state variables as save
- Hardware interaction: `self.usb.set_integration()`, `self.ctrl.set_intensity()`

**UI Dependencies**:
- `QInputDialog.getItem()` for profile selection
- `show_message()` for user feedback and confirmation

---

### 3. auto_polarization() - 40 lines

**Location**: `main.py` lines 1408-1447

**Purpose**: Automatically finds optimal polarizer positions for P and S modes

**Current Implementation**:
```python
def auto_polarization(self: Self) -> None:
    """Find polarizer positions."""
    try:
        if self.device_config["ctrl"] in DEVICES and self.ctrl is not None:
            # Set initial conditions
            self.ctrl.set_intensity("a", 255)
            self.usb.set_integration(max(MIN_INTEGRATION, self.usb.min_integration))
            
            # Define sweep parameters
            min_angle = 10
            max_angle = 170
            half_range = (max_angle - min_angle) // 2
            angle_step = 5
            steps = half_range // angle_step
            
            # Initialize intensity array
            max_intensities = np.zeros(2 * steps + 1)
            
            # Set starting position
            self.ctrl.servo_set(half_range + min_angle, max_angle)
            self.ctrl.set_mode("p")
            self.ctrl.set_mode("s")
            max_intensities[steps] = self.usb.read_intensity().max()
            
            # Sweep through angles
            for i in range(steps):
                x = min_angle + angle_step * i
                self.ctrl.servo_set(s=x, p=x + half_range + angle_step)
                self.ctrl.set_mode("s")
                max_intensities[i] = self.usb.read_intensity().max()
                self.ctrl.set_mode("p")
                max_intensities[i + steps + 1] = self.usb.read_intensity().max()
            
            # Find peaks and optimal positions
            peaks = find_peaks(max_intensities)[0]
            prominences = peak_prominences(max_intensities, peaks)
            i = prominences[0].argsort()[-2:]
            edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
            edges = np.array(edges)[:, i]
            
            # Calculate final positions
            p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
            self.ctrl.servo_set(s_pos, p_pos)
            logger.debug(f"final positions: s = {s_pos}, p = {p_pos}")
            
            self.new_default_values = True
            
    except Exception as e:
        logger.exception(f"Error aligning polarizer servo: {e}")
```

**Data Dependencies**:
- Hardware: `self.ctrl`, `self.usb`
- Reads: `self.device_config["ctrl"]`
- Writes: `self.new_default_values = True` (signals that default values should be updated)

**Usage Pattern**:
- Called during calibration process (line 762: `auto_polarize_callback = self.auto_polarization`)
- Passed to calibrator as `auto_polarize_callback` parameter
- Only executed if `self.auto_polarize` flag is True

---

## Existing Calibrator Module Structure

### CalibrationState Class (lines 65-125)

Already exists and contains all necessary state variables:

```python
class CalibrationState:
    def __init__(self):
        # Wavelength calibration
        self.wave_min_index = 0
        self.wave_max_index = 0
        self.wave_data: np.ndarray = np.array([])
        self.fourier_weights: np.ndarray = np.array([])
        
        # Integration and scanning
        self.integration = MIN_INTEGRATION
        self.num_scans = 1
        
        # LED intensities
        self.ref_intensity: dict[str, int] = {ch: 0 for ch in CH_LIST}
        self.leds_calibrated: dict[str, int] = {ch: 0 for ch in CH_LIST}
        
        # Reference data
        self.dark_noise: np.ndarray = np.array([])
        self.ref_sig: dict[str, np.ndarray | None] = {ch: None for ch in CH_LIST}
        
        # Results
        self.ch_error_list: list[str] = []
        self.is_calibrated = False
        self.calibration_timestamp: float | None = None
    
    def to_dict(self) -> dict:
        """Export calibration state to dictionary for saving."""
        # Already exports all calibration data
    
    def from_dict(self, data: dict) -> None:
        """Import calibration state from dictionary."""
        # Already handles loading
```

**Perfect Match**: The `CalibrationState` already has ALL the data needed for profiles!

### SPRCalibrator Class (lines 127-955)

Already has comprehensive calibration methods:
- `calibrate_wavelength_range()` - Step 1
- `calibrate_integration_time()` - Step 2-3
- `calibrate_led_s_mode()` - Step 4
- `measure_dark_noise()` - Step 5
- `measure_reference_signals()` - Step 6-7
- `calibrate_led_p_mode()` - Step 8
- `validate_calibration()` - Step 9
- `run_full_calibration()` - Orchestrates all 9 steps
- `log_calibration_results()` - Logs calibration to CSV
- `create_data_processor()` - Creates processor from calibration

**Missing**: Profile save/load methods and auto_polarization

---

## Refactoring Plan

### Step 1: Extend CalibrationState (if needed)

Add `med_filt_win` and `led_delay` to `CalibrationState` (they're missing):

```python
class CalibrationState:
    def __init__(self):
        # ... existing attributes ...
        
        # Filter settings
        self.med_filt_win = 11
        self.led_delay = LED_DELAY
```

Update `to_dict()` and `from_dict()` to include these fields.

### Step 2: Add Profile Management to SPRCalibrator

Add three new methods to `SPRCalibrator` class:

```python
def save_profile(
    self, 
    profile_name: str,
    device_type: str
) -> bool:
    """
    Save current calibration state to a profile file.
    
    Args:
        profile_name: Name for the profile
        device_type: Device type (e.g., 'picop4spr')
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        profiles_dir.mkdir(exist_ok=True)
        
        # Build calibration data from state
        calibration_data = {
            "profile_name": profile_name,
            "device_type": device_type,
            "timestamp": time.time(),
            "integration": self.state.integration,
            "num_scans": self.state.num_scans,
            "ref_intensity": self.state.ref_intensity.copy(),
            "leds_calibrated": self.state.leds_calibrated.copy(),
            "wave_min_index": self.state.wave_min_index,
            "wave_max_index": self.state.wave_max_index,
            "led_delay": self.state.led_delay,
            "med_filt_win": self.state.med_filt_win,
        }
        
        # Save to JSON
        profile_path = profiles_dir / f"{profile_name}.json"
        with profile_path.open('w') as f:
            json.dump(calibration_data, f, indent=2)
        
        logger.info(f"Calibration profile saved: {profile_path}")
        return True
        
    except Exception as e:
        logger.exception(f"Error saving calibration profile: {e}")
        return False


def load_profile(
    self, 
    profile_name: str,
    device_type: str | None = None
) -> tuple[bool, str]:
    """
    Load calibration state from a profile file.
    
    Args:
        profile_name: Name of profile to load
        device_type: Expected device type (for validation), optional
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
        profile_path = profiles_dir / f"{profile_name}.json"
        
        if not profile_path.exists():
            return False, f"Profile '{profile_name}' not found"
        
        # Load from JSON
        with profile_path.open('r') as f:
            calibration_data = json.load(f)
        
        # Verify device type if provided
        loaded_device = calibration_data.get("device_type")
        if device_type and loaded_device != device_type:
            warning = (f"Profile was created for {loaded_device} "
                      f"but current device is {device_type}")
            logger.warning(warning)
            # Return warning but allow loading
            return True, warning
        
        # Load into state
        self.state.integration = calibration_data.get("integration", MIN_INTEGRATION)
        self.state.num_scans = calibration_data.get("num_scans", 1)
        self.state.ref_intensity = calibration_data.get("ref_intensity", {ch: 0 for ch in CH_LIST})
        self.state.leds_calibrated = calibration_data.get("leds_calibrated", {ch: 0 for ch in CH_LIST})
        self.state.wave_min_index = calibration_data.get("wave_min_index", 0)
        self.state.wave_max_index = calibration_data.get("wave_max_index", 0)
        self.state.led_delay = calibration_data.get("led_delay", LED_DELAY)
        self.state.med_filt_win = calibration_data.get("med_filt_win", 11)
        
        logger.info(f"Calibration profile loaded: {profile_path}")
        return True, "Profile loaded successfully"
        
    except Exception as e:
        logger.exception(f"Error loading calibration profile: {e}")
        return False, f"Failed to load profile: {e}"


def list_profiles(self) -> list[str]:
    """
    Get list of available calibration profile names.
    
    Returns:
        List of profile names (without .json extension)
    """
    profiles_dir = Path(ROOT_DIR) / "calibration_profiles"
    if not profiles_dir.exists():
        return []
    return [p.stem for p in profiles_dir.glob("*.json")]


def apply_profile_to_hardware(
    self,
    ctrl: "PicoP4SPR | PicoEZSPR",
    usb: "USB4000",
    ch_list: list[str] | None = None
) -> bool:
    """
    Apply loaded calibration profile to hardware.
    
    Args:
        ctrl: SPR controller instance
        usb: USB4000 spectrometer instance
        ch_list: Channels to apply LED settings to (default: CH_LIST)
        
    Returns:
        True if applied successfully
    """
    try:
        if ch_list is None:
            ch_list = CH_LIST
        
        # Apply integration time
        usb.set_integration(self.state.integration)
        
        # Apply LED intensities
        for ch in ch_list:
            if ch in self.state.leds_calibrated:
                ctrl.set_intensity(ch=ch, raw_val=self.state.leds_calibrated[ch])
        
        logger.info("Calibration profile applied to hardware")
        return True
        
    except Exception as e:
        logger.exception(f"Error applying profile to hardware: {e}")
        return False


def auto_polarize(
    self,
    ctrl: "PicoP4SPR | PicoEZSPR",
    usb: "USB4000"
) -> tuple[int, int] | None:
    """
    Automatically find optimal polarizer positions for P and S modes.
    
    Uses peak detection to find the angles where maximum light transmission
    occurs for both polarization modes.
    
    Args:
        ctrl: SPR controller instance
        usb: USB4000 spectrometer instance
        
    Returns:
        Tuple of (s_pos, p_pos) if successful, None if failed
    """
    try:
        # Set initial conditions
        ctrl.set_intensity("a", 255)
        usb.set_integration(max(MIN_INTEGRATION, usb.min_integration))
        
        # Define sweep parameters
        min_angle = 10
        max_angle = 170
        half_range = (max_angle - min_angle) // 2
        angle_step = 5
        steps = half_range // angle_step
        
        # Initialize intensity array
        max_intensities = np.zeros(2 * steps + 1)
        
        # Set starting position
        ctrl.servo_set(half_range + min_angle, max_angle)
        ctrl.set_mode("p")
        ctrl.set_mode("s")
        max_intensities[steps] = usb.read_intensity().max()
        
        # Sweep through angles
        for i in range(steps):
            x = min_angle + angle_step * i
            ctrl.servo_set(s=x, p=x + half_range + angle_step)
            ctrl.set_mode("s")
            max_intensities[i] = usb.read_intensity().max()
            ctrl.set_mode("p")
            max_intensities[i + steps + 1] = usb.read_intensity().max()
        
        # Find peaks and optimal positions
        from scipy.signal import find_peaks, peak_prominences, peak_widths
        peaks = find_peaks(max_intensities)[0]
        prominences = peak_prominences(max_intensities, peaks)
        i = prominences[0].argsort()[-2:]
        edges = peak_widths(max_intensities, peaks, 0.05, prominences)[2:4]
        edges = np.array(edges)[:, i]
        
        # Calculate final positions
        p_pos, s_pos = (min_angle + angle_step * edges.mean(0)).astype(int)
        ctrl.servo_set(s_pos, p_pos)
        
        logger.info(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
        return s_pos, p_pos
        
    except Exception as e:
        logger.exception(f"Error during auto-polarization: {e}")
        return None
```

### Step 3: Update main.py to Use Calibrator Methods

Replace the three methods in `main.py` with thin wrappers that delegate to calibrator:

```python
def save_calibration_profile(self, profile_name: str | None = None) -> bool:
    """Save current calibration settings to a profile file."""
    try:
        # Handle UI prompt for profile name
        if profile_name is None:
            from PySide6.QtWidgets import QInputDialog
            profile_name, ok = QInputDialog.getText(
                self.main_window,
                "Save Calibration Profile",
                "Enter profile name:",
            )
            if not ok or not profile_name:
                return False
        
        # Delegate to calibrator
        if self.calibrator is None:
            show_message(
                msg="No calibration data to save. Please calibrate first.",
                msg_type="Warning",
            )
            return False
        
        success = self.calibrator.save_profile(
            profile_name=profile_name,
            device_type=self.device_config["ctrl"]
        )
        
        if success:
            show_message(
                msg=f"Calibration profile '{profile_name}' saved successfully!",
                msg_type="Information",
                auto_close_time=3,
            )
        else:
            show_message(
                msg="Failed to save calibration profile.",
                msg_type="Warning",
            )
        
        return success
        
    except Exception as e:
        logger.exception(f"Error in save_calibration_profile: {e}")
        return False


def load_calibration_profile(self, profile_name: str | None = None) -> bool:
    """Load calibration settings from a profile file."""
    try:
        # Get profile name from user if not provided
        if profile_name is None:
            from PySide6.QtWidgets import QInputDialog
            
            if self.calibrator is None:
                # Create temporary calibrator just to list profiles
                from utils.spr_calibrator import SPRCalibrator
                temp_calibrator = SPRCalibrator(
                    ctrl=None, usb=None, device_config=self.device_config
                )
                profiles = temp_calibrator.list_profiles()
            else:
                profiles = self.calibrator.list_profiles()
            
            if not profiles:
                show_message(
                    msg="No calibration profiles found.",
                    msg_type="Information",
                )
                return False
            
            profile_name, ok = QInputDialog.getItem(
                self.main_window,
                "Load Calibration Profile",
                "Select profile:",
                profiles,
                0,
                False,
            )
            if not ok:
                return False
        
        # Create calibrator if needed
        if self.calibrator is None:
            from utils.spr_calibrator import SPRCalibrator
            self.calibrator = SPRCalibrator(
                ctrl=self.ctrl,
                usb=self.usb,
                device_config=self.device_config
            )
        
        # Load profile
        success, message = self.calibrator.load_profile(
            profile_name=profile_name,
            device_type=self.device_config["ctrl"]
        )
        
        if not success:
            show_message(msg=message, msg_type="Warning")
            return False
        
        # Check for device mismatch warning
        if "was created for" in message:
            if not show_message(msg=f"{message}. Load anyway?", yes_no=True):
                return False
        
        # Apply to hardware if connected
        if self.ctrl is not None and self.usb is not None:
            self.calibrator.apply_profile_to_hardware(
                ctrl=self.ctrl,
                usb=self.usb,
                ch_list=CH_LIST
            )
        
        # Update main.py state from calibrator state
        self.integration = self.calibrator.state.integration
        self.num_scans = self.calibrator.state.num_scans
        self.ref_intensity = self.calibrator.state.ref_intensity.copy()
        self.leds_calibrated = self.calibrator.state.leds_calibrated.copy()
        self.wave_min_index = self.calibrator.state.wave_min_index
        self.wave_max_index = self.calibrator.state.wave_max_index
        self.led_delay = self.calibrator.state.led_delay
        self.med_filt_win = self.calibrator.state.med_filt_win
        
        show_message(
            msg=f"Calibration profile '{profile_name}' loaded successfully!",
            msg_type="Information",
            auto_close_time=3,
        )
        return True
        
    except Exception as e:
        logger.exception(f"Error in load_calibration_profile: {e}")
        show_message(
            msg=f"Failed to load calibration profile: {e}",
            msg_type="Warning",
        )
        return False


def auto_polarization(self) -> None:
    """Find polarizer positions using calibrator."""
    try:
        if self.device_config["ctrl"] not in DEVICES or self.ctrl is None:
            return
        
        # Create calibrator if needed
        if self.calibrator is None:
            from utils.spr_calibrator import SPRCalibrator
            self.calibrator = SPRCalibrator(
                ctrl=self.ctrl,
                usb=self.usb,
                device_config=self.device_config
            )
        
        # Delegate to calibrator
        result = self.calibrator.auto_polarize(ctrl=self.ctrl, usb=self.usb)
        
        if result is not None:
            s_pos, p_pos = result
            logger.debug(f"Auto-polarization complete: s={s_pos}, p={p_pos}")
            self.new_default_values = True
        
    except Exception as e:
        logger.exception(f"Error in auto_polarization: {e}")
```

**Key Points**:
- UI logic (dialogs) stays in main.py (proper layer separation)
- Business logic (file I/O, data validation) moves to calibrator
- Hardware application delegated to calibrator method
- State synchronization happens after loading

---

## Benefits of This Refactoring

### 1. **Separation of Concerns** ✅
- Calibration logic → SPRCalibrator
- UI/orchestration → main.py
- Clear boundaries between layers

### 2. **Testability** ✅
- Profile methods can be unit tested without UI
- Mock hardware interactions easily
- Validate file I/O independently

### 3. **Reusability** ✅
- Other code can use calibrator's profile methods
- Command-line tools can load profiles
- Batch operations possible

### 4. **Maintainability** ✅
- All calibration code in one module
- Easier to find and modify
- Consistent error handling

### 5. **Code Reduction** ✅
- ~199 lines removed from main.py (8% reduction)
- Projected: main.py → ~2255 lines
- Cleaner, more focused main.py

---

## Testing Strategy

### Unit Tests (spr_calibrator.py)

```python
def test_save_profile():
    """Test profile saving."""
    calibrator = SPRCalibrator(...)
    calibrator.state.integration = 5000
    calibrator.state.num_scans = 3
    
    success = calibrator.save_profile("test_profile", "picop4spr")
    assert success
    assert Path("calibration_profiles/test_profile.json").exists()


def test_load_profile():
    """Test profile loading."""
    calibrator = SPRCalibrator(...)
    success, msg = calibrator.load_profile("test_profile")
    
    assert success
    assert calibrator.state.integration == 5000
    assert calibrator.state.num_scans == 3


def test_list_profiles():
    """Test listing available profiles."""
    calibrator = SPRCalibrator(...)
    profiles = calibrator.list_profiles()
    
    assert "test_profile" in profiles


def test_auto_polarize():
    """Test auto-polarization (with mocked hardware)."""
    # Mock ctrl and usb
    result = calibrator.auto_polarize(mock_ctrl, mock_usb)
    
    assert result is not None
    s_pos, p_pos = result
    assert 10 <= s_pos <= 170
    assert 10 <= p_pos <= 170
```

### Integration Tests (main.py)

```python
def test_save_load_workflow():
    """Test full save/load workflow through main.py."""
    # Calibrate
    main_window.calibrate()
    
    # Save profile
    success = main_window.save_calibration_profile("integration_test")
    assert success
    
    # Modify state
    main_window.integration = 1000
    
    # Load profile
    success = main_window.load_calibration_profile("integration_test")
    assert success
    
    # Verify state restored
    assert main_window.integration == 5000
```

---

## Implementation Checklist

- [ ] **Step 1**: Update `CalibrationState` class
  - [ ] Add `med_filt_win` attribute
  - [ ] Add `led_delay` attribute
  - [ ] Update `to_dict()` method
  - [ ] Update `from_dict()` method

- [ ] **Step 2**: Add profile methods to `SPRCalibrator`
  - [ ] Implement `save_profile()`
  - [ ] Implement `load_profile()`
  - [ ] Implement `list_profiles()`
  - [ ] Implement `apply_profile_to_hardware()`
  - [ ] Implement `auto_polarize()`
  - [ ] Add necessary imports (json, Path, scipy.signal)
  - [ ] Add docstrings with type hints

- [ ] **Step 3**: Update `main.py`
  - [ ] Replace `save_calibration_profile()` with delegation wrapper
  - [ ] Replace `load_calibration_profile()` with delegation wrapper
  - [ ] Replace `auto_polarization()` with delegation wrapper
  - [ ] Test state synchronization after loading

- [ ] **Step 4**: Testing
  - [ ] Write unit tests for calibrator profile methods
  - [ ] Test save/load with real profiles
  - [ ] Test device type mismatch handling
  - [ ] Test auto_polarization with hardware
  - [ ] Verify UI dialogs work correctly
  - [ ] Test error handling paths

- [ ] **Step 5**: Documentation
  - [ ] Update spr_calibrator.py docstring
  - [ ] Document profile file format (JSON schema)
  - [ ] Add usage examples
  - [ ] Update REFACTORING_COMPLETE_SUMMARY.md

---

## Risks and Mitigations

### Risk 1: State Synchronization Issues

**Risk**: main.py and calibrator state getting out of sync

**Mitigation**:
- After loading profile, explicitly sync all state variables
- Use calibrator.state as single source of truth
- Document state ownership clearly

### Risk 2: Backward Compatibility

**Risk**: Existing saved profiles might not load

**Mitigation**:
- Use `.get()` with defaults when loading JSON
- Add profile version field for future changes
- Test with existing profile files before deployment

### Risk 3: Hardware Application Timing

**Risk**: Hardware commands might interfere with ongoing operations

**Mitigation**:
- Check if acquisition is running before applying profile
- Add safety checks in `apply_profile_to_hardware()`
- Log all hardware state changes

---

## Expected Outcome

### Before (main.py: 2454 lines)
```python
class MainWindow(QMainWindow):
    # ... 2454 lines including:
    def save_calibration_profile(self, ...):  # 62 lines
        # Profile save logic mixed with UI
        
    def load_calibration_profile(self, ...):  # 97 lines
        # Profile load logic mixed with UI
        
    def auto_polarization(self):  # 40 lines
        # Polarization logic in main
```

### After (main.py: ~2255 lines)
```python
class MainWindow(QMainWindow):
    # ... ~2255 lines
    def save_calibration_profile(self, ...):  # ~25 lines
        # UI only, delegates to calibrator
        
    def load_calibration_profile(self, ...):  # ~35 lines
        # UI only, delegates to calibrator
        
    def auto_polarization(self):  # ~15 lines
        # Thin wrapper, delegates to calibrator
```

### spr_calibrator.py (955 → ~1155 lines)
```python
class SPRCalibrator:
    # ... existing 955 lines ...
    
    # NEW: ~200 lines of profile management
    def save_profile(self, ...):  # ~35 lines
    def load_profile(self, ...):  # ~40 lines
    def list_profiles(self, ...):  # ~10 lines
    def apply_profile_to_hardware(self, ...):  # ~25 lines
    def auto_polarize(self, ...):  # ~50 lines
```

**Net Result**:
- main.py: 2454 → ~2255 lines (-199 lines, -8.1%)
- spr_calibrator.py: 955 → ~1155 lines (+200 lines, +20.9%)
- Total: 3409 → 3410 lines (neutral, but better organized)

---

## Next Steps After Phase 4

1. **Phase 5** (Optional): Data Acquisition Manager
   - Extract channel acquisition logic from _grab_data()
   - ~100 lines reduction, medium risk
   - Only if complexity vs benefit makes sense

2. **Phase 6** (Recommended): Kinetic Operations Manager
   - Extract regenerate(), flush(), inject() sequences
   - ~150 lines reduction, low risk
   - Good cleanup value

3. **Phase 7** (Complete Phase 3): Data I/O Widget Integration
   - Update datawindow.py and analysis.py
   - Complete Data I/O refactoring story
   - No impact on main.py line count

---

## Conclusion

**Phase 4 is a HIGH-PRIORITY, LOW-RISK refactoring** that:
- Moves ~199 lines of calibration logic to the proper module
- Improves separation of concerns (UI vs business logic)
- Enhances testability and maintainability
- Has clear benefits with minimal risk
- Can be completed in 1-2 hours

**Recommendation**: **Start with Phase 4 immediately** - it's a quick win that sets up the codebase for future improvements while delivering immediate value through better code organization.
