"""Experiment Folder Manager - GLP/GMP-Compliant File Organization.

Creates and manages hierarchical experiment folders following industry standards:
- One folder per experiment session
- Organized subfolders (Raw_Data, Analysis, Figures, QC_Reports, Method)
- Metadata tracking (user, device, date, sensor)
- Audit trail for regulatory compliance

Author: AffiLabs Development Team
Version: 2.0
"""

from pathlib import Path
from datetime import datetime
import json
from typing import Dict, Optional
from affilabs.utils.logger import logger


class ExperimentFolderManager:
    """Manages experiment folder structure following GLP/GMP standards."""

    def __init__(self, base_directory: Optional[Path] = None):
        """Initialize the experiment folder manager.

        Args:
            base_directory: Root directory for all experiments.
                          Defaults to ~/Documents/Affilabs_Data/
        """
        if base_directory is None:
            from affilabs.utils.resource_path import get_writable_data_path
            self.base_directory = get_writable_data_path("data/experiments")
        else:
            self.base_directory = Path(base_directory)

        # Ensure base directory exists
        self.base_directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"📁 Experiment base directory: {self.base_directory}")

    def create_experiment_folder(
        self,
        experiment_name: str,
        user_name: str,
        device_id: str,
        sensor_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Path:
        """Create a new experiment folder with standard subdirectories.

        Args:
            experiment_name: Name of the experiment (e.g., "Antibody_Screening")
            user_name: Name of the operator
            device_id: Device serial number
            sensor_type: Sensor chip type (optional)
            description: Experiment description (optional)

        Returns:
            Path to the created experiment folder

        Folder structure created:
            YYYY-MM-DD_ExperimentName_User/
            ├── Raw_Data/
            ├── Analysis/
            ├── Figures/
            ├── Method/
            ├── QC_Reports/
            └── experiment_metadata.json
        """
        # Create folder name: YYYY-MM-DD_ExperimentName_User
        date_str = datetime.now().strftime("%Y-%m-%d")
        # Clean names (replace spaces with underscores, remove special chars)
        clean_exp_name = self._sanitize_name(experiment_name)
        clean_user = self._sanitize_name(user_name)

        folder_name = f"{date_str}_{clean_exp_name}_{clean_user}"
        experiment_folder = self.base_directory / folder_name

        # Create main folder
        experiment_folder.mkdir(parents=True, exist_ok=True)

        # Create standard subdirectories
        subdirs = {
            "Raw_Data": "Raw timestamped sensor data",
            "Analysis": "Processed analysis results and annotated cycle tables",
            "Figures": "Exported graphs and visualizations",
            "Method": "Method files and experimental protocols",
            "QC_Reports": "Quality control and validation reports",
        }

        for subdir, description_text in subdirs.items():
            subdir_path = experiment_folder / subdir
            subdir_path.mkdir(exist_ok=True)

            # Create README in each subfolder
            readme_path = subdir_path / "README.txt"
            if not readme_path.exists():
                readme_path.write_text(
                    f"{subdir}\n"
                    f"{'=' * len(subdir)}\n\n"
                    f"{description_text}\n\n"
                    f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )

        # Create experiment metadata file
        metadata = {
            "experiment_info": {
                "name": experiment_name,
                "folder_name": folder_name,
                "created_date": datetime.now().isoformat(),
                "description": description or "",
            },
            "operator": {
                "name": user_name,
            },
            "instrument": {
                "device_id": device_id,
                "sensor_type": sensor_type or "Not specified",
            },
            "software": {
                "version": "2.0",
                "name": "Affilabs-Core",
            },
            "files": {
                "raw_data": [],
                "analysis": [],
                "figures": [],
                "methods": [],
                "qc_reports": [],
            },
            "audit_trail": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "action": "Experiment folder created",
                    "user": user_name,
                }
            ]
        }

        metadata_path = experiment_folder / "experiment_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, indent=2, fp=f)

        logger.info(f"✓ Created experiment folder: {folder_name}")
        return experiment_folder

    def get_subfolder_path(self, experiment_folder: Path, subfolder: str) -> Path:
        """Get path to a specific subfolder within experiment folder.

        Args:
            experiment_folder: Path to experiment folder
            subfolder: Name of subfolder (Raw_Data, Analysis, Figures, Method, QC_Reports)

        Returns:
            Path to the subfolder
        """
        valid_subfolders = ["Raw_Data", "Analysis", "Figures", "Method", "QC_Reports"]
        if subfolder not in valid_subfolders:
            raise ValueError(f"Invalid subfolder: {subfolder}. Must be one of {valid_subfolders}")

        subfolder_path = experiment_folder / subfolder
        subfolder_path.mkdir(exist_ok=True)  # Ensure it exists
        return subfolder_path

    def register_file(
        self,
        experiment_folder: Path,
        file_path: Path,
        file_type: str,
        description: Optional[str] = None,
    ) -> None:
        """Register a file in the experiment metadata (audit trail).

        Args:
            experiment_folder: Path to experiment folder
            file_path: Path to the file (should be within experiment folder)
            file_type: Type of file (raw_data, analysis, figures, methods, qc_reports)
            description: Optional description of the file
        """
        metadata_path = experiment_folder / "experiment_metadata.json"

        if not metadata_path.exists():
            logger.warning(f"Metadata file not found: {metadata_path}")
            return

        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Add file to registry
        file_entry = {
            "filename": file_path.name,
            "full_path": str(file_path),
            "created": datetime.now().isoformat(),
            "description": description or "",
            "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
        }

        if file_type in metadata["files"]:
            metadata["files"][file_type].append(file_entry)

        # Add audit trail entry
        metadata["audit_trail"].append({
            "timestamp": datetime.now().isoformat(),
            "action": f"File added: {file_type}",
            "filename": file_path.name,
            "user": metadata["operator"]["name"],
        })

        # Save updated metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, indent=2, fp=f)

        logger.debug(f"Registered file in metadata: {file_path.name} ({file_type})")

    def get_current_experiment_folder(self) -> Optional[Path]:
        """Get the most recently created experiment folder.

        Returns:
            Path to most recent experiment folder, or None if none exist
        """
        experiment_folders = sorted(
            [f for f in self.base_directory.iterdir() if f.is_dir()],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        if experiment_folders:
            return experiment_folders[0]
        return None

    def list_experiments(self) -> list[Dict]:
        """List all experiment folders with their metadata.

        Returns:
            List of dicts containing experiment info
        """
        experiments = []

        for folder in sorted(self.base_directory.iterdir(), reverse=True):
            if not folder.is_dir():
                continue

            metadata_path = folder / "experiment_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    experiments.append({
                        "folder_path": str(folder),
                        "folder_name": folder.name,
                        "name": metadata["experiment_info"]["name"],
                        "created": metadata["experiment_info"]["created_date"],
                        "user": metadata["operator"]["name"],
                        "device": metadata["instrument"]["device_id"],
                    })
            else:
                # Legacy folder without metadata
                experiments.append({
                    "folder_path": str(folder),
                    "folder_name": folder.name,
                    "name": folder.name,
                    "created": datetime.fromtimestamp(folder.stat().st_ctime).isoformat(),
                    "user": "Unknown",
                    "device": "Unknown",
                })

        return experiments

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in folder/file names.

        Args:
            name: Name to sanitize

        Returns:
            Sanitized name (spaces -> underscores, special chars removed)
        """
        # Replace spaces with underscores
        sanitized = name.replace(' ', '_')
        # Remove special characters (keep alphanumeric, underscore, hyphen)
        sanitized = ''.join(c for c in sanitized if c.isalnum() or c in '_-')
        return sanitized

    def generate_filename(
        self,
        prefix: str,
        extension: str,
        include_timestamp: bool = True,
    ) -> str:
        """Generate a standardized filename.

        Args:
            prefix: Filename prefix (e.g., "Raw", "Analysis", "Sensorgram")
            extension: File extension without dot (e.g., "xlsx", "png")
            include_timestamp: Whether to include timestamp in filename

        Returns:
            Generated filename (e.g., "Raw_20260206_143052.xlsx")
        """
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{prefix}_{timestamp}.{extension}"
        else:
            return f"{prefix}.{extension}"
