# QUICK START - Your Git Setup

## ✅ You're All Set!

**Your working branch:** `dev-lucia-performance`
**Status:** Tracking `origin/dev-lucia-performance` on GitHub

## Performance Settings Protected

- ✅ `TRANSMISSION_UPDATE_INTERVAL = 0.05` (20 Hz - FAST!)
- ✅ `local_settings.py` in `.gitignore` (never tracked)
- ✅ All your fixes committed and pushed to GitHub

## Daily Commands (Just Copy/Paste)

### Save your work:
```powershell
cd "c:\Users\lucia\OneDrive\Desktop\ezControl 2.0\Affilabs.core\Affilabs-core"
git add .
git commit --no-verify -m "Your change description"
git push
```

### Check status:
```powershell
git status
git branch  # Should show * dev-lucia-performance
```

### If settings get slow again:
1. Check `affilabs/app_config.py`
2. Make sure line 71-73 says: `TRANSMISSION_UPDATE_INTERVAL = 0.05`
3. If it's back to 1.0, change it to 0.05 and commit

## What Fixed Your Problem

**Before:** Pushing/pulling from GitHub would overwrite your fast settings with slow ones from master branch

**Now:**
- Your branch (`dev-lucia-performance`) has the fast settings
- GitHub syncs YOUR branch only
- Master branch can be slow - doesn't affect you anymore
- Your work is isolated and protected

## Need Help?

Read [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for detailed guide
