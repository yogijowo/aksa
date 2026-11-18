"""Tests for P1.6: Skills Marketplace Supply-Chain Security, Archive Sandboxing, and Atomic Promotion."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
import pytest

from app.db.models import db_manager
from app.skills.skill_manager import agent_skills_manager


@pytest.fixture(autouse=True)
async def init_db():
    await db_manager.initialize()


@pytest.mark.asyncio
async def test_curated_skill_calculates_real_cryptographic_hash():
    """Verify curated skill installation computes genuine SHA-256 from disk files, not fake skill_id hash (P1.6)."""
    installed = await agent_skills_manager.install_curated_skill("excel-monthly-report")
    assert installed["enabled"] is False  # Must be disabled by default
    real_hash = installed["package_hash"]

    # Verify that real_hash is NOT the fake hash of the string "excel-monthly-report"
    fake_hash = hashlib.sha256(b"excel-monthly-report").hexdigest()
    assert real_hash != fake_hash
    assert len(real_hash) == 64


@pytest.mark.asyncio
async def test_zip_slip_path_traversal_strictly_rejected(tmp_path: Path):
    """Verify malicious ZIP archive containing directory traversal paths (../) is rejected in quarantine."""
    malicious_zip = tmp_path / "zip_slip.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("SKILL.md", "---\nname: Test\n---\n# Test")
        zf.writestr("../../../../../../../etc/passwd", "evil:x:0:0:::")

    with pytest.raises(ValueError) as exc_info:
        await agent_skills_manager.scan_package_archive(malicious_zip)

    assert "Path traversal" in str(exc_info.value)


@pytest.mark.asyncio
async def test_hash_mismatch_rejected_during_package_install(tmp_path: Path):
    """Verify package installation with wrong expected hash is rejected."""
    valid_zip = tmp_path / "valid_skill.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("SKILL.md", "---\nname: valid-custom-skill\n---\n# Valid Custom Skill")

    with pytest.raises(ValueError) as exc_info:
        await agent_skills_manager.install_skill_package(
            valid_zip,
            expected_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )

    assert "Hash SHA-256 mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_atomic_stage_and_promote_lifecycle(tmp_path: Path):
    """Verify clean package is safely extracted into staging, atomically promoted, and recorded disabled."""
    valid_zip = tmp_path / "safe_skill.zip"
    skill_content = "---\nname: safe-promoted-skill\nversion: 1.0.0\npublisher: Test Team\n---\n\n# Safe Skill\n"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("SKILL.md", skill_content)

    item = await agent_skills_manager.install_skill_package(valid_zip)
    skill_id = item["skill_id"]
    assert skill_id == "safe-promoted-skill"
    assert item["enabled"] is False  # Disabled by default

    # Verify promoted directory exists
    dest_dir = agent_skills_manager.skills_dir / skill_id
    assert dest_dir.exists()
    assert (dest_dir / "SKILL.md").exists()

    # Uninstall skill
    uninstalled = await agent_skills_manager.uninstall_skill(skill_id)
    assert uninstalled is True
    assert not dest_dir.exists()

