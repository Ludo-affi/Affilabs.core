#!/usr/bin/env python3
"""Development Script to Run Affinite App with Correct Python Environment

This script ensures the application runs with Python 3.12 from the virtual environment,
avoiding any Python version conflicts.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run the Affinite application with Python 3.12."""
    project_root = Path(__file__).parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    main_script = project_root / "main" / "main.py"

    if not venv_python.exists():
        print("❌ Virtual environment Python not found!")
        print(f"Expected: {venv_python}")
        print("Run: pdm install")
        return 1

    if not main_script.exists():
        print("❌ Main script not found!")
        print(f"Expected: {main_script}")
        return 1

    print("🚀 Starting Affinite SPR System...")
    print(f"   Python: {venv_python}")
    print(f"   Script: {main_script}")
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
