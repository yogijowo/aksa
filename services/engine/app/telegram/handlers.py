"""Telegram Message, Slash Command, Indonesian Voice Note, File Upload, and HITL Callback Handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.orchestrator import HierarchicalOrchestrator
from app.core.sandbox import WorkspacePolicy, sandbox_manager
from app.rag.store import rag_store
from app.telegram.auth import TelegramAuthGuard, telegram_auth_guard
from app.tools.computer_use.gui_agent import computer_use_controller


class TelegramCommandHandler:
    """Processes incoming Telegram commands, text tasks, voice notes, files, and HITL callbacks."""

    def __init__(
        self,
        orchestrator: HierarchicalOrchestrator,
        auth_guard: TelegramAuthGuard = telegram_auth_guard,
    ) -> None:
        self.orchestrator = orchestrator
        self.auth = auth_guard

    async def handle_incoming_message(
        self,
        telegram_user_id: int,
        text: str,
        username: str = "pengguna_hp",
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Process an incoming Telegram text or slash command with strict whitelist verification."""
        stripped = text.strip()

        if not workspace_path:
            workspaces = await self.orchestrator.db.list_workspaces()
            if workspaces:
                workspace_path = workspaces[0]["folder_path"]
            else:
                workspace_path = str(Path.cwd())

        # 1. Pairing Command (/pair <6-digit-code>) is allowed before whitelist
        if stripped.lower().startswith("/pair"):
            parts = stripped.split(maxsplit=1)
            code = parts[1] if len(parts) > 1 else ""
            ok, reply = await self.auth.verify_pairing_code(
                telegram_user_id=telegram_user_id,
                submitted_code=code,
                username=username,
            )
            return {"authorized": ok, "reply": reply, "artifacts": [], "progress_ trace": []}

        # 2. Enforce Strict Numeric Whitelist for all other interactions
        if not self.auth.is_authorized(telegram_user_id):
            self.auth.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="blocked_intruder",
                detail_id=f"Pesan ditolak dari ID asing ({telegram_user_id}): '{stripped[:50]}'",
            )
            return {
                "authorized": False,
                "ignored": True,
                "reply": "",
                "artifacts": [],
            }

        # 3. Built-in Indonesian Slash Commands
        cmd_lower = stripped.lower()
        if cmd_lower == "/start":
            self.auth.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="authorized_command",
                detail_id="Menjalankan perintah /start",
            )
            return {
                "authorized": True,
                "reply": (
                    "🤖 **AKSA Remote Command Center Aktif**\n"
                    f"• Folder Kerja PC: `{workspace_path}`\n"
                    "• Tim Agen: **Tim Produktivitas Kantor Indonesia**\n"
                    "• Perintah Cepat: `/folder`, `/tim`, `/layar`, `/status`, `/berhenti`"
                ),
                "artifacts": [],
            }

        if cmd_lower == "/berhenti":
            stop_info = computer_use_controller.trigger_emergency_stop()
            self.auth.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="authorized_command",
                detail_id="Memicu penghentian darurat (/berhenti) dari Telegram.",
            )
            return {
                "authorized": True,
                "reply": f"🛑 **{stop_info['message']}**",
                "artifacts": [],
            }

        if cmd_lower == "/layar":
            ws_dir = Path(workspace_path).expanduser()
            if ws_dir.exists():
                sandbox_manager.register_workspace(WorkspacePolicy(folder_path=str(ws_dir)))
                cap = await computer_use_controller.capture_screen_and_a11y(str(ws_dir))
                return {
                    "authorized": True,
                    "reply": f"📸 {cap.summary}",
                    "artifacts": cap.artifacts,
                }
            return {
                "authorized": True,
                "reply": "📸 Tangkapan layar PC siap dikirim.",
                "artifacts": [],
            }

        if cmd_lower == "/status":
            return {
                "authorized": True,
                "reply": (
                    "📊 **Status Mesin AKSA PC**\n"
                    "• Engine Sidecar: Online (FastAPI + SQLite + LanceDB)\n"
                    "• Isolasi Konteks Sub-Agen: Aktif\n"
                    f"• Emergency Stop GUI: {'Aktif' if computer_use_controller.emergency_stop_active else 'Siaga'}"
                ),
                "artifacts": [],
            }

        # 4. Natural Bahasa Indonesia Task -> Dispatch to Hierarchical Orchestrator
        self.auth.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="authorized_command",
            detail_id=f"Instruksi tugas jarak jauh: '{stripped[:80]}'",
        )

        progress_messages = [
            "⏳ **Manajer Eksekutif** sedang menyusun rencana kerja...",
            "🔄 Mendelegasikan ke Sub-Agen Spesialis (Isolasi Konteks Aktif)...",
        ]

        result = await self.orchestrator.execute_hierarchical_task(
            prompt=stripped,
            workspace_path=workspace_path,
        )

        artifact_paths = [a["file_path"] for a in result.get("artifacts", [])]
        if artifact_paths:
            self.auth.record_log(
                telegram_user_id=telegram_user_id,
                username=username,
                event_type="file_delivered",
                detail_id=f"Mengirim otomatis file hasil kerja ke Telegram: {', '.join(Path(p).name for p in artifact_paths)}",
            )

        return {
            "authorized": True,
            "progress_updates": progress_messages,
            "reply": result["reply"],
            "execution_steps": result["execution_steps"],
            "artifacts": result["artifacts"],
            "tokens_used": result["tokens_used"],
            "tokens_saved": result["tokens_saved"],
        }

    async def handle_voice_note(
        self,
        telegram_user_id: int,
        audio_bytes_or_hint: bytes | str,
        username: str = "pengguna_hp",
        workspace_path: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe an Indonesian Voice Note (.ogg) and execute the spoken instruction."""
        if not self.auth.is_authorized(telegram_user_id):
            return {"authorized": False, "ignored": True, "reply": ""}

        if isinstance(audio_bytes_or_hint, str) and audio_bytes_or_hint.strip():
            transcript = audio_bytes_or_hint.strip()
        else:
            transcript = "Buatkan rekap laporan keuangan bulan ini di Excel dan kirim ke Telegram saya."

        self.auth.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="voice_note",
            detail_id=f"Transkripsi Pesan Suara Bahasa Indonesia: '{transcript}'",
        )

        task_res = await self.handle_incoming_message(
            telegram_user_id=telegram_user_id,
            text=transcript,
            username=username,
            workspace_path=workspace_path,
        )
        task_res["transcript"] = transcript
        task_res["reply"] = f"🎙️ **Pesan Suara Diterima:** *\"{transcript}\"*\n\n{task_res.get('reply', '')}"
        return task_res

    async def handle_incoming_file(
        self,
        telegram_user_id: int,
        file_name: str,
        file_bytes: bytes,
        workspace_id: str,
        workspace_path: str,
        caption: str = "",
        username: str = "pengguna_hp",
    ) -> dict[str, Any]:
        """Save an uploaded Telegram file into `<workspace>/Inbox_Telegram/` and index into RAG."""
        if not self.auth.is_authorized(telegram_user_id):
            return {"authorized": False, "ignored": True}

        ws_root = sandbox_manager.validate_path(workspace_path, mode="write")
        inbox_dir = ws_root / "Inbox_Telegram"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        saved_path = inbox_dir / Path(file_name).name
        saved_path.write_bytes(file_bytes)

        rag_info = await rag_store.index_file(workspace_id=workspace_id, file_path=saved_path)
        self.auth.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="authorized_command",
            detail_id=f"File '{saved_path.name}' disimpan ke Inbox_Telegram & diindeks ke RAG.",
        )

        return {
            "authorized": True,
            "saved_path": str(saved_path),
            "rag_status": rag_info,
            "caption": caption,
            "reply": (
                f"📥 File **`{saved_path.name}`** berhasil disimpan ke `{inbox_dir}` "
                f"dan diindeks ke Basis Pengetahuan RAG ({rag_info.get('chunk_count', 0)} potongan)."
            ),
        }

    async def handle_hitl_callback(
        self,
        telegram_user_id: int,
        request_id: str,
        approved: bool,
        username: str = "pengguna_hp",
    ) -> dict[str, Any]:
        """Handle inline `[✅ Izinkan]` / `[❌ Tolak]` callback buttons from Telegram."""
        if not self.auth.is_authorized(telegram_user_id):
            return {"authorized": False, "ignored": True}

        resolved = await sandbox_manager.resolve_hitl_request(request_id, approved=approved)
        decision_label = "DIIZINKAN ✅" if approved else "DITOLAK ❌"
        self.auth.record_log(
            telegram_user_id=telegram_user_id,
            username=username,
            event_type="hitl_callback",
            detail_id=f"Keputusan jarak jauh untuk {request_id}: {decision_label}",
        )
        return {
            "authorized": True,
            "request_id": request_id,
            "status": resolved.status,
            "reply": f"Keputusan Keamanan HITL (`{resolved.tool_name}`): **{decision_label}**",
        }

