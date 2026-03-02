"""
OQ Suite 2 — Data Recording
Req IDs: OQ-REC-001 to OQ-REC-009

Verifies RecordingManager lifecycle and ExperimentIndex CRUD operations.
No hardware required — in-memory and tmp filesystem only.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from affilabs.domain.timeline import EventContext, TimelineEventStream
from affilabs.services.experiment_index import ExperimentIndex


# ---------------------------------------------------------------------------
# RecordingManager tests
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-REC-001")
def test_recording_manager_instantiates():
    """RecordingManager(data_mgr=None) must instantiate with a TimelineEventStream."""
    from affilabs.core.recording_manager import RecordingManager

    mgr = RecordingManager(data_mgr=None)
    assert isinstance(mgr._timeline_stream, TimelineEventStream)
    assert len(mgr._timeline_stream) == 0


@pytest.mark.req("OQ-REC-002")
def test_recording_manager_start_creates_context():
    """start_recording() must create a TimelineContext with the supplied offset."""
    from affilabs.core.recording_manager import RecordingManager

    mgr = RecordingManager(data_mgr=None)
    mgr.start_recording(filename=None, time_offset=5.0)
    ctx = mgr.get_timeline_context()
    assert ctx is not None, "TimelineContext must not be None after start_recording()"
    assert ctx.recording_start_offset == 5.0, (
        f"Expected offset 5.0, got {ctx.recording_start_offset}"
    )


@pytest.mark.req("OQ-REC-003")
def test_recording_manager_stop_clears_context():
    """stop_recording() must clear the TimelineContext."""
    from affilabs.core.recording_manager import RecordingManager

    mgr = RecordingManager(data_mgr=None)
    mgr.start_recording(filename=None, time_offset=0.0)
    assert mgr.get_timeline_context() is not None
    mgr.stop_recording()
    assert mgr.get_timeline_context() is None, (
        "TimelineContext must be None after stop_recording()"
    )


# ---------------------------------------------------------------------------
# ExperimentIndex tests
# ---------------------------------------------------------------------------

import uuid as _uuid


def _make_entry(label: str = "test run") -> dict:
    return {
        "id": _uuid.uuid4().hex,
        "date": "2026-03-01",
        "time": "10:00:00",
        "notes": label,
        "tags": ["spr", "binding"],
        "user": "Lucia",
        "rating": 0,
        "hardware_model": "P4SPR",
        "chip_serial": "CHIP-001",
        "status": "complete",
    }


@pytest.mark.req("OQ-REC-004")
def test_experiment_index_append_and_retrieve(tmp_path):
    """append_entry() must persist to JSON; all_entries() must return it."""
    idx = ExperimentIndex(index_path=tmp_path / "index.json")
    entry = _make_entry("binding assay 1")
    idx.append_entry(entry)

    entries = idx.all_entries()
    assert len(entries) == 1
    assert entries[0]["notes"] == "binding assay 1"


@pytest.mark.req("OQ-REC-005")
def test_experiment_index_search_keyword(tmp_path):
    """search(keyword=...) must return only matching entries."""
    idx = ExperimentIndex(index_path=tmp_path / "index.json")
    idx.append_entry(_make_entry("kinetics run"))
    idx.append_entry(_make_entry("calibration only"))

    results = idx.search(keyword="kinetics")
    assert len(results) == 1
    assert "kinetics" in results[0]["notes"]


@pytest.mark.req("OQ-REC-006")
def test_experiment_index_set_rating(tmp_path):
    """set_rating() must persist; search(rating=5) must find the entry."""
    idx = ExperimentIndex(index_path=tmp_path / "index.json")
    idx.append_entry(_make_entry("top run"))

    entry_id = idx.all_entries()[0]["id"]
    idx.set_rating(entry_id, 5)

    results = idx.search(rating=5)
    assert len(results) == 1
    assert results[0]["rating"] == 5


@pytest.mark.req("OQ-REC-007")
def test_experiment_index_two_entries(tmp_path):
    """Two sequential append_entry() calls must produce len(all_entries()) == 2."""
    idx = ExperimentIndex(index_path=tmp_path / "index.json")
    idx.append_entry(_make_entry("run A"))
    idx.append_entry(_make_entry("run B"))

    assert len(idx.all_entries()) == 2


@pytest.mark.req("OQ-REC-008")
def test_experiment_index_empty_search(tmp_path):
    """Empty index — search() must return []."""
    idx = ExperimentIndex(index_path=tmp_path / "index.json")
    assert idx.search() == []


@pytest.mark.req("OQ-REC-009")
def test_experiment_index_file_created_at_path(tmp_path):
    """ExperimentIndex must create its JSON file at the supplied path."""
    index_path = tmp_path / "my_index.json"
    idx = ExperimentIndex(index_path=index_path)
    idx.append_entry(_make_entry("any"))

    assert index_path.exists(), f"Index file not created at {index_path}"
