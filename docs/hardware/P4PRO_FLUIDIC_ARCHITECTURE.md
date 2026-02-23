# P4PRO Fluidic Architecture

## Overview

The P4PRO uses a fully automated fluidic system. All samples reach SPR channels via a **6-port rotary loop valve** driven by an **AffiPump** syringe pump. There is no manual syringe injection — the user loads sample into the loop before the run; software controls delivery timing and flow rate.

---

## Kinetic Channels

Two independent fluidic paths, each called a **Kinetic Channel (KC)**:

| Kinetic Channel | Components | SPR channels served |
|----------------|-----------|---------------------|
| **KC1** | AffiPump 1 + 6-port valve 1 + 3-way valve 1 | **A** (NO) and **B** (NC) |
| **KC2** | AffiPump 2 + 6-port valve 2 + 3-way valve 2 | **C** (NO) and **D** (NC) |

Each KC operates independently and can run simultaneously.

---

## 6-Port Valve: Two Operating Positions

The 6-port valve controls whether the pump flows **around** the sample loop (buffer/wash) or **through** it (sample injection).

### Rest position (valve unpowered)

```
AffiPump ──► [bypass path] ──► 3-way valve ──► SPR channel
                                  (buffer/wash flowing)

User inlet ──► [loop] ──► (dead end / isolated)
                ↑
          User loads sample here before run
```

- Pump pushes buffer directly to SPR channels via bypass — continuous flow, no sample
- User inlet connects to the loop — user can pre-fill the loop with sample at this stage
- Loop is isolated from the pump-to-SPR path

### Inject position (valve powered)

```
AffiPump ──► [loop] ──► 3-way valve ──► SPR channel
               ↑
         Sample in loop gets swept to channel

User inlet ──► [waste]
               (user inlet disconnected from loop — no more loading)
```

- Pump now flows **through** the loop, pushing sample to the 3-way valve and into the SPR channel
- User inlet is routed to waste — loop is sealed on the inlet side
- The pump, loop, 3-way valve, and SPR channel form **a single continuous fluidic path**

---

## 3-Way Valve: Channel Selection

After the loop, the 3-way valve routes sample to one of two SPR channels:

| 3-way valve state | KC1 routes to | KC2 routes to |
|------------------|---------------|---------------|
| Unpowered (NO) | Channel **A** | Channel **C** |
| Powered (NC)   | Channel **B** | Channel **D** |

Default pairing: **AC** (valves unpowered) and **BD** (valves powered).

---

## inject_simple — The Core Injection Function

The simplest injection sequence — no user intervention during the run:

1. User pre-fills the loop via the user inlet (rest position, before software starts)
2. Software sends `knx_six: INJECT` → valve powers → loop connects to pump path
3. Pump runs at target flow rate for the full contact time duration
4. Software sends `knx_six: REST` → valve returns to bypass → buffer flows again (wash)

No aspiration step, no loop refill during run. One loop volume = one injection.

Flow rate, contact time, and valve timing are fully software-controlled.

---

## inject_advanced — Air-Segmented Plug Injection

Same fluidic path as `inject_simple`, but the sample plug is sandwiched between two **air bubbles** to reduce Taylor dispersion as the plug travels from the loop to the SPR channel.

### Why air bubbles?

Long tubing between the loop and the SPR chip causes the sample plug to disperse axially (leading and trailing edges smear into buffer). Air segments act as physical barriers that prevent mixing at the plug boundaries, preserving a sharp concentration front at the sensor surface.

### Loading sequence (user-assisted, prompted by software)

```
Loop contents after loading:
  [air] [sample plug] [air] [buffer]
    ↑                   ↑
front bubble         back bubble
(toward pump)       (toward user inlet)
```

1. User injects a small air volume → front air segment enters loop
2. User injects sample → sample plug fills loop behind the air
3. User injects another small air volume → back air segment seals the trailing edge
4. Software takes over: `inject_simple` sequence runs as normal

The software prompts each step and waits for user confirmation before proceeding. Once the loop is loaded, injection is fully automated (same valve/pump sequence as `inject_simple`).

### Trade-offs vs inject_simple

| | inject_simple | inject_advanced |
|--|--------------|----------------|
| Dispersion reduction | None | Yes (air-segmented plug) |
| User steps | 0 (fully automated) | 3 (air + sample + air loading, prompted) |
| Sharp concentration front at sensor | Lower (dispersed edges) | Higher |
| Use case | Fast/routine runs, short tubing | Kinetics, concentration-sensitive assays |

---

## Full Path Summary

```
[Rest]   AffiPump → bypass → 3-way valve → SPR channel A or B (KC1)
                               user inlet → loop (user loads sample)

[Inject] AffiPump → loop → 3-way valve → SPR channel A or B (KC1)
                              user inlet → waste
```

---

## Firmware Commands

| Command | Effect |
|---------|--------|
| `knx_six_1:INJECT` / `knx_six_both:INJECT` | Power 6-port valve(s) → inject position (loop in path) |
| `knx_six_1:REST` / `knx_six_both:REST` | Unpowered → rest position (bypass, loop isolated) |
| `knx_three_both:OFF` | 3-way valves → NO (routes to A, C) |
| `knx_three_both:ON` | 3-way valves → NC (routes to B, D) |

Rate limits enforced by firmware: 6-port valve max 0.5 Hz, 3-way valve max 1 Hz.

---

## Operational Constraints

- **2 of 4 channels per injection** — 3-way valve selects AC or BD, not all 4 simultaneously
- **Loop volume is fixed** — user fills to capacity before the run; software cannot refill mid-run
- **AffiPump only** on P4PRO — pulse-free, aspirate + dispense, fully programmable (flow rate, volume, speed profile)
- **No mid-run sample loading** — user inlet routes to waste during injection; loop is sealed

---

## Comparison: P4PRO vs P4SPR vs P4PROPLUS

| Property | P4SPR | P4PRO | P4PROPLUS |
|-----------|-------|-------|-----------|
| Injection method | Manual syringe | Loop valve + AffiPump | Loop valve + internal pumps |
| Channels per injection | All 4 (manual) | 2 (AC or BD) | 2 (AC or BD) |
| User intervention during injection | Required | None | None |
| Flow quality | N/A | Excellent (pulse-free) | Lower (peristaltic pulsation) |
| Aspiration | N/A | ✅ | ❌ dispense only |
| Per-injection programming | N/A | ✅ (rate, volume, profile) | ❌ on/off, preset rates only |
