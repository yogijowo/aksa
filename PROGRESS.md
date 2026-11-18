# PROGRESS.md — Master Development Tracker & AI Session Handoff

> **🤖 MANDATORY FOR ALL AI AGENTS:**
> 1. **Read this file FIRST** at the start of every task or new conversation session to know the exact project state.
> 2. **Work sequentially** from the **Next Immediate Action** below unless the user explicitly asks to jump to another task.
> 3. **Update this file IMMEDIATELY** after completing and verifying any sub-task: mark `[ ]` as `[x]`, update the `Current Status Summary`, and record any important architectural notes in the `Session Changelog`.

---

## 📍 Current Status Summary (Live State — Section 23.2 Disciplined Tracking)

| Field | Value |
| :--- | :--- |
| **Current Phase** | `Phase 11 — Production-Readiness Remediation & Security Hardening (QC Audit Fixes) [IN_PROGRESS]` |
| **Release Status Classification** | `Beta — All P0 & P1 Remediation Items Verified (QC Audit 2026-11-18 per QC-PRODUCTION-READINESS-FIXES.md)` |
| **Verification Evidence** | `Backend: pytest services/engine/tests -> 72 passed in 14.04s (Python 3.14.2, macOS arm64) | Frontend: npm --prefix apps/desktop run build -> 0 TypeScript/Vite errors | Rust: cargo check -> 0 warnings/errors` |
| **Last Completed Task** | `Completed all P1 High-Priority Remediation items (P1-1 to P1-8). Implemented: P1-1 (Native Tool-Calling & LLM Execution Loop across all providers, CSV to Excel with SUM formula, WebSocket events); P1-2 (Origin/Host allowlist hardening); P1-3 (Constant-time token validation & WebSocket frame auth); P1-4 (Cross-platform native sidecar binary builder scripts/build_sidecar.py and multi-platform CI/CD matrix); P1-5 (Dynamic port & HMAC challenge-response identity verification); P1-6 (Explicit user attachment gate preventing automatic PDF upload on conversational keywords); P1-7 (Hybrid RAG with Lexical N-Gram Projector, Indonesian synonym expansion, atomic file replacement, and SQLite persistent vector chunks recovery); P1-8 (Persistent Telegram whitelist in SQLite table telegram_allowed_users, single-use 6-digit code with 5-minute TTL, and 5-attempt brute-force lockout). Verified with 72/72 automated tests passing.` |
| **Known Limitations** | `1. P2 items pending: Real token metrics calculation, concurrency guards on /orchestrate/execute, and lockfile generation.` |
| **Next Immediate Action** | `Implement P2-1: Real Token Metrics Calculation (replace simulated token savings with real measured provider token usage and documented savings formula).` |
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

### Phase 8: Desktop Intelligence, Application Discovery, Native OS Permissions & Agent Skills (COMPLETED)
*Reference: [`AKSA-SECOND-PASS-REVIEW-AND-OS-INTEGRATION-SKILLS-ROADMAP.md`](./AKSA-SECOND-PASS-REVIEW-AND-OS-INTEGRATION-SKILLS-ROADMAP.md)*

- [x] **8.1 Centralized Execution Policy Gateway & Security Hardening:**
  - [x] **8.1.1** Implemented `ExecutionPolicyGateway` in `services/engine/app/core/sandbox.py` with argument hashing (`compute_canonical_arguments_hash`) and one-time consumption to prevent replay attacks.
  - [x] **8.1.2** Routed all tool invocations through `tool_registry.execute` -> `execution_policy_gateway.execute_tool(...)`.
  - [x] **8.1.3** Removed workspace auto-registration in `GET /workspaces` (strictly read-only endpoint).
  - [x] **8.1.4** Removed `Path.cwd()` fallback in `HierarchicalOrchestrator`, strictly requiring user-selected workspace folders.
  - [x] **8.1.5** Isolated WebSocket session broadcasting by removing empty-subscription leaks.
  - [x] **8.1.6** Hardened Tauri default capabilities (removed `shell:allow-execute` and `shell:allow-spawn`) and applied strict Content Security Policy in `tauri.conf.json`.
