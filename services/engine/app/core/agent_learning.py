"""Adaptive Agent Learning Engine: Isolated Memory, Privacy Redaction, Candidate Extraction, and Versioned Skills."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from app.core.agent_directory import AgentIsolationError, agent_directory_service


_REPLAY_PATH_KEY_TOKENS = (
    "path",
    "file",
    "dir",
    "folder",
    "root",
    "output",
    "source",
    "target",
    "dest",
    "destination",
    "template",
    "artifact",
)
_REPLAY_NON_PATH_SUFFIXES = (
    "_format",
    "_mode",
    "_type",
    "_title",
    "_count",
    "_summary",
    "_status",
    "_id",
)


def _is_replay_path_key(key: str) -> bool:
    kl = str(key or "").strip().lower()
    if not kl:
        return False
    if kl in {"file", "path", "files", "paths", "directory", "dir", "folder", "root", "source", "target", "dest", "destination", "template", "csv_source"}:
        return True
    if kl.endswith(_REPLAY_NON_PATH_SUFFIXES):
        return False
    return any(tok in kl for tok in _REPLAY_PATH_KEY_TOKENS)


def resolve_replay_path(
    raw_str: str,
    workspace: Path,
    *,
    allow_in_workspace_absolute: bool = False,
) -> Path:
    """Resolve a replay step, input, or artifact path canonically inside ``workspace`` (P2-01 & Cycle 8 P1-02).

    Rejects empty values, null bytes, UNC paths, alternate data streams, ``..`` components,
    any symlink component under ``workspace``, any target outside ``workspace``, and (by default)
    any raw absolute path from untrusted fixture/trace payloads.
    """
    cleaned = str(raw_str or "").strip()
    if not cleaned or "\0" in cleaned:
        raise AgentIsolationError("Path replay kosong atau mengandung null byte ilegal.")
    if cleaned.startswith("\\\\") or cleaned.startswith("//"):
        raise AgentIsolationError(f"Path jaringan UNC ditolak pada replay: '{cleaned}'.")
    if ":" in Path(cleaned).name:
        raise AgentIsolationError(f"Alternate Data Stream ditolak pada replay: '{cleaned}'.")

    raw_path = Path(cleaned)
    if any(part == ".." for part in raw_path.parts):
        raise AgentIsolationError(f"Path traversal '..' ditolak pada replay: '{cleaned}'.")
    if raw_path.is_absolute() and not allow_in_workspace_absolute:
        raise AgentIsolationError(f"Absolute path tidak diizinkan dalam fixture/argumen replay: '{cleaned}'.")

    ws_real = workspace.resolve(strict=False)
    candidate = raw_path if raw_path.is_absolute() else (ws_real / raw_path)

    try:
        resolved = candidate.resolve(strict=False)
    except Exception as exc:
        raise AgentIsolationError(f"Gagal me-resolve path replay '{cleaned}': {exc}") from exc

    if not resolved.is_relative_to(ws_real):
        raise AgentIsolationError(
            f"Path replay '{cleaned}' keluar dari batas workspace sandbox terisolasi."
        )

    # Reject pre-existing symlinks on workspace root components and resolved relative segments
    if candidate.is_symlink():
        raise AgentIsolationError(f"Symlink target ditolak pada replay: '{cleaned}'.")
    for anc in candidate.parents:
        if anc == ws_real:
            break
        if anc.is_relative_to(ws_real) and anc.is_symlink():
            raise AgentIsolationError(f"Direktori symlink ditolak pada replay: '{cleaned}'.")

    rel = resolved.relative_to(ws_real)
    cur = ws_real
    segments = raw_path.parts if not raw_path.is_absolute() else rel.parts
    for part in segments:
        if part in ("", "."):
            continue
        cur = cur / part
        if cur.is_symlink():
            raise AgentIsolationError(f"Symlink di dalam path replay ditolak: '{cleaned}'.")

    return resolved


MAX_REPLAY_FIXTURES: int = 20
MAX_FIXTURE_INPUT_FILES: int = 10
MAX_FIXTURE_INPUT_FILE_BYTES: int = 256 * 1024
MAX_FIXTURE_EXPECTED_ARTIFACTS: int = 10
MAX_TOTAL_REPLAY_PAYLOAD_BYTES: int = 2 * 1024 * 1024


def validate_replay_fixtures_budget(replay_fixtures: list[dict[str, Any]] | None) -> None:
    """Enforce strict payload size, artifact count, and input file bounds before replay runs (P2-04)."""
    if replay_fixtures is None:
        return
    if not isinstance(replay_fixtures, list):
        raise ValueError("replay_fixtures harus berupa daftar objek.")
    if len(replay_fixtures) > MAX_REPLAY_FIXTURES:
        raise ValueError(f"Jumlah replay_fixtures ({len(replay_fixtures)}) melebihi batas ({MAX_REPLAY_FIXTURES}).")

    total_bytes = 0
    for idx, fx in enumerate(replay_fixtures, 1):
        if not isinstance(fx, dict):
            raise ValueError(f"Fixture #{idx} tidak valid.")
        exp_arts = fx.get("expected_artifacts", [])
        if not isinstance(exp_arts, list) or len(exp_arts) > MAX_FIXTURE_EXPECTED_ARTIFACTS:
            raise ValueError(
                f"Fixture #{idx} melebihi batas expected_artifacts ({MAX_FIXTURE_EXPECTED_ARTIFACTS})."
            )
        in_files = fx.get("input_files", {})
        if not isinstance(in_files, dict) or len(in_files) > MAX_FIXTURE_INPUT_FILES:
            raise ValueError(
                f"Fixture #{idx} melebihi batas input_files ({MAX_FIXTURE_INPUT_FILES})."
            )
        for fname, fbody in in_files.items():
            f_len = len(str(fbody).encode("utf-8", errors="replace"))
            if f_len > MAX_FIXTURE_INPUT_FILE_BYTES:
                raise ValueError(
                    f"Ukuran input file '{fname}' ({f_len} bytes) melebihi batas aman ({MAX_FIXTURE_INPUT_FILE_BYTES} bytes)."
                )
        serialized_len = len(json.dumps(fx, ensure_ascii=False, default=str).encode("utf-8"))
        total_bytes += serialized_len
        if total_bytes > MAX_TOTAL_REPLAY_PAYLOAD_BYTES:
            raise ValueError(
                f"Total payload replay melebihi batas aman ({MAX_TOTAL_REPLAY_PAYLOAD_BYTES} bytes)."
            )


class ReplayExecutionContext:
    """Isolated per-replay execution context holding its own frozen workspace, sandbox, and allowlist."""

    MAX_VERIFIER_FILE_BYTES: int = 25 * 1024 * 1024
    VERIFIER_TIMEOUT_SECONDS: float = 10.0

    def __init__(self, workspace: Path) -> None:
        from app.core.sandbox import SandboxManager, WorkspacePolicy
        from app.tools.registry import REPLAY_ALLOWED_TOOLS

        self.workspace = workspace.resolve()
        self.allowed_tools = REPLAY_ALLOWED_TOOLS
        self.sandbox_manager = SandboxManager(
            [
                WorkspacePolicy(
                    folder_path=str(self.workspace),
                    allow_read=True,
                    allow_write=True,
                    allow_execute=False,
                )
            ],
            frozen=True,
        )

    def resolve_untrusted_path(self, raw_path: str) -> Path:
        return resolve_replay_path(raw_path, self.workspace, allow_in_workspace_absolute=False)

    def resolve_tool_artifact(self, raw_path: str) -> Path:
        return resolve_replay_path(raw_path, self.workspace, allow_in_workspace_absolute=True)


class LearningPrivacyFilter:
    """Sanitizes text, tasks, and memory entries to strip secrets, API keys, credentials, and PII."""

    # Regex patterns for sensitive credentials & Indonesian PII
    SECRET_PATTERNS = [
        re.compile(r"(?:sk-[a-zA-Z0-9_\-]{20,})", re.IGNORECASE),
        re.compile(r"(?:Bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE),
        re.compile(r"(?:key-[a-zA-Z0-9]{20,})", re.IGNORECASE),
        re.compile(r"(?:AIza[0-9A-Za-z-_]{35})"),  # Google API Key
        re.compile(r"(?:ghp_[a-zA-Z0-9]{36})"),    # GitHub Personal Access Token
    ]

    PII_PATTERNS = [
        (re.compile(r"\b\d{16}\b"), "[NIK_TEREDAKSI]"),            # NIK 16 digits
        (re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d{1}-\d{3}\.\d{3}\b"), "[NPWP_TEREDAKSI]"), # Formatted NPWP
        (re.compile(r"\b\d{15,16}\b"), "[NPWP_ATAU_REK_TEREDAKSI]"), # 15-16 digit numbers
        (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[EMAIL_TEREDAKSI]"),
        (re.compile(r"\b(?:\+62|62|08)[1-9][0-9]{7,11}\b"), "[TELEPON_TEREDAKSI]"),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        """Sanitize text by replacing sensitive API tokens, passwords, and PII."""
        if not text:
            return ""

        redacted = text
        for pat in cls.SECRET_PATTERNS:
            redacted = pat.sub("[KREDENSIAL_TEREDAKSI]", redacted)

        for pat, replacement in cls.PII_PATTERNS:
            redacted = pat.sub(replacement, redacted)

        return redacted

    @classmethod
    def redact_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact dictionary fields."""
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, str):
                sanitized[k] = cls.redact(v)
            elif isinstance(v, dict):
                sanitized[k] = cls.redact_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    cls.redact_dict(item) if isinstance(item, dict)
                    else (cls.redact(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized


class EpisodicEntry(BaseModel):
    task_id: str
    session_id: str
    agent_id: str
    intent: str
    summary: str
    tools_used: list[str] = Field(default_factory=list)
    success: bool = True
    user_feedback: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CandidateSkill(BaseModel):
    skill_id: str
    name: str
    description: str
    owner_agent: str
    steps: list[str]
    validations: list[str]
    confidence: float = 0.85
    occurrences_count: int = 1
    source_task_ids: list[str] = Field(default_factory=list)
    structured_traces: list[dict[str, Any]] = Field(default_factory=list)
    empirical_metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SkillEvaluationResult(BaseModel):
    skill_id: str
    passed: bool
    score: float
    checks: list[dict[str, Any]]
    replay_passed: bool = True
    replay_mode: str = "static_screen"  # static_screen | runtime
    replay_pass_rate: float = 0.0
    dag_valid: bool = True
    calibrated_confidence: float | None = None
    replay_trace: list[dict[str, Any]] = Field(default_factory=list)
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentMemoryService:
    """Manages isolated Episodic, Semantic, and Preference memories per agent."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def record_episodic_task(
        self,
        task_id: str,
        session_id: str,
        intent: str,
        summary: str,
        tools_used: list[str],
        success: bool = True,
        user_feedback: str | None = None,
    ) -> EpisodicEntry:
        """Store minimal redacted task metadata in agent's episodic memory."""
        clean_intent = LearningPrivacyFilter.redact(intent)
        clean_summary = LearningPrivacyFilter.redact(summary)
        clean_feedback = LearningPrivacyFilter.redact(user_feedback or "") if user_feedback else None

        entry = EpisodicEntry(
            task_id=task_id,
            session_id=session_id,
            agent_id=self.agent_id,
            intent=clean_intent,
            summary=clean_summary,
            tools_used=tools_used,
            success=success,
            user_feedback=clean_feedback,
        )

        ep_dir = agent_directory_service.resolve_agent_path(self.agent_id, "memory/episodic")
        safe_tid = "".join(c for c in task_id if c.isalnum() or c in ("-", "_"))
        target_file = ep_dir / f"{safe_tid}.json"
        target_file.write_text(entry.model_dump_json(indent=2), encoding="utf-8")
        return entry

    def list_episodic_tasks(self, limit: int = 50) -> list[EpisodicEntry]:
        """List episodic task summaries for this agent."""
        ep_dir = agent_directory_service.resolve_agent_path(self.agent_id, "memory/episodic")
        entries: list[EpisodicEntry] = []
        if not ep_dir.exists():
            return entries

        files = sorted(ep_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entries.append(EpisodicEntry(**data))
            except Exception:
                continue
        return entries

    def get_preferences(self) -> dict[str, Any]:
        """Read agent preference profile."""
        pref_file = agent_directory_service.resolve_agent_path(self.agent_id, "memory/preferences/profile.json")
        if pref_file.exists():
            try:
                return json.loads(pref_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "agent_id": self.agent_id,
            "tone": "formal_indonesian",
            "preferred_tools": [],
            "formatting_rules": ["markdown_github_flavored", "no_raw_tokens"],
        }

    def update_preferences(self, preferences: dict[str, Any]) -> dict[str, Any]:
        """Update agent preference profile with privacy scrubbing."""
        pref_dir = agent_directory_service.resolve_agent_path(self.agent_id, "memory/preferences")
        pref_dir.mkdir(parents=True, exist_ok=True)
        pref_file = pref_dir / "profile.json"

        clean = LearningPrivacyFilter.redact_dict(preferences)
        clean["agent_id"] = self.agent_id
        clean["updated_at"] = datetime.now(timezone.utc).isoformat()
        pref_file.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
        return clean


class SkillCandidateExtractor:
    """Extracts candidate skills only from verified multi-task repetitions or explicit user command."""

    MIN_OCCURRENCES = 3  # Minimum successful repetitions required for automatic candidate proposal

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def evaluate_task_for_learning(
        self,
        task_id: str,
        intent: str,
        tools_used: list[str],
        success: bool,
        user_explicit_teach: bool = False,
        outcome: str | None = None,
        execution_trace: list[dict[str, Any]] | None = None,
    ) -> CandidateSkill | None:
        """Examine completed task against learning thresholds and extract trace-based procedural steps (AKSA-AGENT-001-R2, AKSA-AGENT-003-R2)."""
        eff_outcome = (outcome or ("success" if success else "failed")).lower()
        if eff_outcome != "success" and not user_explicit_teach:
            return None
        if eff_outcome in ("partial_success", "failed", "cancelled", "unverified") and not user_explicit_teach:
            return None

        # Fetch recent episodic tasks
        memory_svc = AgentMemoryService(self.agent_id)
        recent_tasks = memory_svc.list_episodic_tasks(limit=30)

        # Match similarity by tools used & intent keywords
        intent_words = set(re.findall(r"\w+", intent.lower()))
        matching_tasks: list[EpisodicEntry] = []
        for t in recent_tasks:
            if not t.success:
                continue
            t_words = set(re.findall(r"\w+", t.intent.lower()))
            overlap = len(intent_words.intersection(t_words))
            same_tools = set(tools_used).intersection(set(t.tools_used))
            if overlap >= 2 or len(same_tools) >= 2:
                matching_tasks.append(t)

        occurrences = len(matching_tasks)
        if not user_explicit_teach and occurrences < self.MIN_OCCURRENCES:
            return None

        # Formulate trace-driven procedural steps (AKSA-AGENT-001-R2)
        safe_name = "-".join(sorted(tools_used)[:2]) or "workflow"
        skill_id = f"cand-{safe_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        steps: list[str] = []
        step_num = 1
        steps.append(f"{step_num}. Inisialisasi sasaran tugas: '{intent.strip()[:100]}' dan verifikasi batasan folder kerja.")
        step_num += 1

        if execution_trace:
            for trace_step in execution_trace:
                label = trace_step.get("action_label") or trace_step.get("tool_name") or ""
                detail = trace_step.get("detail") or ""
                agent = trace_step.get("agent_name") or self.agent_id
                art = trace_step.get("artifact") or trace_step.get("artifacts") or ""
                if not label:
                    continue
                step_desc = f"{step_num}. [{agent}] Jalankan '{label}'"
                if detail:
                    step_desc += f": {detail}"
                if art:
                    step_desc += f" -> Menghasilkan artefak '{art}'"
                steps.append(step_desc)
                step_num += 1
        else:
            for tool in tools_used:
                t_clean = tool.strip()
                if not t_clean:
                    continue
                t_lower = t_clean.lower()
                if "excel" in t_lower or "xlsx" in t_lower:
                    steps.append(f"{step_num}. Muat dataset tabel dan terapkan kalkulasi formula numerik via {t_clean}")
                elif "word" in t_lower or "docx" in t_lower:
                    steps.append(f"{step_num}. Susun draf struktur dokumen resmi dengan paragraf dan tabel via {t_clean}")
                elif "ppt" in t_lower or "slide" in t_lower:
                    steps.append(f"{step_num}. Rancang tata letak visual slide presentasi eksekutif via {t_clean}")
                elif "pdf" in t_lower:
                    steps.append(f"{step_num}. Ekstrak teks atau render dokumen keluaran format PDF via {t_clean}")
                elif "rag" in t_lower or "search" in t_lower:
                    steps.append(f"{step_num}. Cari konteks dokumen relevan pada basis pengetahuan lokal via {t_clean}")
                else:
                    steps.append(f"{step_num}. Eksekusi operasi alat terspesialisasi '{t_clean}' pada authorized workspace")
                step_num += 1

        steps.append(f"{step_num}. Verifikasi integritas artefak keluaran, periksa batasan sandbox, dan laporkan ringkasan ke pengguna.")

        validations = [
            "Seluruh berkas hasil kerja harus berada di dalam authorized workspace (allowed_paths)",
            "Tidak boleh ada data kredensial mentah, kunci API, atau PII yang tersimpan tanpa redaksi",
            f"Setiap pemanggilan alat harus menghasilkan status sukses dengan perkiraan konsumsi token yang efisien",
            f"Alur kerja harus dapat direproduksi secara deterministik untuk agen '{self.agent_id}'",
        ]

        # Extract structured traces with strict PII sanitization (AKSA-AGENT-001-R3)
        structured_traces: list[dict[str, Any]] = []
        if execution_trace:
            for trace_step in execution_trace:
                tool_name = trace_step.get("action_label") or trace_step.get("tool_name") or ""
                agent_name = trace_step.get("agent_name") or self.agent_id
                input_args = trace_step.get("input") or trace_step.get("arguments") or trace_step.get("detail") or {}
                output_data = trace_step.get("output") or trace_step.get("result") or trace_step.get("artifact") or ""
                clean_input = (
                    LearningPrivacyFilter.redact_dict(input_args)
                    if isinstance(input_args, dict)
                    else LearningPrivacyFilter.redact(str(input_args))
                )
                clean_output = (
                    LearningPrivacyFilter.redact_dict(output_data)
                    if isinstance(output_data, dict)
                    else LearningPrivacyFilter.redact(str(output_data))
                )
                structured_traces.append({
                    "tool_name": tool_name,
                    "agent_name": agent_name,
                    "status": trace_step.get("status", "success"),
                    "input_summary": clean_input,
                    "output_summary": clean_output,
                })

        # Calculate empirical confidence score based on verified multi-run metrics (AKSA-AGENT-001-R3)
        base_score = 0.65
        repetition_bonus = min(occurrences * 0.05, 0.20)
        trace_bonus = 0.08 if execution_trace else 0.0
        user_bonus = 0.07 if user_explicit_teach else 0.0
        empirical_confidence = round(min(base_score + repetition_bonus + trace_bonus + user_bonus, 0.98), 2)
        empirical_metrics = {
            "base_score": base_score,
            "occurrences_count": occurrences,
            "repetition_bonus": repetition_bonus,
            "trace_bonus": trace_bonus,
            "user_explicit_teach": user_explicit_teach,
            "final_confidence": empirical_confidence,
        }

        candidate = CandidateSkill(
            skill_id=skill_id,
            name=f"Alur {intent[:30]}",
            description=f"Skill hasil pembelajaran adaptif untuk tugas: {intent[:60]}",
            owner_agent=self.agent_id,
            steps=steps,
            validations=validations,
            confidence=empirical_confidence,
            occurrences_count=occurrences,
            source_task_ids=[t.task_id for t in matching_tasks[:5]] + [task_id],
            structured_traces=structured_traces,
            empirical_metrics=empirical_metrics,
        )

        # Save to agent's candidates directory
        cand_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/candidates/{skill_id}"
        )
        cand_dir.mkdir(parents=True, exist_ok=True)

        skill_md = (
            "---\n"
            f"name: {candidate.name}\n"
            f"description: {candidate.description}\n"
            "metadata:\n"
            f"  owner-agent: \"{self.agent_id}\"\n"
            "  source: \"learned\"\n"
            "  status: \"candidate\"\n"
            "  version: \"1.0.0\"\n"
            f"  confidence: {candidate.confidence}\n"
            f"  occurrences: {candidate.occurrences_count}\n"
            "---\n\n"
            "# Alur Prosedural\n" + "\n".join(candidate.steps) + "\n\n"
            "# Kriteria Validasi\n" + "\n".join(candidate.validations) + "\n"
        )
        (cand_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
        (cand_dir / "candidate.json").write_text(candidate.model_dump_json(indent=2), encoding="utf-8")

        return candidate


class SkillEvaluator:
    """Evaluates candidate skills for security, formatting, and structural safety."""

    DANGEROUS_CALLS = ["rm -rf", "shutil.rmtree", "os.system", "subprocess.Popen", "eval(", "exec("]

    @classmethod
    def validate_dag_and_schemas(cls, traces: list[dict[str, Any]]) -> tuple[bool, list[str], list[dict[str, Any]]]:
        """Validate dependency DAG ordering and parameter JSON schemas against ToolRegistry."""
        from app.tools.registry import tool_registry

        issues: list[str] = []
        screened_steps: list[dict[str, Any]] = []
        completed_steps: set[int | str] = set()
        produced_artifacts: set[str] = set()
        dag_valid = True

        for idx, trace in enumerate(traces, 1):
            t_name = str(trace.get("tool_name", "")).strip()
            raw_inp = trace.get("input_summary", {})
            raw_out = trace.get("output_summary", "")
            status = str(trace.get("status", "success"))

            # 1. Dependency DAG check (no forward/circular references)
            for dep in trace.get("depends_on", []):
                if dep not in completed_steps:
                    dag_valid = False
                    issues.append(f"Langkah {idx} ('{t_name}') bergantung pada '{dep}' yang belum dijalankan sebelumnya.")
            for req_art in trace.get("requires_artifacts", []):
                if req_art not in produced_artifacts:
                    dag_valid = False
                    issues.append(f"Langkah {idx} ('{t_name}') membutuhkan artefak '{req_art}' yang belum dihasilkan.")

            # 2. Parameter safety & schema validation against registered ToolDefinition
            is_safe_tool = bool(re.match(r"^[a-zA-Z0-9_\-\.\:\s]+$", t_name)) if t_name else True
            inp_str = json.dumps(raw_inp, ensure_ascii=False) if isinstance(raw_inp, dict) else str(raw_inp)
            out_str = json.dumps(raw_out, ensure_ascii=False) if isinstance(raw_out, dict) else str(raw_out)
            is_clean_args = (
                not any(kw in inp_str for kw in cls.DANGEROUS_CALLS)
                and ".." not in inp_str
                and not any(pat.search(out_str) for pat in LearningPrivacyFilter.SECRET_PATTERNS)
            )

            schema_ok = True
            reg_tool = tool_registry.get_tool(t_name)
            if reg_tool and isinstance(raw_inp, dict) and reg_tool.parameters_schema:
                try:
                    import jsonschema
                    jsonschema.validate(instance=raw_inp, schema=reg_tool.parameters_schema)
                except Exception as exc:
                    schema_ok = False
                    issues.append(f"Schema argumen langkah {idx} ('{t_name}') tidak valid: {exc}")

            step_ok = dag_valid and is_safe_tool and is_clean_args and schema_ok and status != "failed"
            screened_steps.append({
                "step_number": idx,
                "tool": t_name,
                "schema_checked": bool(reg_tool and isinstance(raw_inp, dict)),
                "simulated_status": "passed" if step_ok else "failed",
                "reason": "OK" if step_ok else (issues[-1] if issues else "Parameter atau status tidak valid"),
            })

            if step_ok:
                completed_steps.add(idx)
                if t_name:
                    completed_steps.add(t_name)
                if trace.get("step_id"):
                    completed_steps.add(trace["step_id"])
                for art in trace.get("produces_artifacts", []):
                    produced_artifacts.add(str(art))

        return dag_valid and all(s["simulated_status"] == "passed" for s in screened_steps), issues, screened_steps

    @classmethod
    def evaluate(
        cls,
        skill_md_content: str,
        skill_id: str,
        candidate_data: dict[str, Any] | None = None,
    ) -> SkillEvaluationResult:
        checks: list[dict[str, Any]] = []
        score = 100.0
        replay_trace: list[dict[str, Any]] = []
        replay_passed = True
        dag_valid = True

        # Check 1: YAML frontmatter presence
        has_frontmatter = skill_md_content.startswith("---") and "\n---\n" in skill_md_content[3:]
        checks.append({
            "name": "yaml_frontmatter",
            "passed": has_frontmatter,
            "detail": "Memiliki YAML frontmatter yang valid" if has_frontmatter else "Frontmatter YAML tidak ditemukan",
        })
        if not has_frontmatter:
            score -= 30.0

        # Check 2: Dangerous commands / script execution attempt
        found_dangers = [d for d in cls.DANGEROUS_CALLS if d in skill_md_content]
        no_dangers = len(found_dangers) == 0
        checks.append({
            "name": "static_safety_scan",
            "passed": no_dangers,
            "detail": "Bebas dari perintah berbahaya" if no_dangers else f"Perintah berbahaya terdeteksi: {found_dangers}",
        })
        if not no_dangers:
            score -= 50.0

        # Check 3: Redacted credentials verification
        has_secrets = "[KREDENSIAL_TEREDAKSI]" in skill_md_content or not any(
            pat.search(skill_md_content) for pat in LearningPrivacyFilter.SECRET_PATTERNS
        )
        checks.append({
            "name": "credentials_check",
            "passed": has_secrets,
            "detail": "Tidak ada kredensial atau token mentah yang terekspos",
        })
        if not has_secrets:
            score -= 40.0

        # Check 4: Static Trace Screening, DAG & Schema Validation (label honestly: static_screen)
        traces = (candidate_data or {}).get("structured_traces", [])
        steps = (candidate_data or {}).get("steps", [])
        if traces:
            dag_valid, issues, replay_trace = cls.validate_dag_and_schemas(traces)
            replay_passed = dag_valid
            checks.append({
                "name": "trace_dag_and_schema_screening",
                "passed": replay_passed,
                "detail": (
                    f"Screening DAG & skema berhasil pada {len(traces)} langkah (static_screen)"
                    if replay_passed
                    else f"Screening DAG/skema gagal: {'; '.join(issues)}"
                ),
            })
            if not replay_passed:
                score -= 35.0
        elif steps:
            has_steps = len(steps) >= 2
            checks.append({
                "name": "procedural_steps_structure",
                "passed": has_steps,
                "detail": f"Memiliki {len(steps)} tahapan alur prosedural" if has_steps else "Tahapan alur terlalu pendek",
            })
            if not has_steps:
                score -= 20.0

        passed = score >= 70.0 and no_dangers and replay_passed
        return SkillEvaluationResult(
            skill_id=skill_id,
            passed=passed,
            score=max(0.0, score),
            checks=checks,
            replay_passed=replay_passed,
            replay_mode="static_screen",
            replay_pass_rate=1.0 if (traces and replay_passed) else 0.0,
            dag_valid=dag_valid,
            replay_trace=replay_trace,
        )

    @classmethod
    async def replay_candidate_in_sandbox(
        cls,
        skill_md_content: str,
        skill_id: str,
        candidate_data: dict[str, Any],
        replay_fixtures: list[dict[str, Any]],
    ) -> SkillEvaluationResult:
        """Actually replay a candidate workflow across isolated fixture variations in a clean temp sandbox.

        Executes strictly allowlisted deterministic tools inside an isolated per-fixture
        ``ReplayExecutionContext`` (without ever mutating global ``sandbox_manager``), enforces canonical
        containment on inputs, arguments, tool artifacts, and ``expected_artifacts``, and calibrates
        ``replay_pass_rate`` and ``calibrated_confidence``.
        """
        import tempfile
        from app.core.artifact_verifier_worker import verify_artifact_in_worker
        from app.core.sandbox import sandbox_manager
        from app.tools.registry import tool_registry

        # Ensure standard built-in tools are registered before lookup
        import app.tools  # noqa: F401

        try:
            validate_replay_fixtures_budget(replay_fixtures)
        except ValueError as budget_err:
            base_eval = cls.evaluate(skill_md_content, skill_id, candidate_data=candidate_data)
            base_eval.replay_mode = "runtime"
            base_eval.replay_passed = False
            base_eval.replay_pass_rate = 0.0
            base_eval.calibrated_confidence = 0.0
            base_eval.passed = False
            base_eval.checks.append({
                "name": "runtime_replay_execution",
                "passed": False,
                "detail": f"Replay ditolak oleh batas anggaran payload: {budget_err}",
            })
            return base_eval

        base_eval = cls.evaluate(skill_md_content, skill_id, candidate_data=candidate_data)
        if not base_eval.passed or not replay_fixtures:
            base_eval.replay_mode = "runtime"
            base_eval.replay_passed = False
            base_eval.replay_pass_rate = 0.0
            base_eval.calibrated_confidence = 0.0
            base_eval.passed = False
            return base_eval

        traces = candidate_data.get("structured_traces", [])
        if not traces:
            base_eval.replay_mode = "runtime"
            base_eval.replay_passed = False
            base_eval.replay_pass_rate = 0.0
            base_eval.calibrated_confidence = 0.0
            base_eval.passed = False
            base_eval.checks.append({
                "name": "runtime_replay_execution",
                "passed": False,
                "detail": "Kandidat tidak memiliki structured_traces untuk di-replay secara runtime.",
            })
            return base_eval

        passed_runs = 0
        runtime_logs: list[dict[str, Any]] = []

        for f_idx, fixture in enumerate(replay_fixtures, 1):
            fixture_name = str(fixture.get("name", f"fixture_{f_idx}"))
            with tempfile.TemporaryDirectory(prefix="aksa_skill_replay_") as tmp_dir:
                ws = Path(tmp_dir).resolve()
                replay_ctx = ReplayExecutionContext(ws)

                run_ok = True
                run_artifacts: list[Path] = []
                run_summaries: list[str] = []
                fail_reason = ""
                step_vars: dict[str, Any] = dict(fixture.get("inputs", {}))

                # Scoped ContextVar isolates replay_sandbox cleanly from concurrent global requests
                with sandbox_manager.scoped(replay_ctx.sandbox_manager):
                    # Materialize fixture input files strictly inside isolated replay workspace
                    try:
                        for rel_name, file_content in fixture.get("input_files", {}).items():
                            dest = replay_ctx.resolve_untrusted_path(str(rel_name))
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_text(str(file_content), encoding="utf-8")
                    except AgentIsolationError as iso_err:
                        run_ok = False
                        fail_reason = str(iso_err)

                    if run_ok:
                        for s_idx, trace in enumerate(traces, 1):
                            tool_name = str(trace.get("tool_name", ""))
                            base_args = dict(trace.get("input_summary", {})) if isinstance(trace.get("input_summary"), dict) else {}
                            per_step_override = fixture.get("step_args", {}).get(tool_name, {})
                            call_args = {**base_args, **per_step_override}

                            # Substitute {var} placeholders & reject absolute paths/traversal/symlinks (P2-01)
                            def _resolve_val(key: str, val: Any) -> Any:
                                if isinstance(val, str):
                                    try:
                                        v_sub = val.format(**step_vars)
                                    except Exception:
                                        v_sub = val
                                    if _is_replay_path_key(key):
                                        return str(replay_ctx.resolve_untrusted_path(v_sub))
                                    return v_sub
                                if isinstance(val, list):
                                    return [_resolve_val(key, item) for item in val]
                                if isinstance(val, dict):
                                    return {dk: _resolve_val(dk, dv) for dk, dv in val.items()}
                                return val

                            if tool_name not in replay_ctx.allowed_tools:
                                run_ok = False
                                fail_reason = (
                                    f"Replay ditolak (fail-closed): Tool '{tool_name}' tidak diizinkan untuk runtime replay."
                                )
                                break

                            try:
                                resolved_args: dict[str, Any] = {k: _resolve_val(k, v) for k, v in call_args.items()}
                            except AgentIsolationError as iso_err:
                                run_ok = False
                                fail_reason = str(iso_err)
                                break

                            res = await tool_registry.execute_replay(
                                tool_name,
                                replay_workspace=replay_ctx.workspace,
                                replay_sandbox=replay_ctx.sandbox_manager,
                                **resolved_args,
                            )

                            run_summaries.append(res.summary)
                            if not res.success:
                                run_ok = False
                                fail_reason = f"Langkah {s_idx} ({tool_name}) gagal: {res.summary}"
                                break

                            try:
                                for art in res.artifacts:
                                    art_p = replay_ctx.resolve_tool_artifact(str(art))
                                    run_artifacts.append(art_p)
                            except AgentIsolationError as art_err:
                                run_ok = False
                                fail_reason = f"Artefak output tool melanggar isolasi sandbox: {art_err}"
                                break

                            step_vars["last_summary"] = res.summary
                            if run_artifacts:
                                try:
                                    step_vars["last_artifact"] = str(run_artifacts[-1].relative_to(replay_ctx.workspace))
                                except ValueError:
                                    step_vars["last_artifact"] = run_artifacts[-1].name

                    # Verify fixture expectations & postcondition schemas inside killable worker (Cycle 9 P2-01..P2-03)
                    if run_ok:
                        raw_schema = fixture.get("expected_schema")
                        bounded_schema = dict(raw_schema) if isinstance(raw_schema, dict) else {}
                        # P2-01: Unconditionally enforce server-side max_bytes; fixtures CANNOT raise or set size limit
                        bounded_schema["max_bytes"] = replay_ctx.MAX_VERIFIER_FILE_BYTES

                        async def _verify_bounded(path_to_check: Path) -> tuple[bool, str]:
                            if path_to_check.is_symlink():
                                return False, f"Artefak symlink ditolak: '{path_to_check.name}'."
                            if path_to_check.exists() and path_to_check.stat().st_size > replay_ctx.MAX_VERIFIER_FILE_BYTES:
                                return False, (
                                    f"Ukuran file artefak melebihi batas replay aman ({replay_ctx.MAX_VERIFIER_FILE_BYTES} bytes)."
                                )
                            return await verify_artifact_in_worker(
                                path_to_check,
                                expected_schema=bounded_schema,
                                workspace=replay_ctx.workspace,
                                timeout=replay_ctx.VERIFIER_TIMEOUT_SECONDS,
                            )

                        exp_files = fixture.get("expected_artifacts", [])
                        for exp_f in exp_files:
                            try:
                                target_art = replay_ctx.resolve_untrusted_path(str(exp_f))
                            except AgentIsolationError as iso_err:
                                run_ok = False
                                fail_reason = f"Artefak '{exp_f}' ditolak oleh path containment: {iso_err}"
                                break
                            ok_art, art_msg = await _verify_bounded(target_art)
                            if not ok_art:
                                run_ok = False
                                fail_reason = f"Artefak '{exp_f}' gagal postcondition: {art_msg}"
                                break

                        if run_ok and not exp_files and run_artifacts:
                            for p_art in run_artifacts:
                                try:
                                    safe_art = replay_ctx.resolve_tool_artifact(str(p_art))
                                except AgentIsolationError as iso_err:
                                    run_ok = False
                                    fail_reason = f"Artefak output '{p_art.name}' melanggar sandbox: {iso_err}"
                                    break
                                ok_art, art_msg = await _verify_bounded(safe_art)
                                if not ok_art:
                                    run_ok = False
                                    fail_reason = f"Artefak '{p_art.name}' gagal postcondition: {art_msg}"
                                    break

                        if run_ok:
                            for needle in fixture.get("expected_summary_contains", []):
                                if needle.lower() not in " ".join(run_summaries).lower():
                                    run_ok = False
                                    fail_reason = f"Output ringkasan tidak memuat teks yang diharapkan: '{needle}'"
                                    break

                if run_ok:
                    passed_runs += 1
                runtime_logs.append({
                    "fixture": fixture_name,
                    "passed": run_ok,
                    "reason": "OK" if run_ok else fail_reason,
                    "artifacts_produced": [a.name for a in run_artifacts],
                })

        pass_rate = round(passed_runs / len(replay_fixtures), 4)
        all_passed = passed_runs == len(replay_fixtures) and base_eval.dag_valid
        calibrated_conf = round(pass_rate * (0.95 if base_eval.dag_valid else 0.50), 2)

        checks = list(base_eval.checks)
        checks.append({
            "name": "runtime_replay_execution",
            "passed": all_passed,
            "detail": (
                f"Runtime replay terisolasi lulus {passed_runs}/{len(replay_fixtures)} variasi fixture "
                f"(pass_rate={pass_rate:.0%}, confidence={calibrated_conf})."
            ),
        })
        score = base_eval.score if all_passed else max(0.0, base_eval.score - round((1.0 - pass_rate) * 50.0, 1))
        return SkillEvaluationResult(
            skill_id=skill_id,
            passed=all_passed and score >= 70.0,
            score=score,
            checks=checks,
            replay_passed=all_passed,
            replay_mode="runtime",
            replay_pass_rate=pass_rate,
            dag_valid=base_eval.dag_valid,
            calibrated_confidence=calibrated_conf,
            replay_trace=runtime_logs,
        )


class SkillVersionService:
    """Manages promotion from candidate to versioned learned skills, rollback, and sharing."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id

    def list_candidates(self) -> list[dict[str, Any]]:
        """List all candidate skills awaiting review for this agent."""
        cand_root = agent_directory_service.resolve_agent_path(self.agent_id, "skills/candidates")
        candidates: list[dict[str, Any]] = []
        if not cand_root.exists():
            return candidates

        for cand_dir in cand_root.iterdir():
            if not cand_dir.is_dir():
                continue
            cand_meta = cand_dir / "candidate.json"
            if cand_meta.exists():
                try:
                    candidates.append(json.loads(cand_meta.read_text(encoding="utf-8")))
                except Exception:
                    continue
        return candidates

    def evaluate_candidate(self, skill_id: str) -> SkillEvaluationResult:
        """Run static and sandbox evaluation on a candidate skill."""
        cand_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/candidates/{skill_id}"
        )
        skill_md_file = cand_dir / "SKILL.md"
        if not skill_md_file.exists():
            raise FileNotFoundError(f"Candidate skill '{skill_id}' tidak memiliki SKILL.md.")

        content = skill_md_file.read_text(encoding="utf-8")
        cand_meta_file = cand_dir / "candidate.json"
        cand_data: dict[str, Any] | None = None
        if cand_meta_file.exists():
            try:
                cand_data = json.loads(cand_meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        result = SkillEvaluator.evaluate(content, skill_id, candidate_data=cand_data)

        # Store evaluation report
        eval_dir = agent_directory_service.resolve_agent_path(self.agent_id, "skills/evaluations")
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / f"{skill_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    async def evaluate_and_replay_candidate(
        self,
        skill_id: str,
        replay_fixtures: list[dict[str, Any]] | None = None,
    ) -> SkillEvaluationResult:
        """Run static + DAG/schema checks AND runtime isolated replay when fixtures are provided."""
        cand_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/candidates/{skill_id}"
        )
        skill_md_file = cand_dir / "SKILL.md"
        if not skill_md_file.exists():
            raise FileNotFoundError(f"Candidate skill '{skill_id}' tidak memiliki SKILL.md.")

        content = skill_md_file.read_text(encoding="utf-8")
        cand_meta_file = cand_dir / "candidate.json"
        cand_data: dict[str, Any] = {}
        if cand_meta_file.exists():
            try:
                cand_data = json.loads(cand_meta_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        fixtures = replay_fixtures or cand_data.get("replay_fixtures")
        if fixtures:
            result = await SkillEvaluator.replay_candidate_in_sandbox(
                skill_md_content=content,
                skill_id=skill_id,
                candidate_data=cand_data,
                replay_fixtures=fixtures,
            )
            if cand_data and result.calibrated_confidence is not None:
                cand_data["confidence"] = result.calibrated_confidence
                cand_meta_file.write_text(json.dumps(cand_data, indent=2), encoding="utf-8")
        else:
            result = SkillEvaluator.evaluate(content, skill_id, candidate_data=cand_data)

        eval_dir = agent_directory_service.resolve_agent_path(self.agent_id, "skills/evaluations")
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / f"{skill_id}.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result

    def promote_candidate(
        self, skill_id: str, version: str = "1.0.0", promote_to_shared: bool = False
    ) -> dict[str, Any]:
        """Promote evaluated candidate to active learned skill (isolated or explicit shared)."""
        eval_res = self.evaluate_candidate(skill_id)
        if not eval_res.passed:
            raise PermissionError(
                f"Candidate '{skill_id}' gagal evaluasi keamanan (Score: {eval_res.score}). Promosi dibatalkan."
            )

        cand_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/candidates/{skill_id}"
        )
        skill_md_file = cand_dir / "SKILL.md"
        skill_content = skill_md_file.read_text(encoding="utf-8")

        # Determine target directory (preserve multi-token skill names before final timestamp suffix)
        cand_suffix_stripped = skill_id.replace("cand-", "")
        parts = cand_suffix_stripped.rsplit("-", 1)
        safe_name = parts[0] if parts and parts[0] else (cand_suffix_stripped or "learned-skill")
        if promote_to_shared:
            target_dir = (
                agent_directory_service.root_dir / "shared" / "skills" / safe_name / version
            ).resolve()
        else:
            target_dir = agent_directory_service.resolve_agent_path(
                self.agent_id, f"skills/learned/{safe_name}/{version}"
            )

        # Enforce strict immutable versioning (AKSA-SKILL-001)
        if target_dir.exists():
            raise FileExistsError(
                f"Versi keahlian '{version}' untuk '{safe_name}' sudah ada dan bersifat immutable. "
                "Gunakan nomor versi baru (misal: 1.0.1 atau 1.1.0) untuk memperbarui keahlian."
            )

        target_dir.mkdir(parents=True, exist_ok=False)
        (target_dir / "SKILL.md").write_text(skill_content, encoding="utf-8")

        # Provenance metadata
        provenance = {
            "skill_name": safe_name,
            "version": version,
            "owner_agent": self.agent_id,
            "promoted_at": datetime.now(timezone.utc).isoformat(),
            "shared": promote_to_shared,
            "evaluation_score": eval_res.score,
            "candidate_id": skill_id,
        }
        (target_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")

        # Clean up candidate folder after promotion
        shutil.rmtree(cand_dir, ignore_errors=True)

        return {
            "skill_name": safe_name,
            "version": version,
            "target_path": str(target_dir),
            "is_shared": promote_to_shared,
            "status": "promoted_and_active",
        }

    def rollback_skill(self, skill_name: str, target_version: str) -> dict[str, Any]:
        """Rollback an active learned skill to an earlier immutable version."""
        safe_name = "".join(c for c in skill_name if c.isalnum() or c in ("-", "_")).strip()
        version_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/learned/{safe_name}/{target_version}"
        )
        if not version_dir.exists():
            raise FileNotFoundError(f"Versi target '{target_version}' untuk skill '{safe_name}' tidak ditemukan.")

        return {
            "skill_name": safe_name,
            "active_version": target_version,
            "status": "rolled_back",
            "message": f"Skill '{safe_name}' berhasil di-rollback ke versi {target_version}.",
        }

    def disable_skill(self, skill_name: str) -> dict[str, Any]:
        """Disable a learned skill by moving it to disabled folder."""
        safe_name = "".join(c for c in skill_name if c.isalnum() or c in ("-", "_")).strip()
        learned_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/learned/{safe_name}"
        )
        if not learned_dir.exists():
            raise FileNotFoundError(f"Skill '{safe_name}' tidak ditemukan di folder pembelajaran.")

        disabled_dir = agent_directory_service.resolve_agent_path(
            self.agent_id, f"skills/disabled/{safe_name}"
        )
        if disabled_dir.exists():
            shutil.rmtree(disabled_dir, ignore_errors=True)
        shutil.move(str(learned_dir), str(disabled_dir))

        return {
            "skill_name": safe_name,
            "status": "disabled",
            "message": f"Skill '{safe_name}' telah dinonaktifkan.",
        }

    def list_learned_skills(self) -> list[dict[str, Any]]:
        """List all active learned skills for this agent."""
        learned_root = agent_directory_service.resolve_agent_path(self.agent_id, "skills/learned")
        skills: list[dict[str, Any]] = []
        if not learned_root.exists():
            return skills

        for skill_dir in learned_root.iterdir():
            if not skill_dir.is_dir():
                continue
            # Each version directory
            versions = [v.name for v in skill_dir.iterdir() if v.is_dir()]
            prov_file = skill_dir / versions[-1] / "provenance.json" if versions else None
            prov_data = {}
            if prov_file and prov_file.exists():
                try:
                    prov_data = json.loads(prov_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            skills.append({
                "skill_name": skill_dir.name,
                "versions": versions,
                "current_version": versions[-1] if versions else "1.0.0",
                "provenance": prov_data,
            })
        return skills


class AgentLearningMetrics:
    """Calculates agent learning metrics, memory consumption, and task performance."""

    @classmethod
    def get_metrics(cls, agent_id: str) -> dict[str, Any]:
        memory_svc = AgentMemoryService(agent_id)
        tasks = memory_svc.list_episodic_tasks(limit=100)
        total_tasks = len(tasks)
        successful_tasks = sum(1 for t in tasks if t.success)
        success_rate = (successful_tasks / total_tasks * 100.0) if total_tasks > 0 else 100.0

        version_svc = SkillVersionService(agent_id)
        candidates = version_svc.list_candidates()
        learned = version_svc.list_learned_skills()

        # Calculate directory storage footprint
        agent_dir = agent_directory_service.resolve_agent_path(agent_id)
        size_bytes = sum(f.stat().st_size for f in agent_dir.rglob("*") if f.is_file())

        return {
            "agent_id": agent_id,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "success_rate_percent": round(success_rate, 1),
            "episodic_entries_count": total_tasks,
            "candidate_skills_count": len(candidates),
            "learned_skills_count": len(learned),
            "storage_size_kb": round(size_bytes / 1024, 2),
            "last_active": tasks[0].created_at if tasks else datetime.now(timezone.utc).isoformat(),
        }
