"""Cloud Database Sync for Spark AI Q&A History

Syncs local TinyDB database to cloud storage for backup and analysis:
- Azure Cosmos DB (recommended for Microsoft 365 users)
- Google Firestore
- OneDrive/SharePoint file sync (simplest)
"""

import logging
from datetime import datetime
from pathlib import Path
from tinydb import TinyDB

logger = logging.getLogger(__name__)


class CloudDatabaseSync:
    """Sync local Spark Q&A database to cloud storage."""

    # Configuration - Choose your sync method
    SYNC_METHOD = 'onedrive'  # Options: 'onedrive', 'azure_cosmos', 'firestore'

    # OneDrive/SharePoint settings (simplest - local folder sync)
    # Files saved here will auto-sync to SharePoint via OneDrive
    ONEDRIVE_LOCAL_FOLDER = Path(r"C:\Users\lucia\OneDrive\affiniteam_eng\ezControl_Diagnostics")

    # Azure Cosmos DB settings (enterprise)
    COSMOS_ENDPOINT = "https://your-cosmos-account.documents.azure.com:443/"
    COSMOS_KEY = None  # Set via environment variable
    COSMOS_DATABASE = "ezcontrol"
    COSMOS_CONTAINER = "spark_qa"

    # Firestore settings (Google Cloud)
    FIRESTORE_PROJECT_ID = None

    def __init__(self, local_db_path: str = "spark_qa_history.json"):
        """Initialize cloud sync.
        
        Args:
            local_db_path: Path to local TinyDB database
        """
        self.local_db_path = Path(local_db_path)
        self.last_sync_time = None

    def sync_to_cloud(self, force: bool = False) -> tuple[bool, str]:
        """Sync local database to cloud storage.
        
        Args:
            force: Force sync even if no changes detected
            
        Returns:
            tuple: (success, message)
        """
        if not self.local_db_path.exists():
            return (False, "No local database found")

        try:
            if self.SYNC_METHOD == 'onedrive':
                return self._sync_to_onedrive(force)
            elif self.SYNC_METHOD == 'azure_cosmos':
                return self._sync_to_cosmos(force)
            elif self.SYNC_METHOD == 'firestore':
                return self._sync_to_firestore(force)
            else:
                return (False, f"Unknown sync method: {self.SYNC_METHOD}")

        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            return (False, f"Sync error: {str(e)}")

    def _sync_to_onedrive(self, force: bool = False) -> tuple[bool, str]:
        """Sync to OneDrive/SharePoint (local folder sync - simplest).
        
        Saves files to local OneDrive folder which auto-syncs to SharePoint.
        
        Args:
            force: Force upload even if unchanged
            
        Returns:
            tuple: (success, message)
        """
        try:
            # Create OneDrive folder if it doesn't exist
            self.ONEDRIVE_LOCAL_FOLDER.mkdir(parents=True, exist_ok=True)

            # Generate timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"spark_qa_backup_{timestamp}.json"
            backup_path = self.ONEDRIVE_LOCAL_FOLDER / backup_filename

            # Copy local database to OneDrive folder
            with open(self.local_db_path, 'r', encoding='utf-8') as f:
                db_content = f.read()

            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(db_content)

            self.last_sync_time = datetime.now()
            logger.info(f"✅ Saved to OneDrive: {backup_filename}")
            return (True, f"Backed up to OneDrive: {backup_filename}")

        except Exception as e:
            logger.error(f"OneDrive sync error: {e}")
            return (False, f"OneDrive error: {str(e)}")

    def _upload_file_to_onedrive(self, file_path: Path, remote_filename: str, content: bytes = None) -> tuple[bool, str]:
        """Upload/copy a file to OneDrive folder (auto-syncs to SharePoint).
        
        Args:
            file_path: Path to local file
            remote_filename: Name to use in OneDrive folder
            content: Optional pre-loaded content (otherwise reads from file_path)
        
        Returns:
            tuple: (success, message)
        """
        try:
            # Create OneDrive folder if it doesn't exist
            self.ONEDRIVE_LOCAL_FOLDER.mkdir(parents=True, exist_ok=True)

            backup_path = self.ONEDRIVE_LOCAL_FOLDER / remote_filename
            logger.info(f"Saving to OneDrive: {remote_filename}")

            # Read content if not provided
            if content is None:
                with open(file_path, 'rb') as f:
                    content = f.read()

            # Save to OneDrive folder (will auto-sync)
            with open(backup_path, 'wb') as f:
                f.write(content)

            logger.info(f"✅ Saved to OneDrive: {remote_filename}")
            return (True, f"Uploaded: {remote_filename}")

        except Exception as e:
            logger.error(f"Upload error: {e}")
            return (False, f"Error: {str(e)}")

    def _sync_to_cosmos(self, force: bool = False) -> tuple[bool, str]:
        """Sync to Azure Cosmos DB (enterprise solution).
        
        Uploads each Q&A entry as a document.
        
        Args:
            force: Force sync all records
            
        Returns:
            tuple: (success, message)
        """
        try:
            from azure.cosmos import CosmosClient

            if not self.COSMOS_KEY:
                return (False, "Cosmos DB key not configured")

            # Connect to Cosmos DB
            client = CosmosClient(self.COSMOS_ENDPOINT, self.COSMOS_KEY)
            database = client.get_database_client(self.COSMOS_DATABASE)
            container = database.get_container_client(self.COSMOS_CONTAINER)

            # Read local database
            db = TinyDB(str(self.local_db_path))
            qa_table = db.table('questions_answers')
            all_entries = qa_table.all()

            # Sync each entry
            synced_count = 0
            for entry in all_entries:
                # Add unique ID for Cosmos
                entry['id'] = f"spark_qa_{entry.get('timestamp', '')}_{synced_count}"

                # Upsert to Cosmos
                container.upsert_item(entry)
                synced_count += 1

            db.close()

            self.last_sync_time = datetime.now()
            logger.info(f"✅ Synced {synced_count} entries to Cosmos DB")
            return (True, f"Synced {synced_count} Q&A entries to Azure Cosmos DB")

        except ImportError:
            return (False, "azure-cosmos package not installed. Run: pip install azure-cosmos")
        except Exception as e:
            logger.error(f"Cosmos DB sync error: {e}")
            return (False, f"Cosmos DB error: {str(e)}")

    def _sync_to_firestore(self, force: bool = False) -> tuple[bool, str]:
        """Sync to Google Firestore.
        
        Args:
            force: Force sync all records
            
        Returns:
            tuple: (success, message)
        """
        try:
            from google.cloud import firestore

            if not self.FIRESTORE_PROJECT_ID:
                return (False, "Firestore project ID not configured")

            # Connect to Firestore
            db_client = firestore.Client(project=self.FIRESTORE_PROJECT_ID)
            collection = db_client.collection('spark_qa')

            # Read local database
            db = TinyDB(str(self.local_db_path))
            qa_table = db.table('questions_answers')
            all_entries = qa_table.all()

            # Sync each entry
            synced_count = 0
            for entry in all_entries:
                doc_id = f"qa_{entry.get('timestamp', '')}_{synced_count}"
                collection.document(doc_id).set(entry)
                synced_count += 1

            db.close()

            self.last_sync_time = datetime.now()
            logger.info(f"✅ Synced {synced_count} entries to Firestore")
            return (True, f"Synced {synced_count} Q&A entries to Firestore")

        except ImportError:
            return (False, "google-cloud-firestore package not installed")
        except Exception as e:
            logger.error(f"Firestore sync error: {e}")
            return (False, f"Firestore error: {str(e)}")

    def auto_sync_on_new_entry(self):
        """Set up automatic sync whenever new Q&A is added.
        
        Call this during app initialization to enable auto-sync.
        """
        # This would watch the database file for changes
        # For now, we'll sync manually or on schedule
        pass

    def get_sync_status(self) -> dict:
        """Get current sync status.
        
        Returns:
            dict: Sync status information
        """
        local_size = self.local_db_path.stat().st_size if self.local_db_path.exists() else 0

        db = TinyDB(str(self.local_db_path))
        qa_table = db.table('questions_answers')
        entry_count = len(qa_table.all())
        db.close()

        return {
            'local_db_exists': self.local_db_path.exists(),
            'local_db_size': local_size,
            'entry_count': entry_count,
            'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'sync_method': self.SYNC_METHOD,
        }


