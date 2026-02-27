"""
LicenseManager — thin shim over LicenseService.

All existing call sites in main.py are preserved unchanged:
  self.license_mgr = LicenseManager()
  self.features    = self.license_mgr.load_license()
  license_info     = self.license_mgr.get_license_info()
  self.license_mgr.is_licensed
  show_license_dialog()  (via main.py line 3638)

New call site added for the activation dialog:
  ok, err = self.license_mgr.activate(key_str)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .feature_flags import FeatureTier, FeatureFlags
from affilabs.services.license_service import LicenseService


class LicenseManager:
    """Thin wrapper over LicenseService for backward-compatible call sites."""

    def __init__(self, license_path: Path | None = None) -> None:
        self._svc = LicenseService(license_path)

    # ── Existing call sites (main.py lines 864–873) ──────────────────────────

    def load_license(self) -> FeatureFlags:
        """Return FeatureFlags for the current tier."""
        t = self._svc.tier
        if t == "pro":
            return FeatureFlags(FeatureTier.PRO)
        if t == "enterprise":
            return FeatureFlags(FeatureTier.ENTERPRISE)
        return FeatureFlags(FeatureTier.FREE)

    def get_license_info(self) -> dict[str, Any]:
        """Return dict matching the shape expected by main.py license logging."""
        info = self._svc.get_info()
        return {
            "tier": info["tier"],
            "tier_name": info["tier_name"],
            "licensee": "Licensed" if info["is_licensed"] else "Unlicensed",
            "issued_date": info["activated_at"],
            "expires": "Never",
            "is_valid": info["is_licensed"],
            "errors": [] if info["is_licensed"] else ["No valid license key — running in Demo mode"],
        }

    @property
    def is_licensed(self) -> bool:
        return self._svc.is_licensed

    @property
    def validation_errors(self) -> list[str]:
        return [] if self._svc.is_licensed else ["No valid license key"]

    # ── New call site (activation dialog) ────────────────────────────────────

    def activate(self, key_str: str) -> tuple[bool, str]:
        """Validate and persist a license key. Returns (success, error_msg)."""
        return self._svc.activate(key_str)
