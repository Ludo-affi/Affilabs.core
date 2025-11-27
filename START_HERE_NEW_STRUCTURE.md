# ezControl - Quick Start Guide (New Structure)

## 🚀 Running the Application

### Simple Method (Recommended)
```powershell
.\run_app.ps1
```
This script:
- ✓ Automatically clears Python cache
- ✓ Changes to correct directory (src/)
- ✓ Runs with `-B` flag (no bytecode)
- ✓ Returns to root when done

### Manual Method
```powershell
cd src
python -B main_simplified.py
```

## 📁 New Workspace Structure

```
ezControl-AI/
├── src/                    # 🎯 Main application code
│   ├── core/              # Core logic
│   ├── utils/             # Utilities
│   ├── ui/                # UI components
│   ├── widgets/           # Custom widgets
│   └── main_simplified.py # Entry point
│
├── tools/                  # 🔧 Development tools
│   ├── debug/             # Debug scripts
│   └── diagnostics/       # Diagnostic tools
│
├── docs/                   # 📚 Documentation
│   ├── calibration/       # Calibration guides
│   ├── hardware/          # Hardware docs
│   ├── troubleshooting/   # Debug guides
│   └── guides/            # User guides
│
├── tests/                  # 🧪 Test scripts
├── optical_calibration/    # Calibration data
├── settings/               # Settings files
├── .venv312/              # Python environment
└── run_app.ps1            # ⚡ Start script

```

## 🔄 Migration Status

✅ **COMPLETED:**
- New directory structure created
- Application copied to `src/`
- Startup script created (`run_app.ps1`)
- `.gitignore` updated for new structure

🔜 **TODO (Optional - old structure still works):**
- Organize .md files into `docs/` subdirectories
- Move debug scripts to `tools/debug/`
- Move diagnostic scripts to `tools/diagnostics/`
- Update imports if needed
- Remove old `Affilabs.core beta/` after verification

## 💡 Key Benefits

### Before (Old Structure)
- ❌ Folder name with space: `"Affilabs.core beta"`
- ❌ 100+ .md files scattered in root
- ❌ Debug scripts mixed with main code
- ❌ Cache issues from unclear boundaries
- ❌ Confusing navigation

### After (New Structure)
- ✅ Clean folder names: `src/`, `tools/`, `docs/`
- ✅ Organized documentation by category
- ✅ Separated tools from application code
- ✅ Clear cache management
- ✅ Professional Python project layout
- ✅ Easy to find files

## 🧹 Cache Management

### Why Cache Issues Happen
Python compiles `.py` files to `.pyc` bytecode for speed. When you edit source files, Python might use old cached versions.

### Solutions

**Option 1: Use the startup script (Automatic)**
```powershell
.\run_app.ps1
```

**Option 2: Manual cache clear**
```powershell
Get-ChildItem -Path src -Include __pycache__ -Recurse -Force -Directory | Remove-Item -Recurse -Force
python -B main_simplified.py
```

**Option 3: Nuclear option**
```powershell
cd src
python nuclear_cache_clear.py
python -B main_simplified.py
```

## 🎯 Important Notes

1. **Both structures work**: Old `"Affilabs.core beta"` and new `src/` are identical
2. **No code changes yet**: Just copied, imports unchanged
3. **Safe migration**: Original kept until you verify everything works
4. **Use run_app.ps1**: Best way to avoid cache issues

## 🔧 Development Workflow

1. **Make code changes** in `src/` directory
2. **Run with script**: `.\run_app.ps1` (auto-clears cache)
3. **Or manual**: Clear cache → Run with `-B` flag

## 📝 Next Steps

To complete the migration (optional):

1. **Verify src/ works**: Run `.\run_app.ps1` and test calibration
2. **Move documentation**: Organize .md files into `docs/` subdirectories
3. **Move tools**: Put debug/diagnostic scripts in `tools/`
4. **Test thoroughly**: Make sure everything still works
5. **Remove old**: Delete `"Affilabs.core beta"` directory
6. **Update references**: Any hardcoded paths in scripts

## 🆘 Troubleshooting

**Problem**: "Module not found" errors
**Solution**: Make sure you're in `src/` directory or use `.\run_app.ps1`

**Problem**: Old code still running after changes
**Solution**: Clear cache manually or use `.\run_app.ps1`

**Problem**: Import errors
**Solution**: Check that all files copied correctly to `src/`

## 📞 Questions?

See `RESTRUCTURING_PLAN.md` for detailed migration information.
