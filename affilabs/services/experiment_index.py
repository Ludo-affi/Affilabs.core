"""Experiment Index — searchable log of all recording sessions.

Appends one entry per completed file-mode recording to:
    <exe_dir>/data/experiment_index.json

Entries are written atomically (temp-file + os.replace) so a crash
mid-write never corrupts the existing index.

Search via ExperimentIndex().search(...) — all filters are optional and ANDed.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from affilabs.utils.logger import logger

_INDEX_FILENAME = "experiment_index.json"
_SCHEMA_VERSION = 2


class ExperimentIndex:
    """Read/write the experiment index at <exe_dir>/data/experiment_index.json."""

    def __init__(self, index_path: Path | None = None) -> None:
        if index_path is not None:
            self._path = index_path
        else:
            from affilabs.utils.resource_path import get_writable_data_path
            self._path = get_writable_data_path("data") / _INDEX_FILENAME

    # ── Public API ────────────────────────────────────────────────────────────

    def append_entry(self, entry: dict[str, Any]) -> None:
        """Append one entry to the index.

        Errors are logged as WARNING and never raised — a failed index write
        must never interrupt the recording stop flow.
        """
        try:
            data = self._load()
            data["entries"].append(entry)
            self._save(data)
            logger.debug(f"ExperimentIndex: entry written ({entry.get('id', '?')})")
        except Exception as exc:
            logger.warning(f"ExperimentIndex: failed to write entry: {exc}")

    def search(
        self,
        *,
        keyword: str | None = None,
        tags: list[str] | None = None,
        user: str | None = None,
        chip_serial: str | None = None,
        after: str | None = None,    # "YYYY-MM-DD" inclusive
        before: str | None = None,   # "YYYY-MM-DD" inclusive
        rating: int | None = None,   # exact star count filter, 0–5
        hardware_model: str | None = None,
        status: str | None = None,   # "completed" | "planned" | reserved for future
        # legacy positional aliases kept for callers that pass by position
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching entries sorted newest-first. All filters are optional (AND logic).

        ``after``/``date_from`` and ``before``/``date_to`` are synonyms
        (``after``/``before`` take precedence).
        """
        after = after or date_from
        before = before or date_to

        try:
            data = self._load()
        except Exception as exc:
            logger.warning(f"ExperimentIndex: failed to load for search: {exc}")
            return []

        results: list[dict[str, Any]] = []
        for entry in data.get("entries", []):
            if user and entry.get("user", "").lower() != user.lower():
                continue
            if chip_serial and chip_serial.lower() not in entry.get("chip_serial", "").lower():
                continue
            if hardware_model and hardware_model.lower() not in entry.get("hardware_model", "").lower():
                continue
            if after and entry.get("date", "") < after:
                continue
            if before and entry.get("date", "") > before:
                continue
            if rating is not None and entry.get("rating", 0) != rating:
                continue
            if tags:
                entry_tags = {t.lower() for t in entry.get("tags", [])}
                if not all(t.lower() in entry_tags for t in tags):
                    continue
            if keyword:
                haystack = " ".join([
                    entry.get("notes", ""),
                    entry.get("description", ""),
                    entry.get("analyte_suggestion", ""),
                    entry.get("file", ""),
                    " ".join(entry.get("tags", [])),
                ]).lower()
                if keyword.lower() not in haystack:
                    continue
            results.append(entry)

        return sorted(results, key=lambda e: e.get("date", "") + e.get("time", ""), reverse=True)

    def all_entries(self) -> list[dict[str, Any]]:
        """Return all entries, newest-first."""
        return self.search()

    # ── Rating ────────────────────────────────────────────────────────────────

    def set_rating(self, entry_id: str, rating: int) -> None:
        """Set star rating (0–5) on an entry. 0 means unrated."""
        if not 0 <= rating <= 5:
            raise ValueError(f"rating must be 0–5, got {rating}")
        self._update_entry_field(entry_id, "rating", rating)

    # ── Status ────────────────────────────────────────────────────────────────

    _VALID_STATUSES = {"done", "to_repeat", "archived"}

    def set_status(self, entry_id: str, status: str) -> None:
        """Set kanban status on an entry: 'done' | 'to_repeat' | 'archived'."""
        if status not in self._VALID_STATUSES:
            raise ValueError(f"status must be one of {self._VALID_STATUSES}, got {status!r}")
        self._update_entry_field(entry_id, "kanban_status", status)

    # ── Tags ──────────────────────────────────────────────────────────────────

    def add_tag(self, entry_id: str, tag: str) -> None:
        """Add a tag to an entry (no-op if already present)."""
        tag = tag.strip().lower()
        if not tag:
            return
        try:
            data = self._load()
            for entry in data["entries"]:
                if entry.get("id") == entry_id:
                    existing = entry.setdefault("tags", [])
                    if tag not in existing:
                        existing.append(tag)
                    self._save(data)
                    return
            logger.warning(f"ExperimentIndex.add_tag: entry {entry_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.add_tag failed: {exc}")

    def remove_tag(self, entry_id: str, tag: str) -> None:
        """Remove a tag from an entry (no-op if not present)."""
        tag = tag.strip().lower()
        try:
            data = self._load()
            for entry in data["entries"]:
                if entry.get("id") == entry_id:
                    entry["tags"] = [t for t in entry.get("tags", []) if t != tag]
                    self._save(data)
                    return
            logger.warning(f"ExperimentIndex.remove_tag: entry {entry_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.remove_tag failed: {exc}")

    def all_tags(self) -> dict[str, int]:
        """Return {tag: count} across all entries, sorted by descending count."""
        try:
            data = self._load()
        except Exception:
            return {}
        counts: dict[str, int] = {}
        for entry in data.get("entries", []):
            for t in entry.get("tags", []):
                counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    # ── Text fields ───────────────────────────────────────────────────────────

    def update_notes(self, entry_id: str, notes: str) -> None:
        """Update the ELN freeform notes field on an entry."""
        self._update_entry_field(entry_id, "notes", notes)

    def update_description(self, entry_id: str, description: str) -> None:
        """Update the short one-line description on an entry."""
        self._update_entry_field(entry_id, "description", description)

    # ── Planned entries ───────────────────────────────────────────────────────

    def create_planned(
        self,
        description: str,
        *,
        based_on: str | None = None,      # entry_id of an existing run to copy from
        method_id: str | None = None,     # cycle_template_storage template id
        target_date: str | None = None,   # "YYYY-MM-DD"
        notes: str = "",
    ) -> str:
        """Create a planned (not-yet-run) entry. Returns plan_id."""
        import uuid
        plan_id = f"plan_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:6]}"
        plan: dict[str, Any] = {
            "id": plan_id,
            "description": description,
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "target_date": target_date or "",
            "based_on": based_on or "",
            "method_id": method_id or "",
            "notes": notes,
            "linked_entry_id": "",  # filled by link_planned_to_recording
        }
        try:
            data = self._load()
            data["planned"].append(plan)
            self._save(data)
            logger.debug(f"ExperimentIndex: planned entry created ({plan_id})")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.create_planned failed: {exc}")
        return plan_id

    def update_planned(self, plan_id: str, **fields: Any) -> None:
        """Update one or more fields on a planned entry."""
        forbidden = {"id", "created_date", "linked_entry_id"}
        try:
            data = self._load()
            for plan in data["planned"]:
                if plan.get("id") == plan_id:
                    for k, v in fields.items():
                        if k not in forbidden:
                            plan[k] = v
                    self._save(data)
                    return
            logger.warning(f"ExperimentIndex.update_planned: plan {plan_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.update_planned failed: {exc}")

    def delete_planned(self, plan_id: str) -> None:
        """Remove a planned entry by id."""
        try:
            data = self._load()
            before_count = len(data["planned"])
            data["planned"] = [p for p in data["planned"] if p.get("id") != plan_id]
            if len(data["planned"]) < before_count:
                self._save(data)
            else:
                logger.warning(f"ExperimentIndex.delete_planned: plan {plan_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.delete_planned failed: {exc}")

    def link_planned_to_recording(self, plan_id: str, entry_id: str) -> None:
        """Mark a planned entry as completed by linking it to a real recording entry."""
        try:
            data = self._load()
            for plan in data["planned"]:
                if plan.get("id") == plan_id:
                    plan["linked_entry_id"] = entry_id
                    self._save(data)
                    return
            logger.warning(f"ExperimentIndex.link_planned_to_recording: plan {plan_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex.link_planned_to_recording failed: {exc}")

    def all_planned(self) -> list[dict[str, Any]]:
        """Return all planned entries, ordered by target_date then created_date."""
        try:
            data = self._load()
        except Exception:
            return []
        return sorted(
            data.get("planned", []),
            key=lambda p: (p.get("target_date") or "9999", p.get("created_date", "")),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_entry_field(self, entry_id: str, field: str, value: Any) -> None:
        """Generic single-field updater for completed entries."""
        try:
            data = self._load()
            for entry in data["entries"]:
                if entry.get("id") == entry_id:
                    entry[field] = value
                    self._save(data)
                    return
            logger.warning(f"ExperimentIndex._update_entry_field: entry {entry_id!r} not found")
        except Exception as exc:
            logger.warning(f"ExperimentIndex._update_entry_field({field!r}) failed: {exc}")

    def _load(self) -> dict[str, Any]:
        """Load and return the index dict, creating a blank one if missing."""
        if not self._path.exists():
            return {"schema_version": _SCHEMA_VERSION, "entries": [], "planned": []}

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "entries" not in data:
                raise ValueError("Missing 'entries' key")
            # v1 → v2 migration: add planned key
            if "planned" not in data:
                data["planned"] = []
                data["schema_version"] = _SCHEMA_VERSION
            return data
        except Exception as exc:
            # Back up corrupt file, start fresh
            bak = self._path.with_suffix(".json.bak")
            try:
                import shutil
                shutil.copy2(self._path, bak)
                logger.warning(f"ExperimentIndex: corrupt index backed up to {bak}, starting fresh")
            except Exception:
                pass
            return {"schema_version": _SCHEMA_VERSION, "entries": [], "planned": []}

    def _save(self, data: dict[str, Any]) -> None:
        """Write data atomically via temp file + os.replace."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._path)


# ── Convenience function called by RecordingManager ──────────────────────────

def record_experiment(
    *,
    current_file: str | Path,
    recording_start_time: float,
    cycles: list,
    metadata: dict[str, Any],
    user_manager=None,
    calibration_run: bool = False,
    baseline_run: bool = False,
    analyte_suggestion: str = "",
) -> None:
    """Build and append an index entry from RecordingManager state.

    Args:
        current_file: Absolute path to the saved .xlsx file.
        recording_start_time: Unix timestamp from DataCollector.recording_start_time.
        cycles: DataCollector.cycles list (used for count only).
        metadata: DataCollector.metadata dict.
        user_manager: UserProfileManager instance (optional).
        calibration_run: True if calibration was performed before this recording.
        baseline_run: True if a baseline-only run was detected.
        analyte_suggestion: Tag/analyte name inferred at recording_stopped (may be empty).
    """
    try:
        from affilabs.utils.resource_path import get_writable_data_path
        base = get_writable_data_path("data")
        abs_file = Path(current_file)
        try:
            rel_file = str(abs_file.relative_to(base))
        except ValueError:
            rel_file = str(abs_file)  # file saved outside standard tree — store absolute

        username = ""
        if user_manager:
            try:
                username = user_manager.get_current_user() or ""
            except Exception:
                pass

        now = datetime.now()
        duration_min = round((time.time() - recording_start_time) / 60, 1) if recording_start_time else 0.0

        entry: dict[str, Any] = {
            "id": f"{now.strftime('%Y%m%dT%H%M%S')}_{username}",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "user": username,
            "file": rel_file,
            "chip_serial": metadata.get("detector_serial", ""),
            "hardware_model": metadata.get("hardware_model", ""),
            "duration_min": duration_min,
            "cycle_count": len(cycles),
            "notes": "",
            "description": "",
            "rating": 0,
            "tags": [],
            "calibration_run": calibration_run,
            "baseline_run": baseline_run,
            "analyte_suggestion": analyte_suggestion,
        }

        ExperimentIndex().append_entry(entry)

    except Exception as exc:
        logger.warning(f"ExperimentIndex: record_experiment failed: {exc}")
