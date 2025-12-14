# Critical Error Dialogs Implementation

## Overview
Implemented user-friendly error dialogs for critical calibration failures that provide clear problem descriptions, recovery actions, and appropriate support options. The system differentiates between generic user-facing messages and detailed technical diagnostics for internal support staff.

## Implementation Date
November 23, 2025

## Changes Made

### 1. Error Information Storage (`utils/spr_calibrator.py`)

**Added Error Tracking:**
- New `_last_critical_error` attribute initialized in `__init__`
- New `get_last_critical_error()` method to retrieve error details
- Error dictionary structure:
  ```python
  {
      'type': str,              # Error identifier (e.g., 'dark_noise_high')
      'user_message': str,      # Simple, user-friendly explanation
      'user_actions': list,     # Numbered troubleshooting steps
      'technical_details': str  # Technical diagnostic information (OEM/support)
  }
  ```

### 2. Critical Error Points Instrumented

#### A. Dark Noise Too High
- **Location:** Line ~5371 (Step 1 dark noise measurement)
- **Trigger:** Dark noise > 6,000 counts after 3 retry attempts
- **User Message:** "The sensor is detecting unexpected light when it should be completely dark. This usually indicates a light leak or LED control issue."
- **User Actions:**
  1. Check that the sensor cover is properly closed
  2. Ensure the sensor holder is not damaged or cracked
  3. Verify room lights are not shining directly on the sensor
  4. Wait 30 seconds and try again
- **Technical Details:** Dark noise count, threshold, expected value, retry attempts

#### B. Polarizer Invalid
- **Location:** Line ~6705 (Step 2B polarizer validation)
- **Trigger:** Missing servo_s_position or servo_p_position in device config
- **User Message:** "The polarizer needs to be configured before calibration can proceed. This is a one-time setup required for your device."
- **User Actions:**
  1. Contact Affinité support for polarizer calibration
  2. Support will guide you through the setup process
  3. This typically takes 5-10 minutes
- **Technical Details:** OEM polarizer positions not configured in device_config.json

#### C. No Signal Detected
- **Location:** Line ~6763 (Step 3 weakest channel identification)
- **Trigger:** All channels showing zero/dark signal
- **User Message:** "The system is not detecting any light from the sensor. This usually means the optical connections need attention."
- **User Actions:**
  1. Check that all 4 fiber cables are fully connected
  2. Verify the prism is installed in the sensor holder
  3. Check that the LED indicator light is ON
  4. Inspect fiber tips for damage or dirt
- **Technical Details:** Channel intensities array

#### D. LED Balancing Failed
- **Location:** Line ~3934 (Step 4 LED balancing validation)
- **Trigger:** All channels showing identical LED values or invalid pattern
- **User Message:** "The calibration process encountered an unexpected issue. This may require technical support to resolve."
- **User Actions:**
  1. Click 'Retry' to attempt calibration again
  2. If this error persists after 2-3 attempts, contact Affinité support
  3. Have your device serial number ready
- **Technical Details:** LED balancing validation failure details, ref_intensity values

#### E. LED Off Failure
- **Location:** Lines ~5149, ~5323 (Step 1 and Step 5 dark measurements)
- **Trigger:** Controller not responding to LED off commands
- **User Message:** "The system is having trouble controlling the LEDs. This indicates a communication issue with the controller."
- **User Actions:**
  1. Check that the controller USB cable is securely connected
  2. Try unplugging and reconnecting the controller
  3. Restart the software and try again
  4. Contact support if the problem persists
- **Technical Details:** LED off command failed (intensity=0 or 'lx' batch command)

#### F. Missing LED Values
- **Location:** Line ~5069 (Step 5 pre-validation)
- **Trigger:** ref_intensity is empty after Step 4
- **User Message:** "The calibration process encountered an internal error. Please restart the software and try again."
- **User Actions:**
  1. Close and restart the application
  2. Retry calibration after restart
  3. Contact support if the error continues
- **Technical Details:** self.state.ref_intensity empty (possible state corruption)

### 3. UI Dialog Handler (`Affilabs.core beta/main_simplified.py`)

**Updated `_on_calibration_failed()`:**
- Checks for critical error info using `calibrator.get_last_critical_error()`
- Shows detailed dialog if critical error exists
- Falls back to generic error message if no critical error info

**New `_show_critical_calibration_error_dialog()`:**
- Creates custom QMessageBox with:
  - Critical icon
  - User-friendly problem description
  - Numbered troubleshooting steps ("What to do:")
  - Collapsible "Technical Details" section (for support staff)
  - Three action buttons:
    1. **Retry Calibration** - Automatically triggers calibration again
    2. **Contact Support** - Opens https://affiniteinstruments.com/support
    3. **Close** - Dismisses dialog
- Window stays on top for visibility
- Logs user interactions (Retry vs Contact Support)

## User Experience Flow

