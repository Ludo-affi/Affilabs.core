# UI Migration Plan - Direct Integration

## Phase 1: Replace Sidebar (NOW)
1. Copy SidebarPrototype class from ui_prototype.py → widgets/sidebar_new.py
2. Update mainwindow.py to use new sidebar
3. Port Device and Kinetic widgets to new tab structure
4. Test basic functionality

## Phase 2: Replace Navigation Bar (NEXT)
1. Port navigation bar from ui_prototype.py to mainwindow.py
2. Add recording indicator and controls
3. Update button styling to match prototype
4. Wire up existing signals

## Phase 3: Connect Data Layer (FINAL)
1. Wire recording workflow to actual data capture
2. Connect device status to hardware manager
3. Integrate export system
4. Connect graphs to pyqtgraph

## Files to Modify (Priority Order)
1. ✅ widgets/mainwindow.py - Replace UI initialization
2. ✅ widgets/sidebar.py - Replace with new sidebar
3. ✅ ui/ui_main.py - Update navigation bar
4. ⏸️ main/main.py - Update signal connections (later)

## Quick Win Strategy
- Keep main.py UNCHANGED initially
- Replace only UI layer
- Maintain ALL existing signals
- Add new signals as needed

## Execution Steps
Step 1: Create new sidebar (5 min)
Step 2: Integrate into mainwindow (10 min)
Step 3: Test with real app (5 min)
Total: ~20 minutes for working prototype
