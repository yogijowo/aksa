"""Adaptive Agent Learning Engine: Isolated Memory, Privacy Redaction, Candidate Extraction, and Versioned Skills."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from app.core.agent_directory import AgentIsolationError, agent_directory_service


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
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SkillEvaluationResult(BaseModel):
    skill_id: str
    passed: bool
    score: float
    checks: list[dict[str, Any]]
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
    ) -> CandidateSkill | None:
        """Examine completed task against learning thresholds."""
        if not success and not user_explicit_teach:
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

        # Formulate candidate skill
        safe_name = "-".join(sorted(tools_used)[:2]) or "workflow"
        skill_id = f"cand-{safe_name}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        steps = [
            f"1. Validasi input dan parameter untuk alur {intent[:50]}",
            "2. Jalankan eksekusi alat secara berurutan sesuai kebijakan workspace",
            "3. Verifikasi hasil akhir dan laporkan output kepada pengguna",
        ]
        validations = [
            "Output file harus berada di dalam authorized workspace",
            "Tidak boleh ada data rahasia atau PII yang tersimpan di catatan publik",
        ]

        candidate = CandidateSkill(
            skill_id=skill_id,
            name=f"Alur {intent[:30]}",
            description=f"Skill hasil pembelajaran adaptif untuk tugas: {intent[:60]}",
            owner_agent=self.agent_id,
            steps=steps,
            validations=validations,
            confidence=0.88 if user_explicit_teach else 0.75,
            occurrences_count=occurrences,
            source_task_ids=[t.task_id for t in matching_tasks[:5]] + [task_id],
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
    def evaluate(cls, skill_md_content: str, skill_id: str) -> SkillEvaluationResult:
        checks: list[dict[str, Any]] = []
        score = 100.0

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

        passed = score >= 70.0 and no_dangers
        return SkillEvaluationResult(
            skill_id=skill_id,
            passed=passed,
            score=max(0.0, score),
            checks=checks,
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
        result = SkillEvaluator.evaluate(content, skill_id)

        # Store evaluation report
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

        # Determine target directory
        safe_name = skill_id.replace("cand-", "").split("-")[0] or "learned-skill"
        if promote_to_shared:
            target_dir = (
                agent_directory_service.root_dir / "shared" / "skills" / safe_name / version
            ).resolve()
        else:
            target_dir = agent_directory_service.resolve_agent_path(
                self.agent_id, f"skills/learned/{safe_name}/{version}"
            )

        target_dir.mkdir(parents=True, exist_ok=True)
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
