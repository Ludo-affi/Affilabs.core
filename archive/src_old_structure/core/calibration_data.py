"""
CalibrationData - Type alias for LEDCalibrationResult.

DEPRECATED: CalibrationData was redundant with LEDCalibrationResult.
Now it's just a type alias to avoid breaking existing code.

Single source of truth: Use LEDCalibrationResult from models.led_calibration_result
"""

from models.led_calibration_result import LEDCalibrationResult

# Type alias: CalibrationData is just LEDCalibrationResult
CalibrationData = LEDCalibrationResult

# Expose for backward compatibility
__all__ = ['CalibrationData', 'LEDCalibrationResult']
