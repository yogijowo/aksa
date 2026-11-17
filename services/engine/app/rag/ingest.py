"""Structure-Aware Document Parser, Semantic Chunker, and SHA-256 Hash Calculator."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SUPPORTED_RAG_EXTENSIONS: set[str] = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".csv",
    ".md",
    ".txt",
}


class DocumentChunk(BaseModel):
    """Represents a structure-aware semantic chunk ready for Hybrid Vector + FTS5 indexing."""

    chunk_id: str
    section_title: str
    content: str
    token_estimate: int


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a file for incremental diff indexing."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _chunk_text_paragraphs(
    paragraphs: list[tuple[str, str]],
    doc_prefix: str,
    max_chars: int = 1600,
) -> list[DocumentChunk]:
    """Group (section_title, text) pairs into semantic chunks (~400-500 tokens)."""
    chunks: list[DocumentChunk] = []
    cur_section = "Bagian Utama"
    cur_buf: list[str] = []
    cur_len = 0

    def _flush() -> None:
        nonlocal cur_buf, cur_len
        if not cur_buf:
            return
        body = "\n".join(cur_buf).strip()
        if body:
            idx = len(chunks) + 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{doc_prefix}_chk_{idx}",
                    section_title=cur_section,
                    content=body,
                    token_estimate=max(1, int(len(body) / 3.8)),
                )
            )
        cur_buf = []
        cur_len = 0

    for sec, text in paragraphs:
        clean = text.strip()
        if not clean:
            continue
        if sec != cur_section and cur_len > 300:
            _flush()
        cur_section = sec
        if cur_len + len(clean) > max_chars and cur_buf:
            overlap = cur_buf[-1:] if len(cur_buf[-1]) < 350 else []
            _flush()
            cur_buf = list(overlap)
            cur_len = sum(len(x) for x in cur_buf)
        cur_buf.append(clean)
        cur_len += len(clean)

    _flush()
    return chunks


def parse_and_chunk_file(file_path: Path, doc_id: str) -> list[DocumentChunk]:
    """Parse .pdf, .docx, .xlsx, .pptx, .csv, .md, or .txt into structure-preserving chunks."""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        import pymupdf as fitz

        doc = fitz.open(str(file_path))
        pairs: list[tuple[str, str]] = []
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pairs.append((f"Halaman {idx}", text))
        doc.close()
        return _chunk_text_paragraphs(pairs, doc_id)

    if ext == ".docx":
        import docx

        doc = docx.Document(str(file_path))
        pairs = []
        current_heading = "Dokumen Word"
        for p in doc.paragraphs:
            txt = p.text.strip()
            if not txt:
                continue
            if p.style and "Heading" in p.style.name:
                current_heading = txt
            else:
                pairs.append((current_heading, txt))

        for t_idx, table in enumerate(doc.tables, start=1):
            rows_md: list[str] = []
            for r in table.rows:
                cells = [c.text.strip().replace("\n", " ") for c in r.cells]
                rows_md.append("| " + " | ".join(cells) + " |")
            if rows_md:
                pairs.append((f"{current_heading} (Tabel {t_idx})", "\n".join(rows_md)))
        return _chunk_text_paragraphs(pairs, doc_id)

    if ext == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        chunks: list[DocumentChunk] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            all_rows: list[list[Any]] = [
                [c for c in r] for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)
            ]
            if not all_rows:
                continue
            headers = [str(h) if h is not None else f"Kol_{i+1}" for i, h in enumerate(all_rows[0])]
            header_line = "| " + " | ".join(headers) + " |"
            sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"

            data_rows = all_rows[1:] or [all_rows[0]]
            batch_size = 25
            for start in range(0, len(data_rows), batch_size):
                batch = data_rows[start : start + batch_size]
                md_lines = [header_line, sep_line]
                for row in batch:
                    vals = [str(v) if v is not None else "" for v in row[: len(headers)]]
                    md_lines.append("| " + " | ".join(vals) + " |")
                content = "\n".join(md_lines)
                idx = len(chunks) + 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}_chk_{idx}",
                        section_title=f"Sheet {sheet_name} (Baris {start + 2}-{start + 1 + len(batch)})",
                        content=content,
                        token_estimate=max(1, int(len(content) / 3.8)),
                    )
                )
        wb.close()
        return chunks

    if ext == ".csv":
        rows_list: list[list[str]] = []
        with file_path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if any(cell.strip() for cell in row):
                    rows_list.append(row)
        if not rows_list:
            return []
        headers = rows_list[0]
        header_line = "| " + " | ".join(headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
        chunks = []
        for start in range(1, max(2, len(rows_list)), 30):
            batch = rows_list[start : start + 30]
            md_lines = [header_line, sep_line]
            for r in batch:
                md_lines.append("| " + " | ".join(r[: len(headers)]) + " |")
            content = "\n".join(md_lines)
            idx = len(chunks) + 1
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{doc_id}_chk_{idx}",
                    section_title=f"CSV Baris {start}-{start + len(batch)}",
                    content=content,
                    token_estimate=max(1, int(len(content) / 3.8)),
                )
            )
        return chunks

    if ext == ".pptx":
        from pptx import Presentation

        prs = Presentation(str(file_path))
        pairs = []
        for s_idx, slide in enumerate(prs.slides, start=1):
            title = slide.shapes.title.text.strip() if slide.shapes.title and slide.shapes.title.text else f"Slide {s_idx}"
            texts: list[str] = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    t = shape.text_frame.text.strip()
                    if t and t != title:
                        texts.append(t)
            if texts or title:
                pairs.append((f"Slide {s_idx}: {title}", "\n".join([title, *texts])))
        return _chunk_text_paragraphs(pairs, doc_id)

    # Default: .md, .txt
    raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    pairs = []
    cur_sec = "Dokumen Teks"
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            cur_sec = stripped.lstrip("#").strip() or cur_sec
        else:
            pairs.append((cur_sec, stripped))
    return _chunk_text_paragraphs(pairs, doc_id)

