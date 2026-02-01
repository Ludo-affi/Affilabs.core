# Complete Setup Guide: Cloud Database + Microsoft Forms + Online Deployment

This guide walks through all 3 steps to get your diagnostic system fully online.

---

## Step 1: Move Database to Cloud (Backup)

### Option A: OneDrive/SharePoint (Recommended - Simplest)

**Setup Time:** 5 minutes

#### 1. Create SharePoint Folder for Database Backups

1. Go to your SharePoint site: `https://affinitylabs.sharepoint.com`
2. Navigate to **Documents** or create a new Library
3. Create folder: **"Spark AI Backups"**
4. Click **Share** → **Anyone with the link can upload**
   - Or: "People in [your organization] can upload" (more secure)
5. Copy the upload link

#### 2. Configure Auto-Sync in ezControl

Edit `affilabs/services/cloud_database_sync.py`:

```python
# Line 16 - Set sync method
SYNC_METHOD = 'onedrive'  # Use OneDrive/SharePoint

# Line 19 - Paste your SharePoint upload URL
ONEDRIVE_UPLOAD_URL = "https://affinitylabs.sharepoint.com/sites/yoursite/Shared%20Documents/Spark%20AI%20Backups"
```

#### 3. Test the Sync

Run this in Python terminal:
```python
from affilabs.services.cloud_database_sync import CloudDatabaseSync

syncer = CloudDatabaseSync()
success, message = syncer.sync_to_cloud()
print(f"Sync result: {message}")
```

Check your SharePoint folder - you should see:
```
spark_qa_backup_20260201_143052.json
```

**✅ Done!** Database now backs up to SharePoint automatically when diagnostics are sent.

---

### Option B: Azure Cosmos DB (Enterprise - For Large Scale)

**Setup Time:** 20 minutes
**Cost:** Free tier: 1000 RU/s, 25 GB storage

#### 1. Create Cosmos DB Account

