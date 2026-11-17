# 07 — Database Schema & API Contract Specification

## 1. Local SQLite Database Schema (`<AppData>/aksa/data/aksa.db`)

AKSA uses SQLite (with WAL mode enabled for high concurrency and FTS5 for full-text search) to store all relational state.

```sql
-- 1. Agent Teams (Hierarchical Blueprints)
CREATE TABLE IF NOT EXISTS agent_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                      -- e.g., "Tim Produktivitas Kantor"
    description TEXT,
    is_default INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. Individual Agents within a Team Hierarchy
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES agent_teams(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES agents(id) ON DELETE SET NULL, -- NULL = Root Supervisor
    name TEXT NOT NULL,                      -- e.g., "Spesialis Excel & Keuangan"
    role_title TEXT NOT NULL,
    description TEXT NOT NULL,               -- Used by parent agent for routing decisions
    avatar_icon TEXT DEFAULT 'bot',
    tier_level INTEGER DEFAULT 0,            -- 0 = Supervisor, 1 = Specialist, 2 = Sub-worker
    
    -- Model Configuration
    provider TEXT NOT NULL,                  -- openai, anthropic, gemini, deepseek, openrouter, ollama, lmstudio
    model_id TEXT NOT NULL,                  -- e.g., "ollama/qwen2.5:7b", "claude-3-7-sonnet-latest"
    temperature REAL DEFAULT 0.2,
    max_tokens INTEGER DEFAULT 4096,
    
    -- Instructions & Tools
    system_prompt TEXT NOT NULL,             -- Written in Bahasa Indonesia
    tool_categories_json TEXT NOT NULL,      -- JSON array: ["office_excel", "office_word", "filesystem"]
    
    -- React Flow Canvas Coordinates
    position_x REAL DEFAULT 0,
    position_y REAL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Authorized PC Workspace Folders (Sandbox Whitelist)
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                      -- e.g., "Laporan Keuangan 2026"
    folder_path TEXT NOT NULL UNIQUE,        -- Absolute OS path, e.g., "D:\Kerjaan\Keuangan"
    allow_read INTEGER DEFAULT 1,
    allow_write INTEGER DEFAULT 1,
    allow_execute INTEGER DEFAULT 0,
    auto_rag_sync INTEGER DEFAULT 1,         -- Watchdog auto-index toggle
    last_indexed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 4. Chat Sessions (Desktop GUI or Telegram)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    workspace_id TEXT REFERENCES workspaces(id) ON DELETE SET NULL,
    team_id TEXT REFERENCES agent_teams(id) ON DELETE SET NULL,
    source TEXT DEFAULT 'desktop',           -- 'desktop' | 'telegram'
    telegram_chat_id INTEGER,
    compacted_summary TEXT,                  -- Rolling summary for token optimization
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    estimated_tokens_saved INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 5. Session Messages & Hierarchical Execution Trace
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sender_role TEXT NOT NULL,               -- 'user' | 'supervisor' | 'sub_agent' | 'system'
    agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    execution_steps_json TEXT,               -- JSON trace of sub-agent delegations & tool calls
    artifacts_json TEXT,                     -- JSON array of created/modified file paths
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. RAG Indexed Documents Metadata
CREATE TABLE IF NOT EXISTS rag_documents (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_ext TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    sha256_hash TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'indexed',           -- 'pending' | 'indexing' | 'indexed' | 'error'
    error_message TEXT,
    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 7. Full-Text Search (FTS5) Virtual Table for Hybrid RAG
CREATE VIRTUAL TABLE IF NOT EXISTS rag_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    document_id UNINDEXED,
    workspace_id UNINDEXED,
    file_name,
    section_title,
    content,
    tokenize = 'unicode61'
);

-- 8. Token Usage & Efficiency Analytics Log
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
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 2. REST API Endpoints (`http://127.0.0.1:<port>/api/v1`)

All endpoints require the `X-AKSA-Auth-Token` header generated by the Tauri Rust core process.