# Automatic sync scheduler (optional)
class AutoSyncScheduler:
    """Schedule automatic cloud syncs."""

    def __init__(self, sync_interval_minutes: int = 60):
        """Initialize auto-sync scheduler.
        
        Args:
            sync_interval_minutes: How often to sync (default: hourly)
        """
        self.sync_interval = sync_interval_minutes
        self.syncer = CloudDatabaseSync()
        self.timer = None

    def start(self):
        """Start automatic sync schedule."""
        from PySide6.QtCore import QTimer

        self.timer = QTimer()
        self.timer.timeout.connect(self._sync_callback)
        self.timer.start(self.sync_interval * 60 * 1000)  # Convert to milliseconds

        logger.info(f"Auto-sync started: every {self.sync_interval} minutes")

    def stop(self):
        """Stop automatic sync."""
        if self.timer:
            self.timer.stop()
            logger.info("Auto-sync stopped")

    def _sync_callback(self):
        """Callback for timer - performs sync."""
        success, message = self.syncer.sync_to_cloud()
        if success:
            logger.info(f"Auto-sync completed: {message}")
        else:
            logger.warning(f"Auto-sync failed: {message}")

    def sync_now(self) -> tuple[bool, str]:
        """Trigger immediate sync.
        
        Returns:
            tuple: (success, message)
        """
        return self.syncer.sync_to_cloud(force=True)

