"""Test: RecordingManager timeline integration (Phase 1)."""

import sys
from pathlib import Path

# Add workspace root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime

from affilabs.core.recording_manager import RecordingManager
from affilabs.domain.timeline import (
    TimelineContext,
    TimelineEventStream,
    InjectionFlag,
    EventContext,
)


def test_recording_manager_timeline_initialization():
    """Test that RecordingManager initializes timeline objects."""
    mgr = RecordingManager(data_mgr=None)
    
    # Timeline stream should exist
    assert isinstance(mgr._timeline_stream, TimelineEventStream)
    assert len(mgr._timeline_stream) == 0
    
    # Timeline context should be None until recording starts
    assert mgr._timeline_context is None


def test_recording_manager_timeline_start_recording():
    """Test that start_recording creates timeline context."""
    mgr = RecordingManager(data_mgr=None)
    
    # Start recording (memory only, no file)
    mgr.start_recording(filename=None, time_offset=0.0)
    
    # After start, context should exist
    assert mgr._timeline_context is not None
    assert isinstance(mgr._timeline_context, TimelineContext)
    assert mgr._timeline_context.recording_start_offset == 0.0
    
    # Stream should be empty but ready
    assert len(mgr._timeline_stream) == 0


def test_recording_manager_timeline_context_getter():
    """Test get_timeline_context() method."""
    mgr = RecordingManager(data_mgr=None)
    
    # Before recording
    assert mgr.get_timeline_context() is None
    
    # Start recording
    mgr.start_recording(filename=None, time_offset=5.0)
    
    # After recording
    ctx = mgr.get_timeline_context()
    assert ctx is not None
    assert ctx.recording_start_offset == 5.0


def test_recording_manager_timeline_stream_getter():
    """Test get_timeline_stream() method."""
    mgr = RecordingManager(data_mgr=None)
    
    # Stream should always exist
    stream = mgr.get_timeline_stream()
    assert isinstance(stream, TimelineEventStream)
    
    # Should be able to add events after recording starts
    mgr.start_recording(filename=None, time_offset=0.0)
    
    flag = InjectionFlag(
        time=5.0,
        channel='A',
        context=EventContext.LIVE,
        created_at=datetime.now(),
        spr_value=645.0,
        confidence=0.95
    )
    stream.add_event(flag)
    
    # Event should be in stream
    assert len(stream) == 1
    assert stream.get_flags()[0].spr_value == 645.0


def test_recording_manager_timeline_stop_recording():
    """Test that stop_recording clears timeline."""
    mgr = RecordingManager(data_mgr=None)
    
    mgr.start_recording(filename=None, time_offset=0.0)
    assert mgr.get_timeline_context() is not None
    
    mgr.stop_recording()
    
    # After stop, context should be cleared
    assert mgr.get_timeline_context() is None
    
    # Stream should be reset
    assert len(mgr.get_timeline_stream()) == 0


def test_recording_manager_timeline_pause_offset():
    """Test that pause/resume offset is passed to timeline context."""
    mgr = RecordingManager(data_mgr=None)
    
    # Start with 10.5 second offset (simulating pause)
    mgr.start_recording(filename=None, time_offset=10.5)
    
    ctx = mgr.get_timeline_context()
    assert ctx.recording_start_offset == 10.5


if __name__ == "__main__":
    # Run basic sanity checks
    test_recording_manager_timeline_initialization()
    test_recording_manager_timeline_start_recording()
    test_recording_manager_timeline_context_getter()
    test_recording_manager_timeline_stream_getter()
    test_recording_manager_timeline_stop_recording()
    test_recording_manager_timeline_pause_offset()
    print("✅ All timeline integration tests passed!")
