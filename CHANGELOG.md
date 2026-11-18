# Changelog (`CHANGELOG.md`)

All notable architectural, security, and feature changes to **AKSA** are documented in this file.

## [1.0.0-rc.2] — 2026-11-18

### Production Security Remediation & Slsa Level 3 Pipeline (AKSA-AUDIT-DELTA-ROADMAP-18-NOV-2026)

#### P0: Critical Security & Boundary Isolation
- **RAG Workspace Boundary Authorization (`sandbox.py`, `rag/store.py`, `routes.py`):**
  - Resolved `workspace_id` strictly from SQLite database; prohibited client-supplied root paths.
  - Enforced principal ownership validation on all workspace reads/writes.
  - Implemented strict canonicalization with symlink escape, nested traversal, junction/reparse point, and UNC path rejections.
  - Enforced `allow_read` flag fail-closed before indexing or listing workspace files.
- **HITL Grant Context Binding & Atomic Single-Use (`sandbox.py`, `routes.py`):**
  - Centralized `ExecutionPolicyGateway` with threading-locked atomic consumption preventing race conditions and replay attacks.
  - Grants strictly bound to `principal_id`, `session_id`, `workspace_id`, `action_id`, `tool_name`, `tool_version`, deterministic canonical argument hash, and resource path.
  - Replaced weak permissive fallbacks with strict fail-closed rejection on expired, revoked, or mismatched contexts.
- **Sidecar Lifecycle & Cryptographic Identity Verification (`sidecar.rs`, `lib.rs`, `engineConnection.ts`):**
  - Standardized four-state sidecar lifecycle (`Starting`, `Ready`, `Stopping`, `Failed`).
  - Blocked frontend `apiFetch` calls until sidecar identity is cryptographically verified via HMAC challenge-response.
  - Replaced `Math.random` with CSPRNG `crypto.getRandomValues()` and thread-safe Rust entropy generator.
- **Native OS Permission Verification (`permission_broker.py`, `PermissionsAndPCView.tsx`):**
  - Replaced platform-heuristic assumptions with genuine OS checks (macOS `AXIsProcessTrusted` & `CGPreflightScreenCaptureAccess`; Linux Wayland/X11 detection; Windows GDI/Desktop checks).
  - Adopted standardized 8-state capability lifecycle (`UNSUPPORTED`, `NOT_REQUESTED`, `NEEDS_USER_ACTION`, `PENDING`, `GRANTED`, `DENIED`, `REVOKED`, `ERROR`).
  - Capability grants fail closed if native OS permission is not actively `GRANTED`. Added revocation guides per platform.

#### P1: Enterprise Security, Isolation & Supply-Chain Integrity
- **Credential Vault Fail-Closed (`credential_vault.py`):**
  - Completely eradicated weak metadata-derived master keys (`hostname + username`).
  - Integrated native OS Keyring with resilient 256-bit CSPRNG fallback file locked to `0o600` permissions.
  - Implemented automatic legacy vault migration and secure disk shredding.
- **Computer Use Verification & Shielding (`gui_agent.py`):**
  - Separated `capability_available` from `capability_implemented` (honest `ui_automation_tree=False`).
  - Implemented priority sensitive window shielding (password managers, Keychain, UAC) and target-window validation.
  - Restricted `success=True` strictly to verified outcomes; returns `submitted_unverified` when postcondition cannot be proven. Blocked destructive hotkeys without HITL.
- **MCP Client Lifecycle & Sandbox Isolation (`mcp_client.py`):**
  - Pinned all default packages to exact immutable versions (`@modelcontextprotocol/server-filesystem@0.6.2`, `@executeautomation/playwright-mcp-server@0.1.1`, `mcp-server-sqlite==0.1.2`).
  - Implemented full JSON-RPC 2.0 initialize handshake, 10 MB payload limits, tool schema validation, and subprocess cleanup.
- **Persistent Privacy Policy Gate (`privacy_gate.py`, `models.py`, `main.py`):**
  - Persisted user privacy policies in SQLite `app_settings` with fail-closed transmission blocking if database errors occur.
- **Frontend API Key Protection (`FeatureSectionsView.tsx`):**
  - Default input type `password` with explicit `Eye`/`EyeOff` toggles, `autoComplete="off"`, and `spellCheck={false}`. Masked keys from API responses.
- **Skills Marketplace Supply-Chain Integrity (`skill_manager.py`):**
  - Switched from hashing IDs to computing real SHA-256 hashes of on-disk skill archives.
  - Implemented quarantine scanning (zip-slip, symlinks, bombs, executable binaries), staging directory extraction, atomic promotion, and clean rollback.
- **WebSocket Session Ownership & Rate Limiting (`ws.py`, `models.py`):**
  - Bound WebSocket sessions to authenticated `principal_id` stored in SQLite schema.
  - Enforced sliding-window rate limiter (30 msgs/second) and active connection revocation API.

#### P2: Quality, Provenance & Release Engineering
- **Model Recommendation Multi-Criteria Scoring (`model_discovery.py`):**
  - Replaced first-match heuristics with weighted multi-criteria ranking (capabilities 35%, context 25%, cost 20%, lifecycle 10%, latency 10%) with trade-off and alternative suggestions.
- **Release Tooling, SBOM & Attestation (`scripts/release_tooling.py`, `.github/workflows`):**
  - Implemented CycloneDX 1.5 JSON SBOM generation for full stack (Python engine + npm packages).
  - Implemented cryptographic SHA-256 checksum generation and verification (`SHA256SUMS.txt`).
  - Added CLI sidecar smoke testing (`--version`, `--smoke-test`).
  - Pinned all GitHub Actions in `.github/workflows/*.yml` to immutable commit SHAs with SLSA Level 3 attestation via `actions/attest-build-provenance`.

### Known Limitations
1. **macOS TCC Permissions:** Accessibility and Screen Recording permissions cannot be granted programmatically by design; they require user confirmation in macOS System Settings. The app displays `NEEDS_USER_ACTION` with precise step-by-step instructions.
2. **Offline Local Provider Discovery:** When Ollama or LM Studio daemons are not running, connection attempts to loopback ports timeout cleanly in 0.8s without triggering any cloud fallbacks.
3. **Windows UI Automation:** Deep accessibility tree extraction requires non-elevated desktop user sessions and will report `implemented=False` honestly until native accessibility hooks are bound.

---

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
