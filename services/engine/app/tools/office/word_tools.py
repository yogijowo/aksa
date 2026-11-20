"""Tier 1 Microsoft Word Engine powered by python-docx."""

from __future__ import annotations

import asyncio
from typing import Any

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.core.sandbox import RiskLevel, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.tools.registry import ToolResult, tool_registry


def _sync_word_inspect(file_path: str) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="read")
    if not resolved.exists():
        return ToolResult(
            success=False,
            summary=f"Dokumen Word '{resolved.name}' tidak ditemukan.",
            token_estimate=12,
        )

    doc = docx.Document(str(resolved))
    headings: list[str] = []
    paragraphs_preview: list[str] = []

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if p.style and "Heading" in p.style.name:
            headings.append(f"{p.style.name}: {text}")
        elif len(paragraphs_preview) < 8:
            paragraphs_preview.append(text[:220])

    tables_preview: list[list[list[str]]] = []
    for tbl in doc.tables[:5]:
        t_rows = []
        for row in tbl.rows[:5]:
            t_rows.append([cell.text.strip() for cell in row.cells])
        tables_preview.append(t_rows)

    data = {
        "file_path": str(resolved),
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "headings": headings,
        "paragraphs_preview": paragraphs_preview,
        "tables_preview": tables_preview,
    }
    summary = (
        f"Inspeksi Word '{resolved.name}': {len(doc.paragraphs)} paragraf, "
        f"{len(headings)} sub-judul, dan {len(doc.tables)} tabel."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data=data,
        token_estimate=token_optimizer.estimate_tokens(str(data)),
    )


async def word_inspect(file_path: str) -> ToolResult:
    """Extract document outline, headings, paragraphs preview, and tables from a Word (.docx) file."""
    return await asyncio.to_thread(_sync_word_inspect, file_path)


def _sync_word_create_document(
    file_path: str,
    title: str,
    sections: list[dict[str, Any]] | None = None,
    style_preset: str = "laporan_kerja",
    header_organization: str | None = None,
    header_address: str | None = None,
    **kwargs: Any,
) -> ToolResult:
    # Accept file_name as alias for file_path if passed by LLM
    target_path = file_path or kwargs.get("file_name", "Dokumen.docx")
    resolved = sandbox_manager.validate_path(target_path, mode="write")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        sandbox_manager.backup_before_modify(resolved)

    doc = docx.Document()

    # Configure default Normal style font
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(11)

    # Optional official letterhead (kop surat) - ONLY inserted if user or agent explicitly provides header_organization
    if header_organization:
        kop = doc.add_paragraph()
        kop.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_kop = kop.add_run(f"{header_organization.strip()}\n")
        run_kop.bold = True
        run_kop.font.size = Pt(14)
        run_kop.font.color.rgb = RGBColor(30, 41, 59)
        if header_address:
            sub_kop = kop.add_run(f"{header_address.strip()}\n")
            sub_kop.font.size = Pt(9.5)
            sub_kop.font.color.rgb = RGBColor(100, 116, 139)

    heading = doc.add_heading(title, level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER if (style_preset == "surat_resmi" or header_organization) else WD_ALIGN_PARAGRAPH.LEFT

    if not sections:
        sections = [
            {
                "heading": "Bagian Utama",
                "paragraphs": [
                    f"Draf dokumen '{title}' telah disiapkan. Lengkapi isi dan sesuaikan klausul atau ketentuan sesuai kebutuhan kerja Anda.",
                ],
            }
        ]

    for sec in sections:
        sec_heading = sec.get("heading")
        if sec_heading:
            doc.add_heading(str(sec_heading), level=1)

        for para_text in sec.get("paragraphs", []):
            doc.add_paragraph(str(para_text))

        for bullet_text in sec.get("bullets", []):
            doc.add_paragraph(str(bullet_text), style="List Bullet")

        tbl_spec = sec.get("table")
        if isinstance(tbl_spec, dict):
            headers = tbl_spec.get("headers", [])
            rows = tbl_spec.get("rows", [])
            if headers:
                table = doc.add_table(rows=1, cols=len(headers))
                table.style = "Table Grid"
                hdr_cells = table.rows[0].cells
                for idx, h_text in enumerate(headers):
                    hdr_cells[idx].text = str(h_text)
                for row_data in rows:
                    row_cells = table.add_row().cells
                    for idx, val in enumerate(row_data[: len(headers)]):
                        row_cells[idx].text = str(val)

    doc.save(str(resolved))
    summary = (
        f"Dokumen Word '{resolved.name}' (Preset: {style_preset}) berhasil dibuat "
        f"dengan {len(sections)} bagian."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"file_path": str(resolved), "title": title, "style_preset": style_preset},
        artifacts=[str(resolved)],
        token_estimate=40,
    )


async def word_create_document(
    file_path: str,
    title: str,
    sections: list[dict[str, Any]] | None = None,
    style_preset: str = "laporan_kerja",
    header_organization: str | None = None,
    header_address: str | None = None,
    **kwargs: Any,
) -> ToolResult:
    """Create a formatted Microsoft Word (.docx) document with Indonesian business presets."""
    return await asyncio.to_thread(
        _sync_word_create_document,
        file_path=file_path,
        title=title,
        sections=sections,
        style_preset=style_preset,
        header_organization=header_organization,
        header_address=header_address,
        **kwargs,
    )


