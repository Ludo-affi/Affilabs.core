# Workspace Restructuring Plan

## Current State
- Main code in "Affilabs.core beta/" (space in name causes issues)
- 100+ .md documentation files scattered in root
- Debug/diagnostic scripts mixed with main code
- Cache issues from unclear module boundaries

## New Structure (Being Created)

```
ezControl-AI/
├── src/                              # 🆕 Main application (moved from "Affilabs.core beta")
│   ├── core/                         # Core application logic
│   ├── utils/                        # Utility modules
│   ├── ui/                          # UI components
│   ├── widgets/                     # Custom widgets
│   ├── sidebar_tabs/                # Sidebar components
│   ├── controllers/                 # Hardware controllers
│   ├── main_simplified.py           # Main entry point
│   └── config.py                    # Configuration
│
├── tools/                           # 🆕 Development tools
│   ├── debug/                       # Debug scripts
│   │   ├── add_calib_debug.py
│   │   ├── debug_calibration.py
│   │   └── nuclear_cache_clear.py
│   └── diagnostics/                 # Diagnostic tools
│       ├── diagnose_controller.py
│       ├── check_ports.py
│       └── find_controller.py
│
├── docs/                            # 🆕 All documentation (100+ .md files organized)
│   ├── calibration/                 # Calibration-related docs
│   ├── hardware/                    # Hardware guides
│   ├── troubleshooting/            # Debug/troubleshooting docs
│   └── guides/                      # User guides
│
├── tests/                           # Test scripts
│   └── test_*.py
│
├── optical_calibration/             # Calibration data (keep as-is)
├── calibration_data/                # Calibration data (keep as-is)
├── detector_profiles/               # Detector data (keep as-is)
├── settings/                        # Settings (keep as-is)
├── config/                          # Config files (keep as-is)
├── data/                           # Data files (keep as-is)
├── archive/                        # Old backups (keep as-is)
├── .venv312/                       # Virtual environment (keep as-is)
├── .gitignore                      # Updated with cache exclusions
└── README.md                       # Main readme

## Migration Steps

### Phase 1: Copy core application to src/ ✅ IN PROGRESS
- Copy entire "Affilabs.core beta/" content to "src/"
- Keep original until verified working

### Phase 2: Organize documentation
- Move all .md files from root to docs/ subdirectories
- Categorize by topic (calibration, hardware, guides, etc.)

### Phase 3: Move tools
- Move all debug scripts to tools/debug/
- Move all diagnostic scripts to tools/diagnostics/

### Phase 4: Update imports
- Update all imports to reference src/ correctly
- Add src/ to Python path or use relative imports

### Phase 5: Create startup scripts
- New run_app.ps1 that works with src/
- Automatic cache clearing

### Phase 6: Cleanup
- Remove "Affilabs.core beta/" after verification
- Update .gitignore
- Update README.md

## Benefits After Restructuring
✓ No spaces in folder names (eliminates path issues)
✓ Clear separation: code vs docs vs tools
✓ Easier to find files (logical organization)
✓ Better version control (meaningful directory structure)
✓ Cleaner cache management (src/ is single module root)
✓ Professional structure (follows Python best practices)
