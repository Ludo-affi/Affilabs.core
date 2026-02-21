# Software License Strategy — Future Implementation

> Status: **Not implemented.** Revisit before commercial release.

## Recommended Approach: Instrument-Bound License Key

License keys are tied to the physical instrument's serial number (already available via `firmware_id` / `ctrl_type` at connect time). No activation server required for single-instrument deployments.

### Key Design
```
license_key = sign(instrument_serial + tier + expiry, private_key)
```
- `instrument_serial` — read from controller at connect (e.g. `PicoP4SPR-XXXX`)
- `tier` — `p4spr` | `p4pro` | `p4proplus`
- `expiry` — ISO date string, or `perpetual`
- Signature uses **Ed25519** (fast, small keys) via `cryptography` library
- Public key embedded in the compiled binary; private key never leaves AffiLabs

### Activation Flow
1. Customer receives `license.lic` file with instrument purchase (emailed or shipped on USB)
2. Software reads `config/license.lic` on startup
3. On hardware connect: `LicenseValidator` verifies signature against connected instrument serial
4. If valid: set feature flags on `ApplicationState`; if invalid/expired: show blocking dialog

### Feature Tier Enforcement
| Feature | P4SPR key | P4PRO key | P4PROPLUS key |
|---------|-----------|-----------|---------------|
| Manual injection | ✅ | ✅ | ✅ |
| Semi-automated method | ❌ | ✅ | ✅ |
| AffiPump control | ❌ | ✅ | ❌ |
| Internal pump control | ❌ | ❌ | ✅ |
| Sparq AI features | optional add-on tier | optional add-on tier | optional add-on tier |

### Implementation Touchpoints
| Component | Change needed |
|-----------|--------------|
| `affilabs/core/hardware_manager.py` | Call `LicenseValidator.validate(instrument_serial)` after connect, before emitting `hardware_connected` |
| `affilabs/app_state.py` | Add `license_tier: str`, `license_expiry: date \| None`, `license_valid: bool` fields |
| New: `affilabs/services/license_validator.py` | `LicenseValidator` — reads `config/license.lic`, verifies Ed25519 signature, returns `LicenseInfo` dataclass |
| `affilabs/affilabs_core_ui.py` | Gate Semi-Automated UI / pump controls behind `app_state.license_tier` check |
| NSIS installer | Bundle `license.lic` alongside installer or prompt path on first run |

### Alternative Options Considered

**Online activation (seats-based)**
- Calls an activation API (e.g. [keygen.sh](https://keygen.sh)) on first launch
- Records device fingerprint (CPU ID + MAC) server-side; enforces seat count
- Better for multi-seat lab licenses; requires internet on first activation
- N-day offline grace period recommended

**USB dongle**
- Safest against cracking; adds ~€20–50 hardware cost per unit
- Relevant since the instrument already ships with USB hardware
- Wibu CodeMeter or Sentinel SafeNet

**Installer-tied key (weakest)**
- Key entered during NSIS install, stored in registry, validated at launch
- Trivially bypassable — only viable with high customer trust

### Dependencies
```
cryptography>=41.0  # already in pyproject.toml via other deps — verify at impl time
```

### Notes
- A stolen license key is useless on a different instrument — serial binding is the natural anti-piracy mechanism for hardware-bundled software
- Grace period logic (e.g. allow 30 days after expiry with warning) should be decided before implementation
- Sparq AI features could be a separate optional `sparq_expires` field in the license payload, enabling upsell without re-keying the base license
