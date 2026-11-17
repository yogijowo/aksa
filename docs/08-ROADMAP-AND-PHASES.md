# 08 — Phased Development Roadmap & Implementation Checklist

This document provides the structured, step-by-step engineering roadmap for building **AKSA**. Future AI coding sessions should execute phases in order and mark completed items (`[x]`).

---

## Phase 1: Project Scaffolding, Clean UI Shell & Core Sidecar Bridge
**Goal:** Establish the monorepo structure, Tauri v2 (Rust) + React 19 + Tailwind v4 + `shadcn/ui` Bahasa Indonesia interface, and Python FastAPI sidecar communication.

- [x] **1.1 Monorepo & Tooling Setup:**
  - Initialize `apps/desktop` (Tauri v2 + React 19 + TypeScript + Vite + Tailwind CSS v4).
  - Initialize `services/engine` (Python 3.12+ managed by `uv`, FastAPI, Uvicorn, WebSockets, SQLite `aiosqlite`, Pydantic v2).
- [x] **1.2 Tauri Rust Core & Sidecar Manager:**
  - Implement `src-tauri/src/sidecar.rs` using `tauri-plugin-shell` to spawn and monitor the Python FastAPI server on a dynamic localhost port with auth token protection.
  - Configure Tauri plugins & native commands (`@tauri-apps/plugin-dialog` for folder selection, `@tauri-apps/plugin-opener` for opening Office files/folders, and `TrayIconBuilder` for System Tray background support).
- [x] **1.3 Core Clean UI Design System (`shadcn/ui` + Bahasa Indonesia):**
  - Set up Obsidian Dark & Warm Light themes, `Inter`/`Geist` typography, and `lucide-react` icons.
  - Build the 3-Pane App Layout: Collapsible Left Sidebar (`Ruang Kerja`, `Tim Agen`, `Pengetahuan RAG`, `Telegram`, `Izin & PC`, `Pengaturan`), Main Workspace Area, and Right Artifact Inspector Drawer.
- [x] **1.4 SQLite Database & Default Indonesian Seed Data:**
  - Implement `db/models.py` creating all tables defined in `07-DATABASE-AND-API-SCHEMA.md`.
  - Seed the default hierarchical team: **"Tim Produktivitas Kantor Indonesia"** (*Manajer Eksekutif*, *Spesialis Administrasi & Office*, *Peneliti Dokumen RAG*, *Operator PC*).

---

## Phase 2: Multi-Model Router, Hierarchical Orchestrator & Token Efficiency
**Goal:** Enable visual creation of multi-level agents (`@xyflow/react`), connect Cloud APIs + Local Ollama/LM Studio, and build the token-efficient orchestration loop.

- [x] **2.1 Unified Multi-Model Router (`core/llm_router.py`):**
  - Integrate Cloud APIs (OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, Groq) via `litellm`.
  - Integrate Local AI auto-discovery and streaming for **Ollama (`localhost:11434`)** and **LM Studio (`localhost:1234`)**.
  - Build the **Pengaturan Model** UI screen with connection testing and Ollama model list/pull support.
- [x] **2.2 Visual Hierarchical Agent Builder UI (`components/agents/`):**
  - Implement the interactive **React Flow (`@xyflow/react`)** canvas with custom `AgentHierarchyNode` cards.
  - Allow adding child sub-agents (`+ Sub-Agen`), assigning distinct models per agent, editing Bahasa Indonesia system prompts, and toggling skill categories.
  - Add a toggle for **Mode Daftar/Organisasi** for users who prefer a simple form over a node canvas.
- [x] **2.3 Hierarchical Execution Engine & Token Optimizer (`core/orchestrator.py` & `token_optimizer.py`):**
  - Implement Root Supervisor task decomposition and `delegate_to_agent` execution (sequential & parallel).
  - Implement **Sub-Agent Context Isolation** (sub-agents run in isolated scratchpads and return compact summaries to the Supervisor).
  - Implement **Dynamic Lazy Tool Loading** and **Rolling Context Compaction**.
  - Stream live execution steps and token savings metrics over WebSocket to the UI.

---

## Phase 3: Workspace Sandbox & 3-Tier PC + Office Execution Engine
**Goal:** Allow agents to safely access user-selected PC folders and create/edit Word, Excel, PowerPoint, PDF files, and control desktop apps like a human.

- [x] **3.1 Workspace Sandbox & Permission Gate (`core/sandbox.py`):**
  - Implement strict `allowed_paths` path validation and automatic `.aksa_backup/` file snapshotting before edits.
  - Implement the **Human-in-the-Loop (HITL) Approval Modal** in the Desktop UI for high-risk actions.
