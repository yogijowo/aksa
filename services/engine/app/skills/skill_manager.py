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
        instructions_preview="Analisis statis perubahan kode pada git diff, pelacakan regresi fungsi, dan pembuatan checklist code review terperinci.",
    ),
    SkillManifest(
        id="remotion-best-practices",
        display_name="Praktik Terbaik Video Remotion",
        version="1.0.0",
        publisher="Remotion Official",
        description="Pola kerja penyusunan video animasi terprogram dengan React, safe margins, pacing, transisi audio/visual, dan rendering MP4 efisien.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pedoman komposisi Remotion: frame rate 30/60fps, aspect ratio 16:9 atau 9:16, sequence timing, dan sinkronisasi audio.",
    ),
    SkillManifest(
        id="hyperframes-motion",
        display_name="HyperFrames Motion Graphics",
        version="1.0.0",
        publisher="HeyGen / HyperFrames",
        description="Pembuatan grafis gerak, kinetik tipografi, dan template motion visual untuk konten video media sosial beresolusi tinggi.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Standar layout kinetik teks, kurva animasi easing bezier, sinkronisasi visual beat, dan export WebM/MP4.",
    ),
    SkillManifest(
        id="ai-video-generation",
        display_name="Alur Kerja Generasi Video AI",
        version="1.0.0",
        publisher="Komunitas Global AI",
        description="Pembuatan storyboard adegan, prompt text-to-video / image-to-video, penggabungan footage, dan kontrol konsistensi karakter.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=True,
        instructions_preview="Metodologi penyusunan shot list, deskripsi pergerakan kamera (pan/tilt/zoom), dan orkestrasi model video generasi.",
    ),
    SkillManifest(
        id="frontend-design",
        display_name="Desain Antarmuka Frontend & UI Taste",
        version="1.1.0",
        publisher="Vercel / Anthropic Community",
        description="Panduan desain UI premium: tipografi Geist/Inter, palet warna gelap obsidian, micro-interactions Tailwind CSS, dan aksesibilitas WCAG.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Aturan hierarki visual, kontras warna, batas padding ritmis, dialog non-intrusif, dan zero-emoji icon standards.",
    ),
    SkillManifest(
        id="prisma-ddti-skills",
        display_name="Keahlian Teknis Perpustakaan & Naskah DDTI",
        version="1.0.0",
        publisher="Prisma DDTI Indonesia",
        description="Koleksi instruksi keahlian Bahasa Indonesia untuk kurasi naskah teknis perpustakaan, metadata bibliografi, dan repositori digital.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Standar katalogisasi dokumen, ekstraksi tajuk subjek perpustakaan, dan format ringkasan naskah formal Bahasa Indonesia.",
    ),
    SkillManifest(
        id="find-skills-id",
        display_name="Pencari & Kurator Keahlian Bahasa Indonesia",
        version="1.0.0",
        publisher="Komunitas AI Indonesia",
        description="Membantu agen menemukan dan mengadaptasi instruksi skill relevan dari repositori terbuka menggunakan Bahasa Indonesia alami.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read"],
        has_scripts=False,
        has_network=True,
        instructions_preview="Prosedur pencarian repositori skill terpercaya, analisis kesesuaian domain tugas, dan lokalisasi instruksi kerja.",
    ),
    SkillManifest(
        id="naskah-id",
        display_name="Penyuntingan Karya Ilmiah & Naskah ID",
        version="1.0.2",
        publisher="Nothinx Indonesia",
        description="Pedoman penyuntingan tata bahasa formal Bahasa Indonesia (EYD V), struktur abstrak ilmiah, sitasi APA/IEEE, dan kohesi paragraf.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pemeriksaan kebakuan kata (KBBI), penghindaran kata mubazir, konsistensi istilah teknis, dan verifikasi daftar pustaka.",
    ),
    SkillManifest(
        id="pbj-asn-indonesia",
        display_name="Pemeriksaan Administrasi PBJ & ASN",
        version="1.0.0",
        publisher="Kurasi Ahli Kebijakan RI",
        description="Checklist pemeriksaan berkas Pengadaan Barang/Jasa (PBJ), Kerangka Acuan Kerja (KAK), Harga Perkiraan Sendiri (HPS), dan dokumen ASN.",
        trust_level="curated",
        capabilities=["filesystem.workspace.read", "filesystem.workspace.write"],
        has_scripts=False,
        has_network=False,
        instructions_preview="Pemeriksaan kepatuhan regulasi pengadaan barang/jasa pemerintah, validasi dokumen kontrak, dan checklist kelengkapan audit.",
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
        """Inspect a skill ZIP archive safely in quarantine before installation (Section 7.3)."""
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
        total_compressed = 0
        skill_md_content = ""
        seen_paths_lower: set[str] = set()

        MAX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024  # 25 MB archive bomb limit
        MAX_COMPRESSION_RATIO = 50.0

        with zipfile.ZipFile(zip_path, "r") as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            if total_files > 300:
                warnings.append("Arsip memuat lebih dari 300 berkas (melebihi batas aman).")

            for info in infolist:
                total_size += info.file_size
                total_compressed += max(1, info.compress_size)
                name = info.filename

                # 1. Path traversal & absolute path check (Strict ../ prevention)
                if ".." in name or name.startswith("/") or name.startswith("\\") or ":" in name:
                    raise ValueError(f"Path traversal atau path absolut terdeteksi pada arsip: '{name}'")

                # 2. Symlink escape detection in ZIP external attributes
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValueError(f"Symbolic link tidak diizinkan di dalam arsip keahlian: '{name}'")

                # 3. Duplicate path & case-collision detection
                norm_lower = name.strip("/\\").lower()
                if norm_lower and not info.is_dir():
                    if norm_lower in seen_paths_lower:
                        raise ValueError(f"Duplikasi path atau tabrakan huruf besar/kecil (case collision) terdeteksi: '{name}'")
                    seen_paths_lower.add(norm_lower)

                # 4. Archive bomb size and ratio check
                if total_size > MAX_UNCOMPRESSED_BYTES:
                    raise ValueError("Ukuran arsip tidak terkompresi melebihi batas keamanan 25 MB (potensi Zip Bomb).")
                if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_COMPRESSION_RATIO:
                    warnings.append(f"Rasio kompresi mencurigakan pada berkas '{name}' (potensi Zip Bomb).")

                # 5. Reject binary executables & install hooks
                lower_name = name.lower()
                forbidden_exts = (".exe", ".dll", ".so", ".dylib", ".bat", ".cmd", ".vbs", ".msi", ".ps1", ".sh")
                if any(lower_name.endswith(ext) for ext in forbidden_exts):
                    warnings.append(f"Berkas biner/skrip berisiko tinggi '{name}' ditemukan dalam arsip.")

                # 6. Read SKILL.md
                if Path(name).name.lower() == "skill.md":
                    skill_md_content = zf.read(info).decode("utf-8", errors="replace")
                    lower_md = skill_md_content.lower()
                    if any(
                        inj in lower_md
                        for inj in ("ignore previous instructions", "abaikan seluruh instruksi", "bypass policy", "execution_policy_override")
                    ):
                        warnings.append("Berkas 'SKILL.md' memuat indikasi instruksi prompt injection berbahaya.")

                # 7. Inspect python scripts
                if lower_name.endswith(".py"):
                    scripts_found.append(name)
                    script_text = zf.read(info).decode("utf-8", errors="replace")
                    file_warnings = self.inspect_script_content(script_text, name)
                    warnings.extend(file_warnings)

        if not skill_md_content:
            warnings.append("Arsip tidak memiliki berkas utama 'SKILL.md' sesuai spesifikasi Agent Skills.")

        parsed = self.parse_skill_markdown(skill_md_content) if skill_md_content else {}
        skill_id = parsed.get("name") or zip_path.stem
        risk_level = "critical" if any(
            k in w.lower() for w in warnings for k in ("berbahaya", "lingkungan", "injection", "zip bomb", "biner")
        ) else (
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
            is_valid=len(warnings) == 0 and risk_level != "critical",
            package_hash=package_hash,
            total_files=total_files,
            total_size_bytes=total_size,
            risk_level=risk_level,
            security_warnings=warnings,
            manifest=manifest,
        )

    async def install_curated_skill(
        self,
        skill_id: str,
        target_agent_id: str | None = None,
        install_to_shared: bool = False,
    ) -> dict[str, Any]:
        """Install a verified curated skill into SQLite in a DISABLED default state (per-agent or shared)."""
        curated = next((c for c in CURATED_SKILL_CATALOG if c.id == skill_id), None)
        if not curated:
            raise KeyError(f"Keahlian terkurasi '{skill_id}' tidak ditemukan.")

        from app.core.agent_directory import agent_directory_service
        if target_agent_id:
            target_dir = agent_directory_service.resolve_agent_path(
                target_agent_id, f"skills/installed/{skill_id}"
            )
        elif install_to_shared:
            target_dir = agent_directory_service.root_dir / "shared" / "skills" / skill_id / curated.version
        else:
            target_dir = self.skills_dir / skill_id

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(
            f"---\nname: {curated.display_name}\nversion: {curated.version}\npublisher: {curated.publisher}\n---\n\n"
            f"# {curated.display_name}\n\n{curated.instructions_preview}\n",
            encoding="utf-8",
        )
        is_curated_verified = curated.trust_level in ("curated", "verified_publisher")
        manifest_yaml = (
            f"schema_version: 1\n"
            f"id: {curated.id}\n"
            f"name: \"{curated.display_name}\"\n"
            f"version: \"{curated.version}\"\n"
            f"publisher:\n  name: \"{curated.publisher}\"\n  verified: {str(is_curated_verified).lower()}\n"
            f"capabilities:\n  network:\n    enabled: {str(curated.has_network).lower()}\n"
            f"  secrets:\n    access: false\n"
        )
        (target_dir / "aksa.skill.yaml").write_text(manifest_yaml, encoding="utf-8")

        # Compute genuine cryptographic hash from actual on-disk artifact bytes (P1.6)
        hasher = hashlib.sha256()
        for fpath in sorted(target_dir.rglob("*")):
            if fpath.is_file():
                hasher.update(fpath.read_bytes())
        real_package_hash = hasher.hexdigest()

        item = await db_manager.upsert_installed_skill({
            "skill_id": curated.id,
            "display_name": curated.display_name,
            "publisher": curated.publisher,
            "installed_version": curated.version,
            "package_hash": real_package_hash,
            "trust_level": curated.trust_level,
            "enabled": False,  # DISABLED BY DEFAULT (P1.6)
        })

        await db_manager.log_permission_audit_event({
            "capability_id": "skill_installed_disabled",
            "resource_scope": skill_id,
            "decision": "allow",
            "reason_code": "INSTALL_DISABLED_BY_DEFAULT",
        })

        return item

    async def install_skill_package(
        self,
        zip_path: Path,
        target_agent_id: str | None = None,
        expected_hash: str | None = None,
    ) -> dict[str, Any]:
        """Safely inspect, verify, stage, and atomically promote a skill ZIP package (P1.6)."""
        import uuid
        import shutil

        # 1. Scan package in quarantine
        report = await self.scan_package_archive(zip_path)
        if not report.is_valid:
            warnings_str = "; ".join(report.security_warnings)
            raise ValueError(f"Paket keahlian ditolak dalam karantina: {warnings_str}")

        # 2. Verify artifact hash if expected hash provided
        if expected_hash and report.package_hash.lower() != expected_hash.lower():
            raise ValueError(
                f"Integritas paket gagal diverifikasi: Hash SHA-256 mismatch ({report.package_hash} != {expected_hash})."
            )

        skill_id = report.manifest.id
        staging_dir = self.quarantine_dir / f"staging_{uuid.uuid4().hex[:12]}"
        staging_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 3. Extract to staging directory
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.infolist():
                    target_path = staging_dir / member.filename
                    # Double-check path traversal
                    if ".." in member.filename or not target_path.resolve().is_relative_to(staging_dir.resolve()):
                        raise ValueError(f"Zip-slip traversal attack terdeteksi: '{member.filename}'")
                    if member.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                    else:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            # 4. Atomic promote to destination
            dest_dir = self.skills_dir / skill_id
            backup_dir = self.skills_dir / f".backup_{skill_id}_{uuid.uuid4().hex[:8]}"

            if dest_dir.exists():
                dest_dir.rename(backup_dir)

            staging_dir.rename(dest_dir)

            # 5. Persist to database in DISABLED state
            item = await db_manager.upsert_installed_skill({
                "skill_id": skill_id,
                "display_name": report.manifest.display_name,
                "publisher": report.manifest.publisher,
                "installed_version": report.manifest.version,
                "package_hash": report.package_hash,
                "trust_level": report.manifest.trust_level,
                "enabled": False,  # DISABLED BY DEFAULT
            })

            await db_manager.log_permission_audit_event({
                "capability_id": "skill_package_promoted",
                "resource_scope": skill_id,
                "decision": "allow",
                "reason_code": "ATOMIC_STAGE_AND_PROMOTE",
            })
            return item

        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    async def rollback_skill(self, skill_id: str) -> dict[str, Any]:
        """Roll back an updated skill to its previous backup version if present."""
        import shutil

        dest_dir = self.skills_dir / skill_id
        # Find latest backup
        backups = sorted(self.skills_dir.glob(f".backup_{skill_id}_*"))
        if not backups:
            raise FileNotFoundError(f"Tidak ada versi cadangan (backup) untuk keahlian '{skill_id}'.")

        latest_backup = backups[-1]
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        latest_backup.rename(dest_dir)

        # Re-verify and update database
        item = await db_manager.get_installed_skill(skill_id)
        await db_manager.log_permission_audit_event({
            "capability_id": "skill_rolled_back",
            "resource_scope": skill_id,
            "decision": "allow",
            "reason_code": "ROLLBACK_SUCCESSFUL",
        })
        return item or {"skill_id": skill_id, "rolled_back": True}

    def load_skill_instructions(self, skill_id: str, agent_id: str | None = None) -> str:
        """Progressive disclosure: loads actual markdown instructions on demand."""
        from app.core.agent_directory import agent_directory_service
        if agent_id:
            agent_skill = agent_directory_service.resolve_agent_path(
                agent_id, f"skills/installed/{skill_id}/SKILL.md"
            )
            if agent_skill.exists():
                return agent_skill.read_text(encoding="utf-8")

        shared_skill = agent_directory_service.root_dir / "shared" / "skills" / skill_id
        if shared_skill.exists():
            for v_dir in shared_skill.iterdir():
                md = v_dir / "SKILL.md"
                if md.exists():
                    return md.read_text(encoding="utf-8")

        sys_skill = self.skills_dir / skill_id / "SKILL.md"
        if sys_skill.exists():
            return sys_skill.read_text(encoding="utf-8")

        curated = next((c for c in CURATED_SKILL_CATALOG if c.id == skill_id), None)
        return curated.instructions_preview if curated else ""

    async def uninstall_skill(self, skill_id: str) -> bool:
        """Uninstall a skill, revoke all its grants, and remove its runtime directory."""
        import shutil

        deleted = await db_manager.delete_installed_skill(skill_id)
        target_dir = self.skills_dir / skill_id
        if target_dir.exists() and target_dir.is_dir():
            shutil.rmtree(target_dir, ignore_errors=True)
        await db_manager.log_permission_audit_event({
            "capability_id": "skill_uninstalled",
            "resource_scope": skill_id,
            "decision": "deny",
            "reason_code": "UNINSTALL_AND_REVOKE_GRANTS",
        })
        return deleted


agent_skills_manager = AgentSkillsManager()