def _replace_in_paragraph(paragraph: Any, replacements: dict[str, str]) -> int:
    count = 0
    full_text = paragraph.text
    modified = full_text
    for key, val in replacements.items():
        placeholder = key if key.startswith("{{") else f"{{{{{key}}}}}"
        if placeholder in modified:
            count += modified.count(placeholder)
            modified = modified.replace(placeholder, str(val))
    if count > 0:
        paragraph.text = modified
    return count


def _sync_word_fill_template(
    template_path: str,
    output_path: str,
    replacements: dict[str, str],
) -> ToolResult:
    src = sandbox_manager.validate_path(template_path, mode="read")
    dst = sandbox_manager.validate_path(output_path, mode="write")
    if not src.exists():
        return ToolResult(
            success=False,
            summary=f"File template Word '{src.name}' tidak ditemukan.",
            token_estimate=12,
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        sandbox_manager.backup_before_modify(dst)

    doc = docx.Document(str(src))
    total_replaced = 0

    for p in doc.paragraphs:
        total_replaced += _replace_in_paragraph(p, replacements)

    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    total_replaced += _replace_in_paragraph(p, replacements)

    doc.save(str(dst))
    summary = (
        f"Template Word '{src.name}' berhasil diisi ({total_replaced} placeholder diganti) "
        f"dan disimpan ke '{dst.name}'."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={
            "template_path": str(src),
            "output_path": str(dst),
            "replacements_applied": total_replaced,
        },
        artifacts=[str(dst)],
        token_estimate=35,
    )


async def word_fill_template(
    template_path: str,
    output_path: str,
    replacements: dict[str, str],
) -> ToolResult:
    """Fill `{{placeholder}}` tags inside an existing Word (.docx) template and save to output_path."""
    return await asyncio.to_thread(
        _sync_word_fill_template, template_path, output_path, replacements
    )


def register_word_tools() -> None:
    tool_registry.register(
        name="word_inspect",
        category="office_word",
        description="Ekstrak outline, daftar judul, paragraf, dan tabel dari dokumen Word (.docx).",
        handler=word_inspect,
        risk_level=RiskLevel.LOW,
        parameters_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Jalur berkas .docx yang ingin diperiksa di dalam Folder Kerja.",
                }
            },
            "required": ["file_path"],
        },
    )
    tool_registry.register(
        name="word_create_document",
        category="office_word",
        description="Buat dokumen Microsoft Word (.docx) resmi seperti surat bisnis, nota kesepahaman (MoU), laporan, atau SOP.",
        handler=word_create_document,
        risk_level=RiskLevel.LOW,
        parameters_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Nama file atau jalur berkas .docx yang akan dibuat di folder kerja (contoh: 'Surat_Perjanjian_MoU.docx').",
                },
                "title": {
                    "type": "string",
                    "description": "Judul utama dokumen yang dicetak di bagian atas (contoh: 'MEMORANDUM OF UNDERSTANDING (MoU)').",
                },
                "sections": {
                    "type": "array",
                    "description": "Daftar bab/bagian isi dokumen secara terstruktur.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {
                                "type": "string",
                                "description": "Judul bab atau klausul (contoh: 'Pasal 1: Maksud dan Tujuan').",
                            },
                            "paragraphs": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Daftar paragraf isi teks di dalam bab ini.",
                            },
                            "bullets": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Poin-poin rincian daftar (opsional).",
                            },
                            "table": {
                                "type": "object",
                                "properties": {
                                    "headers": {"type": "array", "items": {"type": "string"}},
                                    "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                                },
                                "description": "Tabel data jika bab ini memuat tabel (opsional).",
                            },
                        },
                        "required": ["heading"],
                    },
                },
                "style_preset": {
                    "type": "string",
                    "enum": ["surat_resmi", "laporan_kerja", "standar", "sop"],
                    "description": "Preset gaya tata letak dokumen (default: 'laporan_kerja').",
                },
                "header_organization": {
                    "type": "string",
                    "description": "Nama instansi/perusahaan untuk kop surat resmi jika ada (opsional).",
                },
                "header_address": {
                    "type": "string",
                    "description": "Alamat instansi untuk kop surat resmi jika ada (opsional).",
                },
            },
            "required": ["file_path", "title"],
        },
    )
    tool_registry.register(
        name="word_fill_template",
        category="office_word",
        description="Isi placeholder {{nama}} pada template surat/dokumen Word (.docx) tanpa merusak format.",
        handler=word_fill_template,
        risk_level=RiskLevel.MEDIUM,
        parameters_schema={
            "type": "object",
            "properties": {
                "template_path": {
                    "type": "string",
                    "description": "Jalur berkas template .docx.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Jalur berkas tujuan penyimpanan .docx.",
                },
                "replacements": {
                    "type": "object",
                    "description": "Pemetaan placeholder ke nilai teks pengganti, contoh: {'nama': 'Budi', 'jabatan': 'Direktur'}.",
                },
            },
            "required": ["template_path", "output_path", "replacements"],
        },
    )


register_word_tools()

