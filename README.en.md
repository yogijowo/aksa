<div align="center">

<a href="#aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# AKSA
### Asisten Kerja &amp; Sistem Automasi — AI Desktop Operating System &amp; Digital Headquarters
*(Hierarchical Multi-Agent Team, Virtual Office Experience, Autonomous Scheduler, Ecosystem Connectors &amp; Enterprise Security Baseline)*

<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/Baca_dalam-Bahasa_Indonesia-D97757?style=for-the-badge" alt="Indonesian Documentation"></a>
  <img src="https://img.shields.io/badge/Current_Version-v0.0.2_(Pre--Beta_Alpha)-3B82F6?style=for-the-badge" alt="Current Version v0.0.2">
  <img src="https://img.shields.io/badge/Security_Audit-Cycle_14_Passed_100%25-10B981?style=for-the-badge" alt="Security Audit Cycle 14">
  <img src="https://img.shields.io/badge/Platform-Windows_10%2F11_%7C_macOS_%7C_Linux-21211F?style=for-the-badge" alt="Cross Platform">
  <img src="https://img.shields.io/badge/Desktop-Tauri_v2_%2B_React_19-D97757?style=for-the-badge" alt="Tauri v2 + React 19">
  <img src="https://img.shields.io/badge/Sidecar-Python_3.12_%2B_FastAPI-10B981?style=for-the-badge" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Tests-325_Passed-10B981?style=for-the-badge" alt="325 Tests Passed">
</p>

<p align="center">
  <b>A local-first AI Desktop Operating System that runs directly on your computer with a hierarchical autonomous agent team, 100% local privacy, real Office document automation, and cloud &amp; social ecosystem connectors.</b><br>
  AKSA connects leading AI models (cloud &amp; 100% offline local) to your real work files, spreadsheets, recurring schedules, and desktop apps without ever leaking confidential data or taking risky actions without your explicit consent.
</p>

