"""Tests for P1-4: Sidecar Binary Freezing & Distribution Packaging."""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to sys.path so scripts.build_sidecar can be imported
repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

from build_sidecar import build_sidecar, detect_target_triple  # noqa: E402


def test_p1_detect_target_triple() -> None:
    """Verify target triple detection returns expected platform string."""
    triple = detect_target_triple()
    assert isinstance(triple, str)
    assert len(triple) > 5
    if sys.platform == "darwin":
        assert "apple-darwin" in triple
    elif sys.platform == "win32":
        assert "windows" in triple or "msvc" in triple


def test_p1_build_sidecar_dry_run() -> None:
    """Verify build_sidecar in dry-run mode targets the src-tauri/binaries directory."""
    binary_path = build_sidecar(dry_run=True)
    assert isinstance(binary_path, Path)
    assert binary_path.parent.name == "binaries"
    assert binary_path.name.startswith("aksa-engine-")
    if sys.platform == "win32":
        assert binary_path.suffix == ".exe"

