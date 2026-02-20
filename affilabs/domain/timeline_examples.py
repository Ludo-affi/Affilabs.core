"""Example: Timeline Context & Event System Usage

Demonstrates how to use the new unified timeline model.
"""

from datetime import datetime
import time

from affilabs.domain.timeline import (
    EventContext,
    EventType,
    TimelineContext,
    TimelineEventStream,
    InjectionFlag,
    WashFlag,
    CycleMarker,
    AutoMarker,
)


def example_basic_timeline():
    """Example 1: Create a timeline context and add events."""
    print("=" * 70)
    print("Example 1: Basic Timeline Setup")
    print("=" * 70)
    
    # Create timeline context at recording start
    recording_start = time.time()
    timeline_context = TimelineContext(
        recording_start_time=recording_start,
        recording_start_offset=0.0
    )
    print(f"Timeline: {timeline_context}")
    
    # Create event stream
    stream = TimelineEventStream()
    
    # Add events (using recording-relative time)
    stream.add_event(InjectionFlag(
        time=5.0,
        channel='A',
        context=EventContext.LIVE,
        created_at=datetime.now(),
        spr_value=645.2,
        is_reference=True,
        confidence=0.95
    ))
    
    stream.add_event(InjectionFlag(
        time=8.5,
        channel='B',
        context=EventContext.LIVE,
        created_at=datetime.now(),
        spr_value=643.8,
        is_reference=False,
        confidence=0.92
    ))
    
    stream.add_event(WashFlag(
        time=120.0,
        channel='A',
        context=EventContext.LIVE,
        created_at=datetime.now(),
        wash_type='buffer_change'
    ))
    
    print(f"\nEvent stream: {stream}")
    print(f"Total events: {len(stream)}")
    print("\nAll events (in time order):")
    for event in stream:
        type_name = event.event_type.value
        print(f"  • {type_name:20s} @ t={event.time:6.1f}s ch={event.channel} "
              f"spr={getattr(event, 'spr_value', 'N/A')}")


def example_query_events():
    """Example 2: Query events by type, channel, time range."""
    print("\n" + "=" * 70)
    print("Example 2: Querying Events")
    print("=" * 70)
    
    stream = TimelineEventStream()
    
    # Add mixed events
    stream.add_event(InjectionFlag(
        time=10.0, channel='A', context=EventContext.LIVE,
        created_at=datetime.now(), spr_value=645.0
    ))
    stream.add_event(InjectionFlag(
        time=15.0, channel='B', context=EventContext.LIVE,
        created_at=datetime.now(), spr_value=644.0
    ))
    stream.add_event(CycleMarker(
        time=20.0, channel='A', context=EventContext.LIVE,
        created_at=datetime.now(),
        cycle_type='Baseline', is_start=True, duration=60.0
    ))
    stream.add_event(AutoMarker(
        time=80.0, channel='A', context=EventContext.LIVE,
        created_at=datetime.now(),
        marker_kind='wash_deadline', label='⏱ Wash Due'
    ))
    
    # Query by type
    print("\nAll flags (injection/wash/spike):")
    for flag in stream.get_flags():
        print(f"  • {flag.event_type.value:20s} @ t={flag.time:6.1f}s ch={flag.channel}")
    
    #
    # Query by time range
    print("\nEvents between 12s and 25s:")
    for event in stream.get_events_in_time_range(12.0, 25.0):
        print(f"  • {event.event_type.value:20s} @ t={event.time:6.1f}s ch={event.channel}")
    
    # Query by channel
    print("\nEvents on channel A:")
    for event in stream.get_events_for_channel('A'):
        print(f"  • {event.event_type.value:20s} @ t={event.time:6.1f}s")
    
    # Query cycle boundaries
    print("\nCycle boundaries:")
    for marker in stream.get_cycle_boundaries():
        start_end = "START" if marker.is_start else "END"
        print(f"  • [{start_end}] {marker.cycle_type:20s} @ t={marker.time:6.1f}s ch={marker.channel}")


