# GitHub Push Strategy - Maintaining Clean Organization

**Date**: November 23, 2025  
**Branch**: v4.0-ui-improvements

---

## 🎯 Recommended Strategy: Clean Commit with Archive

### Step 1: Commit Current Organized State

```powershell
# Check current status
git status

# Add all changes
git add .

# Commit with clear message
git commit -m "chore: Major workspace reorganization and servo calibration improvements

WORKSPACE ORGANIZATION:
- Moved legacy codebase to archive/old_software/
- Moved 48 analysis/test scripts to archive/analysis_scripts/
- Moved backup files to archive/backup_files/
- Clean root directory with only production files
- Clear focus: Affilabs.core beta is primary codebase

SERVO CALIBRATION:
- Implemented auto-trigger when S/P positions missing
- Added user confirmation dialog before saving
- Updated SPRCalibrator to handle defaults gracefully
- Created comprehensive documentation

DOCUMENTATION:
- Created master reference docs (S-pol/P-pol, servo calibration)
- Archived outdated polarizer documentation
- Added workspace organization summary

See: WORKSPACE_ORGANIZATION_CLEAN.md, AUTO_TRIGGER_SERVO_CALIBRATION_COMPLETE.md"

# Push to GitHub
git push origin v4.0-ui-improvements
```

---

## 📊 What Gets Pushed

### ✅ Included in Repository

**Active Code**:
- `Affilabs.core beta/` - Primary application (v4.0)
- `utils/` - Shared utilities (spr_calibrator.py)
- `settings/` - Application settings
- `docs/` - Documentation (master references)
- `tools/` - Production tools
- `tests/` - Test suite
- `scripts/` - Production scripts

**Archive** (for reference):
- `archive/old_software/` - Legacy v3.x codebase
- `archive/backup_files/` - Development backups
- `archive/analysis_scripts/` - Development/analysis scripts

**Configuration**:
- `config/` - Device configurations
- Root production files (setup_device.py, run_app.py, etc.)

### ⚠️ Size Consideration

The archive adds significant size (~150+ subdirectories in old_software).

**If repo becomes too large**, use **Option 2** below to move archive to separate branch.

---

## 🔀 Option 2: Separate Archive Branch (If Needed)

### When to Use
- Repo size > 500MB
- Slow clone times
- GitHub warns about large files
- Most developers don't need legacy code

### Implementation

```powershell
# 1. Create archive branch
git checkout -b archive/legacy-v3
git add archive/
git commit -m "archive: Legacy v3.x code and development scripts

Contents:
- archive/old_software/ - Complete v3.x codebase
- archive/backup_files/ - Development backups
- archive/analysis_scripts/ - 48 analysis/test scripts

Access: git checkout archive/legacy-v3
Main branch: v4.0-ui-improvements (clean)"

git push origin archive/legacy-v3

# 2. Remove archive from main branch
git checkout v4.0-ui-improvements

# Create .gitignore entry for archive
echo "" >> .gitignore
echo "# Legacy code (available in archive/legacy-v3 branch)" >> .gitignore
echo "archive/" >> .gitignore

git rm -r archive/
git commit -m "chore: Move archive to separate branch

Archive moved to: archive/legacy-v3 branch
Active codebase: Affilabs.core beta/
Cleaner repository, faster clones"

git push origin v4.0-ui-improvements
```

### Accessing Archive Later

```powershell
# View archive branch
git checkout archive/legacy-v3

# Return to main development
git checkout v4.0-ui-improvements

# Cherry-pick specific file from archive
git checkout archive/legacy-v3 -- archive/old_software/specific_file.py
```

---

## 📝 Update Documentation

### 1. Update Main README.md

Add clear section pointing to active codebase:

```markdown
## 🚀 Active Development

**Primary Codebase**: `Affilabs.core beta/`

This directory contains the v4.0+ application with:
- Modern UI architecture
- Auto-trigger servo calibration
- EEPROM backup system
- Comprehensive documentation

**Legacy Code**: Available in `archive/` directory (or `archive/legacy-v3` branch)

---

## Quick Start

```bash
# Run application
python run_app.py

# Or use launcher
.\run_app_312.ps1
```

See `Affilabs.core beta/main_simplified.py` for entry point.
```

