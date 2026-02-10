"""Test the updated diagnostic bundle functionality (local save only)"""

import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("\n" + "="*60)
print("DIAGNOSTIC BUNDLE TEST - Local Save Only")
print("="*60 + "\n")

# Test the save_diagnostics_locally method
from affilabs.services.diagnostic_uploader import DiagnosticUploader

print("Creating diagnostic bundle...")
uploader = DiagnosticUploader()

success, message = uploader.save_diagnostics_locally()

print("\n" + "-"*60)
print(f"Success: {success}")
print(f"Message:\n{message}")
print("-"*60 + "\n")

if success:
    print("✅ Test passed!")
    print("\nThe button will now:")
    print("  1. Create a local diagnostic bundle")
    print("  2. Show the bundle path and size")
    print("  3. Open the folder containing the bundle")
    print("  4. Display instructions to email it to info@affiniteinstruments.com")
else:
    print("❌ Test failed!")
    print("Check the error message above")

print("\n" + "="*60 + "\n")
