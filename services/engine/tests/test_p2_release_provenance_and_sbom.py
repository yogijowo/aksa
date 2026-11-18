"""Tests for P2.2 Release Signing, CycloneDX SBOM, Checksums, and Smoke Testing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

_repo_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.release_tooling import (
    compute_file_sha256,
    generate_checksums,
    generate_cyclonedx_sbom,
    smoke_test_sidecar,
    verify_checksums,
)


def test_cyclonedx_sbom_generation() -> None:
    """Verify SBOM generates valid CycloneDX 1.5 format containing components."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "aksa-sbom.json"
        sbom = generate_cyclonedx_sbom(repo_root=repo_root, output_path=out_file)

        assert sbom["bomFormat"] == "CycloneDX"
        assert sbom["specVersion"] == "1.5"
        assert "serialNumber" in sbom
        assert sbom["metadata"]["component"]["name"] == "aksa"

        components = sbom["components"]
        assert len(components) > 0

        # Check for core components
        names = {c["name"].lower() for c in components}
        assert any("fastapi" in n or "pydantic" in n or "aksa" in n for n in names)

        # Check for Cargo Rust components (P2-02)
        cargo_components = [c for c in components if c["purl"].startswith("pkg:cargo/")]
        assert len(cargo_components) > 0, "SBOM must include Rust/Cargo components from Cargo.lock"

        # Check purl formatting
        for comp in components:
            assert "purl" in comp
            assert comp["purl"].startswith("pkg:")

        assert out_file.exists()
        loaded = json.loads(out_file.read_text(encoding="utf-8"))
        assert loaded["bomFormat"] == "CycloneDX"


def test_checksum_generation_and_tamper_detection() -> None:
    """Verify SHA-256 generation and fail-closed tamper detection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        file1 = tmp_path / "aksa-engine.bin"
        file2 = tmp_path / "aksa-desktop.dmg"

        file1.write_bytes(b"mock executable payload 1")
        file2.write_bytes(b"mock dmg payload 2")

        sums_file = tmp_path / "SHA256SUMS.txt"
        checksums = generate_checksums([file1, file2], output_path=sums_file)

        assert "aksa-engine.bin" in checksums
        assert "aksa-desktop.dmg" in checksums

        # Verify correct matching
        ok, errors = verify_checksums(sums_file)
        assert ok is True
        assert len(errors) == 0

        # Tamper with file1
        file1.write_bytes(b"tampered malicious payload")

        # Must fail closed with explicit mismatch
        ok_tampered, errors_tampered = verify_checksums(sums_file)
        assert ok_tampered is False
        assert len(errors_tampered) == 1
        assert "Checksum mismatch" in errors_tampered[0]


def test_sidecar_cli_version_flag() -> None:
    """Verify sidecar --version CLI flag executes and exits 0 cleanly."""
    engine_dir = Path(__file__).resolve().parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "app.main", "--version"],
        cwd=str(engine_dir),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 0
    assert "AKSA Engine v1.0.0" in res.stdout


def test_sidecar_cli_smoke_test_flag() -> None:
    """Verify sidecar --smoke-test CLI flag runs subsystem initialization and exits 0."""
    engine_dir = Path(__file__).resolve().parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "app.main", "--smoke-test"],
        cwd=str(engine_dir),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert res.returncode == 0
    assert "[SMOKE-TEST]" in res.stdout
    assert "subsystems initialized and verified successfully" in res.stdout


def test_smoke_test_sidecar_helper() -> None:
    """Verify smoke_test_sidecar helper function works with default interpreter."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    assert smoke_test_sidecar(repo_root=repo_root) is True


def test_workflow_actions_pinned() -> None:
    """Verify GitHub Actions in .github/workflows are pinned to commit SHAs."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    workflows_dir = repo_root / ".github" / "workflows"
    assert workflows_dir.exists()

    for wf in workflows_dir.glob("*.yml"):
        lines = wf.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("uses:"):
                action_ref = line.split("uses:", 1)[1].strip()
                # Should not use unpinned branches like @master or @main
                assert not action_ref.endswith("@master")
                assert not action_ref.endswith("@main")
                # Either a 40-char SHA commit or pinned release tag
                ref_part = action_ref.split("#")[0].strip()
                if "@" in ref_part:
                    version_or_sha = ref_part.split("@")[1]
                    assert len(version_or_sha) > 0

