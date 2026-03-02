"""
OQ Suite 4 — Timeline & Flags
Req IDs: OQ-TML-001 to OQ-TML-008

Verifies TimelineEventStream CRUD, deduplication, and type-based routing.
No hardware required — domain model only.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from affilabs.domain.timeline import (
    AutoMarker,
    CycleMarker,
    EventContext,
    EventType,
    InjectionFlag,
    TimelineContext,
    TimelineEventStream,
    UserAnnotation,
    WashFlag,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 1, 12, 0, 0)


def _injection(time: float = 10.0, channel: str = "A") -> InjectionFlag:
    return InjectionFlag(
        time=time,
        channel=channel,
        context=EventContext.LIVE,
        created_at=_NOW,
        spr_value=615.0,
        confidence=0.9,
    )


def _cycle_marker(time: float = 0.0, channel: str = "A") -> CycleMarker:
    return CycleMarker(
        time=time,
        channel=channel,
        context=EventContext.LIVE,
        created_at=_NOW,
        cycle_id="C001",
        is_start=True,
    )


def _wash(time: float = 20.0, channel: str = "A") -> WashFlag:
    return WashFlag(
        time=time,
        channel=channel,
        context=EventContext.LIVE,
        created_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.req("OQ-TML-001")
def test_empty_stream():
    """Empty TimelineEventStream must have len() == 0."""
    stream = TimelineEventStream()
    assert len(stream) == 0


@pytest.mark.req("OQ-TML-002")
def test_add_injection_flag():
    """add_event(InjectionFlag) must increment len and appear in get_flags()."""
    stream = TimelineEventStream()
    flag = _injection()
    added = stream.add_event(flag)

    assert added is True
    assert len(stream) == 1
    flags = stream.get_flags()
    assert len(flags) == 1
    assert flags[0] is flag


@pytest.mark.req("OQ-TML-003")
def test_deduplication():
    """Adding an identical event twice must keep len at 1."""
    stream = TimelineEventStream()
    flag = _injection(time=10.0, channel="A")
    stream.add_event(flag)
    stream.add_event(flag)  # exact same object → duplicate

    assert len(stream) == 1


@pytest.mark.req("OQ-TML-004")
def test_cycle_marker_routing():
    """CycleMarker must appear in get_cycle_boundaries(), not in get_flags()."""
    stream = TimelineEventStream()
    stream.add_event(_cycle_marker())

    assert len(stream.get_cycle_boundaries()) == 1
    assert len(stream.get_flags()) == 0


@pytest.mark.req("OQ-TML-005")
def test_time_range_filter():
    """get_events_in_time_range(5, 15) must return only events within [5, 15]."""
    stream = TimelineEventStream()
    stream.add_event(_injection(time=3.0))   # outside
    stream.add_event(_injection(time=10.0, channel="B"))  # inside
    stream.add_event(_injection(time=20.0, channel="C"))  # outside

    results = stream.get_events_in_time_range(5.0, 15.0)
    assert len(results) == 1
    assert results[0].time == 10.0


@pytest.mark.req("OQ-TML-006")
def test_channel_filter():
    """get_events_for_channel('A') must return only channel A events."""
    stream = TimelineEventStream()
    stream.add_event(_injection(time=10.0, channel="A"))
    stream.add_event(_injection(time=11.0, channel="B"))
    stream.add_event(_injection(time=12.0, channel="A"))

    results = stream.get_events_for_channel("A")
    assert len(results) == 2
    assert all(e.channel == "A" for e in results)


@pytest.mark.req("OQ-TML-007")
def test_remove_event():
    """remove_event() must remove the event and reduce len to 0."""
    stream = TimelineEventStream()
    flag = _injection()
    stream.add_event(flag)
    assert len(stream) == 1

    removed = stream.remove_event(flag)
    assert removed is True
    assert len(stream) == 0


@pytest.mark.req("OQ-TML-008")
def test_event_type_filter():
    """get_events_by_type(INJECTION) must return only injection events."""
    stream = TimelineEventStream()
    stream.add_event(_injection(time=10.0))
    stream.add_event(_wash(time=20.0))
    stream.add_event(_cycle_marker(time=0.0))

    injections = stream.get_events_by_type(EventType.INJECTION)
    assert len(injections) == 1
    assert isinstance(injections[0], InjectionFlag)
