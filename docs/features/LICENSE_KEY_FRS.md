# License Key System FRS

**Version:** 1.0
**Status:** Implemented (v2.0.5-beta)
**Source files:** `affilabs/services/license_service.py`, `affilabs/dialogs/license_activation_dialog.py`, `affilabs/config/license_manager.py`, `tools/keygen.py`

---

## 1. Overview

A lightweight offline license gate that prevents casual redistribution of Affilabs.core without a paid license.

**Design principles:**
- One-time activation — customer enters key once, never asked again
- No internet required, ever
- No expiry — perpetual license
- Demo mode if no valid key — hardware blocked, demo dataset auto-loaded
- Simple, typeable key format

**Threat model:** Protection against casual sharing (copy a folder to a colleague). Not designed to resist adversarial reverse engineering. The HMAC secret is embedded in the binary; a determined attacker with a disassembler could extract it. Commercial enforcement (invoicing, serial-number-to-customer mapping) provides the actual binding. A cryptographically stronger online system will replace this in a future version.

---

## 2. Key Format

```
AFFI-XXXX-XXXX-XXXX
```

- 4-character prefix `AFFI` followed by 3 groups of 4 alphanumeric characters
- Total payload: **12 characters**, Base36 alphabet (`A–Z`, `0–9`)
- Dashes are presentational — stripped during validation

### Tier encoding

| First payload char | Tier |
|--------------------|------|
| `B` | base |
| `P` | pro |

The tier code is always the first character of the first group (position 5 in the full string, position 0 in the 12-char payload).

### Examples

```
AFFI-BXXX-XXXX-XXXX   ← base tier
AFFI-PXXX-XXXX-XXXX   ← pro tier
```

---

## 3. Cryptographic Scheme

### Algorithm

```python
tier_code  = "B" | "P"
nonce      = f"affilabs-{tier_code}"        # fixed per tier
message    = f"{tier_code}:{nonce}".encode()
mac        = hmac.new(_SECRET, message, hashlib.sha256).digest()
hmac_chars = base36_encode(mac[:8], length=11)   # 11 chars
payload    = tier_code + hmac_chars               # 12 chars
key        = f"AFFI-{payload[0:4]}-{payload[4:8]}-{payload[8:12]}"
```

### Base36 encoding

```python
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 36 chars

def base36_encode(data: bytes, length: int) -> str:
    n = int.from_bytes(data[:8], "big")
    chars = []
    for _ in range(length):
        chars.append(ALPHABET[n % 36])
        n //= 36
    return "".join(reversed(chars))
```

### Fixed-nonce design rationale

All customers on the same tier receive the same key. Tradeoffs:

| Implication | Impact |
|-------------|--------|
| One leaked key unlocks the tier | Acceptable — hardware serial number is the primary device identity; commercial enforcement (invoice records) handles misuse |
| No per-seat cryptographic binding | Acceptable for v1 — instruments ship to known customers; device registry tracks ownership |
| Simplifies activation UX | Customer only needs a single short key string; no separate nonce or customer ID to transmit |
| Future upgrade path | Per-customer keys are possible by appending a customer_id to the HMAC message — no UX change needed |

### Secret management

- `_SECRET`: 32 random bytes, hex-encoded, hardcoded in both `license_service.py` and `tools/keygen.py`
- Must be identical in both files
- **Never commit the real secret to version control** — use a placeholder in the repo, replace at build time
- To rotate: generate a new secret, update both files, regenerate all outstanding keys, notify customers

---

## 4. Activation Flow

### First launch (no `license.json`)

1. App initializes (`_init_services()` → `LicenseManager()` → `LicenseService._load()`)
2. `license.json` not found → `is_licensed = False`, `tier = "demo"`
3. Main window shown → `_update_demo_banner()` → amber banner appears
4. `_show_license_activation_dialog()` called → `LicenseActivationDialog` opens (modal)
5. Customer types key → auto-formatted as `AFFI-XXXX-XXXX-XXXX` in real time
6. "Activate" button enabled once 12 payload chars are present
7. Click "Activate" → `LicenseService.activate(key)` → HMAC validated
8. Success → `license.json` written → `license_activated` signal emitted → dialog closes → banner hidden
9. Failure → red error label shown → dialog stays open

### Storage (`license.json`)

Written to `get_writable_data_path("license.json")`:
- Dev mode: project root
- PyInstaller build: `%LOCALAPPDATA%\Affilabs\license.json`

```json
{
  "key": "AFFI-BXXX-XXXX-XXXX",
  "tier": "base",
  "activated_at": "2026-02-27T14:30:00+00:00"
}
```

### Subsequent launches

1. `LicenseService._load()` reads `license.json`
2. HMAC re-validated against stored key — tamper detection
3. Stored `tier` field cross-checked against HMAC-decoded tier — prevents tier field tampering
4. Valid → `is_licensed = True` → no dialog shown
5. Invalid or missing → Demo mode

---

## 5. Demo Mode

### Capabilities in Demo mode

| Feature | Demo | Base | Pro |
|---------|------|------|-----|
| Hardware connection | Blocked | ✅ | ✅ |
| Live acquisition | Blocked | ✅ | ✅ |
| Demo dataset in Edits tab | Auto-loaded | Optional | Optional |
| All Edits tab features | ✅ | ✅ | ✅ |
| Recording / export | ✅ | ✅ | ✅ |
| Sparq AI | ✅ | ✅ | ✅ |
| AnIML export | ❌ | ❌ | ✅ |
| Audit trail | ❌ | ❌ | ✅ |

