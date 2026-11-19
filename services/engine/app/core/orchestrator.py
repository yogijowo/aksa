"""Hierarchical Supervisor -> Sub-Agent Execution Engine with Context Isolation."""

from __future__ import annotations

import base64
import csv
import json
import logging
import re
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class TaskOutcome(str, Enum):
    """Granular task outcome classification for multi-agent workflows (AKSA-AGENT-003-R2)."""

    SUCCESS = "success"                  # All steps succeeded, and all postcondition artifacts verified
    PARTIAL_SUCCESS = "partial_success"  # Some steps succeeded but others failed or incomplete
    FAILED = "failed"                    # Tool failure or fatal execution exception
    CANCELLED = "cancelled"              # Cancelled by user, ambiguity guard, or policy rejection
    UNVERIFIED = "unverified"            # Execution finished but postconditions (artifacts on disk) failed

from app.api.ws import ws_manager
from app.core.llm_router import UnifiedLLMRouter
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.core.token_optimizer import token_optimizer
from app.db.models import DatabaseManager, _now_iso
from app.tools import tool_registry


def _generate_non_colliding_path(directory: Path, base_stem: str, extension: str) -> Path:
    """Generate a unique path in directory that does not collide with existing files."""
    ext = extension if extension.startswith(".") else f".{extension}"
    target = directory / f"{base_stem}{ext}"
    if not target.exists():
        return target
    counter = 1
    while True:
        candidate = directory / f"{base_stem} ({counter}){ext}"
        if not candidate.exists():
            return candidate
        counter += 1


MAX_ARTIFACT_VERIFY_BYTES: int = 25 * 1024 * 1024
MAX_EXCEL_PARSE_CELLS: int = 250_000
MAX_PDF_PARSE_PAGES: int = 500
_EXCEL_ERROR_TOKENS: frozenset[str] = frozenset({
    "#REF!",
    "#DIV/0!",
    "#VALUE!",
    "#NAME?",
    "#N/A",
    "#NUM!",
    "#NULL!",
})


def _evaluate_basic_excel_formula(
    formula: str,
    ws_val: Any,
    ws_fml: Any,
    *,
    _depth: int = 0,
    _seen: set[str] | None = None,
) -> float | None:
    """Deterministically evaluate common Excel formulas (SUM, AVERAGE, MIN, MAX, COUNT, + - * /)."""
    if _depth > 4:
        return None
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries

    expr = formula.strip()
    if not expr.startswith("="):
        return None
    body = expr[1:].strip()
    if not body:
        return None

    seen_set = set(_seen or set())

    def _cell_num(coord: str) -> float | None:
        c_up = coord.strip().upper()
        if c_up in seen_set:
            return None
        try:
            row_i, col_i = coordinate_to_tuple(c_up)
        except Exception:
            return None
        v_raw = ws_val.cell(row=row_i, column=col_i).value
        if isinstance(v_raw, (int, float)) and not isinstance(v_raw, bool):
            return float(v_raw)
        f_raw = ws_fml.cell(row=row_i, column=col_i).value
        if isinstance(f_raw, (int, float)) and not isinstance(f_raw, bool):
            return float(f_raw)
        if isinstance(f_raw, str) and f_raw.startswith("="):
            return _evaluate_basic_excel_formula(
                f_raw, ws_val, ws_fml, _depth=_depth + 1, _seen=seen_set | {c_up}
            )
        return None

    # Pattern 1: Single aggregate function FUNC(arg1, arg2, ...)
    fn_match = re.fullmatch(r"([A-Z]+)\s*\(([^()]+)\)", body, re.IGNORECASE)
    if fn_match:
        fn_name = fn_match.group(1).upper()
        if fn_name not in {"SUM", "AVERAGE", "MIN", "MAX", "COUNT"}:
            return None
        nums: list[float] = []
        for token in fn_match.group(2).split(","):
            part = token.strip()
            if not part:
                continue
            if ":" in part:
                try:
                    min_c, min_r, max_c, max_r = range_boundaries(part.upper())
                except Exception:
                    return None
                if (max_r - min_r + 1) * (max_c - min_c + 1) > 50_000:
                    return None
                for rr in range(min_r, max_r + 1):
                    for cc in range(min_c, max_c + 1):
                        val = _cell_num(f"{get_column_letter(cc)}{rr}")
                        if val is not None:
                            nums.append(val)
            else:
                try:
                    nums.append(float(part))
                except ValueError:
                    val = _cell_num(part)
                    if val is not None:
                        nums.append(val)
        if fn_name == "COUNT":
            return float(len(nums))
        if not nums:
            return 0.0 if fn_name == "SUM" else None
        if fn_name == "SUM":
            return float(sum(nums))
        if fn_name == "AVERAGE":
            return float(sum(nums) / len(nums))
        if fn_name == "MIN":
            return float(min(nums))
        if fn_name == "MAX":
            return float(max(nums))

    # Pattern 2: Binary operand expression (<cell|num> <op> <cell|num>)
    bin_match = re.fullmatch(
        r"([A-Z]{1,3}\d+|\d+(?:\.\d+)?)\s*([+\-*/])\s*([A-Z]{1,3}\d+|\d+(?:\.\d+)?)",
        body,
        re.IGNORECASE,
    )
    if bin_match:
        def _resolve_op(tok: str) -> float | None:
            try:
                return float(tok)
            except ValueError:
                return _cell_num(tok)

        lhs = _resolve_op(bin_match.group(1))
        rhs = _resolve_op(bin_match.group(3))
        op = bin_match.group(2)
        if lhs is None or rhs is None:
            return None
        if op == "+":
            return lhs + rhs
        if op == "-":
            return lhs - rhs
        if op == "*":
            return lhs * rhs
        if op == "/":
            return None if rhs == 0.0 else (lhs / rhs)

    return None


