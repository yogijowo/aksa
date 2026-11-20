<div align="center">

<a href="#aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# AKSA
### Asisten Kerja &amp; Sistem Automasi — AI Desktop Operating System &amp; Digital Headquarters
*(Hierarchical Multi-Agent Team, Distributed Server-Client Topology, Office Engine, Autonomous Scheduler &amp; Enterprise Security Baseline)*

<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/Baca_dalam-Bahasa_Indonesia-D97757?style=for-the-badge" alt="Indonesian Documentation"></a>
  <img src="https://img.shields.io/badge/Current_Version-v0.0.2_(Pre--Beta_Alpha)-3B82F6?style=for-the-badge" alt="Current Version v0.0.2">
  <img src="https://img.shields.io/badge/Status-Phase_37_Active-F59E0B?style=for-the-badge" alt="Phase 37 Active">
  <img src="https://img.shields.io/badge/Security_Audit-Cycle_14_Passed_100%25-10B981?style=for-the-badge" alt="Security Audit Cycle 14">
  <img src="https://img.shields.io/badge/GUI-Windows_%7C_macOS_%7C_Linux-21211F?style=for-the-badge" alt="Desktop GUI">
  <img src="https://img.shields.io/badge/CLI_&_Server-Linux_Headless_Daemon-21211F?style=for-the-badge" alt="Linux CLI Headless">
  <img src="https://img.shields.io/badge/Mobile_Client-Roadmap_Android_&_iOS-21211F?style=for-the-badge" alt="Mobile Client Roadmap">
  <img src="https://img.shields.io/badge/Tests-325_Passed-10B981?style=for-the-badge" alt="325 Tests Passed">
</p>

<p align="center">
  <b>A local-first sovereign AI Operating System that runs directly on your hardware — supporting a distributed Server-Client architecture (Native Desktop GUI for Windows/macOS/Linux, Headless 24/7 CLI Linux Server, and upcoming Dedicated Mobile Clients for Android &amp; iOS) — featuring hierarchical autonomous agents, real Office document automation, an extensible omni-channel remote gateway, and 100% local privacy isolation.</b><br>
  AKSA connects leading AI models (cloud APIs and 100% offline local SLMs) to your actual work files, spreadsheets, recurring routines, and desktop applications without ever leaking confidential data or executing risky actions without your explicit Human-in-the-Loop consent.
</p>

