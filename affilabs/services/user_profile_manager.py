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
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.profiles = data.get("users", [])
                    self.current_user = data.get("current_user", "")
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
            # Preserve existing user_data if it exists
            existing_user_data = {}
            if self.config_file.exists():
                try:
                    with open(self.config_file, "r") as f:
                        old_data = json.load(f)
                        existing_user_data = old_data.get("user_data", {})
                except Exception:
                    pass

            data = {
                "users": self.profiles,
                "current_user": self.current_user,
                "user_data": existing_user_data,
            }
            with open(self.config_file, "w") as f:
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

        # Initialize user_data for the new user
        self._initialize_user_data(username)

        self._save_profiles()
        logger.info(f"Added new user: {username}")
        return True

    def _initialize_user_data(self, username: str) -> None:
        """Initialize user_data entry for a new user.

        Args:
            username: Name of user to initialize data for
        """
        try:
            # Load existing data
            user_data = {}
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    user_data = data.get("user_data", {})

            # Initialize new user with default values
            if username not in user_data:
                user_data[username] = {
                    "experiment_count": 0,
                    "compression_training": {"completed": False, "score": None, "date": None},
                }

            # Save back
            data = {
                "users": self.profiles,
                "current_user": self.current_user,
                "user_data": user_data,
            }
            with open(self.config_file, "w") as f:
                json.dump(data, indent=2, fp=f)
            logger.debug(f"Initialized user_data for: {username}")
        except Exception as e:
            logger.error(f"Failed to initialize user_data for {username}: {e}")

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
        return {"User": self.current_user, "User_Profile_Count": len(self.profiles)}

    def get_progression_summary(self, username: str) -> dict:
        """Get progression summary for a user.

        Returns XP, title, and training status for the user progression banner.

        Args:
            username: The username to get summary for.

        Returns:
            Dictionary with progression data.
        """
        from enum import Enum

        class UserTitle(Enum):
            NOVICE = "Novice"
            OPERATOR = "Operator"
            SPECIALIST = "Specialist"
            EXPERT = "Expert"
            MASTER = "Master"

        exp_count = self.get_experiment_count(username)

        # Determine title based on experiment count
        titles = [
            (0, UserTitle.NOVICE, 5),
            (5, UserTitle.OPERATOR, 20),
            (20, UserTitle.SPECIALIST, 50),
            (50, UserTitle.EXPERT, 100),
            (100, UserTitle.MASTER, None),
        ]

        title = UserTitle.NOVICE
        next_title = UserTitle.OPERATOR
        remaining = 5 - exp_count
        for threshold, t, next_thresh in titles:
            if exp_count >= threshold:
                title = t
                if next_thresh is not None:
                    idx = titles.index((threshold, t, next_thresh))
                    if idx + 1 < len(titles):
                        next_title = titles[idx + 1][1]
                        remaining = next_thresh - exp_count
                    else:
                        next_title = None
                        remaining = 0
                else:
                    next_title = None
                    remaining = 0

        # Check compression training status
        compression_completed = False
        compression_score = None
        compression_date = None
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                user_data = data.get("user_data", {}).get(username, {})
                training = user_data.get("compression_training", {})
                compression_completed = training.get("completed", False)
                compression_score = training.get("score")
                compression_date = training.get("date")
        except Exception:
            pass

        return {
            "title": title.value,
            "xp": exp_count,
            "next_title": next_title.value if next_title else None,
            "experiments_to_next_title": max(0, remaining),
            "compression_training_completed": compression_completed,
            "compression_training_score": compression_score,
            "compression_training_date": compression_date,
        }

    def get_title(self, username: str) -> tuple:
        """Get the current title for a user based on experiment count.

        Args:
            username: The username to look up.

        Returns:
            Tuple of (UserTitle enum value, experiment_count).
        """
        from enum import Enum

        class UserTitle(Enum):
            NOVICE = "Novice"
            OPERATOR = "Operator"
            SPECIALIST = "Specialist"
            EXPERT = "Expert"
            MASTER = "Master"

        exp_count = self.get_experiment_count(username)
        thresholds = [
            (100, UserTitle.MASTER),
            (50, UserTitle.EXPERT),
            (20, UserTitle.SPECIALIST),
            (5, UserTitle.OPERATOR),
            (0, UserTitle.NOVICE),
        ]
        for threshold, title in thresholds:
            if exp_count >= threshold:
                return title, exp_count
        return UserTitle.NOVICE, exp_count

    def get_experiment_count(self, username: str) -> int:
        """Get experiment count for a user.

        Args:
            username: The username to look up.

        Returns:
            Number of experiments run by this user.
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                user_data = data.get("user_data", {}).get(username, {})
                return user_data.get("experiment_count", 0)
        except Exception:
            pass
        return 0

    def increment_experiment_count(self, username: str = None) -> int:
        """Increment experiment count for a user.

        Args:
            username: The username to increment. If None, uses current_user.

        Returns:
            New experiment count after increment.
        """
        if username is None:
            username = self.current_user

        if not username or username not in self.profiles:
            logger.warning(f"Cannot increment experiment count for invalid user: {username}")
            return 0

        try:
            # Load current data
            user_data = {}
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    user_data = data.get("user_data", {})

            # Initialize if doesn't exist
            if username not in user_data:
                user_data[username] = {
                    "experiment_count": 0,
                    "compression_training": {"completed": False, "score": None, "date": None},
                }

            # Increment count
            user_data[username]["experiment_count"] = (
                user_data[username].get("experiment_count", 0) + 1
            )
            new_count = user_data[username]["experiment_count"]

            # Save back
            data = {
                "users": self.profiles,
                "current_user": self.current_user,
                "user_data": user_data,
            }
            with open(self.config_file, "w") as f:
                json.dump(data, indent=2, fp=f)

            logger.info(f"Incremented experiment count for {username}: {new_count}")
            return new_count
        except Exception as e:
            logger.error(f"Failed to increment experiment count for {username}: {e}")
            return 0

    def set_experiment_count(self, username: str, count: int) -> bool:
        """Set experiment count for a user (for testing or manual adjustment).

        Args:
            username: The username to update.
            count: The new experiment count.

        Returns:
            True if successful, False otherwise.
        """
        if username not in self.profiles:
            logger.warning(f"Cannot set experiment count for non-existent user: {username}")
            return False

        try:
            # Load current data
            user_data = {}
            if self.config_file.exists():
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    user_data = data.get("user_data", {})

            # Initialize if doesn't exist
            if username not in user_data:
                user_data[username] = {
                    "experiment_count": 0,
                    "compression_training": {"completed": False, "score": None, "date": None},
                }

            # Set count
            user_data[username]["experiment_count"] = max(0, count)

            # Save back
            data = {
                "users": self.profiles,
                "current_user": self.current_user,
                "user_data": user_data,
            }
            with open(self.config_file, "w") as f:
                json.dump(data, indent=2, fp=f)

            logger.info(f"Set experiment count for {username}: {count}")
            return True
        except Exception as e:
            logger.error(f"Failed to set experiment count for {username}: {e}")
            return False

    def needs_compression_training(self, username: str) -> bool:
        """Check if a user still needs compression training.

        Training requirement has been removed — always returns False.
        """
        return False
