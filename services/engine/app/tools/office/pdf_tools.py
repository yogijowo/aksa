"""Tier 1 PDF Tools powered by PyMuPDF (fitz) and ReportLab."""

from __future__ import annotations

import asyncio
from typing import Any

import pymupdf as fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.sandbox import RiskLevel, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.tools.registry import ToolResult, tool_registry


def _sync_pdf_extract_markdown(
    file_path: str,
    pages: list[int] | None = None,
) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="read")
    if not resolved.exists():
        return ToolResult(
            success=False,
            summary=f"File PDF '{resolved.name}' tidak ditemukan.",
            token_estimate=12,
        )

    doc = fitz.open(str(resolved))
    total_pages = len(doc)
    selected_indices = (
        [p - 1 for p in pages if 1 <= p <= total_pages]
        if pages
        else list(range(min(total_pages, 15)))
    )

    md_chunks: list[str] = []
    for idx in selected_indices:
        page = doc[idx]
        text = page.get_text("text").strip()
        md_chunks.append(f"### Halaman {idx + 1}\n{text}")

    doc.close()
    markdown_text = "\n\n".join(md_chunks)
    summary = (
        f"Berhasil mengekstrak {len(selected_indices)} dari {total_pages} halaman PDF '{resolved.name}' ke Markdown."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={
            "file_path": str(resolved),
            "total_pages": total_pages,
            "extracted_pages": [i + 1 for i in selected_indices],
            "markdown": markdown_text,
        },
        token_estimate=token_optimizer.estimate_tokens(markdown_text),
    )


async def pdf_extract_markdown(
    file_path: str,
    pages: list[int] | None = None,
) -> ToolResult:
    """Extract clean Markdown text from specific pages of a PDF document."""
    return await asyncio.to_thread(_sync_pdf_extract_markdown, file_path, pages)


def _sync_pdf_generate_report(
    file_path: str,
    title: str,
    sections: list[dict[str, Any]] | None = None,
) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="write")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        sandbox_manager.backup_before_modify(resolved)

    doc = SimpleDocTemplate(
        str(resolved),
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AksaTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=14,
    )
    h2_style = ParagraphStyle(
        "AksaH2",
        parent=styles["Heading2"],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = styles["BodyText"]

    story: list[Any] = [Paragraph(title, title_style), Spacer(1, 8)]

    if not sections:
        sections = [
            {
                "heading": "Ringkasan Laporan Resmi",
                "paragraphs": [
                    "Dokumen PDF ini dicetak secara otomatis oleh Mesin Dokumen AKSA di dalam Folder Kerja yang diizinkan."
                ],
            }
        ]

    for sec in sections:
        if sec.get("heading"):
            story.append(Paragraph(str(sec["heading"]), h2_style))
        for p_text in sec.get("paragraphs", []):
            story.append(Paragraph(str(p_text), body_style))
            story.append(Spacer(1, 6))
        tbl_spec = sec.get("table")
        if isinstance(tbl_spec, dict):
            headers = tbl_spec.get("headers", [])
            rows = tbl_spec.get("rows", [])
            if headers:
                data_matrix = [headers, *rows]
                tbl = Table(data_matrix, hAlign="LEFT")
                tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                            ("PADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(Spacer(1, 6))
                story.append(tbl)
                story.append(Spacer(1, 10))

    doc.build(story)
    summary = f"Laporan PDF '{resolved.name}' berhasil dibuat dengan judul '{title}'."
    return ToolResult(
        success=True,
        summary=summary,
        data={"file_path": str(resolved), "title": title},
        artifacts=[str(resolved)],
        token_estimate=35,
    )


async def pdf_generate_report(
    file_path: str,
    title: str,
    sections: list[dict[str, Any]] | None = None,
) -> ToolResult:
    """Generate a formatted printable PDF report using ReportLab."""
    return await asyncio.to_thread(_sync_pdf_generate_report, file_path, title, sections)


def _sync_pdf_merge_split(
    input_paths: list[str],
    output_path: str,
    mode: str = "merge",
    page_numbers: list[int] | None = None,
) -> ToolResult:
    validated_inputs = [sandbox_manager.validate_path(p, mode="read") for p in input_paths]
    dst = sandbox_manager.validate_path(output_path, mode="write")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        sandbox_manager.backup_before_modify(dst)

    out_doc = fitz.open()
    if mode == "split" and validated_inputs:
        src_doc = fitz.open(str(validated_inputs[0]))
        selected = page_numbers or [1]
        for p_num in selected:
            if 1 <= p_num <= len(src_doc):
                out_doc.insert_pdf(src_doc, from_page=p_num - 1, to_page=p_num - 1)
        src_doc.close()
    else:
        for src_path in validated_inputs:
            src_doc = fitz.open(str(src_path))
            out_doc.insert_pdf(src_doc)
            src_doc.close()

    total_out_pages = len(out_doc)
    out_doc.save(str(dst))
    out_doc.close()

    summary = (
        f"Operasi PDF '{mode}' selesai: menghasilkan '{dst.name}' ({total_out_pages} halaman)."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"output_path": str(dst), "mode": mode, "page_count": total_out_pages},
        artifacts=[str(dst)],
        token_estimate=32,
    )


async def pdf_merge_split(
    input_paths: list[str],
    output_path: str,
    mode: str = "merge",
    page_numbers: list[int] | None = None,
) -> ToolResult:
    """Merge multiple PDF files or split specific pages into a new PDF file."""
    return await asyncio.to_thread(
        _sync_pdf_merge_split, input_paths, output_path, mode, page_numbers
    )


def register_pdf_tools() -> None:
    tool_registry.register(
        name="pdf_extract_markdown",
        category="pdf_tools",
        description="Ekstrak halaman PDF menjadi teks Markdown bersih.",
        handler=pdf_extract_markdown,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="pdf_generate_report",
        category="pdf_tools",
        description="Buat dokumen laporan PDF rapi siap cetak.",
        handler=pdf_generate_report,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="pdf_merge_split",
        category="pdf_tools",
        description="Gabungkan beberapa file PDF atau pisahkan halaman PDF tertentu.",
        handler=pdf_merge_split,
        risk_level=RiskLevel.MEDIUM,
    )


register_pdf_tools()
