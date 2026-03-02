"""Software Update Manager — Check, download, and apply software updates.

Queries GitHub releases, compares with current version, and orchestrates exe replacement.
Supports both drop-in exe patches and full installer updates.
"""

import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.request import urlopen
from datetime import datetime
import json

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

class UpdateInfo(NamedTuple):
    """Update version and download info."""
    version: str
    release_name: str
    release_url: str
    exe_download_url: str
    installer_download_url: Optional[str]  # Only for major/minor updates
    release_notes: str
    release_date: str
    is_major_update: bool  # True = needs full installer, False = drop-in exe


class VersionInfo(NamedTuple):
    """Current software version."""
    version: str
    exe_path: Path
    backup_dir: Path


# ─────────────────────────────────────────────────────────────────────────────
# Update Manager Service
# ─────────────────────────────────────────────────────────────────────────────

class UpdateManager(QObject):
    """Manages software updates via GitHub releases and local exe replacement."""

    # Signals
    update_available = Signal(UpdateInfo)  # New version found
    update_checking = Signal(bool)  # True = checking, False = done checking
    update_error = Signal(str)  # Error message

    GITHUB_REPO = "Ludo-affi/Affilabs.core"  # Format: owner/repo
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    CHECK_INTERVAL_SECONDS = 86400  # Check once per day

    def __init__(self):
        super().__init__()
        self._check_thread: Optional[threading.Thread] = None
        self._stop_checking = False
        self._last_checked_version: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def get_current_version(self) -> str:
        """Get the current application version."""
        try:
            from version import __version__
            return __version__
        except ImportError:
            return "0.0.0"

    def get_exe_info(self) -> VersionInfo:
        """Get info about the currently running executable."""
        if hasattr(subprocess, "STARTUPINFO"):  # Windows
            exe_path = Path(os.sys.executable) if hasattr(os.sys, "executable") else Path("Affilabs-Core.exe")
            if not exe_path.exists():
                exe_path = Path(f"{os.path.dirname(__file__)}/../../Affilabs-Core.exe").resolve()
        else:
            exe_path = Path(os.sys.executable)

        from affilabs.utils.resource_path import get_writable_data_path
        backup_dir = get_writable_data_path("system/update_backups")
        backup_dir.mkdir(parents=True, exist_ok=True)

        return VersionInfo(
            version=self.get_current_version(),
            exe_path=exe_path,
            backup_dir=backup_dir,
        )

    def start_periodic_check(self) -> None:
        """Start background thread that periodically checks for updates."""
        if self._check_thread and self._check_thread.is_alive():
            logger.warning("Update check already running")
            return

        self._stop_checking = False
        self._check_thread = threading.Thread(
            target=self._periodic_check_worker, daemon=True
        )
        self._check_thread.start()
        logger.info("Started periodic update checker (1 hour interval)")

    def stop_periodic_check(self) -> None:
        """Stop the background update checking thread."""
        self._stop_checking = True
        if self._check_thread:
            self._check_thread.join(timeout=5)
            logger.info("Stopped periodic update checker")

    def check_for_updates_async(self) -> None:
        """Check for updates in a background thread (non-blocking)."""
        thread = threading.Thread(target=self.check_for_updates, daemon=True)
        thread.start()

    def check_for_updates(self) -> Optional[UpdateInfo]:
        """Check GitHub releases for a newer version.

        Returns:
            UpdateInfo if a newer version exists, None otherwise.
        """
        self.update_checking.emit(True)
        try:
            current = self.get_current_version()
            latest = self._fetch_latest_release()

            if not latest:
                logger.info("Could not fetch latest release info")
                return None

            if self._is_newer(latest.version, current):
                logger.info(f"Update available: {current} → {latest.version}")
                self._last_checked_version = latest.version
                self.update_available.emit(latest)
                return latest
            else:
                logger.debug(f"Already on latest version: {current}")
                return None

        except Exception as e:
            msg = f"Update check failed: {e}"
            logger.error(msg)
            self.update_error.emit(msg)
            return None
        finally:
            self.update_checking.emit(False)

    def download_and_apply_update(
        self,
        update_info: UpdateInfo,
        use_installer: bool = False,
    ) -> bool:
        """Download and apply the update.

        Args:
            update_info: The update to apply.
            use_installer: If True, download full installer; if False, drop-in exe.

        Returns:
            True if successful, False otherwise.
        """
        try:
            logger.info(f"Starting update to {update_info.version}")

            # Determine download URL
            download_url = (
                update_info.installer_download_url
                if use_installer
                else update_info.exe_download_url
            )

            if not download_url:
                raise ValueError(f"No download URL for update (installer={use_installer})")

            # Download the file
            temp_file = self._download_file(download_url)
            if not temp_file:
                raise RuntimeError("Download failed")

            logger.info(f"Downloaded: {temp_file}")

            if use_installer:
                # Full installer — launch installer and exit
                return self._launch_installer(temp_file, update_info.version)
            else:
                # Drop-in exe replacement
                exe_info = self.get_exe_info()
                if self._replace_exe(exe_info, temp_file):
                    logger.info(f"Update applied: {update_info.version}")
                    return True
                else:
                    raise RuntimeError("Exe replacement failed")

        except Exception as e:
            msg = f"Update failed: {e}"
            logger.error(msg)
            self.update_error.emit(msg)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Private API
    # ─────────────────────────────────────────────────────────────────────────

    def _periodic_check_worker(self) -> None:
        """Background worker that periodically checks for updates."""
        while not self._stop_checking:
            try:
                self.check_for_updates()
            except Exception as e:
                logger.error(f"Periodic check error: {e}")

            # Sleep in small intervals so we can stop quickly
            for _ in range(self.CHECK_INTERVAL_SECONDS):
                if self._stop_checking:
                    break
                threading.Event().wait(1)

    def _fetch_latest_release(self) -> Optional[UpdateInfo]:
        """Fetch the latest release info from GitHub API."""
        try:
            with urlopen(self.GITHUB_API_URL, timeout=10) as response:
                data = json.loads(response.read().decode())

            # Extract version from release tag (e.g., "v2.0.5" → "2.0.5")
            tag = data.get("tag_name", "").lstrip("v")
            if not tag:
                return None

            # Detect if this is a major/minor update by checking for "installer" asset
            installer_url = None
            exe_url = None

            for asset in data.get("assets", []):
                name = asset.get("name", "").lower()
                if "setup" in name or "installer" in name:
                    installer_url = asset.get("browser_download_url")
                elif "exe" in name and "setup" not in name:
                    exe_url = asset.get("browser_download_url")

            if not exe_url:
                logger.warning(f"No exe found in release {tag}")
                return None

            is_major = installer_url is not None

            return UpdateInfo(
                version=tag,
                release_name=data.get("name", tag),
                release_url=data.get("html_url", ""),
                exe_download_url=exe_url,
                installer_download_url=installer_url,
                release_notes=data.get("body", ""),
                release_date=data.get("published_at", "").split("T")[0],
                is_major_update=is_major,
            )

        except Exception as e:
            logger.error(f"Failed to fetch release info: {e}")
            return None

    def _is_newer(self, version_a: str, version_b: str) -> bool:
        """Compare two semantic version strings.

        Returns:
            True if version_a > version_b.
        """
        try:
            def parse(v: str):
                return tuple(map(int, v.split(".")))
            return parse(version_a) > parse(version_b)
        except Exception:
            logger.warning(f"Version comparison failed: {version_a} vs {version_b}")
            return False

    def _download_file(self, url: str) -> Optional[Path]:
        """Download a file from URL to a temp location.

        Returns:
            Path to downloaded file, or None if download failed.
        """
        try:
            temp_dir = Path.home() / ".affilabs" / "updates"
            temp_dir.mkdir(parents=True, exist_ok=True)

            filename = url.split("/")[-1] or "Affilabs-Core.exe"
            temp_file = temp_dir / filename

            logger.info(f"Downloading {url} → {temp_file}")

            with urlopen(url, timeout=60) as response:
                with open(temp_file, "wb") as f:
                    chunk_size = 8192
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)

            logger.info(f"Download complete: {temp_file.stat().st_size} bytes")
            return temp_file

        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None

    def _replace_exe(self, exe_info: VersionInfo, new_exe: Path) -> bool:
        """Replace the current exe with the new one (with backup).

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Verify new exe exists and is reasonably sized (> 10 MB)
            if not new_exe.exists():
                raise FileNotFoundError(f"Downloaded exe not found: {new_exe}")

            if new_exe.stat().st_size < 10 * 1024 * 1024:  # 10 MB minimum
                raise ValueError(f"Downloaded exe suspiciously small: {new_exe.stat().st_size} bytes")

            # Create backup of current exe
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = exe_info.backup_dir / f"Affilabs-Core_{exe_info.version}_{timestamp}.exe"

            if exe_info.exe_path.exists():
                logger.info(f"Backing up current exe → {backup_file}")
                shutil.copy2(exe_info.exe_path, backup_file)

            # Replace exe
            logger.info(f"Replacing exe: {exe_info.exe_path}")
            shutil.copy2(new_exe, exe_info.exe_path)

            # Mark for cleanup of temp file
            new_exe.unlink(missing_ok=True)

            logger.info("Exe replacement successful")
            return True

        except Exception as e:
            logger.error(f"Exe replacement failed: {e}")
            return False

    def _launch_installer(self, installer_path: Path, version: str) -> bool:
        """Launch the full installer and exit the app.

        Returns:
            True if launcher started successfully.
        """
        try:
            if not installer_path.exists():
                raise FileNotFoundError(f"Installer not found: {installer_path}")

            logger.info(f"Launching full installer: {installer_path}")
            subprocess.Popen([str(installer_path)])

            # Signal app to gracefully exit so installer can proceed
            logger.info("Installer launched. App will exit on next check.")
            return True

        except Exception as e:
            logger.error(f"Failed to launch installer: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Convenience factory
# ─────────────────────────────────────────────────────────────────────────────

_update_manager_instance: Optional[UpdateManager] = None


def get_update_manager() -> UpdateManager:
    """Get or create the singleton UpdateManager instance."""
    global _update_manager_instance
    if _update_manager_instance is None:
        _update_manager_instance = UpdateManager()
    return _update_manager_instance