- [x] **8.2 Database Schema Extensions (`services/engine/app/db/models.py`):**
  - [x] **8.2.1** Added 10 new SQLite tables: `installed_applications`, `application_adapters`, `os_permission_states`, `permission_grants`, `permission_audit_events`, `skill_sources`, `installed_skills`, `skill_versions`, `skill_capability_requests`, and `mcp_servers`.
  - [x] **8.2.2** Implemented asynchronous CRUD methods in `DatabaseManager` for application discovery, permission tracking, capability grants, and skills lifecycle.
- [x] **8.3 Native Desktop Application Discovery Engine (`services/engine/app/system/app_discovery.py`):**
  - [x] **8.3.1** Implemented Windows application registry scanner (`winreg` across HKLM/HKCU 64-bit and 32-bit views) without administrator elevation.
  - [x] **8.3.2** Implemented running process watcher via `tasklist /FO CSV` (Windows) and `ps -A` (macOS).
  - [x] **8.3.3** Implemented macOS `/Applications` and `~/Applications` `.app` bundle scanner.
  - [x] **8.3.4** Implemented safe application launcher (`launch_application`) with executable path resolution.
  - [x] **8.3.5** Built Desktop Applications UI (`ApplicationsView.tsx` — search, status badges, adapter tags, and launch action).
- [x] **8.4 Native OS Permission Broker & Audit Ledger (`services/engine/app/system/permission_broker.py`):**
  - [x] **8.4.1** Implemented independent tracking of platform OS status vs AKSA user consent grants across 10 capabilities.
  - [x] **8.4.2** Implemented grant revocation and detailed permission audit event logging (`permission_audit_events`).
  - [x] **8.4.3** Upgraded Permission Center UI (`PermissionsAndPCView.tsx`) with live capability matrix and one-click grant revocation.
- [x] **8.5 Computer Use Action Enum Validation (`services/engine/app/tools/computer_use/gui_agent.py`):**
  - [x] **8.5.1** Implemented `ComputerActionType` enum pre-execution validation before calling input drivers.
  - [x] **8.5.2** Ensured accurate reporting of `simulated`, `unsupported`, `blocked`, and `executed` states.
- [x] **8.6 Portable Agent Skills Manager (`services/engine/app/skills/skill_manager.py`):**
  - [x] **8.6.1** Implemented portable `SKILL.md` parser with YAML frontmatter.
  - [x] **8.6.2** Implemented package archive quarantine validation with strict ZIP path traversal (`../`) defense.
  - [x] **8.6.3** Implemented static security script scanner detecting suspicious shell commands, dynamic `eval`/`exec`, and secret theft.
  - [x] **8.6.4** Seeded curated Indonesian office skills catalog installed in *disabled-by-default* state.
  - [x] **8.6.5** Built Keahlian UI screen (`SkillsView.tsx` — curated catalog, installed skills, enable/disable toggle, and uninstall).
- [x] **8.7 Real Model Context Protocol (MCP) Runtime (`services/engine/app/tools/mcp/mcp_client.py`):**
  - [x] **8.7.1** Implemented JSON-RPC 2.0 stdio subprocess communication and schema inspection.
  - [x] **8.7.2** Configured all third-party MCP servers as disabled by default.
- [x] **8.8 Verification & Quality Assurance:**
  - [x] **8.8.1** Added test suite `services/engine/tests/test_phase7_os_integration_and_skills.py` with 7 comprehensive tests.
  - [x] **8.8.2** Verified 23 of 23 pytest test suites passing with 100% success.
  - [x] **8.8.3** Verified clean frontend production bundle with `tsc --noEmit && vite build`.

---

### Phase 9: Enterprise Readiness Master Specification (`AKSA-ENTERPRISE-READINESS-MASTER-SPECIFICATION.md`) [VERIFIED_WINDOWS / TESTED]

