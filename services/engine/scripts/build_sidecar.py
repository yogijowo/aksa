"""Proxy to root scripts/build_sidecar.py."""

from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

from build_sidecar import build_sidecar, detect_target_triple, main  # noqa: E402

if __name__ == "__main__":
    main()
