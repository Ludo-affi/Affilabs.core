"""
Security and Access Control System for OEM Service Mode

Implements password-protected superadmin access for OEM personnel.
Separates user-level access from OEM service mode.

Features:
- Password-protected OEM authentication
- Encrypted password storage (SHA-256)
- Session timeout (auto-lock after inactivity)
- Audit logging of all access attempts
- Password change functionality

Usage:
    from utils.security import get_security_manager

    security = get_security_manager()
    if security.authenticate_oem("password"):
        # OEM access granted
        enable_service_mode()

Author: AI Assistant
Date: October 11, 2025
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from utils.logger import logger


class SecurityManager:
    """
    Manages OEM superadmin access and password authentication.

    Singleton pattern ensures only one security manager exists.
    """

    # Session timeout (minutes)
    SESSION_TIMEOUT_MINUTES = 30

    # Salt for password hashing (in production, generate unique salt per installation)
    SALT = "ezControl_SPR_OEM_2025"

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize security manager.

        Args:
            config_dir: Directory for security config (default: C:/Users/<user>/ezControl/config)
        """
        if config_dir is None:
            config_dir = Path.home() / "ezControl" / "config"

        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.security_file = self.config_dir / "security.json"
        self.audit_log_file = self.config_dir / "access_audit.log"

        self.session_active = False
        self.session_start_time: Optional[datetime] = None
        self.session_user = None

        self._load_security_config()

    def _load_security_config(self):
        """Load or create security configuration."""
        if self.security_file.exists():
            try:
                with open(self.security_file, 'r') as f:
                    config = json.load(f)
                    self.password_hash = config.get('oem_password_hash')
                    logger.info("🔒 Security config loaded")
            except Exception as e:
                logger.error(f"Failed to load security config: {e}")
                self._create_default_config()
        else:
            self._create_default_config()

    def _create_default_config(self):
        """Create default security configuration with initial password."""
        # Default OEM password: "Affinite2025"
        default_password = "Affinite2025"
        self.password_hash = self._hash_password(default_password)

        config = {
            'oem_password_hash': self.password_hash,
            'password_set_date': datetime.now().isoformat(),
            'last_changed': datetime.now().isoformat(),
            'version': '1.0',
            'note': 'OEM Superadmin password. Keep secure!'
        }

        try:
            with open(self.security_file, 'w') as f:
                json.dump(config, f, indent=2)

            # Make file read-only for non-admins (Windows: read-only attribute)
            try:
                os.chmod(self.security_file, 0o600)  # Owner read/write only
            except:
                pass  # May fail on Windows, that's OK

            logger.warning("⚠️ Default OEM password created!")
            logger.warning(f"📝 Default password: '{default_password}'")
            logger.warning("🔐 Change this password immediately in production!")

            # Log to audit
            self._audit_log("SYSTEM", "Default password created", success=True)

        except Exception as e:
            logger.error(f"Failed to create security config: {e}")

    def _hash_password(self, password: str) -> str:
        """
        Hash password using SHA-256 with salt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string (hex)
        """
        salted_password = f"{self.SALT}{password}{self.SALT}"
        return hashlib.sha256(salted_password.encode()).hexdigest()

    def _audit_log(self, user: str, action: str, success: bool, details: str = ""):
        """
        Log access attempt to audit log.

        Args:
            user: Username or "SYSTEM"
            action: Action attempted
            success: Whether action succeeded
            details: Additional details
        """
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"

        log_entry = f"[{timestamp}] {status} | User: {user} | Action: {action}"
        if details:
            log_entry += f" | Details: {details}"

        try:
            with open(self.audit_log_file, 'a') as f:
                f.write(log_entry + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def authenticate_oem(self, password: str, username: str = "OEM") -> bool:
        """
        Authenticate OEM user with password.

        Args:
            password: Plain text password to verify
            username: Username for audit log (default: "OEM")

        Returns:
            True if authentication successful, False otherwise
        """
        password_hash = self._hash_password(password)

        if password_hash == self.password_hash:
            # Authentication successful
            self.session_active = True
            self.session_start_time = datetime.now()
            self.session_user = username

            logger.info(f"✅ OEM authentication successful for user: {username}")
            self._audit_log(username, "OEM Login", success=True)
            return True
        else:
            # Authentication failed
            logger.warning(f"❌ OEM authentication failed for user: {username}")
            self._audit_log(username, "OEM Login", success=False, details="Invalid password")
            return False

    def is_session_active(self) -> bool:
        """
        Check if OEM session is active and not expired.

        Returns:
            True if session is active and not expired, False otherwise
        """
        if not self.session_active:
            return False

        if self.session_start_time is None:
            return False

        # Check if session has expired
        elapsed = datetime.now() - self.session_start_time
        if elapsed > timedelta(minutes=self.SESSION_TIMEOUT_MINUTES):
            logger.warning(f"⏱️ OEM session expired after {self.SESSION_TIMEOUT_MINUTES} minutes")
            self.end_session()
            return False

        return True

    def refresh_session(self):
        """Refresh session timeout (reset timer)."""
        if self.session_active:
            self.session_start_time = datetime.now()
            logger.debug("🔄 OEM session refreshed")

    def end_session(self):
        """End OEM session and lock service mode."""
        if self.session_active:
            logger.info(f"🔒 OEM session ended for user: {self.session_user}")
            self._audit_log(self.session_user or "UNKNOWN", "OEM Logout", success=True)

        self.session_active = False
        self.session_start_time = None
        self.session_user = None

    def change_password(self, old_password: str, new_password: str) -> tuple[bool, str]:
        """
        Change OEM password.

        Args:
            old_password: Current password
            new_password: New password

        Returns:
            Tuple of (success, message)
        """
        # Verify old password
        if not self.authenticate_oem(old_password, username="PASSWORD_CHANGE"):
            return False, "Current password is incorrect"

        # Validate new password
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters"

        # Update password
        self.password_hash = self._hash_password(new_password)

        config = {
            'oem_password_hash': self.password_hash,
            'password_set_date': datetime.now().isoformat(),
            'last_changed': datetime.now().isoformat(),
            'version': '1.0',
            'note': 'OEM Superadmin password. Keep secure!'
        }

        try:
            with open(self.security_file, 'w') as f:
                json.dump(config, f, indent=2)

            logger.info("✅ OEM password changed successfully")
            self._audit_log(self.session_user or "OEM", "Password Changed", success=True)
            return True, "Password changed successfully"

        except Exception as e:
            logger.error(f"Failed to save new password: {e}")
            return False, f"Failed to save password: {e}"

    def get_session_info(self) -> dict:
        """
        Get current session information.

        Returns:
            Dictionary with session info
        """
        if not self.session_active:
            return {
                'active': False,
                'user': None,
                'start_time': None,
                'elapsed_minutes': 0,
                'remaining_minutes': 0
            }

        elapsed = datetime.now() - self.session_start_time
        elapsed_minutes = int(elapsed.total_seconds() / 60)
        remaining_minutes = max(0, self.SESSION_TIMEOUT_MINUTES - elapsed_minutes)

        return {
            'active': True,
            'user': self.session_user,
            'start_time': self.session_start_time.isoformat(),
            'elapsed_minutes': elapsed_minutes,
            'remaining_minutes': remaining_minutes,
            'timeout_minutes': self.SESSION_TIMEOUT_MINUTES
        }


# Singleton instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """
    Get singleton security manager instance.

    Returns:
        SecurityManager instance
    """
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def require_oem_access(func):
    """
    Decorator to require active OEM session for function execution.

    Usage:
        @require_oem_access
        def change_critical_setting(value):
            # This will only run if OEM session is active
            pass
    """
    def wrapper(*args, **kwargs):
        security = get_security_manager()
        if not security.is_session_active():
            logger.error("❌ OEM access required but session not active")
            raise PermissionError("OEM authentication required")

        security.refresh_session()  # Keep session alive
        return func(*args, **kwargs)

    return wrapper


# Convenience functions
def authenticate_oem(password: str) -> bool:
    """Authenticate OEM user (convenience function)."""
    return get_security_manager().authenticate_oem(password)


def is_oem_authenticated() -> bool:
    """Check if OEM session is active (convenience function)."""
    return get_security_manager().is_session_active()


def end_oem_session():
    """End OEM session (convenience function)."""
    get_security_manager().end_session()


if __name__ == "__main__":
    # Test security manager
    print("🔐 Security Manager Test")
    print("=" * 50)

    security = get_security_manager()

    print(f"\n📝 Default password: 'Affinite2025'")
    print(f"📁 Security file: {security.security_file}")
    print(f"📋 Audit log: {security.audit_log_file}")

    # Test authentication
    print("\n🔓 Testing authentication...")
    if security.authenticate_oem("Affinite2025"):
        print("✅ Authentication successful!")

        session_info = security.get_session_info()
        print(f"\n📊 Session Info:")
        print(f"   User: {session_info['user']}")
        print(f"   Active: {session_info['active']}")
        print(f"   Timeout: {session_info['timeout_minutes']} minutes")

        security.end_session()
        print("\n🔒 Session ended")
    else:
        print("❌ Authentication failed!")

    print("\n✅ Security manager test complete")
