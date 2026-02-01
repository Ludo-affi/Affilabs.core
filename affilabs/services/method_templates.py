"""Method Templates - Predefined method templates for common workflows.

ARCHITECTURE LAYER: Services (Phase 1.2 - Pro Tier Feature)

This module provides predefined method templates for common SPR workflows.
Templates are gated behind Pro/Enterprise tier licensing.

FEATURE TIER: Pro/Enterprise only

TEMPLATES:
- Kinetics Analysis: Multi-concentration kinetics with baseline
- Affinity Screening: High-throughput concentration series
- Binding Analysis: Single-cycle kinetics
- Regeneration Screening: Test different regeneration conditions
- Custom Template: User-defined starting point

USAGE:
    templates = MethodTemplates()

    # Check if user has access
    if app.features.method_templates:
        # Get available templates
        template_list = templates.get_templates_list()

        # Apply template
        cycles = templates.apply_template(
            "kinetics_analysis",
            concentrations=[100, 50, 25, 12.5, 6.25],
            baseline_minutes=5
        )
    else:
        # Show upgrade prompt
        app.show_upgrade_prompt('method_templates')
"""

from typing import List, Dict, Any, Optional

from affilabs.domain.cycle import Cycle
from affilabs.utils.logger import logger


class MethodTemplates:
    """Predefined method templates for common SPR workflows."""

    def __init__(self):
        """Initialize method templates service."""
        logger.debug("Method templates service initialized")

    def get_templates_list(self) -> List[Dict[str, str]]:
        """Get list of available templates.

        Returns:
            List of template info dicts
        """
        return [
            {
                "id": "kinetics_analysis",
                "name": "Kinetics Analysis",
                "description": "Multi-concentration kinetics with baseline and regeneration",
                "icon": "📊",
                "tier": "Pro",
            },
            {
                "id": "affinity_screening",
                "name": "Affinity Screening",
                "description": "High-throughput concentration series",
                "icon": "🔬",
                "tier": "Pro",
            },
            {
                "id": "single_cycle_kinetics",
                "name": "Single-Cycle Kinetics",
                "description": "Rapid kinetics with sequential injections",
                "icon": "⚡",
                "tier": "Pro",
            },
            {
                "id": "regeneration_screening",
                "name": "Regeneration Screening",
                "description": "Test different regeneration conditions",
                "icon": "🔄",
                "tier": "Pro",
            },
            {
                "id": "binding_analysis",
                "name": "Binding Analysis",
                "description": "Simple association/dissociation analysis",
                "icon": "🧪",
                "tier": "Free",
            },
        ]

    def apply_template(
        self,
        template_id: str,
        **params
    ) -> List[Cycle]:
        """Apply a method template with parameters.

        Args:
            template_id: Template identifier
            **params: Template-specific parameters

        Returns:
            List of Cycle objects

        Raises:
            ValueError: If template_id is unknown
        """
        template_map = {
            "kinetics_analysis": self._kinetics_analysis,
            "affinity_screening": self._affinity_screening,
            "single_cycle_kinetics": self._single_cycle_kinetics,
            "regeneration_screening": self._regeneration_screening,
            "binding_analysis": self._binding_analysis,
        }

        if template_id not in template_map:
            raise ValueError(f"Unknown template: {template_id}")

        cycles = template_map[template_id](**params)
        logger.info(f"✓ Template applied: {template_id} ({len(cycles)} cycles)")
        return cycles

    def _kinetics_analysis(
        self,
        concentrations: Optional[List[float]] = None,
        baseline_minutes: float = 5.0,
        association_minutes: float = 3.0,
        dissociation_minutes: float = 5.0,
        regeneration_minutes: float = 1.0,
        concentration_units: str = "nM",
    ) -> List[Cycle]:
        """Kinetics analysis template.

        Args:
            concentrations: List of analyte concentrations (default: [100, 50, 25, 12.5, 6.25])
            baseline_minutes: Baseline duration
            association_minutes: Association phase duration
            dissociation_minutes: Dissociation phase duration
            regeneration_minutes: Regeneration duration
            concentration_units: Concentration units (nM, µM, etc.)

        Returns:
            List of Cycle objects
        """
        if concentrations is None:
            concentrations = [100, 50, 25, 12.5, 6.25]

        cycles = []

        # Initial baseline
        cycles.append(Cycle(
            type="Baseline",
            length_minutes=baseline_minutes,
            name="Initial Baseline",
            note="Stabilization before kinetics series"
        ))

        # Concentration series
        for i, conc in enumerate(concentrations):
            # Association
            cycles.append(Cycle(
                type="Association",
                length_minutes=association_minutes,
                name=f"Association {i+1}",
                concentration_value=conc,
                concentration_units=concentration_units,
                note=f"Analyte injection: {conc} {concentration_units}"
            ))

            # Dissociation
            cycles.append(Cycle(
                type="Dissociation",
                length_minutes=dissociation_minutes,
                name=f"Dissociation {i+1}",
                note="Buffer flow, no analyte"
            ))

            # Regeneration
            cycles.append(Cycle(
                type="Regeneration",
                length_minutes=regeneration_minutes,
                name=f"Regeneration {i+1}",
                note="Surface regeneration"
            ))

            # Inter-cycle baseline
            if i < len(concentrations) - 1:
                cycles.append(Cycle(
                    type="Baseline",
                    length_minutes=baseline_minutes * 0.5,
                    name=f"Baseline {i+2}",
                    note="Stabilization between cycles"
                ))

        # Final baseline
        cycles.append(Cycle(
            type="Baseline",
            length_minutes=baseline_minutes,
            name="Final Baseline",
            note="Final stabilization"
        ))

        return cycles

    def _affinity_screening(
        self,
        concentrations: Optional[List[float]] = None,
        flow_minutes: float = 2.0,
        static_minutes: float = 3.0,
        concentration_units: str = "nM",
    ) -> List[Cycle]:
        """Affinity screening template for high-throughput.

        Args:
            concentrations: List of screening concentrations
            flow_minutes: Flow phase duration
            static_minutes: Static phase duration
            concentration_units: Concentration units

        Returns:
            List of Cycle objects
        """
        if concentrations is None:
            concentrations = [1000, 500, 250, 100, 50, 25, 10]

        cycles = []

        # Baseline
        cycles.append(Cycle(
            type="Baseline",
            length_minutes=5.0,
            name="Baseline",
            note="Initial baseline"
        ))

        # Screening series
        for i, conc in enumerate(concentrations):
            cycles.append(Cycle(
                type="Association",
                length_minutes=flow_minutes,
                name=f"Screen {i+1}",
                concentration_value=conc,
                concentration_units=concentration_units,
                note=f"Screening: {conc} {concentration_units}"
            ))

        return cycles

    def _single_cycle_kinetics(
        self,
        concentrations: Optional[List[float]] = None,
        injection_minutes: float = 1.0,
        dissociation_minutes: float = 10.0,
        concentration_units: str = "nM",
    ) -> List[Cycle]:
        """Single-cycle kinetics template (rapid method).

        Args:
            concentrations: Concentration series
            injection_minutes: Each injection duration
            dissociation_minutes: Final dissociation duration
            concentration_units: Concentration units

        Returns:
            List of Cycle objects
        """
        if concentrations is None:
            concentrations = [6.25, 12.5, 25, 50, 100]

        cycles = []

        # Baseline
        cycles.append(Cycle(
            type="Baseline",
            length_minutes=3.0,
            name="Baseline",
            note="Initial baseline"
        ))

        # Sequential injections
        for i, conc in enumerate(concentrations):
            cycles.append(Cycle(
                type="Association",
                length_minutes=injection_minutes,
                name=f"Injection {i+1}",
                concentration_value=conc,
                concentration_units=concentration_units,
                note=f"Sequential injection: {conc} {concentration_units}"
            ))

        # Long dissociation
        cycles.append(Cycle(
            type="Dissociation",
            length_minutes=dissociation_minutes,
            name="Dissociation",
            note="Extended dissociation phase"
        ))

        # Regeneration
        cycles.append(Cycle(
            type="Regeneration",
            length_minutes=1.0,
            name="Regeneration",
            note="Surface regeneration"
        ))

        return cycles

    def _regeneration_screening(
        self,
        regeneration_conditions: Optional[List[str]] = None,
        flow_minutes: float = 2.0,
        test_injection_minutes: float = 2.0,
    ) -> List[Cycle]:
        """Regeneration screening template.

        Args:
            regeneration_conditions: List of condition names
            flow_minutes: Regeneration flow duration
            test_injection_minutes: Test injection duration

        Returns:
            List of Cycle objects
        """
        if regeneration_conditions is None:
            regeneration_conditions = [
                "10 mM Glycine pH 2.0",
                "10 mM Glycine pH 2.5",
                "50 mM NaOH",
                "10 mM HCl",
            ]

        cycles = []

        for i, condition in enumerate(regeneration_conditions):
            # Baseline
            cycles.append(Cycle(
                type="Baseline",
                length_minutes=3.0,
                name=f"Baseline {i+1}",
                note=f"Before condition: {condition}"
            ))

            # Test injection
            cycles.append(Cycle(
                type="Association",
                length_minutes=test_injection_minutes,
                name=f"Test Injection {i+1}",
                note="Analyte binding before regeneration"
            ))

            # Regeneration
            cycles.append(Cycle(
                type="Regeneration",
                length_minutes=flow_minutes,
                name=f"Regen {i+1}",
                note=condition
            ))

        return cycles

    def _binding_analysis(
        self,
        concentration: float = 100.0,
        association_minutes: float = 3.0,
        dissociation_minutes: float = 5.0,
        concentration_units: str = "nM",
    ) -> List[Cycle]:
        """Simple binding analysis template.

        Args:
            concentration: Analyte concentration
            association_minutes: Association duration
            dissociation_minutes: Dissociation duration
            concentration_units: Concentration units

        Returns:
            List of Cycle objects
        """
        return [
            Cycle(
                type="Baseline",
                length_minutes=5.0,
                name="Baseline",
                note="Stabilization"
            ),
            Cycle(
                type="Association",
                length_minutes=association_minutes,
                name="Association",
                concentration_value=concentration,
                concentration_units=concentration_units,
                note=f"Analyte injection: {concentration} {concentration_units}"
            ),
            Cycle(
                type="Dissociation",
                length_minutes=dissociation_minutes,
                name="Dissociation",
                note="Buffer flow"
            ),
            Cycle(
                type="Regeneration",
                length_minutes=1.0,
                name="Regeneration",
                note="Surface regeneration"
            ),
        ]

    def export_template(self, template_id: str, **params) -> Dict[str, Any]:
        """Export template as method data for saving.

        Args:
            template_id: Template to export
            **params: Template parameters

        Returns:
            Method data dict ready for MethodStorage
        """
        template_info = next(
            (t for t in self.get_templates_list() if t['id'] == template_id),
            None
        )

        if not template_info:
            raise ValueError(f"Unknown template: {template_id}")

        cycles = self.apply_template(template_id, **params)

        return {
            "name": template_info['name'],
            "description": f"{template_info['description']} (from template)",
            "cycles": [c.to_dict() for c in cycles],
            "tags": ["template", template_id],
            "metadata": {
                "template_id": template_id,
                "template_params": params,
            }
        }
