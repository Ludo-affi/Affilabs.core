# Power On Procedure

## Quick Start Guide for Affilabs.core

This guide walks you through the complete startup sequence from power-on to live data acquisition.

---

## Step-by-Step Instructions

### 1. Power On the System
- Press the **Power On** button (located in the top right corner of the interface)
- The system will attempt to connect to the hardware

### 2. Hardware Connection Check
- If the device is connected properly, the system will proceed to calibration
- If the hardware is **not found**, you will see a popup error message:
  - *"Cannot find the hardware"*
  - Check your USB connections and ensure the device is powered on
  - Press the Power On button again after resolving connection issues

### 3. Start Calibration
- A **Startup Calibration** popup will appear
- Press the **Start** button to begin the calibration sequence
- **Duration:** The calibration process takes approximately 1-2 minutes
- Do not interrupt the calibration process

### 4. Review QC Report
- Once calibration completes, review the **QC Report**
- Verify that all calibration parameters are within acceptable ranges
- Check for any warnings or errors

### 5. Begin Live Acquisition
- Close the QC Report dialog
- Press the **Start** button to begin live data acquisition
- The system will now display real-time sensorgram data

### 6. Recording Data
- **Default Mode:** The system starts in **Auto-Read Mode**
  - Data is displayed in real-time but NOT automatically saved
- **To Record Data:**
  1. Build a method in the **Method** tab (sidebar)
  2. Configure your experimental parameters
  3. Press **Record** when ready to begin data collection
  4. Data will be saved according to your method configuration

---

## Quick Reference

| Step | Action | Expected Time |
|------|--------|---------------|
| 1 | Press Power On | Instant |
| 2 | Hardware Check | 1-5 seconds |
| 3 | Run Calibration | 1-2 minutes |
| 4 | Review QC Report | User dependent |
| 5 | Start Live View | Instant |
| 6 | Record Data | Method dependent |

---

## Troubleshooting

**Cannot find hardware:**
- Check USB cable connections
- Verify device power supply
- Restart the software and try again

**Calibration fails:**
- Ensure no obstructions in the flow path
- Check that reagents are properly loaded
- Contact support if calibration repeatedly fails

**No data in Live View:**
- Verify calibration was successful
- Check that detector is properly initialized
- Review Settings tab for configuration issues

---

*Last Updated: February 3, 2026*
