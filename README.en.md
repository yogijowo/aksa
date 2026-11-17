<div align="center">

<a href="#-aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# ⚡ AKSA
### Autonomous Hierarchical AI Agent Desktop Platform
*(Asisten Kerja &amp; Sistem Automasi — Local-First PC Automation &amp; Multi-Agent Assistant)*

<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/📄_Baca_dalam-Bahasa_Indonesia-F43F5E?style=for-the-badge" alt="Indonesian Documentation"></a>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11%20%7C%20macOS-10B981?style=for-the-badge" alt="Cross Platform">
  <img src="https://img.shields.io/badge/Desktop-Tauri%20v2%20%2B%20React%2019-0EA5E9?style=for-the-badge" alt="Tauri v2 + React 19">
  <img src="https://img.shields.io/badge/Sidecar-Python%203.12%20%2B%20uv-F59E0B?style=for-the-badge" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Database-SQLite%20FTS5%20%2B%20LanceDB-8B5CF6?style=for-the-badge" alt="Hybrid RAG">
</p>

<p align="center">
  <b>Your private, local executive assistant running directly on your PC.</b><br>
  Operates inside local workspaces, automates desktop applications and system workflows, crafts analytical documents and spreadsheets, indexes hundreds of files instantly, and responds to remote commands via Telegram on your smartphone.
</p>

