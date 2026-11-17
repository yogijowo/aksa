"""Portable Agent Skills Manager with Quarantine, Archive Safety, and Static Script Security Inspection.

Implements the standard Agent Skills specification (SKILL.md) and AKSA capability manifest (aksa.skill.yaml).
Skills are ALWAYS installed in a DISABLED state until the user inspects permissions and explicitly enables them.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.db.models import db_manager


class SkillManifest(BaseModel):
    """Parsed metadata from SKILL.md and optional aksa.skill.yaml manifest."""

    id: str
    display_name: str
    version: str = "1.0.0"
    publisher: str = "Komunitas"
    description: str = ""
    trust_level: str = "unreviewed"  # curated | verified_publisher | community_reviewed | unreviewed | blocked
    capabilities: list[str] = Field(default_factory=list)
    has_scripts: bool = False
    has_network: bool = False
    scripts: list[str] = Field(default_factory=list)
    instructions_preview: str = ""


class SkillScanReport(BaseModel):
    """Security audit result from package quarantine inspection."""

    is_valid: bool = True
    package_hash: str
    total_files: int = 0
    total_size_bytes: int = 0
    risk_level: str = "low"  # low | medium | high | critical
    security_warnings: list[str] = Field(default_factory=list)
    manifest: SkillManifest


# Curated catalog definitions ready for one-click installation and review
CURATED_SKILL_CATALOG: list[SkillManifest] = [
    SkillManifest(
        id="excel-monthly-report",
        display_name="Analisis Rekap Bulanan Excel",
        version="1.1.0",
        publisher="Tim Kurasi AKSA",
        description="Format laporan rekapitulasi anggaran bulanan dengan formula otomatis, styling korporat, dan grafik ringkasan.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/validate_workbook.py", "scripts/generate_charts.py"],
        instructions_preview="Keahlian memproses tabel mentah menjadi rekap bulanan berstandar eksekutif dengan validasi sel.",
    ),
    SkillManifest(
        id="official-indonesian-correspondence",
        display_name="Tata Naskah Dinas & Surat Resmi",
        version="1.0.2",
        publisher="Tim Kurasi AKSA",
        description="Penyusunan format Nota Dinas, Surat Keputusan, Surat Edaran, dan Undangan Resmi berstandar administrasi Indonesia.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pedoman tata persuratan resmi, struktur kop dinas standar, nomor surat, perihal, dan tembusan.",
    ),
    SkillManifest(
        id="pdf-table-extractor",
        display_name="Ekstraktor Tabel Dokumen PDF",
        version="1.0.0",
        publisher="Tim Kurasi AKSA",
        description="Membaca dan memisahkan struktur tabel berulang di dalam dokumen PDF lampiran menjadi data spreadsheet terstruktur.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/parse_pdf_tables.py"],
        instructions_preview="Ekstraksi tabel multi-halaman berbasis PyMuPDF dengan auto-mapping kolom numerik.",
    ),
    SkillManifest(
        id="browser-research-assistant",
        display_name="Asisten Riset Regulasi & Web",
        version="1.0.1",
        publisher="Tim Kurasi AKSA",
        description="Riset informasi peraturan perundang-undangan, berita resmi, dan referensi akademik secara terkontrol dan aman.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=True,
        instructions_preview="Metodologi pencarian fakta dan pencatatan sumber sitasi valid tanpa menyimpan cookie atau histori sensitif.",
    ),
]


class AgentSkillsManager:
    """Manages skill discovery, quarantine extraction, static analysis, and lifecycle."""

    def __init__(self) -> None:
        self.skills_dir = settings.appdata_dir / "skills"
        self.quarantine_dir = settings.appdata_dir / "skills_quarantine"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def list_curated_catalog(self) -> list[SkillManifest]:
        return CURATED_SKILL_CATALOG

    def inspect_script_content(self, script_text: str, filename: str) -> list[str]:
        """Scan Python/shell scripts for forbidden APIs, secret scraping, or system compromises."""
        warnings: list[str] = []
        lower = script_text.lower()

        # Check for dangerous code execution
        if any(p in script_text for p in ("eval(", "exec(", "__import__(", "compile(")):
            warnings.append(f"Berkas '{filename}' memuat pemanggilan kode dinamis berbahaya (eval/exec).")

        # Check for process spawning
        if any(p in lower for p in ("os.system", "subprocess.popen", "subprocess.call", "pty.spawn")):
            warnings.append(f"Berkas '{filename}' mencoba menjalankan proses shell eksternal.")

        # Check for credential / secret harvesting
        secret_keys = ("gemini_api_key", "openai_api_key", "anthropic_api_key", "api_key", "password", "token")
        for key in secret_keys:
            if key in lower and "os.environ" in lower:
                warnings.append(f"Berkas '{filename}' terdeteksi mencoba membaca variabel lingkungan kredensial '{key}'.")

        # Check for raw socket or network scraping
        if any(p in lower for p in ("import socket", "urllib.request", "requests.post", "http.client")):
            warnings.append(f"Berkas '{filename}' terdeteksi memuat pemanggilan jaringan/socket langsung.")

        return warnings

    def parse_skill_markdown(self, content: str) -> dict[str, Any]:
        """Parse standard SKILL.md frontmatter and instructions."""
        meta: dict[str, Any] = {}
        body = content

        # Check for YAML frontmatter enclosed in ---
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if match:
            frontmatter_text = match.group(1)
            body = match.group(2)
            for line in frontmatter_text.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip().lower()] = val.strip().strip("\"'")

        return {
            "name": meta.get("name") or meta.get("id") or "skill-kustom",
            "description": meta.get("description", ""),
            "version": meta.get("version", "1.0.0"),
            "publisher": meta.get("publisher", "Komunitas"),
            "instructions": body.strip(),
        }

    async def scan_package_archive(self, zip_path: Path) -> SkillScanReport:
        """Inspect a skill ZIP archive safely in quarantine before installation."""
        if not zip_path.exists() or not zipfile.is_zipfile(zip_path):
            raise ValueError("Berkas arsip keahlian (ZIP) tidak valid atau rusak.")

        sha256 = hashlib.sha256()
        with open(zip_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        package_hash = sha256.hexdigest()

        warnings: list[str] = []
        scripts_found: list[str] = []
        total_files = 0
        total_size = 0
        skill_md_content = ""

        with zipfile.ZipFile(zip_path, "r") as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            if total_files > 300:
                warnings.append("Arsip memuat lebih dari 300 berkas (melebihi batas aman).")

            for info in infolist:
                total_size += info.file_size
                name = info.filename

                # 1. Path traversal check (Strict ../ prevention)
                if ".." in name or name.startswith("/") or name.startswith("\\"):
                    raise ValueError(f"Path traversal terdeteksi pada arsip: '{name}'")

                # 2. Reject binary executables
                lower_name = name.lower()
                forbidden_exts = (".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".vbs", ".msi")
                if any(lower_name.endswith(ext) for ext in forbidden_exts):
                    warnings.append(f"Berkas biner/skrip berisiko tinggi '{name}' ditemukan dalam arsip.")

                # 3. Read SKILL.md
                if Path(name).name.lower() == "skill.md":
                    skill_md_content = zf.read(info).decode("utf-8", errors="replace")

                # 4. Inspect python scripts
                if lower_name.endswith(".py"):
                    scripts_found.append(name)
                    script_text = zf.read(info).decode("utf-8", errors="replace")
                    file_warnings = self.inspect_script_content(script_text, name)
                    warnings.extend(file_warnings)

        if not skill_md_content:
            warnings.append("Arsip tidak memiliki berkas utama 'SKILL.md' sesuai spesifikasi Agent Skills.")

        parsed = self.parse_skill_markdown(skill_md_content) if skill_md_content else {}
        skill_id = parsed.get("name") or zip_path.stem
        risk_level = "critical" if any("berbahaya" in w or "lingkungan" in w for w in warnings) else (
            "medium" if (warnings or scripts_found) else "low"
        )

        manifest = SkillManifest(
            id=skill_id,
            display_name=parsed.get("name", skill_id),
            version=parsed.get("version", "1.0.0"),
            publisher=parsed.get("publisher", "Komunitas"),
            description=parsed.get("description", "Keahlian agen eksternal."),
            trust_level="unreviewed",
            capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
            has_scripts=len(scripts_found) > 0,
            scripts=scripts_found,
            instructions_preview=parsed.get("instructions", "")[:300],
        )

        return SkillScanReport(
            is_valid=len(warnings) == 0 or risk_level != "critical",
            package_hash=package_hash,
            total_files=total_files,
            total_size_bytes=total_size,
            risk_level=risk_level,
            security_warnings=warnings,
            manifest=manifest,
        )

    async def install_curated_skill(self, skill_id: str) -> dict[str, Any]:
        """Install a verified curated skill into SQLite in a DISABLED default state."""
        curated = next((c for c in CURATED_SKILL_CATALOG if c.id == skill_id), None)
        if not curated:
            raise KeyError(f"Keahlian terkurasi '{skill_id}' tidak ditemukan.")

        target_dir = self.skills_dir / skill_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(
            f"---\nname: {curated.display_name}\nversion: {curated.version}\npublisher: {curated.publisher}\n---\n\n"
            f"# {curated.display_name}\n\n{curated.instructions_preview}\n",
            encoding="utf-8",
        )

        fake_hash = hashlib.sha256(skill_id.encode("utf-8")).hexdigest()
        item = await db_manager.upsert_installed_skill({
            "skill_id": curated.id,
            "display_name": curated.display_name,
            "publisher": curated.publisher,
            "installed_version": curated.version,
            "package_hash": fake_hash,
            "trust_level": curated.trust_level,
            "enabled": False,  # DISABLED BY DEFAULT
        })

        await db_manager.log_permission_audit_event({
            "capability_id": "skill_installed_disabled",
            "resource_scope": skill_id,
            "decision": "allow",
            "reason_code": "INSTALL_DISABLED_BY_DEFAULT",
        })

        return item


agent_skills_manager = AgentSkillsManager()
