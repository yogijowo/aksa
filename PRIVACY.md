# Privacy Policy & Data Handling Architecture (`PRIVACY.md`)

## 1. Core Privacy Principles

AKSA is built on a **Local-First, Consent-Driven** architecture:
- **Zero Silent Cloud Fallback:** When configured in `local_only` mode or when executing an agent assigned to a local model (`Ollama` / `LM Studio`), AKSA never transmits prompts, filenames, or document contents to any external cloud provider—even if the local model server is offline and cloud API keys are present.
- **No Automatic Document Attachment:** AKSA never automatically attaches workspace PDFs or documents to external LLM requests. File attachments require explicit user selection and consent through the `DataDisclosureGate`.
- **OS Credential Vault Storage:** Cloud API keys and Telegram Bot tokens are encrypted via the OS Credential Vault (Windows DPAPI / macOS Keychain / Sealed Vault). SQLite stores only opaque `credential_ref` identifiers and masked previews (`sk-p••••••••1234`).

---

## 2. Provider Modes (`ProviderMode`)

Users and administrators can configure one of four explicit routing modes via `POST /api/v1/privacy/settings`:

| Mode | Behavior |
|---|---|
| `local_only` | Strictly restricts all inference to local models (`Ollama`, `LM Studio`). All external cloud providers are blocked. |
| `cloud_by_choice` | Routes requests to the specific provider chosen for the agent without cross-provider fallback. Document attachments still require explicit consent. |
| `hybrid_with_consent` | Evaluates data classification per request; `CONFIDENTIAL` data and document attachments trigger an explicit `DataDisclosureSummary` confirmation before external transmission. |
| `enterprise_managed` | Enforces an organization-defined provider allowlist and data classification policy. |

---

## 3. Data Classification (`DataClassification`)

Every request and workspace resource is evaluated under four classification tiers:

1. **`PUBLIC`**: Non-sensitive general prompts; may be processed by user-selected providers.
2. **`INTERNAL`** *(Default)*: Standard work instructions; processed locally or via user-selected providers without automatic file attachments.
3. **`CONFIDENTIAL`**: Financial records, contracts, personal identifiers (`NIK`, `NPWP`), or attached documents; requires explicit user disclosure consent in `hybrid_with_consent` mode.
4. **`RESTRICTED`**: Credentials, private keys, or top-secret documents; **strictly blocked** from all external cloud providers by default.

---

## 4. Local Data Inventory & Retention (`Section 17`)

All AKSA runtime state resides inside the user's OS application data directory (`%APPDATA%\com.aksa.desktop` on Windows, `~/Library/Application Support/com.aksa.desktop` on macOS):

| Artifact | Location | Purpose & Retention |
|---|---|---|
| Relational Metadata & FTS5 | `data/aksa.db` | Agent teams, session metadata, permission grants, audit ledger, and FTS5 document index. Retained until deleted by user. |
| Sealed Credential Vault | `data/credentials.vault` | DPAPI / HMAC-SHA256 encrypted API keys. Deleted immediately upon key revocation (`DELETE /api/v1/models/keys/{provider}`). |
| Vector Embeddings | `data/lancedb/` | Local semantic chunks for authorized workspaces. Purged when a workspace is removed or revoked. |
| Quarantine & Installed Skills | `skills_quarantine/`, `skills/` | Static-scanned `SKILL.md` packages. Removed immediately upon skill uninstallation (`DELETE /api/v1/skills/{skill_id}`). |
| Workspace Auto-Backups | `<workspace>/.aksa_backup/` | Timestamped `.bak` snapshots created prior to file modifications. |
| Structured Logs | `logs/` | Redacted operational logs. Secrets, API keys, and raw document contents are stripped prior to logging. |

---

## 5. Telemetry & Diagnostics

- **Telemetry is disabled (`telemetry_opt_in: false`) by default.** AKSA does not transmit background analytics, crash dumps, prompts, or filenames to any central server.
- **Support Diagnostic Bundles (`GET /api/v1/system/diagnostics/support-bundle`):** Generated strictly on-demand for user inspection before sharing. All API keys, bearer tokens, passwords, and document bodies are automatically redacted (`[REDACTED_SECRET]`).

---

## 6. Right to Revoke & Delete

- **Revoke All Workspaces:** `POST /api/v1/workspaces/revoke-all` immediately clears all authorized workspace folders and revokes active filesystem grants without deleting the user's original files on disk.
- **Revoke Credentials:** `DELETE /api/v1/models/keys/{provider}` permanently erases the secret from the OS Credential Vault and deletes its SQLite metadata reference.
