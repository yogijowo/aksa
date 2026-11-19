"""Standalone Pure-Python Artifact Postcondition Verifier (Cycle 9 & 10 Hardened).

Deliberately imports NO server, database, config, WebSocket, or LLM dependencies so the
worker process running inside the OS sandbox (Seatbelt / Bubblewrap / AppContainer) has a
minimal attack surface and zero access to application configuration or home directories.

Security properties:
- Opens regular files once atomically via ``O_NOFOLLOW`` + ``os.fstat`` (eliminates
  TOCTOU symlink/file-swap races between stat validation and parser execution).
- Validates intermediate path components inside an optional workspace for symlinks.
- Enforces server-side ``max_bytes`` clamping and pre-parser OOXML ZIP bomb / sheet /
  dimension / PDF text complexity bounds.
- Evaluates supported Excel formulas deterministically and fails closed on unsupported
  formulas (``semantic_status = "unverified_formula"``) without trusting cached ``<v>``.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import operator
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any

MAX_ARTIFACT_VERIFY_BYTES: int = 25 * 1024 * 1024
MAX_ZIP_ENTRIES: int = 2000
MAX_ZIP_UNCOMPRESSED_BYTES: int = 50 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO: float = 50.0
MAX_EXCEL_SHEETS: int = 50
MAX_EXCEL_PARSE_CELLS: int = 250_000
MAX_PDF_PARSE_PAGES: int = 500
MAX_PDF_TEXT_CHARS: int = 5 * 1024 * 1024
_EXCEL_ERROR_TOKENS: frozenset[str] = frozenset({
    "#REF!",
    "#DIV/0!",
    "#VALUE!",
    "#NAME?",
    "#N/A",
    "#NUM!",
    "#NULL!",
})


def sanitize_verifier_schema(expected_schema: dict[str, Any] | None) -> dict[str, Any]:
    """Clamp caller max_bytes strictly within [1, MAX_ARTIFACT_VERIFY_BYTES] (P2-01)."""
    schema = dict(expected_schema) if isinstance(expected_schema, dict) else {}
    if "max_bytes" in schema:
        try:
            req_max = int(schema["max_bytes"])
        except (TypeError, ValueError):
            req_max = MAX_ARTIFACT_VERIFY_BYTES
        schema["max_bytes"] = min(max(1, req_max), MAX_ARTIFACT_VERIFY_BYTES)
    else:
        schema["max_bytes"] = MAX_ARTIFACT_VERIFY_BYTES
    return schema


def check_no_symlink_components(art_path: Path, workspace: Path | None = None) -> tuple[bool, str]:
    """Ensure ``art_path`` and any relative directory segments under ``workspace`` are not symlinks."""
    if art_path.is_symlink():
        return False, f"Artefak symlink ditolak oleh gerbang verifikasi: {art_path}"

    if workspace is None:
        return True, ""

    try:
        ws_real = workspace.resolve(strict=False)
        art_real = art_path.resolve(strict=False)
        if not art_real.is_relative_to(ws_real):
            return False, f"Artefak berada di luar batas workspace terotorisasi: {art_path}"

        # Walk lexical components from workspace down to art_path to catch intermediate symlinks
        ws_abs = Path(os.path.abspath(str(workspace)))
        art_abs = Path(os.path.abspath(str(art_path)))
        try:
            rel = art_abs.relative_to(ws_abs)
            cursor = ws_abs
        except ValueError:
            rel = art_real.relative_to(ws_real)
            cursor = ws_real

        for part in rel.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                return False, f"Komponen path symlink di dalam workspace ditolak: {cursor}"
    except Exception as exc:
        return False, f"Gagal memvalidasi batas path artefak: {exc}"

    return True, ""


def _read_verified_regular_file(
    art_path: Path,
    max_bytes: int,
    workspace: Path | None = None,
) -> tuple[bytes | None, int, str]:
    """Open ``art_path`` once with ``O_NOFOLLOW`` + ``os.fstat`` to prevent TOCTOU races."""
    sym_ok, sym_err = check_no_symlink_components(art_path, workspace=workspace)
    if not sym_ok:
        return None, 0, sym_err

    if not art_path.exists():
        return None, 0, f"File tidak ditemukan: {art_path}"

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(str(art_path), flags)
    except OSError as exc:
        return None, 0, f"Gagal membuka file artefak secara aman: {exc}"

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return None, 0, f"Artefak bukan file reguler yang sah: {art_path}"
        if st.st_size == 0:
            return None, 0, f"File berukuran 0 byte: {art_path}"
        if st.st_size > max_bytes:
            return (
                None,
                st.st_size,
                f"Ukuran artefak ({st.st_size} bytes) melebihi batas verifikasi aman ({max_bytes} bytes).",
            )

        chunks: list[bytes] = []
        total_read = 0
        with os.fdopen(fd, "rb", closefd=False) as fp:
            while True:
                remaining = (max_bytes + 1) - total_read
                chunk = fp.read(min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                total_read += len(chunk)
                if total_read > max_bytes:
                    return (
                        None,
                        total_read,
                        f"Ukuran artefak ({total_read} bytes) melebihi batas verifikasi aman ({max_bytes} bytes).",
                    )
        if total_read == 0:
            return None, 0, f"File berukuran 0 byte: {art_path}"
        return b"".join(chunks), total_read, ""
    except Exception as exc:
        return None, 0, f"Gagal membaca isi file artefak: {exc}"
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def _validate_office_zip_container(source: Path | bytes, suffix: str) -> tuple[bool, str]:
    """Inspect Office OOXML ZIP container metadata BEFORE opening heavy parsers (ZIP bomb & dimension guard)."""
    label_map = {
        ".xlsx": "Integritas Excel (.xlsx)",
        ".xlsm": "Integritas Excel (.xlsm)",
        ".docx": "Integritas dokumen Word (.docx)",
        ".pptx": "Integritas PowerPoint (.pptx)",
    }
    label = label_map.get(suffix, f"Integritas Office ({suffix})")

    zip_arg: Any = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source)
    if not zipfile.is_zipfile(zip_arg):
        return False, f"{label} tidak valid atau bukan arsip ZIP yang sah."

    sheet_entries = 0
    total_uncompressed = 0
    total_compressed = 0

    try:
        zf_target: Any = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else str(source)
        with zipfile.ZipFile(zf_target, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                return False, f"Arsip Office mengandung terlalu banyak entry ZIP ({len(infos)} > {MAX_ZIP_ENTRIES})."

            for info in infos:
                fname = str(info.filename or "")
                norm = fname.replace("\\", "/")
                if norm.startswith("/") or ".." in Path(norm).parts:
                    return False, f"Entry ZIP berbahaya terdeteksi dalam dokumen Office: '{fname}'."

                u_sz = int(info.file_size or 0)
                c_sz = int(info.compress_size or 0)
                if u_sz < 0 or c_sz < 0 or u_sz > MAX_ZIP_UNCOMPRESSED_BYTES:
                    return False, f"Entry XML Office '{fname}' melebihi batas dekompresi aman ({MAX_ZIP_UNCOMPRESSED_BYTES} bytes)."
                total_uncompressed += u_sz
                total_compressed += c_sz
                if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                    return False, f"Total ukuran dekompresi dokumen Office melebihi batas aman ({MAX_ZIP_UNCOMPRESSED_BYTES} bytes)."

                if suffix in (".xlsx", ".xlsm") and norm.startswith("xl/worksheets/sheet") and norm.endswith(".xml"):
                    sheet_entries += 1
                    if sheet_entries > MAX_EXCEL_SHEETS:
                        return False, f"Jumlah sheet Excel ({sheet_entries}) melebihi batas aman ({MAX_EXCEL_SHEETS})."
                    with zf.open(info, "r") as sf:
                        header_bytes = sf.read(4096)
                    header_str = header_bytes.decode("utf-8", errors="ignore")
                    dim_match = re.search(r'<dimension\b[^>]*\bref=["\']([A-Za-z0-9:]+)["\']', header_str)
                    if dim_match and ":" in dim_match.group(1):
                        from openpyxl.utils.cell import range_boundaries

                        try:
                            min_c, min_r, max_c, max_r = range_boundaries(dim_match.group(1).upper())
                            cell_span = (max_r - min_r + 1) * (max_c - min_c + 1)
                            if cell_span > MAX_EXCEL_PARSE_CELLS:
                                return False, f"Dimensi worksheet Excel terlalu besar ({cell_span} sel > {MAX_EXCEL_PARSE_CELLS})."
                        except Exception:
                            return False, "Deklarasi dimensi worksheet Excel tidak valid."

            if total_uncompressed > 512 * 1024:
                ratio = total_uncompressed / max(1, total_compressed)
                if ratio > MAX_ZIP_COMPRESSION_RATIO:
                    return False, f"Rasio kompresi ZIP Office mencurigakan ({ratio:.1f}:1 > {MAX_ZIP_COMPRESSION_RATIO}:1)."
    except Exception as exc:
        return False, f"Gagal memvalidasi kontainer ZIP Office ({suffix}): {exc}"

    return True, ""


def _safe_eval_arithmetic_expr(expr: str, resolve_cell_fn: Any) -> float | None:
    """Safely evaluate basic parenthesized arithmetic over numeric literals and Excel cell refs."""
    token_re = re.compile(r"\$?([A-Z]{1,3})\$?(\d+)", re.IGNORECASE)
    mapping: dict[str, float] = {}
    idx = 0

    def _replace_cell(match: re.Match[str]) -> str:
        nonlocal idx
        coord = f"{match.group(1).upper()}{match.group(2)}"
        val = resolve_cell_fn(coord)
        if val is None:
            raise ValueError("missing_cell")
        sym = f"_c{idx}"
        idx += 1
        mapping[sym] = float(val)
        return sym

    try:
        rewritten = token_re.sub(_replace_cell, expr)
        tree = ast.parse(rewritten, mode="eval")
    except Exception:
        return None

    bin_ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    un_ops = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id in mapping:
            return mapping[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in un_ops:
            return un_ops[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in bin_ops:
            rhs = _eval(node.right)
            if isinstance(node.op, ast.Div) and rhs == 0.0:
                raise ZeroDivisionError("div0")
            return float(bin_ops[type(node.op)](_eval(node.left), rhs))
        raise ValueError("unsupported_ast")

    try:
        return float(_eval(tree))
    except Exception:
        return None


def _evaluate_basic_excel_formula(
    formula: str,
    ws_val: Any,
    ws_fml: Any,
    *,
    _depth: int = 0,
    _seen: set[str] | None = None,
) -> float | None:
    """Deterministically evaluate supported Excel formulas (SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, PRODUCT, ABS, ROUND, arithmetic).

    Returns ``None`` for any unsupported function/expression so callers fail closed rather
    than trusting unverified cached workbook values.
    """
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
        c_up = coord.strip().upper().replace("$", "")
        if c_up in seen_set:
            return None
        try:
            row_i, col_i = coordinate_to_tuple(c_up)
        except Exception:
            return None
        v_raw = ws_val.cell(row=row_i, column=col_i).value
        f_raw = ws_fml.cell(row=row_i, column=col_i).value
        if isinstance(f_raw, str) and f_raw.startswith("="):
            return _evaluate_basic_excel_formula(
                f_raw, ws_val, ws_fml, _depth=_depth + 1, _seen=seen_set | {c_up}
            )
        if isinstance(v_raw, (int, float)) and not isinstance(v_raw, bool):
            return float(v_raw)
        if isinstance(f_raw, (int, float)) and not isinstance(f_raw, bool):
            return float(f_raw)
        return None

    def _cell_nonempty(coord: str) -> bool:
        c_up = coord.strip().upper().replace("$", "")
        try:
            row_i, col_i = coordinate_to_tuple(c_up)
        except Exception:
            return False
        v_raw = ws_val.cell(row=row_i, column=col_i).value
        f_raw = ws_fml.cell(row=row_i, column=col_i).value
        return (v_raw is not None and str(v_raw).strip() != "") or (f_raw is not None and str(f_raw).strip() != "")

    outer_match = re.fullmatch(r"([A-Z]+)\s*\((.*)\)", body, re.IGNORECASE)
    if outer_match:
        fn_name = outer_match.group(1).upper()
        inner_raw = outer_match.group(2).strip()
        if fn_name in {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "PRODUCT"}:
            nums: list[float] = []
            tokens: list[str] = []
            buf: list[str] = []
            p_depth = 0
            for ch in inner_raw:
                if ch == "(":
                    p_depth += 1
                elif ch == ")":
                    p_depth -= 1
                if ch == "," and p_depth == 0:
                    tokens.append("".join(buf).strip())
                    buf = []
                else:
                    buf.append(ch)
            if buf:
                tokens.append("".join(buf).strip())

            for part in tokens:
                if not part:
                    continue
                if ":" in part and "(" not in part:
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
                elif "(" in part:
                    sub_v = _evaluate_basic_excel_formula(
                        f"={part}", ws_val, ws_fml, _depth=_depth + 1, _seen=seen_set
                    )
                    if sub_v is None:
                        return None
                    nums.append(sub_v)
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
            if fn_name == "PRODUCT":
                prod = 1.0
                for n in nums:
                    prod *= n
                return float(prod)

        if fn_name == "COUNTA" and "(" not in inner_raw:
            count_nonempty = 0
            for token in inner_raw.split(","):
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
                            if _cell_nonempty(f"{get_column_letter(cc)}{rr}"):
                                count_nonempty += 1
                elif _cell_nonempty(part):
                    count_nonempty += 1
            return float(count_nonempty)

        if fn_name == "ABS":
            inner = _evaluate_basic_excel_formula(
                f"={inner_raw}", ws_val, ws_fml, _depth=_depth + 1, _seen=seen_set
            )
            return None if inner is None else float(abs(inner))

        if fn_name == "ROUND":
            args: list[str] = []
            buf_r: list[str] = []
            r_depth = 0
            for ch in inner_raw:
                if ch == "(":
                    r_depth += 1
                elif ch == ")":
                    r_depth -= 1
                if ch == "," and r_depth == 0:
                    args.append("".join(buf_r).strip())
                    buf_r = []
                else:
                    buf_r.append(ch)
            if buf_r:
                args.append("".join(buf_r).strip())
            if len(args) != 2:
                return None
            inner = _evaluate_basic_excel_formula(
                f"={args[0]}", ws_val, ws_fml, _depth=_depth + 1, _seen=seen_set
            )
            try:
                digits = int(args[1])
            except ValueError:
                return None
            return None if inner is None else float(round(inner, digits))

        return None

    return _safe_eval_arithmetic_expr(body, _cell_num)


def get_artifact_postcondition_breakdown(
    art_path: Path,
    expected_schema: dict[str, Any] | None = None,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Inspect and validate an artifact across four orthogonal gates (Cycles 9 & 10 hardening):
    1. ``file_created`` — non-zero byte regular file (atomic ``O_NOFOLLOW``, bounded size).
    2. ``format_valid`` — ZIP/PDF container & parser open the format cleanly within complexity caps.
    3. ``content_detected`` — non-trivial real structural content exists.
    4. ``task_requirement_satisfied`` — matches expected schema & deterministic Excel formula rules.
    """
    schema = sanitize_verifier_schema(expected_schema)
    res: dict[str, Any] = {
        "file_created": False,
        "format_valid": False,
        "content_detected": False,
        "task_requirement_satisfied": False,
        "semantic_postcondition_passed": False,
        "semantic_status": "failed",  # passed | failed | unsupported | unverified_formula
        "unsupported_format": False,
        "unverified_formulas": [],
        "detail": "",
    }
    raw_bytes, _, read_err = _read_verified_regular_file(
        art_path,
        schema["max_bytes"],
        workspace=workspace,
    )
    if raw_bytes is None:
        res["detail"] = read_err
        return res

    res["file_created"] = True
    suffix = art_path.suffix.lower()

    expected_ext = str(schema.get("expected_extension", "") or "").strip().lower()
    if expected_ext and not expected_ext.startswith("."):
        expected_ext = f".{expected_ext}"
    if expected_ext and suffix != expected_ext:
        res["detail"] = f"Format artefak '{suffix}' tidak sesuai target tugas '{expected_ext}'."
        return res

    if suffix in (".xlsx", ".xlsm", ".docx", ".pptx"):
        zip_ok, zip_err = _validate_office_zip_container(raw_bytes, suffix)
        if not zip_ok:
            res["detail"] = zip_err
            return res

    if suffix in (".xlsx", ".xlsm"):
        wb_val = None
        wb_fml = None
        try:
            import openpyxl
            wb_val = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
            wb_fml = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=False)
            if not wb_val.sheetnames:
                res["detail"] = f"Buku kerja Excel kosong tanpa lembar kerja: {art_path}"
                return res
            if len(wb_val.sheetnames) > MAX_EXCEL_SHEETS:
                res["detail"] = f"Jumlah sheet Excel ({len(wb_val.sheetnames)}) melebihi batas aman ({MAX_EXCEL_SHEETS})."
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
            unverified_formulas: list[str] = []
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
                            if computed is None:
                                unverified_formulas.append(f"{sname}!{coord}:{fml_str}")
                                non_empty_cells += 1
                                continue
                            if (
                                isinstance(val_v, (int, float))
                                and not isinstance(val_v, bool)
                                and abs(float(val_v) - computed) > 1e-4
                            ):
                                excel_error = (
                                    f"Nilai cache rumus pada {sname}!{coord} ({val_v}) tidak sesuai hasil "
                                    f"kalkulasi '{fml_str}' ({computed})."
                                )
                                break
                            cell_values_map.setdefault(coord, computed)
                            cell_values_map[f"{sname}!{coord}"] = computed
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

            if unverified_formulas:
                res["unverified_formulas"] = unverified_formulas
                res["semantic_status"] = "unverified_formula"
                res["detail"] = (
                    f"Formula Excel tidak didukung evaluator independen dan cached value ditolak "
                    f"(unverified_formula): {unverified_formulas[:3]}"
                )
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
            doc = docx.Document(io.BytesIO(raw_bytes))
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
            prs = Presentation(io.BytesIO(raw_bytes))
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
        doc = None
        try:
            import pymupdf as fitz
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            if doc.page_count < 1:
                res["detail"] = f"Dokumen PDF tidak memiliki halaman: {art_path}"
                return res
            if doc.page_count > MAX_PDF_PARSE_PAGES:
                res["detail"] = f"Jumlah halaman PDF ({doc.page_count}) melebihi batas verifikasi aman ({MAX_PDF_PARSE_PAGES})."
                return res
            res["format_valid"] = True
            page_count = doc.page_count
            page_texts: list[str] = []
            total_chars = 0
            has_images = False
            for page in doc:
                if len(page.get_images()) > 0:
                    has_images = True
                pt = page.get_text().strip()
                total_chars += len(pt)
                if total_chars > MAX_PDF_TEXT_CHARS:
                    res["detail"] = f"Total teks PDF melebihi batas ekstraksi aman ({MAX_PDF_TEXT_CHARS} karakter)."
                    return res
                page_texts.append(pt)
            extracted_text = "\n".join(page_texts).strip()

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
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    elif suffix == ".json":
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
            res["format_valid"] = True
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
            raw = raw_bytes.decode("utf-8", errors="replace")
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
            text = raw_bytes.decode("utf-8", errors="replace")
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

    if isinstance(plan_spec, dict):
        for k, v in plan_spec.items():
            if v is not None:
                schema[k] = list(v) if isinstance(v, list) else v

    if (not suffix or suffix in (".xlsx", ".xlsm")) and any(
        k in p_lower for k in ("rumus", "formula", "=sum", "=average", "kalkulasi otomatis")
    ):
        schema["require_formulas"] = True

    col_match = re.search(
        r"(?:\bkolom\b|\bcolumns?\b|\bheader\b)\s*(?::|terdiri\s+dari|berisi|yaitu|=)?\s*([^\n.;]+)",
        text,
        re.IGNORECASE,
    )
    if col_match:
        frag = re.split(r"\b(?:dengan\s+rumus|minimal\s+\d+|serta\s+grafik|beserta)\b", col_match.group(1), flags=re.IGNORECASE)[0]
        cols = _split_expectation_list(frag)
        if cols:
            existing = list(schema.get("required_columns", []))
            for c in cols:
                if c not in existing:
                    existing.append(c)
            schema["required_columns"] = existing

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
    *,
    workspace: Path | None = None,
) -> tuple[bool, str]:
    """Verify that an artifact exists, is valid format, contains real content, and meets task requirements."""
    breakdown = get_artifact_postcondition_breakdown(
        art_path,
        expected_schema=expected_schema,
        workspace=workspace,
    )
    is_ok = bool(
        breakdown["file_created"]
        and breakdown["format_valid"]
        and breakdown["content_detected"]
        and breakdown["task_requirement_satisfied"]
        and breakdown["semantic_postcondition_passed"]
        and not breakdown["unsupported_format"]
    )
    return is_ok, breakdown["detail"]