def sync_all_databases() -> tuple[bool, str]:
    """Sync all ezControl databases to cloud.
    
    Uploads:
    - Spark AI Q&A history
    - Device history (ML training)
    - Latest QC reports
    - Methods database
    - User profiles
    
    Returns:
        tuple: (success, message with details)
    """
    from pathlib import Path

    syncer = CloudDatabaseSync()
    results = []

    # 1. Spark AI Q&A
    spark_db = Path("spark_qa_history.json")
    if spark_db.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success, msg = syncer._upload_file_to_onedrive(
                spark_db,
                f"spark_qa_backup_{timestamp}.json"
            )
            results.append(f"Spark AI: {'✅' if success else '❌'}")
        except Exception as e:
            results.append(f"Spark AI: ❌ {e}")

    # 2. Device History (SQLite - save as .sqlite to avoid Windows file association issues)
    device_db = Path("tools/ml_training/device_history.db")
    if device_db.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success, msg = syncer._upload_file_to_onedrive(
                device_db,
                f"device_history_{timestamp}.sqlite"
            )
            results.append(f"Device History: {'✅' if success else '❌'}")
        except Exception as e:
            results.append(f"Device History: ❌ {e}")

    # 3. Latest QC Report
    qc_reports = list(Path("calibration_results").glob("qc_report_*.json"))
    if qc_reports:
        latest_qc = max(qc_reports, key=lambda p: p.stat().st_mtime)
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success, msg = syncer._upload_file_to_onedrive(
                latest_qc,
                f"qc_report_{timestamp}.json"
            )
            results.append(f"QC Report: {'✅' if success else '❌'}")
        except Exception as e:
            results.append(f"QC Report: ❌ {e}")

    # 4. Methods Database (TinyDB)
    methods_db = Path("methods_db.json")  # TinyDB file
    if methods_db.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success, msg = syncer._upload_file_to_onedrive(
                methods_db,
                f"methods_db_{timestamp}.json"
            )
            results.append(f"Methods DB: {'✅' if success else '❌'}")
        except Exception as e:
            results.append(f"Methods DB: ❌ {e}")

    # 5. User Profiles
    user_profiles = Path("user_profiles.json")
    if user_profiles.exists():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            success, msg = syncer._upload_file_to_onedrive(
                user_profiles,
                f"user_profiles_{timestamp}.json"
            )
            results.append(f"User Profiles: {'✅' if success else '❌'}")
        except Exception as e:
            results.append(f"User Profiles: ❌ {e}")

    # Summary
    success_count = sum(1 for r in results if '✅' in r)
    total_count = len(results)

    if success_count == total_count:
        return (True, f"✅ All databases synced ({success_count}/{total_count})\n" + "\n".join(results))
    elif success_count > 0:
        return (True, f"⚠️ Partial sync ({success_count}/{total_count})\n" + "\n".join(results))
    else:
        return (False, f"❌ Sync failed (0/{total_count})\n" + "\n".join(results))
