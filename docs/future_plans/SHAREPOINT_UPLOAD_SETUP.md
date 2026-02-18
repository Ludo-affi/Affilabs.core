# SharePoint/OneDrive Upload Setup Guide

## Overview
Configure direct upload of diagnostic files to your SharePoint/OneDrive for easy collection without email attachments.

## Option 1: SharePoint Upload Link (Recommended - Simplest)

### Step 1: Create SharePoint Upload Folder
1. Go to your SharePoint site
2. Navigate to Documents (or create new folder "Diagnostics")
3. Click **Share** → **Anyone with the link can upload**
4. Copy the link

### Step 2: Configure ezControl
Edit `affilabs/services/diagnostic_uploader.py`:

```python
# Line 25 - Replace with your SharePoint upload link
SHAREPOINT_UPLOAD_URL = "https://affinitylabs.sharepoint.com/:f:/g/EwABCDEF123/diagnostics"

# Line 35 - Set upload method
UPLOAD_METHOD = 'sharepoint'
```

### Step 3: Test Upload
1. Run ezControl
2. Go to Device Status tab
3. Click "Send Diagnostic Files to AffiLabs"
4. Files will upload directly to your SharePoint folder

**Pros:**
- ✅ No authentication needed
- ✅ Works with large files
- ✅ Users can upload anonymously
- ✅ You manage permissions from SharePoint

**Cons:**
- ⚠️ Anyone with link can upload (can restrict to your organization)

---

## Option 2: OneDrive Shared Folder

### Step 1: Create OneDrive Folder
1. Go to OneDrive for Business
2. Create folder: "ezControl Diagnostics"
3. Right-click → **Share** → **Get Link**
4. Select: **People in [your organization] can upload**
5. Copy link

### Step 2: Extract Folder ID
From the link like:
```
https://affinitylabs-my.sharepoint.com/personal/you/Documents/Diagnostics?id=/personal/you/Documents/Diagnostics
```

Extract the folder ID (part after `id=`)

### Step 3: Configure
```python
SHAREPOINT_UPLOAD_URL = "YOUR_ONEDRIVE_UPLOAD_LINK"
UPLOAD_METHOD = 'sharepoint'
```

---

## Option 3: Microsoft Graph API (Advanced - Requires Auth)

For enterprise deployments with authentication.

### Step 1: Register Azure AD App
1. Go to [Azure Portal](https://portal.azure.com)
2. Azure Active Directory → App registrations → New registration
3. Name: "ezControl Diagnostics Uploader"
4. Redirect URI: `http://localhost` (or your app URI)
5. Copy **Application (client) ID** and **Directory (tenant) ID**

### Step 2: Configure API Permissions
1. Go to API permissions → Add permission
2. Microsoft Graph → Delegated permissions
3. Add: `Files.ReadWrite`, `Files.ReadWrite.All`
4. Grant admin consent

### Step 3: Create Client Secret
1. Certificates & secrets → New client secret
2. Copy the secret value (only shown once!)

### Step 4: Get Folder ID
1. Upload a test file to your OneDrive folder
2. Use [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer):
   ```
   GET https://graph.microsoft.com/v1.0/me/drive/root/children
   ```
3. Find your folder and copy the `id`

### Step 5: Configure ezControl
```python
ONEDRIVE_FOLDER_ID = "01234567ABCDEF!123"  # From Graph API
UPLOAD_METHOD = 'onedrive'

# Add OAuth credentials to config file (not in code!)
AZURE_CLIENT_ID = "your-client-id"
AZURE_CLIENT_SECRET = "your-secret"
AZURE_TENANT_ID = "your-tenant-id"
```

**Note:** Requires implementing OAuth token flow (more complex)

---

## Option 4: Custom HTTP Server

If you have your own server to receive uploads.

### Step 1: Create Upload Endpoint
Example Flask server:

```python
from flask import Flask, request
import os

app = Flask(__name__)

@app.route('/diagnostics/upload', methods=['POST'])
def upload_diagnostic():
    file = request.files['diagnostic_bundle']
    user_email = request.form.get('user_email', 'anonymous')
    notes = request.form.get('notes', '')
    
    # Save file
    filename = f"{user_email}_{file.filename}"
    file.save(os.path.join('/path/to/storage', filename))
    
    return {'status': 'success'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, ssl_context='adhoc')
```

### Step 2: Configure ezControl
```python
HTTP_UPLOAD_URL = "https://your-server.com/diagnostics/upload"
UPLOAD_METHOD = 'http'
```

---

## Recommended Setup (Quick Start)

**For most users, SharePoint upload link is best:**

1. **Create SharePoint folder:**
   - Go to SharePoint → Documents
   - Create folder "ezControl Diagnostics"
   - Share → "Anyone with link can upload"

2. **Copy link** (looks like):
   ```
   https://affinitylabs.sharepoint.com/:f:/g/personal/...
   ```

3. **Update code** (one line):
   ```python
   # affilabs/services/diagnostic_uploader.py, line 25
   SHAREPOINT_UPLOAD_URL = "YOUR_LINK_HERE"
   ```

4. **Test it:**
   - Launch ezControl
   - Device Status → Send Diagnostic Files
   - Check SharePoint folder for upload

---

## File Size Limits

| Method | Max File Size | Notes |
|--------|--------------|-------|
| SharePoint | 250 GB | Per file limit |
| OneDrive | 250 GB | Per file limit |
| HTTP Server | Depends | Configure your server |
| Email | ~25 MB | Not recommended for diagnostics |

---

## Security Considerations

**SharePoint/OneDrive:**
- ✅ Upload-only links (users can't see other files)
- ✅ Restrict to your organization only
- ✅ Enable virus scanning
- ✅ Set expiration dates on links

**To restrict to organization only:**
1. SharePoint → Share → Settings
2. Change "Anyone" to "People in [Organization]"
3. Requires users to sign in with Microsoft account

---

## Monitoring Uploads

**SharePoint:**
1. Go to your diagnostics folder
2. View → Details to see upload timestamps
3. Set up alerts: Folder → Alert me

**OneDrive:**
1. Activity feed shows all uploads
2. Right-click folder → Version history

---

## Troubleshooting

**Upload fails with "403 Forbidden":**
- Check link hasn't expired
- Verify link allows uploads (not just view)
- Check organization settings allow external sharing

**Upload times out:**
- Large files (>100 MB) may take time
- Increase timeout in code (line 57): `timeout=300`

**Files not appearing:**
- Check you're looking at correct folder
- SharePoint may take a few seconds to index
- Check spam/junk if using notifications

---

## Next Steps

1. Choose your upload method (SharePoint recommended)
2. Create folder and get link
3. Update `diagnostic_uploader.py` with your link
4. Test with "Send Diagnostic Files" button
5. Monitor your SharePoint folder for uploads

For questions, contact your IT admin or AffiLabs support.
