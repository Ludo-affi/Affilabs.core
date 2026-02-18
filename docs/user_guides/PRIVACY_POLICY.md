# Affilabs.core Privacy Policy

**Last Updated:** February 14, 2026
**Version:** 2.0

---

## 🔒 Privacy Commitment

**Your user data stays on YOUR computer.**
We take privacy seriously and follow these principles:

1. **Local-First:** User profiles are stored locally only
2. **No Cloud Upload:** User database is NEVER synced to cloud
3. **Minimal Export:** Only operator name exported (for data attribution)
4. **User Control:** You choose what gets shared (if anything)
5. **Transparency:** This document explains exactly what data goes where

---

## 📍 What Data Stays Local (NEVER Uploaded)

### ✅ User Profiles (`user_profiles.json`)

**Location:** `./user_profiles.json` (workspace directory)

**Contains:**
- User names (e.g., "John Smith", "Ludo")
- Experiment counts (used for progression system)
- Progression data (Novice → Operator → Specialist → Expert → Master)
- Training completion status (compression training)

**Upload Status:** 🔒 **NEVER UPLOADED TO CLOUD**

**Why it's local:**
- Privacy protection
- Sensitive lab personnel information
- No business need to share
- User control over their data

**Code Protection:**
```python
# From cloud_database_sync.py (line 381+)
# 🔒 PRIVACY: User Profiles Are Never Uploaded
# user_profiles.json STAYS LOCAL ONLY for privacy protection
```

### ✅ Methods Database (Per-User)

**Location:** `~/Documents/Affilabs Methods/[Username]/` (JSON files)

**Contains:**
- Your saved method templates
- Cycle configurations
- Personal workflow presets

**Upload Status:** 🔒 **LOCAL ONLY** (unless you explicitly share)

**Why it's local:**
- Your methods are your intellectual property
- May contain proprietary protocols
- Lab-specific configurations

---

## 📤 What Data Gets Exported (With Your Action)

### 1️⃣ Excel Experiment Files

**When You Export Data:**

**What's Included:**
- ✅ Operator name (current user from dropdown)
- ✅ Timestamp
- ✅ Device serial number
- ✅ Experiment data (sensorgrams, cycles, flags)

**What's NOT Included:**
- ❌ Other user profiles
- ❌ Total user count
- ❌ Experiment counts for other users
- ❌ Progression data

**Example Metadata:**
```json
{
  "User": "Ludo",
  "Timestamp": "2026-02-14T15:30:00Z",
  "Device_Serial": "P4SPR_001234"
}
```

**Purpose:** Data attribution for GLP/GMP compliance
**Control:** You can change user name or use "Anonymous" when exporting

### 2️⃣ Diagnostic Bundles (Optional)

**When You Click "Upload Diagnostics":**

**What's Included:**
- ✅ Device logs
- ✅ Calibration results
- ✅ Error messages
- ✅ Hardware configuration
- ✅ **Optional:** Your email (if you provide it)

**What's NOT Included:**
- ❌ User profiles database
- ❌ Other users' information
- ❌ Experiment data (unless you choose to include it)

**Purpose:** Troubleshooting and support
**Upload Destination:** AffiLabs support OneDrive (secure)
**Control:** You manually trigger this (not automatic)

### 3️⃣ Cloud Sync (Optional - Disabled by Default)

**If You Enable Cloud Sync for Spark AI:**

**What's Uploaded:**
- ✅ Spark AI Q&A history (your questions to the AI assistant)
- ✅ Device history (ML training data - no personal info)
- ✅ Latest QC reports (calibration quality metrics)
- ✅ Methods database (if you choose to share templates)

**What's NEVER Uploaded:**
- 🔒 **user_profiles.json** - BLOCKED in code
- ❌ Raw experiment data (unless you export it manually)
- ❌ Personal information

**Code Protection:**
```python
# sync_all_databases() function explicitly EXCLUDES user_profiles.json
# See affilabs/services/cloud_database_sync.py line 381
```

---

## 🛡️ Technical Implementation

### File-Level Protection

