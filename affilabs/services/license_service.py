"""
LicenseService — offline HMAC-SHA256 license key validation.

Key format : AFFI-XXXX-XXXX-XXXX  (12 alphanumeric chars, Base36 A-Z0-9)
Tier codes : B = base  |  P = pro   (first char of 12-char payload)
No expiry. No internet. One-time activation.

Internal generation: tools/keygen.py (never ships to customer).
"""

from __future__ import annotations

import hmac
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from affilabs.utils.resource_path import get_writable_data_path
from affilabs.utils.logger import logger


# ---------------------------------------------------------------------------
# Secret — 32 random bytes, hex-encoded.
# IMPORTANT: replace the placeholder below with a real secret before release.
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
# The same value MUST be copied verbatim into tools/keygen.py.
# ---------------------------------------------------------------------------
_SECRET: bytes = bytes.fromhex(
    "4166666941424344454647484950515253545556575859615b5c5d5e5f606162"
)

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # Base36, 36 chars
_LICENSE_FILENAME = "license.json"
_TIER_CODES = {"B": "base", "P": "pro"}


class LicenseState(NamedTuple):
    is_licensed: bool
    tier: str        # "base" | "pro" | "demo"
    key: str         # formatted AFFI-XXXX-XXXX-XXXX or ""
    activated_at: str


class LicenseService:
    """Offline license key validator. Single instance, created in _init_services.

    Thread-safe for reads (is_licensed, tier). activate() should only be called
    from the Qt main thread (writes license.json and updates internal state).
    """

    def __init__(self, license_path: Path | None = None) -> None:
        self._path: Path = license_path or get_writable_data_path(_LICENSE_FILENAME)
        self._state = LicenseState(is_licensed=False, tier="demo", key="", activated_at="")
        self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_licensed(self) -> bool:
        return self._state.is_licensed

    @property
    def tier(self) -> str:
        return self._state.tier

    def activate(self, key_str: str) -> tuple[bool, str]:
        """Validate key_str and persist if valid.

        Returns:
            (success, error_message)  — error_message is "" on success.
        """
        ok, tier = self._validate(key_str)
        if not ok:
            return False, "Invalid license key. Check for typos and try again."

        data = {
            "key": self._fmt(key_str),
            "tier": tier,
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.error(f"[License] Failed to write {self._path}: {exc}")
            return False, f"Could not save license: {exc}"

        self._state = LicenseState(
            is_licensed=True,
            tier=tier,
            key=data["key"],
            activated_at=data["activated_at"],
        )
        logger.info(f"[License] Activated — tier={tier}, key={data['key'][:9]}***")
        return True, ""

    def get_info(self) -> dict:
        """Return display-ready info dict for UI consumption."""
        return {
            "is_licensed": self._state.is_licensed,
            "tier": self._state.tier,
            "tier_name": self._state.tier.title() if self._state.is_licensed else "Demo",
            "key": self._state.key,
            "activated_at": self._state.activated_at,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        # TEMP: license enforcement disabled — remove this block before shipping
        self._state = LicenseState(is_licensed=True, tier="pro", key="DEV", activated_at="")
        logger.info("[License] Enforcement disabled (dev mode) — full access granted")
        return

        if not self._path.exists():
            logger.info("[License] No license.json — Demo mode")
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            key = data.get("key", "")
            tier_stored = data.get("tier", "")
            ok, tier_validated = self._validate(key)
            if not ok or tier_validated != tier_stored:
                logger.warning("[License] license.json HMAC mismatch — Demo mode")
                return
            self._state = LicenseState(
                is_licensed=True,
                tier=tier_validated,
                key=self._fmt(key),
                activated_at=data.get("activated_at", ""),
            )
            logger.info(f"[License] Valid — tier={tier_validated}")
        except Exception as exc:
            logger.warning(f"[License] Load error ({exc}) — Demo mode")

    def _validate(self, key_str: str) -> tuple[bool, str]:
        """Returns (is_valid, tier_str). tier_str is '' on failure."""
        clean = key_str.upper().replace("-", "").replace(" ", "").strip()
        # Strip the AFFI prefix if present (full key = AFFI + 12 payload chars = 16 chars)
        if clean.startswith("AFFI"):
            clean = clean[4:]
        if len(clean) != 12 or clean[0] not in _TIER_CODES:
            return False, ""
        tier_code = clean[0]
        tier = _TIER_CODES[tier_code]
        # Fixed per-tier nonce — deterministic, no nonce storage needed.
        # All customers on the same tier share one key (commercial enforcement model).
        nonce = f"affilabs-{tier_code}"
        message = f"{tier_code}:{nonce}".encode()
        mac = hmac.new(_SECRET, message, hashlib.sha256).digest()
        expected = _b36(mac, 11)
        if hmac.compare_digest(expected, clean[1:]):
            return True, tier
        return False, ""

    @staticmethod
    def _fmt(raw: str) -> str:
        c = raw.upper().replace("-", "").replace(" ", "")
        if c.startswith("AFFI"):
            c = c[4:]
        c = c[:12]
        return f"AFFI-{c[0:4]}-{c[4:8]}-{c[8:12]}"


def _b36(data: bytes, length: int) -> str:
    """Encode first 8 bytes of data as Base36 string of fixed length."""
    n = int.from_bytes(data[:8], "big")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHABET[n % 36])
        n //= 36
    return "".join(reversed(chars))
