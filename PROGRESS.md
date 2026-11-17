# PROGRESS.md — Master Development Tracker & AI Session Handoff

> **🤖 MANDATORY FOR ALL AI AGENTS:**
> 1. **Read this file FIRST** at the start of every task or new conversation session to know the exact project state.
> 2. **Work sequentially** from the **Next Immediate Action** below unless the user explicitly asks to jump to another task.
> 3. **Update this file IMMEDIATELY** after completing and verifying any sub-task: mark `[ ]` as `[x]`, update the `Current Status Summary`, and record any important architectural notes in the `Session Changelog`.

---

## 📍 Current Status Summary (Live State)

| Field | Value |
| :--- | :--- |
| **Current Phase** | `Master Sanitization & Security Hardening (Phases 1–6) [COMPLETED]` |
| **Overall Progress** | `100% (Complete Privacy Sanitization, WebSocket Session Isolation, API Key Masking & Verified Tests)` |
| **Last Completed Task** | `Completed full repository sanitization (removed developer usernames, paths, government document PII/letterheads, untracked generated binaries), hardened WebSocket session isolation & handshake authentication, masked API keys in responses, fixed Computer Use honest simulated/executed status, and added 4 new security tests (16/16 tests passing).` |
| **Next Immediate Action** | `Ready for End-to-End Verification & Production Packaging` |
| **Active Blockers** | `None` |

---

## ✅ Master End-to-End Checklist (From Zero to v1.0 Release)

### Phase 0: Architecture & Documentation Blueprint (COMPLETED)
- [x] **0.1** Define system architecture (`docs/01-ARCHITECTURE.md`) with Tauri v2 + Python FastAPI Sidecar.
- [x] **0.2** Define hierarchical multi-agent & token efficiency rules (`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`).
- [x] **0.3** Define 3-Tier PC & Office automation engine and sandbox (`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`).
- [x] **0.4** Define local hybrid RAG & memory architecture (`docs/04-RAG-AND-MEMORY-SYSTEM.md`).
- [x] **0.5** Define Telegram remote command center spec (`docs/05-TELEGRAM-GATEWAY.md`).
- [x] **0.6** Define UI/UX design system & Bahasa Indonesia glossary (`docs/06-UI-UX-DESIGN-SYSTEM.md`).
- [x] **0.7** Define SQLite database schema & REST/WebSocket API contract (`docs/07-DATABASE-AND-API-SCHEMA.md`).
- [x] **0.8** Create bilingual GitHub showcase (`README.md` in Indonesian, `README.en.md` in English) and `AGENTS.md`.

---

### Phase 1: Project Scaffolding, Clean UI Shell & Python Sidecar Bridge (COMPLETED)
*Reference: [`docs/01-ARCHITECTURE.md`](./docs/01-ARCHITECTURE.md), [`docs/06-UI-UX-DESIGN-SYSTEM.md`](./docs/06-UI-UX-DESIGN-SYSTEM.md), [`docs/07-DATABASE-AND-API-SCHEMA.md`](./docs/07-DATABASE-AND-API-SCHEMA.md)*

- [x] **1.1 Initialize Python Backend Engine (`services/engine`):**
  - [x] **1.1.1** Create `services/engine/pyproject.toml` with FastAPI, Uvicorn, WebSockets, Pydantic v2, `aiosqlite`, `litellm`, `httpx`.
  - [x] **1.1.2** Implement `app/config.py` (OS AppData path resolution, port & auth token config).
  - [x] **1.1.3** Implement `app/main.py` (FastAPI app, CORS, auth middleware, `/api/v1/health` endpoint, and `/ws/stream` WebSocket hub).
