from pathlib import Path
import sys

# Ensure project root is importable when pytest is executed from varied working directories
ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
