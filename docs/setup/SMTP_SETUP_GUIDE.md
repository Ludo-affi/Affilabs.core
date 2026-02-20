# Bug Reporter — Manual Email Submission

**Version:** Affilabs.core v2.0.5  
**Status:** 🟢 Active (No SMTP Configuration Needed)  
**Last Updated:** February 19, 2026

---

## Overview

The bug reporter generates formatted email drafts that users read and send manually using their own email client. **No SMTP configuration, passwords, or email server setup required.**

**Workflow:**
1. User encounters a bug and clicks **Help** → **SPARK** → **Report Bug**
2. User enters a description
3. App generates an email draft with:
   - System information
   - Last 100 lines of logs
   - Screenshot (saved automatically)
4. User copies the draft text
5. User opens their email client and pastes it
6. User attaches the screenshot file (optional)
7. User sends to `info@affiniteinstruments.com`

---

## How to Use the Bug Reporter

### 1. Click "Report Bug"

From the Help panel:
- Click **Help** (?) button
- Go to **SPARK** tab
- Click **Report Bug**

### 2. Describe the Issue

Type a description of what went wrong:
```
The sensorgram graph freezes when I click on the Edits tab
after recording a 30-minute cycle with 4 channels.
```

### 3. Click Submit

The app will:
- ✅ Generate an email draft  
- ✅ Save a screenshot to `_data/screenshot_YYYYMMDD_HHMMSS.png`
- ✅ Collect system info and logs
- ✅ Display everything in the chat

### 4. Copy the Draft

The email draft appears in the chat. It includes:
```
Subject: [Affilabs Bug] 2026-02-19 14:30 — Your Name

════════════════════════════════════════════════════════════════════════════════
BUG REPORT — Affilabs.core
════════════════════════════════════════════════════════════════════════════════

Reporter : Your Name
Submitted: 2026-02-19 14:30

DESCRIPTION
───────────────────────────────────────────────────────────────────────────────
The sensorgram graph freezes...

SYSTEM INFO
───────────────────────────────────────────────────────────────────────────────
Version : 2.0.5
OS      : Windows-10 (...)
...
```

**Copy this entire text** (`Ctrl+A` → `Ctrl+C`)

### 5. Open Your Email Client

- **Gmail:** gmail.com
- **Outlook:** outlook.com
- **Desktop app:** Outlook, Thunderbird, Apple Mail, etc.

### 6. Compose a New Email

Paste the draft:
1. Click "Compose" or "New Email"
2. Paste the text (`Ctrl+V`)
3. The subject/recipient are already filled in

### 7. Attach the Screenshot

The app saved a screenshot file. Attach it:
- Look in the `_data/` folder or `Documents/Affilabs Data/`
- Find the most recent `screenshot_*.png` file
- Attach it to the email

### 8. Review & Send

- Review the email contents
- Click **Send**
- Confirmation notification appears

---

## What Gets Included in a Bug Report?

### Automatically Collected:
- ✅ User's typed description
- ✅ System info: OS version, Python version, machine type, Affilabs version, device serial
- ✅ Last 100 lines from the app log file
- ✅ Screenshot of the app window (if screenshot is available)

### NOT Included (Privacy Protected):
- ❌ Your password or credentials
- ❌ Experiment data or measurement results
- ❌ Personal files or folders
- ❌ Network configuration
- ❌ Anything you don't explicitly include

---

## Troubleshooting

### Screenshot Not Saved?

If the screenshot could not be captured:
1. Take a manual screenshot (`Windows Key + Shift + S`)
2. Attach it manually to the email

### Can't Find the Screenshot File?

Screenshots are saved to:
- `_data/screenshot_YYYYMMDD_HHMMSS.png` (in the Affilabs.core folder)
- Or check your Downloads folder if you saved it there

### Email Didn't Send?

- Verify the recipient email is correct: `info@affiniteinstruments.com`
- Check your email client's outbox
- Ensure you have an internet connection

### Need to Report Multiple Issues?

Just click **Report Bug** again. Each one generates a new draft and screenshot.

---

## Support Email

Send reports to: **info@affiniteinstruments.com**

We typically respond within 1-2 business days.

### What Happens After You Send?

1. Our support team receives your email
2. We review the system info and logs
3. We reproduce the issue if possible
4. We either:
   - Send a fix in the next release
   - Ask for more information
   - Confirm it's a known issue with a workaround

---

## FAQ

**Q: Why no automatic SMTP sending?**  
A: Manual email is more secure (no passwords stored), simpler (no config needed), and users retain control of what they share.

**Q: Can I send from a different email address?**  
A: Yes — just edit the "To:" field in the email before sending if you want a reply sent elsewhere.

**Q: Is my data secure?**  
A: Yes. You control what you send. Nothing is transmitted automatically. Only you and your email provider see the contents before it reaches our inbox.

**Q: What if I want to add more information?**  
A: Edit the draft before sending. You can add notes, error messages, steps to reproduce, etc.

---

## For Development/Testing

If you want to **test the bug reporter locally**:

```python
from affilabs.services.bug_reporter import send_bug_report, save_screenshot

# Generate a draft
ok, draft = send_bug_report("Test bug description", user_name="Test User")
print(draft)

# Or save a screenshot separately
path = save_screenshot()
print(f"Screenshot saved to: {path}")
```

