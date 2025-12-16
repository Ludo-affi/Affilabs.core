"""Visual diagram showing the channel click selection feature

BEFORE CLICK:
┌─────────────────────────────────────────────────────────────────┐
│  Cycle of Interest Graph                                        │
│                                                                 │
│   ─────  Ch A (Black, 2px)                                     │
│   ─────  Ch B (Red, 2px)                                       │
│   ─────  Ch C (Blue, 2px)                                      │
│   ─────  Ch D (Green, 2px)                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

USER CLICKS ON CHANNEL B (Red line)
              ↓

AFTER CLICK:
┌─────────────────────────────────────────────────────────────────┐
│  Cycle of Interest Graph                                        │
│                                                                 │
│   ─────  Ch A (Black, 2px) ← reset to normal                  │
│   █████  Ch B (Red, 4px) ← SELECTED (thicker!)                │
│   ─────  Ch C (Blue, 2px) ← reset to normal                   │
│   ─────  Ch D (Green, 2px) ← reset to normal                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Channel B toggle button:
[Ch B] ← Automatically checked if it was hidden


FEATURE FLOW:
┌──────────────┐
│ User clicks  │
│ on curve     │
└──────┬───────┘
       │
       ↓
┌──────────────────────────────┐
│ sigClicked signal fired      │
│ _on_curve_clicked(channel_idx)│
└──────┬───────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│ Update all curves:           │
│ - Selected: setPen(4px)      │
│ - Others: setPen(2px)        │
└──────┬───────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│ Update toggle button:        │
│ - Ensure channel is visible  │
└──────┬───────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│ Print debug message          │
│ "Channel X selected..."      │
└──────────────────────────────┘


CLICK DETECTION:
┌─────────────────────────────────────┐
│  Clickable area around curve        │
│                                     │
│  ........... (10px tolerance)       │
│  ─────────── (actual curve 2-4px)   │
│  ........... (10px tolerance)       │
│                                     │
│  Total clickable height: ~24px      │
└─────────────────────────────────────┘


GRAPH DIFFERENTIATION:
┌─────────────────────────────────────┐
│ Full Timeline (Top)                 │
│ - Overview/Navigation               │
│ - NOT clickable                     │
│ - show_delta_spr = False            │
│ - Has Start/Stop cursors            │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ Cycle of Interest (Bottom)          │
│ - Detail View                       │
│ - CLICKABLE (feature enabled)       │
│ - show_delta_spr = True             │
│ - Shows Delta SPR display           │
└─────────────────────────────────────┘


COLOR SCHEMES:
Standard Colors:          Colorblind-Safe Colors:
• Ch A: Black #1D1D1F    • Ch A: Black #1D1D1F
• Ch B: Red #FF3B30      • Ch B: Orange #FF9500
• Ch C: Blue #007AFF     • Ch C: Teal #5AC8FA
• Ch D: Green #34C759    • Ch D: Yellow #FFD60A

(Both schemes work with click selection)


LINE WIDTH COMPARISON:
Normal:   ───  (2px)
Selected: ███  (4px) ← 2x thicker, very noticeable


CHANNEL MAPPING:
Array Index  →  Channel Letter  →  Color (Standard)
     0       →        A          →  Black
     1       →        B          →  Red
     2       →        C          →  Blue
     3       →        D          →  Green

Formula: chr(65 + index) = channel_letter
Example: chr(65 + 2) = chr(67) = 'C'


TECHNICAL IMPLEMENTATION:
┌─────────────────────────────────────────────────────────────┐
│ PlotDataItem Attributes (added to each curve):             │
│                                                             │
│ • original_color: str (e.g., '#FF3B30')                    │
│ • original_pen: pg.mkPen(color, width=2)                   │
│ • selected_pen: pg.mkPen(color, width=4)                   │
│ • channel_index: int (0-3)                                 │
│                                                             │
│ PyQtGraph Methods Used:                                     │
│ • setClickable(True, width=10)                             │
│ • sigClicked.connect(handler)                              │
│ • setPen(pen_object)                                       │
└─────────────────────────────────────────────────────────────┘


USER SCENARIOS:

Scenario 1: Quick Channel Inspection
1. User sees interesting feature in red line
2. Clicks directly on red line
3. Line becomes thicker (easy to track)
4. User examines data for that channel

Scenario 2: Hidden Channel Activation
1. User turns off Channel B (hidden)
2. User clicks where Channel B line was
3. Channel B becomes visible AND selected (thick)
4. User can now see and focus on Channel B

Scenario 3: Sequential Channel Review
1. Click Channel A → becomes thick
2. Review Channel A data
3. Click Channel B → A returns to normal, B becomes thick
4. Review Channel B data
5. Continue through channels C and D

Scenario 4: Integration with Zoom
1. User clicks Channel C to select it
2. Channel C line becomes thick (easy to see)
3. User zooms into specific time region
4. Channel C remains highlighted in zoomed view
5. Easy to track selected channel during analysis
"""

print(__doc__)
