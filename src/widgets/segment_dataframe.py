"""Segment DataFrame Manager

Manages cycle segments using pandas DataFrame while maintaining compatibility
with the existing Segment object interface. Provides efficient operations for
segment storage, search, filtering, and analytics.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
import pandas as pd
import numpy as np
from copy import deepcopy

from utils.logger import logger

if TYPE_CHECKING:
    from widgets.datawindow import Segment


class SegmentDataFrame:
    """Manages cycle segments using pandas DataFrame.

    Provides list-like interface for backwards compatibility while leveraging
    pandas for efficient operations, searching, filtering, and analytics.

    The DataFrame schema:
    - seg_id: int - Unique segment identifier
    - name: str - Segment name (user-editable)
    - start: float - Start time in seconds
    - end: float - End time in seconds
    - ref_ch: str|None - Reference channel (a/b/c/d or None)
    - unit: str - Unit type (RU, nm, etc.)
    - shift_a: float - Channel A shift value
    - shift_b: float - Channel B shift value
    - shift_c: float - Channel C shift value
    - shift_d: float - Channel D shift value
    - cycle_type: str - Cycle type (Auto-read, Baseline, etc.)
    - cycle_time: int|None - Cycle time in minutes
    - note: str - User notes
    - error: str|None - Error message if segment is invalid
    - segment_obj: object - Reference to full Segment object with arrays
    """

    def __init__(self):
        """Initialize empty segment DataFrame."""
        self.df = pd.DataFrame(columns=[
            'seg_id', 'name', 'start', 'end', 'ref_ch', 'unit',
            'shift_a', 'shift_b', 'shift_c', 'shift_d',
            'cycle_type', 'cycle_time', 'note', 'error', 'segment_obj'
        ])

        # Set appropriate dtypes
        self.df = self.df.astype({
            'seg_id': 'int64',
            'name': 'object',
            'start': 'float64',
            'end': 'float64',
            'ref_ch': 'object',
            'unit': 'object',
            'shift_a': 'float64',
            'shift_b': 'float64',
            'shift_c': 'float64',
            'shift_d': 'float64',
            'cycle_type': 'object',
            'cycle_time': 'object',  # Can be None or int
            'note': 'object',
            'error': 'object',
            'segment_obj': 'object',
        })

    def _segment_to_dict(self, segment: Segment) -> dict:
        """Convert Segment object to dictionary for DataFrame row."""
        return {
            'seg_id': segment.seg_id,
            'name': segment.name,
            'start': segment.start,
            'end': segment.end,
            'ref_ch': segment.ref_ch,
            'unit': segment.unit,
            'shift_a': segment.shift['a'],
            'shift_b': segment.shift['b'],
            'shift_c': segment.shift['c'],
            'shift_d': segment.shift['d'],
            'cycle_type': segment.cycle_type,
            'cycle_time': segment.cycle_time,
            'note': segment.note,
            'error': segment.error,
            'segment_obj': segment,  # Store reference to full object
        }

    # List-like interface for backwards compatibility

    def append(self, segment: Segment) -> None:
        """Append a segment to the end."""
        # Use .loc for single row append - much faster than pd.concat()
        self.df.loc[len(self.df)] = self._segment_to_dict(segment)

    def insert(self, index: int, segment: Segment) -> None:
        """Insert a segment at specified index."""
        if index >= len(self.df):
            # Append at end using fast .loc method
            self.df.loc[len(self.df)] = self._segment_to_dict(segment)
        else:
            # Create single-row DataFrame only when needed for insertion
            new_row = pd.DataFrame([self._segment_to_dict(segment)])
            self.df = pd.concat([
                self.df.iloc[:index],
                new_row,
                self.df.iloc[index:]
            ], ignore_index=True)

    def pop(self, index: int = -1) -> Segment:
        """Remove and return segment at index (default last)."""
        if len(self.df) == 0:
            raise IndexError("pop from empty SegmentDataFrame")

        if index < 0:
            index = len(self.df) + index

        if index < 0 or index >= len(self.df):
            raise IndexError("pop index out of range")

        segment = self.df.iloc[index]['segment_obj']
        self.df = self.df.drop(index).reset_index(drop=True)
        return segment

    def clear(self) -> None:
        """Remove all segments."""
        self.df = self.df.iloc[0:0]  # Keep columns, remove rows

    def __len__(self) -> int:
        """Return number of segments."""
        return len(self.df)

    def __getitem__(self, index: int | slice) -> Segment | list[Segment]:
        """Get segment(s) by index."""
        if isinstance(index, slice):
            return [row['segment_obj'] for _, row in self.df.iloc[index].iterrows()]
        else:
            if index < 0:
                index = len(self.df) + index
            if index < 0 or index >= len(self.df):
                raise IndexError("list index out of range")
            return self.df.iloc[index]['segment_obj']

    def __setitem__(self, index: int, segment: Segment) -> None:
        """Set segment at index."""
        if index < 0:
            index = len(self.df) + index
        if index < 0 or index >= len(self.df):
            raise IndexError("list assignment index out of range")

        for key, value in self._segment_to_dict(segment).items():
            self.df.at[index, key] = value

    def __delitem__(self, index: int) -> None:
        """Delete segment at index."""
        if index < 0:
            index = len(self.df) + index
        if index < 0 or index >= len(self.df):
            raise IndexError("list index out of range")
        self.df = self.df.drop(index).reset_index(drop=True)

    def __iter__(self):
        """Iterate over segments."""
        for _, row in self.df.iterrows():
            yield row['segment_obj']

    # Pandas-specific enhancements

    def update_segment(self, index: int, segment: Segment) -> None:
        """Update segment at index (ensures DataFrame stays in sync)."""
        self[index] = segment

    def get_by_name(self, name: str) -> Optional[Segment]:
        """Find segment by name."""
        result = self.df[self.df['name'] == name]
        if len(result) > 0:
            return result.iloc[0]['segment_obj']
        return None

    def get_by_cycle_type(self, cycle_type: str) -> list[Segment]:
        """Get all segments of a specific cycle type."""
        result = self.df[self.df['cycle_type'] == cycle_type]
        return [row['segment_obj'] for _, row in result.iterrows()]

    def get_by_time_range(self, start: float, end: float) -> list[Segment]:
        """Get segments that overlap with time range."""
        result = self.df[
            (self.df['start'] <= end) & (self.df['end'] >= start)
        ]
        return [row['segment_obj'] for _, row in result.iterrows()]

    def get_invalid_segments(self) -> list[tuple[int, Segment]]:
        """Get all segments with errors (returns list of (index, segment))."""
        result = self.df[self.df['error'].notna()]
        return [(idx, row['segment_obj']) for idx, row in result.iterrows()]

    # Analytics methods

    def get_cycle_duration_stats(self) -> pd.DataFrame:
        """Calculate duration statistics by cycle type."""
        df_copy = self.df.copy()
        df_copy['duration'] = df_copy['end'] - df_copy['start']
        return df_copy.groupby('cycle_type')['duration'].describe()

    def get_cycle_type_counts(self) -> pd.Series:
        """Count number of cycles by type."""
        return self.df['cycle_type'].value_counts()

    def get_average_shift_by_cycle_type(self) -> pd.DataFrame:
        """Calculate average shift values by cycle type."""
        return self.df.groupby('cycle_type')[
            ['shift_a', 'shift_b', 'shift_c', 'shift_d']
        ].mean()

    def validate_all(self) -> dict:
        """Validate all segments and return summary."""
        validation = {
            'total': len(self.df),
            'valid': len(self.df[self.df['error'].isna()]),
            'invalid': len(self.df[self.df['error'].notna()]),
            'time_order_issues': 0,
            'missing_data': 0,
        }

        # Check time ordering
        time_issues = self.df[self.df['start'] >= self.df['end']]
        validation['time_order_issues'] = len(time_issues)

        # Check for missing cycle types
        missing = self.df[self.df['cycle_type'].isna() | (self.df['cycle_type'] == '')]
        validation['missing_data'] = len(missing)

        return validation

    # Export/Import methods

    def to_csv(self, filename: str, **kwargs) -> None:
        """Export segments to CSV file.

        Args:
            filename: Output file path
            **kwargs: Additional arguments passed to pandas.to_csv()
        """
        # Validate data before export
        if self.df.empty:
            logger.warning("No segments to export")
            return

        # Create export DataFrame with columns matching legacy format
        export_df = pd.DataFrame({
            'Name': self.df['name'],
            'StartTime': self.df['start'].round(2),
            'EndTime': self.df['end'].round(2),
            'ShiftA': self.df['shift_a'].round(3),
            'ShiftB': self.df['shift_b'].round(3),
            'ShiftC': self.df['shift_c'].round(3),
            'ShiftD': self.df['shift_d'].round(3),
            'Reference': self.df['ref_ch'].fillna('None'),
            'CycleType': self.df['cycle_type'],
            'UserNote': self.df['note'],
        })

        # Default to tab-separated if not specified
        if 'sep' not in kwargs:
            kwargs['sep'] = '\t'

        # Default to UTF-8 encoding if not specified
        if 'encoding' not in kwargs:
            kwargs['encoding'] = 'utf-8'

        export_df.to_csv(filename, index=False, **kwargs)
        logger.info(f"Exported {len(export_df)} segments to {filename}")

    @classmethod
    def from_csv(cls, filename: str, **kwargs) -> SegmentDataFrame:
        """Import segments from CSV file.

        Args:
            filename: Input file path
            **kwargs: Additional arguments passed to pandas.read_csv()

        Returns:
            SegmentDataFrame instance (Note: segment_obj will be None,
            caller must reconstruct Segment objects with add_data())
        """
        # Default to tab-separated if not specified
        if 'sep' not in kwargs:
            kwargs['sep'] = '\t'

        import_df = pd.read_csv(filename, **kwargs)

        # Create instance and populate
        instance = cls()

        # Map legacy column names to internal format
        instance.df = pd.DataFrame({
            'seg_id': range(len(import_df)),
            'name': import_df['Name'],
            'start': import_df['StartTime'].astype(float),
            'end': import_df['EndTime'].astype(float),
            'ref_ch': import_df['Reference'].replace('None', None),
            'unit': 'RU',  # Default
            'shift_a': import_df['ShiftA'].astype(float),
            'shift_b': import_df['ShiftB'].astype(float),
            'shift_c': import_df['ShiftC'].astype(float),
            'shift_d': import_df['ShiftD'].astype(float),
            'cycle_type': import_df.get('CycleType', 'Auto-read'),
            'cycle_time': None,  # Not stored in legacy format
            'note': import_df.get('UserNote', ''),
            'error': None,
            'segment_obj': None,  # Must be populated by caller
        })

        logger.info(f"Imported {len(instance.df)} segments from {filename}")
        return instance

    def to_dict_list(self) -> list[dict]:
        """Export to list of dictionaries (for JSON or other formats)."""
        return self.df.drop(columns=['segment_obj']).to_dict('records')

    def get_summary(self) -> str:
        """Get a human-readable summary of segments."""
        summary = [
            f"Total Segments: {len(self.df)}",
            f"Cycle Types: {', '.join(self.df['cycle_type'].unique())}",
            f"Time Range: {self.df['start'].min():.1f}s - {self.df['end'].max():.1f}s" if len(self.df) > 0 else "Time Range: N/A",
            f"Valid: {len(self.df[self.df['error'].isna()])}",
            f"Invalid: {len(self.df[self.df['error'].notna()])}",
        ]
        return "\n".join(summary)
