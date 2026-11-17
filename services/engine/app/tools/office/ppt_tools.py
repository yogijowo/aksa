"""Tier 1 Microsoft PowerPoint Engine powered by python-pptx."""

from __future__ import annotations

import asyncio
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt

from app.core.sandbox import RiskLevel, sandbox_manager
from app.tools.registry import ToolResult, tool_registry


def _sync_ppt_create_presentation(
    file_path: str,
    title: str,
    subtitle: str = "Disusun Otomatis oleh Tim Agen AKSA",
    slides_spec: list[dict[str, Any]] | None = None,
) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="write")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        sandbox_manager.backup_before_modify(resolved)

    prs = Presentation()

    # Title Slide
    title_layout = prs.slide_layouts[0]
    slide0 = prs.slides.add_slide(title_layout)
    if slide0.shapes.title:
        slide0.shapes.title.text = title
    if len(slide0.placeholders) > 1:
        slide0.placeholders[1].text = subtitle

    if not slides_spec:
        slides_spec = [
            {
                "layout": "bullets",
                "title": "Pokok Bahasan Utama",
                "bullets": [
                    "Ringkasan Kinerja & Operasional Kuartal",
                    "Evaluasi Anggaran dan Efisiensi Biaya",
                    "Rencana Tindak Lanjut Tim",
                ],
            },
            {
                "layout": "table",
                "title": "Ringkasan Data Utama",
                "headers": ["Divisi", "Target", "Capaian"],
                "rows": [
                    ["Operasional", "95%", "98%"],
                    ["Keuangan", "100%", "100%"],
                ],
            },
        ]

    for spec in slides_spec:
        layout_kind = str(spec.get("layout", "bullets")).lower()
        slide_title = str(spec.get("title", "Slide"))

        if layout_kind == "table":
            slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
            if slide.shapes.title:
                slide.shapes.title.text = slide_title
            headers: list[str] = spec.get("headers", ["Kolom 1", "Kolom 2"])
            rows: list[list[Any]] = spec.get("rows", [])
            total_rows = len(rows) + 1
            total_cols = max(1, len(headers))

            table_shape = slide.shapes.add_table(
                total_rows,
                total_cols,
                Inches(0.8),
                Inches(1.8),
                Inches(8.4),
                Inches(0.6 * total_rows),
            )
            table = table_shape.table
            for c_idx, h_text in enumerate(headers):
                table.cell(0, c_idx).text = str(h_text)
            for r_idx, row_vals in enumerate(rows, start=1):
                for c_idx, val in enumerate(row_vals[:total_cols]):
                    table.cell(r_idx, c_idx).text = str(val)

        elif layout_kind == "two_column":
            slide = prs.slides.add_slide(prs.slide_layouts[3])  # Two Content
            if slide.shapes.title:
                slide.shapes.title.text = slide_title
            left_items: list[str] = spec.get("left_bullets", [])
            right_items: list[str] = spec.get("right_bullets", [])
            if len(slide.placeholders) > 1:
                tf_left = slide.placeholders[1].text_frame
                tf_left.text = left_items[0] if left_items else ""
                for item in left_items[1:]:
                    p = tf_left.add_paragraph()
                    p.text = str(item)
            if len(slide.placeholders) > 2:
                tf_right = slide.placeholders[2].text_frame
                tf_right.text = right_items[0] if right_items else ""
                for item in right_items[1:]:
                    p = tf_right.add_paragraph()
                    p.text = str(item)

        else:
            slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content
            if slide.shapes.title:
                slide.shapes.title.text = slide_title
            bullets: list[str] = spec.get("bullets", [])
            if len(slide.placeholders) > 1 and bullets:
                tf = slide.placeholders[1].text_frame
                tf.text = str(bullets[0])
                for b_text in bullets[1:]:
                    p = tf.add_paragraph()
                    p.text = str(b_text)
                    p.font.size = Pt(18)

    prs.save(str(resolved))
    total_slides = len(prs.slides)
    summary = (
        f"Presentasi PowerPoint '{resolved.name}' berhasil dibuat dengan {total_slides} slide."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"file_path": str(resolved), "slide_count": total_slides, "title": title},
        artifacts=[str(resolved)],
        token_estimate=38,
    )


async def ppt_create_presentation(
    file_path: str,
    title: str,
    subtitle: str = "Disusun Otomatis oleh Tim Agen AKSA",
    slides_spec: list[dict[str, Any]] | None = None,
) -> ToolResult:
    """Create a Microsoft PowerPoint (.pptx) presentation with title, bullet, two-column, and table slides."""
    return await asyncio.to_thread(
        _sync_ppt_create_presentation, file_path, title, subtitle, slides_spec
    )


def register_ppt_tools() -> None:
    tool_registry.register(
        name="ppt_create_presentation",
        category="office_ppt",
        description="Buat slide presentasi PowerPoint (.pptx) lengkap dengan poin, dua kolom, dan tabel.",
        handler=ppt_create_presentation,
        risk_level=RiskLevel.LOW,
    )


register_ppt_tools()

