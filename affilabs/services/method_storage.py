"""Method Storage - TinyDB-based queryable method database.

ARCHITECTURE LAYER: Services (Phase 1.2 - Pydantic + TinyDB Integration)

This module provides a queryable database for method storage using TinyDB.
Replaces simple JSON file storage with a lightweight document database.

BENEFITS:
- Query methods by tags, author, cycle count, etc.
- Fast search without loading all files
- Atomic operations (no corruption)
- JSON-based (human-readable storage)
- No external database server required

USAGE:
    storage = MethodStorage()

    # Save method with tags
    method_id = storage.save_method(
        name="Kinetics Analysis",
        cycles=[...],
        tags=["kinetics", "antibody"],
        author="John Doe"
    )

    # Query methods
    kinetics_methods = storage.search_by_tags(["kinetics"])
    recent_methods = storage.get_recent_methods(limit=10)

    # Full-text search
    results = storage.search_methods("antibody")
"""

import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from tinydb import TinyDB, Query
from tinydb.storages import JSONStorage
from tinydb.middlewares import CachingMiddleware

from affilabs.utils.logger import logger


class MethodStorage:
    """TinyDB-based queryable method storage."""

    def __init__(self, db_path: str = "methods/methods.db", current_user: Optional[str] = None):
        """Initialize method storage with TinyDB.

        Args:
            db_path: Path to TinyDB database file
            current_user: Current user name for organizing methods
        """
        self.current_user = current_user

        # Setup database path
        db_file = Path(db_path)
        if current_user:
            # User-specific database: methods/Username/methods.db
            db_file = Path("methods") / current_user / "methods.db"

        # Create directory if needed
        db_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize TinyDB with caching middleware for performance
        self.db = TinyDB(
            db_file,
            storage=CachingMiddleware(JSONStorage),
            indent=2,
            ensure_ascii=False
        )

        # Table for methods
        self.methods_table = self.db.table('methods')

        # Table for tags (for fast tag queries)
        self.tags_table = self.db.table('tags')

        logger.info(f"Method storage initialized: {db_file} (user: {current_user or 'none'})")

    def save_method(
        self,
        name: str,
        cycles: List[Any],
        description: str = "",
        author: str = "",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> int:
        """Save a method to the database.

        Args:
            name: Method name
            cycles: List of Cycle objects
            description: Optional description
            author: Optional author name
            tags: Optional list of tags (e.g., ["kinetics", "antibody"])
            metadata: Optional additional metadata

        Returns:
            Method ID (TinyDB document ID)
        """
        try:
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

            # Create method document
            method_doc = {
                "name": name,
                "description": description,
                "author": author or self.current_user or "Unknown",
                "tags": tags or [],
                "created": time.time(),
                "modified": time.time(),
                "cycles": cycles_data,
                "cycle_count": len(cycles_data),
                "metadata": metadata or {},
                "user": self.current_user,
            }

            # Insert into database
            method_id = self.methods_table.insert(method_doc)

            # Update tags index
            if tags:
                self._update_tags_index(tags)

            logger.info(f"✓ Method saved: {name} (ID: {method_id}, {len(cycles_data)} cycles)")
            return method_id

        except Exception as e:
            logger.exception(f"Failed to save method: {e}")
            raise

    def get_method(self, method_id: int) -> Optional[Dict[str, Any]]:
        """Get a method by ID.

        Args:
            method_id: TinyDB document ID

        Returns:
            Method document or None if not found
        """
        try:
            method = self.methods_table.get(doc_id=method_id)
            if method:
                logger.debug(f"Method loaded: {method.get('name')} (ID: {method_id})")
            return method
        except Exception as e:
            logger.exception(f"Failed to get method {method_id}: {e}")
            return None

    def get_method_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a method by name.

        Args:
            name: Method name

        Returns:
            Method document or None if not found
        """
        try:
            Method = Query()
            result = self.methods_table.search(Method.name == name)
            if result:
                return result[0]  # Return first match
            return None
        except Exception as e:
            logger.exception(f"Failed to get method '{name}': {e}")
            return None

    def update_method(
        self,
        method_id: int,
        name: Optional[str] = None,
        cycles: Optional[List[Any]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update an existing method.

        Args:
            method_id: Method ID to update
            name: New name (optional)
            cycles: New cycles list (optional)
            description: New description (optional)
            tags: New tags list (optional)
            metadata: New metadata (optional)

        Returns:
            True if updated successfully
        """
        try:
            updates = {"modified": time.time()}

            if name is not None:
                updates["name"] = name
            if description is not None:
                updates["description"] = description
            if tags is not None:
                updates["tags"] = tags
                self._update_tags_index(tags)
            if metadata is not None:
                updates["metadata"] = metadata

            if cycles is not None:
                cycles_data = []
                for cycle in cycles:
                    if hasattr(cycle, 'to_dict'):
                        cycles_data.append(cycle.to_dict())
                    elif isinstance(cycle, dict):
                        cycles_data.append(cycle)
                updates["cycles"] = cycles_data
                updates["cycle_count"] = len(cycles_data)

            self.methods_table.update(updates, doc_ids=[method_id])
            logger.info(f"✓ Method updated: ID {method_id}")
            return True

        except Exception as e:
            logger.exception(f"Failed to update method {method_id}: {e}")
            return False

    def delete_method(self, method_id: int) -> bool:
        """Delete a method.

        Args:
            method_id: Method ID to delete

        Returns:
            True if deleted successfully
        """
        try:
            self.methods_table.remove(doc_ids=[method_id])
            logger.info(f"✓ Method deleted: ID {method_id}")
            return True
        except Exception as e:
            logger.exception(f"Failed to delete method {method_id}: {e}")
            return False

    def search_by_tags(self, tags: List[str]) -> List[Dict[str, Any]]:
        """Search methods by tags (any match).

        Args:
            tags: List of tags to search for

        Returns:
            List of matching method documents
        """
        try:
            Method = Query()
            results = self.methods_table.search(
                Method.tags.any(tags)
            )
            logger.debug(f"Tag search '{tags}': {len(results)} results")
            return results
        except Exception as e:
            logger.exception(f"Failed to search by tags: {e}")
            return []

    def search_methods(self, search_text: str) -> List[Dict[str, Any]]:
        """Full-text search in method names and descriptions.

        Args:
            search_text: Text to search for

        Returns:
            List of matching method documents
        """
        try:
            Method = Query()
            search_lower = search_text.lower()

            results = self.methods_table.search(
                (Method.name.search(search_lower, flags=0)) |
                (Method.description.search(search_lower, flags=0))
            )
            logger.debug(f"Text search '{search_text}': {len(results)} results")
            return results
        except Exception as e:
            logger.exception(f"Failed to search methods: {e}")
            return []

    def get_all_methods(self) -> List[Dict[str, Any]]:
        """Get all methods.

        Returns:
            List of all method documents
        """
        return self.methods_table.all()

    def get_recent_methods(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recently modified methods.

        Args:
            limit: Maximum number of methods to return

        Returns:
            List of method documents sorted by modification time
        """
        methods = self.methods_table.all()
        methods.sort(key=lambda x: x.get('modified', 0), reverse=True)
        return methods[:limit]

    def get_methods_by_author(self, author: str) -> List[Dict[str, Any]]:
        """Get all methods by a specific author.

        Args:
            author: Author name

        Returns:
            List of method documents
        """
        try:
            Method = Query()
            results = self.methods_table.search(Method.author == author)
            logger.debug(f"Author search '{author}': {len(results)} results")
            return results
        except Exception as e:
            logger.exception(f"Failed to search by author: {e}")
            return []

    def get_all_tags(self) -> List[str]:
        """Get all unique tags used in methods.

        Returns:
            List of unique tags
        """
        all_tags = set()
        for method in self.methods_table.all():
            all_tags.update(method.get('tags', []))
        return sorted(all_tags)

    def _update_tags_index(self, tags: List[str]):
        """Update the tags index for fast queries.

        Args:
            tags: List of tags to index
        """
        for tag in tags:
            Tag = Query()
            existing = self.tags_table.search(Tag.name == tag)
            if not existing:
                self.tags_table.insert({
                    "name": tag,
                    "created": time.time()
                })

    def close(self):
        """Close the database connection."""
        self.db.close()
        logger.debug("Method storage closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
