"""
Test script for Phase 1 - Feature Flag System
Demonstrates license tiers and feature gating.
"""

from affilabs.config.feature_flags import FeatureTier, FeatureFlags
from affilabs.config.license_manager import LicenseManager


def test_feature_tiers():
    """Test all three license tiers."""
    print("=" * 70)
    print("FEATURE FLAGS - LICENSE TIER COMPARISON")
    print("=" * 70)

    tiers = [FeatureTier.FREE, FeatureTier.PRO, FeatureTier.ENTERPRISE]

    for tier in tiers:
        features = FeatureFlags(tier)
        print(f"\n{features.tier_name} TIER:")
        print("-" * 40)

        # Test key features
        test_features = [
            ("Basic Acquisition", features.basic_acquisition),
            ("Excel Export", features.excel_export),
            ("Method Manager", features.method_manager),
            ("AnIML Export", features.animl_export),
            ("Audit Trail", features.audit_trail),
            ("SiLA Integration", features.sila_integration),
            ("LIMS Integration", features.lims_integration),
            ("Electronic Signatures", features.electronic_signatures),
            ("21 CFR Part 11", features.cfr_part11_compliance),
        ]

        for name, enabled in test_features:
            status = "✅" if enabled else "❌"
            print(f"  {status} {name}")

        print(f"\nAvailable features: {len(features.get_available_features())}")
        locked = features.get_locked_features()
        if locked:
            print(f"Locked features: {len(locked)}")


def test_license_generation():
    """Test license file generation."""
    print("\n" + "=" * 70)
    print("LICENSE GENERATION TEST")
    print("=" * 70)

    mgr = LicenseManager()

    # Generate test licenses for each tier
    tiers = [
        ("pro", "Test Company Pro"),
        ("enterprise", "Test Company Enterprise"),
    ]

    for tier, licensee in tiers:
        license_data = mgr.generate_license(
            tier=tier,
            licensee=licensee,
            expiration_days=365
        )

        print(f"\n{tier.upper()} LICENSE:")
        print(f"  Licensee: {license_data['licensee']}")
        print(f"  Key: {license_data['license_key']}")
        print(f"  Expires: {license_data['expiration_date'][:10]}")
        print(f"  Features: {len(license_data['features_enabled'])}")


def test_license_loading():
    """Test loading license from file (if exists)."""
    print("\n" + "=" * 70)
    print("LICENSE FILE LOADING TEST")
    print("=" * 70)

    mgr = LicenseManager()
    features = mgr.load_license()
    info = mgr.get_license_info()

    print("\nCurrent License Status:")
    print(f"  Tier: {info['tier_name']}")
    print(f"  Licensee: {info['licensee']}")
    print(f"  Valid: {'✅ Yes' if info['is_valid'] else '❌ No'}")
    print(f"  Expires: {info['expires']}")

    if not info['is_valid'] and info.get('errors'):
        print("\n  Validation Errors:")
        for error in info['errors']:
            print(f"    • {error}")

    print(f"\nAvailable Features ({len(features.get_available_features())}):")
    for feature in features.get_available_features()[:10]:  # Show first 10
        print(f"  ✅ {feature}")

    locked = features.get_locked_features()
    if locked:
        print(f"\nLocked Features ({len(locked)}):")
        for feature, req_tier in list(locked.items())[:5]:  # Show first 5
            print(f"  🔒 {feature} (requires {req_tier})")


def test_feature_access():
    """Test feature access checking."""
    print("\n" + "=" * 70)
    print("FEATURE ACCESS TEST")
    print("=" * 70)

    # Test with Free tier
    features = FeatureFlags(FeatureTier.FREE)
    print("\nFree Tier Access Check:")
    print(f"  Excel Export: {features.excel_export}")
    print(f"  AnIML Export: {features.animl_export}")
    print(f"  SiLA Integration: {features.sila_integration}")

    # Test with Pro tier
    features = FeatureFlags(FeatureTier.PRO)
    print("\nPro Tier Access Check:")
    print(f"  Excel Export: {features.excel_export}")
    print(f"  AnIML Export: {features.animl_export}")
    print(f"  SiLA Integration: {features.sila_integration}")

    # Test with Enterprise tier
    features = FeatureFlags(FeatureTier.ENTERPRISE)
    print("\nEnterprise Tier Access Check:")
    print(f"  Excel Export: {features.excel_export}")
    print(f"  AnIML Export: {features.animl_export}")
    print(f"  SiLA Integration: {features.sila_integration}")


if __name__ == "__main__":
    test_feature_tiers()
    test_license_generation()
    test_license_loading()
    test_feature_access()

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED")
    print("=" * 70)
    print("\nTo test in the application:")
    print("  1. Run: python main.py")
    print("  2. Click AnIML Export button (should show upgrade prompt)")
    print("  3. Generate test license via License dialog")
    print("  4. Restart application")
    print("  5. AnIML Export button should now work")
    print("=" * 70)