| File | Location | Cloud Sync | Export | Purpose |
|------|----------|------------|--------|---------|
| **user_profiles.json** | `./ ` | 🔒 **NEVER** | ❌ No | User management |
| **methods_db.json** | `./ ` | ⚠️ Optional | ❌ No | Method templates |
| **spark_qa_history.json** | `./ ` | ⚠️ Optional | ❌ No | AI chat logs |
| **device_history.db** | `tools/ml_training/` | ⚠️ Optional | ❌ No | ML training data |
| **[Experiment].xlsx** | `output/[User]/SPR_data/` | ❌ No | ✅ Yes | Experiment results |
| **calibration_results/** | `calibration_results/` | ⚠️ Optional | ❌ No | QC metrics |

### Code-Level Protection

**1. Cloud Sync Exclusion:**
```python
# affilabs/services/cloud_database_sync.py, line 310
def sync_all_databases():
    # ...uploads Spark AI, Device History, QC Reports, Methods...

    # 🔒 PRIVACY: User Profiles Are Never Uploaded
    # user_profiles.json STAYS LOCAL ONLY
```

**2. Export Metadata Filter:**
```python
# affilabs/services/user_profile_manager.py, line 190
def get_user_for_metadata(self) -> dict:
    """Only current user NAME exported - never full database"""
    return {"User": self.current_user}  # Single name only
```

**3. No Auto-Upload:**
- User profiles are NOT included in diagnostic bundles
- No automatic sync timer for user data
- Manual export only (you click "Export")

---

## 🔐 Data Security

### Local Storage
- **Location:** Workspace directory (not AppData, not cloud folders)
- **Format:** JSON (plain text for transparency)
- **Access:** Only you (Windows file permissions)
- **Backup:** Your responsibility (copy user_profiles.json manually)

### Network Communication
- **No Auto-Upload:** User profiles never sent over network
- **TLS/HTTPS:** Diagnostic uploads use encrypted channels (if you choose to upload)
- **No Tracking:** No analytics or telemetry on user profiles

### GLP/GMP Compliance
- **Data Attribution:** Operator name required by regulations
- **Audit Trail:** Timestamps and user actions logged
- **No PII Leak:** Only current operator name in exports (not all users)

---

## 📋 Your Rights & Controls

### ✅ What You Can Do

**1. Review Your Data:**
```
Open: user_profiles.json
View: Your name, experiment count, progression level
```

**2. Delete Your Profile:**
- Settings tab → User Management → Select user → Delete Selected
- Your data removed from database
- Cannot delete last remaining user (system requires at least one)

**3. Export Anonymously:**
- Before exporting, change user dropdown to "Anonymous" or create a generic user
- Excel files will show that name instead of yours

**4. Disable Cloud Sync:**
```python
# Default setting (already disabled for user_profiles.json)
# Even if you enable Spark AI sync, user profiles are BLOCKED
```

**5. Request Data Deletion:**
- Delete `user_profiles.json` file
- System creates new file with "Default User" on next launch
- Your data is gone (cannot be recovered)

### ⚠️ What We Cannot Do

**We CANNOT:**
- Access your user profiles remotely
- See who uses your system
- Retrieve deleted user data
- Sync user profiles to cloud (code blocks it)

**Even if you grant diagnostic access:**
- Support engineers see device logs, not user profiles
- user_profiles.json is NOT included in diagnostic bundles
- Code explicitly excludes it from all uploads

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL MACHINE ONLY                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  user_profiles.json                                         │
│  ├── User: "Ludo"                                           │
│  ├── Experiment Count: 42                                   │
│  ├── Title: "Specialist"                                    │
│  └── Training: Completed                                    │
│                                                             │
│  🔒 NEVER UPLOADED TO CLOUD                                 │
│  ❌ NOT in diagnostic bundles                               │
│  ❌ NOT in database sync                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                          ⬇️
                   USER CLICKS "EXPORT"
                          ⬇️
┌─────────────────────────────────────────────────────────────┐
│                    EXCEL FILE (LOCAL)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Metadata Sheet:                                            │
│  ├── User: "Ludo"          ← Only current user name        │
│  ├── Timestamp: 2026-02-14                                  │
│  └── Device: P4SPR_001234                                   │
│                                                             │
│  ✅ ONLY if you share this file                             │
│  ✅ You control who receives it                             │
│  ✅ Required for data attribution (GLP/GMP)                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆘 Privacy FAQs

### Q: Is my user profile uploaded to the cloud?
**A:** 🔒 **NO.** The code explicitly blocks user_profiles.json from all cloud sync operations. Even if you enable Spark AI cloud sync, user profiles stay local.

### Q: Can AffiLabs see who uses my system?
**A:** ❌ **NO.** We have no access to your user profiles. Your user data never leaves your machine unless you manually share exported Excel files.

### Q: What if I need to share my data with a collaborator?
**A:** ✅ You control this:
- Option 1: Export Excel with your name (for attribution)
- Option 2: Change user to "Anonymous" before exporting
- Option 3: Create a generic "Lab User" profile for shared data

### Q: Can I see what data would be uploaded before I sync?
**A:** ✅ Yes:
```python
# Check sync function in affilabs/services/cloud_database_sync.py
# Lines 310-403 list EXACTLY what gets synced
# user_profiles.json is EXCLUDED (line 381 comment)
```

### Q: What if I delete user_profiles.json?
**A:** The system creates a new file with "Default User" on next launch. Your old data is permanently deleted (no copies exist unless you made backups).

### Q: Is user data encrypted?
**A:** Local files are plain JSON (no encryption at rest). Files are protected by Windows file system permissions (only your account can access).

### Q: What about GDPR compliance?
**A:** ✅ Compliant:
- **Right to Access:** You can open user_profiles.json anytime
- **Right to Delete:** Delete user profiles via UI or delete file
- **Right to Portability:** JSON format is portable
- **No Consent Needed:** Data never leaves your machine
- **No Data Processor:** We don't process user profiles

---

## 📞 Contact & Questions

**Privacy Concerns:**
- Email: privacy@affinite.com
- Review code: `affilabs/services/user_profile_manager.py`
- Review sync code: `affilabs/services/cloud_database_sync.py`

**Open Source Transparency:**
- All code is visible in your installation
- Search for "user_profiles.json" to see every reference
- No hidden network calls or telemetry

---

## 🔄 Changes to This Policy

**Policy Updates:**
- Version 2.0 (2026-02-14): Added explicit user profile protection
- Future changes will be documented here
- Check this file for latest privacy practices

**Code Changes:**
- All privacy-critical code is commented with 🔒 markers
- Search codebase for "PRIVACY" to find protection points
- Any changes to data handling will be documented

---

**Summary:** Your user profiles stay on YOUR computer. Forever. We can't access them. We don't upload them. You control your data. 🔒

