"""Cycle Template Storage - Save and load cycle templates.

ARCHITECTURE LAYER: Service (Business Logic)

This service manages cycle templates:
- Save cycle configurations as reusable templates
- Load templates to quickly create cycles
- Template CRUD operations
- Persistence via TinyDB

USAGE:
    storage = CycleTemplateStorage()

    # Save template
    template_id = storage.save_template("5-Min Baseline", cycle)

    # Load template
    cycle = storage.load_template(template_id)

    # List all templates
    templates = storage.get_all_templates()
"""

from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from tinydb import TinyDB, Query

from affilabs.domain.cycle import Cycle
from affilabs.utils.logger import logger
from affilabs.utils.resource_path import get_writable_data_path


class CycleTemplate:
    """Cycle template data structure."""

    def __init__(
        self,
        template_id: int,
        name: str,
        cycle_type: str,
        length_minutes: float,
        note: str = "",
        units: str = "nM",
        concentrations: Dict[str, float] = None,
        created_at: str = None,
        modified_at: str = None
    ):
        self.template_id = template_id
        self.name = name
        self.cycle_type = cycle_type
        self.length_minutes = length_minutes
        self.note = note
        self.units = units
        self.concentrations = concentrations or {}
        self.created_at = created_at or datetime.now().isoformat()
        self.modified_at = modified_at or self.created_at

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'template_id': self.template_id,
            'name': self.name,
            'cycle_type': self.cycle_type,
            'length_minutes': self.length_minutes,
            'note': self.note,
            'units': self.units,
            'concentrations': self.concentrations,
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CycleTemplate':
        """Create from dictionary."""
        return cls(**data)

    def to_cycle(self) -> Cycle:
        """Convert template to a Cycle instance."""
        return Cycle(
            type=self.cycle_type,
            length_minutes=self.length_minutes,
            note=self.note,
            units=self.units,
            concentrations=self.concentrations,
            status="pending"
        )


class CycleTemplateStorage:
    """Storage service for cycle templates using TinyDB."""

    def __init__(self, db_path: str = ""):
        """Initialize template storage.

        Args:
            db_path: Path to TinyDB database file (default: writable data dir)
        """
        self.db_path = Path(db_path) if db_path else get_writable_data_path("cycle_templates.json")
        self.db = TinyDB(self.db_path)
        self.templates_table = self.db.table('templates')

        logger.debug(f"CycleTemplateStorage initialized: {self.db_path}")

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def save_template(
        self,
        name: str,
        cycle: Cycle,
        template_id: Optional[int] = None
    ) -> int:
        """Save or update a cycle template.

        Args:
            name: Template name
            cycle: Cycle instance to save as template
            template_id: Existing template ID (for updates), or None for new

        Returns:
            Template ID
        """
        timestamp = datetime.now().isoformat()

        if template_id is not None:
            # Update existing template
            Template = Query()
            existing = self.templates_table.get(Template.template_id == template_id)

            if existing:
                template_data = {
                    'template_id': template_id,
                    'name': name,
                    'cycle_type': cycle.type,
                    'length_minutes': cycle.length_minutes,
                    'note': cycle.note,
                    'units': cycle.units,
                    'concentrations': cycle.concentrations,
                    'created_at': existing.get('created_at', timestamp),
                    'modified_at': timestamp
                }

                self.templates_table.update(template_data, Template.template_id == template_id)
                logger.info(f"Updated template: {name} (ID: {template_id})")
                return template_id

        # Create new template
        # Find next available ID
        all_templates = self.templates_table.all()
        next_id = max([t.get('template_id', 0) for t in all_templates], default=0) + 1

        template_data = {
            'template_id': next_id,
            'name': name,
            'cycle_type': cycle.type,
            'length_minutes': cycle.length_minutes,
            'note': cycle.note,
            'units': cycle.units,
            'concentrations': cycle.concentrations,
            'created_at': timestamp,
            'modified_at': timestamp
        }

        self.templates_table.insert(template_data)
        logger.info(f"Saved template: {name} (ID: {next_id})")
        return next_id

    def load_template(self, template_id: int) -> Optional[CycleTemplate]:
        """Load a template by ID.

        Args:
            template_id: Template ID

        Returns:
            CycleTemplate instance or None if not found
        """
        Template = Query()
        result = self.templates_table.get(Template.template_id == template_id)

        if result:
            return CycleTemplate.from_dict(result)

        logger.warning(f"Template not found: ID {template_id}")
        return None

    def delete_template(self, template_id: int) -> bool:
        """Delete a template.

        Args:
            template_id: Template ID

        Returns:
            True if deleted, False if not found
        """
        Template = Query()
        result = self.templates_table.remove(Template.template_id == template_id)

        if result:
            logger.info(f"Deleted template: ID {template_id}")
            return True

        logger.warning(f"Template not found for deletion: ID {template_id}")
        return False

    def get_all_templates(self) -> List[CycleTemplate]:
        """Get all templates.

        Returns:
            List of CycleTemplate instances
        """
        results = self.templates_table.all()
        templates = [CycleTemplate.from_dict(data) for data in results]

        # Sort by name
        templates.sort(key=lambda t: t.name.lower())

        return templates

    def search_templates(self, query: str) -> List[CycleTemplate]:
        """Search templates by name or type.

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        query_lower = query.lower()
        all_templates = self.get_all_templates()

        matches = [
            t for t in all_templates
            if query_lower in t.name.lower() or query_lower in t.cycle_type.lower()
        ]

        return matches

    def get_templates_by_type(self, cycle_type: str) -> List[CycleTemplate]:
        """Get all templates of a specific type.

        Args:
            cycle_type: Cycle type to filter by

        Returns:
            List of matching templates
        """
        Template = Query()
        results = self.templates_table.search(Template.cycle_type == cycle_type)

        return [CycleTemplate.from_dict(data) for data in results]

    # ========================================================================
    # Import/Export
    # ========================================================================

    def export_template(self, template_id: int, export_path: str) -> bool:
        """Export template to JSON file.

        Args:
            template_id: Template ID
            export_path: Path to export file

        Returns:
            True if successful
        """
        template = self.load_template(template_id)

        if not template:
            return False

        import json
        export_file = Path(export_path)

        with open(export_file, 'w') as f:
            json.dump(template.to_dict(), f, indent=2)

        logger.info(f"Exported template to: {export_path}")
        return True

    def import_template(self, import_path: str) -> Optional[int]:
        """Import template from JSON file.

        Args:
            import_path: Path to import file

        Returns:
            New template ID or None if failed
        """
        import json
        import_file = Path(import_path)

        if not import_file.exists():
            logger.error(f"Import file not found: {import_path}")
            return None

        try:
            with open(import_file, 'r') as f:
                data = json.load(f)

            # Create cycle from imported data
            cycle = Cycle(
                type=data['cycle_type'],
                length_minutes=data['length_minutes'],
                note=data.get('note', ''),
                units=data.get('units', 'nM'),
                concentrations=data.get('concentrations', {}),
                status='pending'
            )

            # Save as new template (don't preserve old ID)
            template_id = self.save_template(data['name'], cycle)

            logger.info(f"Imported template from: {import_path}")
            return template_id

        except Exception as e:
            logger.error(f"Failed to import template: {e}")
            return None

    def close(self):
        """Close database connection."""
        self.db.close()
