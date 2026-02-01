"""Method Manager - Save and load cycle queue methods.

Manages method files (sequences of cycles) for reusable experimental protocols.

ARCHITECTURE LAYER: Services (Phase 1.2 - Enhanced with TinyDB)

STORAGE BACKENDS:
- TinyDB: Primary storage (queryable, tagged methods)
- JSON Files: Legacy backup (for compatibility)

ENHANCEMENTS:
- Queryable database with tags and search
- Method templates (Pro tier)
- Backward compatible with JSON files
- Automatic migration from JSON to TinyDB

USAGE:
    manager = MethodManager(current_user="John Doe")

    # Save method with tags
    manager.save_method(
        name="Kinetics Analysis",
        cycles=[...],
        tags=["kinetics", "antibody"]
    )

    # Search methods
    results = manager.search_methods("kinetics")
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from affilabs.services.method_storage import MethodStorage
from affilabs.utils.logger import logger


class MethodManager:
    """Manages saving and loading of cycle queue methods with TinyDB backend."""

    def __init__(self, methods_dir: str = "methods", current_user: str = None):
        """Initialize method manager with TinyDB storage.

        Args:
            methods_dir: Base directory to store method files
            current_user: Current user name for organizing files
        """
        self.base_dir = Path(methods_dir)
        self.current_user = current_user

        # If user is specified, organize into user subfolder
        if current_user:
            # Create: methods/Username/ (parallel to output/Username/SPR_data/)
            self.methods_dir = self.base_dir / current_user
        else:
            # Create: methods/ (flat structure for no user)
            self.methods_dir = self.base_dir

        self.methods_dir.mkdir(parents=True, exist_ok=True)

        # Initialize TinyDB storage
        self.storage = MethodStorage(current_user=current_user)

        # Migrate legacy JSON files to TinyDB on first run
        self._migrate_json_files()

        logger.debug(f"Method manager initialized: {self.methods_dir} (user: {current_user or 'none'})")

    def save_method(
        self,
        name: str,
        cycles: List[Any],
        description: str = "",
        author: str = "",
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Save a method (cycle queue) to TinyDB and JSON backup.

        Args:
            name: Method name (filename will be sanitized)
            cycles: List of Cycle objects
            description: Optional description
            author: Optional author name
            tags: Optional list of tags for categorization

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Save to TinyDB (primary storage)
            method_id = self.storage.save_method(
                name=name,
                cycles=cycles,
                description=description,
                author=author or self.current_user or "",
                tags=tags or [],
            )

            # Also save as JSON backup for compatibility
            self._save_json_backup(name, cycles, description, author)

            logger.info(f"✓ Method saved: {name} (ID: {method_id})")
            return True

        except Exception as e:
            logger.exception(f"Failed to save method: {e}")
            return False

    def _save_json_backup(
        self,
        name: str,
        cycles: List[Any],
        description: str = "",
        author: str = "",
    ):
        """Save JSON backup for backward compatibility.

        Args:
            name: Method name
            cycles: List of Cycle objects
            description: Method description
            author: Method author
        """
        try:
            # Sanitize filename
            safe_name = self._sanitize_filename(name)
            filepath = self.methods_dir / f"{safe_name}.json"

            # Convert cycles to dict format
            cycles_data = []
            for cycle in cycles:
                if hasattr(cycle, 'to_dict'):
                    cycles_data.append(cycle.to_dict())
                elif isinstance(cycle, dict):
                    cycles_data.append(cycle)
                else:
                    logger.warning(f"Unknown cycle format: {type(cycle)}")
                    continue

            # Create method data
            method_data = {
                "name": name,
                "description": description,
                "author": author,
                "created": time.time(),
                "cycles": cycles_data,
                "cycle_count": len(cycles_data),
            }

            # Save to file
            with open(filepath, 'w') as f:
                json.dump(method_data, f, indent=2)

            logger.debug(f"JSON backup saved: {filepath}")

        except Exception as e:
            logger.warning(f"Failed to save JSON backup: {e}")

    def load_method(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a method from TinyDB or JSON fallback.

        Args:
            name: Method name (with or without .json extension)

        Returns:
            Method data dict with cycles, or None if not found
        """
        try:
            # Try loading from TinyDB first
            method_data = self.storage.get_method_by_name(name.replace('.json', ''))

            if method_data:
                logger.info(f"✓ Method loaded from DB: {method_data.get('name', name)}")
                return method_data

            # Fallback to JSON file
            if not name.endswith('.json'):
                name = f"{name}.json"

            filepath = self.methods_dir / name

            if not filepath.exists():
                logger.warning(f"Method not found: {name}")
                return None

            with open(filepath, 'r') as f:
                method_data = json.load(f)

            logger.info(f"✓ Method loaded from JSON: {method_data.get('name', name)}")

            # Migrate to TinyDB for future use
            self._migrate_method_to_db(method_data)

            return method_data

        except Exception as e:
            logger.exception(f"Failed to load method: {e}")
            return None

    def get_methods_list(self) -> List[Dict[str, Any]]:
        """Get list of all saved methods with metadata from TinyDB.

        Returns:
            List of dicts with method info (name, description, cycle_count, created)
        """
        try:
            # Get from TinyDB
            methods = self.storage.get_all_methods()

            # Format for UI compatibility
            formatted = []
            for method in methods:
                formatted.append({
                    "filename": self._sanitize_filename(method.get("name", "unknown")),
                    "name": method.get("name", "Unknown"),
                    "description": method.get("description", ""),
                    "author": method.get("author", ""),
                    "cycle_count": method.get("cycle_count", len(method.get("cycles", []))),
                    "created": method.get("created", 0),
                    "tags": method.get("tags", []),
                })

            # Sort by creation time (newest first)
            formatted.sort(key=lambda x: x['created'], reverse=True)

            return formatted

        except Exception as e:
            logger.exception(f"Failed to get methods list: {e}")
            return []

    def search_methods(self, search_text: str) -> List[Dict[str, Any]]:
        """Search methods by text (name, description, tags).

        Args:
            search_text: Search query

        Returns:
            List of matching method documents
        """
        return self.storage.search_methods(search_text)

    def search_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Search methods by tags.

        Args:
            tags: List of tags to search for

        Returns:
            List of matching method documents
        """
        return self.storage.search_by_tags(tags)

    def delete_method(self, name: str) -> bool:
        """Delete a method from both TinyDB and JSON file.

        Args:
            name: Method name (with or without .json extension)

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Delete from TinyDB
            method = self.storage.get_method_by_name(name.replace('.json', ''))
            if method:
                # Get the document ID (TinyDB internal ID)
                method_id = method.doc_id if hasattr(method, 'doc_id') else None
                if method_id:
                    self.storage.delete_method(method_id)

            # Delete JSON file
            if not name.endswith('.json'):
                name = f"{name}.json"

            filepath = self.methods_dir / name

            if filepath.exists():
                filepath.unlink()
                logger.info(f"✓ Method deleted: {name}")
                return True
            else:
                logger.warning(f"Method file not found: {name}")
                return method is not None  # Return True if deleted from DB

        except Exception as e:
            logger.exception(f"Failed to delete method: {e}")
            return False

    def _migrate_json_files(self):
        """Migrate existing JSON files to TinyDB on first run."""
        try:
            json_files = list(self.methods_dir.glob("*.json"))

            if not json_files:
                return

            migrated_count = 0

            for filepath in json_files:
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    # Check if already in DB
                    existing = self.storage.get_method_by_name(data.get('name', filepath.stem))
                    if existing:
                        continue

                    # Migrate to DB
                    self._migrate_method_to_db(data)
                    migrated_count += 1

                except Exception as e:
                    logger.warning(f"Failed to migrate {filepath.name}: {e}")

            if migrated_count > 0:
                logger.info(f"✓ Migrated {migrated_count} methods from JSON to TinyDB")

        except Exception as e:
            logger.exception(f"Failed to migrate JSON files: {e}")

    def _migrate_method_to_db(self, method_data: Dict[str, Any]):
        """Migrate a single method to TinyDB.

        Args:
            method_data: Method data from JSON file
        """
        try:
            self.storage.save_method(
                name=method_data.get('name', 'Unknown'),
                cycles=method_data.get('cycles', []),
                description=method_data.get('description', ''),
                author=method_data.get('author', ''),
                tags=method_data.get('tags', []),
            )
            logger.debug(f"Migrated method: {method_data.get('name')}")
        except Exception as e:
            logger.warning(f"Failed to migrate method: {e}")

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize method name for use as filename.

        Args:
            name: Original method name

        Returns:
            Sanitized filename (no special chars)
        """
        # Replace spaces with underscores
        safe = name.replace(' ', '_')

        # Remove special characters
        safe = ''.join(c for c in safe if c.isalnum() or c in ('_', '-'))

        # Limit length
        safe = safe[:50]

        return safe