[Key Features](#-key-features) • [How It Works](#-how-aksa-works-on-your-pc) • [System Architecture](#️-system-architecture) • [Quickstart Guide](#-quickstart-guide) • [Security & Privacy](#-local-first-security--privacy) • [Engineering Docs](#-engineering-docs--architectural-specs)

</div>

---

## 🌟 Why AKSA?

Most AI tools today are web chatbots isolated from your local desktop applications and files. When you need to create an official document, run a system routine, or analyze complex data across applications, you end up manually copy-pasting data, re-formatting paragraphs, and managing files yourself.

**AKSA (Asisten Kerja & Sistem Automasi)** was built from day one as a **local-first autonomous desktop application platform** with real execution capabilities across authorized applications and folders on your computer:

1. **PC Application & Document Automation:** Beyond conversational suggestions, AKSA interacts with local software and generates complete production files: **Microsoft Excel (`.xlsx` with dynamic formulas and charts)**, **Microsoft Word (`.docx` with executive templates)**, **PowerPoint (`.pptx`)**, and **PDF** reports.
2. **Zero-Setup Local Hybrid RAG:** Instantly searches thousands of PDF pages, policies, and spreadsheets with semantic understanding and exact keyword matching—100% locally with zero external database servers.
3. **Remote Control via Telegram:** Commuting or away from your desk? Send a text or **voice note** to your private Telegram Bot. AKSA runs the task on your PC and uploads the finished document directly back to your phone.
4. **Extreme Token Efficiency:** Saves up to **80%** in API costs using sub-agent context isolation, lazy tool loading, and rolling compaction.

---

## ✨ Key Features

### 🕸️ 1. Visual Hierarchical Multi-Agent Builder
* **Executive Team Structure:** Design your digital workforce featuring a **Manager/Supervisor Agent** coordinating specialized sub-agents (Office Specialist, RAG Document Researcher, PC & Screen Operator) via an interactive node canvas (`@xyflow/react`) or structured organization chart.
* **Per-Agent Model Assignment (Cloud APIs + 100% Free Local AI):**
  * Assign frontier **Cloud Models** (Claude 3.7 Sonnet, Gemini 2.5 Pro, GPT-4o, DeepSeek V3) to the Manager Agent for strategic reasoning.
  * Assign **100% Free & Private Local Models** via **Ollama** or **LM Studio** (Qwen 2.5, Llama 3.3, DeepSeek R1) to sub-agents for confidential document analysis, ensuring sensitive records never leave your machine.

### 💻 2. 3-Tier PC & Office Action Engine with Workspace Sandbox
* **Workspace Sandbox Path Jail:** Agents can only access and modify files inside user-authorized folders (e.g. `D:\Work\Reports_2026`). Attempts to traverse outside are automatically blocked at the engine layer.
* **Human-in-the-Loop (HITL) Permission Gate:** High-risk system actions (script execution, file deletion, visual computer use) require explicit user approval via a desktop modal or interactive Telegram buttons (`[✅ Allow]` / `[❌ Deny]`).
* **3-Tier Execution Layers:**
  * **Tier 1 (Direct Office Engine):** Programmatic file creation using native libraries (`openpyxl`, `python-docx`, `python-pptx`, `pymupdf`).
  * **Tier 2 (Native OS Bridge & uv Runner):** Real-time interaction with open Office windows (Windows COM / macOS AppleScript), isolated Python script execution via `uv`, and Model Context Protocol (MCP) clients.
  * **Tier 3 (Visual Computer Use):** Screen inspection, mouse navigation, and keyboard typing for legacy software without APIs, equipped with Failsafe Corner Abort and emergency hotkey `Ctrl+Shift+Q`.

### ⚡ 3. Intelligent Token Optimization (Up to 80% Cost Reduction)
* **Sub-Agent Context Isolation:** Sub-agents analyze bulky documents and scratchpads in isolated sessions, returning only concise executive summaries and generated file paths to the Manager Agent.
* **Lazy Tool Loading:** Injects only the tool definitions required for an agent's active domain, keeping context windows lightweight.
* **Rolling Compaction:** Automatically condenses long conversation turns while retaining critical facts and project decisions.

### 📚 4. Zero-Setup Local Hybrid RAG
* **Semantic Vector + BM25 Exact Keyword Search:** Combines **LanceDB** (semantic vectors) and **SQLite FTS5** (exact matching for reference numbers, codes, and IDs) using Reciprocal Rank Fusion (RRF).
* **Watchdog Folder Monitor:** Detects new or modified PDFs, spreadsheets, and Word documents in authorized folders, incrementally re-indexing them in the background using SHA-256 hashing.

### 📱 5. Telegram Remote Command Center
* **Control Your PC from Anywhere:** Send work instructions, upload reference documents, or speak naturally with **Voice Notes** from your smartphone.
* **Instant File Delivery:** Receives live step-by-step progress updates and finished files (`.docx`, `.xlsx`, `.pdf`, screenshots) directly in your Telegram chat.
* **Strict Whitelist & Pairing Security:** Only authorized Telegram user IDs verified with a 6-digit desktop pairing code can interact with the bot.

### 🖥️ 6. Native Desktop Discovery, OS Permissions & Portable Agent Skills
* **Zero-Elevation Application Inventory:** Safely discovers installed desktop applications (Office suites, browsers, IDEs) and automation adapters without requiring administrative privileges.
* **OS-Level Permission Broker:** Independently tracks native operating system permissions (Accessibility, Screen Recording, filesystem ACLs) versus AKSA user consent grants with audit event logs.
* **Standard Agent Skills (`SKILL.md`):** Extends agent workflows using the standard portable format with quarantine extraction validation, static code scanning, and disabled-by-default activation.

---

## 🚀 How AKSA Works on Your PC

```text
                                  +---------------------------------------+
                                  |         USER / OPERATOR               |
                                  |   (Desktop UI / Telegram Smartphone)  |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |        EXECUTIVE MANAGER (AI)         |
                                  |     (Supervisor Graph Orchestrator)   |
                                  +-------------------+-------------------+
                                                      |
                  +-----------------------------------+-----------------------------------+
                  |                                   |                                   |
                  v                                   v                                   v
      +-----------------------+           +-----------------------+           +-----------------------+
      |   Office & Document   |           |    Local Hybrid RAG   |           |      PC & Screen      |
      |      Specialist       |           |   Document Researcher |           |     Operator Agent    |
      +-----------+-----------+           +-----------+-----------+           +-----------+-----------+
                  |                                   |                                   |
                  v                                   v                                   v
      +-----------------------+           +-----------------------+           +-----------------------+
      |        TIER 1         |           |      HYBRID RAG       |           |     TIER 2 & TIER 3   |
      | Excel, Word, PPT, PDF |           | LanceDB + SQLite FTS5 |           | Win32 COM, uv, Visual |
      +-----------------------+           +-----------------------+           +-----------------------+
                  |                                   |                                   |
                  +-----------------------------------+-----------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |         WORKSPACE SANDBOX             |
                                  |    (User-Authorized PC Folder)        |
                                  +---------------------------------------+
```

---

## 🏗️ System Architecture

AKSA combines a **Native Desktop Shell (Tauri v2)** with an **Asynchronous Python FastAPI Sidecar**:

* **Desktop Frontend (`apps/desktop`):** Built with **Tauri v2 (Rust)**, **React 19**, **TypeScript**, and **Tailwind CSS v4**. Delivers instant startup, ultra-low RAM footprint (~40–80 MB), system tray support, and a distraction-free aesthetic inspired by *Linear* and *Claude Desktop*.
* **Core Sidecar Engine (`services/engine`):** Runs locally on `127.0.0.1:43120` using Python 3.12+ managed by `uv`. Orchestrates multi-agent execution graphs, LiteLLM router, LanceDB + SQLite FTS5 search, and asynchronous Telegram bot services (`aiogram` v3).

---

## 💻 Quickstart Guide

### 1. Prerequisites
Ensure your machine has:
* **Node.js:** v20.x or v22.x LTS ([Download](https://nodejs.org/))
* **Python:** v3.12+ with [uv](https://docs.astral.sh/uv/)
* **Rust:** Latest stable toolchain ([rustup.rs](https://rustup.rs/)) — *required for compiling native Tauri binaries*
* **Ollama (Optional):** For 100% free local models ([ollama.ai](https://ollama.ai/))

### 2. Clone Repository & Install
```bash
# Clone the repository
git clone https://github.com/yogijowo/aksa.git
cd aksa

# Install frontend dependencies
npm --prefix apps/desktop install

# Set up Python virtual environment with uv
uv venv services/engine/.venv
uv pip install -r services/engine/pyproject.toml --project services/engine
```

### 3. Run in Development Mode (One Command)
```bash
# Launch Desktop Web & Backend Sidecar concurrently
python scripts/dev.py

# Or launch as a Native Tauri v2 Desktop Window
python scripts/dev.py --tauri
```
The application will automatically launch on `http://localhost:5173` or open a native desktop application window.

### 4. Run Automated Test Suite
```bash
# Backend Unit & Integration Tests (23 comprehensive test suites)
uv run --project services/engine pytest services/engine/tests -v

# Frontend TypeScript Check & Production Build
npm --prefix apps/desktop run build
```

---

## 🔒 Local-First Security, Privacy & Model Transparency

AKSA is architected on strict **Local-First Data Sovereignty**:
* **Zero Third-Party Telemetry:** No conversation records, document contents, or file indices are transmitted to developer servers.
* **Transparent Processing Model:**
  * **Local Models (Ollama / LM Studio):** 100% of reasoning, prompt processing, and RAG hybrid search runs completely offline on your own machine.
  * **Cloud Models (Gemini, OpenAI, Anthropic, DeepSeek):** When you select a cloud provider and supply your own API key, request data and referenced files are dispatched directly over HTTPS only to your chosen provider's official API endpoints.
* **Protected Credential Storage:** API keys are stored in the user's local SQLite database and strictly masked in the UI and HTTP API responses (`••••••••••••9iYY`).
* **Session-Isolated WebSockets:** Real-time agent streaming events are isolated by session ID, preventing cross-window or cross-client data leakage.
* **OS-Level Capability Broker & Sandbox Folders:** Filesystem operations are confined to explicitly authorized workspace directories (`allowed_paths`). High-risk operations (command execution, GUI automation) require human confirmation (Human-in-the-Loop).

---

## 📚 Engineering Docs & Architectural Specs

Comprehensive engineering blueprints and guidelines for contributors and AI agents are maintained in [`AGENTS.md`](./AGENTS.md) and the [`docs/`](./docs/) directory:

* 🤖 [**`AGENTS.md`**](./AGENTS.md) — Coding conventions, bilingual rules, and monorepo structure.
* 🏛️ [**`docs/01-ARCHITECTURE.md`**](./docs/01-ARCHITECTURE.md) — Tauri v2 IPC protocols, sidecar lifecycle, and bundling specs.
* 🧠 [**`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`**](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md) — Hierarchical orchestration and the 5 token optimization algorithms.
* 💻 [**`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`**](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md) — 3-Tier PC Action Engine and Human-in-the-Loop sandbox.
* 📚 [**`docs/04-RAG-AND-MEMORY-SYSTEM.md`**](./docs/04-RAG-AND-MEMORY-SYSTEM.md) — Hybrid LanceDB + SQLite FTS5 RRF search engine.
* 📱 [**`docs/05-TELEGRAM-GATEWAY.md`**](./docs/05-TELEGRAM-GATEWAY.md) — Telegram remote gateway, pairing protocols, and voice transcription.
* 🎨 [**`docs/06-UI-UX-DESIGN-SYSTEM.md`**](./docs/06-UI-UX-DESIGN-SYSTEM.md) — Claude Desktop / Linear aesthetic guidelines and UI glossary.
* 🗄️ [**`docs/07-DATABASE-AND-API-SCHEMA.md`**](./docs/07-DATABASE-AND-API-SCHEMA.md) — SQLite schema and REST/WebSocket API contracts.
* 🗺️ [**`docs/08-ROADMAP-AND-PHASES.md`**](./docs/08-ROADMAP-AND-PHASES.md) — Engineering roadmap and milestone tracking.

---

## 📄 License

AKSA is distributed under the **[MIT License](./LICENSE)**. Free for personal, commercial, and open-source use.
