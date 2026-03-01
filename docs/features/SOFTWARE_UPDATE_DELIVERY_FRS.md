# SOFTWARE_UPDATE_DELIVERY_FRS — Update Delivery & Installation

**Source:** `_build/installer.nsi`, `_build/Affilabs-Core.spec`, `version.py`
**Consumed by:** Field deployment, customer support, release workflow
**Version:** Affilabs.core v2.0.5 beta
**Status:** Manual update path implemented. Auto-update not yet implemented.

---

## 1. Overview

Two update delivery modes exist depending on what changed in the release:

| Mode | When to use | Customer action |
|------|-------------|-----------------|
| **Drop-in exe** | Patch hotfix — only `Affilabs-Core.exe` changed | Replace one file |
| **Full installer** | Minor/major version — new bundled files, new configs, new Zadig | Run new `Setup.exe` |

User data is never at risk in either mode (see §4).

---

## 2. Drop-in Exe (Patch Hotfix)

### Use when
- Bug fix or performance improvement
- No new bundled files (Zadig, detector profiles, config files)
- `PRODUCT_VERSION` patch digit increments (e.g. 2.0.4 → 2.0.5)

### Delivery
Ship `Affilabs-Core.exe` via email / shared link / USB stick.

### Customer steps
1. Close AffiLabs.core (power-off button or window X)
2. Navigate to install folder (default: `C:\Program Files\Affilabs\Affilabs-Core\`)
3. Replace `Affilabs-Core.exe` with the new file
4. Launch as normal

### Notes
- No UAC required if replacing a file in a user-writable location; UAC prompt appears if in `Program Files` (expected)
- Zadig, device profiles, and all other files in the install folder are untouched

---

## 3. Full Installer Re-run (Minor / Major Version)

### Use when
- New bundled files required (new Zadig, new detector profile, new config)
- Minor or major version bump (e.g. 2.0.x → 2.1.0)
- Registry entries or Start Menu shortcuts changed

### Delivery
Ship `Affilabs-Core-Setup-X.Y.Z.exe` via email / shared link / USB stick.

### Customer steps
1. Close AffiLabs.core
2. Run the new `Setup.exe` — accepts UAC prompt
3. NSIS overwrites only the files explicitly listed in `SecMain` (`Affilabs-Core.exe`, `zadig.exe`)
4. All other files in `$INSTDIR` are untouched
5. Launch as normal — Zadig re-run prompt appears; safe to skip if driver was already installed

### NSIS re-install behavior
The installer does **not** run `RMDir /r` before installing — it performs an in-place overwrite of listed files only. No uninstall step required between versions.

---

## 4. User Data Safety

Recording data is stored **in memory only** during a session. No user experiment data is written to the install folder at any point. Files written by the app:

| Data | Location | Survives update? |
|------|----------|-----------------|
| Exported xlsx/csv | User-chosen path (Documents, Desktop, etc.) | ✅ Always |
| Device config (`device_config.json`) | `config/devices/{SERIAL}/` (relative to install or AppData) | ✅ Not touched by installer |
| Logs | `logs/` or `AppData` | ✅ Not touched by installer |
| In-memory recording (not yet exported) | RAM only | ⚠️ Lost on any close |

**Rule:** Instruct customers to export data before closing the app. An update cannot cause data loss for already-exported files.

---

## 5. Post-Update USB Spectrometer Edge Case

On hard crash (Task Manager kill, power loss), libusb may retain a USB claim on the spectrometer. The spectrometer will appear disconnected on next launch even after a successful update.

**Resolution:** Unplug and replug the spectrometer USB cable. The driver (Zadig/WinUSB) does not need to be reinstalled.

This is a Windows/libusb platform behavior, not an installer or update issue.

---

## 6. Version Identification

Version is defined in `VERSION` (plain text) and `version.py` (imported at runtime). The installer reads `PRODUCT_VERSION` from the NSIS script header — these three must be kept in sync before building.

```
VERSION          ← plain text, read by pyproject.toml and CI
version.py       ← imported by main.py for About dialog / window title
_build/installer.nsi  !define PRODUCT_VERSION "X.Y.Z"
```

Current: `2.0.5`

---

## 7. Planned: Auto-Update (Not Implemented)

Future: App checks a version endpoint on launch and prompts user to download + install.

Design sketch:
- `GET https://affinitelabs.com/releases/latest.json` → `{ "version": "X.Y.Z", "url": "...", "sha256": "..." }`
- Compare against `version.py` at startup
- On newer version: Sparq bubble or modal prompt with "Download & Install" button
- Download to temp, verify SHA-256, launch new installer with `/S` (silent) flag, exit current app
- Implementation estimate: ~1 day

**Blocked on:** CDN / release endpoint infrastructure.