1. Go to [Azure Portal](https://portal.azure.com)
2. Create resource → **Azure Cosmos DB**
3. Choose **Core (SQL) API**
4. Fill in:
   - Subscription: Your subscription
   - Resource Group: Create new "ezControl-Resources"
   - Account Name: "ezcontrol-db" (must be globally unique)
   - Location: Choose closest region
   - Capacity mode: **Serverless** (free tier)
5. Click **Review + Create**

#### 2. Create Database and Container

1. Go to your Cosmos DB account
2. **Data Explorer** → **New Container**
3. Database id: `ezcontrol`
4. Container id: `spark_qa`
5. Partition key: `/timestamp`
6. Click **OK**

#### 3. Get Connection Details

1. Go to **Keys** tab
2. Copy:
   - **URI** (looks like: `https://ezcontrol-db.documents.azure.com:443/`)
   - **PRIMARY KEY** (long string)

#### 4. Configure ezControl

Edit `affilabs/services/cloud_database_sync.py`:

```python
# Line 16
SYNC_METHOD = 'azure_cosmos'

# Line 22-24
COSMOS_ENDPOINT = "https://ezcontrol-db.documents.azure.com:443/"
COSMOS_KEY = "YOUR_PRIMARY_KEY_HERE"  # KEEP SECRET!
COSMOS_DATABASE = "ezcontrol"
COSMOS_CONTAINER = "spark_qa"
```

**Security:** Store the key in environment variable:
```python
import os
COSMOS_KEY = os.getenv('COSMOS_DB_KEY')
```

Set environment variable:
```powershell
$env:COSMOS_DB_KEY = "your-key-here"
```

#### 5. Install Azure SDK

```bash
pip install azure-cosmos
```

#### 6. Test Connection

```python
from affilabs.services.cloud_database_sync import CloudDatabaseSync

syncer = CloudDatabaseSync()
success, message = syncer.sync_to_cloud()
print(message)
```

Check Azure Portal → Data Explorer → You should see documents in `spark_qa` container.

**✅ Done!** Your Q&A data is now in Azure Cosmos DB.

---

## Step 2: Setup Microsoft Forms for Tickets

**Setup Time:** 10 minutes

### 1. Create Support Ticket Form

1. Go to [forms.office.com](https://forms.office.com)
2. Click **+ New Form**
3. Title: **"ezControl Support Ticket"**
4. Description: "Report issues and request support for ezControl SPR software"

### 2. Add Form Fields

Click **+ Add new** for each field:

#### **Section 1: Contact Information**

1. **Your Name**
   - Type: Short answer
   - Required: ✅ Yes

2. **Email Address**
   - Type: Short answer
   - Required: ✅ Yes

3. **Company/Institution**
   - Type: Short answer
   - Required: ❌ No

#### **Section 2: System Information** (Pre-filled by ezControl)

4. **Diagnostic ID**
   - Type: Short answer
   - Required: ✅ Yes
   - Description: "Automatically generated - do not change"
   - Default: Will be filled by URL parameter

5. **Software Version**
   - Type: Short answer
   - Required: ✅ Yes
   - Default: Will be filled by URL parameter

#### **Section 3: Issue Details**

6. **Priority**
   - Type: Choice (single answer)
   - Options:
     - 🟢 Low - General question or minor issue
     - 🟡 Medium - Issue affecting workflow
     - 🟠 High - Critical functionality not working
     - 🔴 Urgent - System completely down
   - Required: ✅ Yes

7. **Issue Summary** (one-line description)
   - Type: Short answer
   - Required: ✅ Yes
   - Example: "Calibration fails with detector timeout error"

8. **Detailed Description**
   - Type: Long answer
   - Required: ✅ Yes
   - Description: "Describe what happened in detail"

9. **Steps to Reproduce**
   - Type: Long answer
   - Required: ❌ No
   - Description: "How can we reproduce this issue?"

10. **Expected Behavior**
    - Type: Long answer
    - Required: ❌ No
    - Description: "What should have happened?"

11. **Additional Screenshots** (if needed)
    - Type: File upload
    - Required: ❌ No
    - Allow multiple files: ✅ Yes

### 3. Configure Form Settings

Click **⚙️ Settings** (top right):

#### **Responses Tab:**
- ✅ **Record name and collect email**
- ✅ **One response per person**
- ✅ **Send email receipt of response**

#### **Notifications Tab:**
- ✅ **Get email notification of each response**
- Email address: `support@affinitylabs.com`

#### **Customize Thank You Message:**
```
✅ Your support ticket has been submitted!

Ticket ID: [Response ID]

We've received your diagnostic files and issue report. 
Our support team will review your ticket and respond within 24 hours.

You'll receive a copy of your submission via email.

Thank you for using ezControl!
```

### 4. Get Form URL

1. Click **Collect responses** (top right)
2. Copy the link (looks like):
   ```
   https://forms.office.com/r/AbC123XyZ
   ```

### 5. Connect Form to SharePoint List (Optional - Advanced)

For better ticket tracking:

1. Create SharePoint list: **"Support Tickets"**
2. In Microsoft Forms, go to **Responses** tab
3. Click **Open in Excel** → **Create Table**
4. Or use Power Automate to auto-create SharePoint items

### 6. Configure ezControl

Edit `affilabs/services/diagnostic_uploader.py`:

```python
# Line 38 - Paste your Microsoft Forms URL
MICROSOFT_FORMS_URL = "https://forms.office.com/r/AbC123XyZ"
```

### 7. Test the Integration

1. Run ezControl
2. Go to **Device Status** tab
3. Click **"Send Diagnostic Files to AffiLabs"**
4. Follow the prompts
5. Form should open in browser with:
   - Diagnostic ID pre-filled
   - Software version pre-filled
   - Your email pre-filled (if provided)

**✅ Done!** Users can now submit tickets directly!

---

## Step 3: Put It Online (Full Deployment)

### What "Online" Means:

1. ✅ Database backs up to cloud automatically
2. ✅ Diagnostic files upload to SharePoint
3. ✅ Support tickets created via Microsoft Forms
4. ✅ Everything accessible from anywhere

### Quick Test Checklist

- [ ] **Database Sync Works**
  - Upload diagnostics → Check SharePoint for backup JSON
  - Or check Azure Cosmos DB Data Explorer

- [ ] **File Upload Works**
  - Click "Send Diagnostics" button
  - Check SharePoint diagnostics folder for ZIP file

- [ ] **Form Opens Correctly**
  - Browser opens to Microsoft Forms
  - Diagnostic ID is pre-filled
  - Software version is pre-filled

- [ ] **Email Notification Works**
  - Submit test ticket
  - Check support@affinitylabs.com inbox
  - Verify email contains all ticket details

- [ ] **User Confirmation Works**
  - User receives email receipt from Microsoft Forms
  - Thank you message shows ticket created

---

## Complete User Flow (After Setup)

### User Side:
1. Encounters issue in ezControl
2. Clicks **"📤 Send Diagnostic Files to AffiLabs"**
3. Enters email (optional)
4. Clicks **Yes** on confirmation dialog
5. Waits 5-10 seconds while files upload
6. Browser opens to ticket form
7. Fills out:
   - Name
   - Issue description
   - Priority
   - Steps to reproduce
8. Clicks **Submit**
9. Sees: "✅ Ticket created! We'll respond within 24 hours"
10. Receives email confirmation

### Your Side (Support Team):
1. Receive email notification:
   ```
   Subject: [New Support Ticket] Issue from John Doe
   
   Priority: High
   User: John Doe (john@company.com)
   Diagnostic ID: ezcontrol_diagnostics_20260201_143052
   
   Issue: Calibration fails with detector timeout
   
   Description: When I try to calibrate...
   
   Diagnostic Files:
   https://affinitylabs.sharepoint.com/diagnostics/ezcontrol_diagnostics_20260201_143052.zip
   ```

2. Download diagnostic bundle from SharePoint
3. Review logs, Spark transcripts, calibration data
4. Reply to user's email with solution
5. Update SharePoint ticket status to "Resolved"

---

## Monitoring & Maintenance

### Weekly Tasks:
- Check SharePoint folders for new diagnostics
- Review open tickets in Microsoft Forms responses
- Check database backup folder (ensure syncing)

### Monthly Tasks:
- Export Microsoft Forms responses to Excel
- Analyze common issues from Spark transcripts
- Update Spark patterns for frequent questions
- Check storage usage in SharePoint/Azure

### Quarterly Tasks:
- Train new Spark AI model with collected Q&A data
- Update calibration procedures based on support tickets
- Review and improve Microsoft Forms questions

---

## Costs

| Service | Free Tier | Paid Options |
|---------|-----------|--------------|
| **OneDrive/SharePoint** | 1 TB with Microsoft 365 | Unlimited with E3/E5 |
| **Microsoft Forms** | Unlimited forms | Free with Microsoft 365 |
| **Azure Cosmos DB** | 1000 RU/s, 25 GB | Pay per use after limit |
| **Email** | Included with Microsoft 365 | N/A |

**Recommended Setup Cost:** $0 (if you have Microsoft 365)

---

## Troubleshooting

### Database Not Syncing
- Check SharePoint URL is correct
- Verify upload permissions on folder
- Check logs: `logger.info("Sync result...")` messages

### Form Not Opening
- Verify MICROSOFT_FORMS_URL is set correctly
- Check default browser is configured
- Test form URL manually in browser

### Diagnostic Files Not Uploading
- Check SharePoint upload link hasn't expired
- Verify network connection
- Check file size (SharePoint limit: 250 GB)

### No Email Notifications
- Check Microsoft Forms notification settings
- Verify support@affinitylabs.com inbox
- Check spam/junk folder
- Ensure Forms license allows notifications

---

## Security Best Practices

1. **Use organization-only sharing** for SharePoint folders
2. **Store Azure keys in environment variables**, not code
3. **Enable virus scanning** on SharePoint uploads
4. **Set expiration dates** on upload links (renew monthly)
5. **Review access logs** in SharePoint regularly
6. **Limit who can view** support tickets (confidential data)

---

## Next Steps

1. ✅ Complete Step 1 (Database to cloud)
2. ✅ Complete Step 2 (Microsoft Forms)
3. ✅ Configure URLs in code
4. ✅ Test end-to-end workflow
5. ✅ Train support team on new process
6. ✅ Announce to users

**Need help?** Email me or check the documentation!
