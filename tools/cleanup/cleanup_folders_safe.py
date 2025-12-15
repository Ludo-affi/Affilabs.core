#!/usr/bin/env python3
"""
cleanup_folders_safe.py
Conservative folder cleanup - only moves definitely safe folders.
Preserves all active code modules and frequently accessed data paths.
"""

import os
from pathlib import Path
import shutil

# Get workspace root
WORKSPACE_ROOT = Path(__file__).parent

# Define SAFE folder moves (no active imports, no hardcoded paths)
SAFE_MOVES = {
    # Firmware folders (separate git repos, not imported)
    'firmware/': 'firmware_archive/pico_general/',
    'firmware_v2.1/': 'firmware_archive/v2.1/',
    'pico-p4spr-firmware/': 'firmware_archive/pico_p4spr/',
    'elf2uf2/': 'firmware_archive/elf2uf2/',
    
    # Archive folders (old code)
    '_archived_Affilabs.core_beta/': 'archive/affilabs_core_beta/',
    'Old software/': 'archive/old_software/',
    'LED-Counts relationship/': 'archive/led_counts_relationship/',
    
    # Build artifacts (temporary, regenerated)
    'build/': 'build_artifacts/build/',
    'dist/': 'build_artifacts/dist/',
    'generated-files/': 'build_artifacts/generated/',
    
    # Output/results folders (data only, not in hot path)
    'analysis_results/': 'data_results/analysis/',
    'results/': 'data_results/results/',
    'training_data/': 'data_results/training/',
    'spectral_training_data/': 'data_results/spectral_training/',
    
    # Log folders (output only)
    'debug_logs/': 'logs/debug/',
    'fmea_reports/': 'logs/fmea_reports/',
}

# Keep these in root (active modules or hardcoded paths)
KEEP_IN_ROOT = {
    'affilabs/', 'utils/', 'widgets/', 'ui/', 'src/', 'tests/',
    'servo_polarizer_calibration/', 'spr_calibration/',
    'config/', 'settings/', 'detector_profiles/',
    'calibration_data/', 'calibration_results/', 'calibration_checkpoints/',
    'OpticalSystem_QC/', 'affipump/', 'led_calibration_official/',
    'scripts/', 'tools/', 'docs/', 'data/', 'logs/',
    'main/',
}


def find_folders_to_move():
    """Find folders that exist and can be moved."""
    moves = {}
    missing = []
    
    for source, dest in SAFE_MOVES.items():
        source_path = WORKSPACE_ROOT / source
        if source_path.exists() and source_path.is_dir():
            moves[source] = dest
        else:
            missing.append(source)
    
    return moves, missing


def display_plan(moves, missing):
    """Display the move plan."""
    if not moves:
        print("✓ No folders to move - already organized!")
        return False
    
    print(f"Found {len(moves)} folders to organize:\n")
    
    # Group by category
    categories = {
        'FIRMWARE': [],
        'ARCHIVES': [],
        'BUILD ARTIFACTS': [],
        'DATA/RESULTS': [],
        'LOGS': [],
    }
    
    for source, dest in sorted(moves.items()):
        if 'firmware' in dest:
            categories['FIRMWARE'].append((source, dest))
        elif 'archive' in dest:
            categories['ARCHIVES'].append((source, dest))
        elif 'build_artifacts' in dest:
            categories['BUILD ARTIFACTS'].append((source, dest))
        elif 'data_results' in dest:
            categories['DATA/RESULTS'].append((source, dest))
        elif 'logs' in dest:
            categories['LOGS'].append((source, dest))
    
    for category, items in categories.items():
        if items:
            print(f"{category}:")
            for source, dest in items:
                print(f"  {source} → {dest}")
            print()
    
    if missing:
        print(f"Note: {len(missing)} folders already moved or not found")
    
    print("=" * 70)
    print("KEEPING IN ROOT (active modules):")
    for folder in sorted(KEEP_IN_ROOT):
        path = WORKSPACE_ROOT / folder
        if path.exists():
            print(f"  ✓ {folder}")
    print("=" * 70)
    
    return True


def move_folders(moves):
    """Move folders to new locations."""
    moved_count = 0
    failed_count = 0
    
    for source, dest in moves.items():
        source_path = WORKSPACE_ROOT / source
        dest_path = WORKSPACE_ROOT / dest
        
        try:
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the folder
            shutil.move(str(source_path), str(dest_path))
            print(f"✓ Moved: {source} → {dest}")
            moved_count += 1
        except Exception as e:
            print(f"✗ Failed: {source} - {e}")
            failed_count += 1
    
    print()
    print(f"✅ Successfully moved {moved_count} folders")
    if failed_count > 0:
        print(f"❌ Failed to move {failed_count} folders")
    
    print()
    print("Root directory now organized:")
    print("  • Active code modules remain in place")
    print("  • Firmware files archived to firmware_archive/")
    print("  • Old code archived to archive/")
    print("  • Build outputs in build_artifacts/")
    print("  • Results/data in data_results/")
    print("  • Logs organized in logs/")
    print()
    print("=" * 70)


def main():
    """Main execution."""
    print("Safe Folder Organization Tool")
    print("=" * 70)
    print("Moving only SAFE folders (no active imports)")
    print("=" * 70)
    print()
    
    # Find and display plan
    moves, missing = find_folders_to_move()
    has_moves = display_plan(moves, missing)
    
    if not has_moves:
        return
    
    # Ask for confirmation
    response = input("\nMove these folders? (yes/no): ").strip().lower()
    
    if response == "yes":
        print()
        move_folders(moves)
    else:
        print("Cancelled - no folders were moved.")


if __name__ == "__main__":
    main()
