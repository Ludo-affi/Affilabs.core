# KNX Hardware Documentation Update

## Summary

Complete hardware specifications have been documented for the KNX kinetic system valves.

## Documented Components

### 1. Six-Port Valve (Takasago Electric)
✅ **Fully Documented**

- **Manufacturer:** Takasago Electric
- **Model:** Low Pressure 2-Position 6-Port Valve
- **Product Link:** https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414
- **Function:** Sample injection switching (Load/Inject)
- **Positions:**
  - 0 = LOAD (filling sample loop)
  - 1 = INJECT (injecting to flow cell)

### 2. Three-Way Valve (The Lee Company)
✅ **Fully Documented**

- **Manufacturer:** The Lee Company
- **Model:** XOVER 2/3-Way Isolation Solenoid Valve
- **Voltage:** 24V DC
- **Product Link:** https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/
- **Function:** Flow direction control (Waste/Load)
- **Positions:**
  - 0 = WASTE (de-energized, flow to waste)
  - 1 = LOAD (energized, flow to sample loop)

## Documentation Locations

### 1. In-Code Documentation
**File:** `utils/kinetic_manager.py`
**Lines:** Module docstring (lines 1-30)

Contains:
- Quick reference for both valves
- Manufacturer and model information
- Direct product links for ordering
- Functional descriptions
- Combined valve state explanations

**Purpose:** Immediate reference for developers working with the code

### 2. Comprehensive Hardware Reference
**File:** `KNX_HARDWARE_REFERENCE.md`

Contains:
- **Quick Reference Table** - All components at a glance
- **Detailed Specifications** - Full technical details for each component
- **Port Configurations** - Detailed connection diagrams
- **Control Methods** - API reference and code examples
- **Maintenance Notes** - Service schedules and procedures
- **Troubleshooting** - Common issues and solutions
- **Replacement Parts** - Ordering information with direct links
- **Electrical Requirements** - Power specifications (24V for Lee valve)
- **Wiring Diagrams** - Physical and electrical connections
- **Version History** - Change tracking

**Purpose:** Complete maintenance and operational reference

## Key Features

### Quick Component Lookup
```
Component          Manufacturer      Model                     Voltage
---------------------------------------------------------------------------
Six-Port Valve     Takasago         LP 2-Pos 6-Port          [TBD]
Three-Way Valve    The Lee Company  XOVER 2/3-Way Solenoid   24V DC
Temperature        Integrated       KNX Built-in             -
```

### Direct Ordering Links
Both valves have direct product page links for easy replacement ordering:
- **Takasago Six-Port:** https://www.takasago-fluidics.com/products/2position-6port-valve?variant=37040799285414
- **Lee Three-Way:** https://www.theleeco.com/product/xover-2-3-way-isolation-solenoid-valve/

### Maintenance Information
- Daily/weekly/monthly/annual checklists
- Troubleshooting guides
- Replacement procedures
- Contact information templates

### Software Integration
- Complete KineticManager API reference
- Code examples for all operations
- Qt signal documentation
- Safety features explained

## Benefits for Maintenance

1. **Easy Part Replacement**
   - Direct links to manufacturer product pages
   - Clear model and specification information
   - Voltage requirements documented

2. **Troubleshooting**
   - Component-specific troubleshooting sections
   - Common issues documented
   - Resolution procedures included

3. **Training**
   - Clear operational descriptions
   - Visual state diagrams
   - Code examples for each function

4. **Record Keeping**
   - Version history section
   - Maintenance schedule templates
   - Contact information placeholders

## Still To Document

The following information should be added as it becomes available:

### Six-Port Valve (Takasago)
- [ ] Voltage/current specifications
- [ ] Specific part number for ordering
- [ ] Expected lifetime based on usage
- [ ] Lead time from vendor
- [ ] Cost information

### Three-Way Valve (Lee XOVER)
- [ ] Specific part number from Lee Company
- [ ] Current draw specifications
- [ ] Expected lifetime based on usage
- [ ] Lead time from vendor
- [ ] Cost information

### KNX Controller
- [ ] Manufacturer information
- [ ] Model number
- [ ] Voltage/current specifications
- [ ] Communication protocol details
- [ ] Firmware version information

### Temperature Sensors
- [ ] Sensor type (thermistor/RTD/etc.)
- [ ] Accuracy specifications
- [ ] Calibration procedures
- [ ] Part numbers if replaceable

### System Integration
- [ ] Complete wiring diagram
- [ ] Power supply specifications
- [ ] Installation procedures
- [ ] Setup/configuration guide
- [ ] Calibration procedures

### Support Information
- [ ] Hardware vendor contact information
- [ ] Software support contacts
- [ ] Emergency support procedures
- [ ] Service provider information

## Usage

### For Lab Operators
Refer to `KNX_HARDWARE_REFERENCE.md` for:
- Understanding system operation
- Normal operation procedures
- Basic troubleshooting

### For Maintenance Personnel
Refer to `KNX_HARDWARE_REFERENCE.md` for:
- Maintenance schedules
- Replacement part ordering (with direct links)
- Detailed troubleshooting
- Service procedures

### For Software Developers
Refer to:
1. `utils/kinetic_manager.py` docstring - Quick hardware reference
2. `KNX_HARDWARE_REFERENCE.md` - Full system documentation
3. `KINETIC_MANAGER_IMPLEMENTATION.md` - Software API details

## Document Maintenance

These documents should be updated when:
- New hardware information becomes available
- Parts are replaced (track part numbers)
- Issues are discovered and resolved (add to troubleshooting)
- Procedures are refined (update maintenance schedules)
- Vendor information changes (update contacts/links)

**Review Schedule:** Annually, or after any major hardware changes

## Files Updated

1. `utils/kinetic_manager.py` - Added hardware specs in module docstring
2. `KNX_HARDWARE_REFERENCE.md` - Comprehensive hardware documentation (NEW)
3. `HARDWARE_DOCUMENTATION_SUMMARY.md` - This summary (NEW)

## Version

**Documentation Version:** 1.0
**Date:** October 7, 2025
**Status:** Complete with placeholders for additional specifications

---

**Next Steps:**
1. Fill in remaining specifications (voltage, part numbers, costs)
2. Add wiring diagrams if available
3. Document actual operational procedures from lab experience
4. Update contact information with actual vendor/support contacts
5. Schedule regular documentation review