def example_time_conversion():
    """Example 3: Convert between absolute and relative times."""
    print("\n" + "=" * 70)
    print("Example 3: Time Conversion")
    print("=" * 70)
    
    # Create context
    recording_start_absolute = time.time()
    print(f"Recording started at: {datetime.fromtimestamp(recording_start_absolute).isoformat()}")
    
    timeline_context = TimelineContext(
        recording_start_time=recording_start_absolute,
        recording_start_offset=0.0
    )
    
    # Create event with relative time
    event = InjectionFlag(
        time=42.5,  # 42.5 seconds into recording
        channel='A',
        context=EventContext.LIVE,
        created_at=datetime.now(),
        spr_value=645.0
    )
    
    print(f"\nEvent time (relative): {event.time}s")
    
    # Convert to absolute
    absolute_time = timeline_context.denormalize_time(event.time)
    print(f"Event time (absolute): {datetime.fromtimestamp(absolute_time).isoformat()}")
    
    # Convert back
    relative_again = timeline_context.normalize_time(absolute_time)
    print(f"Event time (relative, back): {relative_again}s")


def example_pause_resume():
    """Example 4: Handle pause/resume with timeline context offset."""
    print("\n" + "=" * 70)
    print("Example 4: Pause/Resume Recording")
    print("=" * 70)
    
    # Start recording
    start_time = time.time()
    timeline = TimelineContext(
        recording_start_time=start_time,
        recording_start_offset=0.0
    )
    print(f"Recording started. Timeline offset: {timeline.recording_start_offset}s")
    
    # Add some events
    stream = TimelineEventStream()
    stream.add_event(InjectionFlag(
        time=10.0, channel='A', context=EventContext.LIVE,
        created_at=datetime.now(), spr_value=645.0
    ))
    print(f"Added injection at 10.0s (relative time)")
    
    # Simulate pause (5 seconds elapsed)
    elapsed_before_pause = 10.5
    print(f"\nPaused after {elapsed_before_pause}s of elapsed time")
    
    # Simulate 10 second pause in real time (not recorded)
    print("... paused for 10 seconds (not counted) ...")
    
    # Resume recording
    # Set offset to elapsed time to skip the pause
    timeline.recording_start_offset = elapsed_before_pause
    print(f"\nResumed recording. Timeline offset: {timeline.recording_start_offset}s")
    
    # Add event after resume (this happened 15 seconds of relative time into the session)
    stream.add_event(InjectionFlag(
        time=15.0, channel='B', context=EventContext.LIVE,
        created_at=datetime.now(), spr_value=644.0
    ))
    print(f"Added injection at 15.0s (relative time, after pause)")
    
    # The gap between 10.0s and 15.0s represents actual pause time
    print(f"\nFinal event stream (note: gap represents pause):")
    for event in stream:
        print(f"  • {event.event_type.value:20s} @ t={event.time:6.1f}s ch={event.channel}")


def example_edits_context():
    """Example 5: Separate live vs edits contexts."""
    print("\n" + "=" * 70)
    print("Example 5: Live vs Edits Context")
    print("=" * 70)
    
    stream = TimelineEventStream()
    
    # Live context: auto-detected during acquisition
    stream.add_event(InjectionFlag(
        time=5.0, channel='A', context=EventContext.LIVE,
        created_at=datetime.now(),
        spr_value=645.0, confidence=0.95, is_reference=True
    ))
    print("Added live injection (auto-detected during acquisition)")
    
    # Edits context: user manually added/moved during post-processing
    stream.add_event(InjectionFlag(
        time=5.2, channel='A', context=EventContext.EDITS,
        created_at=datetime.now(),
        spr_value=645.0, confidence=1.0, time_shift=0.2
    ))
    print("Added edits injection (user manually adjusted)")
    
    print("\nLive events only:")
    for event in stream:
        if event.context == EventContext.LIVE:
            conf = getattr(event, 'confidence', 'N/A')
            print(f"  • {event.event_type.value:20s} @ t={event.time:6.1f}s "
                  f"confidence={conf}")
    
    print("\nEdits events only:")
    for event in stream:
        if event.context == EventContext.EDITS:
            shift = getattr(event, 'time_shift', 0.0)
            print(f"  • {event.event_type.value:20s} @ t={event.time:6.1f}s "
                  f"(shifted by {shift:+.1f}s)")


if __name__ == "__main__":
    example_basic_timeline()
    example_query_events()
    example_time_conversion()
    example_pause_resume()
    example_edits_context()
    
    print("\n" + "=" * 70)
    print("Examples complete!")
    print("=" * 70)
