import sys
from pathlib import Path
import pytest

# Add project root and engine directory to sys.path so scripts and app are always resolvable
root_dir = Path(__file__).resolve().parent.parent.parent.parent
engine_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
if str(engine_dir) not in sys.path:
    sys.path.insert(0, str(engine_dir))


@pytest.fixture(autouse=True)
def _cleanup_background_watchers():
    """Ensure real-time Watchdog observers are stopped after each test so no thread outlives its event loop."""
    yield
    try:
        from app.rag.watcher import rag_watcher

        rag_watcher.stop_all()
    except Exception:
        pass

