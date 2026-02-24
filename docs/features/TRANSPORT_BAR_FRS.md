# Transport Bar \u0026 Icon Rail FRS \u2014 Affilabs.core v2.0.5

> **Status**: Implemented (v2.0.5)
> **Source files**: [\](../../affilabs/widgets/transport_bar.py), [\](../../affilabs/widgets/icon_rail.py)

---

## Overview

The Transport Bar and Icon Rail together replace the legacy nav bar in v2.0.5. They split navigation concerns into two dedicated strips:

| Component | Location | Height/Width | Purpose |
|-----------|----------|--------------|---------|
| \ | Top of workspace, full-width | 56px tall | Tab switching, acquisition controls, floating panel toggles |
| \ | Far left, full-height | 48px wide | Sidebar tab selection, utility popups (timer, spectrum, user) |

Both are plain \ subclasses \u2014 not \ toolbar or \. They wire their buttons directly onto \ attributes for backward compatibility with existing mixins.

---

## TransportBar

**File**: **Class**: **Fixed height**: 56px
**Background**: 
### Layout (left \u2192 right)

\
| Zone | Contents | Notes |
|------|----------|-------|
| Brand | Company logo (PNG, 30px tall) or \u201cAffinit\xe9\u201d text fallback | Always visible |
| Nav pills | \ \ \u2014 checkable pills, 32px tall | Switch \ pages via \ |
| Separator | 1px \ vertical rule | Visual divider |
| Method | \ outlined pill | Opens \ |
| Stretch | Flexible spacer | Pushes right group to far right |
| Spark | \ checkable icon button | Toggles Spark AI panel; uses \; amber off / blue on |
| Separator | 1px vertical rule | |
| Pause | \ icon button, checkable | Disabled until calibrated; orange when paused |
| Record | \ icon button, checkable | Disabled until calibrated; red when recording |
| Separator | 1px vertical rule | |
| Power | \ icon button | Hardware connect/disconnect; state color set externally |

### Button Aliasing

Every button is set on \ immediately after creation so existing mixin code finds them unchanged:

\
\ is created as a **hidden stub** (not in layout) and set on \ \u2014 keeps \ calls from crashing. The visible timer lives in \.

### Hidden Compat Widgets

These are created but not added to any layout \u2014 kept for mixin compatibility:
- \ (\, hidden)
- \ (\, hidden)
- \ (\, hidden) \u2014 shown as an overlay by hardware coordinator

### Nav Button State

\ is set to the list of nav pill buttons. \ updates \ on each pill when the page changes.

---

## IconRail

**File**: **Class**: **Fixed width**: 48px
**Background**: **Border**: 
### Layout (top \u2192 bottom)

\
### Tab Buttons (Flow, Export, Settings)

Each tab button is 44\u00d740px, checkable, SVG icon. Clicking uses this logic:

| Sidebar state | Same tab clicked | Different tab clicked |
|---------------|------------------|-----------------------|
| Collapsed | Expand + select tab | Expand + select tab |
| Expanded | Collapse | Switch to new tab (stay expanded) |

Tab switching calls \ and \ / \.

### Flow Tab Visibility

\
Called by \ when hardware model is determined. Flow tab hidden for P4SPR.

### Utility Buttons

| Button | Behaviour | Popup |
|--------|-----------|-------|
| User | Toggles \ panel (inline) or \ (legacy fallback) | Positioned right of rail |
| Spectrum | Calls \, updates icon color (cyan off / blue on) | \ (owned by main window) |
| Timer | Lazily creates \, positions it right of rail button | \ |

### 
Must be called after both \ and \ are created:
- Stores sidebar reference
- Hides \ \u2014 rail takes over tab bar role
- Wires \ on main_ui

---

## Icon Style

All icons are inline SVG strings rendered via \. Color is substituted by replacing \ before rendering. No external SVG files needed for icon rail icons.

| State | Color |
|-------|-------|
| Inactive | \ (grey) |
| Active tab | \ (blue) |
| Spectrum inactive | \ (cyan) |
| Spectrum active | \ (blue) |
| Timer finished alert | \ (orange) |

---

## Wiring (main.py)

\
---

## Interaction State Rules

| State | Power btn | Record btn | Pause btn |
|-------|-----------|------------|-----------|
| Disconnected | Enabled | Disabled | Disabled |
| Connected, not calibrated | Enabled | Disabled | Disabled |
| Calibrated | Enabled | Enabled | Disabled |
| Acquiring | Enabled | Enabled (recording style) | Enabled |
| Paused | Enabled | Enabled | Enabled (orange) |

These rules are enforced externally by \ and \ \u2014 \ does not self-manage enable/disable state.
