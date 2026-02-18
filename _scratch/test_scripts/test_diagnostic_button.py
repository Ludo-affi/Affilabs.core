"""Test Diagnostic Upload Button Functionality

This script tests the diagnostic upload workflow to identify why the button doesn't work.
"""

import sys
import logging
from pathlib import Path

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("\n" + "="*60)
print("DIAGNOSTIC UPLOAD BUTTON TEST")
print("="*60 + "\n")

# Test 1: Import the uploader service
print("Test 1: Importing DiagnosticUploader...")
try:
    from affilabs.services.diagnostic_uploader import DiagnosticUploader
    print("✅ DiagnosticUploader imported successfully\n")
except Exception as e:
    print(f"❌ Failed to import DiagnosticUploader: {e}\n")
    sys.exit(1)

# Test 2: Check configuration
print("Test 2: Checking upload configuration...")
uploader = DiagnosticUploader()
print(f"  Upload Method: {uploader.UPLOAD_METHOD}")
print(f"  SharePoint URL: {uploader.SHAREPOINT_UPLOAD_URL}")
print(f"  HTTP URL: {uploader.HTTP_UPLOAD_URL}")
print(f"  Forms URL: {uploader.MICROSOFT_FORMS_URL}")
print(f"  Upload Enabled: {uploader.upload_enabled}")

# Check if URLs are still placeholder values
if "YourFormID" in uploader.MICROSOFT_FORMS_URL:
    print("\n⚠️  WARNING: MICROSOFT_FORMS_URL is still a placeholder!")
    print("   Update this with a real Microsoft Forms URL\n")

if "affinitylabs" in uploader.SHAREPOINT_UPLOAD_URL.lower():
    print("⚠️  WARNING: SHAREPOINT_UPLOAD_URL appears to be a placeholder!")
    print("   Update this with a real SharePoint upload link\n")

# Test 3: Test file collection
print("\nTest 3: Testing diagnostic file collection...")
try:
    files = uploader.collect_diagnostic_files()
    print(f"✅ Collected {len(files)} diagnostic files:")
    for file_type, file_path in files.items():
        exists = file_path.exists()
        size = file_path.stat().st_size if exists else 0
        status = "✓" if exists else "✗"
        print(f"  {status} {file_type}: {file_path} ({size:,} bytes)")
    print()
except Exception as e:
    print(f"❌ File collection failed: {e}\n")
    import traceback
    traceback.print_exc()

# Test 4: Test bundle creation (local only, no upload)
print("\nTest 4: Testing diagnostic bundle creation...")
try:
    bundle_path = uploader.create_diagnostic_bundle()
    print(f"✅ Bundle created successfully!")
    print(f"   Path: {bundle_path}")
    print(f"   Size: {bundle_path.stat().st_size:,} bytes")
    print()
except Exception as e:
    print(f"❌ Bundle creation failed: {e}\n")
    import traceback
    traceback.print_exc()

# Test 5: Test upload (expect failure due to fake URL)
print("\nTest 5: Testing upload to configured endpoint...")
print("⚠️  This will FAIL if SharePoint URL is not configured properly")
try:
    # Try to upload the bundle
    success = uploader.upload_diagnostics(bundle_path, user_email="test@example.com", notes="Test upload")

    if success:
        print("✅ Upload succeeded!")
    else:
        print("❌ Upload failed (expected if URL not configured)")
        print("   Check the logs above for the specific error\n")

except Exception as e:
    print(f"❌ Upload raised exception: {e}\n")
    import traceback
    traceback.print_exc()

# Test 6: Test the complete workflow
print("\nTest 6: Testing complete send_diagnostics workflow...")
try:
    success, message, diagnostic_id = uploader.send_diagnostics(
        user_email="test@example.com",
        notes="Test diagnostic submission"
    )

    print(f"  Success: {success}")
    print(f"  Message: {message}")
    print(f"  Diagnostic ID: {diagnostic_id}")
    print()

    if not success:
        print("❌ Workflow failed (expected if upload URL not configured)")
        print("   However, a bundle should still be created locally\n")

except Exception as e:
    print(f"❌ Workflow raised exception: {e}\n")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
print("\nDIAGNOSIS:")
print("The diagnostic upload button likely fails because:")
print("1. ⚠️  SharePoint upload URL is a placeholder, not a real endpoint")
print("2. ⚠️  Microsoft Forms URL is a placeholder")
print("\nFIX OPTIONS:")
print("\nOption A - Configure Real Upload Endpoints (Recommended):")
print("  1. Create a SharePoint upload link")
print("  2. Create a Microsoft Forms support ticket form")
print("  3. Update the URLs in diagnostic_uploader.py")
print("\nOption B - Disable Upload, Bundle Locally Only:")
print("  1. Modify the button to call save_diagnostics_locally() instead")
print("  2. Tell users to email the bundle file to support")
print("\nOption C - Use HTTP Endpoint:")
print("  1. Set up a web server to receive uploads")
print("  2. Change UPLOAD_METHOD to 'http'")
print("  3. Configure HTTP_UPLOAD_URL")

print("\n" + "="*60 + "\n")