### 2. Create CONTRIBUTING.md

```markdown
# Contributing Guidelines

## Development Focus

**Active Development**: `Affilabs.core beta/`

All new features, bug fixes, and improvements should target this directory.

## Archive Policy

- `archive/` contains historical code for reference only
- Do NOT import from `archive/`
- Do NOT modify files in `archive/`
- If you need old code, copy to appropriate location and update

## Pull Request Guidelines

1. Target branch: `v4.0-ui-improvements`
2. Focus area: `Affilabs.core beta/`
3. Update docs in `docs/` if needed
4. Run tests before submitting
```

---

## 🔧 .gitignore Updates

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyc
.Python
*.so

# Virtual environments
.venv/
.venv312/
venv/

# IDE
.vscode/
.idea/

# Logs
logs/
*.log

# Analysis results (optional)
analysis_results/
spectral_training_data/
training_data/

# Generated files
generated-files/
.mypy_cache/
build/
dist/

# Device configs (if sensitive)
config/devices/*/

# Archive (if using Option 2)
# archive/
```

---

## 🏷️ GitHub Release Strategy

### Create Release for Clean v4.0

```powershell
# Tag the clean organized state
git tag -a v4.0.0-clean -m "Version 4.0.0 - Clean organized codebase

- Workspace reorganization complete
- Auto-trigger servo calibration
- EEPROM backup system
- Comprehensive documentation
- Archive of legacy code for reference"

git push origin v4.0.0-clean
```

### GitHub Release Notes

Create release on GitHub with:

**Title**: `v4.0.0 - Clean Organized Codebase`

**Description**:
```markdown
## 🎉 Major Workspace Reorganization

This release represents a complete reorganization of the codebase for clarity and maintainability.

### ✨ New Features
- **Auto-trigger servo calibration** when positions missing
- **EEPROM backup system** for device configurations
- **Master reference documentation** (S-pol/P-pol, servo calibration)

### 📁 Workspace Organization
- **Active code**: `Affilabs.core beta/` (v4.0+)
- **Legacy code**: `archive/` (v3.x reference)
- **Documentation**: `docs/` (master references)

### 🚀 Quick Start
```bash
python run_app.py
```

See `WORKSPACE_ORGANIZATION_CLEAN.md` for complete details.
```

---

## 📊 Maintenance Going Forward

### Branch Strategy

```
main (or master)
├── v4.0-ui-improvements (current)
├── v4.1-new-features (future)
└── archive/legacy-v3 (if using Option 2)
```

### Development Workflow

1. **Feature branches** off `v4.0-ui-improvements`
2. **All work** in `Affilabs.core beta/`
3. **Never modify** `archive/`
4. **Update docs** when adding features
5. **Merge to** `v4.0-ui-improvements` when ready

### Prevent Archive Confusion

Add to `.github/CODEOWNERS` (if exists):
```
# Only maintainers can modify archive
/archive/ @maintainer-username
```

Add branch protection rule:
- Require PR review for `archive/` changes
- Prevent direct pushes to `archive/`

---

## ✅ Pre-Push Checklist

- [ ] Committed workspace organization changes
- [ ] Updated README.md with clear active codebase location
- [ ] Updated .gitignore to exclude generated files
- [ ] Tested application runs: `python run_app.py`
- [ ] Verified import paths work correctly
- [ ] Documentation files created/updated
- [ ] Checked repo size (consider Option 2 if >500MB)
- [ ] Created release tag if desired

---

## 🎯 Summary: Recommended Commands

```powershell
# Standard push (with archive)
git add .
git commit -m "chore: Workspace reorganization and servo calibration improvements"
git push origin v4.0-ui-improvements

# Create release tag
git tag -a v4.0.0-clean -m "Clean organized v4.0.0 release"
git push origin v4.0.0-clean

# Optional: If repo too large, use separate archive branch
git checkout -b archive/legacy-v3
git add archive/
git commit -m "archive: Legacy code for reference"
git push origin archive/legacy-v3
git checkout v4.0-ui-improvements
git rm -r archive/
git commit -m "chore: Move archive to separate branch"
git push origin v4.0-ui-improvements
```

---

**END OF GITHUB PUSH STRATEGY**
