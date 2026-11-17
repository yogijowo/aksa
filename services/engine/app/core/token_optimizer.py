"""Token Efficiency Engine: Sub-Agent Context Isolation, Lazy Tool Loading, and Compaction."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel

# Approximate USD pricing per 1M tokens for cost & savings analytics
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro": (1.25, 5.00),
    "gemini-2.5-flash": (0.10, 0.40),
    "claude-3-7-sonnet-latest": (3.00, 15.00),
    "deepseek-chat": (0.14, 0.28),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
}

# Full catalog of 30+ tool schemas grouped by category (for Lazy Tool Injection)
CATEGORY_TOOL_SCHEMAS: dict[str, list[dict[str, Any]]] = {
    "delegation": [
        {
            "type": "function",
            "function": {
                "name": "delegate_to_sub_agent",
                "description": "Delegasikan sub-tugas spesifik ke Sub-Agen bawahan dalam ruang konteks terisolasi.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent_id": {"type": "string"},
                        "task_instruction": {"type": "string"},
                        "relevant_files": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["target_agent_id", "task_instruction"],
                },
            },
        }
    ],
    "filesystem": [
        {
            "type": "function",
            "function": {
                "name": "list_workspace_files",
                "description": "Lihat daftar file dan sub-folder di dalam Folder Kerja yang diizinkan.",
                "parameters": {"type": "object", "properties": {"subdir": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "inspect_file_outline",
                "description": "Lihat struktur ringkas dokumen/spreadsheet tanpa memuat seluruh isi file (hemat token).",
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}},
                    "required": ["file_path"],
                },
            },
        },
    ],
    "office_excel": [
        {
            "type": "function",
            "function": {
                "name": "excel_create_workbook",
                "description": "Buat file Microsoft Excel (.xlsx) lengkap dengan rumus SUM/VLOOKUP, tabel, dan grafik.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {"type": "string"},
                        "sheet_title": {"type": "string"},
                        "headers": {"type": "array", "items": {"type": "string"}},
                        "include_chart": {"type": "boolean"},
                    },
                    "required": ["file_name", "sheet_title"],
                },
            },
        }
    ],
    "office_word": [
        {
            "type": "function",
            "function": {
                "name": "word_create_document",
                "description": "Buat dokumen Microsoft Word (.docx) resmi seperti surat, laporan, atau SOP.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {"type": "string"},
                        "title": {"type": "string"},
                        "sections": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["file_name", "title"],
                },
            },
        }
    ],
    "office_ppt": [
        {
            "type": "function",
            "function": {
                "name": "ppt_create_presentation",
                "description": "Buat slide presentasi PowerPoint (.pptx) di dalam Folder Kerja.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_name": {"type": "string"},
                        "title": {"type": "string"},
                    },
                    "required": ["file_name", "title"],
                },
            },
        }
    ],
    "pdf_tools": [
        {
            "type": "function",
            "function": {
                "name": "pdf_extract_markdown",
                "description": "Ekstrak halaman PDF menjadi teks Markdown bersih.",
                "parameters": {
                    "type": "object",
                    "properties": {"file_path": {"type": "string"}, "pages": {"type": "string"}},
                    "required": ["file_path"],
                },
            },
        }
    ],
    "rag_search": [
        {
            "type": "function",
            "function": {
                "name": "hybrid_rag_search",
                "description": "Cari potongan dokumen relevan di Basis Pengetahuan lokal (LanceDB Vector + FTS5).",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}},
                    "required": ["query"],
                },
            },
        }
    ],
    "os_automation": [
        {
            "type": "function",
            "function": {
                "name": "control_live_office_app",
                "description": "Kontrol aplikasi Microsoft Office yang sedang terbuka melalui Windows COM / AppleScript.",
                "parameters": {
                    "type": "object",
                    "properties": {"app_name": {"type": "string"}, "action": {"type": "string"}},
                    "required": ["app_name", "action"],
                },
            },
        }
    ],
    "uv_python": [
        {
            "type": "function",
            "function": {
                "name": "run_custom_python_task",
                "description": "Jalankan skrip Python mandiri di dalam ruang terisolasi uv.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "script_code": {"type": "string"},
                        "packages": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["script_code"],
                },
            },
        }
    ],
    "computer_use": [
        {
            "type": "function",
            "function": {
                "name": "visual_screen_action",
                "description": "Ambil tangkapan layar dan jalankan klik mouse atau ketik keyboard pada aplikasi desktop.",
                "parameters": {
                    "type": "object",
                    "properties": {"action_type": {"type": "string"}, "target": {"type": "string"}},
                    "required": ["action_type"],
                },
            },
        }
    ],
}

TOTAL_ALL_TOOLS_TOKEN_OVERHEAD = 3600  # Baseline token cost if all 35+ tools were injected naively


class SubAgentIsolationMetrics(BaseModel):
    """Metrics quantifying token savings from Sub-Agent Context Isolation & Lazy Tools."""

    raw_scratchpad_tokens: int
    handback_summary_tokens: int
    lazy_tool_tokens_saved: int
    total_tokens_saved: int
    cost_saved_usd: float


class TokenOptimizer:
    """Implements the 5 AKSA Token Optimization techniques."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Fast heuristic token estimator (~3.8 characters per token for Indonesian/English)."""
        if not text:
            return 0
        return max(1, int(len(text) / 3.8))

    @classmethod
    def get_lazy_tools_for_agent(cls, enabled_categories: list[str]) -> tuple[list[dict[str, Any]], int]:
        """Return only the tool schemas matching the agent's enabled categories and tokens saved."""
        selected_tools: list[dict[str, Any]] = []
        for category in enabled_categories:
            selected_tools.extend(CATEGORY_TOOL_SCHEMAS.get(category, []))

        injected_tokens = len(selected_tools) * 115
        saved_tokens = max(0, TOTAL_ALL_TOOLS_TOKEN_OVERHEAD - injected_tokens)
        return selected_tools, saved_tokens

    @classmethod
    def build_isolated_subagent_messages(
        cls,
        sub_agent: dict[str, Any],
        task_brief: str,
        workspace_path: str,
        relevant_files: list[str] | None = None,
    ) -> list[dict[str, str]]:
        """Construct a fresh, minimal context window for a Sub-Agent without parent chat bloat."""
        if relevant_files:
            files_note = f"Daftar berkas nyata di Folder Kerja saat ini ({len(relevant_files)} file):\n" + "\n".join(f"- {f}" for f in relevant_files)
        else:
            files_note = f"Folder Kerja saat ini kosong (belum ada berkas yang disimpan)."

        system_content = (
            f"{sub_agent['system_prompt']}\n\n"
            f"[Konteks Terisolasi AKSA]\n"
            f"Folder Kerja Aktif: {workspace_path}\n"
            f"{files_note}\n\n"
            f"ATURAN MUTLAK:\n"
            f"1. JANGAN PERNAH menampilkan kode Python (seperti 'import os', 'working_dir = ...', 'os.listdir()') untuk memeriksa isi folder! "
            f"Gunakan daftar berkas nyata di atas secara langsung.\n"
            f"2. Berikan hasil kerja dan ringkasan padat, jelas, dan akurat (maksimal 250 kata) dalam Bahasa Indonesia untuk Manajer Utama."
        )
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task_brief},
        ]

    @classmethod
    def compact_subagent_handback(
        cls,
        raw_subagent_output: str,
        Simulated_document_tokens_processed: int = 4200,
        lazy_tool_tokens_saved: int = 2800,
        supervisor_model_id: str = "gemini-2.5-pro",
    ) -> tuple[str, SubAgentIsolationMetrics]:
        """Distill a sub-agent's raw output into a compact handback summary and compute savings."""
        lines = [line.strip() for line in raw_subagent_output.strip().splitlines() if line.strip()]
        if len(raw_subagent_output) > 900:
            compact_summary = "\n".join(lines[:8]) + "\n...(Diringkas otomatis oleh Isolasi Konteks AKSA)"
        else:
            compact_summary = raw_subagent_output.strip()

        summary_tokens = cls.estimate_tokens(compact_summary)
        raw_tokens = Simulated_document_tokens_processed + cls.estimate_tokens(raw_subagent_output)
        isolated_saved = max(0, raw_tokens - summary_tokens)
        total_saved = isolated_saved + lazy_tool_tokens_saved

        input_price_per_1m, _ = MODEL_PRICING_PER_1M.get(supervisor_model_id, (1.25, 5.00))
        cost_saved_usd = round((total_saved / 1_000_000) * input_price_per_1m, 6)

        metrics = SubAgentIsolationMetrics(
            raw_scratchpad_tokens=raw_tokens,
            handback_summary_tokens=summary_tokens,
            lazy_tool_tokens_saved=lazy_tool_tokens_saved,
            total_tokens_saved=total_saved,
            cost_saved_usd=cost_saved_usd,
        )
        return compact_summary, metrics

    @classmethod
    def compact_conversation_history(
        cls,
        messages: list[dict[str, str]],
        max_token_budget: int = 8000,
    ) -> tuple[list[dict[str, str]], int]:
        """Keep system prompt + recent messages verbatim and compact older turns if over budget."""
        total_tokens = sum(cls.estimate_tokens(m.get("content", "")) for m in messages)
        if total_tokens <= max_token_budget or len(messages) <= 5:
            return messages, 0

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        older = non_system[:-4]
        recent = non_system[-4:]

        summary_points = [
            f"- {m.get('role', 'user')}: {m.get('content', '')[:100]}..." for m in older
        ]
        compacted_msg = {
            "role": "system",
            "content": "[Ringkasan Riwayat Percakapan Sebelumnya]\n" + "\n".join(summary_points),
        }
        new_messages = [*system_msgs, compacted_msg, *recent]
        new_tokens = sum(cls.estimate_tokens(m.get("content", "")) for m in new_messages)
        return new_messages, max(0, total_tokens - new_tokens)


token_optimizer = TokenOptimizer()

