"""
Feature Flag System for Tiered Licensing
Supports Free, Pro, and Enterprise tiers with progressive feature unlocking.
"""


class FeatureTier:
    """License tier constants."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class FeatureFlags:
    """
    Feature flag manager for tiered licensing.

    Controls access to features based on license tier:
    - Free: Academic/research use
    - Pro: Commercial labs with advanced features
    - Enterprise: Pharma/biotech with full compliance
    """

    def __init__(self, tier=FeatureTier.FREE):
        """
        Initialize feature flags.

        Args:
            tier: License tier (FeatureTier.FREE, PRO, or ENTERPRISE)
        """
        self._tier = tier

    @property
    def tier(self):
        """Get current license tier."""
        return self._tier

    @property
    def tier_name(self):
        """Get human-readable tier name."""
        names = {
            FeatureTier.FREE: "Free",
            FeatureTier.PRO: "Pro",
            FeatureTier.ENTERPRISE: "Enterprise"
        }
        return names.get(self._tier, "Unknown")

    # ========================================================================
    # CORE FEATURES (Always Available)
    # ========================================================================

    @property
    def basic_acquisition(self):
        """SPR data acquisition - always available."""
        return True

    @property
    def excel_export(self):
        """Excel data export - always available."""
        return True

    @property
    def method_manager(self):
        """Method creation and management - always available."""
        return True

    @property
    def basic_qc(self):
        """Basic QC validation - always available."""
        return True

    @property
    def basic_graphs(self):
        """Standard sensorgram plots - always available."""
        return True

    # ========================================================================
    # PRO FEATURES (Pro + Enterprise)
    # ========================================================================

    @property
    def animl_export(self):
        """AnIML XML export for regulatory compliance."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def audit_trail(self):
        """Comprehensive audit logging system."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def advanced_analytics(self):
        """Advanced data analysis and fitting algorithms."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def batch_processing(self):
        """Batch data processing and analysis."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def advanced_qc(self):
        """Enhanced QC with statistical process control."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    @property
    def custom_reports(self):
        """Customizable report templates."""
        return self._tier in [FeatureTier.PRO, FeatureTier.ENTERPRISE]

    # ========================================================================
    # ENTERPRISE FEATURES (Enterprise Only)
    # ========================================================================

    @property
    def sila_integration(self):
        """SiLA 2.0 device control protocol."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def lims_integration(self):
        """LIMS system integration and data upload."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def electronic_signatures(self):
        """Electronic signature capture and validation."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def cfr_part11_compliance(self):
        """21 CFR Part 11 compliance features."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def user_management(self):
        """Multi-user accounts with role-based access control."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def data_integrity_verification(self):
        """Cryptographic data integrity checks."""
        return self._tier == FeatureTier.ENTERPRISE

    @property
    def audit_trail_review(self):
        """Formal audit trail review and approval workflow."""
        return self._tier == FeatureTier.ENTERPRISE

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def get_locked_features(self):
        """
        Get list of features locked for current tier.

        Returns:
            dict: {feature_name: required_tier}
        """
        all_features = {
            'AnIML Export': (self.animl_export, FeatureTier.PRO),
            'Audit Trail': (self.audit_trail, FeatureTier.PRO),
            'Advanced Analytics': (self.advanced_analytics, FeatureTier.PRO),
            'Batch Processing': (self.batch_processing, FeatureTier.PRO),
            'Advanced QC': (self.advanced_qc, FeatureTier.PRO),
            'Custom Reports': (self.custom_reports, FeatureTier.PRO),
            'SiLA 2.0 Integration': (self.sila_integration, FeatureTier.ENTERPRISE),
            'LIMS Integration': (self.lims_integration, FeatureTier.ENTERPRISE),
            'Electronic Signatures': (self.electronic_signatures, FeatureTier.ENTERPRISE),
            '21 CFR Part 11 Compliance': (self.cfr_part11_compliance, FeatureTier.ENTERPRISE),
            'User Management': (self.user_management, FeatureTier.ENTERPRISE),
            'Data Integrity Verification': (self.data_integrity_verification, FeatureTier.ENTERPRISE),
            'Audit Trail Review': (self.audit_trail_review, FeatureTier.ENTERPRISE),
        }

        return {name: tier for name, (enabled, tier) in all_features.items() if not enabled}

    def get_available_features(self):
        """
        Get list of features available for current tier.

        Returns:
            list: Feature names available
        """
        all_features = {
            'Basic SPR Acquisition': self.basic_acquisition,
            'Excel Export': self.excel_export,
            'Method Manager': self.method_manager,
            'Basic QC': self.basic_qc,
            'Standard Graphs': self.basic_graphs,
            'AnIML Export': self.animl_export,
            'Audit Trail': self.audit_trail,
            'Advanced Analytics': self.advanced_analytics,
            'Batch Processing': self.batch_processing,
            'Advanced QC': self.advanced_qc,
            'Custom Reports': self.custom_reports,
            'SiLA 2.0 Integration': self.sila_integration,
            'LIMS Integration': self.lims_integration,
            'Electronic Signatures': self.electronic_signatures,
            '21 CFR Part 11 Compliance': self.cfr_part11_compliance,
            'User Management': self.user_management,
            'Data Integrity Verification': self.data_integrity_verification,
            'Audit Trail Review': self.audit_trail_review,
        }

        return [name for name, enabled in all_features.items() if enabled]

    def __repr__(self):
        """String representation."""
        return f"FeatureFlags(tier={self.tier_name})"