### 2.1 System & Models
- `GET  /api/v1/health` — Returns engine status, active watchers, Ollama availability, and Telegram bot state.
- `GET  /api/v1/models/providers` — Lists configured Cloud API providers and auto-discovered Local Ollama / LM Studio models.
- `POST /api/v1/models/test` — Tests an API key or local model connection.
- `POST /api/v1/models/ollama/pull` — Streams download progress for pulling a local Ollama model.

### 2.2 Agent Teams & Hierarchy
- `GET    /api/v1/teams` — Lists all hierarchical agent teams and their nested agent nodes.
- `POST   /api/v1/teams` — Creates a new agent team.
- `PUT    /api/v1/teams/{team_id}/hierarchy` — Saves visual React Flow node positions, parent-child links, and per-agent model configs in one atomic transaction.
- `POST   /api/v1/agents` — Adds a new agent node to a team.
- `PATCH  /api/v1/agents/{agent_id}` — Updates an agent's model, Bahasa Indonesia prompt, or allowed tool categories.
- `DELETE /api/v1/agents/{agent_id}` — Removes an agent node.

### 2.3 Workspaces, Files & Office Artifacts
- `GET    /api/v1/workspaces` — Lists authorized PC folders and their permission flags.
- `POST   /api/v1/workspaces` — Registers a newly selected PC folder and optionally triggers initial RAG indexing.
- `GET    /api/v1/workspaces/{id}/files` — Lists files inside the workspace folder with metadata.
- `POST   /api/v1/workspaces/{id}/backup/restore` — Restores a file from `.aksa_backup/` if the user wants to undo an agent's edit.

### 2.4 RAG & Knowledge Base
- `GET  /api/v1/rag/{workspace_id}/documents` — Lists indexed files, chunk counts, and sync status.
- `POST /api/v1/rag/{workspace_id}/reindex` — Triggers an incremental or full re-index of the workspace folder.
- `POST /api/v1/rag/{workspace_id}/search` — Executes a Hybrid Search (LanceDB Vector + SQLite FTS5) and returns ranked chunks with citations.

### 2.5 Telegram Gateway & Security
- `GET  /api/v1/telegram/status` — Returns bot connection status, bot `@username`, and whitelisted Telegram User IDs.
- `POST /api/v1/telegram/configure` — Saves bot token, starts/restarts polling, and generates a 6-digit pairing code.
- `POST /api/v1/telegram/Approval/{request_id}` — Resolves a pending HITL permission request.

---

## 3. WebSocket Real-Time Event Protocol (`ws://127.0.0.1:<port>/ws/stream`)

When a task is running, the backend streams JSON events to the React UI so the user sees every sub-agent action live:

```json
{
  "event": "sub_agent_delegated",
  "session_id": "sess_01J9...",
  "timestamp": "2026-11-17T00:01:12Z",
  "payload": {
    "from_agent": { "id": "agt_mgr", "name": "Manajer Utama" },
    "to_agent": { "id": "agt_excel", "name": "Spesialis Office & Laporan", "model": "deepseek/deepseek-chat" },
    "task_brief": "Membuat file Rekap_Keuangan_Nov2026.xlsx dengan rumus SUM dan grafik bulanan"
  }
}
```

### Supported WebSocket Event Types:
- `plan_created` — Displays the structured step-by-step plan in Bahasa Indonesia.
- `sub_agent_delegated` — Highlights the active sub-agent node and animates the connection edge.
- `tool_execution_start` / `tool_execution_end` — Updates the collapsible tool step card (e.g., `📊 Membuat sheet 'Ringkasan' di Laporan.xlsx...`).
- `token_stream_delta` — Streams markdown response text token-by-token.
- `artifact_created` — Immediately populates the Right Artifact Drawer with the newly created Word/Excel/PPT/PDF file.
- `hitl_approval_required` — Pops up the confirmation modal in the GUI when a high-risk action requires user approval.
- `token_metrics_updated` — Updates the live token counter and "Token Hemat" badge in the sidebar.

