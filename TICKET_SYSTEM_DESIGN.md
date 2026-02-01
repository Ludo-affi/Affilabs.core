# Improved Diagnostic & Ticket Submission Workflow

## Current Issues with Basic Upload:
- ❌ No ticket tracking
- ❌ No user contact information
- ❌ No issue description/priority
- ❌ Hard to follow up
- ❌ Files uploaded with no context

## Recommended Solution: Integrated Ticket System

### **Option 1: Microsoft Forms + SharePoint (Best for Microsoft 365 Users)**

**User Experience:**
1. User clicks "Report Issue" button in ezControl
2. App uploads diagnostic bundle to SharePoint
3. App opens Microsoft Form in browser with:
   - Diagnostic ID pre-filled
   - User enters: email, issue description, priority
4. Form submits ticket to your email/Teams/SharePoint list
5. User gets confirmation with ticket number

**Setup:**
1. Create Microsoft Form:
   - Name, email, company
   - Issue description
   - Priority (Low/Medium/High/Critical)
   - Diagnostic ID (hidden, pre-filled by app)
   - Screenshot upload (optional)

2. Configure Form to:
   - Send email notification to support@affinitylabs.com
   - Save responses to SharePoint list
   - Auto-reply with ticket number

3. ezControl opens form URL with parameters:
   ```
   https://forms.office.com/r/abc123?DiagnosticID=20260201_143052_user@company.com
   ```

**Pros:**
- ✅ Free with Microsoft 365
- ✅ Professional ticket tracking
- ✅ Email notifications
- ✅ Easy to manage in SharePoint
- ✅ Users can attach screenshots
- ✅ Export to Excel for analytics

---

### **Option 2: Jira Service Desk Integration (Enterprise)**

**User Experience:**
1. Click "Report Issue"
2. Upload diagnostics
3. Opens Jira portal in browser
4. User creates ticket with pre-filled diagnostic link
5. Ticket routed to your support team

**Setup:**
- Requires Jira Service Desk license
- Create customer portal
- API integration for automatic ticket creation

**Pros:**
- ✅ Full ticketing system (SLA, assignment, status)
- ✅ Professional support workflow
- ✅ Knowledge base integration
- ✅ Customer portal

**Cons:**
- ⚠️ Paid service (~$20/agent/month)
- ⚠️ More complex setup

---

### **Option 3: Simple Web Form + Email (Easiest)**

**User Experience:**
1. Click "Report Issue"
2. Upload diagnostics to SharePoint
3. Opens simple web form (your website)
4. User fills: name, email, issue
5. Form sends email to support@affinitylabs.com with:
   - User info
   - Issue description
   - Link to diagnostic file in SharePoint

**Setup:**
1. Create simple HTML form on your website
2. Form submits to email via FormSpree/Netlify/SendGrid
3. ezControl opens: `https://affinitylabs.com/support?diagnostic_id=XYZ`

**Example Web Form:**
```html
<form action="https://formspree.io/f/support@affinitylabs.com" method="POST">
  <input type="text" name="name" placeholder="Your Name" required>
  <input type="email" name="email" placeholder="Your Email" required>
  <input type="hidden" name="diagnostic_id" value="PREFILLED_BY_APP">
  <textarea name="issue" placeholder="Describe the issue"></textarea>
  <select name="priority">
    <option>Low</option>
    <option>Medium</option>
    <option>High</option>
  </select>
  <button type="submit">Submit Ticket</button>
</form>
```

**Pros:**
- ✅ Very simple
- ✅ No monthly costs
- ✅ Works everywhere
- ✅ Easy to customize

---

### **Option 4: In-App Ticket Form (No Browser Required)**

**User Experience:**
1. Click "Report Issue"
2. Dialog opens IN ezControl:
   - Name/Email
   - Issue description
   - Priority dropdown
   - Screenshot button
3. Click Submit
4. App uploads bundle + sends email with ticket

**Implementation:**
- Qt dialog with form fields
- Capture screenshot with one click
- Bundle everything and upload
- Send formatted email to support

**Pros:**
- ✅ No browser needed
- ✅ Fastest for users
- ✅ Can include screenshot
- ✅ Professional experience

**Cons:**
- ⚠️ More development work

---

### **Option 5: QR Code for Mobile Submission (Hybrid)**

**User Experience:**
1. Click "Report Issue"
2. Dialog shows QR code
3. User scans with phone
4. Opens mobile-friendly form
5. Can add photos from phone
6. Submits ticket

**Use Case:**
- Lab environments where desktop can't upload
- Users want to add photos from phone
- Quick mobile reporting

---

## **Recommended Implementation**

I suggest **Microsoft Forms + SharePoint** if you have Microsoft 365, or **Simple Web Form** if you want free/simple.

