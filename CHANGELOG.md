# Changelog (`CHANGELOG.md`)

All notable architectural, security, and feature changes to **AKSA** are documented in this file.

## [1.0.0] — 2026-11-17

### Security & Enterprise Baseline (P0 / P1 Remediation)
- **OS Credential Vault (`credential_vault.py`):** Migrated API keys from SQLite plaintext JSON into Windows DPAPI (`CryptProtectData`) / macOS Keychain / Sealed Vault. SQLite `credentials_metadata` now stores only `credential_ref` and masked previews.
- **Zero Local-to-Cloud Fallback (`llm_router.py`, `privacy_gate.py`):** Added `ProviderMode` (`local_only`, `cloud_by_choice`, `hybrid_with_consent`, `enterprise_managed`). Local models (`Ollama`, `LM Studio`) never fall back to cloud providers under any condition.
- **Data Disclosure Gate & Classification (`privacy_gate.py`, `orchestrator.py`):** Added `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, and `RESTRICTED` classification tiers. Removed automatic workspace PDF attachment; external document disclosure now requires explicit user consent.
- **ExecutionPolicyGateway & Bound One-Time Approvals (`sandbox.py`):** Actively rejects forbidden public override fields (`execution_policy_override`, `skip_approval`, `is_admin`, `force_allow`). Bound approvals to canonical SHA-256 argument hashes, session ID, workspace ID, tool version, and expiration with one-time atomic consumption.
- **Workspace Isolation & Revocation (`sandbox.py`, `models.py`):** Removed implicit `workspaces[0]` fallback, blocked UNC network paths (`\\server\share`) and NTFS Alternate Data Streams, preserved read-only workspace flags during orchestration, and added `POST /api/v1/workspaces/revoke-all`.
- **Loopback API & WebSocket Hardening (`main.py`, `ws.py`, `sidecar.rs`):** Enforced loopback Host/Origin allowlists (preventing DNS rebinding), 10 MB request body limits, 64 KB WebSocket frame limits, per-session WebSocket ownership (preventing cross-session subscription hijacking), and dynamic loopback port allocation in Rust.

### OS Integration & Extensibility
- **Honest Application Discovery (`app_discovery.py`, `ApplicationsView.tsx`):** Removed hardcoded fallback app records; added `launch_status` verification (`not_launchable` when `InstallLocation` is empty), confidence scoring, integration categories, and offline/online Connect/Disconnect authorization toggles.
- **Two-Layer Permission Broker (`permission_broker.py`):** Separated `OSPermissionState` from `AKSAConsentState` (`NOT_GRANTED`, `GRANTED_SCOPED`, `REVOKED`, `EXPIRED`).
- **Platform Computer Use Adapters (`gui_agent.py`):** Implemented `WindowsComputerUseAdapter` and `MacOSComputerUseAdapter` with sensitive window blocking (password managers, credential dialogs, UAC, Keychain) and precondition/postcondition verification.
- **Secure Agent Skills & MCP Runtime (`skill_manager.py`, `mcp_client.py`):** Added zip-bomb, symlink, case-collision, and prompt-injection quarantine checks; `aksa.skill.yaml` manifest generation; automatic grant revocation upon skill uninstall; and scrubbed subprocess environments (`build_isolated_mcp_env`) for MCP servers.
- **Observability & Support Bundle (`observability.py`):** Implemented structured log redaction and `GET /api/v1/system/diagnostics/support-bundle`.
