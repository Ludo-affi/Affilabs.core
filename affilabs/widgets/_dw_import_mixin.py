"""Import functionality mixin for DataWindow.

Methods (2 total):
    - import_raw_data
    - import_table
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

import numpy as np
from PySide6.QtWidgets import QFileDialog
from scipy.signal import medfilt

from affilabs.utils.logger import logger
from affilabs.widgets._dw_models import Segment
from affilabs.widgets.message import show_message
from affilabs.widgets.segment_dataframe import SegmentDataFrame
from settings import CH_LIST, MED_FILT_WIN


class ImportMixin:
    """Raw data and table import methods for DataWindow."""

    def import_raw_data(self: Self) -> None:
        """Import raw data."""
        proceed = True
        if len(self.data["lambda_times"]["a"]) > 0:
            if not show_message(
                msg_type="Warning",
                msg="Import will overwrite data & erase Cycle Data Table!"
                "\nProceed with new import?",
                yes_no=True,
            ):
                proceed = False
            else:
                self.reset_graphs(no_msg=True)

        if proceed:
            file_name = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "Text Files (*.txt)",
            )[0]

            try:
                file = Path(file_name).open(encoding="utf-8")  # noqa: SIM115
            except Exception as e:
                logger.exception(f"file open error: {e}")
                return
            try:
                skip_first = True

                if "All_Graph" in file_name:
                    # 🚀 OPTIMIZED: Use pandas for fast CSV loading
                    import pandas as pd

                    columns = ["GraphAll_x", "GraphAll_y"]
                    # Read entire CSV at once (much faster than row-by-row)
                    df = pd.read_csv(file, sep="\t", names=columns, skiprows=1)

                    # Convert to numpy arrays
                    times = df["GraphAll_x"].values.astype(float)
                    intensities = df["GraphAll_y"].values.astype(float)

                    # Distribute data across channels (d, a, b, c pattern)
                    ch_list = ["d", "a", "b", "c"]
                    for i, ch in enumerate(ch_list):
                        # Extract every 4th value starting at position i
                        ch_times = times[i::4]
                        ch_intensities = intensities[i::4]

                        self.data["lambda_times"][ch] = np.append(
                            self.data["lambda_times"][ch],
                            ch_times,
                        )
                        self.data["lambda_values"][ch] = np.append(
                            self.data["lambda_values"][ch],
                            ch_intensities,
                        )

                else:
                    # 🚀 OPTIMIZED: Use pandas for fast CSV loading
                    import pandas as pd

                    columns = [
                        "Time_A",
                        "Channel_A",
                        "Time_B",
                        "Channel_B",
                        "Time_C",
                        "Channel_C",
                        "Time_D",
                        "Channel_D",
                    ]

                    # Read CSV with pandas (much faster)
                    df = pd.read_csv(file, sep="\t", names=columns)

                    # Extract reference values from first row if present
                    references = None
                    try:
                        # Check if first row contains reference values (non-numeric)
                        first_row = df.iloc[0]
                        if pd.isna(first_row["Time_A"]) or not isinstance(
                            first_row["Time_A"],
                            (int, float),
                        ):
                            # Has header/reference row
                            references = [
                                float(first_row[f"Channel_{ch}"])
                                if pd.notna(first_row[f"Channel_{ch}"])
                                else 0.0
                                for ch in ["A", "B", "C", "D"]
                            ]
                            df = df.iloc[1:]  # Skip reference row
                    except (ValueError, KeyError):
                        pass

                    # Convert to numeric
                    df = df.apply(pd.to_numeric, errors="coerce")

                    # Apply reference conversion if needed (RU to nm)
                    if references:
                        for i, ch in enumerate(["A", "B", "C", "D"]):
                            df[f"Channel_{ch}"] = (
                                df[f"Channel_{ch}"] / 355 + references[i]
                            )

                    # Append to data arrays
                    self.data["lambda_times"]["a"] = np.append(
                        self.data["lambda_times"]["a"],
                        df["Time_A"].values,
                    )
                    self.data["lambda_values"]["a"] = np.append(
                        self.data["lambda_values"]["a"],
                        df["Channel_A"].values,
                    )
                    self.data["lambda_times"]["b"] = np.append(
                        self.data["lambda_times"]["b"],
                        df["Time_B"].values,
                    )
                    self.data["lambda_values"]["b"] = np.append(
                        self.data["lambda_values"]["b"],
                        df["Channel_B"].values,
                    )
                    self.data["lambda_times"]["c"] = np.append(
                        self.data["lambda_times"]["c"],
                        df["Time_C"].values,
                    )
                    self.data["lambda_values"]["c"] = np.append(
                        self.data["lambda_values"]["c"],
                        df["Channel_C"].values,
                    )
                    self.data["lambda_times"]["d"] = np.append(
                        self.data["lambda_times"]["d"],
                        df["Time_D"].values,
                    )
                    self.data["lambda_values"]["d"] = np.append(
                        self.data["lambda_values"]["d"],
                        df["Channel_D"].values,
                    )

                self.data["filt"] = False
                for ch in CH_LIST:
                    self.data["filtered_lambda_values"][ch] = medfilt(
                        self.data["lambda_values"][ch],
                        MED_FILT_WIN,
                    )
                self.data["buffered_lambda_times"] = deepcopy(
                    self.data["lambda_times"],
                )

                for _i in range(len(self.saved_segments)):
                    self.delete_row(first_available=True)

                self.current_segment = None
                self.enable_controls(data_ready=True)
                self.update_data(self.data)
                self.full_segment_view.center_cursors()
                self.new_segment()

            except Exception as e:
                logger.exception(f"import raw data error {e}")
                show_message(msg="Import Error: Incorrect file for Raw Data")

    def import_table(self: Self) -> None:
        """Import cycle data table using pandas."""
        if (len(self.data["lambda_times"]["a"]) > 0) and (
            len(self.data["lambda_times"]["a"]) == len(self.data["lambda_times"]["d"])
        ):
            file_name = QFileDialog.getOpenFileName(
                self,
                "Open File",
                "",
                "Text Files (*.txt)",
            )[0]

            if not file_name:
                return

            try:
                # Clear existing segments
                if self.segment_edit is not None:
                    self.new_segment()

                for _i in range(self._get_table_widget().rowCount()):
                    self.delete_row(first_available=True)
                self.seg_count = 0

                # Import using pandas
                imported_df = SegmentDataFrame.from_csv(file_name, encoding="utf-8")

                # Reconstruct Segment objects with data
                for i, row_dict in enumerate(imported_df.df.iterrows()):
                    _, row = row_dict
                    self.current_segment = Segment(
                        i,
                        float(row["start"]),
                        float(row["end"]),
                    )
                    self.current_segment.add_info(
                        {"name": str(row["name"]), "note": str(row["note"])},
                    )
                    ref_ch = row["ref_ch"]
                    if ref_ch in {"", "None", None}:
                        ref_ch = None
                    self.current_segment.add_data(
                        self.data,
                        self.unit,
                        ref_ch,
                    )
                    # Set cycle type from imported data
                    self.current_segment.cycle_type = str(
                        row.get("cycle_type", "Auto-read"),
                    )
                    self.save_segment()

                logger.info(f"Successfully imported {len(imported_df)} segments")

            except Exception as e:
                logger.exception(f"import table error {e}, type {type(e)}")
                show_message(msg="Import Error: Incorrect file for Data Table")

        else:
            show_message(
                msg="Missing Data:\n"
                "Please import raw data first, then load segment data table",
            )
