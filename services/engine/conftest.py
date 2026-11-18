import sys
from pathlib import Path

# Add project root and engine directory to sys.path so scripts and app are always resolvable
root_dir = Path(__file__).resolve().parent.parent.parent
engine_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(engine_dir) not in sys.path:
    sys.path.insert(0, str(engine_dir))
