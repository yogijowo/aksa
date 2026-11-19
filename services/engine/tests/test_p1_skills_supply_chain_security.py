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


@pytest.mark.asyncio
async def test_publisher_signature_verification_against_trust_store(tmp_path: Path):
    """Verify digital signature verification against publisher trust store (P1-03)."""
    from cryptography.hazmat.primitives.asymmetric import ed25519
    import base64
    from app.skills.skill_manager import PublisherTrustStore, publisher_trust_store

    # Generate test root authority and custom publisher keypair
    test_root_priv = ed25519.Ed25519PrivateKey.generate()
    test_root_pub_b64 = base64.b64encode(test_root_priv.public_key().public_bytes_raw()).decode("ascii")
    publisher_trust_store.set_root_public_key(test_root_pub_b64)

    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key_b64 = base64.b64encode(priv_key.public_key().public_bytes_raw()).decode("ascii")

    # Prove root delegation signature is required and valid
    delegation_sig = PublisherTrustStore.sign_publisher_delegation("trusted_corp", pub_key_b64, test_root_priv)
    publisher_trust_store.register_publisher("trusted_corp", pub_key_b64, root_signature_b64=delegation_sig)

    # Create signed skill ZIP
    signed_zip = tmp_path / "signed_skill.zip"
    with zipfile.ZipFile(signed_zip, "w") as zf:
        zf.writestr("SKILL.md", "---\nname: corporate-skill\npublisher: trusted_corp\n---\n# Corporate Skill")

    # Hash the package
    hasher = hashlib.sha256()
    with open(signed_zip, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    pkg_hash = hasher.hexdigest()

    # Sign package hash with publisher private key
    sig_bytes = priv_key.sign(pkg_hash.encode("ascii"))
    valid_sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    # 1. Valid signature -> verified_publisher
    report = await agent_skills_manager.scan_package_archive(
        signed_zip,
        signature_b64=valid_sig_b64,
        publisher_id="trusted_corp",
    )
    assert report.is_valid is True
    assert report.signature_verified is True
    assert report.publisher_trusted is True
    assert report.manifest.trust_level == "verified_publisher"

    # 2. Tampered signature -> rejected
    tampered_sig = base64.b64encode(b"invalid_signature_bytes_32_bytes!").decode("ascii")
    report_tampered = await agent_skills_manager.scan_package_archive(
        signed_zip,
        signature_b64=tampered_sig,
        publisher_id="trusted_corp",
    )
    assert report_tampered.is_valid is False
    assert report_tampered.signature_verified is False
    assert any("Tanda tangan digital" in w for w in report_tampered.security_warnings)


@pytest.mark.asyncio
async def test_disabled_skill_execution_rejected_fail_closed(tmp_path: Path):
    """Verify executing scripts on disabled skills fails closed with PermissionError (P1-03)."""
    # Create and install a skill with script
    skill_zip = tmp_path / "script_skill.zip"
    with zipfile.ZipFile(skill_zip, "w") as zf:
        zf.writestr("SKILL.md", "---\nname: runnable-skill\n---\n# Runnable")
        zf.writestr("scripts/run.py", "print('hello from skill')")

    item = await agent_skills_manager.install_skill_package(skill_zip)
    assert item["enabled"] is False

    # Attempt to execute while disabled must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        await agent_skills_manager.execute_skill_script(
            skill_id="runnable-skill",
            script_rel_path="scripts/run.py",
            workspace_path=str(tmp_path),
        )
    assert "nonaktif atau belum disetujui" in str(exc_info.value)