- [x] **9.1 P0 Security Blockers Remediation (`VERIFIED_WINDOWS`, `TESTED`):**
  - [x] **9.1.1** Implemented `CredentialVault` (`app/core/credential_vault.py`) using Windows DPAPI (`CryptProtectData`), macOS Keychain, and sealed HMAC-SHA256 vault; added transactional one-time migration scrubbing plaintext `provider_api_keys` from SQLite (`test_p0_credential_vault_and_plaintext_migration`).
  - [x] **9.1.2** Implemented `PrivacyPolicyGate` (`app/core/privacy_gate.py`) with `ProviderMode` (`local_only`, `cloud_by_choice`, `hybrid_with_consent`, `enterprise_managed`) and eliminated all silent local-to-cloud and cross-provider fallbacks (`test_p0_local_only_mode_blocks_cloud_and_prevents_fallback`).
  - [x] **9.1.3** Implemented `DataClassification` (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`) and `DataDisclosureGate`, removing automatic PDF workspace attachments (`test_p0_data_classification_and_no_auto_pdf_attachment`).
  - [x] **9.1.4** Hardened `ExecutionPolicyGateway` (`app/core/sandbox.py`) to actively reject `execution_policy_override`, `skip_approval`, `is_admin`, and `force_allow`, binding one-time `ApprovalGrant`s to canonical SHA-256 argument hashes, session ID, workspace ID, tool version, and expiry (`test_p0_policy_override_rejected_and_approval_binding`).
  - [x] **9.1.5** Hardened `SandboxManager` & `HierarchicalOrchestrator`: removed `workspaces[0]` fallback, blocked UNC network paths (`\\server\share`) and NTFS ADS (`:`), preserved read-only workspace flags, and added `POST /api/v1/workspaces/revoke-all` (`test_p0_workspace_isolation_unc_and_read_only_preservation`).
- [x] **9.2 P1 Sidecar, OS Integration, Skills, MCP & Computer Use Hardening (`VERIFIED_WINDOWS`, `TESTED`):**
  - [x] **9.2.1** Hardened FastAPI middleware (`app/main.py`) and WebSocket hub (`app/api/ws.py`): enforced loopback Host/Origin allowlists, 10 MB body limit, 64 KB WebSocket frame limit, and per-session ownership preventing cross-session subscription hijacking (`test_p1_websocket_cross_session_hijack_and_host_origin_protection`).
  - [x] **9.2.2** Hardened Tauri Rust `SidecarState` (`apps/desktop/src-tauri/src/sidecar.rs`) with dynamic loopback port allocation (`allocate_loopback_port`), 256-bit per-launch token, and child-process `Drop` cleanup (`IMPLEMENTED`).
  - [x] **9.2.3** Removed hardcoded fake fallback apps from `app_discovery.py`, added `launch_status`, `automation_status`, and `confidence` metadata, and enforced honest `not_launchable` failure when `InstallLocation` is empty (`test_p1_app_launcher_verifies_install_location`).
  - [x] **9.2.4** Hardened `AgentSkillsManager` (`app/skills/skill_manager.py`) with zip-bomb (25 MB / 50:1 ratio), symlink, case-collision, and prompt-injection checks, `aksa.skill.yaml` manifest generation, and automatic grant revocation upon uninstall (`test_p1_skill_archive_security_and_uninstall_grant_revocation`).
  - [x] **9.2.5** Hardened `MCPClientManager` (`app/tools/mcp/mcp_client.py`) with `build_isolated_mcp_env` secret scrubbing, full `initialize` -> `notifications/initialized` -> `tools/call` lifecycle, strict JSON-RPC result verification, and `revoke_server` (`test_p1_mcp_isolated_env_and_computer_use_sensitive_window`).
  - [x] **9.2.6** Refactored `gui_agent.py` with `WindowsComputerUseAdapter` and `MacOSComputerUseAdapter`, sensitive window blocking (`1Password`, `Bitwarden`, `KeePass`, `Windows Security`, `Keychain Access`), and precondition/postcondition metadata (`test_p1_mcp_isolated_env_and_computer_use_sensitive_window`).
- [x] **9.3 P2 Observability, Migrations, Governance Docs & CI/CD (`VERIFIED_WINDOWS`, `TESTED`):**
  - [x] **9.3.1** Implemented `StructuredObservabilityManager` (`app/core/observability.py`) with secret/token redaction and `GET /api/v1/system/diagnostics/support-bundle` (`test_p2_observability_redaction_and_support_bundle`).
  - [x] **9.3.2** Added `schema_migrations`, `credentials_metadata`, and `approval_requests` tables with WAL mode and `PRAGMA foreign_keys = ON` in `app/db/models.py`.
  - [x] **9.3.3** Created `SECURITY.md`, `PRIVACY.md`, `SUPPORT.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/PULL_REQUEST_TEMPLATE.md`, and `.github/workflows/{ci.yml,security.yml,release.yml}`.

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
- **2026-11-17:** Brand Identity & Clean GitHub Release Synchronization: designed official geometric monogram logo (`assets/logo.svg`, `docs/assets/logo.svg`), updated high-resolution banners (`assets/banner.svg`, `docs/assets/banner.svg`) broadening capability scope to PC device applications and documents, aligned official acronym **AKSA** (*Asisten Kerja & Sistem Automasi*), and synchronized local clean orphan root commit with GitHub (`origin/main`) resolving the `refusing to merge unrelated histories` divergence. Working tree and remote are 100% up to date.
- **2026-11-17:** Completed Phase 8 Desktop Intelligence, OS Permissions & Agent Skills Roadmap (`AKSA-SECOND-PASS-REVIEW-AND-OS-INTEGRATION-SKILLS-ROADMAP.md`): implemented centralized `ExecutionPolicyGateway` with argument hashing and replay attack prevention; removed workspace auto-registration and cwd fallback; isolated WebSocket sessions; restricted Tauri shell capabilities and defined strict CSP; implemented native Application Discovery (`app_discovery.py` via `winreg` and process watcher); implemented OS Permission Broker (`permission_broker.py`) tracking OS status vs AKSA user consent independently; hardened Computer Use with `ComputerActionType` enum validation; built portable Agent Skills Manager (`skill_manager.py`) with `SKILL.md` parser, archive quarantine path traversal protection, and static code scanner; implemented JSON-RPC 2.0 stdio MCP client (`mcp_client.py`) with disabled-by-default external servers; added `ApplicationsView.tsx` and `SkillsView.tsx` UI screens; added test suite `test_phase7_os_integration_and_skills.py`; verified all 23 backend tests passing with 100% success and frontend Vite build succeeding with 0 TypeScript errors.
- **2026-11-17:** Resolved Pyrefly Diagnostics & Desktop Intelligence Architecture Theme Alignment: fixed `page.get_text` union type error in `orchestrator.py` and `Row | None` type coercion in `models.py` (`_row_to_dict`); integrated the user's **AKSA — Desktop Intelligence Architecture** theme into `WorkspaceChatView.tsx` with interactive cards for *AKSA AI Orchestrator*, *App Intelligence*, *OS Permission Broker*, *External Skill Manager*, *Integration Manager*, and *Native OS Execution Layer*; updated `assets/banner.svg` and `docs/assets/banner.svg` with the new architecture diagram while strictly preserving the Obsidian slate, terracotta `#D97757`, and emerald palette; updated `README.md` and `README.en.md` positioning AKSA as an **AI Desktop Operating Assistant** with matching architecture specifications; verified 23/23 tests pass and production build succeeds cleanly.
- **2026-11-17:** Unified Multi-Provider Models, PC Application Permissions & Dynamic Agent Skills Assignment:
  1. Updated default models across all providers to their latest official 2025/2026 documentation models (Gemini 2.5 Pro/Flash/Flash-Lite/2.0 Flash/1.5 Pro, Claude 3.7 Sonnet/3.5 Sonnet/3.5 Haiku/3 Opus, OpenAI GPT-4.5 Preview/o3-mini/o1/GPT-4o/GPT-4o Mini, DeepSeek V3/R1, Groq Llama 3.3 70B/DeepSeek R1 Distill/Llama 3.1 8B/Qwen 2.5 32B, OpenRouter, and Ollama Qwen 2.5/Coder/Llama 3.3/Llama 3.2/DeepSeek R1 8B/Phi-4/Mistral) in `llm_router.py`, `FeatureSectionsView.tsx`, and `AgentHierarchyView.tsx`.
  2. Upgraded `ApplicationsView.tsx` and `app_discovery.py` to filter non-application system updates/redistributables, show clear Indonesian integration categories (*Otomasi Dokumen Office*, *Navigasi & Analisis Web*, *Penyunting Kode & Teks*, *Komunikasi & Produktivitas*, *Alat Sistem & Utilitas*), display clear authorization status badges (`Diizinkan (Terhubung)` vs `Belum Diizinkan`), and provide 1-click **Hubungkan ke AKSA** / **Putuskan Akses** actions that function seamlessly whether the application is running or closed.
  3. Expanded `CURATED_SKILL_CATALOG` in `skill_manager.py` with 15+ popular open-source agent skills (Anthropic, Microsoft, CrewAI, LangChain, GitHub) available uninstalled by default for 1-click installation in `SkillsView.tsx`, complete with category pills, search bar, and secure disabled-by-default isolation.
  4. Interconnected all configurations into **Tim Agen** (`AgentHierarchyView.tsx`): upgraded the agent inspector panel with 3 dynamic sub-tabs under *Keahlian & Akses Alat (Lazy Tool Loading)* allowing users to assign specific **Authorized PC Applications**, **Installed Agent Skills**, and **Core System Tools** to any individual agent in the team alongside their preferred model.
  5. Verified 23/23 pytest test suites passing (100% success) and clean TypeScript + Vite production bundle (`tsc --noEmit && vite build`).
- **2026-11-17:** Completed Phase 9 Enterprise Readiness Master Specification (`AKSA-ENTERPRISE-READINESS-MASTER-SPECIFICATION.md`) — Implemented P0/P1/P2 controls (`credential_vault.py`, `privacy_gate.py`, `observability.py`, hardened `sandbox.py`, `llm_router.py`, `orchestrator.py`, `app_discovery.py`, `permission_broker.py`, `skill_manager.py`, `mcp_client.py`, `gui_agent.py`, `main.py`, `ws.py`, `sidecar.rs`), created governance & support docs (`SECURITY.md`, `PRIVACY.md`, `SUPPORT.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/workflows/{ci.yml,security.yml,release.yml}`), and verified 33/33 pytest test suites (`test_phase8_enterprise_readiness.py`) + 0 TypeScript build errors on Windows (`VERIFIED_WINDOWS`).
- **2026-11-18:** Started Phase 11 Production-Readiness Remediation & Security Hardening based on `QC-PRODUCTION-READINESS-FIXES.md`. Status updated from premature "Release Candidate" to "Beta — Security Hardening & Remediation in Progress". Tracking prioritized fixes P0 -> P1 -> P2 -> P3.
- **2026-11-18:** Completed all **P0 Critical Release Blockers (`P0-1` – `P0-6`)**:
  1. `P0-1`: Hardened `/system/open-path` with strict sandbox jail, safe extension allowlist, `.app` bundle block, and structured audit logs.
  2. `P0-2`: Integrated Tauri v2 Rust child process management with clean exit hooks, dynamic port & token resolution via `engineConnection.ts`, and universal `apiFetch()` with `X-AKSA-Auth-Token`.
  3. `P0-3`: Inverted security default to production-first; enforced mandatory non-empty auth tokens, constant-time validation (`secrets.compare_digest`), and disabled `/docs` in production.
  4. `P0-4`: Eliminated Gemini `?key=` URL parameter leakage via `x-goog-api-key` header; verified response schemas never expose plaintext secrets.
  5. `P0-5`: Replaced custom crypto with `keyring` (macOS Keychain / Windows Credential Manager) and AES-GCM authenticated fallback; removed CLI subprocess calls to `security` avoiding argv inspection in `ps`.
  6. `P0-6`: Implemented non-colliding file generation (`_generate_non_colliding_path`), multi-PDF prompt disambiguation with Indonesian clarification, real-time size computation (eliminated hardcoded `"42 KB"`), honest failure handling with 0-byte cleanup, and zero artifacts on failed operations.
  Verified with 54/54 automated test suites passing on macOS arm64 and 0 TypeScript build errors.

- **2026-11-18:** Completed all **P1 High-Priority Remediation items (`P1-1` – `P1-8`)**:
  1. `P1-1`: Implemented native LLM tool-calling and execution loop in `UnifiedLLMRouter`, `ToolRegistry`, and `HierarchicalOrchestrator` across Gemini, OpenAI, Anthropic, and Ollama. Added lazy tool loading schemas and dynamic CSV-to-Excel conversion with `=SUM(...)` formulas.
  2. `P1-2`: Hardened Origin/Host allowlists in `main.py`, removing test bypasses in production and blocking malicious origins like `http://test.evil.com` with 403.
  3. `P1-3`: Enforced constant-time token comparison (`secrets.compare_digest`), disabled `/docs` in production, and implemented 3-second initial JSON frame WebSocket authentication.
  4. `P1-4`: Built `scripts/build_sidecar.py` for freezing native binaries across target triples (`aarch64-apple-darwin`, `x86_64-apple-darwin`, `x86_64-pc-windows-msvc`), with automated matrix in GitHub Actions workflows (`release.yml` and `ci.yml`).
  5. `P1-5`: Added challenge-response HMAC identity verification to `/api/v1/health?nonce=...` and integrated webview client validation in `engineConnection.ts`.
  6. `P1-6`: Enforced DataDisclosureGate requiring explicit user attachment selection; verified `"apa kabar?"` attaches zero documents even when PDFs exist in workspace.
  7. `P1-7`: Renamed and documented `LexicalNgramEmbedder`, added Indonesian administrative synonym expansion (`INDONESIAN_SYNONYMS`: "anggaran" <-> "pagu"), implemented crash-safe atomic `.tmp` file replacement, and added SQLite persistent vector chunks table (`rag_vector_chunks`) for automatic disaster recovery.
  8. `P1-8`: Persisted Telegram whitelist in SQLite table `telegram_allowed_users`, implemented single-use 6-digit pairing codes with 5-minute TTL (`_pairing_ttl_seconds = 300`), and enforced 5-attempt brute-force lockout.
  Verified with 72/72 automated tests passing on macOS arm64, 0 TypeScript/Vite errors, and clean cargo check.

---

### Phase 11: Production-Readiness Remediation & Security Hardening (QC Audit Fixes)
*Reference: [`QC-PRODUCTION-READINESS-FIXES.md`](./QC-PRODUCTION-READINESS-FIXES.md)*

#### P0 — Critical (Release Blockers)
- [x] **P0-1** Security Hardening of `/system/open-path` (Sandbox validation, extension allowlist, app bundle reject, audit log)
- [x] **P0-2** Sidecar Lifecycle & Frontend Auth Integration (Spawn sidecar in Rust, pass env token/port, API client token header)
- [x] **P0-3** Default Production Security Mode (Require `--dev` + `AKSA_DEV_MODE=1` for dev, disallow empty auth tokens)
- [x] **P0-4** API Key Exposure & Gemini Query Param Leakage (`x-goog-api-key` header, scrub response schemas & logs)
- [x] **P0-5** Credential Vault Hardening (`keyring` OS store integration, remove plaintext master keys & argv leaks, AES-GCM fallback)
- [x] **P0-6** Safe Document Generation & No-Overwrite (Unique file naming, multi-PDF disambiguation, real size & status reporting)

#### P1 — High Priority
- [x] **P1-1** Native Tool-Calling & LLM Execution Loop (Replace keyword heuristics with LLM function calling & lazy schemas)
- [x] **P1-2** Origin/Host Allow-list Hardening (Remove test bypasses in production mode)
- [x] **P1-3** Constant-Time Token Comparison & WebSocket Frame Auth
- [x] **P1-4** Sidecar Binary Freezing & Distribution Packaging
- [x] **P1-5** Dynamic Port & Engine Connection Discovery
- [x] **P1-6** Explicit User File Attachment & Data-Classification Gate
- [x] **P1-7** Hybrid RAG with Real Embedder & Persistent LanceDB
- [x] **P1-8** Persistent Telegram Whitelist & Single-Use Pairing

#### P2 — Medium Priority
- [ ] **P2-1** Real Token Metrics Calculation (Measured provider usage)
- [ ] **P2-2** Strict Local AI Privacy (Zero cloud fallback for local-only agents)
- [ ] **P2-3** Concurrency Guards & Request Rate Limiting
- [ ] **P2-4** Dependency Pinning & Lockfile Generation
- [ ] **P2-5** Single Source of Truth Settings & Path Normalization
- [ ] **P2-6** Sanitized Global Error Handling
- [ ] **P2-7** Comprehensive Security & E2E Test Suite Expansion

#### P3 — Low Priority
- [ ] **P3-1** Modular Router & Repository Refactoring
- [ ] **P3-2** Frontend Dynamic Code Splitting (<400 KB initial chunk)
- [ ] **P3-3** Honest Documentation Alignment











