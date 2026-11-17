# AGENTS.md — Master Instructions for AI Coding Agents

This file defines the mandatory architectural rules, coding conventions, localization standards, and workflows for any AI coding agent (Antigravity, Claude Code, Cursor, etc.) working on the **AKSA** repository.

---

## 1. Golden Rules (Read First)

1. **Language Split Rule (CRITICAL):**
   - **Code, Identifiers, Comments, Git Commits, and Technical Docs:** Must be written in **English**.
   - **User-Facing Application (UI Labels, Tooltips, Placeholders, Error Messages, Toast Notifications, Default Agent Prompts, Onboarding, Telegram Bot Replies):** Must be written in **natural, polite, modern Bahasa Indonesia**.
   - Never mix awkward literal translations in the UI. Refer to [`docs/06-UI-UX-DESIGN-SYSTEM.md`](./docs/06-UI-UX-DESIGN-SYSTEM.md) for the official Indonesian UI glossary.
2. **Clean, Premium UI/UX Standard:**
   - Every UI component must follow a clean, distraction-free aesthetic inspired by **Linear**, **Claude Desktop**, and **Cursor**.
   - Use **Tailwind CSS v4**, **`shadcn/ui`**, **`lucide-react`**, and **`framer-motion`**.
   - **No Static / Emoji Icons Rule (CRITICAL):** Never use static Unicode emojis (`🏠`, `☁️`, `🎙️`, `📊`, `✅`, etc.) or hardcoded static icon strings in the UI. Always use dynamic vector icon components from `lucide-react` (or dedicated React icon libraries) paired with `framer-motion` / Tailwind micro-interactions (`hover:scale-110`, animated status indicators, dynamic icon mapping). Refer to [`docs/06-UI-UX-DESIGN-SYSTEM.md`](./docs/06-UI-UX-DESIGN-SYSTEM.md).
   - Avoid visual clutter: use progressive disclosure (collapsible tool execution cards, slide-over inspector panels, clean typography with `Inter` / `Geist`).
3. **Security & Workspace Sandbox First:**
   - No file system tool, Office generator, or terminal command may read or write outside the user's active **Authorized Workspace Folders** (`allowed_paths`) unless explicitly granted permission via the **Human-in-the-Loop (HITL) Approval Gate**.
   - Path traversal checks (`os.path.realpath` validation against `allowed_paths`) must be enforced at the Python engine layer, never just in the UI or prompt.
