"""
OQ Suite 5 — Configuration
Req IDs: OQ-CFG-001 to OQ-CFG-004

Verifies that required configuration files are present, valid, and parseable.
No hardware required — filesystem reads only.
"""
import json
import re
import sys
from pathlib import Path

import pytest

# Repo root so absolute imports work
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.mark.req("OQ-CFG-001")
def test_user_profiles_json_schema():
    """user_profiles.json must be valid JSON with a 'users' key containing ≥1 entry."""
    path = ROOT / "user_profiles.json"
    assert path.exists(), f"user_profiles.json not found at {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "users" in data, "'users' key missing from user_profiles.json"
    assert len(data["users"]) >= 1, "user_profiles.json must contain at least one user entry"


@pytest.mark.req("OQ-CFG-002")
def test_detector_profile_schema():
    """At least one detector_profiles/*.json must exist with required top-level keys."""
    profile_dir = ROOT / "detector_profiles"
    assert profile_dir.is_dir(), f"detector_profiles/ directory not found at {profile_dir}"
    profiles = list(profile_dir.glob("*.json"))
    assert len(profiles) >= 1, "No .json files found in detector_profiles/"

    required_keys = {"hardware_specs", "acquisition_limits", "spr_settings"}
    for profile_path in profiles:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        missing = required_keys - set(data.keys())
        assert not missing, (
            f"{profile_path.name} is missing required keys: {missing}"
        )


@pytest.mark.req("OQ-CFG-003")
def test_version_file_semver():
    """VERSION file must exist and match semver pattern \\d+\\.\\d+\\.\\d+."""
    version_path = ROOT / "VERSION"
    assert version_path.exists(), f"VERSION file not found at {version_path}"
    content = version_path.read_text(encoding="utf-8").strip()
    assert re.match(r"^\d+\.\d+\.\d+", content), (
        f"VERSION file content '{content}' does not match semver pattern"
    )


@pytest.mark.req("OQ-CFG-004")
def test_channel_indices_importable():
    """CHANNEL_INDICES must be importable from affilabs.app_state and contain a/b/c/d keys."""
    from affilabs.app_state import CHANNEL_INDICES  # noqa: PLC0415

    assert isinstance(CHANNEL_INDICES, dict), "CHANNEL_INDICES must be a dict"
    for ch in ("a", "b", "c", "d"):
        assert ch in CHANNEL_INDICES, f"CHANNEL_INDICES missing key '{ch}'"
