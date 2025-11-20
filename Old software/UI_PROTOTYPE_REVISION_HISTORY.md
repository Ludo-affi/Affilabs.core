# UI Prototype Revision History

## Rev 1 - November 20, 2025

**File:** `ui_prototype_rev1.py`

### Major Features Implemented

#### Navigation & Layout
- **Left Sidebar**: Resizable tab-based navigation (55px min, 800px max, 450px default)
  - Non-collapsible design with 6px resizable handle
  - 6 tabs: Device Status, Graphic Control, Settings, Static, Export, (remaining tabs placeholder)
  - West-oriented vertical tabs with grayscale theme

- **Top Navigation Bar**:
  - Pill-shaped navigation buttons (Sensorgram, Edits, Analyze, Report)
  - Recording status indicator with live state display
  - Record button (● symbol) - gray when viewing, red when recording
  - Power button (⏻ symbol) - gray/yellow/green states for disconnected/searching/connected

#### Recording Workflow
- **Auto-read Mode**: Device displays data without saving by default
- **Recording States**:
  - Viewing Mode: Gray dot + "Viewing (not saved)"
  - Recording Mode: Red dot + "Recording to: filename.h5"
- **Save Dialog**: Appears on Record button press before recording starts
- **Visual Feedback**: Red button and indicator during active recording

#### Sidebar Tabs

##### Device Status Tab
- Hardware detection with scan functionality
- Subunit readiness indicators (Sensor, Optics, Fluidics)
- System status overview

##### Graphic Control Tab
- LED/Polarizer control settings
- Filter control toggles
- Integration time controls
- Live preview functionality

##### Settings Tab
- Wavelength range configuration
- Data processing settings
- Peak detection parameters
- Calibration controls

##### Static Tab
- **Signal Assessment**: Always-visible card at top
  - Real-time signal status with countdown
  - Status badges (Good/Warning/Error states)
- **Cycle Settings**: Collapsible section
  - Compact button sizing (Start Now: 120x36px, Add to Queue: 140x36px)
  - Optimized combo box widths (Type: 140px, Length: 100px, Units: 140px)
- **Cycle History & Queue**: Collapsible section
  - Recent cycles table
  - Queue management

##### Export Tab
- **Section 1: Data Selection**
  - Raw/Processed/Segments/Summary checkboxes
  - Time range selector (Full/Current/Selected/Custom)

- **Section 2: Channel Selection**
  - Individual channel checkboxes (A, B, C, D)
  - Select All button

- **Section 3: Export Format**
  - Excel (.xlsx) - Multi-tab workbook
  - CSV (.csv) - Single or multiple files
  - JSON (.json) - Structured data
  - HDF5 (.h5) - Large datasets

- **Section 4: Export Options**
  - Metadata inclusion toggle
  - Event markers toggle
  - Decimal precision selector (2-5)
  - Timestamp format options (Relative/Absolute/Elapsed)

- **Section 5: File Settings & Export**
  - Filename input with placeholder
  - Destination folder with browse button
  - Estimated file size display
  - Primary Export button (dark gray #1D1D1F)
  - Quick export presets (Quick CSV, Analysis Ready, Publication)

#### Sensorgram Content
- **Dual-graph layout**: Master-detail pattern with vertical split
  - Top graph (30%): Full Experiment Timeline
  - Bottom graph (70%): Cycle of Interest
- **Resizable splitter**: 8px handle between graphs
- **Channel toggles**: A/B/C/D with consistent color coding
- **Delta SPR display**: Real-time values in bottom graph header
- **Zoom controls**: Reset and zoom buttons with tooltips

### Design System

#### Color Palette (Grayscale Theme)
- **Primary Dark**: #1D1D1F (buttons, text, primary actions)
- **Medium Gray**: #636366 (secondary text, borders)
- **Hover States**: #3A3A3C (button hover)
- **Pressed States**: #48484A (button pressed)
- **Helper Text**: #86868B (labels, placeholders)
- **Backgrounds**:
  - rgba(0,0,0,0.03) - Light cards
  - rgba(0,0,0,0.04) - Subtle backgrounds
  - rgba(0,0,0,0.06) - Controls
  - rgba(0,0,0,0.08-0.15) - Selections, focus
- **Accent Red**: #FF3B30 (recording state, alerts)
- **Accent Green**: #34C759 (success, Channel D)

#### Typography
- **Font Family**: -apple-system, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif
- **Monospace**: -apple-system, 'SF Mono', 'Menlo', monospace (for data display)
- **Font Sizes**: 11px (labels), 12-13px (body), 14-15px (headers), 16px+ (titles)
- **Font Weights**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)

#### Component Styles
- **Border Radius**: 4-8px (inputs), 6px (cards), 12px (containers)
- **Spacing**: 4px, 8px, 12px, 16px increments
- **Button Heights**: 28px (small), 32-36px (medium), 40px (large)
- **Shadows**: QGraphicsDropShadowEffect with 8px blur, offset (0,2)

### UI Optimizations
- **Compact Information Density**: Reduced button widths and padding for better space utilization
- **Consistent Spacing**: Standardized margins and padding throughout
- **Visual Hierarchy**: Clear distinction between primary/secondary actions
- **State Feedback**: Immediate visual response to user actions
- **Accessibility**: Tooltips on all interactive elements

### Technical Implementation
- **Framework**: PySide6 (Qt 6.10.0)
- **File Size**: ~6,200 lines
- **Custom Widgets**: CollapsibleSection for accordion-style sections
- **Animations**: QPropertyAnimation for smooth state transitions
- **Layout Management**: QSplitter for resizable panels, QVBoxLayout/QHBoxLayout for structure

### Known Limitations
- Export tab functionality is UI-only (no backend implementation)
- Recording workflow is simulated (file save dialog functional, no actual data capture)
- Graph areas are placeholders (no pyqtgraph integration yet)
- Device connection states are simulated (no hardware integration)

### Next Steps for Production Integration
1. Connect recording workflow to actual data capture backend
2. Integrate real hardware detection and status updates
3. Implement export functionality with actual file generation
4. Add pyqtgraph widgets for live sensorgram display
5. Connect sidebar controls to hardware control layer
6. Implement keyboard shortcuts (Ctrl+R for record, Ctrl+P for power)
7. Add loading states and progress indicators
8. Implement error handling and user feedback dialogs

---

## Revision Notes
This revision represents a complete UI overhaul with:
- Modern grayscale aesthetic
- Improved workflow for recording and data management
- Comprehensive export capabilities
- Better information architecture with sidebar navigation
- Optimized space utilization and visual consistency
