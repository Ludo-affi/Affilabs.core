# Firmware Quick Reference

> **Canonical source:** `C:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Firmware\CLAUDE.md`
> **Git repo:** `https://github.com/Ludo-affi/pico-p4spr-firmware` · branch: `main`

---

## Latest Firmware — All Hardware Models

| Hardware | Marketing Name | Version | Source (.c) | Binary (.uf2) |
|----------|---------------|---------|-------------|---------------|
| **P4SPR** | SimplexSPR | **v2.4.1** | `p4spr/src/affinite_p4spr_v2.4.1.c` | `p4spr/releases/affinite_p4spr_v2.4.1.uf2` |
| **P4PRO** | SimplexFlow | **v2.3** | `P4PRO/src/affinite_p4pro_v2.3.c` | `P4PRO/releases/affinite_p4pro_v2.3.uf2` |
| **P4PROPLUS** | SimplexPro | **v2.3.4** | `p4proplus/src/affinite_p4proplus.c` | `p4proplus/releases/affinite_p4proplus_v2.3.4_FINAL.uf2` |

### Flash (bootloader mode)
```powershell
# With device in bootloader mode (hold BOOTSEL while plugging in), it mounts as RPI-RP2 (e.g. E:\)
Copy-Item "p4spr\releases\affinite_p4spr_v2.4.1.uf2" "E:\"       # P4SPR
Copy-Item "P4PRO\releases\affinite_p4pro_v2.3.uf2" "E:\"          # P4PRO
Copy-Item "p4proplus\releases\affinite_p4proplus_v2.3.4_FINAL.uf2" "E:\"  # P4PROPLUS
```

---

## Shipped Devices (March 2026)

| Serial | Customer | Country | Hardware | Firmware | Git Tag |
|--------|----------|---------|----------|----------|---------|
| AFFI09788 | Phase Photonics | Switzerland | P4SPR | v2.4.1 | `p4spr/v2.4.1` |
| AFFI09792 | AffiLabs (in-house) | — | P4SPR | v2.4.1 | `p4spr/v2.4.1` |
| AFFI10979 | Testa/NovaMedTech | Italy | P4SPR | v2.4.1 | `p4spr/v2.4.1` |

---

## Firmware Repo Structure (post-March 2026 reorg)

```
Firmware/
├── p4spr/           ← P4SPR (SimplexSPR) all files
├── P4PRO/           ← P4PRO (SimplexFlow) all files  [uppercase on disk, git sees p4pro/]
├── p4proplus/       ← P4PROPLUS (SimplexPro) all files
├── docs/            ← Shared: BUILD_GUIDE, CHANGELOG, FIRMWARE_VERSIONS
├── tools/           ← Shared: firmware_updater.py, build scripts
└── CLAUDE.md        ← Full AI reference (gotchas, tagging process, build env)
```

Each product folder follows the same layout:
```
<model>/
├── src/             ← CURRENT source (.c)
├── releases/        ← CURRENT binary (.uf2) + archive/ subfolder
├── src_archive/     ← Historical source versions
├── tools/           ← Model-specific scripts
└── docs/            ← Model-specific docs
```

---

## App ↔ Firmware Version Compatibility

| App Version | Minimum Firmware | Notes |
|-------------|-----------------|-------|
| v2.0.5.x | P4SPR v2.4.1 | CYCLE_SYNC command required |
| v2.0.5.x | P4PRO v2.3 | Internal pump on/off control |
| v2.0.5.x | P4PROPLUS v2.3.4 | Peristaltic pump support |

> **`USE_CYCLE_SYNC` flag** in `settings/settings.py` must be `True` for P4SPR v2.4.1+ devices. Older firmware falls back to EVENT_RANK mode automatically.

---

## Firmware Feature Flags Used by App

These constants in `settings/settings.py` and `affilabs/app_config.py` depend on firmware version:

| Constant | Firmware requirement | File |
|----------|---------------------|------|
| `USE_CYCLE_SYNC` | P4SPR ≥ v2.4 | `settings/settings.py` |
| `INTERNAL_PUMP_*` | P4PROPLUS ≥ v2.3 | `settings/settings.py` |
| `ctrl_type` detection | All | `affilabs/core/hardware_manager.py` |

Detection logic: `'p4proplus' in firmware_id.lower()` guards all P4PROPLUS-specific code paths.
