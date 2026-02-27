#!/usr/bin/env python3
"""
Affilabs.core License Key Generator — INTERNAL USE ONLY, never ship to customers.

Usage:
    python tools/keygen.py --tier base
    python tools/keygen.py --tier pro
    python tools/keygen.py --verify AFFI-BXXX-XXXX-XXXX

The _SECRET below MUST match the value in affilabs/services/license_service.py exactly.
If you rotate the secret, regenerate all outstanding keys and update both files together.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import sys

# ---------------------------------------------------------------------------
# Secret — must be identical to _SECRET in affilabs/services/license_service.py
# ---------------------------------------------------------------------------
_SECRET: bytes = bytes.fromhex(
    "4166666941424344454647484950515253545556575859615b5c5d5e5f606162"
)

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_TIER_MAP = {"base": "B", "pro": "P"}
_CODE_MAP = {"B": "base", "P": "pro"}


def _b36(data: bytes, length: int) -> str:
    n = int.from_bytes(data[:8], "big")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHABET[n % 36])
        n //= 36
    return "".join(reversed(chars))


def generate_key(tier: str) -> str:
    """Generate one AFFI-XXXX-XXXX-XXXX key for the given tier."""
    assert tier in _TIER_MAP, f"Unknown tier: {tier!r}. Use 'base' or 'pro'."
    tier_code = _TIER_MAP[tier]
    nonce = f"affilabs-{tier_code}"
    message = f"{tier_code}:{nonce}".encode()
    mac = hmac.new(_SECRET, message, hashlib.sha256).digest()
    payload = tier_code + _b36(mac, 11)          # 12 chars
    return f"AFFI-{payload[0:4]}-{payload[4:8]}-{payload[8:12]}"


def verify_key(key_str: str) -> tuple[bool, str]:
    """Verify a key string. Returns (is_valid, tier). tier is '' on failure."""
    clean = key_str.upper().replace("-", "").replace(" ", "").strip()
    if clean.startswith("AFFI"):
        clean = clean[4:]
    if len(clean) != 12 or clean[0] not in _CODE_MAP:
        return False, ""
    tier_code = clean[0]
    tier = _CODE_MAP[tier_code]
    nonce = f"affilabs-{tier_code}"
    message = f"{tier_code}:{nonce}".encode()
    mac = hmac.new(_SECRET, message, hashlib.sha256).digest()
    expected = _b36(mac, 11)
    if hmac.compare_digest(expected, clean[1:]):
        return True, tier
    return False, ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Affilabs.core License Key Generator (internal use only)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", aliases=["gen"], help="Generate a license key")
    gen.add_argument("--tier", choices=["base", "pro"], required=True)

    ver = sub.add_parser("verify", aliases=["check"], help="Verify an existing key")
    ver.add_argument("key", help="Key to verify, e.g. AFFI-BXXX-XXXX-XXXX")

    # Also support positional --tier / --verify at top level for convenience
    parser.add_argument("--tier", choices=["base", "pro"])
    parser.add_argument("--verify", metavar="KEY")

    args = parser.parse_args()

    # Top-level shortcuts
    if args.verify:
        _do_verify(args.verify)
        return
    if args.tier and args.cmd is None:
        _do_generate(args.tier)
        return

    if args.cmd in ("generate", "gen"):
        _do_generate(args.tier)
    elif args.cmd in ("verify", "check"):
        _do_verify(args.key)


def _do_generate(tier: str) -> None:
    key = generate_key(tier)
    print(f"\n  Key  : {key}")
    print(f"  Tier : {tier}")
    print()
    print("  NOTE: All customers on the same tier receive the same key.")
    print("  Distribute via purchase confirmation email only.")
    print()


def _do_verify(key_str: str) -> None:
    ok, tier = verify_key(key_str)
    if ok:
        print(f"  VALID — tier: {tier}")
    else:
        print("  INVALID")
        sys.exit(1)


if __name__ == "__main__":
    # Convenience: allow  python tools/keygen.py --tier pro
    #                 or  python tools/keygen.py --verify AFFI-...
    _args = sys.argv[1:]
    if "--tier" in _args and "generate" not in _args and "verify" not in _args:
        idx = _args.index("--tier")
        tier_val = _args[idx + 1] if idx + 1 < len(_args) else None
        if tier_val in ("base", "pro"):
            _do_generate(tier_val)
            sys.exit(0)

    if "--verify" in _args:
        idx = _args.index("--verify")
        key_val = _args[idx + 1] if idx + 1 < len(_args) else None
        if key_val:
            _do_verify(key_val)
            sys.exit(0)

    main()
