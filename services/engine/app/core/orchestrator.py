"""Hierarchical Supervisor -> Sub-Agent Execution Engine with Context Isolation."""

from __future__ import annotations

import base64
import json
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import aiosqlite


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


def verify_artifact_postcondition(art_path: Path) -> tuple[bool, str]:
    """Verify that an artifact file exists, is non-empty, and satisfies format-specific integrity (AKSA-AGENT-003-R3)."""
    if not art_path.exists():
        return False, f"File tidak ditemukan: {art_path}"
    try:
        if art_path.stat().st_size == 0:
            return False, f"File berukuran 0 byte: {art_path}"
    except Exception as exc:
        return False, f"Gagal membaca stat file: {exc}"

    suffix = art_path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(art_path), read_only=True)
            if not wb.sheetnames:
                return False, f"Buku kerja Excel kosong tanpa lembar kerja: {art_path}"
            wb.close()
        except Exception as exc:
            return False, f"Integritas Excel (.xlsx) tidak valid atau korup: {exc}"
    elif suffix == ".docx":
        try:
            import docx
            _ = docx.Document(str(art_path))
        except Exception as exc:
            return False, f"Integritas dokumen Word (.docx) tidak valid atau korup: {exc}"
    elif suffix == ".pdf":
        try:
            import pymupdf as fitz
            doc = fitz.open(str(art_path))
            if doc.page_count < 1:
                doc.close()
                return False, f"Dokumen PDF tidak memiliki halaman: {art_path}"
            doc.close()
        except Exception as exc:
            return False, f"Integritas PDF tidak valid atau korup: {exc}"
    elif suffix == ".json":
        try:
            import json
            json.loads(art_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"Integritas JSON tidak valid atau korup: {exc}"

    return True, "Valid"


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

        # Record episodic task & evaluate candidate skills under isolated agent storage (AKSA-AGENT-002, AKSA-AGENT-003)
        try:
            from app.core.agent_learning import AgentMemoryService, SkillCandidateExtractor
            sup_agent_id = supervisor.get("id") or "supervisor"
            tools_called = [s.get("action_label", "") for s in execution_steps]

            # Compute granular task outcome reflecting actual tool execution & artifact postconditions (AKSA-AGENT-003-R2)
            has_failed_step = any(s.get("status") == "failed" for s in execution_steps)
            has_succeeded_step = any(s.get("status") in ("completed", "success") for s in execution_steps)

            if is_ambiguous_duplication:
                task_outcome = TaskOutcome.CANCELLED
            elif tool_failed:
                task_outcome = TaskOutcome.PARTIAL_SUCCESS if has_succeeded_step else TaskOutcome.FAILED
            elif has_failed_step:
                task_outcome = TaskOutcome.PARTIAL_SUCCESS if has_succeeded_step else TaskOutcome.FAILED
            else:
                postcondition_failed = False
                postcondition_error_reason: str | None = None
                if artifacts:
                    for art_path_str in artifacts:
                        art_path = Path(art_path_str)
                        ok, reason = verify_artifact_postcondition(art_path)
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

            task_uid = f"task_{uuid.uuid4().hex[:8]}"

            # 1. Record in isolated storage for each executing sub-agent
            for sub in sub_agents_to_run:
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
            pass

        return {
            "supervisor_name": supervisor["name"],
            "reply": final_reply,
            "execution_steps": execution_steps,
            "artifacts": artifacts,
            "tokens_used": total_tokens_used,
            "tokens_saved": total_tokens_saved,
        }

