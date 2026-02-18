# SharePoint File Upload Integration Guide

## Step 1: Create the Power Automate Flow

### Method 1: Import from JSON (Fastest)
1. Open the file `SharePoint_Upload_Flow.json`
2. Copy the entire contents
3. Go to [Power Automate](https://make.powerautomate.com)
4. Click **My flows** → **New flow** → **Instant cloud flow**
5. Name it: "SharePoint File Upload from Wix"
6. Choose trigger: **When a HTTP request is received**
7. Click **Create**
8. In the flow editor, click **...** (top right) → **Peek code**
9. Replace everything with the JSON content
10. Click **Save**

### Method 2: Manual Creation
1. Go to [Power Automate](https://make.powerautomate.com)
2. Create **Instant cloud flow** → **When a HTTP request is received**
3. Copy the Request Body JSON Schema from the flow definition
4. Add actions as shown in the JSON file

## Step 2: Get the HTTP Trigger URL

1. After saving the flow, the **HTTP POST URL** will appear in the trigger
2. **Copy this URL** - you'll need it for Wix

Example URL format:
```
https://prod-xx.westus.logic.azure.com:443/workflows/.../triggers/manual/paths/invoke?...
```

## Step 3: Configure Your Wix Website

### Add Form Elements to Wix Page:
1. **Upload Button** (ID: `uploadButton`)
   - Type: File Upload
   - Allowed: All file types

2. **Text Input - Full Name** (ID: `fullNameInput`)
   - Placeholder: "Your full name"
   - Required

3. **Text Input - Email** (ID: `emailInput`)
   - Input type: Email
   - Placeholder: "your@email.com"
   - Required

4. **Text Element - Status** (ID: `statusMessage`)
   - For showing upload status/errors

### Add the Code:
1. Open **Developer Tools** in Wix
2. Enable **Velo** (if not already enabled)
3. Open the code for your page
4. Copy the contents of `Wix_Upload_Code.js`
5. **Replace** `YOUR_HTTP_TRIGGER_URL_HERE` with your actual Power Automate URL
6. Save and publish

## Step 4: Test the Integration

1. Go to your Wix page
2. Fill in name and email
3. Upload a file
4. Check SharePoint folder for:
   - New subfolder named with timestamp and email
   - Uploaded file inside that folder

## Flow Behavior

**What happens:**
1. User uploads file on Wix website
2. File is converted to base64 and sent to Power Automate via HTTP
3. Flow creates a new folder: `/External General Share/Diagnostic Files Intake/20260202-120530-username/`
4. File is saved in that folder
5. Success message shown to user with ticket number

**Ticket Number Format:**
`20260202-120530-username` (Date-Time-EmailPrefix)

## Troubleshooting

### Flow fails with "Root folder not found"
- Verify the SharePoint site URL is correct
- Check the folder path exists: `/External General Share/Diagnostic Files Intake/`

### Wix upload fails with CORS error
- Power Automate HTTP triggers allow CORS by default
- No additional configuration needed

### File appears corrupted
- Ensure base64 conversion is correct
- Check the Wix code uses `fileToBase64()` function properly

### Connection authentication fails
- In Power Automate flow, click each SharePoint action
- Re-authenticate your SharePoint connection

## Security Notes

⚠️ **Important**: The HTTP trigger URL is sensitive
- Anyone with the URL can upload files
- Consider adding additional validation in the flow
- Monitor usage and disable if needed

## Alternative: Add Basic Authentication

To add a simple API key check, modify the flow:

1. Add **Condition** action after trigger
2. Expression: `@equals(triggerBody()?['apiKey'], 'YOUR_SECRET_KEY')`
3. If no: Return 401 Unauthorized
4. Update Wix code to include `apiKey: 'YOUR_SECRET_KEY'` in the request body

---

Files created:
- `SharePoint_Upload_Flow.json` - Power Automate flow definition
- `Wix_Upload_Code.js` - Wix website integration code
- `INTEGRATION_GUIDE.md` - This documentation
