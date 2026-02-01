"""Diagnostic File Uploader Service

Collects and uploads diagnostic files to AffiLabs OEM database:
- Spark AI Q&A transcripts
- Calibration files
- Debug logs
- System information
"""

import json
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
from tinydb import TinyDB
from .cloud_database_sync import CloudDatabaseSync

logger = logging.getLogger(__name__)


class DiagnosticUploader:
    """Service for collecting and uploading diagnostic files to OEM."""
    
    # Upload configuration options:
    # Option 1: SharePoint/OneDrive upload link (recommended for large files)
    # Get this by: SharePoint -> Create upload link -> Copy link
    SHAREPOINT_UPLOAD_URL = "https://affinitylabs.sharepoint.com/:f:/g/diagnostics/upload"
    
    # Option 2: Direct HTTP endpoint (your custom server)
    HTTP_UPLOAD_URL = "https://api.affinitylabs.com/diagnostics/upload"
    
    # Option 3: OneDrive shared folder (requires Microsoft Graph API)
    ONEDRIVE_FOLDER_ID = None  # Set to OneDrive folder ID if using Graph API
    
    # Choose upload method: 'sharepoint', 'http', or 'onedrive'
    UPLOAD_METHOD = 'sharepoint'
    
    # Microsoft Forms ticket submission URL
    # Get this from forms.office.com after creating your support form
    MICROSOFT_FORMS_URL = "https://forms.office.com/r/YourFormID"
    
    def __init__(self):
        """Initialize diagnostic uploader."""
        self.upload_enabled = True  # Can be disabled via settings
        
    def collect_diagnostic_files(self) -> dict[str, Path]:
        """Collect all diagnostic files for upload.
        
        Returns:
            dict: Mapping of file type to file path
        """
        files = {}
        
        # 0. Sync Spark database to cloud first
        try:
            syncer = CloudDatabaseSync()
            sync_success, sync_msg = syncer.sync_to_cloud()
            if sync_success:
                logger.info(f"Cloud backup completed: {sync_msg}")
        except Exception as e:
            logger.warning(f"Cloud sync failed (will include local DB): {e}")
        
        # 1. Spark AI Transcript (local copy)
        spark_db = Path("spark_qa_history.json")
        if spark_db.exists():
            files['spark_transcript'] = spark_db
            logger.info(f"Found Spark transcript: {spark_db.stat().st_size} bytes")
        
        # 2. Calibration files
        calibration_log = Path("calibration_log.txt")
        if calibration_log.exists():
            files['calibration_log'] = calibration_log
            logger.info(f"Found calibration log: {calibration_log.stat().st_size} bytes")
        
        # Look for other calibration files
        for cal_file in Path(".").glob("*calibration*.json"):
            files[f'calibration_{cal_file.stem}'] = cal_file
        
        # 3. Debug logs (look for recent log files)
        log_dir = Path("logs")
        if log_dir.exists():
            # Get most recent log file
            log_files = sorted(log_dir.glob("ezcontrol_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
            if log_files:
                files['debug_log'] = log_files[0]
                logger.info(f"Found debug log: {log_files[0].stat().st_size} bytes")
        
        # Fallback: look for log files in current directory
        if 'debug_log' not in files:
            for log_file in Path(".").glob("*.log"):
                files['debug_log'] = log_file
                break
        
        return files
    
    def generate_system_info(self) -> dict:
        """Generate system information for diagnostics.
        
        Returns:
            dict: System information
        """
        import platform
        import sys
        
        try:
            from version import __version__
        except ImportError:
            __version__ = "unknown"
        
        info = {
            'timestamp': datetime.now().isoformat(),
            'software_version': __version__,
            'python_version': sys.version,
            'platform': platform.platform(),
            'machine': platform.machine(),
            'processor': platform.processor(),
        }
        
        # Add Spark statistics if available
        spark_db = Path("spark_qa_history.json")
        if spark_db.exists():
            try:
                db = TinyDB(str(spark_db))
                qa_table = db.table('questions_answers')
                info['spark_questions_total'] = len(qa_table.all())
                db.close()
            except Exception as e:
                logger.warning(f"Could not read Spark statistics: {e}")
        
        return info
    
    def create_diagnostic_bundle(self, output_path: Optional[str] = None) -> Path:
        """Create a ZIP bundle of all diagnostic files.
        
        Args:
            output_path: Custom output path. If None, generates timestamped name.
        
        Returns:
            Path: Path to created ZIP file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"ezcontrol_diagnostics_{timestamp}.zip"
        
        output_path = Path(output_path)
        
        # Collect files
        files = self.collect_diagnostic_files()
        system_info = self.generate_system_info()
        
        # Create ZIP bundle
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add system info as JSON
            zipf.writestr('system_info.json', json.dumps(system_info, indent=2))
            
            # Add all diagnostic files
            for file_type, file_path in files.items():
                if file_path.exists():
                    arcname = f"{file_type}{file_path.suffix}"
                    zipf.write(file_path, arcname=arcname)
                    logger.info(f"Added to bundle: {arcname}")
        
        logger.info(f"Diagnostic bundle created: {output_path} ({output_path.stat().st_size:,} bytes)")
        return output_path
    
    def upload_diagnostics(self, bundle_path: Path, user_email: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Upload diagnostic bundle to OEM (SharePoint/OneDrive/HTTP).
        
        Args:
            bundle_path: Path to diagnostic ZIP bundle
            user_email: Optional user contact email
            notes: Optional notes/description of issue
        
        Returns:
            bool: True if upload successful
        """
        if not self.upload_enabled:
            logger.warning("Diagnostic upload is disabled")
            return False
        
        try:
            if self.UPLOAD_METHOD == 'sharepoint':
                return self._upload_to_sharepoint(bundle_path, user_email, notes)
            elif self.UPLOAD_METHOD == 'onedrive':
                return self._upload_to_onedrive(bundle_path, user_email, notes)
            elif self.UPLOAD_METHOD == 'http':
                return self._upload_via_http(bundle_path, user_email, notes)
            else:
                logger.error(f"Unknown upload method: {self.UPLOAD_METHOD}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected error during upload: {e}")
            return False
    
    def _upload_to_sharepoint(self, bundle_path: Path, user_email: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Upload to SharePoint using upload link.
        
        Args:
            bundle_path: Path to diagnostic ZIP bundle
            user_email: Optional user contact email
            notes: Optional notes
        
        Returns:
            bool: True if upload successful
        """
        try:
            logger.info(f"Uploading to SharePoint: {self.SHAREPOINT_UPLOAD_URL}")
            
            # Add metadata to filename for tracking
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{timestamp}_{user_email or 'anonymous'}_{bundle_path.name}"
            
            with open(bundle_path, 'rb') as f:
                files = {'file': (new_filename, f, 'application/zip')}
                
                # SharePoint upload links accept form data
                data = {
                    'user_email': user_email or '',
                    'notes': notes or '',
                    'timestamp': timestamp,
                }
                
                response = requests.post(
                    self.SHAREPOINT_UPLOAD_URL,
                    files=files,
                    data=data,
                    timeout=120,  # 2 minutes for large files
                )
                
                if response.status_code in [200, 201, 204]:
                    logger.info("✅ Uploaded to SharePoint successfully")
                    return True
                else:
                    logger.error(f"❌ SharePoint upload failed: {response.status_code} - {response.text}")
                    return False
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during SharePoint upload: {e}")
            return False
    
    def _upload_to_onedrive(self, bundle_path: Path, user_email: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Upload to OneDrive using Microsoft Graph API.
        
        Requires: Microsoft Graph API credentials and folder ID
        
        Args:
            bundle_path: Path to diagnostic ZIP bundle
            user_email: Optional user contact email
            notes: Optional notes
        
        Returns:
            bool: True if upload successful
        """
        if not self.ONEDRIVE_FOLDER_ID:
            logger.error("OneDrive folder ID not configured")
            return False
        
        try:
            # Microsoft Graph API endpoint
            upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{self.ONEDRIVE_FOLDER_ID}:/{bundle_path.name}:/content"
            
            # This requires OAuth token - simplified example
            # In production, you'd need proper authentication
            headers = {
                'Authorization': 'Bearer YOUR_OAUTH_TOKEN',  # TODO: Implement OAuth
                'Content-Type': 'application/zip',
            }
            
            with open(bundle_path, 'rb') as f:
                response = requests.put(
                    upload_url,
                    headers=headers,
                    data=f,
                    timeout=120,
                )
            
            if response.status_code in [200, 201]:
                logger.info("✅ Uploaded to OneDrive successfully")
                return True
            else:
                logger.error(f"❌ OneDrive upload failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ OneDrive upload error: {e}")
            return False
    
    def _upload_via_http(self, bundle_path: Path, user_email: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Upload via direct HTTP POST to custom server.
        
        Args:
            bundle_path: Path to diagnostic ZIP bundle
            user_email: Optional user contact email
            notes: Optional notes
        
        Returns:
            bool: True if upload successful
        """
        try:
            with open(bundle_path, 'rb') as f:
                files = {'diagnostic_bundle': (bundle_path.name, f, 'application/zip')}
                
                data = {
                    'timestamp': datetime.now().isoformat(),
                    'user_email': user_email or '',
                    'notes': notes or '',
                }
                
                logger.info(f"Uploading to HTTP endpoint: {self.HTTP_UPLOAD_URL}...")
                response = requests.post(
                    self.HTTP_UPLOAD_URL,
                    files=files,
                    data=data,
                    timeout=60,
                )
                
                if response.status_code == 200:
                    logger.info("✅ HTTP upload successful")
                    return True
                else:
                    logger.error(f"❌ HTTP upload failed: {response.status_code} - {response.text}")
                    return False
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error during HTTP upload: {e}")
            return False
    
    def send_diagnostics(self, user_email: Optional[str] = None, notes: Optional[str] = None) -> tuple[bool, str, str]:
        """Complete workflow: collect, bundle, upload, and open ticket form.
        
        Args:
            user_email: Optional user contact email
            notes: Optional notes/description
        
        Returns:
            tuple: (success, message, diagnostic_id)
        """
        try:
            # Create bundle
            logger.info("Creating diagnostic bundle...")
            bundle_path = self.create_diagnostic_bundle()
            
            # Extract diagnostic ID from filename
            diagnostic_id = bundle_path.stem  # e.g., "ezcontrol_diagnostics_20260201_143052"
            
            # Upload
            success = self.upload_diagnostics(bundle_path, user_email, notes)
            
            if success:
                message = f"✅ Diagnostic files uploaded!\n\nDiagnostic ID: {diagnostic_id}\n\nOpening ticket form..."
            else:
                message = f"⚠️ Upload failed, but bundle saved locally:\n{bundle_path}\n\nYou can submit it manually."
            
            return (success, message, diagnostic_id)
            
        except Exception as e:
            logger.error(f"Error in diagnostic workflow: {e}", exc_info=True)
            return (False, f"❌ Error: {str(e)}", "")
    
    def open_ticket_form(self, diagnostic_id: str, user_email: Optional[str] = None, software_version: str = "unknown"):
        """Open Microsoft Forms ticket submission in browser.
        
        Args:
            diagnostic_id: Unique ID of uploaded diagnostic bundle
            user_email: User's email to pre-fill
            software_version: Software version to pre-fill
        """
        import webbrowser
        import urllib.parse
        
        # Build URL with pre-filled parameters
        params = {
            'diagnostic_id': diagnostic_id,
            'user_email': user_email or '',
            'software_version': software_version,
        }
        
        # Microsoft Forms accepts URL parameters for pre-filling
        # Format: https://forms.office.com/r/FormID?param1=value1&param2=value2
        form_url = self.MICROSOFT_FORMS_URL
        if '?' in form_url:
            form_url += '&'
        else:
            form_url += '?'
        
        form_url += urllib.parse.urlencode(params)
        
        logger.info(f"Opening ticket form: {form_url}")
        webbrowser.open(form_url)
    
    def send_diagnostics_and_open_form(self, user_email: Optional[str] = None, notes: Optional[str] = None) -> tuple[bool, str]:
        """Complete workflow: upload diagnostics AND open Microsoft Forms.
        
        Args:
            user_email: Optional user contact email
            notes: Optional notes
        
        Returns:
            tuple: (success, message)
        """
        # Upload diagnostics
        success, message, diagnostic_id = self.send_diagnostics(user_email, notes)
        
        if success and diagnostic_id:
            # Open ticket form in browser
            try:
                from version import __version__
                software_version = __version__
            except ImportError:
                software_version = "unknown"
            
            self.open_ticket_form(diagnostic_id, user_email, software_version)
        
        return (success, message)
    
    def save_diagnostics_locally(self) -> tuple[bool, str]:
        """Create diagnostic bundle and save locally (no upload).
        
        Returns:
            tuple: (success, message)
        """
        try:
            bundle_path = self.create_diagnostic_bundle()
            message = f"✅ Diagnostic bundle created:\n{bundle_path}\n\nSize: {bundle_path.stat().st_size:,} bytes"
            return (True, message)
        except Exception as e:
            logger.error(f"Error creating diagnostic bundle: {e}", exc_info=True)
            return (False, f"❌ Error: {str(e)}")
