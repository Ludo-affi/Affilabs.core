# WORKSPACE STRUCTURE RECOMMENDATIONS

## Current Issues:
1. **Folder name with space**: "Affilabs.core beta" can cause shell/path issues
2. **Cache ambiguity**: Python caches modules, making changes hard to debug
3. **No clear separation**: Development vs production code mixed together

## Recommended Structure:

```
ezControl-AI/
├── src/                          # Main application code (rename from "Affilabs.core beta")
│   ├── core/                     # Core application logic
│   ├── utils/                    # Utility modules
│   ├── controllers/              # Hardware controllers
│   ├── main.py                   # Main entry point
│   └── requirements.txt          # Dependencies
│
├── tests/                        # Unit and integration tests
│   ├── test_calibration.py
│   └── test_controllers.py
│
├── tools/                        # Development/debugging tools
│   ├── clear_cache.ps1
│   ├── debug_calibration.py
│   └── run_diagnostics.py
│
├── docs/                         # Documentation (all your .md files)
│   ├── calibration/
│   ├── hardware/
│   └── troubleshooting/
│
├── archive/                      # Old versions (keep separate)
│   └── 2025-11-24-morning-backup/
│
├── optical_calibration/          # Calibration data files
├── .venv312/                     # Virtual environment
├── .gitignore
└── README.md
```

## Benefits:
1. **No spaces in folder names** - eliminates path issues
2. **Clear organization** - easy to find code vs docs vs tools
3. **Better caching** - Python knows where to look for modules
4. **Version control friendly** - easier to track changes

## Migration Plan:
1. Create new `src/` folder
2. Move code from "Affilabs.core beta/" to `src/`
3. Update imports to use `src.` prefix (or add `src/` to PYTHONPATH)
4. Move all .md files to `docs/`
5. Move debug scripts to `tools/`

## Quick Fix for Now:
Since you're actively developing, you can:
1. Always use `run_clean.ps1` to start the app
2. Or run: `.\clear_cache.ps1 ; python -B main_simplified.py`
3. Use `-B` flag to prevent bytecode generation

## Python Cache Behavior:
- `.pyc` files are compiled bytecode (faster loading)
- `__pycache__/` stores these files
- Once imported, modules stay in memory until process ends
- Changes to `.py` files won't reload automatically
- **Solution**: Kill process + clear cache + restart

## IDE Configuration:
If using VS Code, add to `.vscode/settings.json`:
```json
{
    "python.analysis.exclude": ["**/__pycache__"],
    "files.watcherExclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```