### For End Users (Customers)
1. Calibration fails with critical error
2. Brief auto-closing notification (4 seconds)
3. Detailed error dialog appears with:
   - Clear explanation of what went wrong
   - Step-by-step troubleshooting instructions
   - "Retry Calibration" button for immediate action
   - "Contact Support" button for help
4. Technical details hidden in collapsible section

### For Internal Staff (OEM/Support)
1. Same user experience as customers
2. Click "Show Details" button to expand technical diagnostics
3. Technical section shows:
   - Exact error type identifier
   - Numeric values (thresholds, counts, intensities)
   - Step numbers and internal state information
   - Specific failure conditions
4. Copy technical details for bug reports or support tickets

## Design Principles

### User-Facing Messages
- **Simple language:** Avoid technical jargon
- **Problem-focused:** Explain what went wrong in plain terms
- **Actionable:** Provide concrete steps users can take
- **Reassuring:** Frame as solvable issues, not critical failures

### Technical Details
- **Comprehensive:** Include all diagnostic information
- **Specific:** Exact values, thresholds, and conditions
- **Traceable:** Reference step numbers and internal variables
- **Debug-ready:** Sufficient info for developers to diagnose

### Dialog Behavior
- **Non-blocking:** Auto-close notification followed by action dialog
- **Prominent:** Stays on top, critical icon
- **Action-oriented:** Retry button as default, support easily accessible
- **Progressive disclosure:** Technical details hidden until needed

## Error Type Coverage

| Error Type | Blocking | User Guidance | Technical Diagnostics | Recovery Path |
|------------|----------|---------------|----------------------|---------------|
| Dark noise high | ✅ | ✅ | ✅ | Retry + environment check |
| Polarizer invalid | ✅ | ✅ | ✅ | Contact support (one-time setup) |
| No signal | ✅ | ✅ | ✅ | Check connections |
| LED balancing failed | ✅ | ✅ | ✅ | Retry, then support |
| LED off failure | ✅ | ✅ | ✅ | Reconnect controller |
| Missing LED values | ✅ | ✅ | ✅ | Restart application |

## Testing Recommendations

### User Testing
1. Trigger each error type intentionally
2. Verify user messages are clear and actionable
3. Test "Retry Calibration" button functionality
4. Test "Contact Support" button opens correct URL
5. Verify technical details are hidden by default

### Support Testing
1. Expand technical details for each error type
2. Verify all diagnostic information is present
3. Test copy/paste of technical details
4. Verify technical details match log output

### Edge Cases
1. Multiple rapid calibration failures
2. Error during retry operation
3. Device disconnection during error dialog display
4. Missing calibrator object (graceful degradation)

## Benefits

### For Customers
- Clear understanding of what went wrong
- Actionable troubleshooting steps
- Immediate retry option
- Easy access to support

### For Support Staff
- Detailed diagnostic information
- Faster issue resolution
- Better bug reports
- Reduced back-and-forth with customers

### For Development
- Centralized error handling
- Consistent error reporting format
- Easy to add new error types
- Clear separation of user/technical info

## Future Enhancements

### Short Term
- Add error frequency tracking for diagnostics
- Implement error-specific help links
- Add "Export Diagnostics" button for support tickets

### Medium Term
- Create guided troubleshooting wizards for common errors
- Add inline video/image tutorials for hardware checks
- Implement auto-retry with exponential backoff

### Long Term
- Machine learning to predict error causes
- Remote diagnostics integration
- Automated hardware health checks

## Code Locations

### Modified Files
1. `utils/spr_calibrator.py`
   - Lines ~588: `_last_critical_error` initialization
   - Lines ~5371, ~6705, ~6763, ~3934, ~5149, ~5323, ~5069: Error storage points
   - Lines ~7660: `get_last_critical_error()` method

2. `Affilabs.core beta/main_simplified.py`
   - Lines ~1484: Updated `_on_calibration_failed()`
   - Lines ~1632: New `_show_critical_calibration_error_dialog()`

### Dependencies
- PySide6.QtWidgets (QMessageBox, QPushButton, QTextEdit)
- PySide6.QtCore (Qt)
- Standard library: webbrowser

## Maintenance Notes

### Adding New Error Types
1. Create error dictionary in calibrator at failure point:
   ```python
   self._last_critical_error = {
       'type': 'new_error_type',
       'user_message': "User-friendly explanation",
       'user_actions': ["Step 1", "Step 2"],
       'technical_details': "Diagnostic info"
   }
   ```

2. Error will automatically be displayed by existing UI handler

3. Update this documentation with new error type details

### Modifying Error Messages
- **User messages:** Keep simple, focus on symptoms and solutions
- **Technical details:** Add more context, never less
- **User actions:** Keep to 3-5 steps, most important first

### Dialog Customization
- Modify `_show_critical_calibration_error_dialog()` in main_simplified.py
- Keep "Retry" and "Contact Support" buttons for consistency
- Maintain technical details in collapsible section