### Workflow Diagram:
```
┌─────────────────────────────────────────────────────────┐
│  User clicks "Report Issue & Send Diagnostics"          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  1. ezControl collects diagnostic files                 │
│     • Spark transcripts                                 │
│     • Calibration logs                                  │
│     • Debug logs                                        │
│     • System info                                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. Create ZIP bundle with unique ID                    │
│     Format: 20260201_143052_user@company.com.zip        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. Upload to SharePoint/OneDrive                       │
│     URL: /diagnostics/20260201_143052_user@...zip       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  4. Open ticket form in browser                         │
│     https://forms.office.com/r/support                  │
│     ?diagnostic_id=20260201_143052                      │
│     ?user_email=user@company.com                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  5. User fills form:                                    │
│     • Name (pre-filled if known)                        │
│     • Email (pre-filled)                                │
│     • Issue description                                 │
│     • Priority                                          │
│     • Expected vs actual behavior                       │
│     • Steps to reproduce                                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  6. Form submits to:                                    │
│     • Email to support@affinitylabs.com                 │
│     • Saves to SharePoint list (ticket database)        │
│     • Auto-reply with ticket #SUP-2026-0001             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  7. User sees confirmation:                             │
│     "✅ Ticket #SUP-2026-0001 created!                   │
│      Diagnostic files uploaded.                         │
│      We'll respond within 24 hours."                    │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Step 1: Create Microsoft Form (10 minutes)

1. Go to [forms.office.com](https://forms.office.com)
2. Create new form: "ezControl Support Ticket"
3. Add fields:
   - **Name** (short answer, required)
   - **Email** (short answer, required)
   - **Company** (short answer)
   - **Diagnostic ID** (short answer, hidden, pre-filled by URL)
   - **Software Version** (short answer, pre-filled)
   - **Issue Priority** (choice: Low/Medium/High/Critical)
   - **Issue Summary** (short answer, required)
   - **Detailed Description** (long answer, required)
   - **Steps to Reproduce** (long answer)
   - **Expected Behavior** (long answer)
   - **Actual Behavior** (long answer)
   - **Screenshot** (file upload, optional)

4. Settings:
   - ✅ One response per person
   - ✅ Email notification to support@affinitylabs.com
   - ✅ Customize thank you message: "Ticket created! We'll respond within 24 hours."
   - ✅ Save responses to Excel in SharePoint

5. Get form URL (looks like):
   ```
   https://forms.office.com/r/AbC123XyZ
   ```

### Step 2: Update ezControl Code

See implementation in code below...

### Step 3: Create SharePoint List for Tracking (Optional)

1. Create list: "Support Tickets"
2. Columns:
   - Ticket ID (auto-increment)
   - User Name
   - User Email
   - Priority
   - Status (New/In Progress/Resolved)
   - Diagnostic File Link
   - Issue Description
   - Assigned To
   - Created Date
   - Resolved Date

3. Connect Microsoft Form to save to this list

### Step 4: Set Up Email Notifications

Configure Form to send email like:
```
Subject: [Support Ticket #SUP-2026-0001] Issue from user@company.com

Priority: High
User: John Doe (john@company.com)
Company: ACME Labs
Software Version: v2.5.1
Diagnostic ID: 20260201_143052

Issue Summary:
Calibration fails with error "detector not responding"

Detailed Description:
When attempting to calibrate the optical detector, the software
shows "detector not responding" error after 30 seconds...

Steps to Reproduce:
1. Connect hardware
2. Go to Settings > Calibrate
3. Click Start Calibration
4. Wait 30 seconds
5. Error appears

Diagnostic Files:
https://affinitylabs.sharepoint.com/diagnostics/20260201_143052_john@company.com.zip
```

---

## Alternative: Zendesk/Freshdesk Integration

If you want a professional ticketing system:

**Zendesk:**
- API endpoint: `https://affinitylabs.zendesk.com/api/v2/tickets`
- Create ticket via POST request
- Attach diagnostic bundle
- User gets ticket number via email

**Freshdesk:**
- Similar API
- Free tier available
- Email integration

---

## User Communication

Update button text:
- "Report Issue & Send Diagnostics" (clearer than "Send Diagnostic Files")

Add tooltip:
- "Upload diagnostic files and create support ticket. Your diagnostic bundle will be uploaded and a ticket form will open in your browser."

Success message:
- "✅ Diagnostic files uploaded!
   
   Opening ticket form in your browser...
   
   Please fill out the form to complete your support request."

---

## Testing Checklist

- [ ] Upload creates unique diagnostic ID
- [ ] SharePoint receives file correctly
- [ ] Form opens with pre-filled diagnostic ID
- [ ] Form submission sends email to support
- [ ] Email contains all ticket details + diagnostic link
- [ ] User receives confirmation email
- [ ] Ticket appears in SharePoint list

---

## Future Enhancements

1. **In-app ticket status checking**
   - Query SharePoint list to show "Your ticket #SUP-001 is In Progress"

2. **Automatic screenshot capture**
   - Button to capture current window state
   - Include in diagnostic bundle

3. **Live chat integration**
   - Add chat widget for immediate support

4. **Knowledge base search**
   - Before submitting ticket, search for similar issues
   - "Did you try: Calibration troubleshooting guide?"

5. **Diagnostic preview**
   - Show user what will be uploaded before sending

Would you like me to implement the Microsoft Forms integration or the in-app ticket form approach?
