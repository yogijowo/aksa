"""SQLite schema initialization and async CRUD operations for AKSA."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agent_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    is_default INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES agent_teams(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    description TEXT NOT NULL,
    avatar_icon TEXT DEFAULT 'bot',
    tier_level INTEGER DEFAULT 0,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    temperature REAL DEFAULT 0.2,
    max_tokens INTEGER DEFAULT 4096,
    system_prompt TEXT NOT NULL,
    tool_categories_json TEXT NOT NULL,
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    folder_path TEXT NOT NULL UNIQUE,
    allow_read INTEGER DEFAULT 1,
    allow_write INTEGER DEFAULT 1,
    allow_execute INTEGER DEFAULT 0,
    auto_rag_sync INTEGER DEFAULT 1,
    last_indexed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    team_id TEXT REFERENCES agent_teams(id) ON DELETE SET NULL,
    source TEXT DEFAULT 'desktop',
    telegram_chat_id INTEGER,
    compacted_summary TEXT,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    estimated_tokens_saved INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sender_role TEXT NOT NULL,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    execution_steps_json TEXT,
    artifacts_json TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_documents (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'indexed',
    error_message TEXT,
    indexed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    workspace_id UNINDEXED,
    file_name,
    section_title,
    content,
    tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS token_usage_logs (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_tokens INTEGER DEFAULT 0,
    tokens_saved_by_isolation INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_memories (
    id TEXT PRIMARY KEY,
    category TEXT DEFAULT 'general',
    fact TEXT NOT NULL,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    return dict(row)


class DatabaseManager:
    """Async SQLite manager for AKSA state persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.sqlite_path

    async def initialize(self) -> None:
        """Create database tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

    async def list_teams_with_agents(self) -> list[dict[str, Any]]:
        """Return all agent teams along with their nested hierarchical agents."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM agent_teams ORDER BY is_default DESC, created_at ASC")
            teams = [_row_to_dict(r) for r in await cursor.fetchall()]

            for team in teams:
                agent_cursor = await db.execute(
                    "SELECT * FROM agents WHERE team_id = ? ORDER BY tier_level ASC, created_at ASC",
                    (team["id"],),
                )
                agents_raw = [_row_to_dict(a) for a in await agent_cursor.fetchall()]
                for agent in agents_raw:
                    agent["tool_categories"] = json.loads(agent.pop("tool_categories_json", "[]"))
                team["agents"] = agents_raw
                team["is_default"] = bool(team["is_default"])
            return teams

    async def create_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert a new agent node into a team hierarchy."""
        agent_id = payload.get("id") or f"agt_{uuid.uuid4().hex[:10]}"
        tool_categories_json = json.dumps(payload.get("tool_categories", []))
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO agents (
                    id, team_id, parent_id, name, role_title, description,
                    avatar_icon, tier_level, provider, model_id, temperature,
                    max_tokens, system_prompt, tool_categories_json, position_x, position_y, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id,
                    payload["team_id"],
                    payload.get("parent_id"),
                    payload["name"],
                    payload["role_title"],
                    payload["description"],
                    payload.get("avatar_icon", "bot"),
                    payload.get("tier_level", 1),
                    payload["provider"],
                    payload["model_id"],
                    payload.get("temperature", 0.2),
                    payload.get("max_tokens", 4096),
                    payload["system_prompt"],
                    tool_categories_json,
                    payload.get("position_x", 0.0),
                    payload.get("position_y", 0.0),
                    _now_iso(),
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = await cursor.fetchone()
            result = _row_to_dict(row)
            result["tool_categories"] = json.loads(result.pop("tool_categories_json", "[]"))
            return result

    async def update_agent(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update an existing agent's model, prompt, position, or tools."""
        allowed_fields = {
            "parent_id", "name", "role_title", "description", "avatar_icon",
            "tier_level", "provider", "model_id", "temperature", "max_tokens",
            "system_prompt", "position_x", "position_y"
        }
        set_clauses: list[str] = []
        values: list[Any] = []

        for key, value in updates.items():
            if key == "tool_categories":
                set_clauses.append("tool_categories_json = ?")
                values.append(json.dumps(value))
            elif key in allowed_fields:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if not set_clauses:
            return None

        values.append(agent_id)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                f"UPDATE agents SET {', '.join(set_clauses)} WHERE id = ?",
                tuple(values),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            result = _row_to_dict(row)
            result["tool_categories"] = json.loads(result.pop("tool_categories_json", "[]"))
            return result

    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent node by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_workspaces(self) -> list[dict[str, Any]]:
        """List all authorized PC workspace folders."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                item = _row_to_dict(row)
                item["allow_read"] = bool(item["allow_read"])
                item["allow_write"] = bool(item["allow_write"])
                item["allow_execute"] = bool(item["allow_execute"])
                item["auto_rag_sync"] = bool(item["auto_rag_sync"])
                results.append(item)
            return results

    async def upsert_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Register or update an authorized PC workspace folder."""
        ws_id = payload.get("id") or f"ws_{uuid.uuid4().hex[:10]}"
        resolved_path = str(Path(payload["folder_path"]).expanduser().resolve())
        name = payload.get("name") or Path(resolved_path).name or resolved_path

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO workspaces (
                    id, name, folder_path, allow_read, allow_write, allow_execute, auto_rag_sync, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    name = excluded.name,
                    allow_read = excluded.allow_read,
                    allow_write = excluded.allow_write,
                    allow_execute = excluded.allow_execute,
                    auto_rag_sync = excluded.auto_rag_sync
                """,
                (
                    ws_id,
                    name,
                    resolved_path,
                    int(payload.get("allow_read", True)),
                    int(payload.get("allow_write", True)),
                    int(payload.get("allow_execute", False)),
                    int(payload.get("auto_rag_sync", True)),
                    _now_iso(),
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM workspaces WHERE folder_path = ?", (resolved_path,))
            row = await cursor.fetchone()
            item = _row_to_dict(row)
            item["allow_read"] = bool(item["allow_read"])
            item["allow_write"] = bool(item["allow_write"])
            item["allow_execute"] = bool(item["allow_execute"])
            item["auto_rag_sync"] = bool(item["auto_rag_sync"])
            return item

    async def delete_workspace(self, workspace_id: str) -> bool:
        """Remove an authorized PC workspace folder from the database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List chat sessions ordered by most recently updated."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    async def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new chat session."""
        session_id = payload.get("id") or f"sess_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO sessions (id, title, workspace_id, team_id, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    payload.get("title", "Sesi Kerja Baru"),
                    payload.get("workspace_id"),
                    payload.get("team_id"),
                    payload.get("source", "desktop"),
                    now,
                    now,
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            return _row_to_dict(await cursor.fetchone())


db_manager = DatabaseManager()

