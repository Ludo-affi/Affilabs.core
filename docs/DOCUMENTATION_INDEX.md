# Affilabs 0.1.0 - Documentation Index

**Quick navigation to all Affilabs documentation**

---

## 📖 Getting Started

### New Users Start Here
1. **[README.md](../README.md)** - Project overview and quick start
2. **[RELEASE_0.1.0.md](../RELEASE_0.1.0.md)** - What's new in version 0.1.0
3. **[VERSION.md](../VERSION.md)** - Version history and changelog

---

## 🔧 Setup & Configuration

### Hardware Setup
- **[OEM_CALIBRATION_TOOL_GUIDE.md](../OEM_CALIBRATION_TOOL_GUIDE.md)** - **START HERE** for polarizer configuration
- **[POLARIZER_REFERENCE.md](POLARIZER_REFERENCE.md)** - Comprehensive polarizer system guide
- **[PRODUCTION_SYSTEMS_README.md](../PRODUCTION_SYSTEMS_README.md)** - Production deployment guide

### Software Configuration
- **[SETTINGS_QUICK_REFERENCE.md](../SETTINGS_QUICK_REFERENCE.md)** - Application settings reference

---

## 🔬 User Guides

### Calibration
- **OEM Calibration** → See [OEM_CALIBRATION_TOOL_GUIDE.md](../OEM_CALIBRATION_TOOL_GUIDE.md)
- **System Calibration** → Automatic 8-step process (covered in README)
- **Troubleshooting** → See [POLARIZER_REFERENCE.md](POLARIZER_REFERENCE.md#troubleshooting)

### Measurements
- **Live SPR Measurements** → Covered in README
- **Data Export** → See Settings Reference
- **Diagnostic Tools** → [DIAGNOSTIC_VIEWER_QUICKSTART.md](../DIAGNOSTIC_VIEWER_QUICKSTART.md)

### Advanced Features
- **Pump Integration** → [CAVRO_PUMP_MANAGER.md](../CAVRO_PUMP_MANAGER.md)
- **Custom Protocols** → Contact support

---

## 🏗️ Technical Documentation

### System Architecture
- **[SIMPLIFIED_ARCHITECTURE_README.md](../SIMPLIFIED_ARCHITECTURE_README.md)** - System overview
- **[SMART_PROCESSING_README.md](../SMART_PROCESSING_README.md)** - Data processing pipeline
- **[WAVELENGTH_PIXEL_ARCHITECTURE.md](../WAVELENGTH_PIXEL_ARCHITECTURE.md)** - Wavelength calibration system

### Hardware Integration
- **[POLARIZER_REFERENCE.md](POLARIZER_REFERENCE.md)** - Polarizer hardware details
- **[CAVRO_PUMP_MANAGER.md](../CAVRO_PUMP_MANAGER.md)** - Pump control system

---

## 🔍 Troubleshooting

### Common Issues

**Calibration Problems**:
- Positions not loading → See [POLARIZER_REFERENCE.md](POLARIZER_REFERENCE.md#troubleshooting)
- Validation failures → Run OEM calibration tool
- Integration time issues → Check Settings Reference

**Measurement Problems**:
- Inverted transmittance → Polarizer positions swapped (see Polarizer Reference)
- Saturation → P-mode using wrong window (run OEM calibration)
- Poor signal quality → Check LED intensities and integration time

**Hardware Problems**:
- Serial port errors → Check COM port in Settings
- Spectrometer not found → Verify USB connection and drivers
- Pump not responding → See Cavro Pump Manager guide

### Getting Help
1. Check relevant documentation (see index above)
2. Review archived troubleshooting docs in `docs/archive/`
3. Check GitHub issues: https://github.com/Ludo-affi/ezControl-AI/issues

---

## 📚 Historical Documentation

**Archive Location**: `docs/archive/`

The archive contains 87 historical documents including:
- Development notes and debugging sessions
- Bug fixes and patches
- Performance optimization history
- Obsolete configuration guides

**Archive Index**: See [docs/archive/README.md](archive/README.md)

---

## 📝 Document Organization

### Root Directory (Essential Docs)
```
README.md                           - Main project documentation
VERSION.md                          - Version history
RELEASE_0.1.0.md                   - Release notes
POLARIZER_POSITION_FIX_COMPLETE.md - Critical fix documentation
OEM_CALIBRATION_TOOL_GUIDE.md      - Polarizer setup guide
PRODUCTION_SYSTEMS_README.md       - Deployment guide
SETTINGS_QUICK_REFERENCE.md        - Settings reference
DIAGNOSTIC_VIEWER_QUICKSTART.md    - Diagnostic tools
SIMPLIFIED_ARCHITECTURE_README.md  - Architecture overview
SMART_PROCESSING_README.md         - Data processing
WAVELENGTH_PIXEL_ARCHITECTURE.md   - Wavelength system
CAVRO_PUMP_MANAGER.md             - Pump integration
CLEANUP_COMPLETE.md                - Cleanup summary
```

### docs/ Directory (Consolidated Guides)
```
docs/
├── POLARIZER_REFERENCE.md         - Consolidated polarizer guide
├── DOCUMENTATION_INDEX.md         - This file
└── archive/                       - Historical documentation (87 files)
    └── README.md                  - Archive index
```

---

## 🔄 Recent Updates

**October 19, 2025** (v0.1.0 Cleanup):
- Archived 87 historical documents
- Consolidated polarizer documentation
- Created this index for easy navigation
- Improved documentation organization

---

## 📖 Reading Guide

### For New Users
1. Start with **README.md**
2. Run **OEM Calibration Tool** for polarizer setup
3. Review **Settings Quick Reference** for configuration
4. Start measuring!

### For System Administrators
1. Read **PRODUCTION_SYSTEMS_README.md**
2. Review **OEM_CALIBRATION_TOOL_GUIDE.md**
3. Check **POLARIZER_REFERENCE.md** for hardware details
4. Set up monitoring and backup procedures

### For Developers
1. Review **SIMPLIFIED_ARCHITECTURE_README.md**
2. Study **SMART_PROCESSING_README.md**
3. Check **WAVELENGTH_PIXEL_ARCHITECTURE.md**
4. Explore archived development notes in `docs/archive/`

### For Troubleshooting
1. Identify problem category (calibration/measurement/hardware)
2. Check relevant troubleshooting section
3. Review related documentation
4. Check archive for historical fixes if needed

---

## 🎯 Quick Links by Task

| Task | Documentation |
|------|--------------|
| **Install system** | README → Production Systems README |
| **Configure polarizer** | OEM Calibration Tool Guide |
| **Run calibration** | README (automatic process) |
| **Adjust settings** | Settings Quick Reference |
| **Integrate pump** | Cavro Pump Manager |
| **Diagnose issues** | Polarizer Reference → Troubleshooting |
| **Understand architecture** | Simplified Architecture README |
| **Process data** | Smart Processing README |
| **Review history** | docs/archive/ |

---

## 📞 Support Resources

- **Documentation**: This index and linked guides
- **GitHub**: https://github.com/Ludo-affi/ezControl-AI
- **Issues**: Report bugs via GitHub Issues
- **Version**: 0.1.0 "The Core"

---

**Index Version**: 1.0
**Last Updated**: October 19, 2025
**Affilabs Version**: 0.1.0
