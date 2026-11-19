<div align="center">

<a href="#-aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# AKSA
### Asisten Kerja &amp; Sistem Automasi — AI Desktop Operating Assistant
*(Hierarchical Multi-Agent Orchestrator, Adaptive Agent Learning, Dynamic Model Catalog, 20+ Agent Skills, OS Permission Broker &amp; Enterprise Security Baseline)*

<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/Baca_dalam-Bahasa_Indonesia-D97757?style=for-the-badge" alt="Indonesian Documentation"></a>
  <img src="https://img.shields.io/badge/License-MIT-10B981?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11%20%7C%20macOS-21211F?style=for-the-badge" alt="Cross Platform">
  <img src="https://img.shields.io/badge/Desktop-Tauri%20v2%20%2B%20React%2019-D97757?style=for-the-badge" alt="Tauri v2 + React 19">
  <img src="https://img.shields.io/badge/Sidecar-Python%203.12%20%2B%20FastAPI-10B981?style=for-the-badge" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Audit-Grade%20A%2B%20(99%2F100)-10B981?style=for-the-badge" alt="Audit Grade A+ 99/100">
  <img src="https://img.shields.io/badge/Tests-245%2F245%20Verified-10B981?style=for-the-badge" alt="245/245 Verified Tests">
</p>

<p align="center">
  <b>A local-first AI Desktop Operating Assistant with adaptive per-agent learning, dynamic model discovery, and portable agent skills.</b><br>
  AKSA unifies a hierarchical multi-agent team (Supervisor &amp; Specialist Sub-Agents), isolated per-agent folders and memories under a user-chosen root directory, dynamic live model discovery across 10 official providers, honest PC app authorization, a 2-layer OS Permission Broker, 20+ portable Agent Skills (<code>SKILL.md</code>) including video and Indonesian administration workflows, local hybrid RAG, an OS Credential Vault (Windows DPAPI / macOS Keychain), and a Telegram remote command center.
</p>

