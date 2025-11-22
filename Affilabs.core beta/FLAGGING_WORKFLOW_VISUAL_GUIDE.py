"""
Visual Guide: Channel Selection & Flagging Workflow

This demonstrates the complete user interaction flow for selecting channels
and adding/removing flags on the Cycle of Interest graph.
"""

print(__doc__)

workflow = """
═══════════════════════════════════════════════════════════════════════════
                    CHANNEL SELECTION & FLAGGING WORKFLOW
═══════════════════════════════════════════════════════════════════════════


STEP 1: INITIAL STATE (All Channels Visible)
┌────────────────────────────────────────────────────────────────────────┐
│  Cycle of Interest Graph                                               │
│                                                                        │
│   ──── Ch A (Black, 2px)                                             │
│   ──── Ch B (Red, 2px)                                               │
│   ──── Ch C (Blue, 2px)                                              │
│   ──── Ch D (Green, 2px)                                             │
│                                                                        │
│  Header: [Ch A] [Ch B] [Ch C] [Ch D]  (all checked)                  │
└────────────────────────────────────────────────────────────────────────┘


STEP 2: USER LEFT-CLICKS CHANNEL B (Red Line)
                    ↓ (left-click on red line)


STEP 3: CHANNEL B SELECTED FOR FLAGGING
┌────────────────────────────────────────────────────────────────────────┐
│  Cycle of Interest Graph                                               │
│                                                                        │
│   ──── Ch A (Black, 2px)                                             │
│   ████ Ch B (Red, 4px) ← SELECTED (thicker!)                        │
│   ──── Ch C (Blue, 2px)                                              │
│   ──── Ch D (Green, 2px)                                             │
│                                                                        │
│  Status: "Channel B selected for flagging"                           │
│  Instruction: "Right-click on the graph to add a flag"               │
└────────────────────────────────────────────────────────────────────────┘


STEP 4: USER RIGHT-CLICKS AT TIME=25s
                    ↓ (right-click at x=25)


STEP 5: FLAG MARKER ADDED TO CHANNEL B
┌────────────────────────────────────────────────────────────────────────┐
│  Cycle of Interest Graph                                               │
│  🚩 ChB                                                                │
│     ┆                                                                  │
│   ──┆─ Ch A (Black, 2px)                                             │
│   ██●██ Ch B (Red, 4px) ← Flag at x=25s                             │
│   ──┆─ Ch C (Blue, 2px)                                              │
│   ──┆─ Ch D (Green, 2px)                                             │
│     ┆                                                                  │
│  Status: "Flag added to Channel B at x=25.0, y=1234.5"               │
└────────────────────────────────────────────────────────────────────────┘

Data Table:
┌─────────┬───────┬─────┬───────┬────────┬──────────┐
│ Type    │ Start │ End │ Units │ Notes  │ Flags    │
├─────────┼───────┼─────┼───────┼────────┼──────────┤
│ Binding │ 0.0   │ 60.0│ RU    │        │ ChB: 1   │
└─────────┴───────┴─────┴───────┴────────┴──────────┘

"""

print(workflow)
