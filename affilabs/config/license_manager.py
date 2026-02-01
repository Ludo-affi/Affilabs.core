"""
License Manager for Feature Tier Validation
Handles license file parsing, validation, and expiration checking.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .feature_flags import FeatureTier, FeatureFlags


class LicenseManager:
    """
    Manages software licensing and feature tier activation.

    Supports:
    - File-based licensing (simple deployment)
    - Expiration dates
    - Hardware binding (optional)
    - License validation
    """

    def __init__(self, license_path: Optional[Path] = None):
        """
        Initialize license manager.

        Args:
            license_path: Path to license file (default: ./license.json)
        """
        self.license_path = license_path or Path("license.json")
        self._license_data = None
        self._validation_errors = []

    def load_license(self) -> FeatureFlags:
        """
        Load and validate license file.

        Returns:
            FeatureFlags: Configured feature flags based on license
        """
        # Try to load license file
        if not self.license_path.exists():
            return FeatureFlags(FeatureTier.FREE)

        try:
            with open(self.license_path, 'r') as f:
                self._license_data = json.load(f)

            # Validate license
            if self._validate_license():
                tier = self._license_data.get('tier', FeatureTier.FREE)
                return FeatureFlags(tier)
            else:
                # Invalid license - revert to free tier
                return FeatureFlags(FeatureTier.FREE)

        except Exception as e:
            self._validation_errors.append(f"License load error: {e}")
            return FeatureFlags(FeatureTier.FREE)

    def _validate_license(self) -> bool:
        """
        Validate license data.

        Returns:
            bool: True if license is valid
        """
        self._validation_errors = []

        if not self._license_data:
            self._validation_errors.append("No license data loaded")
            return False

        # Check required fields
        required_fields = ['tier', 'issued_date', 'license_key']
        for field in required_fields:
            if field not in self._license_data:
                self._validation_errors.append(f"Missing required field: {field}")
                return False

        # Validate tier
        valid_tiers = [FeatureTier.FREE, FeatureTier.PRO, FeatureTier.ENTERPRISE]
        if self._license_data['tier'] not in valid_tiers:
            self._validation_errors.append(f"Invalid tier: {self._license_data['tier']}")
            return False

        # Check expiration
        if 'expiration_date' in self._license_data:
            try:
                expiration = datetime.fromisoformat(self._license_data['expiration_date'])
                if datetime.now() > expiration:
                    self._validation_errors.append("License has expired")
                    return False
            except ValueError:
                self._validation_errors.append("Invalid expiration date format")
                return False

        # Validate license key signature
        if not self._validate_signature():
            self._validation_errors.append("Invalid license signature")
            return False

        return True

    def _validate_signature(self) -> bool:
        """
        Validate license key signature.

        Simple implementation - in production, use cryptographic signing.

        Returns:
            bool: True if signature is valid
        """
        try:
            # Extract signature components
            license_key = self._license_data.get('license_key', '')
            tier = self._license_data.get('tier', '')
            issued_date = self._license_data.get('issued_date', '')
            licensee = self._license_data.get('licensee', '')

            # Calculate expected signature
            # In production, use proper public/private key cryptography
            signature_input = f"{tier}:{licensee}:{issued_date}:ezControl-secret-key"
            expected_signature = hashlib.sha256(signature_input.encode()).hexdigest()[:16]

            # Compare signatures
            return license_key.startswith(expected_signature)

        except Exception:
            return False

    def get_license_info(self) -> Dict[str, Any]:
        """
        Get license information for display.

        Returns:
            dict: License details
        """
        if not self._license_data:
            return {
                'tier': FeatureTier.FREE,
                'tier_name': 'Free',
                'licensee': 'Unlicensed',
                'status': 'No license file found',
                'expires': None,
                'is_valid': True
            }

        tier = self._license_data.get('tier', FeatureTier.FREE)
        tier_names = {
            FeatureTier.FREE: 'Free',
            FeatureTier.PRO: 'Pro',
            FeatureTier.ENTERPRISE: 'Enterprise'
        }

        expiration = None
        if 'expiration_date' in self._license_data:
            try:
                exp_date = datetime.fromisoformat(self._license_data['expiration_date'])
                expiration = exp_date.strftime('%Y-%m-%d')
            except:
                expiration = 'Invalid date'

        return {
            'tier': tier,
            'tier_name': tier_names.get(tier, 'Unknown'),
            'licensee': self._license_data.get('licensee', 'Unknown'),
            'issued_date': self._license_data.get('issued_date', 'Unknown'),
            'expires': expiration or 'Never',
            'is_valid': len(self._validation_errors) == 0,
            'errors': self._validation_errors
        }

    def save_license(self, license_data: Dict[str, Any]) -> bool:
        """
        Save license data to file.

        Args:
            license_data: License information

        Returns:
            bool: True if saved successfully
        """
        try:
            with open(self.license_path, 'w') as f:
                json.dump(license_data, f, indent=2)
            return True
        except Exception as e:
            self._validation_errors.append(f"Failed to save license: {e}")
            return False

    def generate_license(self, tier: str, licensee: str,
                        expiration_days: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a new license file (for testing/distribution).

        Args:
            tier: License tier (free, pro, enterprise)
            licensee: Name of licensee (company/person)
            expiration_days: Days until expiration (None = never)

        Returns:
            dict: License data
        """
        issued_date = datetime.now().isoformat()

        # Calculate expiration
        expiration_date = None
        if expiration_days:
            expiration = datetime.now() + timedelta(days=expiration_days)
            expiration_date = expiration.isoformat()

        # Generate license key (simple signature)
        signature_input = f"{tier}:{licensee}:{issued_date}:ezControl-secret-key"
        signature = hashlib.sha256(signature_input.encode()).hexdigest()[:16]
        license_key = f"{signature}-{tier.upper()}"

        license_data = {
            'tier': tier,
            'licensee': licensee,
            'issued_date': issued_date,
            'expiration_date': expiration_date,
            'license_key': license_key,
            'version': '1.0',
            'product': 'ezControl SPR',
            'features_enabled': self._get_tier_features(tier)
        }

        return license_data

    def _get_tier_features(self, tier: str) -> list:
        """Get list of features for a given tier."""
        features = FeatureFlags(tier)
        return features.get_available_features()

    @property
    def validation_errors(self) -> list:
        """Get validation errors from last license check."""
        return self._validation_errors

    @property
    def is_licensed(self) -> bool:
        """Check if a valid license is loaded."""
        return self._license_data is not None and len(self._validation_errors) == 0
