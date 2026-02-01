#!/usr/bin/env python3
"""Development Script to Run Affinite App with Correct Python Environment

This script ensures the application runs with Python 3.12 from the virtual environment,
avoiding any Python version conflicts.
"""

import subprocess
import sys
import time
from pathlib import Path


def kill_stale_processes():
    """Kill any stale Python processes from previous runs that might hold COM ports.

    CRITICAL: This aggressively kills all app-related Python processes to ensure
    COM ports (especially COM4) are released. Ghost processes from frozen/crashed
    runs can block serial port access.
    """
    import os

    import psutil

    current_pid = os.getpid()
    killed_count = 0
    workspace_path = str(Path(__file__).parent).lower()

    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "exe"]):
            try:
                # Skip ourselves
                if proc.info["pid"] == current_pid:
                    continue

                if proc.info["name"] and "python" in proc.info["name"].lower():
                    cmdline = proc.info.get("cmdline", [])
                    exe_path = proc.info.get("exe", "")

                    if cmdline or exe_path:
                        cmdline_str = " ".join(cmdline).lower() if cmdline else ""
                        exe_str = exe_path.lower() if exe_path else ""

                        # Skip VS Code extensions (mypy, isort, pylance, etc.)
                        skip_patterns = [
                            "lsp_server",
                            "mypy",
                            "isort",
                            "pylance",
                            "extensions",
                            "language_server",
                            "debugpy",
                            "jedi",
                        ]
                        if any(skip in cmdline_str for skip in skip_patterns):
                            continue

                        # Skip this launcher script (but not if it's an old instance)
                        if (
                            "run_app.py" in cmdline_str
                            and proc.info["pid"] == current_pid
                        ):
                            continue

                        # AGGRESSIVE: Kill ANY Python process running from our workspace
                        # This catches main.py, background threads, frozen processes, etc.
                        if workspace_path in cmdline_str or workspace_path in exe_str:
                            print(
                                f"   Killing workspace process PID {proc.info['pid']}: {proc.info['name']}",
                            )
                            proc.kill()
                            killed_count += 1
                        # Also catch control-3.2.9 in case workspace path doesn't match
                        elif (
                            "control-3.2.9" in cmdline_str and "main.py" in cmdline_str
                        ):
                            print(
                                f"   Killing app process PID {proc.info['pid']}: {proc.info['name']}",
                            )
                            proc.kill()
                            killed_count += 1

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if killed_count > 0:
            print(f"   Killed {killed_count} stale process(es)")
            time.sleep(2)  # Wait longer for COM port to be fully released
        else:
            print("   No stale processes found")

    except Exception as e:
        print(f"   WARNING: Could not check for stale processes: {e}")


def main():
    """Run the Affinite application with Python 3.12."""
    project_root = Path(__file__).parent

    # Try Python 3.12 venv first, then fall back to .venv
    venv_python = project_root / ".venv312" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"

    # Main application entry point
    main_script = project_root / "main.py"

    if not venv_python.exists():
        print("ERROR: Virtual environment Python not found!")
        print(f"Expected: {venv_python}")
        print("Run: py -3.12 -m venv .venv312")
        return 1

    if not main_script.exists():
        print("ERROR: Main script not found!")
        print(f"Expected: {main_script}")
        return 1

    print("Starting Affinite SPR System...")
    print(f"   Python: {venv_python}")
    print(f"   Script: {main_script}")

    # Kill any stale processes from previous crashes
    print("\nChecking for stale processes...")
    kill_stale_processes()

    print("=" * 50)

    # Set environment
    env = {
        "PYTHONPATH": str(project_root),
        **dict(os.environ),
    }

    # Run the application
    try:
        result = subprocess.run(
            [
                str(venv_python),
                str(main_script),
            ],
            check=False,
            env=env,
            cwd=project_root,
        )
        return result.returncode

    except KeyboardInterrupt:
        print("\n🛑 Application interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        return 1


if __name__ == "__main__":
    import os

    sys.exit(main())
