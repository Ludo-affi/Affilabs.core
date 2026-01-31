"""Method Manager - Save and load cycle queue methods.

Manages method files (sequences of cycles) for reusable experimental protocols.
Methods are stored as JSON files in a methods/ directory.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from affilabs.utils.logger import logger


class MethodManager:
    """Manages saving and loading of cycle queue methods."""

    def __init__(self, methods_dir: str = "methods", current_user: str = None):
        """Initialize method manager.
        
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
        logger.debug(f"Method manager initialized: {self.methods_dir} (user: {current_user or 'none'})")

    def save_method(
        self,
        name: str,
        cycles: List[Any],
        description: str = "",
        author: str = "",
    ) -> bool:
        """Save a method (cycle queue) to file.
        
        Args:
            name: Method name (filename will be sanitized)
            cycles: List of Cycle objects
            description: Optional description
            author: Optional author name
            
        Returns:
            True if saved successfully, False otherwise
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
            
            user_info = f" (user: {self.current_user})" if self.current_user else ""
            logger.info(f"✓ Method saved: {name} ({len(cycles_data)} cycles){user_info}")
            logger.debug(f"   Path: {filepath}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to save method: {e}")
            return False

    def load_method(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a method from file.
        
        Args:
            name: Method name (with or without .json extension)
            
        Returns:
            Method data dict with cycles, or None if not found
        """
        try:
            # Handle both "method_name" and "method_name.json"
            if not name.endswith('.json'):
                name = f"{name}.json"
            
            filepath = self.methods_dir / name
            
            if not filepath.exists():
                logger.warning(f"Method not found: {name}")
                return None
            
            with open(filepath, 'r') as f:
                method_data = json.load(f)
            
            logger.info(f"✓ Method loaded: {method_data.get('name', name)}")
            return method_data
            
        except Exception as e:
            logger.exception(f"Failed to load method: {e}")
            return None

    def get_methods_list(self) -> List[Dict[str, Any]]:
        """Get list of all saved methods with metadata.
        
        Returns:
            List of dicts with method info (name, description, cycle_count, created)
        """
        methods = []
        
        try:
            for filepath in self.methods_dir.glob("*.json"):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    methods.append({
                        "filename": filepath.stem,
                        "name": data.get("name", filepath.stem),
                        "description": data.get("description", ""),
                        "author": data.get("author", ""),
                        "cycle_count": data.get("cycle_count", len(data.get("cycles", []))),
                        "created": data.get("created", 0),
                    })
                except Exception as e:
                    logger.warning(f"Could not read method {filepath.name}: {e}")
            
            # Sort by creation time (newest first)
            methods.sort(key=lambda x: x['created'], reverse=True)
            
        except Exception as e:
            logger.exception(f"Failed to get methods list: {e}")
        
        return methods

    def delete_method(self, name: str) -> bool:
        """Delete a method file.
        
        Args:
            name: Method name (with or without .json extension)
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if not name.endswith('.json'):
                name = f"{name}.json"
            
            filepath = self.methods_dir / name
            
            if filepath.exists():
                filepath.unlink()
                logger.info(f"✓ Method deleted: {name}")
                return True
            else:
                logger.warning(f"Method not found: {name}")
                return False
                
        except Exception as e:
            logger.exception(f"Failed to delete method: {e}")
            return False

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
