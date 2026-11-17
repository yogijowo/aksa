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
        id="excel-financial-modeler",
        display_name="Pemodelan Finansial & Valuasi Excel",
        version="1.2.0",
        publisher="Anthropic Community / Kurasi AKSA",
        description="Analisis laporan laba rugi, proyeksi arus kas bebas (DCF), valuasi rasio keuangan korporat, dan format mata uang Rupiah standar.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/calculate_dcf.py", "scripts/format_sheets.py"],
        instructions_preview="Keahlian merancang model keuangan tiga laporan (Income Statement, Balance Sheet, Cash Flow) dengan formula dinamis dan sensitivitas.",
    ),
    SkillManifest(
        id="word-legal-contract",
        display_name="Penyusun Kontrak & Perjanjian MoU",
        version="1.1.0",
        publisher="Microsoft Ecosystem / Kurasi AKSA",
        description="Perancangan draf Perjanjian Kerjasama (MoU), Perjanjian Kerahasiaan (NDA), dan Kontrak Kerja Karyawan sesuai KUHPerdata.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pedoman penyusunan klausul hukum formal, hak & kewajiban para pihak, force majeure, dan mekanisme penyelesaian sengketa.",
    ),
    SkillManifest(
        id="official-indonesian-correspondence",
        display_name="Tata Naskah Dinas & Surat Resmi RI",
        version="1.0.5",
        publisher="Tim Kurasi AKSA",
        description="Penyusunan format Nota Dinas, Surat Keputusan, Surat Perintah Tugas (SPT), dan Undangan Resmi berstandar administrasi pemerintahan & BUMN.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pedoman tata persuratan resmi, struktur kop dinas standar, nomor surat, perihal, rujukan regulasi, dan tembusan.",
    ),
    SkillManifest(
        id="pdf-table-extractor",
        display_name="Ekstraktor Tabel Dokumen PDF",
        version="1.1.0",
        publisher="Open Agent Skills",
        description="Membaca dan memisahkan struktur tabel berulang di dalam dokumen PDF lampiran, tagihan, dan mutasi rekening menjadi spreadsheet terstruktur.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/parse_pdf_tables.py"],
        instructions_preview="Ekstraksi tabel multi-halaman berbasis PyMuPDF dengan auto-mapping kolom numerik dan pembersihan artefak spasi.",
    ),
    SkillManifest(
        id="python-data-analyst",
        display_name="Analisis Data Eksploratif (EDA) & Visualisasi",
        version="1.3.0",
        publisher="CrewAI Community",
        description="Pembersihan dataset CSV/Parquet, deteksi nilai kosong/outlier, korelasi statistik, dan generasi grafik visual Matplotlib/Seaborn resolusi tinggi.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/data_cleaner.py", "scripts/plot_summary.py"],
        instructions_preview="Alur kerja eksplorasi data ilmiah: membaca data, ringkasan statistik deskriptif, imputasi data, dan visualisasi distribusi.",
    ),
    SkillManifest(
        id="browser-research-assistant",
        display_name="Asisten Riset Regulasi & Web Terverifikasi",
        version="1.1.2",
        publisher="Claude Research Team",
        description="Penelusuran peraturan perundang-undangan, berita resmi, dan referensi akademik secara terkontrol tanpa menyimpan cookie atau histori sensitif.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=True,
        instructions_preview="Metodologi pencarian fakta dan pencatatan sumber sitasi valid, cross-check regulasi, dan sintesis ringkasan eksekutif.",
    ),
    SkillManifest(
        id="git-code-reviewer",
        display_name="Tinjauan Mutu Kode Git & Audit Standar",
        version="1.0.8",
        publisher="GitHub Engineering",
        description="Pemeriksaan diff commit Git, deteksi potensi bug konkurensi, kebocoran memori, pelanggaran gaya penulisan, dan saran refactoring modular.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Evaluasi kode berdasarkan SOLID principles, clean architecture, penanganan eksepsi eksplisit, dan keamanan input pengguna.",
    ),
    SkillManifest(
        id="sql-query-optimizer",
        display_name="Analisis & Optimasi Kueri SQL Relasional",
        version="1.1.0",
        publisher="LangChain Ecosystem",
        description="Membaca skema DDL relasional, memeriksa rencana eksekusi EXPLAIN, merekomendasikan indeks B-Tree/Composite, dan merevisi kueri lambat.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Metode deteksi sequential scan berlebih, N+1 query problem, indexing strategi, dan penyusunan kueri agregasi efisien.",
    ),
    SkillManifest(
        id="indonesian-tax-calculator",
        display_name="Kalkulator PPh 21 & Simulasi Pajak Indonesia",
        version="1.0.4",
        publisher="Tim Kurasi AKSA",
        description="Perhitungan tarif efektif PPh 21 bulanan/tahunan (TER PP 58/2023), PPh 23 jasa, simulasi PPN 11%, dan rekap bukti potong SPT Tahunan.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/pph21_calculator.py"],
        instructions_preview="Perhitungan komprehensif penghasilan kena pajak (PKP), PTKP status (TK/0 sampai K/3), tarif TER A/B/C, dan rekonsiliasi Desember.",
    ),
    SkillManifest(
        id="meeting-minutes-generator",
        display_name="Notula Rapat Eksekutif & Matriks Tindak Lanjut",
        version="1.2.1",
        publisher="Microsoft Semantic Kernel",
        description="Mengubah transkrip audio atau catatan rapat mentah menjadi notula formal, ringkasan konsensus eksekutif, PIC, dan tenggat waktu tugas.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Format terstruktur: Tujuan Rapat, Daftar Kehadiran, Poin Pembahasan Pokok, Keputusan Final, dan Matriks Action Items.",
    ),
    SkillManifest(
        id="powerpoint-pitch-deck",
        display_name="Arsitek Presentasi & Slide Pitching",
        version="1.0.3",
        publisher="Open Agent Skills",
        description="Menyusun alur narasi presentasi (Problem, Solution, Market Size, Traction, Business Model) dan menghasilkan berkas .pptx rapi.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/generate_presentation.py"],
        instructions_preview="Pedoman visualisasi piramida Minto, pemilihan headline tegas, eliminasi teks padat, dan penempatan callout statistik.",
    ),
    SkillManifest(
        id="academic-paper-summarizer",
        display_name="Telaah Jurnal Ilmiah & Sitasi APA/IEEE",
        version="1.1.5",
        publisher="DeepMind Research Tools",
        description="Ekstraksi metodologi penelitian, parameter dataset, perbandingan benchmark, limitasi studi, dan pemformatan sitasi BibTeX/APA 7th.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Sintesis literatur ilmiah: abstraksi kontribusi utama, validasi metodologi statistik, dan perbandingan dengan state-of-the-art.",
    ),
    SkillManifest(
        id="csv-reconciliation-engine",
        display_name="Rekonsiliasi Transaksi Bank & Audit Saldo",
        version="1.0.7",
        publisher="Open Agent Skills",
        description="Mencocokkan baris transaksi rekening koran bank dengan buku besar akuntansi internal, mendeteksi selisih nominal, dan mencatat transaksi tak terdata.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/reconcile_records.py"],
        instructions_preview="Pencocokan fuzzy string nomor referensi pembayaran, toleransi tanggal transaksi (t+2), dan pembagian kategori unallocated funds.",
    ),
    SkillManifest(
        id="security-audit-scanner",
        display_name="Audit Konfigurasi Keamanan & Header HTTP",
        version="1.0.2",
        publisher="ProjectDiscovery",
        description="Pemeriksaan keamanan konfigurasi web server, header pertahanan (HSTS, CSP, X-Frame-Options), dan audit izin berkas pada workspace proyek.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read"],
        has_scripts=False,
        has_network=True,
        instructions_preview="Inspeksi postur keamanan defensif: validasi header keamanan browser, audit port terbuka lokal, dan sanitasi berkas .env terbuka.",
    ),
    SkillManifest(
        id="system-admin-diagnostics",
        display_name="Diagnostik Kesehatan OS & Utilisasi Sistem",
        version="1.1.0",
        publisher="Open Source Admin",
        description="Pemeriksaan status utilisasi memori RAM, kapasitas partisi hard drive/SSD, kesehatan background service, dan pelaporan anomali sistem.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read"],
        has_scripts=True,
        has_network=False,
        scripts=["scripts/diagnose_health.py"],
        instructions_preview="Inspeksi metrik performa komputer tanpa menjalankan perintah destruktif, memberikan rekomendasi pembersihan cache aman.",
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