[Vision & Future Direction](#vision-what-aksa-will-become) • [Current Position & Maturity Score](#current-position-status--maturity-score-v002) • [Key Features](#key-features) • [System Architecture](#aksa-desktop-intelligence-architecture) • [Roadmap](#phased-development-roadmap) • [Quickstart](#quickstart) • [Documentation](#technical--governance-documentation)

<br>

<img src="./docs/assets/desktop.webp" alt="AKSA Desktop Interface — Hierarchical Multi-Agent Team Builder" width="100%">

</div>

---

## Vision: What AKSA Will Become

Most current AI assistants are passive browser chat windows disconnected from your local files and workflows. In contrast, unrestricted computer agents risk breaking operating systems or leaking sensitive documents.

**AKSA is engineered to be your Digital Headquarters & Autonomous Co-Worker:**

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
│ or wave for permission. │ (Desktop & Telegram).   │ (LinkedIn, X, Meta).    │
├─────────────────────────┴─────────────────────────┴─────────────────────────┤
│                          LOCAL EXECUTION ENGINE                             │
│  • Real Office Automation (Excel formulas & charts, Word contracts, PPT)    │
│  • Path Jail Sandbox & Automated File Backups (.aksa_backup/)               │
│  • Multi-Model Router (Gemini, Claude, GPT, DeepSeek, Ollama, LM Studio)    │
│  • 100% Local Privacy (Zero Silent Cloud Fallback & DPAPI/Keyring Vault)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **A Visual Co-Worker, Not Just a Chatbot:** Users can observe a virtual office where agents actively work, collaborate in conference rooms, or raise their hand when Human-in-the-Loop permission is required.
2. **Proactive Scheduled Autonomy:** Instruct AKSA once (*"Every Monday at 8 AM, aggregate last week's sales reports, build a PowerPoint slide deck, and prepare an email draft"*), and AKSA executes precisely on time.
3. **Bridge Between Local Files and the Cloud Ecosystem:** Connects local disk files to Google Workspace and social publication channels, guarded by a strict policy: **zero unapproved public posts or external data transfers**.
4. **Absolute Privacy Sovereignty:** 100% local-first. Your private data is never used for public model training, and local models (Ollama / LM Studio) operate entirely offline.

---

## Current Position, Status & Maturity Score (v0.0.2)

AKSA is currently in **Pre-Beta Alpha (v0.0.2)**. All core architectural foundations are 100% implemented, independently audited across 14 rigorous remediation cycles, and tested locally and via private CI before Public Beta (v0.1.0) and Production LTS (v1.0.0).

### Verification Scores & Maturity Metrics

| Evaluation Dimension | Score / Metric | Status | Verification Evidence |
| :--- | :---: | :---: | :--- |
| **Security Audit & OS Integrity** | **100% Passed** | Verified | Passed 14 independent re-audit cycles ([`docs/AKSA — Independent Re-Audit Siklus 14.md`](./docs/AKSA%20—%20Independent%20Re-Audit%20Siklus%2014.md)). Zero-trust sidecar handshake, DPAPI/Keychain vault, canonical path jail, and bound anti-replay HITL tokens. |
| **Backend Test Suite (Python Pytest)** | **291 Passed** / 4 Skipped | Verified | 291 scenarios pass cleanly on the engine (4 OS-specific sandbox tests skipped on macOS runner). |
| **Frontend Test Suite (React Vitest)** | **16 Passed** (100%) | Verified | Zustand store unit tests, initial database hydration, and sidecar identity verification pass in 1.1s. |
| **Desktop Shell Integrity (Tauri v2 Rust)** | **18 Passed** (100%) | Verified | `cargo check` and `cargo test` pass with zero errors on native host targets. |
| **TypeScript & Vite Production Bundle** | **0 Errors** (Clean) | Verified | `tsc --noEmit && vite build` completes in 2.5s with optimized code chunks. |
| **Supply Chain Dependency Audit** | **0 Vulnerabilities** | Verified | `npm audit --omit=dev --audit-level=high` reports zero critical or high vulnerabilities. |
| **Token Efficiency & Budget Guard** | **28% – 80% Saved** | Verified | Significant API cost reduction via Sub-Agent Context Isolation, dynamic lazy tools, and rolling context compaction. |
| **Windows Setup .exe Compilation** | **100% Succeeded** | Verified | GitHub Actions private pipeline freezes native sidecar (115 MB) and bundles standalone NSIS installer: `AKSA_0.0.2_x64-setup.exe` (114.5 MB). |

---

## Key Features

### 1. Hierarchical Multi-Agent Team & Token Optimization
* **Executive Supervisor & Sub-Agents:** Breaks complex requests down, delegates sub-tasks to specialists (*Data Analyst*, *Office Document Specialist*, *RAG Researcher*), and synthesizes executive conclusions.
* **Sub-Agent Context Isolation:** Sub-agents execute tool loops in isolated scratchpads. Only structured summaries and generated artifacts return to the Supervisor, keeping context compact and saving up to 80% token costs.
* **Multi-Turn Context Awareness:** Retains historical references across conversation turns (e.g., *"turn that Excel data into a PowerPoint presentation"*).

### 2. Native Office & Document Automation Engine
* **Microsoft Excel (`.xlsx`):** Inspects sheets, headers, and rows; creates corporate-styled tables with formatted currency (`Rp`), active formulas (`=SUM`, `=AVERAGE`, `=VLOOKUP`), and embedded Bar/Line/Pie charts.
* **Microsoft Word (`.docx`):** Drafts formal letters, official Indonesian administrative templates, partnership agreements (MoU), and reports.
* **Microsoft PowerPoint (`.pptx`):** Generates executive slide decks populated with real data from spreadsheets (overview, sample tables, key takeaways).
* **PDF Extraction & Generation:** Extracts Markdown from large PDFs and compiles print-ready reports.

### 3. Sandboxed Path Jail & Human-in-the-Loop (HITL) Gate
* **Path Jail & Automated Backups:** Agents are constrained to user-authorized folders (`allowed_paths`). Modifying existing files automatically creates backups in `.aksa_backup/`.
* **Human-in-the-Loop Approval:** High-risk actions (out-of-bounds writes, email sending, social posting) require interactive confirmation via Desktop Notification or Telegram Bot.
* **Privacy Sanitization:** Automatically masks API keys, Bearer tokens, national identity numbers, bank accounts, and contact info before saving to memory or forwarding to models.

### 4. Multi-Model Router (Cloud & Offline Local AI)
* **Official Cloud Providers:** Google Gemini, Anthropic Claude, OpenAI, DeepSeek, Groq Cloud, OpenRouter, Mistral, and xAI Grok.
* **Free Offline Local AI:** Connects to Ollama and LM Studio with zero subscription fees and zero internet requirement.
* **Zero Silent Cloud Fallback:** When local mode or `local_only` is selected, data is never leaked or routed to cloud APIs.

---

## Phased Development Roadmap

### Completed Foundations (Phases 0 – 37) — Status: v0.0.2 Pre-Beta Alpha
- [x] **Core Desktop Host:** Tauri v2, React 19, Tailwind CSS v4, Obsidian Slate & Warm Paper design themes.
- [x] **Hierarchical Multi-Agent Engine:** Supervisor planning, isolated sub-agent scratchpads, token savings.
- [x] **Office Document Generator:** Native `.xlsx`, `.docx`, `.pptx`, and `.pdf` generation.
- [x] **Multi-Turn Session Memory:** Contextual continuity across multi-turn queries.
- [x] **Enterprise Security Baseline:** 14 independent re-audit cycles, DPAPI/Keychain credential vault, sandbox path jail.
- [x] **Automated Windows .exe Packaging:** Isolated GitHub Actions pipeline packaging NSIS setup `.exe`.

---

### Upcoming Phases (Phases 38 – 42) — Toward v0.1.0 Public Beta & v1.0.0 LTS
*Detailed specification available in [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md).*

* **Phase 38: Autonomous Scheduler Engine & Multi-Channel HITL Gate:** `APScheduler` backend, natural language cron parser, desktop & Telegram interactive approval cards.
* **Phase 39: Google Workspace Ecosystem Connector:** OAuth 2.0 PKCE, Google Drive, Docs, Sheets bidirectional sync, Calendar scheduling, and guarded Gmail sender.
* **Phase 40: Social Media Hub & Community Specialist:** LinkedIn, X, Meta Graph connectors, live post preview cards, Zero Unapproved Post enforcement.
* **Phase 41: AKSA Virtual Office Experience:** 2.5D isometric visual canvas, live agent state animations (typing, meeting, alerting, idle), interactive desk inspector.
* **Phase 42: Usability Testing, Production Hardening & Public Launch:** Usability verification with non-technical users, v0.1.0 Public Beta, and v1.0.0 LTS release.

---

## Quickstart

### 1. Download Windows Setup Installer (.exe)
1. Go to the **Actions** tab on your GitHub repository.
2. Select the workflow **Build Windows Setup Executable (.exe)**.
3. Under **Artifacts** at the bottom of the summary, download **`AKSA-Windows-x64-Setup`**.
4. Extract and run `AKSA_0.0.2_x64-setup.exe` to install on Windows.

---

### 2. Run from Source Code (Development Mode)
```bash
# 1. Clone repository
git clone https://github.com/yogijowo/aksa.git
cd aksa

# 2. Install desktop dependencies
npm --prefix apps/desktop install

# 3. Setup Python engine environment
cd services/engine
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cd ../..

# 4. Launch development servers:
# Fast Web Browser UI (http://localhost:1420 + FastAPI on port 43120):
npm run dev

# Or launch native Tauri v2 desktop window:
npm run dev:tauri
```

---

## Technical & Governance Documentation

* [**`AGENTS.md`**](./AGENTS.md) — Master guidelines for architecture, coding conventions, and language split standards.
* [**`PROGRESS.md`**](./PROGRESS.md) — Real-time progress tracker and session changelog.
* [**`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`**](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) — **Full PRD:** Virtual Office Canvas, Autonomous Scheduler & Ecosystem Connectors.
* [**`docs/01-ARCHITECTURE.md`**](./docs/01-ARCHITECTURE.md) — Unified Tauri v2 + Python FastAPI architecture.
* [**`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`**](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md) — Multi-agent orchestration & token efficiency.
* [**`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`**](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md) — 3-Tier automation engine & Office generators.
* [**`docs/04-RAG-AND-MEMORY-SYSTEM.md`**](./docs/04-RAG-AND-MEMORY-SYSTEM.md) — Hybrid RAG search (LanceDB + SQLite FTS5).
* [**`docs/05-TELEGRAM-GATEWAY.md`**](./docs/05-TELEGRAM-GATEWAY.md) — Telegram remote command center specification.
* [**`docs/06-UI-UX-DESIGN-SYSTEM.md`**](./docs/06-UI-UX-DESIGN-SYSTEM.md) — UI/UX design tokens and Indonesian UI glossary.
* [**`docs/07-DATABASE-AND-API-SCHEMA.md`**](./docs/07-DATABASE-AND-API-SCHEMA.md) — SQLite database schema & REST/WebSocket contracts.
* [**`docs/08-ROADMAP-AND-PHASES.md`**](./docs/08-ROADMAP-AND-PHASES.md) — Technical phased development checklist.
* [**`SECURITY.md`**](./SECURITY.md) • [**`PRIVACY.md`**](./PRIVACY.md) • [**`SUPPORT.md`**](./SUPPORT.md)

---

## License

Distributed under the **[MIT License](./LICENSE)**. Open source and free for individual and commercial innovation.