def get_artifact_postcondition_breakdown(
    art_path: Path,
    expected_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect and validate an artifact across four orthogonal gates (P2-03):
    1. ``file_created`` — non-zero byte regular file (non-symlink, bounded size) exists on disk.
    2. ``format_valid`` — parser opens the format cleanly.
    3. ``content_detected`` — non-trivial real structural content exists (rejects scalars,
       1-cell placeholders, empty docs, and ornamental textless vector PDFs).
    4. ``task_requirement_satisfied`` — artifact matches pre-execution prompt/plan
       expectations (columns, formulas, formula evaluation consistency, expected values,
       sections, keywords, minimum row/item counts).

    ``semantic_postcondition_passed`` is True ONLY when all four gates pass for a
    supported format (NEVER auto-passes unknown extensions).
    """
    schema = expected_schema or {}
    res: dict[str, Any] = {
        "file_created": False,
        "format_valid": False,
        "content_detected": False,
        "task_requirement_satisfied": False,
        "semantic_postcondition_passed": False,
        "semantic_status": "failed",  # passed | failed | unsupported
        "unsupported_format": False,
        "detail": "",
    }
    if art_path.is_symlink():
        res["detail"] = f"Artefak symlink ditolak oleh gerbang verifikasi: {art_path}"
        return res
    if not art_path.exists():
        res["detail"] = f"File tidak ditemukan: {art_path}"
        return res
    try:
        st_size = art_path.stat().st_size
        if st_size == 0:
            res["detail"] = f"File berukuran 0 byte: {art_path}"
            return res
        max_bytes = int(schema.get("max_bytes", MAX_ARTIFACT_VERIFY_BYTES))
        if st_size > max_bytes:
            res["detail"] = f"Ukuran artefak ({st_size} bytes) melebihi batas verifikasi aman ({max_bytes} bytes)."
            return res
    except Exception as exc:
        res["detail"] = f"Gagal membaca stat file: {exc}"
        return res

    res["file_created"] = True
    suffix = art_path.suffix.lower()

    expected_ext = str(schema.get("expected_extension", "") or "").strip().lower()
    if expected_ext and not expected_ext.startswith("."):
        expected_ext = f".{expected_ext}"
    if expected_ext and suffix != expected_ext:
        res["detail"] = f"Format artefak '{suffix}' tidak sesuai target tugas '{expected_ext}'."
        return res

    if suffix in (".xlsx", ".xlsm"):
        wb_val = None
        wb_fml = None
        try:
            import openpyxl
            wb_val = openpyxl.load_workbook(str(art_path), data_only=True)
            wb_fml = openpyxl.load_workbook(str(art_path), data_only=False)
            if not wb_val.sheetnames:
                res["detail"] = f"Buku kerja Excel kosong tanpa lembar kerja: {art_path}"
                return res
            res["format_valid"] = True

            non_empty_cells = 0
            cells_scanned = 0
            max_rows_seen = 0
            all_text_lower: list[str] = []
            header_tokens: set[str] = set()
            has_formula = False
            seen_formula_funcs: set[str] = set()
            cell_values_map: dict[str, Any] = {}
            excel_error: str | None = None

            for sname in wb_val.sheetnames:
                ws = wb_val[sname]
                ws_f = wb_fml[sname]
                if ws.max_row and ws.max_row > max_rows_seen:
                    max_rows_seen = ws.max_row
                for r_idx, (row_v, row_f) in enumerate(
                    zip(ws.iter_rows(values_only=False), ws_f.iter_rows(values_only=False)),
                    start=1,
                ):
                    for c_v, c_f in zip(row_v, row_f):
                        cells_scanned += 1
                        if cells_scanned > MAX_EXCEL_PARSE_CELLS:
                            res["detail"] = f"Buku kerja Excel melebihi batas sel aman ({MAX_EXCEL_PARSE_CELLS})."
                            return res

                        coord = c_f.coordinate
                        val_v = c_v.value
                        val_f = c_f.value
                        if isinstance(val_v, str) and val_v.strip().upper() in _EXCEL_ERROR_TOKENS:
                            excel_error = f"Sel Excel {sname}!{coord} menghasilkan error rumus: {val_v}"
                            break

                        is_formula_cell = isinstance(val_f, str) and val_f.startswith("=")
                        if is_formula_cell:
                            has_formula = True
                            fml_str = val_f.strip()
                            if len(fml_str) < 2 or fml_str.count("(") != fml_str.count(")"):
                                excel_error = f"Sintaks rumus Excel tidak valid pada {sname}!{coord}: {fml_str}"
                                break
                            for fn_tok in re.findall(r"([A-Z][A-Z0-9_.]*)\s*\(", fml_str.upper()):
                                seen_formula_funcs.add(fn_tok)
                            computed = _evaluate_basic_excel_formula(fml_str, ws, ws_f)
                            if (
                                computed is not None
                                and isinstance(val_v, (int, float))
                                and not isinstance(val_v, bool)
                                and abs(float(val_v) - computed) > 1e-4
                            ):
                                excel_error = (
                                    f"Nilai cache rumus pada {sname}!{coord} ({val_v}) tidak sesuai hasil "
                                    f"kalkulasi '{fml_str}' ({computed})."
                                )
                                break
                            effective_v = computed if val_v is None else val_v
                            cell_values_map.setdefault(coord, effective_v)
                            cell_values_map[f"{sname}!{coord}"] = effective_v
                            non_empty_cells += 1
                        elif val_v is not None and str(val_v).strip() != "":
                            non_empty_cells += 1
                            txt = str(val_v).strip().lower()
                            all_text_lower.append(txt)
                            if r_idx <= 2:
                                header_tokens.add(txt)
                            cell_values_map.setdefault(coord, val_v)
                            cell_values_map[f"{sname}!{coord}"] = val_v
                    if excel_error:
                        break
                if excel_error:
                    break

            min_cells = int(schema.get("min_cells", 2))
            if non_empty_cells < min_cells:
                res["detail"] = (
                    f"Buku kerja Excel hanya memiliki {non_empty_cells} sel terisi "
                    f"(minimum semantik: {min_cells} sel nyata): {art_path}"
                )
                return res

            res["content_detected"] = True

            if excel_error:
                res["detail"] = excel_error
                return res

            min_rows = int(schema.get("min_rows", 1))
            if max_rows_seen < min_rows:
                res["detail"] = f"Jumlah baris Excel ({max_rows_seen}) kurang dari syarat tugas ({min_rows})."
                return res

            if schema.get("require_formulas") and not has_formula:
                res["detail"] = "Buku kerja Excel tidak memuat formula/rumus dinamis yang disyaratkan tugas."
                return res

            req_funcs = [str(f).strip().upper() for f in schema.get("required_formula_functions", []) if str(f).strip()]
            missing_funcs = [f for f in req_funcs if f not in seen_formula_funcs]
            if missing_funcs:
                res["detail"] = f"Fungsi rumus wajib Excel tidak ditemukan: {missing_funcs}"
                return res

            expected_vals = schema.get("expected_values")
            if isinstance(expected_vals, dict):
                for coord_key, exp_v in expected_vals.items():
                    if coord_key not in cell_values_map:
                        res["detail"] = f"Nilai target sel Excel '{coord_key}' tidak ditemukan."
                        return res
                    actual_v = cell_values_map[coord_key]
                    if isinstance(exp_v, (int, float)) and not isinstance(exp_v, bool):
                        if not isinstance(actual_v, (int, float)) or abs(float(actual_v) - float(exp_v)) > 1e-4:
                            res["detail"] = f"Nilai sel '{coord_key}' ({actual_v}) tidak sesuai target ({exp_v})."
                            return res
                    elif str(actual_v).strip().lower() != str(exp_v).strip().lower():
                        res["detail"] = f"Nilai sel '{coord_key}' ('{actual_v}') tidak sesuai target ('{exp_v}')."
                        return res

            req_cols = [str(c).strip().lower() for c in schema.get("required_columns", []) if str(c).strip()]
            if req_cols:
                combined_headers = " ".join(header_tokens)
                missing_cols = [c for c in req_cols if c not in combined_headers]
                if missing_cols:
                    res["detail"] = f"Kolom wajib Excel tidak ditemukan: {missing_cols}"
                    return res

            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            if req_kw:
                corpus = " ".join(all_text_lower)
                missing_kw = [k for k in req_kw if k not in corpus]
                if missing_kw:
                    res["detail"] = f"Konten wajib Excel tidak ditemukan: {missing_kw}"
                    return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas Excel (.xlsx) tidak valid atau korup: {exc}"
            return res
        finally:
            if wb_val is not None:
                try:
                    wb_val.close()
                except Exception:
                    pass
            if wb_fml is not None:
                try:
                    wb_fml.close()
                except Exception:
                    pass

    elif suffix == ".docx":
        try:
            import docx
            doc = docx.Document(str(art_path))
            res["format_valid"] = True
            chunks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text.strip():
                            chunks.append(cell.text.strip())
            full_text = "\n".join(chunks)
            min_chars = int(schema.get("min_chars", 10))
            if len(full_text) < min_chars:
                res["detail"] = (
                    f"Dokumen Word (.docx) hanya berisi {len(full_text)} karakter "
                    f"(minimum semantik: {min_chars}): {art_path}"
                )
                return res

            res["content_detected"] = True

            if schema.get("min_paragraphs") and len(chunks) < int(schema["min_paragraphs"]):
                res["detail"] = f"Jumlah paragraf Word kurang dari syarat ({schema['min_paragraphs']})."
                return res

            lower_text = full_text.lower()
            req_sections = [str(s).strip().lower() for s in schema.get("required_sections", []) if str(s).strip()]
            missing_sec = [s for s in req_sections if s not in lower_text]
            if missing_sec:
                res["detail"] = f"Bagian/section wajib dokumen Word tidak ditemukan: {missing_sec}"
                return res

            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            missing_kw = [k for k in req_kw if k not in lower_text]
            if missing_kw:
                res["detail"] = f"Konten wajib dokumen Word tidak ditemukan: {missing_kw}"
                return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas dokumen Word (.docx) tidak valid atau korup: {exc}"
            return res

    elif suffix == ".pptx":
        try:
            from pptx import Presentation
            prs = Presentation(str(art_path))
            if len(prs.slides) < 1:
                res["detail"] = f"Presentasi PowerPoint tidak memiliki slide: {art_path}"
                return res
            res["format_valid"] = True
            slide_texts: list[str] = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and str(shape.text).strip():
                        slide_texts.append(str(shape.text).strip())
            full_text = "\n".join(slide_texts)
            if len(full_text) < int(schema.get("min_chars", 10)):
                res["detail"] = f"Slide PowerPoint tidak memuat teks isi yang memadai: {art_path}"
                return res

            res["content_detected"] = True

            if schema.get("min_slides") and len(prs.slides) < int(schema["min_slides"]):
                res["detail"] = f"Jumlah slide PowerPoint kurang dari syarat ({schema['min_slides']})."
                return res

            lower_text = full_text.lower()
            req_sections = [str(s).strip().lower() for s in schema.get("required_sections", []) if str(s).strip()]
            missing_sec = [s for s in req_sections if s not in lower_text]
            if missing_sec:
                res["detail"] = f"Bagian/topik wajib PowerPoint tidak ditemukan: {missing_sec}"
                return res

            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            missing_kw = [k for k in req_kw if k not in lower_text]
            if missing_kw:
                res["detail"] = f"Konten wajib PowerPoint tidak ditemukan: {missing_kw}"
                return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas PowerPoint (.pptx) tidak valid atau korup: {exc}"
            return res

    elif suffix == ".pdf":
        try:
            import pymupdf as fitz
            doc = fitz.open(str(art_path))
            if doc.page_count < 1:
                doc.close()
                res["detail"] = f"Dokumen PDF tidak memiliki halaman: {art_path}"
                return res
            if doc.page_count > MAX_PDF_PARSE_PAGES:
                doc.close()
                res["detail"] = f"Jumlah halaman PDF ({doc.page_count}) melebihi batas verifikasi aman ({MAX_PDF_PARSE_PAGES})."
                return res
            res["format_valid"] = True
            page_count = doc.page_count
            extracted_text = "\n".join(page.get_text().strip() for page in doc).strip()
            has_images = any(len(page.get_images()) > 0 for page in doc)
            doc.close()

            # Reject ornamental-only vector drawings without extractable text or images
            min_chars = int(schema.get("min_chars", 10))
            if len(extracted_text) < min_chars and not (schema.get("allow_image_only") and has_images):
                res["detail"] = (
                    f"Dokumen PDF tidak memiliki teks yang cukup ({len(extracted_text)} karakter, "
                    "ornamental vector drawing ditolak oleh semantic gate)."
                )
                return res

            res["content_detected"] = True

            if schema.get("min_pages") and page_count < int(schema["min_pages"]):
                res["detail"] = f"Jumlah halaman PDF ({page_count}) kurang dari syarat ({schema['min_pages']})."
                return res

            lower_text = extracted_text.lower()
            req_sections = [str(s).strip().lower() for s in schema.get("required_sections", []) if str(s).strip()]
            missing_sec = [s for s in req_sections if s not in lower_text]
            if missing_sec:
                res["detail"] = f"Bagian wajib PDF tidak ditemukan: {missing_sec}"
                return res

            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            missing_kw = [k for k in req_kw if k not in lower_text]
            if missing_kw:
                res["detail"] = f"Konten wajib PDF tidak ditemukan: {missing_kw}"
                return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas PDF tidak valid atau korup: {exc}"
            return res

    elif suffix == ".json":
        try:
            data = json.loads(art_path.read_text(encoding="utf-8"))
            res["format_valid"] = True
            # Reject scalars (int, float, bool, str, None) and empty containers
            if not isinstance(data, (dict, list)) or len(data) == 0:
                res["detail"] = f"File JSON harus berupa objek atau array terstruktur non-kosong (skalar ditolak): {art_path}"
                return res

            res["content_detected"] = True

            if schema.get("min_items") and len(data) < int(schema["min_items"]):
                res["detail"] = f"Jumlah item JSON kurang dari syarat ({schema['min_items']})."
                return res
            req_keys = [str(k) for k in schema.get("required_keys", []) if str(k).strip()]
            if req_keys:
                sample = data if isinstance(data, dict) else (data[0] if isinstance(data[0], dict) else {})
                missing_keys = [k for k in req_keys if k not in sample]
                if missing_keys:
                    res["detail"] = f"Kunci wajib JSON tidak ditemukan: {missing_keys}"
                    return res
            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            if req_kw:
                dumped = json.dumps(data, ensure_ascii=False).lower()
                missing_kw = [k for k in req_kw if k not in dumped]
                if missing_kw:
                    res["detail"] = f"Konten wajib JSON tidak ditemukan: {missing_kw}"
                    return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas JSON tidak valid atau korup: {exc}"
            return res

    elif suffix in (".csv", ".tsv"):
        try:
            delimiter = "\t" if suffix == ".tsv" else ","
            raw = art_path.read_text(encoding="utf-8", errors="replace")
            rows = [r for r in csv.reader(raw.splitlines(), delimiter=delimiter) if any(c.strip() for c in r)]
            res["format_valid"] = True
            if len(rows) < 2:
                res["detail"] = f"File {suffix} hanya memiliki {len(rows)} baris terisi (minimum 2 baris konten)."
                return res

            res["content_detected"] = True

            min_rows = int(schema.get("min_rows", 2))
            if len(rows) < min_rows:
                res["detail"] = f"File {suffix} hanya memiliki {len(rows)} baris terisi (minimum {min_rows})."
                return res
            req_cols = [str(c).strip().lower() for c in schema.get("required_columns", []) if str(c).strip()]
            if req_cols:
                header_lower = {c.strip().lower() for c in rows[0]}
                missing_cols = [c for c in req_cols if c not in header_lower]
                if missing_cols:
                    res["detail"] = f"Kolom wajib {suffix} tidak ditemukan: {missing_cols}"
                    return res
            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            if req_kw:
                lower_raw = raw.lower()
                missing_kw = [k for k in req_kw if k not in lower_raw]
                if missing_kw:
                    res["detail"] = f"Konten wajib {suffix} tidak ditemukan: {missing_kw}"
                    return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Integritas {suffix} tidak valid: {exc}"
            return res

    elif suffix in (".txt", ".md", ".html"):
        try:
            text = art_path.read_text(encoding="utf-8", errors="replace")
            res["format_valid"] = True
            stripped = text.strip()
            min_chars = int(schema.get("min_chars", 10))
            if len(stripped) < min_chars:
                res["detail"] = f"File teks terlalu pendek ({len(stripped)} < {min_chars} karakter): {art_path}"
                return res

            res["content_detected"] = True

            lower_text = stripped.lower()
            req_sections = [str(s).strip().lower() for s in schema.get("required_sections", []) if str(s).strip()]
            missing_sec = [s for s in req_sections if s not in lower_text]
            if missing_sec:
                res["detail"] = f"Bagian wajib {suffix} tidak ditemukan: {missing_sec}"
                return res

            req_kw = [str(k).strip().lower() for k in schema.get("required_keywords", []) if str(k).strip()]
            missing_kw = [k for k in req_kw if k not in lower_text]
            if missing_kw:
                res["detail"] = f"Konten wajib {suffix} tidak ditemukan: {missing_kw}"
                return res

            res["task_requirement_satisfied"] = True
            res["semantic_postcondition_passed"] = True
            res["semantic_status"] = "passed"
            res["detail"] = "Valid"
            return res
        except Exception as exc:
            res["detail"] = f"Gagal membaca teks file: {exc}"
            return res

    # AKSA-AGENT-003-R5: Unknown extensions MUST return 'unsupported', NEVER auto-pass semantic gate
    res["format_valid"] = False
    res["content_detected"] = False
    res["task_requirement_satisfied"] = False
    res["semantic_postcondition_passed"] = False
    res["semantic_status"] = "unsupported"
    res["unsupported_format"] = True
    res["detail"] = f"Ekstensi '{suffix or '(tanpa ekstensi)'}' tidak didukung untuk verifikasi semantik otomatis (unsupported)."
    return res


def _split_expectation_list(raw_fragment: str) -> list[str]:
    """Parse comma/'dan'/'&'-separated column, section, or key specifications cleanly."""
    cleaned = re.split(r"(?:,|\sdan\s|\sand\s|\s&\s|;)", raw_fragment.strip())
    items: list[str] = []
    for tok in cleaned:
        t = tok.strip(" \t\r\n'\"`:.")
        if t and len(t) <= 60 and t.lower() not in {"dengan", "untuk", "yang", "serta"}:
            items.append(t)
    return items


def derive_expected_artifact_schema(
    prompt: str,
    art_path: Path | None = None,
    plan_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive structured pre-execution postcondition expectations from user prompt & optional plan spec (P2-03)."""
    text = prompt or ""
    p_lower = text.lower()
    suffix = art_path.suffix.lower() if art_path is not None else ""
    schema: dict[str, Any] = {
        "expectation_source": "prompt+plan" if plan_spec else "prompt",
    }

    # Merge explicit plan_spec first as structured baseline
    if isinstance(plan_spec, dict):
        for k, v in plan_spec.items():
            if v is not None:
                schema[k] = list(v) if isinstance(v, list) else v

    # 1. Formulas requirement for Excel / spreadsheets
    if (not suffix or suffix in (".xlsx", ".xlsm")) and any(
        k in p_lower for k in ("rumus", "formula", "=sum", "=average", "kalkulasi otomatis")
    ):
        schema["require_formulas"] = True

    # 2. Explicit column expectations: e.g., "kolom: Tanggal, Kategori, Nominal" or "columns Nama and Nilai"
    col_match = re.search(
        r"(?:\bkolom\b|\bcolumns?\b|\bheader\b)\s*(?::|terdiri\s+dari|berisi|yaitu|=)?\s*([^\n.;]+)",
        text,
        re.IGNORECASE,
    )
    if col_match:
        # Stop before trailing instruction clauses such as "dengan rumus ..." or "minimal 5 baris"
        frag = re.split(r"\b(?:dengan\s+rumus|minimal\s+\d+|serta\s+grafik|beserta)\b", col_match.group(1), flags=re.IGNORECASE)[0]
        cols = _split_expectation_list(frag)
        if cols:
            existing = list(schema.get("required_columns", []))
            for c in cols:
                if c not in existing:
                    existing.append(c)
            schema["required_columns"] = existing

    # 3. Explicit section/heading expectations: e.g., "bagian: Ringkasan Eksekutif, Anggaran, Kesimpulan"
    sec_match = re.search(
        r"(?:\bbagian\b|\bsections?\b|\bbab\b)\s*(?::|terdiri\s+dari|meliputi|berisi|yaitu|=)?\s*([^\n.;]+)",
        text,
        re.IGNORECASE,
    )
    if sec_match:
        frag = re.split(r"\b(?:minimal\s+\d+|dalam\s+format)\b", sec_match.group(1), flags=re.IGNORECASE)[0]
        secs = _split_expectation_list(frag)
        if secs:
            existing_secs = list(schema.get("required_sections", []))
            for s in secs:
                if s not in existing_secs:
                    existing_secs.append(s)
            schema["required_sections"] = existing_secs

    # 4. Explicit JSON key expectations: e.g., "keys: status, total, items"
    key_match = re.search(
        r"(?:\bkunci\b|\bkeys?\b|\bfields?\b)\s*(?::|wajib|=)?\s*([^\n.;]+)",
        text,
        re.IGNORECASE,
    )
    if key_match and (not suffix or suffix == ".json"):
        keys = _split_expectation_list(key_match.group(1))
        if keys:
            existing_keys = list(schema.get("required_keys", []))
            for k in keys:
                if k not in existing_keys:
                    existing_keys.append(k)
            schema["required_keys"] = existing_keys

    # 5. Minimum row / item / paragraph / page / slide requirements
    row_match = re.search(r"(?:minimal|paling\s+sedikit|at\s+least)\s+(\d+)\s+(?:baris|rows?|data)\b", p_lower)
    if row_match:
        schema["min_rows"] = max(int(schema.get("min_rows", 1)), int(row_match.group(1)))

    para_match = re.search(r"(?:minimal|paling\s+sedikit|at\s+least)\s+(\d+)\s+(?:paragraf|paragraphs?)\b", p_lower)
    if para_match:
        schema["min_paragraphs"] = max(int(schema.get("min_paragraphs", 1)), int(para_match.group(1)))

    page_match = re.search(r"(?:minimal|paling\s+sedikit|at\s+least)\s+(\d+)\s+(?:halaman|pages?)\b", p_lower)
    if page_match:
        schema["min_pages"] = max(int(schema.get("min_pages", 1)), int(page_match.group(1)))

    slide_match = re.search(r"(?:minimal|paling\s+sedikit|at\s+least)\s+(\d+)\s+(?:slide|slides)\b", p_lower)
    if slide_match:
        schema["min_slides"] = max(int(schema.get("min_slides", 1)), int(slide_match.group(1)))

    # 6. Explicit required keywords if preceded by explicit content cue: e.g. 'wajib memuat kata "Q4 Revenue"'
    kw_matches = re.findall(
        r"(?:wajib\s+memuat|harus\s+berisi|memuat\s+kata|contain|include)\s+[\"']([^\"']{2,60})[\"']",
        text,
        re.IGNORECASE,
    )
    if kw_matches:
        existing_kw = list(schema.get("required_keywords", []))
        for kw in kw_matches:
            if kw.strip() and kw.strip() not in existing_kw:
                existing_kw.append(kw.strip())
        schema["required_keywords"] = existing_kw

    return schema


def verify_artifact_postcondition(
    art_path: Path,
    expected_schema: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Verify that an artifact exists, is valid format, contains real content, and meets task requirements."""
    breakdown = get_artifact_postcondition_breakdown(art_path, expected_schema=expected_schema)
    is_ok = bool(
        breakdown["file_created"]
        and breakdown["format_valid"]
        and breakdown["content_detected"]
        and breakdown["task_requirement_satisfied"]
        and breakdown["semantic_postcondition_passed"]
        and not breakdown["unsupported_format"]
    )
    return is_ok, breakdown["detail"]


def _create_word_duplicate_from_pdf(source_pdf: Path, target_docx: Path) -> str:
    """Generate a clean Word document duplicated dynamically from source PDF."""
    import docx
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import pymupdf as fitz

    if not source_pdf.exists():
        raise FileNotFoundError(f"Berkas sumber PDF '{source_pdf.name}' tidak ditemukan.")

    doc = docx.Document()
    for s in doc.sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    try:
        pdf_doc = fitz.open(str(source_pdf))
    except Exception as exc:
        raise RuntimeError(f"Gagal membuka berkas PDF '{source_pdf.name}': {exc}") from exc

    try:
        for page_idx, page in enumerate(pdf_doc):
            if page_idx > 0:
                doc.add_page_break()

            tables = []
            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    tables = tabs.tables
            except Exception:
                tables = []

            if tables:
                for tab in tables:
                    extracted = tab.extract()
                    if extracted and len(extracted) > 0:
                        cols_count = max(len(row) for row in extracted)
                        tbl = doc.add_table(rows=len(extracted), cols=cols_count)
                        tbl.style = "Table Grid"
                        for r_idx, row_vals in enumerate(extracted):
                            for c_idx, val in enumerate(row_vals):
                                cell_text = str(val or "").strip()
                                tbl.rows[r_idx].cells[c_idx].text = cell_text
                                if r_idx == 0:
                                    for p in tbl.rows[r_idx].cells[c_idx].paragraphs:
                                        for run in p.runs:
                                            run.bold = True
                        doc.add_paragraph()

                raw_page_text = page.get_text("text")
                page_text = str(raw_page_text).strip() if isinstance(raw_page_text, str) else ""
                if page_text:
                    for line in page_text.splitlines():
                        line_str = line.strip()
                        if line_str:
                            doc.add_paragraph(line_str)
            else:
                blocks = page.get_text("blocks")
                if isinstance(blocks, list):
                    for b in sorted(blocks, key=lambda x: (x[1], x[0])):
                        if len(b) > 6 and b[6] == 0:
                            text = str(b[4]).strip() if len(b) > 4 else ""
                            if text:
                                p = doc.add_paragraph()
                                p.paragraph_format.space_after = Pt(4)
                                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                                if len(lines) == 1 and len(lines[0]) < 60 and (lines[0].isupper() or lines[0].endswith(":")):
                                    run = p.add_run(lines[0])
                                    run.bold = True
                                else:
                                    p.add_run("\n".join(lines))
        pdf_doc.close()
        doc.save(str(target_docx))
    except Exception as exc:
        try:
            pdf_doc.close()
        except Exception:
            pass
        raise RuntimeError(f"Gagal memproses duplikasi PDF '{source_pdf.name}': {exc}") from exc

    return f"Duplikasi dokumen '{source_pdf.name}' ke Word ('{target_docx.name}') berhasil dibuat."


class HierarchicalOrchestrator:
    """Coordinates Supervisor task decomposition, isolated sub-agent execution, and token logging."""

    def __init__(self, db: DatabaseManager, llm_router: UnifiedLLMRouter) -> None:
        self.db = db
        self.llm_router = llm_router

    def _select_relevant_sub_agents(
        self, prompt: str, sub_agents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Select which specialist sub-agents should be delegated to based on the user's prompt."""
        if not sub_agents:
            return []

        lower = prompt.lower()
        selected: list[dict[str, Any]] = []

        for agt in sub_agents:
            cats = set(agt.get("tool_categories", []))
            if any(k in lower for k in ("baca", "cari", "dokumen", "pdf", "arsip", "folder", "data")):
                if "rag_search" in cats or "filesystem" in cats:
                    selected.append(agt)
                    continue
            if any(
                k in lower
                for k in ("excel", "xlsx", "word", "docx", "surat", "laporan", "rekap", "ppt", "slide", "duplikasi", "duplikat", "konversi", "salin")
            ):
                if "office_excel" in cats or "office_word" in cats or "office_ppt" in cats:
                    selected.append(agt)
                    continue
            if any(k in lower for k in ("python", "skrip", "script", "aplikasi", "otomatis", "csv")):
                if "uv_python" in cats or "os_automation" in cats or "computer_use" in cats:
                    selected.append(agt)
                    continue

        if not selected:
            # Only delegate to specialists if the prompt asks for concrete document or search tasks
            # Conversational greetings and general questions are answered directly by the supervisor
            wants_action = any(
                k in lower
                for k in ("buat", "bikin", "generate", "tulis", "rekap", "cari", "analisis", "eksekusi", "jalankan", "proses")
            )
            if wants_action and sub_agents:
                selected = sub_agents[:2]

        return selected

    async def _log_token_usage(
        self,
        session_id: str | None,
        agent: dict[str, Any],
        input_tokens: int,
        output_tokens: int,
        tokens_saved: int,
        cost_usd: float = 0.0,
    ) -> None:
        log_id = f"tok_{uuid.uuid4().hex[:10]}"
        async with aiosqlite.connect(self.db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO token_usage_logs (
                    id, session_id, agent_id, provider, model_id,
                    input_tokens, output_tokens, cached_tokens,
                    tokens_saved_by_isolation, cost_usd, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    session_id,
                    agent["id"],
                    agent["provider"],
                    agent["model_id"],
                    input_tokens,
                    output_tokens,
                    0,
                    tokens_saved,
                    cost_usd,
                    _now_iso(),
                ),
            )
            await conn.commit()

    async def execute_hierarchical_task(
        self,
        prompt: str,
        team_id: str | None = None,
        workspace_id: str | None = None,
        workspace_path: str | None = None,
        session_id: str | None = None,
        explicit_attachments: list[str] | None = None,
        allow_external_disclosure: bool = False,
    ) -> dict[str, Any]:
        """Run a full Supervisor -> Sub-Agents workflow with isolated scratchpads and WebSocket events."""
        teams = await self.db.list_teams_with_agents()
        team = next((t for t in teams if t["id"] == team_id), teams[0] if teams else None)
        if not team:
            raise ValueError("Tim agen tidak ditemukan di database.")

        agents: list[dict[str, Any]] = team["agents"]
        supervisor = next((a for a in agents if a["parent_id"] is None), agents[0])
        sub_agents = [a for a in agents if a["id"] != supervisor["id"]]

        delegated_agents = self._select_relevant_sub_agents(prompt, sub_agents)
        # Pre-execution structured task expectation specification (P2-03)
        pre_execution_expectation = derive_expected_artifact_schema(prompt)

        # Resolve workspace directory explicitly (NO fallback to workspaces[0] or Path.cwd())
        target_ws_path: Path | None = None
        ws_policy_record: dict[str, Any] | None = None
        workspaces = await self.db.list_workspaces()

        if workspace_id:
            ws = next((w for w in workspaces if w["id"] == workspace_id), None)
            if ws:
                p = Path(ws["folder_path"]).expanduser().resolve()
                if p.exists() and p.is_dir():
                    target_ws_path = p
                    ws_policy_record = ws
        elif workspace_path:
            p = Path(workspace_path).expanduser().resolve()
            if p.exists() and p.is_dir():
                target_ws_path = p
                ws_policy_record = next(
                    (w for w in workspaces if Path(w["folder_path"]).expanduser().resolve() == p),
                    None,
                )

        if not target_ws_path:
            await ws_manager.broadcast_event(
                "task_failed",
                {
                    "error": "Folder kerja belum dipilih secara eksplisit. Silakan pilih dan izinkan folder di PC Anda sebelum memulai pekerjaan.",
                },
                session_id=session_id,
            )
            return {
                "session_id": session_id or str(uuid.uuid4()),
                "status": "error",
                "message": "Folder kerja belum dipilih atau tidak diizinkan.",
                "response": "Folder kerja belum dipilih. Silakan pilih atau daftarkan folder kerja di komputer Anda terlebih dahulu melalui menu Ruang Kerja sebelum meminta agen memproses tugas.",
                "artifacts": [],
                "token_usage": {"input_tokens": 0, "output_tokens": 0, "savings_percent": 0.0},
            }

        # Enforce sandbox registration preserving stored least-privilege policy (never auto-escalate)
        allow_read = bool(ws_policy_record["allow_read"]) if ws_policy_record else True
        allow_write = bool(ws_policy_record["allow_write"]) if ws_policy_record else True
        allow_execute = bool(ws_policy_record["allow_execute"]) if ws_policy_record else False

        sandbox_manager.register_workspace(
            WorkspacePolicy(
                folder_path=str(target_ws_path),
                allow_read=allow_read,
                allow_write=allow_write,
                allow_execute=allow_execute,
            )
        )

        ws_dir = target_ws_path
        real_files: list[dict[str, Any]] = []
        if allow_read and ws_dir.exists() and ws_dir.is_dir():
            for item in sorted(ws_dir.iterdir(), key=lambda x: x.name.lower()):
                if item.name.startswith("."):
                    continue
                try:
                    stat = item.stat()
                    kb = round(stat.st_size / 1024, 1)
                    size_label = f"{kb} KB" if kb < 1024 else f"{round(kb/1024, 2)} MB"
                    real_files.append({
                        "name": item.name,
                        "path": str(item),
                        "is_dir": item.is_dir(),
                        "size": stat.st_size,
                        "size_label": size_label,
                        "ext": item.suffix.lower(),
                    })
                except Exception:
                    pass

        if real_files:
            file_lines = [
                f"- {f['name']} ({'Folder' if f['is_dir'] else f['size_label']})"
                for f in real_files
            ]
            workspace_files_text = (
                f"BERKAS NYATA YANG DITEMUKAN DI FOLDER KERJA '{ws_dir}' SAAT INI ({len(real_files)} berkas/folder):\n"
                + "\n".join(file_lines)
            )
        else:
            workspace_files_text = f"Folder Kerja '{ws_dir}' saat ini kosong (belum ada berkas yang tersimpan)."

        # Strict DataDisclosureGate: NEVER auto-attach PDF/workspace files without explicit user selection & consent
        attachments: list[dict[str, Any]] = []
        pdf_files = [f for f in real_files if f["ext"] == ".pdf"]
        pdf_extracted_notes: list[str] = []

        if explicit_attachments and allow_external_disclosure:
            for req_file in explicit_attachments[:2]:
                try:
                    candidate_path = (ws_dir / req_file) if not Path(req_file).is_absolute() else Path(req_file)
                    validated_path = sandbox_manager.validate_path(candidate_path, mode="read")
                    if validated_path.exists() and validated_path.is_file() and validated_path.stat().st_size <= 15 * 1024 * 1024:
                        raw_bytes = validated_path.read_bytes()
                        pdf_b64 = base64.b64encode(raw_bytes).decode("utf-8")
                        attachments.append({
                            "name": validated_path.name,
                            "mime_type": "application/pdf" if validated_path.suffix.lower() == ".pdf" else "application/octet-stream",
                            "data": pdf_b64,
                        })
                        pdf_extracted_notes.append(
                            f"Dokumen '{validated_path.name}' telah dilampirkan atas persetujuan eksplisit pengguna."
                        )
                except Exception:
                    pass

        await ws_manager.broadcast_event(
            "plan_created",
            {
                "supervisor": supervisor["name"],
                "delegated_count": len(delegated_agents),
                "workspace_path": str(ws_dir),
            },
            session_id=session_id,
        )

        execution_steps: list[dict[str, Any]] = []
        sub_agent_summaries: list[str] = []
        artifacts: list[dict[str, Any]] = []
        total_tokens_used = 0
        total_tokens_saved = 0

        for idx, sub in enumerate(delegated_agents, start=1):
            _, lazy_saved = token_optimizer.get_lazy_tools_for_agent(sub.get("tool_categories", []))
            task_brief = (
                f"Sub-tugas #{idx} dari {supervisor['name']}: Kerjakan bagian sesuai keahlian "
                f"({sub['role_title']}) untuk perintah pengguna: '{prompt}'"
            )

            await ws_manager.broadcast_event(
                "sub_agent_delegated",
                {
                    "from_agent": {"id": supervisor["id"], "name": supervisor["name"]},
                    "to_agent": {
                        "id": sub["id"],
                        "name": sub["name"],
                        "provider": sub["provider"],
                        "model_id": sub["model_id"],
                    },
                    "task_brief": task_brief,
                },
                session_id=session_id,
            )

            isolated_msgs = token_optimizer.build_isolated_subagent_messages(
                sub_agent=sub,
                task_brief=task_brief,
                workspace_path=str(ws_dir),
                relevant_files=[f"{f['name']} ({f['size_label']})" for f in real_files],
            )
            sub_tools = tool_registry.get_schemas_for_categories(sub.get("tool_categories", []))
            completion = await self.llm_router.complete(
                provider=sub["provider"],
                model_id=sub["model_id"],
                messages=isolated_msgs,
                temperature=sub.get("temperature", 0.2),
                max_tokens=sub.get("max_tokens", 2048),
                tools=sub_tools if sub_tools else None,
                attachments=attachments,
                user_consent_granted=allow_external_disclosure,
            )

            # Process any tool calls emitted by the sub-agent
            sub_tool_calls = completion.get("tool_calls", [])
            if sub_tool_calls and allow_write:
                for tc in sub_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        fn_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except Exception:
                        fn_args = {}

                    await ws_manager.broadcast_event(
                        "tool_started",
                        {"agent": sub["name"], "tool": fn_name, "arguments": fn_args},
                        session_id=session_id,
                    )

                    if "file_path" in fn_args:
                        fp = Path(fn_args["file_path"])
                        if not fp.is_absolute():
                            fn_args["file_path"] = str(ws_dir / fp)
                    if "csv_source_path" in fn_args:
                        cp = Path(fn_args["csv_source_path"])
                        if not cp.is_absolute():
                            fn_args["csv_source_path"] = str(ws_dir / cp)

                    res = await tool_registry.execute(fn_name, session_id=session_id, **fn_args)

                    await ws_manager.broadcast_event(
                        "tool_finished",
                        {"agent": sub["name"], "tool": fn_name, "success": res.success, "summary": res.summary},
                        session_id=session_id,
                    )

                    if res.success and res.artifacts:
                        for art_str in res.artifacts:
                            art_p = Path(art_str)
                            if art_p.exists() and art_p.stat().st_size > 0:
                                kb = round(art_p.stat().st_size / 1024, 1)
                                size_label = f"{kb} KB" if kb < 1024 else f"{round(kb / 1024, 2)} MB"
                                artifacts.append({
                                    "id": f"art_{uuid.uuid4().hex[:8]}",
                                    "name": art_p.name,
                                    "file_path": str(art_p),
                                    "file_type": art_p.suffix.lstrip(".").lower(),
                                    "size_label": size_label,
                                    "created_by_agent": sub["name"],
                                    "created_at_label": "Baru saja",
                                    "summary": res.summary,
                                })

            step_tokens = completion["input_tokens"] + completion["output_tokens"]
            handback_summary, metrics = token_optimizer.compact_subagent_handback(
                raw_subagent_output=completion["content"],
                measured_scratchpad_tokens=step_tokens,
                lazy_tool_tokens_saved=lazy_saved,
                supervisor_model_id=supervisor["model_id"],
            )

            total_tokens_used += step_tokens
            total_tokens_saved += metrics.total_tokens_saved

            await self._log_token_usage(
                session_id=session_id,
                agent=sub,
                input_tokens=completion["input_tokens"],
                output_tokens=completion["output_tokens"],
                tokens_saved=metrics.total_tokens_saved,
                cost_usd=0.0 if sub["provider"] in ("ollama", "lmstudio") else 0.0004,
            )

            execution_steps.append(
                {
                    "id": f"step_{uuid.uuid4().hex[:8]}",
                    "agent_name": sub["name"],
                    "agent_role": sub["role_title"],
                    "provider": sub["provider"],
                    "model_id": sub["model_id"],
                    "action_label": f"Menjalankan {sub['role_title']} di {ws_dir.name}",
                    "detail": (
                        f"Isolasi Konteks: Meringkas {metrics.raw_scratchpad_tokens} token kerja mentah "
                        f"menjadi {metrics.handback_summary_tokens} token + Lazy Tools."
                    ),
                    "status": "completed",
                    "tokens_used": step_tokens,
                    "tokens_saved": metrics.total_tokens_saved,
                }
            )
            sub_agent_summaries.append(f"[{sub['name']}]: {handback_summary}")

        lower_prompt = prompt.lower()
        has_create_verb = any(
            k in lower_prompt
            for k in (
                "buat", "bikin", "generate", "tulis", "rekap", "duplikasi",
                "duplikat", "konversi", "convert", "ubah", "salin",
            )
        )
        has_doc_type = any(
            k in lower_prompt
            for k in (
                "excel", "xlsx", "word", "docx", "surat", "laporan",
                "ppt", "slide", "presentasi",
            )
        )
        is_duplication = any(
            k in lower_prompt
            for k in ("duplikasi", "duplikat", "konversi", "convert", "ubah", "salin")
        ) and any(
            k in lower_prompt
            for k in ("word", "docx", "pdf", "file", "dokumen", "sama persis")
        )
        wants_doc = (has_create_verb and has_doc_type) or is_duplication

        action_confirmation_note = ""
        is_ambiguous_duplication = False
        clarification_text = ""
        tool_failed = False
        tool_failure_message = ""
        src_pf = None

        if wants_doc and allow_write:
            is_word = "word" in lower_prompt or "surat" in lower_prompt or "docx" in lower_prompt
            is_ppt = "ppt" in lower_prompt or "slide" in lower_prompt or "presentasi" in lower_prompt
            is_pdf = "pdf" in lower_prompt and not is_word and not is_ppt and not is_duplication

            ws_candidate = ws_dir

            if is_duplication and is_word:
                if not pdf_files:
                    is_ambiguous_duplication = True
                    clarification_text = f"Tidak ditemukan berkas PDF di folder kerja '{ws_dir.name}' untuk diduplikasi ke format Word."
                else:
                    matched_sources = [
                        f for f in pdf_files
                        if Path(f["name"]).stem.lower() in lower_prompt or f["name"].lower() in lower_prompt
                    ]
                    if len(pdf_files) == 1:
                        src_pf = pdf_files[0]
                    elif len(matched_sources) == 1:
                        src_pf = matched_sources[0]
                    else:
                        is_ambiguous_duplication = True
                        pdf_list_bullets = "\n".join(f"- `{pf['name']}`" for pf in pdf_files)
                        clarification_text = (
                            f"Ditemukan beberapa berkas PDF di folder kerja Anda:\n{pdf_list_bullets}\n\n"
                            "Mohon sebutkan nama berkas PDF yang ingin Anda duplikasi ke format Word (.docx) agar saya dapat memprosesnya."
                        )

                if not is_ambiguous_duplication and src_pf:
                    src_path = Path(src_pf["path"])
                    real_target = _generate_non_colliding_path(ws_dir, src_path.stem, "docx")
                    artifact_ext = "docx"
                    artifact_name = real_target.name

                    try:
                        dup_summary = _create_word_duplicate_from_pdf(src_path, real_target)
                        if real_target.exists() and real_target.stat().st_size > 0:
                            kb = round(real_target.stat().st_size / 1024, 1)
                            size_label = f"{kb} KB" if kb < 1024 else f"{round(kb / 1024, 2)} MB"
                            artifact = {
                                "id": f"art_{uuid.uuid4().hex[:8]}",
                                "name": artifact_name,
                                "file_path": str(real_target),
                                "file_type": artifact_ext,
                                "size_label": size_label,
                                "created_by_agent": delegated_agents[-1]["name"] if delegated_agents else supervisor["name"],
                                "created_at_label": "Baru saja",
                                "summary": dup_summary,
                            }
                            artifacts.append(artifact)
                            action_confirmation_note = (
                                f"PEMBERITAHUAN EKSEKUSI DUPLIKASI:\n"
                                f"- Dokumen sumber: '{src_pf['name']}'\n"
                                f"- Berkas Word hasil duplikasi: '{artifact_name}' (tersimpan di folder kerja '{real_target}')\n"
                                f"- Status: Berhasil dibuat dengan struktur isi dokumen dan tabel sesuai berkas sumber.\n"
                                f"- Konfirmasikan dengan ramah kepada pengguna bahwa file Word duplikasi tersebut telah siap di panel Artefak."
                            )
                        else:
                            tool_failed = True
                            tool_failure_message = "Berkas Word hasil duplikasi berukuran 0 byte."
                    except Exception as exc:
                        tool_failed = True
                        tool_failure_message = str(exc)

                    if tool_failed:
                        if real_target.exists() and real_target.stat().st_size == 0:
                            try:
                                real_target.unlink()
                            except Exception:
                                pass
                        action_confirmation_note = (
                            f"PERINGATAN KEGAGALAN EKSEKUSI:\n"
                            f"- Gagal menduplikasi berkas '{src_pf['name']}': {tool_failure_message}\n"
                            f"- JANGAN mengatakan file berhasil dibuat!\n"
                            f"- Jelaskan secara jujur kepada pengguna bahwa proses duplikasi gagal."
                        )
            elif not is_duplication:
                base_stem = "Dokumen_Resmi" if is_word else ("Presentasi" if is_ppt else ("Laporan_Resmi" if is_pdf else "Rekap_Data"))
                ext = "docx" if is_word else ("pptx" if is_ppt else ("pdf" if is_pdf else "xlsx"))
                real_target = _generate_non_colliding_path(ws_dir, base_stem, ext)
                artifact_ext = ext
                artifact_name = real_target.name

                if ws_candidate.exists() and ws_candidate.is_dir():
                    if artifact_ext == "docx":
                        res = await tool_registry.execute(
                            "word_create_document",
                            file_path=str(real_target),
                            title="Dokumen Resmi AKSA",
                            style_preset="surat_resmi",
                        )
                    elif artifact_ext == "pptx":
                        res = await tool_registry.execute(
                            "ppt_create_presentation",
                            file_path=str(real_target),
                            title="Presentasi Eksekutif AKSA",
                        )
                    elif artifact_ext == "pdf":
                        res = await tool_registry.execute(
                            "pdf_generate_report",
                            file_path=str(real_target),
                            title="Laporan Resmi AKSA",
                        )
                    else:
                        res = await tool_registry.execute(
                            "excel_create_workbook",
                            file_path=str(real_target),
                        )

                    if res.success and real_target.exists() and real_target.stat().st_size > 0:
                        kb = round(real_target.stat().st_size / 1024, 1)
                        size_label = f"{kb} KB" if kb < 1024 else f"{round(kb / 1024, 2)} MB"
                        artifacts.append({
                            "id": f"art_{uuid.uuid4().hex[:8]}",
                            "name": artifact_name,
                            "file_path": str(real_target),
                            "file_type": artifact_ext,
                            "size_label": size_label,
                            "created_by_agent": delegated_agents[-1]["name"] if delegated_agents else supervisor["name"],
                            "created_at_label": "Baru saja",
                            "summary": res.summary,
                        })
                        action_confirmation_note = (
                            f"PEMBERITAHUAN GENERASI DOKUMEN:\n"
                            f"- Berkas '{artifact_name}' telah selesai dibuat di folder kerja pengguna.\n"
                            f"- Konfirmasikan kepada pengguna secara singkat dan profesional."
                        )
                    else:
                        tool_failed = True
                        tool_failure_message = res.summary if hasattr(res, "summary") else "Eksekusi alat pembuatan berkas gagal."
                        if real_target.exists() and real_target.stat().st_size == 0:
                            try:
                                real_target.unlink()
                            except Exception:
                                pass
                        action_confirmation_note = (
                            f"PERINGATAN KEGAGALAN EKSEKUSI:\n"
                            f"- Gagal membuat berkas '{artifact_name}': {tool_failure_message}\n"
                            f"- JANGAN mengatakan file berhasil dibuat!\n"
                            f"- Jelaskan secara jujur kepada pengguna bahwa proses pembuatan berkas gagal."
                        )

        grounded_system_prompt = (
            f"{supervisor['system_prompt']}\n\n"
            f"=== KONTEKS SISTEM & RUNTIME DESKTOP LOKAL (PENTING) ===\n"
            f"1. Anda beroperasi sebagai AKSA Desktop Assistant (Tauri v2 + Python Engine) yang berjalan langsung di komputer/PC pengguna.\n"
            f"2. Folder Kerja lokal aktif Anda di PC saat ini: '{ws_dir}'. Anda MEMILIKI AKSES LOKAL PENUH untuk membaca berkas, "
            f"menganalisis dokumen, membuat file baru (Excel .xlsx dengan rumus/grafik, Word .docx surat/laporan resmi, PowerPoint .pptx, PDF), "
            f"dan menjalankan automasi lokal di dalam folder tersebut.\n"
            f"3. {workspace_files_text}\n"
            + (f"\nCatatan Lampiran:\n" + "\n".join(pdf_extracted_notes) + "\n" if pdf_extracted_notes else "") +
            f"\n=== ATURAN MUTLAK CARA MENJAWAB PENGGUNA ===\n"
            f"1. JANGAN PERNAH menampilkan potongan kode Python seperti `import os`, `working_dir = ...`, atau pura-pura mengeksekusi os.listdir() "
            f"untuk menjawab pertanyaan mengenai isi folder! Anda BUKAN simulator kode; Anda adalah asisten kerja yang sudah memiliki hasil scan berkas nyata di atas.\n"
            f"2. Jika pengguna bertanya apa isi folder atau berkas apa yang ada, langsung sebutkan daftar berkas nyata tersebut secara ramah dan profesional dalam Bahasa Indonesia.\n"
            f"3. Jika ada berkas PDF yang ditanyakan atau diminta dibaca, jelaskan isi dokumen tersebut secara lengkap berdasarkan dokumen yang telah dilampirkan.\n"
            f"4. Jangan pernah mengatakan folder kerja kosong jika pada daftar berkas nyata di atas terdapat berkas!\n"
            f"5. Jika terjadi duplikasi berkas, pastikan memberikan konfirmasi sesuai hasil eksekusi nyata. Jika terdapat ambiguitas berkas, minta klarifikasi kepada pengguna secara jelas.\n"
        )

        # Supervisor synthesis call: receive sub-agent summaries if delegated, or answer directly
        if sub_agent_summaries:
            supervisor_msgs = [
                {"role": "system", "content": grounded_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Instruksi Pengguna: {prompt}\n"
                        f"Folder Kerja: {ws_dir}\n\n"
                        + (f"{action_confirmation_note}\n\n" if action_confirmation_note else "") +
                        f"Ringkasan Hasil Sub-Agen:\n" + "\n".join(sub_agent_summaries) + "\n\n"
                        "Sebagai Manajer Eksekutif, berikan rangkuman profesional dan informatif kepada pengguna dalam Bahasa Indonesia mengenai apa yang telah diselesaikan."
                    ),
                },
            ]
        else:
            supervisor_msgs = [
                {"role": "system", "content": grounded_system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        + (f"{action_confirmation_note}\n\n" if action_confirmation_note else "")
                    ),
                },
            ]

        sup_tool_schemas = tool_registry.get_schemas_for_categories(supervisor.get("tool_categories", []))
        sup_completion = await self.llm_router.complete(
            provider=supervisor["provider"],
            model_id=supervisor["model_id"],
            messages=supervisor_msgs,
            temperature=supervisor.get("temperature", 0.2),
            max_tokens=supervisor.get("max_tokens", 4096),
            tools=sup_tool_schemas if sup_tool_schemas else None,
            attachments=attachments,
            user_consent_granted=allow_external_disclosure,
        )
        sup_tokens = sup_completion["input_tokens"] + sup_completion["output_tokens"]
        total_tokens_used += sup_tokens

        # Dynamic tool execution loop for supervisor per P1-1
        loop_step = 0
        max_loops = 5
        while loop_step < max_loops:
            sup_tool_calls = sup_completion.get("tool_calls", [])
            if not sup_tool_calls:
                break
            loop_step += 1

            supervisor_msgs.append({
                "role": "assistant",
                "content": sup_completion.get("content") or "",
                "tool_calls": sup_tool_calls,
            })

            for tc in sup_tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                raw_args = fn.get("arguments", "{}")
                try:
                    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception:
                    fn_args = {}

                await ws_manager.broadcast_event(
                    "tool_started",
                    {"agent": supervisor["name"], "tool": fn_name, "arguments": fn_args},
                    session_id=session_id,
                )

                if "file_path" in fn_args:
                    fp = Path(fn_args["file_path"])
                    if not fp.is_absolute():
                        fn_args["file_path"] = str(ws_dir / fp)
                if "csv_source_path" in fn_args:
                    cp = Path(fn_args["csv_source_path"])
                    if not cp.is_absolute():
                        fn_args["csv_source_path"] = str(ws_dir / cp)

                res = await tool_registry.execute(fn_name, session_id=session_id, **fn_args)

                await ws_manager.broadcast_event(
                    "tool_finished",
                    {"agent": supervisor["name"], "tool": fn_name, "success": res.success, "summary": res.summary},
                    session_id=session_id,
                )

                if res.success and res.artifacts:
                    for art_str in res.artifacts:
                        art_p = Path(art_str)
                        if art_p.exists() and art_p.stat().st_size > 0:
                            kb = round(art_p.stat().st_size / 1024, 1)
                            size_label = f"{kb} KB" if kb < 1024 else f"{round(kb / 1024, 2)} MB"
                            artifacts.append({
                                "id": f"art_{uuid.uuid4().hex[:8]}",
                                "name": art_p.name,
                                "file_path": str(art_p),
                                "file_type": art_p.suffix.lstrip(".").lower(),
                                "size_label": size_label,
                                "created_by_agent": supervisor["name"],
                                "created_at_label": "Baru saja",
                                "summary": res.summary,
                            })

                supervisor_msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    "name": fn_name,
                    "content": res.summary if res.success else f"Error: {res.summary}",
                })

            sup_completion = await self.llm_router.complete(
                provider=supervisor["provider"],
                model_id=supervisor["model_id"],
                messages=supervisor_msgs,
                temperature=supervisor.get("temperature", 0.2),
                max_tokens=supervisor.get("max_tokens", 4096),
                tools=sup_tool_schemas if sup_tool_schemas else None,
                attachments=attachments,
                user_consent_granted=allow_external_disclosure,
            )
            sup_tokens = sup_completion["input_tokens"] + sup_completion["output_tokens"]
            total_tokens_used += sup_tokens

        await self._log_token_usage(
            session_id=session_id,
            agent=supervisor,
            input_tokens=sup_completion["input_tokens"],
            output_tokens=sup_completion["output_tokens"],
            tokens_saved=0,
            cost_usd=0.0012,
        )

        if is_ambiguous_duplication:
            final_reply = clarification_text
        elif tool_failed:
            final_reply = f"Gagal memproses dokumen: {tool_failure_message}. Berkas tidak berhasil dibuat di folder kerja."
        else:
            final_reply = sup_completion["content"]
            if artifacts and not any(a["name"] in final_reply for a in artifacts):
                art_names = ", ".join(f"**`{a['name']}`**" for a in artifacts)
                final_reply += f"\n\nFile hasil kerja {art_names} telah siap di panel Artefak."

        if not execution_steps:
            execution_steps.append(
                {
                    "id": f"step_{uuid.uuid4().hex[:8]}",
                    "agent_name": supervisor["name"],
                    "agent_role": supervisor["role_title"],
                    "provider": supervisor["provider"],
                    "model_id": supervisor["model_id"],
                    "action_label": f"Menganalisis instruksi & memeriksa Folder Kerja {ws_dir.name}",
                    "detail": "Menjawab langsung sebagai Manajer Utama dengan akses lokal aktif.",
                    "status": "completed",
                    "tokens_used": sup_tokens,
                    "tokens_saved": 0,
                }
            )

        await ws_manager.broadcast_event(
            "token_metrics_updated",
            {
                "tokens_used": total_tokens_used,
                "tokens_saved": total_tokens_saved,
                "artifact": artifacts[0] if artifacts else None,
            },
            session_id=session_id,
        )

        # Compute granular task outcome reflecting actual tool execution & artifact postconditions (AKSA-AGENT-003-R5)
        has_failed_step = any(s.get("status") == "failed" for s in execution_steps)
        has_succeeded_step = any(s.get("status") in ("completed", "success") for s in execution_steps)
        postcondition_error_reason: str | None = None

        if is_ambiguous_duplication:
            task_outcome = TaskOutcome.CANCELLED
        elif tool_failed or has_failed_step:
            task_outcome = TaskOutcome.PARTIAL_SUCCESS if has_succeeded_step else TaskOutcome.FAILED
        else:
            postcondition_failed = False
            if artifacts:
                for art_entry in artifacts:
                    raw_path = art_entry.get("file_path") if isinstance(art_entry, dict) else art_entry
                    if not raw_path:
                        continue
                    art_path = Path(str(raw_path))
                    expected_schema = derive_expected_artifact_schema(
                        prompt, art_path, plan_spec=pre_execution_expectation
                    )
                    ok, reason = verify_artifact_postcondition(art_path, expected_schema=expected_schema)
                    if not ok:
                        postcondition_failed = True
                        postcondition_error_reason = reason
                        break
            if postcondition_failed:
                task_outcome = TaskOutcome.UNVERIFIED
                logger.warning("[AKSA Orchestrator] Validasi postcondition artefak gagal: %s", postcondition_error_reason)
            else:
                task_outcome = TaskOutcome.SUCCESS

        actual_success = (task_outcome == TaskOutcome.SUCCESS)

        # Record episodic task & evaluate candidate skills under isolated agent storage (AKSA-AGENT-002, AKSA-AGENT-003)
        try:
            from app.core.agent_learning import AgentMemoryService, SkillCandidateExtractor
            sup_agent_id = supervisor.get("id") or "supervisor"
            tools_called = [s.get("action_label", "") for s in execution_steps]
            task_uid = f"task_{uuid.uuid4().hex[:8]}"

            # 1. Record in isolated storage for each executing sub-agent
            for sub in delegated_agents:
                sub_id = sub.get("id") or sub.get("name")
                if sub_id and sub_id != sup_agent_id:
                    mem_sub = AgentMemoryService(sub_id)
                    mem_sub.record_episodic_task(
                        task_id=f"{task_uid}_{sub_id[:6]}",
                        session_id=session_id or "default",
                        intent=prompt[:150],
                        summary=f"[{sub.get('name')}] [{task_outcome.value}] " + final_reply[:200],
                        tools_used=tools_called,
                        success=actual_success,
                    )
                    if actual_success:
                        ext_sub = SkillCandidateExtractor(sub_id)
                        ext_sub.evaluate_task_for_learning(
                            task_id=f"{task_uid}_{sub_id[:6]}",
                            intent=prompt,
                            tools_used=tools_called,
                            success=actual_success,
                            user_explicit_teach="jadikan skill" in prompt.lower() or "pelajari ini" in prompt.lower(),
                            outcome=task_outcome.value,
                            execution_trace=execution_steps,
                        )

            # 2. Record in supervisor isolated memory
            mem_sup = AgentMemoryService(sup_agent_id)
            mem_sup.record_episodic_task(
                task_id=task_uid,
                session_id=session_id or "default",
                intent=prompt[:150],
                summary=f"[{task_outcome.value}] " + final_reply[:200],
                tools_used=tools_called,
                success=actual_success,
            )
            extractor = SkillCandidateExtractor(sup_agent_id)
            extractor.evaluate_task_for_learning(
                task_id=task_uid,
                intent=prompt,
                tools_used=tools_called,
                success=actual_success,
                user_explicit_teach="jadikan skill" in prompt.lower() or "pelajari ini" in prompt.lower(),
                outcome=task_outcome.value,
                execution_trace=execution_steps,
            )
        except Exception:
            logger.exception("[AKSA Orchestrator] Gagal mencatat memori episodik / pembelajaran agen")

        return {
            "supervisor_name": supervisor["name"],
            "reply": final_reply,
            "task_outcome": task_outcome.value,
            "postcondition_error": postcondition_error_reason,
            "execution_steps": execution_steps,
            "artifacts": artifacts,
            "tokens_used": total_tokens_used,
            "tokens_saved": total_tokens_saved,
        }

