"""Seed default Bahasa Indonesia hierarchical agent team templates into SQLite."""

from __future__ import annotations

import json
import aiosqlite

from app.db.models import DatabaseManager, _now_iso

DEFAULT_TEAM_ID = "team_nusantara_default"

DEFAULT_AGENTS = [
    {
        "id": "agt_supervisor_utama",
        "team_id": DEFAULT_TEAM_ID,
        "parent_id": None,
        "name": "Manajer Eksekutif",
        "role_title": "Manajer Utama (Supervisor)",
        "description": (
            "Menerima instruksi pengguna, menyusun rencana kerja bertahap, "
            "mendelegasikan tugas ke sub-agen spesialis, dan merangkum hasil akhir."
        ),
        "avatar_icon": "brain-circuit",
        "tier_level": 0,
        "provider": "gemini",
        "model_id": "gemini-4-carbon",
        "temperature": 0.2,
        "max_tokens": 4096,
        "system_prompt": (
            "Anda adalah Manajer Eksekutif AKSA, asisten kerja cerdas utama yang memimpin tim sub-agen spesialis. "
            "Tugas Anda adalah memahami instruksi pengguna dalam Bahasa Indonesia, memeriksa konteks Folder Kerja aktif, "
            "membagi pekerjaan secara efisien kepada Sub-Agen yang tepat, serta memastikan setiap dokumen yang dibuat "
            "rapi, akurat, dan siap digunakan."
        ),
        "tool_categories": ["delegation", "filesystem"],
        "position_x": 400.0,
        "position_y": 60.0,
    },
    {
        "id": "agt_spesialis_office",
        "team_id": DEFAULT_TEAM_ID,
        "parent_id": "agt_supervisor_utama",
        "name": "Spesialis Administrasi & Office",
        "role_title": "Sub-Agen Pembuat Word, Excel, PPT & PDF",
        "description": (
            "Ahli membuat dan mengedit file Microsoft Excel (.xlsx dengan rumus & grafik), "
            "Word (.docx surat resmi & laporan), PowerPoint (.pptx), dan PDF di dalam Folder Kerja."
        ),
        "avatar_icon": "file-spreadsheet",
        "tier_level": 1,
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "temperature": 0.1,
        "max_tokens": 4096,
        "system_prompt": (
            "Anda adalah Spesialis Administrasi & Microsoft Office. Tugas Anda adalah membuat atau memodifikasi "
            "file Excel (.xlsx lengkap dengan rumus SUM/VLOOKUP/IF dan format Rupiah), dokumen Word (.docx dengan "
            "tata bahasa Indonesia baku dan rapi), slide presentasi PowerPoint (.pptx), serta laporan PDF di dalam "
            "Folder Kerja pengguna."
        ),
        "tool_categories": ["office_excel", "office_word", "office_ppt", "pdf_tools", "filesystem"],
        "position_x": 80.0,
        "position_y": 280.0,
    },
    {
        "id": "agt_peneliti_rag",
        "team_id": DEFAULT_TEAM_ID,
        "parent_id": "agt_supervisor_utama",
        "name": "Peneliti Dokumen & Arsip RAG",
        "role_title": "Sub-Agen Pencarian & Analisis Dokumen Lokal",
        "description": (
            "Mencari informasi akurat dari ratusan dokumen di Basis Pengetahuan (RAG) menggunakan "
            "pencarian hibrida (makna + kata kunci) secara hemat token."
        ),
        "avatar_icon": "book-open-check",
        "tier_level": 1,
        "provider": "ollama",
        "model_id": "qwen3.8:8b",
        "temperature": 0.1,
        "max_tokens": 2048,
        "system_prompt": (
            "Anda adalah Peneliti Dokumen & Arsip RAG. Tugas Anda adalah mencari dan mengekstrak fakta, angka, "
            "nomor surat, atau kutipan penting dari dokumen-dokumen di dalam Folder Kerja pengguna. Berikan ringkasan "
            "yang padat beserta nama file dan halaman sumbernya agar menghemat token bagi Manajer Eksekutif."
        ),
        "tool_categories": ["rag_search", "filesystem", "pdf_tools"],
        "position_x": 400.0,
        "position_y": 280.0,
    },
    {
        "id": "agt_operator_pc",
        "team_id": DEFAULT_TEAM_ID,
        "parent_id": "agt_supervisor_utama",
        "name": "Operator PC & Automasi Sistem",
        "role_title": "Sub-Agen Kontrol Aplikasi, Skrip Python & Layar",
        "description": (
            "Mengoperasikan aplikasi PC secara langsung (Windows COM / AppleScript), "
            "menjalankan skrip Python otomatis (uv), dan kontrol layar visual (Computer Use)."
        ),
        "avatar_icon": "monitor-cog",
        "tier_level": 1,
        "provider": "anthropic",
        "model_id": "claude-sonnet-5-5",
        "temperature": 0.1,
        "max_tokens": 4096,
        "system_prompt": (
            "Anda adalah Operator PC & Automasi Sistem. Anda bertugas menjalankan otomatisasi tingkat lanjut di PC "
            "pengguna, termasuk mengontrol aplikasi yang sedang terbuka, menulis dan mengeksekusi skrip Python di "
            "ruang terisolasi (uv), serta mengoperasikan antarmuka aplikasi desktop dengan aman di bawah izin pengguna."
        ),
        "tool_categories": ["os_automation", "uv_python", "computer_use", "filesystem"],
        "position_x": 720.0,
        "position_y": 280.0,
    },
]


async def seed_default_indonesian_team(db: DatabaseManager) -> None:
    """Ensure the default Indonesian hierarchical agent team exists on first launch."""
    async with aiosqlite.connect(db.db_path) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM agent_teams")
        count_row = await cursor.fetchone()
        if count_row and count_row[0] > 0:
            return

        now = _now_iso()
        await conn.execute(
            """
            INSERT INTO agent_teams (id, name, description, is_default, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            """,
            (
                DEFAULT_TEAM_ID,
                "Tim Produktivitas Kantor Indonesia",
                "Tim agen bertingkat siap pakai untuk pengolahan dokumen Office, riset arsip RAG, dan automasi PC.",
                now,
                now,
            ),
        )

        for agent in DEFAULT_AGENTS:
            await conn.execute(
                """
                INSERT INTO agents (
                    id, team_id, parent_id, name, role_title, description,
                    avatar_icon, tier_level, provider, model_id, temperature,
                    max_tokens, system_prompt, tool_categories_json, position_x, position_y, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent["id"],
                    agent["team_id"],
                    agent["parent_id"],
                    agent["name"],
                    agent["role_title"],
                    agent["description"],
                    agent["avatar_icon"],
                    agent["tier_level"],
                    agent["provider"],
                    agent["model_id"],
                    agent["temperature"],
                    agent["max_tokens"],
                    agent["system_prompt"],
                    json.dumps(agent["tool_categories"]),
                    agent["position_x"],
                    agent["position_y"],
                    now,
                ),
            )
        await conn.commit()