### Demo banner spec

- **Position:** below `TransportBar`, above `content_stack` in `right_layout`
- **Height:** 30px fixed
- **Background:** `#FFFBEC` (amber tint)
- **Border:** 1px bottom, `#F0C840`
- **Text:** "Demo Mode — hardware connection disabled."
- **Link button:** "Enter License Key" (`#007AFF`, underline, flat)
- **Object name:** `DemoBanner` (banner frame), `demo_activate_link` (button)

### Power button behaviour in Demo mode

- Clicking power button → `_show_license_activation_dialog()` called
- If user dismisses without activating → connection blocked, no state change
- Tooltip: "License required to connect hardware. Click to enter your license key."

### Demo data auto-load

`QTimer.singleShot(500, self._load_demo_data)` called when demo banner is shown. Loads `_data/demo/kinetics_demo.xlsx` into Edits tab.

---

## 6. Tier Capabilities

| Tier | Code | Features |
|------|------|----------|
| `demo` | — | Edits tab + demo dataset only; hardware blocked |
| `base` | `B` | Full hardware + acquisition + recording + Excel export |
| `pro` | `P` | base + AnIML export + audit trail + advanced analytics + batch processing |

Tier is enforced via `FeatureFlags` in `affilabs/config/feature_flags.py`. `LicenseManager.load_license()` returns the appropriate `FeatureFlags` instance.

---

## 7. Internal Key Generation

### Tool: `tools/keygen.py`

Never ships to customers. Run from the project root with the venv Python.

```bash
# Generate a base key
python tools/keygen.py --tier base

# Generate a pro key
python tools/keygen.py --tier pro

# Verify an existing key
python tools/keygen.py --verify AFFI-BXXX-XXXX-XXXX
```

Output is deterministic — same tier always produces the same key. Print it once and distribute to all customers of that tier.

### Distribution workflow

1. Customer purchases → invoice generated
2. Run `keygen.py --tier base` (or `--tier pro`) → copy the key
3. Paste key into purchase confirmation email
4. Customer enters key at first launch

---

## 8. Pre-Ship Checklist (license system)

**Do this once, before the first customer build is compiled.**

### Step 1 — Generate a real secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output (64 hex chars). Store it somewhere safe (password manager, internal doc). **Do not commit it to git.**

### Step 2 — Replace the placeholder secret in both files

In **`affilabs/services/license_service.py`**, replace the `_SECRET` hex string:

```python
_SECRET: bytes = bytes.fromhex(
    "PASTE_YOUR_64_HEX_CHAR_SECRET_HERE"
)
```

In **`tools/keygen.py`**, replace the same field with the identical value:

```python
_SECRET: bytes = bytes.fromhex(
    "PASTE_YOUR_64_HEX_CHAR_SECRET_HERE"
)
```

Both files must have the **exact same hex string**. A mismatch means keys generated by `keygen.py` will fail validation in the app.

### Step 3 — Generate and record the final customer keys

```bash
python tools/keygen.py --tier base
python tools/keygen.py --tier pro
```

Save both keys internally (e.g. Notion, password manager). These are the keys you'll paste into purchase confirmation emails.

### Step 4 — Verify round-trip

```bash
python tools/keygen.py --verify <base-key>   # should print VALID — tier: base
python tools/keygen.py --verify <pro-key>    # should print VALID — tier: pro
```

### Step 5 — Re-enable enforcement

In **`affilabs/services/license_service.py`**, delete the three dev-bypass lines at the top of `_load()`:

```python
# DELETE these 3 lines:
self._state = LicenseState(is_licensed=True, tier="pro", key="DEV", activated_at="")
logger.info("[License] Enforcement disabled (dev mode) — full access granted")
return
```

### Step 6 — Test the full flow on a clean machine

1. Delete any existing `license.json` from `%LOCALAPPDATA%\Affilabs\`
2. Launch app → activation dialog appears
3. Enter base key → activates, banner gone, hardware connects
4. Close and reopen → no dialog (persisted)
5. Enter a garbage key → red error shown
6. Click "Continue in Demo" → demo banner visible, power button blocked

### Secret rotation

If the secret is ever compromised:
1. Generate a new 32-byte secret
2. Update both files
3. Regenerate base and pro keys
4. Notify all existing customers with their new key

---

## 9. Security Notes

- **Threat model:** casual redistribution prevention, not adversarial bypass resistance
- **Secret storage:** embedded in binary — obfuscation level, not cryptographic secrecy
- **Tamper detection:** HMAC re-validated from stored key on every launch; `tier` field cross-checked
- **No replay attack surface:** no server, no token exchange, no nonce transmission
- **Dev bypass:** `_load()` has a 3-line bypass block — **must be removed before shipping**
- **Future:** online activation with per-device binding planned for v2.x enterprise tier

---

## 10. File Index

| File | Role |
|------|------|
| `affilabs/services/license_service.py` | Core HMAC validation, `license.json` storage, `LicenseState` |
| `affilabs/config/license_manager.py` | Shim preserving existing `main.py` call sites |
| `affilabs/dialogs/license_activation_dialog.py` | One-time key entry dialog (frameless, modal) |
| `affilabs/affilabs_core_ui.py` | `_build_demo_banner()`, banner widget in `right_layout` |
| `main.py` | `_show_license_activation_dialog()`, `_on_license_activated()`, `_update_demo_banner()`, hook in `_init_services()`, `_load_deferred_then_show()`, `_on_power_on_requested()` |
| `tools/keygen.py` | Internal CLI key generator (never distributed) |
