"""Test Cloud Database Sync for All Databases

Tests syncing all 5 databases to SharePoint:
1. Spark AI Q&A (spark_qa_history.json)
2. Device History (tools/ml_training/device_history.db)
3. QC Reports (calibration_results/*.json)
4. Methods Database (methods_db.json)
5. User Profiles (user_profiles.json)
"""

from affilabs.services.cloud_database_sync import sync_all_databases
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    print("=" * 70)
    print(" TESTING ALL-DATABASE SYNC TO SHAREPOINT")
    print("=" * 70)
    print()
    print("SharePoint folder:")
    print("https://affiniteinstrumentscom.sharepoint.com/:f:/s/affiniteam_eng/...")
    print()
    print("Syncing all databases...")
    print("-" * 70)

    # Sync all databases
    success, message = sync_all_databases()

    print()
    print("=" * 70)
    print(f" RESULT: {'SUCCESS' if success else 'FAILED'}")
    print("=" * 70)
    print()
    print(message)
    print()

    if success:
        print("✅ All databases have been backed up to SharePoint!")
        print()
        print("Files uploaded:")
        print("  - spark_qa_backup_TIMESTAMP.json")
        print("  - device_history_TIMESTAMP.db")
        print("  - qc_report_TIMESTAMP.json")
        print("  - methods_db_TIMESTAMP.json")
        print("  - user_profiles_TIMESTAMP.json")
        print()
        print("Next steps:")
        print("  1. Check SharePoint folder to verify files uploaded")
        print("  2. Create Microsoft Forms for ticket system")
        print("  3. Test complete diagnostic workflow")
    else:
        print("❌ Some databases failed to sync")
        print()
        print("Check the error messages above for details")
        print("Common issues:")
        print("  - SharePoint permissions (need upload access)")
        print("  - Network connectivity")
        print("  - Database files not found")

    print()

if __name__ == '__main__':
    main()
