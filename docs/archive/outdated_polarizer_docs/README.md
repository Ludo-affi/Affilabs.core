# Outdated Polarizer Documentation Archive

** WARNING: These files contain INCORRECT or OUTDATED information**

Archived on: November 23, 2025

## Why These Were Archived

These documents contain incorrect understanding of S-polarization and P-polarization:

**Incorrect Claims** (from old docs):
-  S-pol shows SPR dip
-  S-pol can be analyzed for FWHM
-  P-pol/S-pol ratio should show peak (actually shows dip)
-  S-mode is "perpendicular" for SPR (actually it's for LED reference)

**Correct Understanding** (see master reference):
-  S-pol: LED spectral profile + detector baseline (NO SPR information)
-  P-pol: Light after SPR interaction (contains SPR dip)
-  Transmission (P/S ratio): ONLY place to analyze SPR dip/FWHM
-  Water detection requires transmission calculation (not raw S or P)

## Current Documentation

Use this instead:
- ** docs/S_POL_P_POL_SPR_MASTER_REFERENCE.md**  AUTHORITATIVE SOURCE

## Files in This Archive

1. **POLARIZER_REFERENCE.md**
   - Status: Outdated physical understanding
   - Issue: Claims S-pol is "perpendicular" for SPR measurements

2. **POLARIZER_CALIBRATION_SYSTEM.md**
   - Status: Outdated algorithm description
   - Issue: Documents old auto_polarize method, not current implementation

3. **POLARIZER_*.md** (from root directory)
   - Status: Mixed - some sections outdated, some accurate
   - Issue: Inconsistent terminology and understanding across different documents

## Preservation Reason

These files are preserved for historical reference and to understand the evolution of the codebase. They should NOT be used for current development or troubleshooting.

---
**For current information, always refer to: docs/S_POL_P_POL_SPR_MASTER_REFERENCE.md**