4. **Token Efficiency by Design:**
   - Never dump raw megabytes of document text, huge tool schemas, or full sub-agent scratchpads into the Supervisor Agent's context window.
   - Always follow the **Sub-Agent Context Isolation** and **Lazy Tool Loading** patterns defined in [`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md).
5. **Cross-Platform Compatibility (Windows & macOS):**
   - Never hardcode Windows-only paths (`\` or `C:\`) or macOS-only commands (`open`, `pbcopy`) without an OS abstraction layer (`sys.platform == "win32"` vs `"darwin"`).
   - Always use `pathlib.Path` in Python, `std::path::PathBuf` in Rust (Tauri), and `@tauri-apps/api/path` in the frontend.

---

## 2. Target Repository Structure

Maintain the following clean monorepo structure as features are implemented:

```text
aksa/
├── README.md
├── AGENTS.md
├── docs/                                # Architectural & engineering specifications
│   ├── 01-ARCHITECTURE.md
│   ├── 02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md
│   ├── 03-PC-AUTOMATION-AND-OFFICE-ENGINE.md
│   ├── 04-RAG-AND-MEMORY-SYSTEM.md
│   ├── 05-TELEGRAM-GATEWAY.md
│   ├── 06-UI-UX-DESIGN-SYSTEM.md
│   ├── 07-DATABASE-AND-API-SCHEMA.md
│   └── 08-ROADMAP-AND-PHASES.md
├── apps/
│   └── desktop/                         # Tauri v2 + React 19 + TypeScript Desktop App
│       ├── src-tauri/                   # Tauri v2 Rust Core & Native Shell
│       │   ├── Cargo.toml               # Rust dependencies & Tauri plugins
│       │   ├── tauri.conf.json          # Window config, bundle targets (.exe/.msi/.dmg), sidecar config
│       │   ├── capabilities/            # Tauri v2 fine-grained security permissions
│       │   ├── binaries/                # Bundled Python sidecar executable per target triple
│       │   └── src/
│       │       ├── main.rs              # Rust entrypoint
│       │       ├── lib.rs               # Tauri builder, System Tray, commands, plugin registration
│       │       └── sidecar.rs           # Lifecycle & healthcheck manager for Python FastAPI sidecar
│       ├── src/                         # React Renderer Application
│       │   ├── components/
│       │   │   ├── ui/                  # shadcn/ui primitives (Button, Dialog, Sheet, etc.)
│       │   │   ├── layout/              # Sidebar, Header, StatusFooter, CommandPalette
│       │   │   ├── workspace/           # Chat stream, SubAgentStepCard, FileArtifactPreview
│       │   │   ├── agents/              # React Flow hierarchy canvas, AgentNode, ModelSelector
│       │   │   ├── rag/                 # Folder watcher manager, DocumentIndexTable
│       │   │   ├── telegram/            # Telegram bot setup, whitelist manager, live logs
│       │   │   └── settings/            # API keys, Ollama status, Token efficiency analytics
│       │   ├── stores/                  # Zustand state stores
│       │   ├── services/                # Tauri invoke commands + REST & WebSocket clients to sidecar
│       │   ├── lib/                     # Utilities, formatting, Indonesian i18n constants
│       │   └── types/                   # Shared TypeScript interfaces
│       ├── package.json
│       └── vite.config.ts
└── services/
    └── engine/                          # Python FastAPI Backend Sidecar
        ├── pyproject.toml               # Managed by uv
        ├── app/
        │   ├── main.py                  # FastAPI entrypoint, CORS, WebSocket hub
        │   ├── config.py                # App data paths, SQLite/LanceDB initialization
        │   ├── api/                     # REST & WebSocket routers
        │   ├── core/
        │   │   ├── orchestrator.py      # Hierarchical Supervisor -> Sub-Agent execution engine
        │   │   ├── llm_router.py        # Unified LiteLLM + Ollama/LM Studio client
        │   │   ├── token_optimizer.py   # Compaction, lazy tools, token counting & budget guard
        │   │   └── sandbox.py           # Workspace path jail & HITL approval manager
        │   ├── tools/
        │   │   ├── registry.py          # Dynamic tool registry & category loader
        │   │   ├── office/              # Word (.docx), Excel (.xlsx), PPT (.pptx), PDF tools
        │   │   ├── filesystem/          # Scoped file CRUD, search, archive tools
        │   │   ├── os_bridge/           # Windows COM, macOS AppleScript, shell & uv runner
        │   │   ├── computer_use/        # Screen capture, Vision grounding, mouse/keyboard
        │   │   └── mcp/                 # Model Context Protocol client integration
        │   ├── rag/
        │   │   ├── ingest.py            # MarkItDown/PyMuPDF parser & semantic chunker
        │   │   ├── store.py             # LanceDB + SQLite FTS5 hybrid search engine
        │   │   └── watcher.py           # Watchdog real-time folder synchronization
        │   ├── telegram/
        │   │   ├── bot.py               # Aiogram long-polling service
        │   │   ├── auth.py              # User ID whitelist & pairing verification
        │   │   └── handlers.py          # Text, voice note, file upload, & HITL callback handlers
        │   ├── db/
        │   │   ├── models.py            # SQLite schema & CRUD operations
        │   │   └── seed.py              # Default Indonesian agent team templates
        │   └── prompts/                 # System prompts in Bahasa Indonesia & tool instructions
        └── tests/                       # Pytest suite for tools, sandbox, orchestrator, and RAG
```

---

## 3. Coding Standards & Best Practices

### TypeScript / React (Frontend)
- **Strict TypeScript:** Enable `"strict": true`. Avoid `any`; define explicit interfaces in `src/types/`.
- **Component Modularity:** Keep components under 250 lines. Extract complex logic into custom hooks (`src/hooks/`) or Zustand stores (`src/stores/`).
- **Real-Time Responsiveness:** All agent execution updates (thinking, sub-agent delegation, tool execution, file creation, token increments) must stream over WebSockets/SSE so the UI feels instantaneous.
- **Error Boundaries & Empty States:** Every view must have a clean, helpful Indonesian empty state (e.g., *"Belum ada folder kerja yang dipilih. Pilih folder di PC Anda untuk mulai bekerja."*).

### Python (Backend Engine)
- **Python 3.12+ & Type Hints:** Use modern Python typing (`list[str]`, `dict[str, Any]`, `X | None`) and **Pydantic v2** for all data validation, API payloads, and tool schemas.
- **Async First:** Use `async`/`await` across FastAPI endpoints, LLM calls (`litellm.acompletion`), SQLite (`aiosqlite`), and Telegram (`aiogram`). Run blocking CPU/IO operations (like `openpyxl` or `pyautogui`) inside `asyncio.to_thread()`.
- **Structured Tool Outputs:** Every tool executed by an agent must return a structured `ToolResult(success: bool, summary: str, data: Any, artifacts: list[str], token_estimate: int)` so the orchestrator can log artifacts (like newly created `.xlsx` files) and keep context compact.

---

## 4. How to Approach Implementation Tasks (Mandatory Progress Tracking)

1. **Read [`PROGRESS.md`](./PROGRESS.md) First (CRITICAL):**
   - At the start of every session or task, read [`PROGRESS.md`](./PROGRESS.md) to check the **Current Status Summary**, **Last Completed Task**, and **Next Immediate Action**.
   - Never guess what has or hasn't been built—always check the master checklist in `PROGRESS.md`.
2. **Consult Domain Specs:**
   - Before implementing a subsystem (e.g., RAG, Office Tools, Agent Canvas, Telegram), read its dedicated markdown specification in `docs/`.
3. **Verify Incrementally:**
   - After implementing a backend endpoint or tool, test it via `pytest` or FastAPI health checks; after implementing a UI view, verify TypeScript compilation (`tsc --noEmit`) and visual layout consistency.
4. **Update [`PROGRESS.md`](./PROGRESS.md) Immediately After Every Step:**
   - Whenever you finish a sub-task (e.g., `1.1.1`), immediately update `[ ]` to `[x]` in [`PROGRESS.md`](./PROGRESS.md), update the `Current Status Summary` table (`Last Completed Task` & `Next Immediate Action`), and add a brief entry in `Session Changelog`. This ensures seamless handoffs across AI sessions until v1.0 release.

