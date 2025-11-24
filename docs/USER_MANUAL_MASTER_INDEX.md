# User Manual & Documentation Master Index

**Purpose:** Central reference for all documentation needed to write user manuals, technical guides, and support documentation.

**Last Updated:** November 23, 2025

---

## 📖 Documentation Categories

### 1. Hardware & Connection
**User Manual Sections:** Getting Started, Hardware Setup, Device Connection

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| Power button behavior | `README_HARDWARE_BEHAVIOR.md` | ✅ Complete | 2.1 Connecting Device |
| Hardware scanning | `README_HARDWARE_BEHAVIOR.md` | ✅ Complete | 2.2 Device Detection |
| Device type identification | `HARDWARE_CONNECTION_LOGIC_FIX.md` | ✅ Complete | Appendix A: Device Types |
| Connection troubleshooting | `README_HARDWARE_BEHAVIOR.md` | ✅ Complete | 9. Troubleshooting |

**Key User-Facing Features:**
- Click gray power button → Searches for hardware → Turns green when connected
- Clicking green power button → Prompts for confirmation → Disconnects safely
- Scanning while connected → Reports status (won't disconnect)
- Auto-detection of P4SPR, P4SPR+KNX, ezSPR, P4PRO configurations

---

### 2. Device Configuration & Storage ⭐ NEW
**User Manual Sections:** Device Setup, Configuration Management, Backup & Restore

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| **EEPROM portable backup** | **`EEPROM_DEVICE_CONFIG_SPEC.md`** | ✅ Spec complete | **3. Device Configuration** |
| **EEPROM implementation** | **`EEPROM_IMPLEMENTATION_SUMMARY.md`** | ✅ Backend ready | **3.4 Configuration Backup** |
| Device config dialog | `DEVICE_CONFIG_STATUS.md` | ⚠️ Needs UI port | 3.1 Initial Setup |
| JSON vs EEPROM storage | `EEPROM_DEVICE_CONFIG_SPEC.md` | ✅ Complete | 3.5 Storage Architecture |

**Key User-Facing Features:**
- **Plug-and-play**: Factory-calibrated devices work immediately (EEPROM pre-configured)
- **Portability**: Move device between computers without reconfiguration
- **Auto-recovery**: If JSON deleted/corrupted, automatically restores from EEPROM
- **Manual backup**: "Push to EEPROM" button (optional UI feature)
- **Transparent operation**: Users don't need to know about EEPROM vs JSON

**Configuration Items Stored:**
- LED PCB model (Luminus Cool White or Osram Warm White)
- Optical fiber diameter (100µm or 200µm)
- Polarizer type (barrel or round)
- Servo positions (S and P mode angles)
- LED intensities (A, B, C, D channels)
- Integration time and scan count

**User Workflow:**
1. **First-time setup**: Device config dialog prompts for hardware details
2. **Calibration**: LED intensities auto-optimized and saved
3. **Auto-backup**: Configuration synced to EEPROM automatically
4. **Move to new computer**: Plug in device → Software reads EEPROM → Creates JSON → Ready to use

**Troubleshooting:**
- "No configuration found" → Device will load from EEPROM or prompt for setup
- "Configuration mismatch" → JSON vs EEPROM out of sync → Software prefers JSON
- "EEPROM write failed" → Check controller firmware version (needs update)

---

### 3. Calibration Systems
**User Manual Sections:** Calibration, Quality Control, Validation

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| Calibration sequence | `CALIBRATION_MASTER.md`, `led_calibration.py` | ✅ Complete | 4.0 Calibration Overview |
| Afterglow correction | `CALIBRATION_SYSTEMS_SUMMARY.md` | ✅ Complete | 4.1 Afterglow Calibration |
| S/P orientation validation | `CALIBRATION_SYSTEMS_SUMMARY.md` | ✅ Complete | 4.2 Polarizer Validation |
| LED intensity optimization | `CALIBRATION_SYSTEMS_SUMMARY.md` | ✅ Complete | 4.3 LED Calibration |
| Calibration workflow | `CALIBRATION_SYSTEMS_SUMMARY.md` | ✅ Complete | 4. Calibration Guide |
| Servo position calibration | `SERVO_CALIBRATION_MASTER_REFERENCE.md` | ✅ Complete | 4.4 Servo Calibration |
| Polarizer types | `S_POL_P_POL_SPR_MASTER_REFERENCE.md` | ✅ Complete | 4.5 Polarizer Types |

**Calibration Sequence (User Flow)**:
1. **Connect Hardware** → Device detected and identified
2. **Load Configuration** → Check device_config.json for servo positions
3. **Decision Point**:
   - **If servo positions exist** → Fast path: LED calibration only (~30-60 seconds)
   - **If servo positions missing** → Servo calibration first (method depends on polarizer type)
     - Barrel: ~1.4 minutes (simple window detection)
     - Circular: ~13 measurements (quadrant search, water required)
4. **LED Calibration** → Common path for all polarizer types (~30-60 seconds)
5. **Ready** → Press Start button to begin measurements

**Key User-Facing Features:**
- **Pre-Calibration Checklist**: Water/buffer required, prism installed, no bubbles, temperature stable
- **Fast Path**: If device previously calibrated, skips servo calibration
- **OEM Calibration**: Factory-level calibration with spectral reference
- **Afterglow correction**: Compensates for LED phosphor decay
- **S/P validation**: Fool-proof detection of correct polarizer orientation
- **Auto-prompts**: Software suggests missing calibrations
- **Progress Dialog**: Shows checklist and calibration status

---

### 4. User Interface
**User Manual Sections:** Software Interface, Features, Controls

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| UI adapter system | `UI_ADAPTER_EXAMPLES.md` | ✅ Complete | Developer Guide |
| UI adapter API | `UI_ADAPTER_REFERENCE.md` | ✅ Complete | Developer Guide |
| Main window layout | `affilabs_core_ui.py` | ✅ Complete | 5. Software Overview |

---

### 5. Measurement & Data Acquisition
**User Manual Sections:** Taking Measurements, Data Analysis, Experiment Setup

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| Acquisition modes | TBD | 🔜 Needs doc | 6. Measurement Modes |
| Data recording | TBD | 🔜 Needs doc | 6.2 Data Recording |
| Export formats | TBD | 🔜 Needs doc | 6.4 Data Export |

---

### 6. Maintenance & Troubleshooting
**User Manual Sections:** Maintenance, Troubleshooting, Support

| Topic | Source Document | Status | Manual Section |
|-------|----------------|--------|----------------|
| LED on-time tracking | `device_configuration.py` | ✅ Complete | 8.1 Maintenance Tracking |
| Cycle counters | `device_configuration.py` | ✅ Complete | 8.2 Usage Statistics |
| Error messages | TBD | 🔜 Needs doc | 9.1 Error Reference |
| Common issues | `README_HARDWARE_BEHAVIOR.md` | ✅ Complete | 9.2 Common Issues |

---

## 🎯 User Manual Outline (Proposed)

### Chapter 1: Introduction
- 1.1 Welcome
- 1.2 System Requirements
- 1.3 Safety Information
- 1.4 Support Contact

### Chapter 2: Getting Started
- 2.1 Installation
- 2.2 Connecting Your Device
- 2.3 First-Time Setup
- 2.4 Software Overview

### Chapter 3: Device Configuration ⭐ NEW
- 3.1 Initial Configuration Dialog
- 3.2 Hardware Parameters
  - LED PCB Model
  - Fiber Diameter
  - Polarizer Type
- 3.3 Servo Position Setup (S/P modes)
- 3.4 Configuration Backup (EEPROM)
  - Automatic Backup
  - Manual "Push to EEPROM"
  - Recovery from Backup
- 3.5 Storage Architecture (JSON vs EEPROM)
- 3.6 Moving Device Between Computers

### Chapter 4: Calibration
- 4.1 Why Calibration Matters
- 4.2 LED Intensity Calibration
- 4.3 Afterglow Correction
- 4.4 S/P Orientation Validation
- 4.5 OEM (Factory) Calibration
- 4.6 Calibration Troubleshooting

### Chapter 5: Taking Measurements
- 5.1 Acquisition Modes
- 5.2 Setting Parameters
- 5.3 Real-Time Monitoring
- 5.4 Recording Data

### Chapter 6: Data Analysis
- 6.1 Viewing Sensorgrams
- 6.2 Exporting Data
- 6.3 Post-Processing

### Chapter 7: Advanced Features
- 7.1 Batch Processing
- 7.2 Custom Scripts
- 7.3 API Integration

### Chapter 8: Maintenance
- 8.1 LED Lifetime Tracking
- 8.2 Usage Statistics
- 8.3 Cleaning & Care
- 8.4 Firmware Updates

### Chapter 9: Troubleshooting
- 9.1 Connection Issues
- 9.2 Calibration Problems
- 9.3 Configuration Recovery
- 9.4 Performance Issues
- 9.5 Error Messages Reference

### Appendices
- Appendix A: Device Types & Hardware Variants
- Appendix B: Technical Specifications
- Appendix C: File Formats
- Appendix D: Glossary
- Appendix E: Compliance & Certifications

---

## 📝 Writing Guidelines for User Manual

### Language & Style
- **Audience**: Lab technicians and scientists (technical but not programmers)
- **Tone**: Professional, clear, instructional
- **Voice**: Second person ("You can...", "To calibrate...")
- **Avoid**: Jargon, developer terms, implementation details

### Structure
- **Step-by-step**: Number sequential actions
- **Screenshots**: Annotate key UI elements
- **Warnings**: Highlight critical steps and potential issues
- **Tips**: Include best practices and shortcuts

### EEPROM Configuration (User Perspective)
**DON'T SAY:**
- "The system writes a 20-byte config packet to EEPROM address 0x00"
- "Configuration uses little-endian uint16 for servo positions"
- "XOR checksum validates data integrity"

**DO SAY:**
- "Your device automatically saves its configuration to built-in memory"
- "This allows your device to work on any computer without reconfiguration"
- "If your configuration file is deleted, the system will restore it automatically"

### Configuration Section (User Manual Draft)

---

## 🔍 Quick Reference: Documentation Lookup

**Need info about...**
- Connection behavior? → `README_HARDWARE_BEHAVIOR.md`
- EEPROM backup? → `EEPROM_DEVICE_CONFIG_SPEC.md` or `EEPROM_IMPLEMENTATION_SUMMARY.md`
- Calibration? → `CALIBRATION_SYSTEMS_SUMMARY.md`
- Device config dialog? → `DEVICE_CONFIG_STATUS.md`
- UI features? → `UI_ADAPTER_EXAMPLES.md`

---

## 📊 Documentation Status

| Category | Documents | Status | Ready for Manual |
|----------|-----------|--------|------------------|
| Hardware Connection | 3 docs | ✅ Complete | Yes |
| **Device Configuration** | **4 docs** | **✅ Backend ready** | **Yes** |
| Calibration Systems | 1 doc | ✅ Complete | Yes |
| UI & Integration | 2 docs | ✅ Complete | Dev guide only |
| Measurement/Data | 0 docs | ❌ Missing | No |
| Troubleshooting | Partial | ⚠️ Incomplete | Partial |

---

## 🚀 Next Steps for User Manual

### Immediate (Ready to Write)
1. ✅ Chapter 2: Getting Started (Hardware Connection)
2. ✅ Chapter 3: Device Configuration (EEPROM backup) ⭐ NEW
3. ✅ Chapter 4: Calibration (LED/Afterglow/S-P)
4. ✅ Chapter 9: Connection Troubleshooting

### Pending Documentation
1. 🔜 Measurement modes and data acquisition
2. 🔜 Data export formats
3. 🔜 Error message reference
4. 🔜 UI feature screenshots

### Future Enhancements
1. Video tutorials for calibration
2. Interactive troubleshooting flowchart
3. FAQ section from user support tickets

---

**Note:** This master index should be updated whenever new documentation is created or existing docs are significantly revised.
