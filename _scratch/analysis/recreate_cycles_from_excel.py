"""Recreate Cycle objects from exported Excel data.

This script demonstrates how to accurately parse and recreate cycles
from an exported AffiLabs.core Excel file.

CRITICAL FINDINGS from "spr_data_20260211_194755 - concentrations.xlsx":

1. end_time_sensorgram is NaN for all cycles
   -> Cycles were stopped early or recording incomplete

2. concentration_value field is NaN for all cycles
   -> Concentration NOT stored in dedicated field

3. concentrations dict is empty {} for all cycles
   -> Multi-channel concentrations NOT populated

4. Concentration data IS PRESERVED in the "note" field
   -> Format: "conc 8min 0nm", "conc 8min 1.37nm", "conc 8min 4.1nm"
   -> This is the ONLY source of concentration values

5. SPR deltas stored in delta_ch1/ch2/ch3/ch4 columns
   -> These map to channels A, B, C, D respectively

RECONSTRUCTION STRATEGY:
- Parse concentration value from note field (extract number before "nm")
- Reconstruct delta_spr_by_channel from delta_ch1/ch2/ch3/ch4
- Handle missing end_time_sensorgram gracefully
- Preserve all metadata from the Excel export
"""

import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

from affilabs.domain.cycle import Cycle
from affilabs.utils.logger import logger


def parse_concentration_from_note(note: str) -> float | None:
    """Extract concentration value from cycle note.

    Args:
        note: Cycle note field (e.g., "conc 8min 1.37nm")

    Returns:
        Concentration value in nM, or None if not found

    Examples:
        "conc 8min 0nm" -> 0.0
        "conc 8min 1.37nm" -> 1.37
        "conc 8min 111nm" -> 111.0
        "conc 8min 1000nm" -> 1000.0
    """
    if not note or pd.isna(note):
        return None

    # Match number before "nm" or "nM" (handles decimals)
    match = re.search(r'(\d+\.?\d*)n[mM]', str(note))
    if match:
        return float(match.group(1))

    return None


def reconstruct_delta_spr_by_channel(row: pd.Series) -> Dict[str, float]:
    """Reconstruct delta_spr_by_channel dict from delta_ch1/ch2/ch3/ch4 columns.

    Args:
        row: DataFrame row with delta_ch1, delta_ch2, delta_ch3, delta_ch4 columns

    Returns:
        Dictionary mapping channel letter to delta SPR value
        Example: {'A': 2.35, 'B': 1.55, 'C': -0.76, 'D': -2.40}
    """
    delta_by_channel = {}

    for ch_num in [1, 2, 3, 4]:
        delta_col = f'delta_ch{ch_num}'
        if delta_col in row and pd.notna(row[delta_col]):
            ch_letter = chr(64 + ch_num)  # 1->A, 2->B, 3->C, 4->D
            delta_by_channel[ch_letter] = float(row[delta_col])

    return delta_by_channel


def recreate_cycles_from_excel(excel_path: Path) -> List[Cycle]:
    """Recreate Cycle objects from exported Excel file.

    Args:
        excel_path: Path to exported Excel file

    Returns:
        List of Cycle objects with all metadata preserved

    Raises:
        FileNotFoundError: If Excel file doesn't exist
        ValueError: If Cycles sheet not found in Excel file
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    # Read Cycles sheet
    try:
        df_cycles = pd.read_excel(excel_path, sheet_name='Cycles', engine='openpyxl')
    except ValueError as e:
        raise ValueError(f"Cycles sheet not found in Excel file: {e}") from e

    logger.info(f"Loading {len(df_cycles)} cycles from {excel_path.name}")

    cycles = []

    for idx, row in df_cycles.iterrows():
        # Parse concentration from note field (CRITICAL)
        concentration = parse_concentration_from_note(row.get('note', ''))

        # Reconstruct delta_spr_by_channel from delta_ch columns
        delta_by_channel = reconstruct_delta_spr_by_channel(row)

        # Calculate end_time_sensorgram from start + duration if missing
        end_time = row.get('end_time_sensorgram')
        if pd.isna(end_time):
            # Calculate from start time + duration
            start_time = row.get('start_time_sensorgram')
            duration_min = row.get('duration_minutes')
            if start_time is not None and duration_min is not None:
                end_time = start_time + (duration_min * 60.0)
                logger.debug(f"Cycle {row.get('cycle_num', idx+1)}: Calculated end time = {end_time:.2f}s (from start + duration)")
            else:
                end_time = None
                logger.warning(f"Cycle {row.get('cycle_num', idx+1)}: Cannot calculate end time (missing start or duration)")

        # Create Cycle object with all available data
        cycle_data = {
            'type': row.get('type', 'Unknown'),
            'length_minutes': row.get('duration_minutes', 0.0),
            'name': row.get('name', f"Cycle {idx + 1}"),
            'note': row.get('note', ''),
            'cycle_id': int(row.get('cycle_id', idx + 1)),
            'cycle_num': int(row.get('cycle_num', idx + 1)),
            'status': 'completed',  # Assume completed since it's in export
            'sensorgram_time': row.get('start_time_sensorgram'),
            'end_time_sensorgram': end_time,

            # Concentration data (parsed from note)
            'concentration_value': concentration,
            'concentration_units': row.get('concentration_units', 'nM'),
            'units': row.get('units', 'nM'),

            # SPR deltas (reconstructed from delta_ch columns)
            'delta_spr_by_channel': delta_by_channel,

            # Automation settings
            'injection_method': row.get('injection_method'),
            'injection_delay': row.get('injection_delay', 20.0),
            'flow_rate': row.get('flow_rate') if pd.notna(row.get('flow_rate')) else None,
            'pump_type': row.get('pump_type') if pd.notna(row.get('pump_type')) else None,
            'channels': row.get('channels') if pd.notna(row.get('channels')) else None,
            'contact_time': row.get('contact_time') if pd.notna(row.get('contact_time')) else None,
        }

        # Create validated Cycle object (Pydantic validation)
        cycle = Cycle(**cycle_data)
        cycles.append(cycle)

        logger.debug(f"Recreated: {cycle.type} - {cycle.name} ({concentration} nM)")

    logger.info(f"Successfully recreated {len(cycles)} cycles")

    return cycles


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Path to exported Excel file
    excel_file = Path(r"C:\Users\lucia\Documents\Affilabs Data\spr_data_20260211_194755 - concentrations.xlsx")

    # Recreate cycles
    cycles = recreate_cycles_from_excel(excel_file)

    # Display recreated cycles
    print("\n" + "=" * 80)
    print("RECREATED CYCLES")
    print("=" * 80)

    for cycle in cycles:
        print(f"\nCycle {cycle.cycle_num}: {cycle.name}")
        print(f"  Type: {cycle.type}")
        print(f"  Duration: {cycle.length_minutes} minutes")
        print(f"  Start: {cycle.sensorgram_time:.2f}s")
        print(f"  End: {cycle.end_time_sensorgram if cycle.end_time_sensorgram else 'Not recorded'}")
        print(f"  Concentration: {cycle.concentration_value} {cycle.concentration_units}")
        print(f"  Note: \"{cycle.note}\"")

        if cycle.delta_spr_by_channel:
            print(f"  SPR Deltas: {cycle.delta_spr_by_channel}")

        if cycle.injection_method:
            print(f"  Injection: {cycle.injection_method} (delay: {cycle.injection_delay}s)")

    print("\n" + "=" * 80)
    print(f"Total cycles recreated: {len(cycles)}")
    print("=" * 80)
