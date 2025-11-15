"""
Launcher script for ezControl Old software
Adds the Old software directory to Python path and runs main
"""
import sys
from pathlib import Path

# Add Old software directory to path so modules can be found
old_software_dir = Path(__file__).parent
sys.path.insert(0, str(old_software_dir))

# Now import and run main
from main import main

if __name__ == "__main__":
    main()
