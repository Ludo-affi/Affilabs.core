# Method Architecture Refactor

**Date:** February 2, 2026
**Status:** ✅ Complete

## Overview

Refactored the method management system for better naming consistency and clearer architectural boundaries.

## Problem

The system had three overlapping services managing similar concepts with confusing names:
- `MethodManager` - Saved complete methods (queue snapshots)
- `MethodTemplates` - Predefined templates (Pro tier)
- `CycleTemplateStorage` - User-saved cycle templates

**Issues:**
- Naming inconsistency: `MethodManager` vs `CycleTemplateStorage` (why not `MethodStorage`?)
- Unclear terminology: "method" vs "method template" vs "cycle template"
- Architectural overlap causing confusion

## Solution

### 1. Renamed `MethodManager` → `MethodStorage`

**Why?**
- Matches naming pattern of `CycleTemplateStorage`
- Better describes functionality: "Storage" = Save/Load operations
- Clearer distinction from "Manager" (which implies orchestration)

### 2. Updated All Docstrings with Clear Distinctions

Each service now has clear documentation explaining:

#### **MethodStorage** (formerly MethodManager)
- **Purpose:** Save/Load complete methods (entire queue snapshots)
- **Use Case:** User wants to save current queue and reload later
- **Example:** "Kinetics Protocol" with 20 cycles configured
- **Analogy:** "Save Game" - complete state snapshot

#### **MethodTemplates** (Pro Tier)
- **Purpose:** Pre-built professional method templates
- **Use Case:** User wants to quickly set up common experiments
- **Example:** "Kinetics Analysis", "Affinity Screening" templates
- **Analogy:** "Recipe Book" - built-in expert protocols

#### **CycleTemplateStorage**
- **Purpose:** Save/Load individual cycle templates
- **Use Case:** User wants to reuse specific cycle configurations
- **Example:** "5-Min Baseline", "100nM Association" templates
- **Analogy:** "Building Blocks" - reusable single components

## Changes Made

### Files Modified

1. **affilabs/services/method_manager.py**
   - Renamed class: `MethodManager` → `MethodStorage`
   - Updated docstring with clear distinctions
   - Updated log messages

2. **affilabs/widgets/method_manager_dialog.py**
   - Renamed class: `MethodManagerDialog` → `MethodStorageDialog`
   - Updated import: `from method_manager import MethodStorage`
   - Updated window title: "Method Manager" → "Method Storage"
   - Updated docstring

3. **affilabs/services/method_templates.py**
   - Enhanced docstring with clear distinction from other services

4. **affilabs/services/cycle_template_storage.py**
   - Enhanced docstring with clear distinction from other services

5. **test_pydantic_tinydb.py**
   - Updated test imports and variable names
   - Changed `manager` → `storage`
   - Updated test method name: "Manager_Test_Method" → "Storage_Test_Method"

### Architecture Clarity

```
┌─────────────────────────────────────────────────────────────┐
│                     METHOD ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  CycleTemplateStorage     MethodTemplates     MethodStorage  │
│  ────────────────────     ───────────────     ─────────────  │
│  User-saved               Pre-built           User-saved     │
│  single cycles            method recipes      queue snapshots│
│                           (Pro tier)                          │
│  "Building Blocks"        "Recipe Book"       "Save Game"    │
│                                                               │
│  Example:                 Example:            Example:        │
│  - "5-Min Baseline"       - Kinetics          - "My Protocol" │
│  - "100nM Assoc"          - Affinity          - "Expt_2024"  │
│                           - Screening                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Benefits

1. **Naming Consistency:** `MethodStorage` matches `CycleTemplateStorage` pattern
2. **Clear Purpose:** Each service has distinct, documented role
3. **Better UX:** Users understand difference between templates and storage
4. **Code Clarity:** Developers can quickly understand architecture
5. **Maintainability:** Reduced confusion when adding features

## Migration Notes

### For Developers
- Update any imports from `MethodManager` to `MethodStorage`
- Dialog class is now `MethodStorageDialog`
- All functionality remains identical - only naming changed

### For Users
- No visible changes to functionality
- Window title now reads "Method Storage" (was "Method Manager")
- All saved methods remain accessible

## Testing

- ✅ All imports updated
- ✅ Test file runs successfully
- ✅ Dialog class renamed
- ✅ Docstrings enhanced with distinctions
- ✅ No breaking changes to functionality

## Future Improvements

Consider:
1. Renaming `method_manager.py` → `method_storage.py` for complete consistency
2. Adding visual indicators in UI to distinguish template types
3. Creating architecture diagram in main README
