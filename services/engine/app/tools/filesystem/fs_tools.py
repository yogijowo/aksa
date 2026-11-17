"""Scoped Filesystem Tools: list_workspace_files, inspect_file_outline, search_files, move_or_copy_file."""

from __future__ import annotations

import asyncio
import fnmatch
import shutil
from pathlib import Path
from typing import Any

from app.core.sandbox import RiskLevel, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.tools.registry import ToolResult, tool_registry


def _sync_list_workspace_files(workspace_path: str, subdir: str | None = None) -> ToolResult:
    base_dir = sandbox_manager.validate_path(workspace_path, mode="read")
    target_dir = base_dir / subdir if subdir else base_dir
    target_dir = sandbox_manager.validate_path(target_dir, mode="read")

    if not target_dir.exists() or not target_dir.is_dir():
        return ToolResult(
            success=False,
            summary=f"Direktori '{target_dir}' tidak ditemukan.",
            token_estimate=15,
        )

    entries: list[dict[str, Any]] = []
    for entry in sorted(target_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        stat = entry.stat()
        entries.append(
            {
                "name": entry.name,
                "path": str(entry),
                "is_dir": entry.is_dir(),
                "ext": entry.suffix.lower(),
                "size_bytes": stat.st_size if entry.is_file() else 0,
            }
        )

    summary = f"Menemukan {len(entries)} item di dalam '{target_dir.name}'."
    return ToolResult(
        success=True,
        summary=summary,
        data={"directory": str(target_dir), "items": entries},
        token_estimate=token_optimizer.estimate_tokens(summary) + len(entries) * 12,
    )


async def list_workspace_files(workspace_path: str, subdir: str | None = None) -> ToolResult:
    """List files and subdirectories inside an authorized workspace folder."""
    return await asyncio.to_thread(_sync_list_workspace_files, workspace_path, subdir)


def _sync_inspect_file_outline(file_path: str) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="read")
    if not resolved.exists() or not resolved.is_file():
        return ToolResult(
            success=False,
            summary=f"File '{resolved.name}' tidak ditemukan.",
            token_estimate=12,
        )

    ext = resolved.suffix.lower()
    stat = resolved.stat()
    outline: dict[str, Any] = {
        "file_name": resolved.name,
        "file_path": str(resolved),
        "extension": ext,
        "size_bytes": stat.st_size,
    }

    if ext in (".txt", ".md", ".csv", ".json", ".py", ".ts", ".tsx"):
        text = resolved.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        headings = [ln.strip() for ln in lines if ln.strip().startswith("#")][:15]
        outline["line_count"] = len(lines)
        outline["headings"] = headings
        outline["preview_head"] = "\n".join(lines[:10])
    elif ext == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(resolved, read_only=True, data_only=True)
        sheets_info = []
        for name in wb.sheetnames:
            ws = wb[name]
            first_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
            headers = [str(c) for c in first_row if c is not None]
            sheets_info.append(
                {
                    "sheet": name,
                    "max_row": ws.max_row,
                    "max_column": ws.max_column,
                    "headers": headers[:15],
                }
            )
        wb.close()
        outline["sheets"] = sheets_info
    elif ext == ".docx":
        import docx

        doc = docx.Document(str(resolved))
        headings = [
            p.text.strip()
            for p in doc.paragraphs
            if p.text.strip() and p.style and "Heading" in p.style.name
        ]
        outline["paragraph_count"] = len(doc.paragraphs)
        outline["table_count"] = len(doc.tables)
        outline["headings"] = headings[:20]
    elif ext == ".pdf":
        import pymupdf as fitz

        doc = fitz.open(str(resolved))
        outline["page_count"] = len(doc)
        first_page_text = doc[0].get_text("text")[:300] if len(doc) > 0 else ""
        outline["first_page_preview"] = first_page_text.strip()
        doc.close()

    summary = f"Ringkasan struktur '{resolved.name}' ({ext}, {stat.st_size} bytes) berhasil diekstrak secara hemat token."
    return ToolResult(
        success=True,
        summary=summary,
        data=outline,
        token_estimate=token_optimizer.estimate_tokens(str(outline)),
    )


