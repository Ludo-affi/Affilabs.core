"""User Profile Manager - Simple user profile storage and management.

Stores user profiles in a JSON file for tracking who runs experiments.
Profiles are saved in Excel metadata and used for filename generation.
"""

import json
from pathlib import Path
from typing import List

from affilabs.utils.logger import logger


class UserProfileManager:
    """Manages user profiles for experiment tracking."""

    def __init__(self, config_file: str = "user_profiles.json"):
        """Initialize user profile manager.
        
        Args:
            config_file: Name of JSON file to store profiles
        """
        self.config_file = Path(config_file)
        self.profiles: List[str] = []
        self.current_user: str = ""
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load user profiles from JSON file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.profiles = data.get('users', [])
                    self.current_user = data.get('current_user', '')
                    logger.debug(f"Loaded {len(self.profiles)} user profiles")
            except Exception as e:
                logger.error(f"Failed to load user profiles: {e}")
                self.profiles = ["Default User"]
                self.current_user = "Default User"
        else:
            # Create default profile
            self.profiles = ["Default User"]
            self.current_user = "Default User"
            self._save_profiles()

    def _save_profiles(self) -> None:
        """Save user profiles to JSON file."""
        try:
            data = {
                'users': self.profiles,
                'current_user': self.current_user
            }
            with open(self.config_file, 'w') as f:
                json.dump(data, indent=2, fp=f)
            logger.debug(f"Saved {len(self.profiles)} user profiles")
        except Exception as e:
            logger.error(f"Failed to save user profiles: {e}")

    def get_profiles(self) -> List[str]:
        """Get list of all user profiles.
        
        Returns:
            List of user profile names
        """
        return self.profiles.copy()

    def get_current_user(self) -> str:
        """Get currently selected user profile.
        
        Returns:
            Current user name
        """
        return self.current_user

    def set_current_user(self, username: str) -> None:
        """Set the current active user.
        
        Args:
            username: Name of user to set as current
        """
        if username in self.profiles:
            self.current_user = username
            self._save_profiles()
            logger.info(f"Current user set to: {username}")
        else:
            logger.warning(f"User '{username}' not found in profiles")

    def add_user(self, username: str) -> bool:
        """Add a new user profile.
        
        Args:
            username: Name of user to add
            
        Returns:
            True if user was added, False if already exists
        """
        if not username or username.strip() == "":
            logger.warning("Cannot add empty username")
            return False
            
        username = username.strip()
        
        if username in self.profiles:
            logger.warning(f"User '{username}' already exists")
            return False
        
        self.profiles.append(username)
        self.profiles.sort()  # Keep alphabetically sorted
        self._save_profiles()
        logger.info(f"Added new user: {username}")
        return True

    def remove_user(self, username: str) -> bool:
        """Remove a user profile.
        
        Args:
            username: Name of user to remove
            
        Returns:
            True if user was removed, False if not found
        """
        if username not in self.profiles:
            logger.warning(f"User '{username}' not found")
            return False
        
        # Don't allow removing the last user
        if len(self.profiles) == 1:
            logger.warning("Cannot remove the last user profile")
            return False
        
        self.profiles.remove(username)
        
        # If current user was removed, switch to first available
        if self.current_user == username:
            self.current_user = self.profiles[0]
        
        self._save_profiles()
        logger.info(f"Removed user: {username}")
        return True

    def get_user_for_metadata(self) -> dict:
        """Get user information for Excel metadata.
        
        Returns:
            Dictionary with user information
        """
        return {
            'User': self.current_user,
            'User_Profile_Count': len(self.profiles)
        }
