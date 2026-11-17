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
  <img src="https://img.shields.io/badge/Tests-41%2F41%20Verified-10B981?style=for-the-badge" alt="41/41 Verified Tests">
</p>

<p align="center">
  <b>A local-first AI Desktop Operating Assistant with adaptive per-agent learning, dynamic model discovery, and portable agent skills.</b><br>
  AKSA unifies a hierarchical multi-agent team (Supervisor &amp; Specialist Sub-Agents), isolated per-agent folders and memories under a user-chosen root directory, dynamic live model discovery across 10 official providers, honest PC app authorization, a 2-layer OS Permission Broker, 20+ portable Agent Skills (<code>SKILL.md</code>) including video and Indonesian administration workflows, local hybrid RAG, an OS Credential Vault (Windows DPAPI / macOS Keychain), and a Telegram remote command center.
</p>

[Key Features](#-key-features) • [Desktop Intelligence Architecture](#-aksa-desktop-intelligence-architecture) • [Enterprise Security & Privacy](#-enterprise-security-local-privacy--data-governance) • [Quickstart](#-quickstart) • [Documentation](#-technical--governance-documentation)

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
  * **Google Gemini:** `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash`, `gemini-1.5-pro`
  * **Anthropic Claude:** `claude-3-7-sonnet-latest`, `claude-3-5-sonnet-latest`, `claude-3-5-haiku-latest`, `claude-3-opus-latest`
  * **OpenAI:** `gpt-4.5-preview`, `o3-mini`, `o1`, `gpt-4o`, `gpt-4o-mini`
  * **DeepSeek:** `deepseek-chat` (DeepSeek-V3 671B), `deepseek-reasoner` (DeepSeek-R1)
  * **Groq Cloud (LPU):** `llama-3.3-70b-versatile`, `deepseek-r1-distill-llama-70b`, `llama-3.1-8b-instant`, `qwen-2.5-32b`
  * **OpenRouter:** `anthropic/claude-3.7-sonnet`, `google/gemini-2.5-pro`, `deepseek/deepseek-r1`, `openrouter/auto`
  * **Ollama & LM Studio (100% Free & Local):** `qwen2.5:7b`, `qwen2.5-coder:7b`, `llama3.3:70b`, `llama3.2:3b`, `deepseek-r1:8b`, `phi4:14b`, `mistral:7b`

### 2. PC App Intelligence & Independent Connect/Disconnect Control
* **Honest Native Discovery:** Scans Windows Registry (`HKLM`/`HKCU`) and macOS application bundles without administrator privileges, filtering out system redistributables/updates and verifying on-disk `InstallLocation` (`launch_status: launchable | not_launchable`) with zero fake fallback entries.
* **Domain Integration Categories:** Automatically classifies software into *Office Document Automation*, *Web Navigation & Analysis*, *Code & Text Editors*, *Communication & Productivity*, and *System Utilities*.
* **Offline/Online Connect & Disconnect Actions:** Authorize or revoke AKSA access to any installed application at any time—even when the application is not currently running.

### 3. External Skill Manager (`SKILL.md` & 16+ Curated Repository Skills)
* **16 Ready-to-Install Skills (Uninstalled by Default):** One-click installation for *Excel Financial Modeler*, *Excel Monthly Report*, *Word Legal Contract & MoU*, *Indonesian Official Correspondence*, *PDF Table Extractor*, *Python Exploratory Data Analyst*, *Browser Research Assistant*, *Git Code Reviewer*, *SQL Query Optimizer*, *Indonesian Tax Calculator (PPh 21/TER)*, *Executive Meeting Minutes*, *PowerPoint Pitch Deck*, *Academic Paper Summarizer*, *CSV Bank Reconciliation*, *Security Audit Scanner*, and *System Admin Diagnostics*.
* **Strict Quarantine & Static Analysis:** Blocks `../` path traversal, symbolic links, case-colliding paths, zip bombs (>25 MB or >50:1 compression ratio), binary executables, environment credential scraping, and `SKILL.md` prompt injection. Skills install in a **DISABLED-by-default** state and automatically revoke all grants upon uninstallation.

### 4. Enterprise Security Baseline (`ExecutionPolicyGateway` & `CredentialVault`)
* **OS Credential Vault:** API keys are encrypted via **Windows DPAPI (`CryptProtectData`)** / **macOS Keychain** / **Sealed HMAC-SHA256 Vault**. SQLite `credentials_metadata` stores only `credential_ref` and masked previews—never plaintext secrets.
* **Zero Local-to-Cloud Fallback:** Requests assigned to local models (`Ollama` / `LM Studio`) or running under `local_only` mode never fall back to cloud providers under any condition.
* **Data Disclosure Gate & Classification:** Enforces `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, and `RESTRICTED` data classification tiers and prevents automatic PDF attachments without explicit user consent.
* **Bound One-Time Approvals (`R0`–`R4`):** High-risk operations require one-time cryptographic `ApprovalGrant`s bound to canonical SHA-256 argument hashes, session ID, workspace ID, tool version, and expiration. Public override fields (`execution_policy_override`, `skip_approval`, `is_admin`) are actively rejected.

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

# Run all 41 backend unit, integration & security regression tests
npm run test:backend

# Run TypeScript typecheck & Vite production bundle
npm run test:frontend
```

---

## Technical & Governance Documentation

* [**`SECURITY.md`**](./SECURITY.md) • [**`PRIVACY.md`**](./PRIVACY.md) • [**`SUPPORT.md`**](./SUPPORT.md) • [**`CHANGELOG.md`**](./CHANGELOG.md) • [**`CONTRIBUTING.md`**](./CONTRIBUTING.md) • [**`CODE_OF_CONDUCT.md`**](./CODE_OF_CONDUCT.md) • [**`PROGRESS.md`**](./PROGRESS.md)

## License

Distributed under the **[MIT License](./LICENSE)**.
