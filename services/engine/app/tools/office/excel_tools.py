"""Tier 1 Microsoft Excel Engine powered by openpyxl."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.core.sandbox import RiskLevel, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.tools.registry import ToolResult, tool_registry

HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=11, color="0F172A")
TOTAL_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
TOTAL_FONT = Font(name="Calibri", size=11, bold=True, color="0F172A")
THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)
IDR_NUMBER_FORMAT = '"Rp" #,##0;("Rp" #,##0);"-"'


def _sync_excel_inspect(file_path: str) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="read")
    if not resolved.exists():
        return ToolResult(
            success=False,
            summary=f"File Excel '{resolved.name}' tidak ditemukan.",
            token_estimate=12,
        )

    wb = openpyxl.load_workbook(resolved, data_only=False)
    sheets_summary: list[dict[str, Any]] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows_preview: list[list[Any]] = []
        formulas_detected: list[str] = []

        for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=min(6, ws.max_row), values_only=True), start=1):
            clean_row = [cell for cell in row]
            rows_preview.append(clean_row)
            for c_idx, val in enumerate(clean_row, start=1):
                if isinstance(val, str) and val.startswith("="):
                    formulas_detected.append(f"{get_column_letter(c_idx)}{r_idx}: {val}")

        headers = [str(h) if h is not None else "" for h in (rows_preview[0] if rows_preview else [])]
        sheets_summary.append(
            {
                "sheet_name": sheet_name,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "headers": headers,
                "sample_rows": rows_preview[1:4],
                "formulas_sample": formulas_detected[:10],
            }
        )

    wb.close()
    summary = (
        f"Inspeksi Excel '{resolved.name}' selesai: {len(sheets_summary)} sheet "
        f"({', '.join(s['sheet_name'] for s in sheets_summary)})."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"file_path": str(resolved), "sheets": sheets_summary},
        token_estimate=token_optimizer.estimate_tokens(str(sheets_summary)),
    )


async def excel_inspect(file_path: str) -> ToolResult:
    """Inspect sheets, headers, dimensions, formulas, and sample rows of an Excel (.xlsx) file."""
    return await asyncio.to_thread(_sync_excel_inspect, file_path)


def _sync_excel_create_workbook(
    file_path: str,
    sheets_spec: list[dict[str, Any]] | None = None,
    csv_source_path: str | None = None,
) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="write")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if resolved.exists():
        sandbox_manager.backup_before_modify(resolved)

    if csv_source_path:
        csv_resolved = sandbox_manager.validate_path(csv_source_path, mode="read")
        import csv
        with open(csv_resolved, mode="r", encoding="utf-8-sig") as f:
            reader = list(csv.reader(f))
            if reader:
                headers = reader[0]
                data_rows: list[list[Any]] = []
                for row_idx, r in enumerate(reader[1:], start=2):
                    parsed_row = []
                    for c_val in r:
                        try:
                            num = float(c_val)
                            parsed_row.append(int(num) if num.is_integer() else num)
                        except ValueError:
                            parsed_row.append(c_val)
                    data_rows.append(parsed_row)

                num_data_rows = len(data_rows)
                sum_row: list[Any] = []
                for col_idx, _ in enumerate(headers):
                    col_letter = openpyxl.utils.get_column_letter(col_idx + 1)
                    has_numbers = any(isinstance(r[col_idx], (int, float)) for r in data_rows if col_idx < len(r))
                    if has_numbers:
                        sum_row.append(f"=SUM({col_letter}2:{col_letter}{num_data_rows + 1})")
                    else:
                        sum_row.append("TOTAL" if col_idx == 0 or (col_idx == 1 and not any(sum_row)) else "")
                data_rows.append(sum_row)

                sheets_spec = [
                    {
                        "title": Path(csv_source_path).stem[:31],
                        "headers": headers,
                        "rows": data_rows,
                    }
                ]

    if not sheets_spec:
        sheets_spec = [
            {
                "title": "Rekap Keuangan",
                "headers": ["No", "Kategori", "Anggaran (Rp)", "Realisasi (Rp)", "Selisih (Rp)"],
                "rows": [
                    [1, "Operasional Kantor", 25000000, 21500000, "=C2-D2"],
                    [2, "Infrastruktur Cloud & AI", 18000000, 14200000, "=C3-D3"],
                    [3, "Pemasaran Digital", 32000000, 29800000, "=C4-D4"],
                    ["", "TOTAL", "=SUM(C2:C4)", "=SUM(D2:D4)", "=SUM(E2:E4)"],
                ],
                "currency_columns": [3, 4, 5],
                "chart": {
                    "type": "bar",
                    "title": "Perbandingan Anggaran vs Realisasi",
                    "data_cols": [3, 4],
                    "category_col": 2,
                    "max_data_row": 4,
                    "position": "G2",
                },
            }
        ]

    wb = openpyxl.Workbook()
    # Remove default sheet after creating custom sheets
    default_sheet = wb.active

    created_sheet_names: list[str] = []
    for spec in sheets_spec:
        title = str(spec.get("title", "Sheet1"))[:31]
        ws = wb.create_sheet(title=title)
        created_sheet_names.append(title)

        headers: list[str] = spec.get("headers", [])
        rows: list[list[Any]] = spec.get("rows", [])
        currency_cols: set[int] = set(spec.get("currency_columns", []))

        if headers:
            ws.append(headers)
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_idx)
                cell.fill = HEADER_FILL
                cell.font = HEADER_FONT
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = THIN_BORDER
            ws.row_dimensions[1].height = 24

        for r_offset, row_values in enumerate(rows, start=2 if headers else 1):
            ws.append(row_values)
            is_total_row = any(
                isinstance(v, str) and ("total" in v.lower() or v.startswith("=SUM"))
                for v in row_values
            )
            for col_idx in range(1, len(row_values) + 1):
                cell = ws.cell(row=r_offset, column=col_idx)
                cell.border = THIN_BORDER
                cell.font = TOTAL_FONT if is_total_row else BODY_FONT
                if is_total_row:
                    cell.fill = TOTAL_FILL

                val = cell.value
                # Auto-detect currency columns by header or explicit currency_columns
                header_text = headers[col_idx - 1].lower() if col_idx <= len(headers) else ""
                is_currency = col_idx in currency_cols or any(
                    k in header_text for k in ("rp", "harga", "biaya", "anggaran", "realisasi", "total", "nilai", "selisih")
                )
                if is_currency and (isinstance(val, (int, float)) or (isinstance(val, str) and val.startswith("="))):
                    cell.number_format = IDR_NUMBER_FORMAT
                    cell.alignment = Alignment(horizontal="right", vertical="center")

        # Auto-fit column widths
        for col in ws.columns:
            max_len = 10
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or "")
                max_len = max(max_len, min(42, len(val_str) + 5))
            ws.column_dimensions[col_letter].width = max_len

        # Optional Embedded Chart (Bar / Line / Pie)
        chart_spec = spec.get("chart")
        if isinstance(chart_spec, dict) and len(rows) >= 1:
            chart_type = str(chart_spec.get("type", "bar")).lower()
            if chart_type == "line":
                chart_obj = LineChart()
            elif chart_type == "pie":
                chart_obj = PieChart()
            else:
                chart_obj = BarChart()

            chart_obj.title = chart_spec.get("title", f"Grafik {title}")
            chart_obj.width = 16
            chart_obj.height = 10

            data_cols = chart_spec.get("data_cols", [3])
            min_col = min(data_cols)
            max_col = max(data_cols)
            max_data_row = int(chart_spec.get("max_data_row", len(rows)))
            cat_col = int(chart_spec.get("category_col", 2))

            data_ref = Reference(
                ws,
                min_col=min_col,
                min_row=1,
                max_col=max_col,
                max_row=max_data_row,
            )
            cats_ref = Reference(
                ws,
                min_col=cat_col,
                min_row=2,
                max_row=max_data_row,
            )
            chart_obj.add_data(data_ref, titles_from_data=True)
            chart_obj.set_categories(cats_ref)
            ws.add_chart(chart_obj, str(chart_spec.get("position", "G2")))

    if default_sheet is not None and len(wb.sheetnames) > 1:
        wb.remove(default_sheet)

    wb.save(resolved)
    wb.close()

    summary = (
        f"Workbook Excel '{resolved.name}' berhasil dibuat dengan {len(created_sheet_names)} sheet "
        f"({', '.join(created_sheet_names)}), format Rupiah, rumus aktif, dan grafik."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={"file_path": str(resolved), "sheets": created_sheet_names},
        artifacts=[str(resolved)],
        token_estimate=45,
    )


async def excel_create_workbook(
    file_path: str,
    sheets_spec: list[dict[str, Any]] | None = None,
    csv_source_path: str | None = None,
) -> ToolResult:
    """Create a styled Excel (.xlsx) workbook with Rupiah formatting, live formulas, and charts."""
    return await asyncio.to_thread(_sync_excel_create_workbook, file_path, sheets_spec, csv_source_path)


def _sync_excel_modify_cells(
    file_path: str,
    sheet_name: str | None = None,
    cell_updates: dict[str, Any] | None = None,
    append_rows: list[list[Any]] | None = None,
) -> ToolResult:
    resolved = sandbox_manager.validate_path(file_path, mode="write")
    if not resolved.exists():
        return ToolResult(
            success=False,
            summary=f"File Excel '{resolved.name}' tidak ditemukan.",
            token_estimate=12,
        )

    backup_path = sandbox_manager.backup_before_modify(resolved)
    wb = openpyxl.load_workbook(resolved)
    ws = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active

    updated_count = 0
    if cell_updates:
        for coord, value in cell_updates.items():
            ws[coord] = value
            updated_count += 1

    appended_count = 0
    if append_rows:
        for row_vals in append_rows:
            ws.append(row_vals)
            appended_count += 1

    wb.save(resolved)
    wb.close()

    summary = (
        f"File Excel '{resolved.name}' (Sheet '{ws.title}') berhasil diperbarui: "
        f"{updated_count} sel diubah, {appended_count} baris ditambahkan (Backup: {backup_path.name if backup_path else 'N/A'})."
    )
    return ToolResult(
        success=True,
        summary=summary,
        data={
            "file_path": str(resolved),
            "sheet": ws.title,
            "updated_cells": updated_count,
            "appended_rows": appended_count,
            "backup_path": str(backup_path) if backup_path else None,
        },
        artifacts=[str(resolved)],
        token_estimate=36,
    )


async def excel_modify_cells(
    file_path: str,
    sheet_name: str | None = None,
    cell_updates: dict[str, Any] | None = None,
    append_rows: list[list[Any]] | None = None,
) -> ToolResult:
    """Modify specific cells or append rows to an existing Excel (.xlsx) workbook with auto-backup."""
    return await asyncio.to_thread(
        _sync_excel_modify_cells, file_path, sheet_name, cell_updates, append_rows
    )


def register_excel_tools() -> None:
    tool_registry.register(
        name="excel_inspect",
        category="office_excel",
        description="Inspeksi daftar sheet, header, rumus, dan sampel baris dari file Excel (.xlsx).",
        handler=excel_inspect,
        risk_level=RiskLevel.LOW,
        parameters_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Jalur berkas .xlsx yang ingin diperiksa.",
                }
            },
            "required": ["file_path"],
        },
    )
    tool_registry.register(
        name="excel_create_workbook",
        category="office_excel",
        description="Buat file Microsoft Excel (.xlsx) baru dengan tabel rapi, format Rupiah, rumus aktif, dan grafik.",
        handler=excel_create_workbook,
        risk_level=RiskLevel.LOW,
        parameters_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Jalur berkas .xlsx tujuan di dalam folder kerja.",
                },
                "csv_source_path": {
                    "type": "string",
                    "description": "Jalur berkas .csv sumber yang ingin dikonversi menjadi tabel Excel dengan baris SUM (opsional).",
                },
                "sheets_spec": {
                    "type": "array",
                    "description": "Daftar spesifikasi sheet dengan title, headers, rows data, dan chart (opsional).",
                    "items": {"type": "object"},
                },
            },
            "required": ["file_path"],
        },
    )
    tool_registry.register(
        name="excel_modify_cells",
        category="office_excel",
        description="Ubah sel atau tambah baris pada file Excel (.xlsx) dengan backup otomatis ke .aksa_backup/.",
        handler=excel_modify_cells,
        risk_level=RiskLevel.MEDIUM,
        parameters_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Jalur berkas .xlsx yang ingin dimodifikasi.",
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Nama sheet (opsional).",
                },
                "cell_updates": {
                    "type": "object",
                    "description": "Pemetaan koordinat sel ke nilai baru, contoh: {'A1': 'Nilai Baru'}.",
                },
                "append_rows": {
                    "type": "array",
                    "description": "Daftar baris baru yang ingin ditambahkan.",
                    "items": {"type": "array", "items": {"type": "string"}},
                },
            },
            "required": ["file_path"],
        },
    )


register_excel_tools()

