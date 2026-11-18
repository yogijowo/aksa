"""SQLite schema initialization and async CRUD operations for AKSA."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings
from app.core.auth_context import get_default_host_principal

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
    owner_id TEXT DEFAULT 'default_user',
    last_indexed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    team_id TEXT REFERENCES agent_teams(id) ON DELETE SET NULL,
    source TEXT DEFAULT 'desktop',
    principal_id TEXT DEFAULT 'default_user',
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

CREATE TABLE IF NOT EXISTS installed_applications (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    platform_app_id TEXT NOT NULL,
    bundle_id TEXT,
    aumid TEXT,
    display_name TEXT NOT NULL,
    publisher TEXT,
    version TEXT,
    install_location TEXT,
    install_scope TEXT DEFAULT 'machine',
    signature_status TEXT DEFAULT 'unknown',
    detection_sources_json TEXT DEFAULT '[]',
    is_installed INTEGER DEFAULT 1,
    is_running INTEGER DEFAULT 0,
    is_connected INTEGER DEFAULT 0,
    category_label TEXT DEFAULT 'Aplikasi Komputer Umum',
    available_adapters_json TEXT DEFAULT '[]',
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS application_adapters (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES installed_applications(id) ON DELETE CASCADE,
    adapter_type TEXT NOT NULL,
    adapter_version TEXT DEFAULT '1.0.0',
    status TEXT DEFAULT 'available',
    supported_actions_json TEXT DEFAULT '[]',
    last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS os_permission_states (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    resource_id TEXT,
    status TEXT NOT NULL,
    checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_requested_at TEXT,
    last_error_code TEXT
);

CREATE TABLE IF NOT EXISTS permission_grants (
    id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    resource_scope TEXT NOT NULL,
    grant_source TEXT DEFAULT 'desktop_ui',
    granted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    revoked_at TEXT,
    policy_version INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS permission_audit_events (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    session_id TEXT,
    principal_type TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    resource_scope TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_sources (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    publisher_id TEXT,
    trust_level TEXT DEFAULT 'unreviewed',
    enabled INTEGER DEFAULT 1,
    last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS installed_skills (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    publisher TEXT,
    source_id TEXT REFERENCES skill_sources(id) ON DELETE SET NULL,
    installed_version TEXT NOT NULL,
    package_hash TEXT NOT NULL,
    trust_level TEXT DEFAULT 'unreviewed',
    enabled INTEGER DEFAULT 0,
    installed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_versions (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    package_hash TEXT NOT NULL,
    source_commit TEXT,
    manifest_json TEXT NOT NULL,
    scan_report_json TEXT NOT NULL,
    installed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skill_capability_requests (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    version TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    resource_scope TEXT NOT NULL,
    decision TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    transport TEXT DEFAULT 'stdio',
    command TEXT NOT NULL,
    args_json TEXT DEFAULT '[]',
    environment_allowlist_json TEXT DEFAULT '[]',
    package_version TEXT,
    package_hash TEXT,
    enabled INTEGER DEFAULT 0,
    trust_level TEXT DEFAULT 'unreviewed',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS credentials_metadata (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL UNIQUE,
    credential_ref TEXT NOT NULL,
    label TEXT,
    masked_preview TEXT,
    backend TEXT DEFAULT 'windows_dpapi',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approval_requests (
    approval_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    session_id TEXT,
    user_id TEXT DEFAULT 'default_user',
    tool_id TEXT NOT NULL,
    tool_version TEXT DEFAULT '1.0.0',
    arguments_json TEXT NOT NULL,
    arguments_hash TEXT NOT NULL,
    resource_ids_json TEXT DEFAULT '[]',
    workspace_id TEXT,
    risk_level TEXT NOT NULL,
    data_classification TEXT DEFAULT 'INTERNAL',
    requested_permissions_json TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    decided_at TEXT,
    decision TEXT DEFAULT 'pending',
    one_time INTEGER DEFAULT 1,
    consumed INTEGER DEFAULT 0,
    policy_version INTEGER DEFAULT 1,
    decision_reason TEXT
);

CREATE TABLE IF NOT EXISTS rag_vector_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    section_title TEXT,
    content TEXT NOT NULL,
    vector_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS telegram_allowed_users (
    telegram_user_id INTEGER PRIMARY KEY,
    username TEXT,
    paired_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


class DatabaseManager:
    """Async SQLite manager for AKSA state persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.sqlite_path

    async def initialize(self) -> None:
        """Create database tables and apply versioned migrations transactionally."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.executescript(SCHEMA_SQL)
            try:
                await db.execute("ALTER TABLE installed_applications ADD COLUMN is_connected INTEGER DEFAULT 0")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE installed_applications ADD COLUMN category_label TEXT DEFAULT 'Aplikasi Komputer Umum'")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE workspaces ADD COLUMN owner_id TEXT DEFAULT 'default_user'")
            except Exception:
                pass
            try:
                await db.execute("ALTER TABLE sessions ADD COLUMN principal_id TEXT DEFAULT 'default_user'")
            except Exception:
                pass

            now = _now_iso()
            for ver, name in (
                (1, "v1_initial_core_schema"),
                (2, "v2_enterprise_security_vault_and_approvals"),
            ):
                await db.execute(
                    """
                    INSERT INTO schema_migrations (version, name, applied_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(version) DO NOTHING
                    """,
                    (ver, name, now),
                )
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

    async def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        """Retrieve a specific authorized PC workspace folder by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = _row_to_dict(row)
            item["allow_read"] = bool(item["allow_read"])
            item["allow_write"] = bool(item["allow_write"])
            item["allow_execute"] = bool(item["allow_execute"])
            item["auto_rag_sync"] = bool(item["auto_rag_sync"])
            if "owner_id" not in item or not item["owner_id"]:
                item["owner_id"] = get_default_host_principal()
            return item

    async def get_workspace_by_path(self, folder_path: str) -> dict[str, Any] | None:
        """Retrieve a workspace record matching canonical folder path (P0-02)."""
        resolved = str(Path(folder_path).expanduser().resolve())
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM workspaces WHERE folder_path = ?", (resolved,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = _row_to_dict(row)
            item["allow_read"] = bool(item["allow_read"])
            item["allow_write"] = bool(item["allow_write"])
            item["allow_execute"] = bool(item["allow_execute"])
            item["auto_rag_sync"] = bool(item["auto_rag_sync"])
            if "owner_id" not in item or not item["owner_id"]:
                item["owner_id"] = get_default_host_principal()
            return item

    async def list_workspaces(self, principal_id: str | None = None) -> list[dict[str, Any]]:
        """List all authorized PC workspace folders, optionally filtered by principal."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if principal_id:
                cursor = await db.execute(
                    "SELECT * FROM workspaces WHERE owner_id = ? ORDER BY created_at DESC",
                    (principal_id,),
                )
            else:
                cursor = await db.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                item = _row_to_dict(row)
                item["allow_read"] = bool(item["allow_read"])
                item["allow_write"] = bool(item["allow_write"])
                item["allow_execute"] = bool(item["allow_execute"])
                item["auto_rag_sync"] = bool(item["auto_rag_sync"])
                if "owner_id" not in item or not item["owner_id"]:
                    item["owner_id"] = get_default_host_principal()
                results.append(item)
            return results

    async def upsert_workspace(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Register or update an authorized PC workspace folder."""
        ws_id = payload.get("id") or f"ws_{uuid.uuid4().hex[:10]}"
        resolved_path = str(Path(payload["folder_path"]).expanduser().resolve())
        name = payload.get("name") or Path(resolved_path).name or resolved_path
        owner_id = payload.get("owner_id") or get_default_host_principal()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO workspaces (
                    id, name, folder_path, allow_read, allow_write, allow_execute, auto_rag_sync, owner_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_path) DO UPDATE SET
                    name = excluded.name,
                    allow_read = excluded.allow_read,
                    allow_write = excluded.allow_write,
                    allow_execute = excluded.allow_execute,
                    auto_rag_sync = excluded.auto_rag_sync,
                    owner_id = COALESCE(excluded.owner_id, workspaces.owner_id)
                """,
                (
                    ws_id,
                    name,
                    resolved_path,
                    int(payload.get("allow_read", True)),
                    int(payload.get("allow_write", True)),
                    int(payload.get("allow_execute", False)),
                    int(payload.get("auto_rag_sync", True)),
                    owner_id,
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
            if "owner_id" not in item or not item["owner_id"]:
                item["owner_id"] = owner_id
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

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve a specific chat session by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            item = _row_to_dict(row)
            if "principal_id" not in item or not item["principal_id"]:
                item["principal_id"] = get_default_host_principal()
            return item

    async def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a new chat session."""
        session_id = payload.get("id") or f"sess_{uuid.uuid4().hex[:10]}"
        principal_id = payload.get("principal_id") or get_default_host_principal()
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT OR REPLACE INTO sessions (id, title, workspace_id, team_id, source, principal_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    payload.get("title", "Sesi Kerja Baru"),
                    payload.get("workspace_id"),
                    payload.get("team_id"),
                    payload.get("source", "desktop"),
                    principal_id,
                    now,
                    now,
                ),
            )
            await db.commit()
            return await self.get_session(session_id)

    # --- Installed Applications CRUD ---
    async def upsert_installed_app(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Store or update a normalized application discovery record."""
        app_id = payload.get("id") or f"app_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        category = payload.get("category_label") or "Aplikasi Komputer Umum"
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO installed_applications (
                    id, platform, platform_app_id, bundle_id, aumid, display_name,
                    publisher, version, install_location, install_scope, signature_status,
                    detection_sources_json, is_installed, is_running, is_connected, category_label,
                    available_adapters_json, last_seen_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = excluded.display_name,
                    publisher = excluded.publisher,
                    version = excluded.version,
                    install_location = excluded.install_location,
                    is_installed = excluded.is_installed,
                    is_running = excluded.is_running,
                    category_label = excluded.category_label,
                    available_adapters_json = excluded.available_adapters_json,
                    last_seen_at = excluded.last_seen_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    app_id,
                    payload.get("platform", "windows"),
                    payload.get("platform_app_id", app_id),
                    payload.get("bundle_id"),
                    payload.get("aumid"),
                    payload.get("display_name", "Aplikasi"),
                    payload.get("publisher"),
                    payload.get("version"),
                    payload.get("install_location"),
                    payload.get("install_scope", "machine"),
                    payload.get("signature_status", "unknown"),
                    json.dumps(payload.get("detection_sources", [])),
                    int(payload.get("is_installed", True)),
                    int(payload.get("is_running", False)),
                    int(payload.get("is_connected", False)),
                    category,
                    json.dumps(payload.get("available_adapters", [])),
                    now,
                    json.dumps(payload.get("metadata", {})),
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM installed_applications WHERE id = ?", (app_id,))
            row = await cursor.fetchone()
            item = _row_to_dict(row)
            item["detection_sources"] = json.loads(item.pop("detection_sources_json", "[]"))
            item["available_adapters"] = json.loads(item.pop("available_adapters_json", "[]"))
            item["metadata"] = json.loads(item.pop("metadata_json", "{}"))
            item["is_installed"] = bool(item["is_installed"])
            item["is_running"] = bool(item["is_running"])
            item["is_connected"] = bool(item.get("is_connected", 0))
            item["category_label"] = item.get("category_label") or "Aplikasi Komputer Umum"
            return item

    async def list_installed_apps(self, platform: str | None = None) -> list[dict[str, Any]]:
        """List all discovered desktop applications."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if platform:
                cursor = await db.execute(
                    "SELECT * FROM installed_applications WHERE platform = ? ORDER BY display_name ASC",
                    (platform,),
                )
            else:
                cursor = await db.execute("SELECT * FROM installed_applications ORDER BY display_name ASC")
            items = []
            for r in await cursor.fetchall():
                d = _row_to_dict(r)
                d["detection_sources"] = json.loads(d.pop("detection_sources_json", "[]"))
                d["available_adapters"] = json.loads(d.pop("available_adapters_json", "[]"))
                d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
                d["is_installed"] = bool(d["is_installed"])
                d["is_running"] = bool(d["is_running"])
                d["is_connected"] = bool(d.get("is_connected", 0))
                d["category_label"] = d.get("category_label") or "Aplikasi Komputer Umum"
                items.append(d)
            return items

    async def get_installed_app(self, app_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM installed_applications WHERE id = ?", (app_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = _row_to_dict(row)
            d["detection_sources"] = json.loads(d.pop("detection_sources_json", "[]"))
            d["available_adapters"] = json.loads(d.pop("available_adapters_json", "[]"))
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            d["is_installed"] = bool(d["is_installed"])
            d["is_running"] = bool(d["is_running"])
            d["is_connected"] = bool(d.get("is_connected", 0))
            d["category_label"] = d.get("category_label") or "Aplikasi Komputer Umum"
            return d

    async def toggle_app_connection(self, app_id: str, is_connected: bool) -> dict[str, Any] | None:
        """Connect or disconnect an application's authorization in AKSA, working offline or online."""
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM installed_applications WHERE id = ?", (app_id,))
            row = await cursor.fetchone()
            if not row:
                return None

            await db.execute(
                "UPDATE installed_applications SET is_connected = ? WHERE id = ?",
                (int(is_connected), app_id),
            )

            cap_id = f"app.access.{app_id}"
            if is_connected:
                grant_id = f"grant_{uuid.uuid4().hex[:12]}"
                await db.execute(
                    """
                    INSERT INTO permission_grants (id, principal_type, principal_id, capability_id, resource_scope, grant_source, granted_at, policy_version)
                    VALUES (?, 'user', 'default_user', ?, 'application', 'desktop_ui', ?, 1)
                    """,
                    (grant_id, cap_id, now),
                )
            else:
                await db.execute(
                    "UPDATE permission_grants SET revoked_at = ? WHERE capability_id = ? AND revoked_at IS NULL",
                    (now, cap_id),
                )

            # Audit event
            aud_id = f"aud_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """
                INSERT INTO permission_audit_events (id, principal_type, principal_id, capability_id, resource_scope, decision, reason_code, created_at)
                VALUES (?, 'user', 'default_user', ?, 'application', ?, ?, ?)
                """,
                (
                    aud_id,
                    cap_id,
                    "allow" if is_connected else "deny",
                    "USER_APP_CONNECT" if is_connected else "USER_APP_DISCONNECT",
                    now,
                ),
            )

            await db.commit()

            cursor = await db.execute("SELECT * FROM installed_applications WHERE id = ?", (app_id,))
            r = await cursor.fetchone()
            d = _row_to_dict(r)
            d["detection_sources"] = json.loads(d.pop("detection_sources_json", "[]"))
            d["available_adapters"] = json.loads(d.pop("available_adapters_json", "[]"))
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            d["is_installed"] = bool(d["is_installed"])
            d["is_running"] = bool(d["is_running"])
            d["is_connected"] = bool(d.get("is_connected", 0))
            d["category_label"] = d.get("category_label") or "Aplikasi Komputer Umum"
            return d

    # --- OS Permission States & Grants CRUD ---
    async def upsert_os_permission(self, payload: dict[str, Any]) -> dict[str, Any]:
        perm_id = payload.get("id") or f"perm_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO os_permission_states (id, platform, capability_id, resource_id, status, checked_at, last_requested_at, last_error_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    checked_at = excluded.checked_at,
                    last_requested_at = excluded.last_requested_at,
                    last_error_code = excluded.last_error_code
                """,
                (
                    perm_id,
                    payload.get("platform", "windows"),
                    payload["capability_id"],
                    payload.get("resource_id"),
                    payload["status"],
                    now,
                    payload.get("last_requested_at"),
                    payload.get("last_error_code"),
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM os_permission_states WHERE id = ?", (perm_id,))
            return _row_to_dict(await cursor.fetchone())

    async def list_os_permissions(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM os_permission_states ORDER BY capability_id ASC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    async def create_permission_grant(self, payload: dict[str, Any]) -> dict[str, Any]:
        grant_id = payload.get("id") or f"grant_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO permission_grants (id, principal_type, principal_id, capability_id, resource_scope, grant_source, granted_at, expires_at, policy_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    grant_id,
                    payload.get("principal_type", "user"),
                    payload.get("principal_id") or get_default_host_principal(),
                    payload["capability_id"],
                    payload["resource_scope"],
                    payload.get("grant_source", "desktop_ui"),
                    now,
                    payload.get("expires_at"),
                    payload.get("policy_version", 1),
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM permission_grants WHERE id = ?", (grant_id,))
            return _row_to_dict(await cursor.fetchone())

    async def list_permission_grants(self, active_only: bool = True) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if active_only:
                cursor = await db.execute("SELECT * FROM permission_grants WHERE revoked_at IS NULL ORDER BY granted_at DESC")
            else:
                cursor = await db.execute("SELECT * FROM permission_grants ORDER BY granted_at DESC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    async def revoke_permission_grant(self, grant_id: str) -> bool:
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE permission_grants SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (now, grant_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def log_permission_audit_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO permission_audit_events (id, task_id, session_id, principal_type, principal_id, capability_id, resource_scope, decision, reason_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    payload.get("task_id"),
                    payload.get("session_id"),
                    payload.get("principal_type", "agent"),
                    payload.get("principal_id", "operator"),
                    payload["capability_id"],
                    payload.get("resource_scope", "workspace"),
                    payload["decision"],
                    payload.get("reason_code"),
                    now,
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM permission_audit_events WHERE id = ?", (event_id,))
            return _row_to_dict(await cursor.fetchone())

    # Alias for consistent naming across modules
    record_permission_audit = log_permission_audit_event

    async def list_permission_audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM permission_audit_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    # --- Agent Skills CRUD ---
    async def upsert_installed_skill(self, payload: dict[str, Any]) -> dict[str, Any]:
        skill_id = payload["skill_id"]
        pk_id = payload.get("id") or f"iskill_{uuid.uuid4().hex[:10]}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO installed_skills (
                    id, skill_id, display_name, publisher, source_id,
                    installed_version, package_hash, trust_level, enabled,
                    installed_at, last_verified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    publisher = excluded.publisher,
                    installed_version = excluded.installed_version,
                    package_hash = excluded.package_hash,
                    trust_level = excluded.trust_level,
                    last_verified_at = excluded.last_verified_at
                """,
                (
                    pk_id,
                    skill_id,
                    payload.get("display_name", skill_id),
                    payload.get("publisher", "Komunitas"),
                    payload.get("source_id"),
                    payload.get("installed_version", "1.0.0"),
                    payload.get("package_hash", ""),
                    payload.get("trust_level", "unreviewed"),
                    int(payload.get("enabled", False)),  # Disabled by default
                    now,
                    now,
                ),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM installed_skills WHERE skill_id = ?", (skill_id,))
            row = await cursor.fetchone()
            d = _row_to_dict(row)
            d["enabled"] = bool(d["enabled"])
            return d

    async def list_installed_skills(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM installed_skills ORDER BY display_name ASC")
            items = []
            for r in await cursor.fetchall():
                d = _row_to_dict(r)
                d["enabled"] = bool(d["enabled"])
                items.append(d)
            return items

    async def get_installed_skill(self, skill_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM installed_skills WHERE skill_id = ?", (skill_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            d = _row_to_dict(row)
            d["enabled"] = bool(d["enabled"])
            return d

    async def toggle_skill_enabled(self, skill_id: str, enabled: bool) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                "UPDATE installed_skills SET enabled = ?, last_verified_at = ? WHERE skill_id = ?",
                (int(enabled), _now_iso(), skill_id),
            )
            await db.commit()
            return await self.get_installed_skill(skill_id)

    async def delete_installed_skill(self, skill_id: str) -> bool:
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM installed_skills WHERE skill_id = ?", (skill_id,))
            deleted = cursor.rowcount > 0
            # Revoke all capability requests and permission grants bound to this skill
            await db.execute(
                "UPDATE skill_capability_requests SET decision = 'revoked', revoked_at = ? WHERE skill_id = ? AND revoked_at IS NULL",
                (now, skill_id),
            )
            await db.execute(
                "UPDATE permission_grants SET revoked_at = ? WHERE (resource_scope = ? OR principal_id = ?) AND revoked_at IS NULL",
                (now, skill_id, skill_id),
            )
            await db.commit()
            return deleted

    async def revoke_all_workspaces(self, principal_id: str | None = None) -> int:
        """Revoke all workspace access and remove registered workspace entries, optionally filtered by principal."""
        now = _now_iso()
        eff_principal = principal_id or get_default_host_principal()
        async with aiosqlite.connect(self.db_path) as db:
            if principal_id:
                cursor = await db.execute("DELETE FROM workspaces WHERE owner_id = ?", (principal_id,))
            else:
                cursor = await db.execute("DELETE FROM workspaces")
            removed = cursor.rowcount
            await db.execute(
                "UPDATE permission_grants SET revoked_at = ? WHERE capability_id LIKE 'filesystem.%' AND revoked_at IS NULL",
                (now,),
            )
            aud_id = f"aud_{uuid.uuid4().hex[:12]}"
            await db.execute(
                """
                INSERT INTO permission_audit_events (id, principal_type, principal_id, capability_id, resource_scope, decision, reason_code, created_at)
                VALUES (?, 'user', ?, 'filesystem.workspace.revoke_all', 'all_workspaces', 'deny', 'USER_REVOKE_ALL_WORKSPACES', ?)
                """,
                (aud_id, eff_principal, now),
            )
            await db.commit()
            return removed

    async def list_schema_migrations(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM schema_migrations ORDER BY version ASC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    # --- Credentials Metadata CRUD (No Plaintext Secrets) ---
    async def upsert_credential_metadata(
        self,
        provider: str,
        credential_ref: str,
        masked_preview: str,
        backend: str = "windows_dpapi",
        label: str | None = None,
    ) -> dict[str, Any]:
        meta_id = f"cmeta_{provider}"
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO credentials_metadata (id, provider, credential_ref, label, masked_preview, backend, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    credential_ref = excluded.credential_ref,
                    label = excluded.label,
                    masked_preview = excluded.masked_preview,
                    backend = excluded.backend,
                    updated_at = excluded.updated_at
                """,
                (meta_id, provider, credential_ref, label or f"{provider} API Key", masked_preview, backend, now, now),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM credentials_metadata WHERE provider = ?", (provider,))
            return _row_to_dict(await cursor.fetchone())

    async def get_credential_metadata(self, provider: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM credentials_metadata WHERE provider = ?", (provider,))
            row = await cursor.fetchone()
            return _row_to_dict(row) if row else None

    async def list_credentials_metadata(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM credentials_metadata ORDER BY provider ASC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    async def delete_credential_metadata(self, provider: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM credentials_metadata WHERE provider = ?", (provider,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_telegram_allowed_users(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM telegram_allowed_users ORDER BY paired_at ASC")
            return [_row_to_dict(r) for r in await cursor.fetchall()]

    async def add_telegram_allowed_user(self, telegram_user_id: int, username: str = "pengguna_telegram") -> dict[str, Any]:
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """
                INSERT INTO telegram_allowed_users (telegram_user_id, username, paired_at, last_active_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    username = excluded.username,
                    last_active_at = excluded.last_active_at
                """,
                (telegram_user_id, username, now, now),
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM telegram_allowed_users WHERE telegram_user_id = ?", (telegram_user_id,))
            return _row_to_dict(await cursor.fetchone())

    async def remove_telegram_allowed_user(self, telegram_user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM telegram_allowed_users WHERE telegram_user_id = ?", (telegram_user_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def get_setting(self, key: str, default: Any = None) -> Any:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value_json"])
                except Exception:
                    return row["value_json"]
            return default

    async def set_setting(self, key: str, value: Any) -> None:
        val_json = json.dumps(value) if not isinstance(value, str) else value
        now = _now_iso()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, val_json, now),
            )
            await db.commit()


db_manager = DatabaseManager()