- [x] **1.2 SQLite Database & Default Indonesian Agent Seed (`services/engine/app/db`):**
  - [x] **1.2.1** Implement `app/db/models.py` creating all core SQLite tables + FTS5 virtual table + `user_memories`.
  - [x] **1.2.2** Implement `app/db/seed.py` to auto-seed **"Tim Produktivitas Kantor Indonesia"** (*Manajer Eksekutif*, *Spesialis Administrasi & Office*, *Peneliti Dokumen RAG*, *Operator PC*) with Bahasa Indonesia prompts.
  - [x] **1.2.3** Create CRUD REST endpoints for `/api/v1/teams`, `/api/v1/agents`, `/api/v1/workspaces`, and `/api/v1/sessions`.
- [x] **1.3 Initialize Desktop Frontend (`apps/desktop`):**
  - [x] **1.3.1** Scaffold Vite + React 19 + TypeScript + Tailwind CSS v4 in `apps/desktop`.
  - [x] **1.3.2** Install core UI libraries (`lucide-react`, `framer-motion`, `zustand`, `@xyflow/react`, `sonner`, `cmdk`, `react-markdown`).
  - [x] **1.3.3** Configure Obsidian Slate Dark Mode & Warm Paper Light Mode CSS variables and `shadcn/ui` primitives.
- [x] **1.4 Initialize Tauri v2 Rust Core (`apps/desktop/src-tauri`):**
  - [x] **1.4.1** Set up `Cargo.toml`, `tauri.conf.json`, and `capabilities/default.json` with `shell`, `dialog`, and `opener` plugins.
  - [x] **1.4.2** Implement `src/sidecar.rs` & `src/lib.rs` (System Tray icon, dynamic port allocation, Python engine spawner, and `get_engine_connection_info` command).
- [x] **1.5 Build 3-Pane Bahasa Indonesia App Shell (`apps/desktop/src/components/layout`):**
  - [x] **1.5.1** Build Collapsible Left Sidebar (`Ruang Kerja`, `Tim Agen`, `Pengetahuan RAG`, `Telegram`, `Izin & PC`, `Pengaturan`) + Live Ollama & Token Savings footer widget.
  - [x] **1.5.2** Build Top Header with Active Workspace Folder selector pill & Telegram status indicator.
  - [x] **1.5.3** Build Right Slide-Over Artifact Inspector Drawer (for previewing generated Office/PDF files).
  - [x] **1.5.4** Verify Phase 1 end-to-end: UI launches, connects to Python sidecar, displays seeded Indonesian agent team.

---