async def inspect_file_outline(file_path: str) -> ToolResult:
    """Inspect a file's structure (headers, sheets, outline, line count) without loading full raw content."""
    return await asyncio.to_thread(_sync_inspect_file_outline, file_path)


def _sync_search_files(workspace_path: str, query: str, pattern: str = "*") -> ToolResult:
    root = sandbox_manager.validate_path(workspace_path, mode="read")
    q_lower = query.lower()
    matches: list[dict[str, Any]] = []

    for path in root.rglob("*"):
        if any(part.startswith(".") for part in path.parts):
            continue
        if not path.is_file():
            continue
        if not fnmatch.fnmatch(path.name.lower(), pattern.lower()):
            continue

        matched_in = None
        if q_lower in path.name.lower():
            matched_in = "filename"
        elif path.suffix.lower() in (".txt", ".md", ".csv", ".py", ".json"):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if q_lower in content.lower():
                    matched_in = "content"
            except Exception:
                pass

        if matched_in:
            matches.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "matched_in": matched_in,
                    "size_bytes": path.stat().st_size,
                }
            )
            if len(matches) >= 50:
                break

    summary = f"Pencarian '{query}' menemukan {len(matches)} file yang cocok di '{root.name}'."
    return ToolResult(
        success=True,
        summary=summary,
        data={"query": query, "matches": matches},
        token_estimate=token_optimizer.estimate_tokens(summary) + len(matches) * 15,
    )


async def search_files(workspace_path: str, query: str, pattern: str = "*") -> ToolResult:
    """Search files by name or text content inside an authorized workspace folder."""
    return await asyncio.to_thread(_sync_search_files, workspace_path, query, pattern)


def _sync_move_or_copy_file(
    source_path: str,
    destination_path: str,
    operation: str = "copy",
) -> ToolResult:
    src = sandbox_manager.validate_path(source_path, mode="read")
    dst = sandbox_manager.validate_path(destination_path, mode="write")

    if not src.exists():
        return ToolResult(
            success=False,
            summary=f"File sumber '{src}' tidak ditemukan.",
            token_estimate=12,
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if dst.exists() and dst.is_file():
        backup_path = sandbox_manager.backup_before_modify(dst)

    if operation == "move":
        sandbox_manager.validate_path(source_path, mode="write")
        shutil.move(str(src), str(dst))
        action_word = "dipindahkan"
    else:
        shutil.copy2(str(src), str(dst))
        action_word = "disalin"

    summary = f"File '{src.name}' berhasil {action_word} ke '{dst}'."
    return ToolResult(
        success=True,
        summary=summary,
        data={
            "source": str(src),
            "destination": str(dst),
            "operation": operation,
            "backup_created": str(backup_path) if backup_path else None,
        },
        artifacts=[str(dst)],
        token_estimate=28,
    )


async def move_or_copy_file(
    source_path: str,
    destination_path: str,
    operation: str = "copy",
) -> ToolResult:
    """Copy or move a file within authorized workspace folders with automatic backup if overwriting."""
    return await asyncio.to_thread(_sync_move_or_copy_file, source_path, destination_path, operation)


def register_filesystem_tools() -> None:
    """Register all scoped filesystem tools into the global ToolRegistry."""
    tool_registry.register(
        name="list_workspace_files",
        category="filesystem",
        description="Lihat daftar file dan sub-folder di dalam Folder Kerja yang diizinkan.",
        handler=list_workspace_files,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="inspect_file_outline",
        category="filesystem",
        description="Lihat struktur ringkas dokumen/spreadsheet tanpa memuat seluruh isi file.",
        handler=inspect_file_outline,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="search_files",
        category="filesystem",
        description="Cari file berdasarkan nama atau kata kunci di dalam Folder Kerja.",
        handler=search_files,
        risk_level=RiskLevel.LOW,
    )
    tool_registry.register(
        name="move_or_copy_file",
        category="filesystem",
        description="Salin atau pindahkan file di dalam Folder Kerja dengan auto-backup otomatis.",
        handler=move_or_copy_file,
        risk_level=RiskLevel.MEDIUM,
    )


register_filesystem_tools()
