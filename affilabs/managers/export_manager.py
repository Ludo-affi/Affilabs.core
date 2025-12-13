"""Export Manager - Handles data export functionality.

This manager encapsulates all export-related logic:
- Export configuration extraction from UI
- Export presets (Quick CSV, Analysis, Publication)
- Custom export configurations
- Export request generation
"""

from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..affilabs_core_ui import AffilabsMainWindow


class ExportManager:
    """Manages data export operations and export configurations."""

    def __init__(self, window: 'AffilabsMainWindow'):
        """Initialize the export manager.

        Args:
            window: Reference to the main window
        """
        self.window = window

    def on_export_data(self) -> None:
        """Handle export data button click - emit signal with export configuration."""
        export_config = self.get_export_config()
        self.window.export_requested.emit(export_config)

    def on_quick_csv_preset(self) -> None:
        """Quick CSV export preset - all data, all channels, CSV format."""
        config = self.get_export_config()
        config['preset'] = 'quick_csv'
        config['format'] = 'csv'
        config['include_metadata'] = False
        config['include_events'] = False
        self.window.export_requested.emit(config)

    def on_analysis_preset(self) -> None:
        """Analysis-ready preset - processed data, summary table, Excel format."""
        config = self.get_export_config()
        config['preset'] = 'analysis'
        config['format'] = 'excel'
        config['data_types'] = {'processed': True, 'summary': True, 'raw': False, 'cycles': False}
        config['include_metadata'] = True
        config['include_events'] = True
        self.window.export_requested.emit(config)

    def on_publication_preset(self) -> None:
        """Publication preset - high precision, metadata, Excel format."""
        config = self.get_export_config()
        config['preset'] = 'publication'
        config['format'] = 'excel'
        config['precision'] = 5
        config['include_metadata'] = True
        config['include_events'] = True
        self.window.export_requested.emit(config)

    def get_export_config(self) -> Dict:
        """Extract export configuration from UI controls.

        Returns:
            Dictionary with export settings
        """
        sidebar = self.window.sidebar

        # Get selected data types
        data_types = {
            'raw': (getattr(sidebar, 'raw_data_check', None) and
                   sidebar.raw_data_check.isChecked()
                   if hasattr(sidebar, 'raw_data_check') else True),
            'processed': (getattr(sidebar, 'processed_data_check', None) and
                         sidebar.processed_data_check.isChecked()
                         if hasattr(sidebar, 'processed_data_check') else True),
            'cycles': (getattr(sidebar, 'cycle_segments_check', None) and
                      sidebar.cycle_segments_check.isChecked()
                      if hasattr(sidebar, 'cycle_segments_check') else True),
            'summary': (getattr(sidebar, 'summary_table_check', None) and
                       sidebar.summary_table_check.isChecked()
                       if hasattr(sidebar, 'summary_table_check') else True),
        }

        # Get selected channels
        channels = self._get_selected_channels()

        # Get format
        format_type = self._get_export_format()

        # Get options
        include_metadata = (getattr(sidebar, 'metadata_check', None) and
                           sidebar.metadata_check.isChecked()
                           if hasattr(sidebar, 'metadata_check') else True)
        include_events = (getattr(sidebar, 'events_check', None) and
                         sidebar.events_check.isChecked()
                         if hasattr(sidebar, 'events_check') else False)

        # Get precision
        precision = self._get_precision()

        # Get timestamp format
        timestamp_format = self._get_timestamp_format()

        # Get filename and destination
        filename = (getattr(sidebar, 'export_filename_input', None) and
                   sidebar.export_filename_input.text()
                   if hasattr(sidebar, 'export_filename_input') else '')
        destination = (getattr(sidebar, 'export_dest_input', None) and
                      sidebar.export_dest_input.text()
                      if hasattr(sidebar, 'export_dest_input') else '')

        return {
            'data_types': data_types,
            'channels': channels,
            'format': format_type,
            'include_metadata': include_metadata,
            'include_events': include_events,
            'precision': precision,
            'timestamp_format': timestamp_format,
            'filename': filename,
            'destination': destination,
            'preset': None  # Will be set by preset buttons
        }

    def _get_selected_channels(self) -> List[str]:
        """Get list of selected channels from UI.

        Returns:
            List of channel names ('a', 'b', 'c', 'd')
        """
        sidebar = self.window.sidebar
        channels = []

        if hasattr(sidebar, 'export_channel_checkboxes'):
            channel_names = ['a', 'b', 'c', 'd']
            for i, cb in enumerate(sidebar.export_channel_checkboxes):
                if cb.isChecked():
                    channels.append(channel_names[i])
        else:
            channels = ['a', 'b', 'c', 'd']  # Default all channels

        return channels

    def _get_export_format(self) -> str:
        """Get selected export format from UI.

        Returns:
            Format string ('excel', 'csv', 'json', 'hdf5')
        """
        sidebar = self.window.sidebar
        format_type = 'excel'  # Default

        if hasattr(sidebar, 'excel_radio') and sidebar.excel_radio.isChecked():
            format_type = 'excel'
        elif hasattr(sidebar, 'csv_radio') and sidebar.csv_radio.isChecked():
            format_type = 'csv'
        elif hasattr(sidebar, 'json_radio') and sidebar.json_radio.isChecked():
            format_type = 'json'
        elif hasattr(sidebar, 'hdf5_radio') and sidebar.hdf5_radio.isChecked():
            format_type = 'hdf5'

        return format_type

    def _get_precision(self) -> int:
        """Get selected data precision from UI.

        Returns:
            Precision (number of decimal places)
        """
        sidebar = self.window.sidebar
        precision = 4  # Default

        if hasattr(sidebar, 'precision_combo'):
            precision = int(sidebar.precision_combo.currentText())

        return precision

    def _get_timestamp_format(self) -> str:
        """Get selected timestamp format from UI.

        Returns:
            Timestamp format ('relative', 'absolute', 'elapsed')
        """
        sidebar = self.window.sidebar
        timestamp_format = 'relative'  # Default

        if hasattr(sidebar, 'timestamp_combo'):
            timestamp_text = sidebar.timestamp_combo.currentText()
            if 'Absolute' in timestamp_text:
                timestamp_format = 'absolute'
            elif 'seconds' in timestamp_text:
                timestamp_format = 'elapsed'

        return timestamp_format