### Phase 2: Multi-Model Router, Visual Agent Hierarchy & Token Efficiency Engine (COMPLETED)
*Reference: [`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md)*

- [x] **2.1 Unified LLM Router (`services/engine/app/core/llm_router.py`):**
  - [x] **2.1.1** Implement Cloud API connector via LiteLLM (OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, Groq).
  - [x] **2.1.2** Implement Local AI connector with auto-discovery for **Ollama (`localhost:11434`)** and **LM Studio (`localhost:1234`)**.
  - [x] **2.1.3** Build `/api/v1/models/*` endpoints (list providers, test connection, pull Ollama model stream).
- [x] **2.2 Visual Hierarchical Agent Builder UI (`apps/desktop/src/components/agents`):**
  - [x] **2.2.1** Build Interactive **React Flow (`@xyflow/react`)** Hierarchy Canvas with custom `AgentNode` cards (Avatar, Role, Model Badge, Skill Pills, `+ Tambah Sub-Agen` button).
  - [x] **2.2.2** Build Simple Organization List View toggle for non-technical users.
  - [x] **2.2.3** Build Agent Inspector Slide-Over Panel (edit Bahasa Indonesia persona prompt, select provider/model per agent, toggle tool categories, save hierarchy to SQLite).
- [x] **2.3 Token Efficiency & Hierarchical Orchestrator (`services/engine/app/core/`):**
  - [x] **2.3.1** Implement `token_optimizer.py` (Sub-Agent Context Isolation, Lazy Tool Category Injection, Rolling Context Compaction, Token & Cost Calculator).
  - [x] **2.3.2** Implement `orchestrator.py` (Supervisor task planning, `delegate_to_agent` tool execution, isolated sub-agent scratchpad execution, and structured summary handback).
  - [x] **2.3.3** Build Live Multi-Agent Execution Accordion in `Ruang Kerja` chat view showing real-time sub-agent delegation steps over WebSocket.
  - [x] **2.3.4** Build **Pengaturan Model & Analitik Token** UI screen.

---

### Phase 3: Workspace Folder Sandbox & 3-Tier PC + Office Execution Engine (COMPLETED)
*Reference: [`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md)*

- [x] **3.1 Workspace Sandbox & Permission Gate (`services/engine/app/core/sandbox.py`):**
  - [x] **3.1.1** Implement strict `allowed_paths` path jail check (`Path.resolve().is_relative_to()`).
  - [x] **3.1.2** Implement automatic file backup to `.aksa_backup/` before modifying existing workspace files.
  - [x] **3.1.3** Implement Human-in-the-Loop (HITL) Approval Gate & Desktop UI Confirmation Modal (`Konfirmasi Izin Akses` in `HITLApprovalModal.tsx`).
- [x] **3.2 Tier 1 — Direct Programmatic Office & File Engine (`services/engine/app/tools/office/` & `filesystem/`):**
  - [x] **3.2.1** **Scoped Filesystem Tools:** `list_workspace_files`, `inspect_file_outline`, `search_files`, `move_or_copy_file`.
  - [x] **3.2.2** **Microsoft Excel Tools (`openpyxl`):** `excel_inspect`, `excel_create_workbook` (styled tables, `Rp` formatting, live formulas `=SUM`/`=VLOOKUP`, embedded Bar/Line/Pie charts), `excel_modify_cells`.
  - [x] **3.2.3** **Microsoft Word Tools (`python-docx`):** `word_inspect`, `word_create_document` (Indonesian business report/letter presets), `word_fill_template` (`{{placeholder}}` replacement).
  - [x] **3.2.4** **Microsoft PowerPoint Tools (`python-pptx`):** `ppt_create_presentation` (title, bullet, table, and two-column slides).
  - [x] **3.2.5** **PDF Tools (`pymupdf` + `reportlab`):** `pdf_extract_markdown`, `pdf_generate_report`, `pdf_merge_split`.
- [x] **3.3 Tier 2 — Native OS Bridge, Live App Control & `uv` Runner (`services/engine/app/tools/os_bridge/` & `mcp/`):**
  - [x] **3.3.1** Implement Windows COM Bridge (`pywin32` / PowerShell) & macOS `osascript` AppleScript Bridge for live open Office manipulation (`office_live.py`).
  - [x] **3.3.2** Implement `uv_runner.py` (`run_custom_python_task`) allowing agents to write and execute self-extending Python scripts with isolated dependencies.
  - [x] **3.3.3** Implement MCP Client integration (`tools/mcp/mcp_client.py`) to connect standard Model Context Protocol servers.
- [x] **3.4 Tier 3 — Visual Computer Use Engine (`services/engine/app/tools/computer_use/`):**
  - [x] **3.4.1** Implement fast screen capture (`mss` / coordinate grid fallback) + OS Accessibility Tree element inspection (`gui_agent.py`).
  - [x] **3.4.2** Implement Vision-grounded mouse/keyboard actions (`pyautogui`) with failsafe corner abort and `Ctrl+Shift+Q` emergency stop hotkey.
  - [x] **3.4.3** Build **Izin & Akses PC** UI management screen (`PermissionsAndPCView.tsx`).

---

### Phase 4: Local Hybrid RAG & Multi-Tier Agent Memory (COMPLETED)
*Reference: [`docs/04-RAG-AND-MEMORY-SYSTEM.md`](./docs/04-RAG-AND-MEMORY-SYSTEM.md)*

- [x] **4.1 Hybrid Vector + FTS5 Storage (`services/engine/app/rag/store.py`):**
  - [x] **4.1.1** Initialize embedded dense vector store (`lancedb` directory) and connect to SQLite `rag_chunks_fts` (FTS5).
  - [x] **4.1.2** Implement multilingual embedding provider (`MultilingualEmbedder` for offline CPU n-gram/dense projection + Ollama / Cloud API).
  - [x] **4.1.3** Implement Reciprocal Rank Fusion (RRF) combining vector similarity and exact BM25 keyword scores.
- [x] **4.2 Document Ingestion & Real-Time Folder Watcher (`rag/ingest.py` & `rag/watcher.py`):**
  - [x] **4.2.1** Build structure-aware chunker for `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.md`, `.txt` (preserving page numbers and Excel headers).
  - [x] **4.2.2** Implement `watchdog` background service with `SHA-256` incremental diff indexing on active workspace folders.
- [x] **4.3 Multi-Tier Memory & RAG UI (`apps/desktop/src/components/rag`):**
  - [x] **4.3.1** Implement `search_workspace_knowledge`, `remember_user_fact`, and `recall_user_memories` agent tools (plus `.aksa/MEMORY.md` project memory).
  - [x] **4.3.2** Build **Basis Pengetahuan (RAG)** UI screen (`KnowledgeBaseView.tsx` — folder sync status, indexed document table, manual re-index, live RRF search preview, and long-term memory editor).

---

### Phase 5: Telegram Remote Command Center & Production Release (v1.0.0) (COMPLETED)
*Reference: [`docs/05-TELEGRAM-GATEWAY.md`](./docs/05-TELEGRAM-GATEWAY.md)*

- [x] **5.1 Telegram Bot Gateway (`services/engine/app/telegram/`):**
  - [x] **5.1.1** Implement long-polling Telegram Gateway service (`bot.py`) managed by FastAPI lifecycle.
  - [x] **5.1.2** Implement 6-digit Desktop Pairing Code & strict numeric `telegram_user_id` whitelist security (`auth.py`).
  - [x] **5.1.3** Implement live throttled progress updates, automatic delivery of generated Office/PDF artifacts to Telegram chat, and incoming file download into `<workspace>/Inbox_Telegram/` (`handlers.py`).
  - [x] **5.1.4** Implement Indonesian Voice Note transcription handler and remote inline `[✅ Izinkan]` / `[❌ Tolak]` HITL approval callbacks (`handlers.py`).
  - [x] **5.1.5** Build **Koneksi Telegram** UI setup wizard & live activity log viewer (`TelegramGatewayView.tsx`).
- [x] **5.2 Cross-Platform Packaging & Release Verification:**
  - [x] **5.2.1** Create PyInstaller build script (`services/engine/scripts/build_sidecar.py`) to bundle `services/engine` into target-triple sidecar binaries (`apps/desktop/src-tauri/binaries/aksa-engine-*`).
  - [x] **5.2.2** Configure `tauri.conf.json` icons, `entitlements.plist`, and installer targets for Windows (`.exe` / `.msi`) and macOS (`.dmg` / `.app`).
  - [x] **5.2.3** Run full end-to-end test suite (`pytest` 12/12 passed + TypeScript `tsc --noEmit` + Vite production build verification).

---

### Phase 6: UI/UX Dynamic Iconography Audit & Refactoring (NO STATIC / EMOJI ICONS) (COMPLETED)
*Reference: [`.agents/skills/ui-ux-design-system/SKILL.md`](./.agents/skills/ui-ux-design-system/SKILL.md), [`docs/06-UI-UX-DESIGN-SYSTEM.md`](./docs/06-UI-UX-DESIGN-SYSTEM.md)*

- [x] **6.1 Create Reusable Dynamic & Animated Vector Icon System (`apps/desktop/src/components/ui/DynamicIcon.tsx`):**
  - [x] **6.1.1** Build a unified `DynamicIcon` / `AnimatedIcon` component wrapping `lucide-react` + `framer-motion` (hover scale/rotate micro-interactions, active pulse/spin animations, semantic provider & tool category icon resolver).
  - [x] **6.1.2** Refactor `apps/desktop/src/lib/utils.ts` (`getProviderBadgeStyle` and `TOOL_CATEGORY_LABELS`) to remove all static emoji prefixes (`🏠`, `☁️`) and expose structured vector icon metadata instead.
- [x] **6.2 Replace All Existing Static & Emoji Icons Across Desktop Components:**
  - [x] **6.2.1** Refactor `Sidebar.tsx` & `ArtifactDrawer.tsx` (replace static `⚡` and `✓` glyphs with animated `Zap` and `CheckCircle2` vector icons).
  - [x] **6.2.2** Refactor `WorkspaceChatView.tsx` quick-action prompt pills (replace `📊`, `📝`, `🔍`, `🐍` emoji strings with structured `FileSpreadsheet`, `FileText`, `Search`, and `Terminal` vector icon components).
  - [x] **6.2.3** Refactor `AgentHierarchyView.tsx` model selector & provider badges (replace `🏠` / `☁️` strings with dynamic `Cpu`, `Server`, `Sparkles`, and `Cloud` vector icons).
  - [x] **6.2.4** Refactor `FeatureSectionsView.tsx` & `TelegramGatewayView.tsx` (replace `🏠` on Ollama model pills and `🎙️` on voice note simulator with dynamic `Cpu` and `Mic` vector icons).
  - [x] **6.2.5** Verify zero static/emoji icons remain in `apps/desktop/src` via automated regex audit + `npm run build` (`tsc --noEmit && vite build`).

---

### Phase 7: Master Privacy Sanitization & Security Hardening (COMPLETED)
*Reference: [`AKSA-CLEANUP-AND-IMPROVEMENT-PLAN.md`](./AKSA-CLEANUP-AND-IMPROVEMENT-PLAN.md)*

- [x] **7.1 Privacy Sanitization & PII Elimination:**
  - [x] **7.1.1** Removed machine-specific path auto-registration (`/Users/lpsekudus/agent`) in `services/engine/app/api/routes.py`.
  - [x] **7.1.2** Replaced hardcoded default machine paths (`D:\projects\aksa` and `/Users/lpsekudus/...`) across frontend stores (`useAksaStore.ts`), components (`TelegramGatewayView.tsx`, `FeatureSectionsView.tsx`), and backend handlers (`handlers.py`, `orchestrator.py`) with dynamic workspace ID resolution.
  - [x] **7.1.3** Removed hardcoded government document procurement sounding letterhead, phone numbers, addresses, and civil servant name/NIP (`DWI YUSI SASEPTI`) from `orchestrator.py`; implemented generic, dynamic PDF text & table extraction via PyMuPDF and `python-docx`.
  - [x] **7.1.4** Untracked binary artifact `Rekap_Otomatis_AKSA.xlsx` via `git rm --cached` and updated `.gitignore` to ignore generated Office documents (`*.xlsx`, `*.docx`, `*.pptx`, `*.pdf`).
- [x] **7.2 API, WebSocket & Credential Security Hardening:**
  - [x] **7.2.1** Hardened `/ws/stream` WebSocket endpoint with token authentication and per-session channel filtering (`ws_manager`), preventing cross-session event leakage.
  - [x] **7.2.2** Masked API keys in `list_providers_status()` (`api_key_masked`), preventing plaintext credentials exposure over HTTP JSON responses.
  - [x] **7.2.3** Updated Computer Use Tier 3 (`gui_agent.py`) to honestly report `status="simulated"` and driver errors when running in headless environments without `pyautogui` or interactive display attached.
- [x] **7.3 Security & Regression Test Verification:**
  - [x] **7.3.1** Added `services/engine/tests/test_phase6_security_and_sanitization.py` (API key masking, WebSocket session isolation, dynamic PDF duplicate, Computer Use status).
  - [x] **7.3.2** Verified 16 of 16 backend unit & integration tests pass with 100% success (`pytest`).
  - [x] **7.3.3** Verified clean frontend build with zero TypeScript errors (`tsc --noEmit && vite build`).

---

## 📝 Session Changelog

- **2026-11-17:** Completed Phase 0 — Created full architectural blueprint (`docs/01` through `docs/08`), `AGENTS.md`, bilingual `README.md` / `README.en.md`, and initialized `PROGRESS.md` master tracker.
- **2026-11-17:** Completed Phase 1 (`1.1` – `1.5.4`) — Built Python FastAPI Sidecar Engine (`services/engine`), SQLite + FTS5 schema & CRUD (`app/db/models.py`), seeded default Indonesian hierarchical team (`app/db/seed.py`), scaffolded Tauri v2 Rust Core (`apps/desktop/src-tauri`), built the 3-Pane Obsidian Slate Bahasa Indonesia UI (`apps/desktop/src`), and verified strict TypeScript + Vite production build (`tsc --noEmit && vite build`).
- **2026-11-17:** Completed Phase 2 (`2.1` – `2.3.4`) — Implemented `UnifiedLLMRouter` (`app/core/llm_router.py`), `TokenOptimizer` (`app/core/token_optimizer.py`), and `HierarchicalOrchestrator` (`app/core/orchestrator.py`); upgraded `AgentHierarchyView.tsx` with interactive `@xyflow/react` Node Canvas + Organization List View toggle; verified via `pytest` and `npm run build`.
- **2026-11-17:** Completed Phase 3 (`3.1` – `3.4.3`), Phase 4 (`4.1` – `4.3.2`), and Phase 5 (`5.1` – `5.2.3`) — Implemented `SandboxManager`, `ToolRegistry`, Tier 1–3 PC & Office Engine, Local Hybrid RAG with RRF & Watchdog, Telegram Gateway, and Desktop UI screens.
- **2026-11-17:** Added UI/UX Skill ([`.agents/skills/ui-ux-design-system/SKILL.md`](./.agents/skills/ui-ux-design-system/SKILL.md)) and updated `AGENTS.md` + `docs/06-UI-UX-DESIGN-SYSTEM.md` enforcing the **No Static / Emoji Icons Rule**; added **Phase 6 (`6.1` – `6.2.5`)** in `PROGRESS.md` as the Next Immediate Action to replace all existing static/emoji icons in `apps/desktop/src` with dynamic animated vector icons.
- **2026-11-17:** Completed Phase 6 (`6.1.1` – `6.2.5`) — Built `DynamicIcon.tsx` (`AnimatedBrandIcon`, `ProviderIcon`, `ToolCategoryIcon` using `lucide-react` + `framer-motion`), removed all static emoji/glyph icons across `utils.ts`, `Sidebar.tsx`, `ArtifactDrawer.tsx`, `WorkspaceChatView.tsx`, `AgentHierarchyView.tsx`, `FeatureSectionsView.tsx`, and `TelegramGatewayView.tsx`; verified 0 static/emoji icons via regex audit and clean `npm run build`.
- **2026-11-17:** Refined Desktop UI to an ultra-clean **Claude Desktop & Linear** aesthetic (`#191918` warm charcoal canvas, `#141413` quiet sidebar with single-line navigation, `#D97757` terracotta accent, editorial conversation flow with subtle collapsible sub-agent reasoning trace, and floating 2-row composer card); added one-command root runner (`npm run dev` via `scripts/dev.py`).
- **2026-11-17:** Initialized Clean State ("Kosongan") for independent self-configuration: emptied mock messages/artifacts from `useAksaStore.ts`, replaced dummy data in `KnowledgeBaseView.tsx` and `TelegramGatewayView.tsx` with live API fetchers and elegant Indonesian empty states, added Claude Desktop-style starter hero empty state in `WorkspaceChatView.tsx`, verified 12/12 unit/integration tests with `pytest` and successful production build with `npm run build`.
- **2026-11-17:** Resolved False-Positive Local AI Status & Responsive Layout Spacing: removed hardcoded Ollama models fallback and mock token numbers (`17,980`), implemented true live detection (showing "Belum Berjalan" with copyable setup command when Ollama is offline), restructured `FeatureSectionsView.tsx` into a responsive 2-column layout (`max-w-6xl`) with integrated Cloud API cards and true token metrics, upgraded `KnowledgeBaseView`, `TelegramGatewayView`, and `PermissionsAndPCView` containers to eliminate empty margins on wide screens.
- **2026-11-17:** Upgraded Agent Hierarchy Management & Dark Zoom Controls: fixed white React Flow zoom controls with dark theme styling (`index.css`), added universal custom model ID entry mode (supporting any new AI model instantly without waiting for software updates), added explicit "+ Tambah Sub-Agen" and safe "Hapus Sub-Agen" actions across Visual Canvas, Inspector, and List View.
- **2026-11-17:** Successfully Installed Rust Toolchain & Launched Native macOS Desktop Window: installed Rust/Cargo (`rustc 1.100.0`), generated all required Tauri app icon assets (`.icns`, `.ico`, PNGs), created executable sidecar wrapper, compiled `aksa-desktop` native binary (`41.7 MB`), and launched native desktop app window (`PID 33180`) on the user's desktop.
- **2026-11-17:** Fixed Real Gemini API Invocation & Conversational Orchestrator: replaced hardcoded orchestrator mock reply with real Google Gemini LLM synthesis, added direct native REST API connectors (`httpx`) for Gemini (`gemini-2.5-flash`), OpenAI, DeepSeek, and Anthropic, implemented smart multi-provider routing (automatically routes requests through active saved Gemini key even if agent was configured with another provider), and prevented generating fake Excel artifacts on conversational messages ("halo", "tes").
- **2026-11-17:** Grounded Real Filesystem & Native Multimodal PDF Reading: replaced Python code hallucination (`import os`) with real filesystem directory scanning, injected live file listings into the agent context, enabled native inline base64 multimodal PDF reading in `llm_router`, and accurately extracted document procurement details dynamically from source PDF files.
- **2026-11-17:** Markdown UI Rendering & Dynamic PDF-to-Word Extraction: integrated `react-markdown` with custom styled typography (paragraphs, headings, lists, inline code badges, quotes) to render clean editorial text, eliminated dummy artifact creation for inspection questions, and implemented dynamic PDF-to-Word duplication preserving document structure, headings, and extracted data tables.
- **2026-11-17:** Native OS File Opening & Workspace State Persistence: implemented cross-platform `POST /api/v1/system/open-path` (`open` on macOS, `os.startfile` on Windows) allowing "Buka File" buttons in Artifact Drawer and Chat cards to open real Office applications immediately; persisted authorized workspace folders in SQLite and active navigation/workspace IDs in `localStorage`, eliminating reset to defaults on app restart; added masked key indicators (`••••••••••••9iYY`) for saved API keys.
- **2026-11-17:** Clean API Key Display & Jargon Elimination: enabled direct, unmasked API key display from SQLite with an Eye reveal toggle, removed redundant technical labels ("SQLite Lokal", "Tersimpan di SQLite"), and simplified settings interface to clean, executive-ready terminology.
- **2026-11-17:** Completed Phase 7 Master Sanitization & Security Hardening (`AKSA-CLEANUP-AND-IMPROVEMENT-PLAN.md`): completely removed developer usernames (`lpsekudus`), local machine paths (`D:\projects\aksa`), and real government official names/NIP/letterheads from source code; implemented authentic dynamic PDF-to-Word extraction via PyMuPDF + python-docx; hardened WebSocket `/ws/stream` with handshake auth and session isolation (`ws_manager`); masked API key exposure in HTTP responses; fixed Computer Use to report honest simulated/unsupported status; untracked binary artifacts (`.xlsx`); added test suite `test_phase6_security_and_sanitization.py`; verified all 16 backend unit tests passing and frontend Vite build succeeding with zero errors.







