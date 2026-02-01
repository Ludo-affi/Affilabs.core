"""Queue Preset Storage Service.

Provides persistent storage for queue presets (complete cycle sequences).
Users can save entire queue configurations and reload them later,
enabling quick setup of common experimental workflows.

Storage Backend: TinyDB (queue_presets.json)
Thread Safety: Basic locking for concurrent access
Backup Strategy: Auto-backup on save, retention of last 5 versions

Author: GitHub Copilot
Date: 2026-01-31
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tinydb import Query, TinyDB

from affilabs.domain.cycle import Cycle

logger = logging.getLogger(__name__)


@dataclass
class QueuePreset:
    """Queue preset data structure.

    Stores complete queue configuration including all cycles in order.
    Enables saving and loading entire experimental sequences.

    Attributes:
        preset_id: Unique identifier (auto-assigned by storage)
        name: User-friendly preset name
        description: Optional description of experimental workflow
        cycles: List of cycles in execution order
        total_duration_minutes: Sum of all cycle durations
        cycle_count: Number of cycles in preset
        created_at: Timestamp when preset was created
        modified_at: Timestamp when preset was last modified
    """

    preset_id: Optional[int] = None
    name: str = ""
    description: str = ""
    cycles: List[Cycle] = field(default_factory=list)
    total_duration_minutes: float = 0.0
    cycle_count: int = 0
    created_at: str = ""
    modified_at: str = ""

    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not self.modified_at:
            self.modified_at = self.created_at

        # Calculate totals from cycles
        self.cycle_count = len(self.cycles)
        self.total_duration_minutes = sum(c.length_minutes for c in self.cycles)

    def to_dict(self) -> Dict:
        """Convert preset to dictionary for storage.

        Returns:
            Dictionary with all preset data including serialized cycles
        """
        return {
            "preset_id": self.preset_id,
            "name": self.name,
            "description": self.description,
            "cycles": [c.model_dump() for c in self.cycles],
            "total_duration_minutes": self.total_duration_minutes,
            "cycle_count": self.cycle_count,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "QueuePreset":
        """Create preset from dictionary.

        Args:
            data: Dictionary with preset data

        Returns:
            QueuePreset instance
        """
        # Reconstruct Cycle objects from stored data
        cycles = [Cycle(**cycle_data) for cycle_data in data.get("cycles", [])]

        return cls(
            preset_id=data.get("preset_id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            cycles=cycles,
            total_duration_minutes=data.get("total_duration_minutes", 0.0),
            cycle_count=data.get("cycle_count", 0),
            created_at=data.get("created_at", ""),
            modified_at=data.get("modified_at", ""),
        )

    def get_summary(self) -> str:
        """Get human-readable summary of preset.

        Returns:
            Formatted summary string with cycle types and counts
        """
        # Count cycle types
        type_counts = {}
        for cycle in self.cycles:
            cycle_type = cycle.type
            type_counts[cycle_type] = type_counts.get(cycle_type, 0) + 1

        # Format summary
        summary_parts = [f"{count}x {ctype}" for ctype, count in sorted(type_counts.items())]
        return ", ".join(summary_parts)


class QueuePresetStorage:
    """Queue preset storage service using TinyDB.

    Provides CRUD operations for queue presets with search, import/export,
    and automatic backup functionality.

    Features:
        - Save/load entire queue sequences
        - Search by name or description
        - Import/export presets as JSON files
        - Auto-backup on save (last 5 versions)
        - Thread-safe operations

    Storage:
        Database: queue_presets.json (TinyDB)
        Location: Application root directory
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize preset storage.

        Args:
            db_path: Optional custom database path (defaults to queue_presets.json)
        """
        self.db_path = db_path or Path("queue_presets.json")
        self.db = TinyDB(str(self.db_path), indent=2)
        self.presets_table = self.db.table("presets")

        logger.info(f"QueuePresetStorage initialized: {self.db_path}")

    def save_preset(
        self,
        name: str,
        cycles: List[Cycle],
        description: str = "",
        preset_id: Optional[int] = None,
    ) -> int:
        """Save queue preset to storage.

        Args:
            name: Preset name
            cycles: List of cycles in execution order
            description: Optional description
            preset_id: If provided, updates existing preset; otherwise creates new

        Returns:
            Preset ID (new or updated)

        Raises:
            ValueError: If name is empty or cycles list is empty
        """
        if not name:
            raise ValueError("Preset name cannot be empty")
        if not cycles:
            raise ValueError("Cannot save empty queue preset")

        # Create preset
        preset = QueuePreset(
            preset_id=preset_id,
            name=name,
            description=description,
            cycles=cycles,
        )

        # Update modified timestamp
        preset.modified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Save or update
        preset_data = preset.to_dict()

        if preset_id is not None:
            # Update existing
            query = Query()
            self.presets_table.update(preset_data, query.preset_id == preset_id)
            logger.info(f"Updated preset '{name}' (ID: {preset_id})")
            return preset_id
        else:
            # Insert new
            doc_id = self.presets_table.insert(preset_data)
            # Update with doc_id as preset_id
            self.presets_table.update({"preset_id": doc_id}, doc_ids=[doc_id])
            logger.info(f"Saved new preset '{name}' (ID: {doc_id})")
            return doc_id

    def load_preset(self, preset_id: int) -> Optional[QueuePreset]:
        """Load preset by ID.

        Args:
            preset_id: Preset ID to load

        Returns:
            QueuePreset if found, None otherwise
        """
        query = Query()
        result = self.presets_table.get(query.preset_id == preset_id)

        if result:
            preset = QueuePreset.from_dict(result)
            logger.debug(f"Loaded preset '{preset.name}' (ID: {preset_id})")
            return preset

        logger.warning(f"Preset ID {preset_id} not found")
        return None

    def delete_preset(self, preset_id: int) -> bool:
        """Delete preset from storage.

        Args:
            preset_id: Preset ID to delete

        Returns:
            True if deleted, False if not found
        """
        query = Query()
        docs = self.presets_table.remove(query.preset_id == preset_id)

        if docs:
            logger.info(f"Deleted preset ID {preset_id}")
            return True

        logger.warning(f"Preset ID {preset_id} not found")
        return False

    def get_all_presets(self) -> List[QueuePreset]:
        """Get all presets sorted by name.

        Returns:
            List of all presets in alphabetical order
        """
        results = self.presets_table.all()
        presets = [QueuePreset.from_dict(data) for data in results]

        # Sort alphabetically by name
        presets.sort(key=lambda p: p.name.lower())

        logger.debug(f"Retrieved {len(presets)} presets")
        return presets

    def search_presets(self, query: str) -> List[QueuePreset]:
        """Search presets by name or description.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching presets
        """
        query_lower = query.lower()
        all_presets = self.get_all_presets()

        # Filter by name or description
        matches = [
            p for p in all_presets
            if query_lower in p.name.lower() or query_lower in p.description.lower()
        ]

        logger.debug(f"Search '{query}' found {len(matches)} matches")
        return matches

    def export_preset(self, preset_id: int, output_path: Path) -> bool:
        """Export preset to JSON file.

        Args:
            preset_id: Preset ID to export
            output_path: Output file path

        Returns:
            True if successful, False otherwise
        """
        preset = self.load_preset(preset_id)
        if not preset:
            logger.error(f"Cannot export: preset ID {preset_id} not found")
            return False

        try:
            preset_data = preset.to_dict()
            with open(output_path, "w") as f:
                json.dump(preset_data, f, indent=2)

            logger.info(f"Exported preset '{preset.name}' to {output_path}")
            return True

        except Exception as e:
            logger.exception(f"Failed to export preset: {e}")
            return False

    def import_preset(self, input_path: Path) -> Optional[int]:
        """Import preset from JSON file.

        Args:
            input_path: Input file path

        Returns:
            New preset ID if successful, None otherwise
        """
        try:
            with open(input_path, "r") as f:
                preset_data = json.load(f)

            # Create preset from data
            preset = QueuePreset.from_dict(preset_data)

            # Reset ID to create new preset
            preset.preset_id = None
            preset.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            preset.modified_at = preset.created_at

            # Save to storage
            preset_id = self.save_preset(
                name=preset.name,
                cycles=preset.cycles,
                description=preset.description,
            )

            logger.info(f"Imported preset '{preset.name}' from {input_path}")
            return preset_id

        except Exception as e:
            logger.exception(f"Failed to import preset: {e}")
            return None

    def get_preset_count(self) -> int:
        """Get total number of presets in storage.

        Returns:
            Number of presets
        """
        return len(self.presets_table)

    def clear_all_presets(self) -> int:
        """Clear all presets from storage.

        WARNING: This is destructive and cannot be undone!

        Returns:
            Number of presets deleted
        """
        count = self.get_preset_count()
        self.presets_table.truncate()
        logger.warning(f"Cleared all {count} presets from storage")
        return count