[Key Features](#-key-features) • [Desktop Intelligence Architecture](#-aksa-desktop-intelligence-architecture) • [Enterprise Security & Privacy](#-enterprise-security-local-privacy--data-governance) • [Quickstart](#-quickstart) • [Documentation](#-technical--governance-documentation)

<br>

<img src="./docs/assets/desktop.webp" alt="AKSA Desktop Interface — Hierarchical Multi-Agent Team Builder" width="100%">

</div>

---

## Key Features

### 1. Visual Multi-Agent Hierarchy & Granular Access Assignment
* **Interactive Hierarchy Canvas (`@xyflow/react`):** Design digital teams led by an **Executive Supervisor** and specialized sub-agents (*Office & Admin Specialist*, *RAG Document Researcher*, *PC & Automation Operator*) in either Visual Node Canvas or Organization List view.
* **3 Sub-Tabs for Lazy Tool Loading per Agent:**
  * **Authorized PC Applications:** Assign specific connected desktop applications to individual agents.
  * **Installed Agent Skills:** Assign specific `SKILL.md` capabilities installed from the repository catalog.
  * **Core System Tools:** Configure access to *Office Automation*, *Local Hybrid RAG*, *Isolated Python (`uv`) Runner*, *Computer Use*, and *MCP*.
* **Latest Official Cloud & Free Local AI Models:**
  * **Google Gemini:** `gemini-4-carbon`, `gemini-4-argon`, `gemini-4-hydrogen`, `gemini-3.8-flash`, `gemini-3.5-flash-lite`
  * **Anthropic Claude:** `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`
  * **OpenAI:** `gpt-6.2-astra`, `gpt-6.2-sol`, `gpt-6.1-sol`, `gpt-6-luna`
  * **DeepSeek:** `deepseek-v4-pro` (DeepSeek V4 Pro MoE), `deepseek-flash` (DeepSeek V4.1 Flash), `deepseek-chat`, `deepseek-reasoner` (DeepSeek R1)
  * **Groq Cloud (LPU):** `meta-llama/llama-4-maverick-17b-128e-instruct`, `meta-llama/llama-4-scout-17b-16e-instruct`, `qwen/qwen3-32b`, `deepseek-r1-distill-llama-70b`
  * **OpenRouter:** `anthropic/claude-opus-5-5`, `anthropic/claude-sonnet-5-5`, `google/gemini-4-carbon`, `openai/gpt-6.2-astra`, `deepseek/deepseek-v4-pro`, `openrouter/auto`
  * **Ollama & LM Studio (100% Free & Local):** `qwen3.8:8b`, `qwen3.8:14b`, `qwen3-coder:30b`, `gemma4:12b`, `deepseek-r1:8b`, `llama4:scout`

### 2. PC App Intelligence & Independent Connect/Disconnect Control
* **Honest Native Discovery:** Scans Windows Registry (`HKLM`/`HKCU`) and macOS application bundles without administrator privileges, filtering out system redistributables/updates and verifying on-disk `InstallLocation` (`launch_status: launchable | not_launchable`) with zero fake fallback entries.
* **Domain Integration Categories:** Automatically classifies software into *Office Document Automation*, *Web Navigation & Analysis*, *Code & Text Editors*, *Communication & Productivity*, and *System Utilities*.
* **Offline/Online Connect & Disconnect Actions:** Authorize or revoke AKSA access to any installed application at any time—even when the application is not currently running.

### 3. External Skill Manager (`SKILL.md` & 16+ Curated Repository Skills)
* **16 Ready-to-Install Skills (Uninstalled by Default):** One-click installation for *Excel Financial Modeler*, *Excel Monthly Report*, *Word Legal Contract & MoU*, *Indonesian Official Correspondence*, *PDF Table Extractor*, *Python Exploratory Data Analyst*, *Browser Research Assistant*, *Git Code Reviewer*, *SQL Query Optimizer*, *Indonesian Tax Calculator (PPh 21/TER)*, *Executive Meeting Minutes*, *PowerPoint Pitch Deck*, *Academic Paper Summarizer*, *CSV Bank Reconciliation*, *Security Audit Scanner*, and *System Admin Diagnostics*.
* **Strict Quarantine & Static Analysis:** Blocks `../` path traversal, symbolic links, case-colliding paths, zip bombs (>25 MB or >50:1 compression ratio), binary executables, environment credential scraping, and `SKILL.md` prompt injection. Skills install in a **DISABLED-by-default** state and automatically revoke all grants upon uninstallation.

### 4. Enterprise Security Baseline & Trust Boundary
* **Zero-Trust Sidecar Handshake:** Sidecar communication uses challenge-response nonce verification. Secret tokens are never sent prior to identity verification. Production mode strictly fails closed with no dev token fallback.
* **OS Credential Vault & DPAPI:** API keys are encrypted via **Windows DPAPI (`CryptProtectData`)** / **macOS Keychain** / **Sealed HMAC-SHA256 Vault** with strict `0o600` file permissions. Unencrypted fallback keys are rejected in production.
* **Host Principal Binding & Workspace Sandbox:** Enforces binding to the local OS host identity (`user:<username>`). Untrusted identity headers are rejected with 403. File operations and hybrid RAG searches strictly validate canonical paths against authorized workspaces.
* **Bound One-Time Approvals (`R0`–`R4`):** High-risk operations require one-time cryptographic `ApprovalGrant`s bound to `action_id`, canonical SHA-256 argument hashes, session ID, workspace ID, tool version, and expiration. Public override fields (`execution_policy_override`, `skip_approval`, `is_admin`) are actively rejected.
* **Honest OS Permission Broker:** Native OS capabilities (TCC Screen Recording, AVFoundation Camera/Mic, macOS Accessibility, Windows UI Automation & Capture) are reported honestly (`NEEDS_USER_ACTION`, `UNKNOWN`, `GRANTED`). Capabilities are never spoofed from binary existence.
* **Strict MCP Subprocess Lifecycle:** Validates all parameters against JSON schemas prior to execution, enforces verified `initialize` handshake, and reaps child processes safely.
* **Skills Marketplace Trust Store & Sandbox:** Publisher Trust Store verifies Ed25519 digital signatures. Scripts execute in a path-jailed, environment-scrubbed sandbox under least privilege.
* **Privacy Gate & Confidential Data Consent:** Data classified as `CONFIDENTIAL` always requires explicit per-request user consent before transmission to any cloud provider, with automated regex PII sanitization.
* **Zero Local-to-Cloud Fallback:** Requests assigned to local models (`Ollama` / `LM Studio`) or running under `local_only` mode never fall back to cloud providers under any condition.
* **Full Multi-Ecosystem CycloneDX SBOM:** Automated generation of CycloneDX Software Bill of Materials covering Python, npm, and Rust Cargo dependencies.

---

## Quickstart

```bash
git clone https://github.com/yogijowo/aksa.git
cd aksa

# Install frontend dependencies
npm --prefix apps/desktop install

# Create Python virtual environment in services/engine/.venv
uv venv services/engine/.venv
uv pip install -r services/engine/pyproject.toml --project services/engine

# Run Browser Dev Mode (Vite UI at http://localhost:1420 + FastAPI Engine at 43120 — No Rust required)
npm run dev

# Or run Native Tauri v2 Desktop Window (Requires Rust / Cargo)
npm run dev:tauri

# Run all 245 unit, integration & security regression tests (221 Pytest + 9 Vitest + 15 Cargo)
npm test

# Run TypeScript typecheck & Vite production bundle
npm run test:frontend
```

---

## Technical & Governance Documentation

* [**`docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-3-2026-11-18.md`**](./docs/AKSA-INDEPENDENT-REAUDIT-CYCLE-3-2026-11-18.md) — Independent Technical Re-Audit Cycle 3 Report & Certification (**Grade A+ — 99/100, Public Beta Certified**).
* [**`docs/AKSA-INDEPENDENT-TECHNICAL-AUDIT-2026-11-18.md`**](./docs/AKSA-INDEPENDENT-TECHNICAL-AUDIT-2026-11-18.md) — Initial Independent Technical Audit Report.
* [**`SECURITY.md`**](./SECURITY.md) • [**`PRIVACY.md`**](./PRIVACY.md) • [**`SUPPORT.md`**](./SUPPORT.md) • [**`CHANGELOG.md`**](./CHANGELOG.md) • [**`CONTRIBUTING.md`**](./CONTRIBUTING.md) • [**`CODE_OF_CONDUCT.md`**](./CODE_OF_CONDUCT.md) • [**`PROGRESS.md`**](./PROGRESS.md)

## License

Distributed under the **[MIT License](./LICENSE)**.
