# Git Workflow Guide

## Your Branch Strategy

You now have a clean separation between production code and your development work:

- **`master`** - Stable production code (don't work directly here)
- **`injection-alignment-flags`** - Feature branch (old work)
- **`dev-lucia-performance`** ← **YOUR WORKING BRANCH** (current)

## Daily Workflow

### 1. Always Work on Your Dev Branch

```powershell
# Make sure you're on your branch
git branch  # Should show * dev-lucia-performance

# If not, switch to it:
git checkout dev-lucia-performance
```

### 2. Save Your Work Often

```powershell
# See what changed
git status

# Add specific files (recommended)
git add affilabs/app_config.py
git add affilabs/core/calibration_service.py
# ... add other files you want to save

# Or add everything (be careful!)
git add .

# Commit with a clear message
git commit --no-verify -m "Your description of changes"
```

### 3. Push to GitHub (Backup Your Work)

```powershell
# Push your branch to GitHub
git push origin dev-lucia-performance
```

### 4. When You Need to Merge with Master

```powershell
# First, make sure your work is committed
git status  # Should be clean

# Get latest from master
git fetch origin master

# Merge master into your branch (not the other way!)
git merge origin/master

# If there are conflicts, resolve them, then:
git add .
git commit --no-verify -m "Merge master into dev branch"
git push origin dev-lucia-performance
```

## Important Files to Protect

These files have your performance optimizations:

- `affilabs/app_config.py` - TRANSMISSION_UPDATE_INTERVAL = 0.05
- `affilabs/local_settings.py` - Your local overrides (Git ignores this)
- `.gitignore` - Protects local_settings.py

## If Settings Get Overwritten

If you accidentally pull old slow settings from GitHub:

```powershell
# Check what changed
git diff affilabs/app_config.py

# If TRANSMISSION_UPDATE_INTERVAL is back to 1.0, restore it:
# Edit the file and change it back to 0.05, then:
git add affilabs/app_config.py
git commit --no-verify -m "Restore fast update interval"
git push origin dev-lucia-performance
```

## Emergency: Undo Last Commit (Before Push)

```powershell
# Undo commit but keep your changes
git reset --soft HEAD~1

# Undo commit AND discard changes (DANGEROUS!)
git reset --hard HEAD~1
```

## Quick Reference

```powershell
# Where am I?
git branch

# What changed?
git status

# Save work
git add <files>
git commit --no-verify -m "message"

# Backup to GitHub
git push origin dev-lucia-performance

# See commit history
git log --oneline -10
```

## Why This Fixes Your Problem

**Before:** You were working on different branches, and when you pushed/pulled, Git would merge old settings from `master` into your local code.

**Now:** 
- Your work is on `dev-lucia-performance` 
- This branch has your fast settings (0.05s updates)
- When you push/pull, it only syncs with YOUR branch on GitHub
- `master` can have slow settings (1.0s) - doesn't affect you
- Your `local_settings.py` is never tracked by Git (in .gitignore)

## When You're Ready for Production

Create a Pull Request on GitHub:
1. Go to https://github.com/Ludo-affi/ezControl-AI
2. Click "Pull Requests" → "New Pull Request"
3. Base: `master` ← Compare: `dev-lucia-performance`
4. Review changes, add description
5. Merge when ready

This way `master` gets your improvements, but you control when it happens.
