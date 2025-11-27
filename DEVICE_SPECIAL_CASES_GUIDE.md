# Device Special Cases - Quick Reference Guide

## Overview

The special cases system allows device-specific configurations to be applied automatically when a detector with a known serial number is connected. This is useful for:

- Hardware quirks or variations
- Calibration anomalies
- Custom modifications
- Early production units with different characteristics
- Beta test units
- RMA devices with known issues

## How It Works

1. **Hardware Connection**: When the power button is pressed, hardware scanning occurs
2. **Serial Number Check**: After successful connection, the detector serial number is checked against `SPECIAL_CASES` registry
3. **Automatic Application**: If found, special case parameters are automatically applied before normal operation
4. **Logging**: All special case applications are logged with details

## File Location

**Primary File**: `utils/device_special_cases.py`

## Adding a Special Case

### Method 1: Edit the Registry Directly

Open `utils/device_special_cases.py` and add to the `SPECIAL_CASES` dictionary:

```python
SPECIAL_CASES: Dict[str, Dict[str, Any]] = {
    "USB4C12345": {
        'description': 'Beta unit with modified LED board',
        'afterglow_correction': {
            'channel_a': 1.15,
            'channel_b': 1.08,
            'channel_c': 1.12,
            'channel_d': 1.05
        },
        'servo_positions': {
            's_pos': 45,
            'p_pos': 135
        },
        'led_intensity_scaling': {
            'a': 1.0,
            'b': 0.95,
            'c': 1.05,
            'd': 0.98
        },
        'integration_time': 50,
        'notes': 'Do not ship - engineering test unit'
    },

    # Add more special cases here...
}
```

### Method 2: Add Programmatically

```python
from utils.device_special_cases import add_special_case

add_special_case(
    'USB4C67890',
    'RMA unit with afterglow correction issue',
    afterglow_correction={
        'channel_a': 1.2,
        'channel_b': 1.1,
        'channel_c': 1.15,
        'channel_d': 1.08
    },
    notes='Returned for repair - needs optics realignment'
)
```

## Available Special Case Parameters

### Standard Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `description` | str | Brief description (required) | `'Beta unit with modified optics'` |
| `notes` | str | Additional notes | `'Contact engineering before shipping'` |

### Hardware Override Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `afterglow_correction` | dict | Per-channel afterglow multipliers | `{'channel_a': 1.15, 'channel_b': 1.08, ...}` |
| `led_intensity_scaling` | dict | Per-channel LED intensity scaling | `{'a': 1.0, 'b': 0.95, 'c': 1.05, 'd': 0.98}` |
| `servo_positions` | dict | Custom servo positions (degrees) | `{'s_pos': 45, 'p_pos': 135}` |
| `integration_time` | int | Integration time in milliseconds | `50` |

### Custom Parameters

You can add any custom parameters needed for specific cases:

```python
"USB4C11111": {
    'description': 'Custom firmware variant',
    'custom_calibration_target': 30000,
    'use_alternative_algorithm': True,
    'temperature_compensation': 1.05,
    'notes': 'Special order for customer XYZ'
}
```

## Removing a Special Case

### Method 1: Edit the Registry

Simply delete the entry from `SPECIAL_CASES` in `device_special_cases.py`

### Method 2: Remove Programmatically

```python
from utils.device_special_cases import remove_special_case

remove_special_case('USB4C12345')
```

## Viewing All Special Cases

To list all registered special cases in the log:

```python
from utils.device_special_cases import list_special_cases

list_special_cases()
```

## Testing a Special Case

1. Add the detector serial number to `SPECIAL_CASES`
2. Connect the device using the power button
3. Watch the logs for special case detection messages:

```
==============================================================
⚠️ SPECIAL CASE DETECTED - S/N: USB4C12345
   Description: Beta unit with modified LED board
   Notes: Do not ship - engineering test unit
==============================================================
📋 Special case will be applied during device initialization
   Overrides: afterglow_correction, servo_positions, led_intensity_scaling
```

## Log Messages to Look For

### Successful Special Case Application

```
✅ Hardware scan SUCCESSFUL - found 2 device(s)
==============================================================
⚠️ SPECIAL CASE DETECTED - S/N: USB4C12345
   Description: Beta unit with modified LED board
==============================================================
📋 APPLYING SPECIAL CASE CONFIGURATION
   Detector S/N: USB4C12345
   Description: Beta unit with modified LED board
==============================================================
Applying special case configuration...
  → Afterglow correction: {'channel_a': 1.15, ...}
  → Servo positions: S=45, P=135
  → LED intensity scaling: {'a': 1.0, 'b': 0.95, ...}
✅ Special case configuration applied to device
```

### No Special Case Found (Normal Operation)

```
No special case found for detector S/N: USB4C00000
```

## Example: Beta Unit with Afterglow Issue

```python
"USB4C99999": {
    'description': 'Beta unit - afterglow correction 20% higher',
    'afterglow_correction': {
        'channel_a': 1.20,
        'channel_b': 1.22,
        'channel_c': 1.18,
        'channel_d': 1.21
    },
    'notes': 'Beta tester: University Lab - Do not recall'
}
```

## Example: RMA Unit with Servo Position Issue

```python
"USB4C88888": {
    'description': 'RMA - polarizer servo positions recalibrated',
    'servo_positions': {
        's_pos': 42,
        'p_pos': 138
    },
    'notes': 'RMA#2024-123 - Servo mechanism replaced, DO NOT recalibrate'
}
```

## Example: Custom Production Variant

```python
"USB4C77777": {
    'description': 'Custom order - enhanced sensitivity variant',
    'integration_time': 100,  # 2x normal integration time
    'led_intensity_scaling': {
        'a': 0.5,  # Reduce LED power by 50%
        'b': 0.5,
        'c': 0.5,
        'd': 0.5
    },
    'notes': 'Custom order #CO-2024-456 - Enhanced sensitivity for low concentration'
}
```

## Best Practices

1. **Always include `description` and `notes`** - Future you will thank you
2. **Use full detector serial number** - Match exactly what appears in logs
3. **Document WHY** - Explain the reason for the special case
4. **Test thoroughly** - Verify the special case works as expected
5. **Keep registry clean** - Remove obsolete entries when devices are retired
6. **Log everything** - Special cases are logged automatically, review logs regularly

## Troubleshooting

### Special case not being applied?

1. Check detector serial number matches exactly (case-sensitive)
2. Verify detector is actually connected (check hardware scan logs)
3. Check for typos in `SPECIAL_CASES` dictionary
4. Ensure `device_special_cases.py` is in the correct location
5. Restart application to reload special cases

### Parameters not taking effect?

1. Verify parameter names match expected keys
2. Check if parameter is supported (see Available Parameters table)
3. Ensure values are correct type (dict, str, int, etc.)
4. Review logs for application errors

## Need Help?

- Check logs for detailed error messages
- Review `device_special_cases.py` for documentation
- Contact engineering team for complex cases