[Vision & Future Direction](#-vision-what-aksa-will-become) • [Current Position & Maturity Score](#-current-position-status--maturity-score-v002) • [Server & Client Topology](#-server-and-client-topology-aksa-server--dedicated-clients) • [Omni-Channel Remote Gateway](#-omni-channel-remote-command-gateway) • [Core Capabilities & Architectural Innovations](#-core-capabilities--architectural-innovations) • [Key Features](#-key-features) • [Phased Engineering Roadmap](#-phased-engineering-roadmap) • [Quickstart Guide](#-quickstart-guide) • [Technical Documentation](#-technical--governance-documentation)

<br>

<img src="./docs/assets/desktop.webp" alt="AKSA Desktop Interface — Hierarchical Multi-Agent Team Builder" width="100%">

</div>

---

## 🏛️ Vision: What AKSA Will Become

Most current AI assistants are passive browser chat windows disconnected from your local files and operating workflows. In contrast, unrestricted computer agents risk breaking operating systems or leaking sensitive documents.

**AKSA is engineered to be your Sovereign Digital Headquarters & Autonomous Co-Worker:**

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AKSA DIGITAL HEADQUARTERS                             │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│     VIRTUAL OFFICE      │  AUTONOMOUS SCHEDULER   │   ECOSYSTEM CONNECTORS  │
│  (Visual Office Canvas) │    & HITL RECURRING     │  (Cloud & Social Media) │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Interactive 2.5D visual │ Executes recurring tasks│ Native integrations for │
│ office floor plan;      │ (Cron & natural language│ Google Workspace (Drive,│
│ agents type at desks,   │ prompts) guarded by     │ Docs, Sheets, Calendar, │
│ collaborate in meetings,│ multi-channel approvals │ Gmail) & social channels│
│ or wave for permission. │ (Desktop, Mobile, Chat).│ (LinkedIn, X, Meta).    │
├─────────────────────────┴─────────────────────────┴─────────────────────────┤
│                          LOCAL EXECUTION ENGINE                             │
│  • Real Office Automation (Excel formulas & charts, Word contracts, PPT)    │
│  • Server-Client Topology: Desktop GUI, Linux Headless Server, Mobile App   │
│  • Path Jail Sandbox & Automated File Backups (.aksa_backup/)               │
│  • Multi-Model Router (Gemini, Claude, GPT, DeepSeek, Ollama, LM Studio)    │
│  • 100% Local Privacy (Zero Silent Cloud Fallback & DPAPI/Keyring Vault)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **A Visual Co-Worker, Not Just a Chatbot:** Users can observe a 2.5D virtual office where agents actively work at desks, collaborate in conference rooms, or raise their hand when Human-in-the-Loop permission is required.
2. **Proactive Scheduled Autonomy:** Instruct AKSA once (*"Every Monday at 8 AM, aggregate last week's sales reports, build a PowerPoint slide deck, and prepare an email draft"*), and AKSA executes precisely on time with multi-channel confirmation.
3. **Flexible Architecture: Dedicated Server & Clients:** The AKSA Core Server can run locally on an office workstation or 24/7 on a private Linux VPS, accessible via native desktop GUIs, dedicated mobile clients (iOS/Android), and secure remote chat gateways.
4. **Absolute Privacy Sovereignty:** 100% local-first. Your private data is never used for external model training, and local SLMs (Ollama / LM Studio) operate entirely offline.

---

## 📊 Current Position, Status & Maturity Score (v0.0.2)

### Honest Status Disclosure
* **Current Phase:** **Phase 37 — Pre-Beta Alpha (Version 0.0.2)**.
* **Maturity Level:** Core architecture, multi-agent orchestration, and security baselines are 100% verified. However, this is **not yet released as general production (not v1.0.0)** and is currently undergoing internal private verification before Public Beta (v0.1.0).
* **Transparent Limitations:**
  1. *External Usability Testing:* Live testing with 5 external non-technical participants (Usability Testing Section 14) is officially documented as *"not yet conducted with live humans"*.
  2. *Upcoming Features Status:* Virtual Office (Pillar 1), Autonomous Scheduler (Pillar 2), Ecosystem Connectors (Pillar 3), and Dedicated Mobile Clients are fully specified in our architectural PRD ([`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) and [`ROADMAP.md`](./ROADMAP.md)) and are scheduled for implementation in Phases 38+.

### Real Verification Scores & Maturity Metrics

| Evaluation Dimension | Score / Metric | Status | Verification Evidence |
| :--- | :---: | :---: | :--- |
| **Security Audit & OS Integrity** | **100% Passed** | Verified | Passed 14 independent re-audit cycles ([`docs/AKSA — Independent Re-Audit Siklus 14.md`](./docs/AKSA%20—%20Independent%20Re-Audit%20Siklus%2014.md)). Zero-trust sidecar handshake, DPAPI/Keychain vault, canonical path jail, and bound anti-replay HITL tokens. |
| **Backend Test Suite (Python Pytest)** | **291 Passed** / 4 Skipped | Verified | 291 scenarios pass cleanly on the engine (4 OS-specific sandbox tests skipped on macOS runner). |
| **Frontend Test Suite (React Vitest)** | **16 Passed** (100%) | Verified | Zustand store unit tests, initial database hydration, and sidecar identity verification pass in 1.1s. |
| **Desktop Shell Integrity (Tauri v2 Rust)** | **18 Passed** (100%) | Verified | `cargo check` and `cargo test` pass with zero errors on native host targets. |
| **TypeScript & Vite Production Bundle** | **0 Errors** (Clean) | Verified | `tsc --noEmit && vite build` completes in 2.5s with optimized code chunks. |
| **Supply Chain Dependency Audit** | **0 Vulnerabilities** | Verified | `npm audit --omit=dev --audit-level=high` reports zero critical or high vulnerabilities. |
| **Token Efficiency & Budget Guard** | **28% – 80% Saved** | Verified | Significant API cost reduction via Sub-Agent Context Isolation, dynamic lazy tools, and rolling context compaction. |

---

## 🌐 Server and Client Topology: AKSA Server & Dedicated Clients

AKSA decouples host execution from client interfaces through a distributed topology:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DISTRIBUTED SERVER-CLIENT TOPOLOGY                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌───────────────────────────┐             ┌─────────────────────────┐    │
│    │    AKSA DESKTOP CLIENT    │             │   AKSA MOBILE CLIENT    │    │
│    │ (Tauri v2 + React 19 GUI) │             │  (Roadmap: iOS/Android) │    │
│    │ • Windows, macOS, Linux   │             │ • Biometric One-Tap HITL│    │
│    │ • Visual Office Canvas    │             │ • Real-time Monitoring  │    │
│    └─────────────┬─────────────┘             └────────────┬────────────┘    │
│                  │                                        │                 │
│                  │        Encrypted TLS / Local E2EE      │                 │
│                  └───────────────────┬────────────────────┘                 │
│                                      │                                      │
│                                      ▼                                      │
│               ┌──────────────────────────────────────────────┐              │
│               │               AKSA CORE SERVER               │              │
│               │ (Python FastAPI + SQLite + LLM Router + OS)  │              │
│               │ • Core Engine: Office, RAG, Sandbox, Rules   │              │
│               │ • Runs on Local PC, Homelab, or Private VPS  │              │
│               │ • 24/7 Headless Linux Server / CLI Mode      │              │
│               └──────────────────────┬───────────────────────┘              │
│                                      │                                      │
│                   ┌──────────────────┴──────────────────┐                   │
│                   ▼                                     ▼                   │
│     ┌───────────────────────────┐         ┌───────────────────────────┐     │
│     │   OMNI-CHANNEL GATEWAY    │         │    ECOSYSTEM CONNECTORS   │     │
│     │ (Multi-Platform Messaging)│         │ (Google Workspace, Social)│     │
│     └───────────────────────────┘         └───────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **AKSA Core Server (Autonomous Host Engine):**
   * The central computing engine built on Python FastAPI, SQLite, and isolated sandboxing. Handles multi-agent orchestration, Office generation, hybrid RAG, cron scheduler, and audit logging.
   * Can be run locally on your desktop workstation (Windows, macOS, Linux) or deployed as a 24/7 headless background service on Linux servers, homelabs, VPS, or Docker containers without requiring a graphical display server.
2. **AKSA Desktop Client (Windows, macOS, Linux):**
   * Native visual application (Tauri v2 + React 19) securely communicating with local or distributed AKSA Core Servers.
   * Features the 2.5D Virtual Office Canvas, interactive agent hierarchy builder (@xyflow/react), and artifact drawers.
3. **AKSA Mobile Client (Roadmap: Android & iOS):**
   * Dedicated native mobile companion app providing a pocket command center:
     * Real-time monitoring of virtual office activities and agent states.
     * Instant one-tap Human-in-the-Loop (HITL) approvals backed by biometric hardware authentication (fingerprint / FaceID).
     * Voice dictation and mobile task delegation while on the move.

---

## 📡 Omni-Channel Remote Command Gateway

AKSA does not restrict remote interaction to a single app. It features an extensible **Omni-Channel Remote Gateway** with a modular adapter architecture:

1. **Modular Adapter Layer:**
   * Built on an abstract messaging interface capable of bridging with any secure modern chat or webhook platform (Telegram, WhatsApp Business API / Baileys, Discord Webhooks, Slack, Matrix, or corporate webhooks).
2. **Telegram as an Out-of-the-Box Reference Adapter:**
   * Telegram currently serves as our verified reference adapter, secured with a 6-digit GUI pairing code and strict numeric account whitelisting.
3. **Comprehensive Remote Autonomy:**
   * Issue instructions via natural text or voice notes, upload workspace documents directly from your phone, receive finished Office outputs, and approve high-risk actions through interactive inline buttons from anywhere in the world.

---

## ⚡ Core Capabilities & Architectural Innovations

AKSA incorporates nine strategic architectural capabilities engineered for an autonomous enterprise operating system:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 CORE CAPABILITIES & ARCHITECTURAL INNOVATIONS               │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│   1. VOICE-TO-ACTION    │   2. DATA & DOC DOCTOR  │   3. SMART SCANNER OCR  │
│  Ambient Audio Briefing │  Self-Healing Documents │ Receipts -> Excel Sheet │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Local voice dictation   │ Detects & repairs broken│ Scans invoice/receipt   │
│ via Whisper; AKSA reads │ Excel formulas (#REF!,  │ images into structured  │
│ daily briefings aloud   │ #DIV/0!) and corrupted  │ spreadsheets & audit    │
│ completely hands-free.  │ tabular data.           │ ledger entries.         │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│   4. DEEP WORK SHIELD   │   5. P2P MESH SYNC      │  6. AUDIT COMPLIANCE    │
│ Focus Guard Throttling  │ Cloudless P2P Sync      │ Tamper-Proof Hash Chain │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Queues non-urgent       │ Encrypted peer-to-peer  │ Records every file edit │
│ interruptions while you │ sync between work PC,   │ and HITL grant into a   │
│ write or code; delivers │ home Mac, & Linux server│ verifiable cryptographic│
│ a digest when you finish│ with zero cloud storage.│ ledger for compliance.  │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│   7. VIRTUAL OFFICE     │ 8. AUTONOMOUS SCHEDULER │  9. DYNAMIC MCP PLUGINS │
│ 2.5D Visual Agent Floor │ Proactive Recurring Cron│ Hot-Reloading MCP Tools│
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Agents visualized typing│ Runs recurring tasks    │ Dynamically extends     │
│ at desks, meeting, and  │ with multi-channel      │ tool capabilities       │
│ gesturing for HITL auth.│ confirmation gates.     │ without server restarts.│
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

1. **Voice-to-Action & Ambient Executive Audio Briefing (Whisper & Piper TTS Local):**
   * Dictate tasks directly through your microphone using local Whisper (100% offline, zero cloud leakage).
   * AKSA reads aloud hands-free executive briefings in natural speech while you prepare for the day.
2. **Self-Healing Document & Data Doctor (Automated Document Repair):**
   * When encountering broken Excel spreadsheets, corrupted formulas (`#REF!`, `#DIV/0!`), or inconsistent data types, AKSA doesn't crash. The *Data Doctor* agent analyzes anomalies, repairs broken references, and outputs a clean remediation audit.
3. **Multimodal Smart Scanner & OCR (Receipts & Invoices):**
   * Drop invoice photos, receipt snapshots, or scanned PDF vouchers into your workspace folder. AKSA extracts dates, numbers, and vendor entities into clean Excel tables.
4. **Deep Work & Focus Guard (Distraction-Free Throttling):**
   * When intense typing or coding activity is detected, AKSA suppresses minor notifications and delivers a structured digest when you pause.
5. **Distributed Multi-Node Agent Mesh & P2P Local Sync:**
   * Synchronize agent memory, learned skills, and workspace state across your devices (office Windows laptop, home Mac, homelab Linux server) via encrypted peer-to-peer (E2EE) tunnels without middleman cloud servers.
6. **Corporate Audit & Cryptographic Compliance Ledger:**
   * Every file mutation and permission grant is recorded into a tamper-proof cryptographic hash chain, ready for enterprise compliance audits (ISO 27001, GDPR, SOX).
7. **2.5D Virtual Office Canvas (Spatial Agent Workspace):**
   * An interactive visual floor plan representing agents actively working at desks, meeting in conference rooms, or waving when Human-in-the-Loop authorization is required.
8. **Autonomous Scheduler Engine & Proactive Cron:**
   * Schedules and executes recurring tasks via natural language or standard Cron expressions guarded by multi-channel HITL approval cards.
9. **Dynamic Plugin & Hot-Reloading MCP Tools Engine:**
   * Extends agent toolsets and capabilities on the fly using Model Context Protocol (MCP) servers and localized plugins without requiring server restarts.

---

## 🛠️ Key Features

### 1. Hierarchical Multi-Agent Orchestration & Token Efficiency
* **Executive Supervisor & Sub-Agents:** Breaks complex business goals into sub-tasks, delegates to specialists (Data Analyst, Document Writer, RAG Researcher), and synthesizes results.
* **Sub-Agent Context Isolation:** Sub-agents execute tool-loops in clean, isolated context scratchpads, returning only dense summaries and artifact paths (saving 28% to 80% on token consumption).
* **Multi-Turn Conversational Memory:** Understands follow-up references (*"from that Excel sheet, generate a PowerPoint summary deck"*) without losing context.

### 2. Real Office Document Automation Engine
* **Microsoft Excel (`.xlsx`):** Inspects sheets, builds corporate tables, formats currencies (`Rp`, `$`, `€`), generates active formulas (`SUM`, `AVERAGE`, `VLOOKUP`), and embeds native charts (Bar, Line, Pie).
* **Microsoft Word (`.docx`):** Produces formal business letters, official decrees, and contract drafts (MoU) with corporate styling and structured tables.
* **Microsoft PowerPoint (`.pptx`):** Generates executive presentations directly from real spreadsheet data, including title slides, overview summaries, and formatted data tables.
* **PDF & Text Extraction:** Extracts clean Markdown from complex PDFs and produces publication-quality documents.

### 3. Workspace Sandboxing & Tiered Human-in-the-Loop (HITL) Gate
* **Path Jail & Automated Backups:** Operations are strictly constrained to user-authorized folders (`allowed_paths`). Modifications automatically generate snapshots in `.aksa_backup/`.
* **Fail-Closed Permission Gate:** Risky actions (file deletions, system commands, external publishing) pause for explicit user confirmation via desktop modals or remote gateways.
* **Privacy Sanitization:** Automatically scrubs PII (API keys, Bearer tokens, national identity numbers, bank accounts) before saving to local memory or sending to LLMs.

### 4. Flexible Multi-Model Router (Cloud & 100% Offline Local)
* **Official Cloud Providers:** Google Gemini, Anthropic Claude, OpenAI, DeepSeek, Groq Cloud, OpenRouter, Mistral, and xAI Grok.
* **Free Local SLMs (Ollama & LM Studio):** Run models like `qwen2.5:7b`, `deepseek-r1:8b`, or `llama3.1:8b` locally with zero API fees and complete offline independence.
* **Zero Silent Cloud Fallback:** When local mode is selected, the system guarantees data is never routed to cloud providers.

### 5. Local Hybrid Knowledge Base (RAG)
* **Hybrid Search (LanceDB + SQLite FTS5):** Combines dense vector semantics with exact keyword matching (BM25) and real-time file system monitoring (`watchdog`).

---

## 🗺️ Phased Engineering Roadmap

AKSA's end-to-end engineering roadmap spans 45 structured phases, documented in detail in [**`ROADMAP.md`**](./ROADMAP.md) and [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md):

* **Phases 0 – 37 (Completed Foundations — Status: v0.0.2 Pre-Beta Alpha):**
  * Multi-agent hierarchy, sandbox path jail, automated backup recovery (`.aksa_backup/`), real Office engine (Excel formulas & charts, Word correspondence, data-driven PPT, PDF), hybrid RAG, remote command gateway, and 14 enterprise security audit cycles.
* **Phase 38: Autonomous Scheduler Engine & Multi-Channel HITL Gate:**
  * Recurring task execution (Cron & natural language) with interactive approval cards (Desktop & Remote Chat).
* **Phase 39: Google Workspace Ecosystem Connector:**
  * Google Drive, Docs, Sheets bidirectional sync, Google Calendar, and guarded Gmail sender.
* **Phase 40: Social Media Hub & Community Specialist:**
  * LinkedIn, X, Meta Graph connectors with post preview cards and Zero Unapproved Post enforcement.
* **Phase 41: AKSA Virtual Office Experience:**
  * 2.5D visual isometric floor plan with real-time agent activity animations (typing, meeting, alerting, idle).
* **Phase 42: Distributed Server-Client Topology & Mobile Apps:**
  * Architecture decoupling for AKSA Core Server and dedicated native mobile clients (Android & iOS) with biometric one-tap HITL approvals.
* **Phase 43: Advanced Strategic Capabilities:**
  * Local Speech-to-Action (Whisper), Self-Healing Data Doctor, Smart OCR Scanner, and P2P Mesh sync.
* **Phase 44: Real User Usability Testing & Final Compliance Certification:**
  * Structured usability verification with 5 non-technical users.
* **Phase 45: Official Public Launch:**
  * Public Beta (v0.1.0) $\rightarrow$ stable Production LTS (v1.0.0).

---

## 🚀 Quickstart Guide

### System Requirements:
* **Node.js:** Version 20.x or 22.x LTS ([nodejs.org](https://nodejs.org/))
* **Python:** Version 3.12+ ([python.org](https://python.org/))
* **Rust (Optional):** Required only if compiling native Tauri desktop windows ([rustup.rs](https://rustup.rs/))
* **Ollama (Optional):** To run 100% free, offline local AI models ([ollama.com](https://ollama.com/))

---

### Installation Steps:

```bash
# 1. Clone repository
git clone https://github.com/yogijowo/aksa.git
cd aksa

# 2. Install desktop frontend dependencies
npm --prefix apps/desktop install

# 3. Setup Python virtual environment for backend sidecar
cd services/engine
python -m venv .venv

# Activate virtual environment:
# Windows (cmd/PowerShell):
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install engine dependencies:
pip install -e ".[dev]"
cd ../..
```

---

### Running AKSA for Your Environment:

#### 1. Fast Web Browser Mode (Windows, macOS, Linux — No Rust Required)
Launches the React interface in your web browser and the Python FastAPI engine locally:
```bash
npm run dev
# Open in browser: http://localhost:1420
```

#### 2. Native Desktop GUI Mode (Windows, macOS, Linux — Requires Rust)
Launches AKSA as a native desktop application with System Tray and OS permission dialogs:
```bash
npm run dev:tauri
```

#### 3. Linux Headless Server / CLI Mode (Server, VPS, Docker — No GUI Required)
Runs the AKSA engine as a 24/7 background service on Linux without an X11/Wayland display server. Tasks are controlled remotely via the remote command gateway or local REST/WebSocket APIs:
```bash
cd services/engine
source .venv/bin/activate
python -m app.main --host 0.0.0.0 --port 43120 --production
```

---

### Running the Test Suite:
```bash
# Frontend UI unit tests (Vitest):
npm --prefix apps/desktop run test

# Strict TypeScript check & Vite production build:
npm --prefix apps/desktop run build

# Native Rust shell verification:
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml

# Backend Python test suite (295 test scenarios):
cd services/engine && pytest
```

---

## 📚 Technical & Governance Documentation

* [**`ROADMAP.md`**](./ROADMAP.md) — **Master Phased Engineering Roadmap (Phases 1 through 45).**
* [**`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`**](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) — **Full PRD:** Virtual Office Canvas, Autonomous Scheduler & Ecosystem Connectors.
* [**`AGENTS.md`**](./AGENTS.md) — Master architectural rules, coding standards, and language split conventions.
* [**`PROGRESS.md`**](./PROGRESS.md) — Live progress tracker and session changelog.
* [**`docs/01-ARCHITECTURE.md`**](./docs/01-ARCHITECTURE.md) — Unified Tauri v2 + Python FastAPI architecture.
* [**`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`**](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md) — Multi-agent orchestration & token efficiency.
* [**`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`**](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md) — 3-Tier automation engine & Office generators.
* [**`docs/04-RAG-AND-MEMORY-SYSTEM.md`**](./docs/04-RAG-AND-MEMORY-SYSTEM.md) — Hybrid RAG search (LanceDB + SQLite FTS5).
* [**`docs/05-TELEGRAM-GATEWAY.md`**](./docs/05-TELEGRAM-GATEWAY.md) — Remote command gateway specification.
* [**`docs/06-UI-UX-DESIGN-SYSTEM.md`**](./docs/06-UI-UX-DESIGN-SYSTEM.md) — UI/UX design tokens and Indonesian UI glossary.
* [**`docs/07-DATABASE-AND-API-SCHEMA.md`**](./docs/07-DATABASE-AND-API-SCHEMA.md) — SQLite database schema & REST/WebSocket contracts.
* [**`docs/08-ROADMAP-AND-PHASES.md`**](./docs/08-ROADMAP-AND-PHASES.md) — Phased engineering implementation checklist.
* [**`SECURITY.md`**](./SECURITY.md) • [**`PRIVACY.md`**](./PRIVACY.md) • [**`SUPPORT.md`**](./SUPPORT.md)

---

## License

Distributed under the **[MIT License](./LICENSE)**. Open source and free for individual and commercial innovation.