- [x] **3.2 Tier 1 — Native Office & Document Tools (`tools/office/`):**
  - **Excel (`openpyxl`):** Inspect sheets, create styled workbooks, write dynamic formulas (`SUM`, `VLOOKUP`, `IF`), and generate embedded charts.
  - **Word (`python-docx`):** Inspect docs, generate structured Indonesian reports/letters (`Surat Resmi`, `Laporan`, `Proposal`), and fill `.docx` templates (`{{placeholder}}`).
  - **PowerPoint (`python-pptx`):** Generate presentation decks from outlines and data tables.
  - **PDF (`pymupdf` + `reportlab` + `markitdown`):** Token-efficient PDF-to-Markdown extraction, PDF report generation, and merge/split utilities.
- [x] **3.3 Tier 2 — OS Bridge, Live App Control & Self-Extending `uv` Runner (`tools/os_bridge/`):**
  - Implement Windows COM automation (`pywin32` / PowerShell) for live MS Office interaction and macOS `osascript` AppleScript bridge.
  - Implement `run_custom_python_task` using embedded `uv` so agents can write and run custom Python scripts for any specialized PC task.
  - Implement MCP Client support (`tools/mcp/`) for connecting external MCP servers (e.g., Playwright browser automation).
- [x] **3.4 Tier 3 — Visual Computer Use (`tools/computer_use/`):**
  - Implement screen capture (`mss`), OS Accessibility Tree element inspection, and Vision-guided mouse/keyboard automation (`pyautogui`).
  - Add the emergency kill-switch hotkey (`ESC` / `Ctrl+Shift+Q`) and floating on-screen status indicator.

---

## Phase 4: Local Hybrid RAG & Multi-Tier Memory
**Goal:** Enable instant, accurate document search across the user's PC folders without external database servers.

- [x] **4.1 Hybrid Storage Engine (`rag/store.py`):**
  - Set up embedded **LanceDB** for dense vectors and **SQLite FTS5** for exact Indonesian keyword/code matching.
  - Implement **Reciprocal Rank Fusion (RRF)** hybrid search and multilingual embedding support (`fastembed` BGE-M3 / Ollama / Cloud API).
- [x] **4.2 Structure-Aware Ingestion & Folder Watcher (`rag/ingest.py` & `rag/watcher.py`):**
  - Parse `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.csv`, `.md`, `.txt` into clean semantic chunks preserving page numbers and Excel column headers.
  - Implement `watchdog` real-time folder monitoring with `SHA-256` incremental indexing.
- [x] **4.3 Basis Pengetahuan UI & Long-Term Agent Memory:**
  - Build the **Basis Pengetahuan (RAG)** UI view (index status, manual re-index button, live search tester).
  - Implement persistent `user_memories` and workspace `.aksa/MEMORY.md` tools.

---

## Phase 5: Telegram Remote Command Center & Native OS Polish
**Goal:** Connect AKSA to Telegram for mobile remote control and enable direct native OS file handling.

- [x] **5.1 Telegram Gateway (`telegram/bot.py` & `handlers.py`):**
  - Implement `aiogram` v3 long-polling bot service with 6-digit GUI pairing code and numeric `telegram_user_id` whitelist security.
  - Implement live throttled progress message updates, automatic upload of generated Office/PDF files back to Telegram, and incoming file saving to the PC workspace.
  - Implement Indonesian Voice Note transcription (Local Whisper / Groq Whisper API) and inline `[✅ Izinkan]` / `[❌ Tolak]` HITL approval buttons.
- [x] **5.2 Native OS File Opening & Workspace State Persistence:**
  - Cross-platform native application launcher (`POST /api/v1/system/open-path`) for Word, Excel, PowerPoint, and Finder/Explorer.
  - Local SQLite and localStorage workspace persistence across application restarts.

---

## Phase 6: Vector Icon System & Claude Desktop / Linear UI Design
**Goal:** Implement premium, distraction-free aesthetic with dynamic vector icons and zero Unicode emojis.

- [x] **6.1 Dynamic Vector Icon System (`DynamicIcon.tsx`):**
  - Unified dynamic icon mapping with `lucide-react` + `framer-motion` micro-interactions.
  - Eliminated static emoji strings across the entire user interface.

---

## Phase 7: Master Privacy Sanitization & Security Hardening
**Goal:** Remove machine paths, eliminate PII, isolate WebSocket connections, mask API keys, and verify test suites.

- [x] **7.1 Source Sanitization & Dynamic Document Duplication:**
  - Complete removal of developer paths, usernames, and real administrative sample content.
  - Dynamic PyMuPDF + python-docx extraction without hardcoded document templates.
- [x] **7.2 WebSocket Handshake Authentication & Session Channel Isolation:**
  - Token-verified WebSocket connection and per-session event delivery pools.
  - Masked API key display preventing plaintext credential exposure in HTTP responses.
- [x] **7.3 100% Automated Test Suite Verification:**
  - 16/16 backend tests passed; TypeScript + Vite build clean with 0 errors.

---

## 🔮 Future Roadmap (v1.1+)
- [ ] End-to-end encrypted multi-device workspace sync.
- [ ] Role-based access control (RBAC) for team shared workspaces.
- [ ] Native mobile shell companion for iOS & Android.

