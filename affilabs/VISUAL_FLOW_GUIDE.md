# Hardware Connection Flow - Visual Guide

## 🔌 Power Button State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    POWER BUTTON STATES                           │
└─────────────────────────────────────────────────────────────────┘

    ╔════════════════╗
    ║ DISCONNECTED   ║  ← Initial state
    ║    (GRAY)      ║    No hardware connected
    ╚════════════════╝
           │
           │ User clicks power button
           ▼
    ╔════════════════╗
    ║   SEARCHING    ║  ← Backend scanning USB
    ║   (YELLOW)     ║    Can be cancelled by user
    ╚════════════════╝
           │
           ├──────────────┬─────────────────┐
           │              │                 │
    Hardware found   No hardware      User clicks
           │              │              (cancel)
           ▼              ▼                 │
    ╔════════════════╗ ╔════════════════╗  │
    ║   CONNECTED    ║ ║ DISCONNECTED   ║ ◄┘
    ║    (GREEN)     ║ ║    (GRAY)      ║
    ╚════════════════╝ ╚════════════════╝
           │              ▲
           │              │
           └──────────────┘
         User disconnects
```

## 🔍 Scan for Hardware Button Behavior

```
┌─────────────────────────────────────────────────────────────────┐
│             SCAN BUTTON LOGIC (Device Status)                    │
└─────────────────────────────────────────────────────────────────┘

User clicks "🔍 Scan for Hardware"
         │
         ▼
   Is hardware already connected?
         │
    ┌────┴────┐
    │   YES   │                      │   NO    │
    └────┬────┘                      └────┬────┘
         │                                 │
         ▼                                 ▼
  ╔═══════════════════╗         ╔═══════════════════╗
  ║ Report current    ║         ║ Scan USB devices  ║
  ║ hardware status   ║         ║ Try to connect    ║
  ║                   ║         ║                   ║
  ║ ✅ NO disconnect  ║         ║ Update status     ║
  ║ ✅ NO re-scan     ║         ║                   ║
  ║ ✅ EXIT immediate ║         ║ Emit results      ║
  ╚═══════════════════╝         ╚═══════════════════╝
         │                                 │
         └────────────┬────────────────────┘
                      ▼
              Status displayed
              in Device Status UI
```

## 📡 Hardware Detection Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                HARDWARE DETECTION SEQUENCE                       │
└─────────────────────────────────────────────────────────────────┘

    Power Button Clicked (gray)
            │
            ▼
    Button → YELLOW (searching)
            │
            ▼
    Emit: power_on_requested signal
            │
            ▼
    ┌───────────────────────────────────────┐
    │  Backend: scan_and_connect()          │
    │                                       │
    │  Step 1: Check if already connected   │
    │  Step 2: Scan for spectrometer        │
    │  Step 3: Scan for controller          │
    │  Step 4: Scan for kinetic controller  │
    │  Step 5: Scan for pump                │
    └───────────────────────────────────────┘
            │
            ▼
    Emit: hardware_connected(status)
            │
            ├─────────────┬──────────────┐
            │             │              │
         Found         Not found      Cancelled
            │             │              │
            ▼             ▼              ▼
    Button → GREEN   Button → GRAY  Button → GRAY
    Show status      Show error     Silent exit
```

## 🎯 Device Type Identification

```
┌─────────────────────────────────────────────────────────────────┐
│              DEVICE TYPE DETERMINATION                           │
└─────────────────────────────────────────────────────────────────┘

Physically Connected Hardware Detection:
─────────────────────────────────────────

Arduino?
   │
   └──→ YES ──→ Device Type = "P4SPR"

PicoP4SPR?
   │
   ├──→ Alone ──────────────────→ Device Type = "P4SPR"
   │
   └──→ + RPi (KNX) ────────────→ Device Type = "P4SPR+KNX"
                                   (or "ezSPR" via serial check)

PicoEZSPR?
   │
   └──→ YES ──→ Device Type = "P4PRO"

Nothing?
   │
   └──→ YES ──→ Device Type = "" (empty)
                Power button → GRAY
                No status displayed
```

## ⚠️ Safety Guarantees

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHAT WON'T BREAK                              │
└─────────────────────────────────────────────────────────────────┘

✅ Clicking power button while CONNECTED
   → Shows disconnect confirmation dialog
   → User must confirm before disconnect

✅ Clicking "Scan for Hardware" while CONNECTED
   → Reports current status
   → Does NOT disconnect
   → Does NOT re-scan USB

✅ Clicking power button while SEARCHING
   → Immediately cancels scan
   → Returns to GRAY (disconnected)
   → Backend cleans up connection thread

✅ Backend finds NO hardware
   → Automatically returns button to GRAY
   → Shows error message
   → Clears all status displays

✅ User can retry connection indefinitely
   → Each attempt is independent
   → No stuck states
   → Full user control
```

## 🔄 State Transitions Summary

| Current State | User Action | Next State | Side Effects |
|--------------|-------------|------------|--------------|
| **GRAY** | Click power | **YELLOW** | Start USB scan |
| **YELLOW** | Click power | **GRAY** | Cancel scan |
| **YELLOW** | Hardware found | **GREEN** | Show status |
| **YELLOW** | Nothing found | **GRAY** | Show error |
| **GREEN** | Click power | **GRAY** | Disconnect (after confirm) |
| **GREEN** | Click scan | **GREEN** | Report status (no change) |

---

**See `README_HARDWARE_BEHAVIOR.md` for complete technical details**
