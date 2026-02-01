#!/usr/bin/env python3
"""
cleanup_workspace.py
Comprehensive workspace cleanup - organize utility scripts, docs, and data files.
"""

from pathlib import Path

# Get workspace root
WORKSPACE_ROOT = Path(__file__).parent

# Define essential files that should stay in root
ESSENTIAL_FILES = {
    'run_app.py',
    'README.md',
    'pyproject.toml',
    'pdm.toml',
    'pyrightconfig.json',
    '.gitignore',
    '.pylintrc',
    '.gitlab-ci.yml',
    'VERSION',
    'version.py',
    'cleanup_md_docs.py',
    'cleanup_root_files.py',
    'cleanup_workspace.py',
}

# Define organization structure
ORGANIZATION = {
    # Python utility scripts
    'scripts/analysis': [
        'analyze_baseline_noise.py',
        'analyze_peak_tracking_parameters.py',
        'performance_comparison_analysis.py',
        'FINAL_METHOD_COMPARISON.py',
        'compare_baseline_methods.py',
        'spectral_quality_analyzer.py',
    ],
    'scripts/plotting': [
        'plot_calibration_results.py',
        'plot_failed_calibration.py',
        'plot_latest_calibration.py',
        'plot_sp_calibration.py',
        'plot_sp_data.py',
    ],
    'scripts/calibration': [
        'calibrate_servo_v1.8.py',
        'calibration_6step_GOLDEN.py',
        'led_afterglow_integration_time_model.py',
        'led_afterglow_model.py',
        'measure_spr_calibration_with_polarization.py',
        'process_spr_calibration.py',
        'run_polarizer_calibration.py',
        'regenerate_afterglow_calibration.py',
        'use_calibration_models.py',
    ],
    'scripts/recovery': [
        'quick_recovery_console.py',
        'recover_baseline_data.py',
        'diagnose_led_hardware.py',
        'fix_traceback_bytes_issue.py',
    ],
    'scripts/data_conversion': [
        'convert_to_ru.py',
        'results_in_ru.py',
    ],
    'scripts/provisioning': [
        'factory_provision_device.py',
        'setup_device.py',
        'install_config.py',
        'reorganize_device_config.py',
    ],
    'scripts/examples': [
        'example_controller_hal_usage.py',
        'example_reference_baseline_usage.py',
    ],
    'scripts/utilities': [
        'check_ports.py',
        'quick_polarizer_test.py',
        'quick_test.py',
        'sync_test_from_git.py',
        'verify_data_storage.py',
        'training_data_manager.py',
    ],
    'scripts/legacy': [
        'temp_original_processor.py',
        'usb4000_wrapper_GOLDEN.py',
    ],

    # Firmware tools
    'tools/firmware': [
        'bin_to_uf2.py',
        'elf_to_uf2.py',
    ],

    # PowerShell scripts
    'tools/powershell': [
        'flash_v1.2.ps1',
        'run_app.ps1',
        'run_app_312.ps1',
        'run_no_cache.ps1',
        'set_no_cache_permanent.ps1',
    ],

    # Documentation and reference files
    'docs/reference': [
        'calibration_output.txt',
        'COMMIT_MESSAGE.txt',
        'GITHUB_UPLOAD_GUIDE.txt',
        'QUICK_REFERENCE.txt',
        'REFLASH_V1.1_INSTRUCTIONS.txt',
        'original_sidebar.txt',
        'original_sidebar_COMPLETE.txt',
        'original_sidebar_full.txt',
    ],

    # Test logs
    'docs/test_logs': [
        'test_ch1_log.txt',
        'test_ch2_log.txt',
        'test_cycle_table_export.txt',
        'test_temp_log.txt',
    ],

    # Data files
    'data/optimization': [
        'integration_time_optimization.json',
    ],
}


def find_files_to_move():
    """Find all files that need to be organized."""
    plan = {}
    found_files = set()
    missing_files = set()

    for dest_dir, file_list in ORGANIZATION.items():
        plan[dest_dir] = []
        for filename in file_list:
            file_path = WORKSPACE_ROOT / filename
            if file_path.exists():
                plan[dest_dir].append(file_path)
                found_files.add(filename)
            else:
                missing_files.add(filename)

    return plan, found_files, missing_files


def display_plan(plan, found_files, missing_files):
    """Display the organization plan to the user."""
    total_files = sum(len(files) for files in plan.values())

    if total_files == 0:
        print("✓ No files to organize - workspace is already clean!")
        return False

    print(f"Found {total_files} files to organize:\n")

    # Group by main category
    categories = {}
    for dest_dir, files in sorted(plan.items()):
        if not files:
            continue
        main_cat = dest_dir.split('/')[0]
        if main_cat not in categories:
            categories[main_cat] = []
        categories[main_cat].append((dest_dir, files))

    # Display by category
    for main_cat, items in sorted(categories.items()):
        print(f"{main_cat.upper()}:")
        for dest_dir, files in items:
            if files:
                print(f"  → {dest_dir}/")
                for f in sorted(files):
                    print(f"    • {f.name}")
        print()

    if missing_files:
        print(f"Note: {len(missing_files)} files already moved or not found")

    print("=" * 70)
    return True


def move_files(plan):
    """Move files to their organized locations."""
    moved_count = 0
    failed_count = 0

    for dest_dir, files in plan.items():
        if not files:
            continue

        dest_path = WORKSPACE_ROOT / dest_dir
        dest_path.mkdir(parents=True, exist_ok=True)

        for file_path in files:
            try:
                dest = dest_path / file_path.name
                file_path.rename(dest)
                print(f"✓ Moved: {file_path.name} → {dest_dir}/")
                moved_count += 1
            except Exception as e:
                print(f"✗ Failed: {file_path.name} - {e}")
                failed_count += 1

    print()
    print(f"✅ Successfully organized {moved_count} files")
    if failed_count > 0:
        print(f"❌ Failed to move {failed_count} files")

    print()
    print("Root directory now contains only:")
    print("  • run_app.py (main entry point)")
    print("  • Configuration files (pyproject.toml, pyrightconfig.json, etc.)")
    print("  • README.md")
    print("  • Core project folders (affilabs/, utils/, etc.)")
    print()
    print("=" * 70)


def main():
    """Main execution function."""
    print("Workspace Organization Tool")
    print("=" * 70)
    print()

    # Find and display plan
    plan, found_files, missing_files = find_files_to_move()
    has_files = display_plan(plan, found_files, missing_files)

    if not has_files:
        return

    # Ask for confirmation
    response = input("Organize these files? (yes/no): ").strip().lower()

    if response == "yes":
        print()
        move_files(plan)
    else:
        print("Cancelled - no files were moved.")


if __name__ == "__main__":
    main()
