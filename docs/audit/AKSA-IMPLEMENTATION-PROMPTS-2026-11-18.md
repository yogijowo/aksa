# AKSA — Engineering Remediation Implementation Prompts
**Document ID:** `AKSA-IMPLEMENTATION-PROMPTS-2026-11-18`  
**Date:** 2026-11-18  
**Auditor Lead:** Independent Multi-Disciplinary Engineering & Security Audit Team  
**Scope:** Actionable, turnkey implementation prompts for AI coding agents and engineering contributors.  
**Companion Documents:**
- Audit Report: [`docs/audit/AKSA-COMPREHENSIVE-AUDIT-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-COMPREHENSIVE-AUDIT-2026-11-18.md)
- Remediation Roadmap: [`docs/audit/AKSA-REMEDIATION-ROADMAP-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-REMEDIATION-ROADMAP-2026-11-18.md)
- Test Ledger: [`docs/audit/AKSA-AUDIT-TEST-RESULTS-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-AUDIT-TEST-RESULTS-2026-11-18.md)

---

## Instructions for Coding Agents
Each prompt below is an independent, self-contained instruction set designed for an automated coding agent (Antigravity, Cursor, Claude Code, etc.). 
- Always follow the **Language Split Rule** from `AGENTS.md`: Code, comments, identifiers, git commits in **English**; UI strings and notifications in natural **Bahasa Indonesia**.
- Run the specified verification commands after executing changes.
- Never bypass tests or weaken security boundaries.

---

## PROMPT CLUSTER 1: P0 RELEASE BLOCKERS

### PROMPT-P0-01: Fix CI Security Workflow & npm Audit Scoping
```markdown
# TASK: Resolve npm DevSecOps Audit Failure in GitHub Actions Security Workflow

## Context & Problem
During the independent engineering audit on 2026-11-18, `.github/workflows/security.yml` line 47 (`npm audit --audit-level=high`) was found to fail because of a high-severity ReDoS advisory in transitive devDependency `picomatch` (used by `tinyglobby`/`fdir` inside `vite`).
However, production dependencies (`npm audit --omit=dev`) are completely clean (0 vulnerabilities). Because `--omit=dev` is missing in `security.yml`, the security CI pipeline breaks on push and pull requests.

## Scope & Affected Files
1. `.github/workflows/security.yml`
2. `apps/desktop/package.json`

## Requirements
1. In `apps/desktop/package.json`, add an `overrides` or `resolutions` block if possible to pin `picomatch` to a patched release without breaking Vite, OR run `npm audit fix` inside `apps/desktop` to update dependencies safely.
2. In `.github/workflows/security.yml`, update the `Audit Frontend npm lockfile` step:
   - Ensure production dependencies are strictly enforced: `npm audit --omit=dev --audit-level=high`.
   - Add a separate non-blocking or targeted scan for dev dependencies: `npm audit --audit-level=critical || true` or report dev-only advisories as warnings.
3. Verify that `npm --prefix apps/desktop run build` continues to produce the clean production bundle (`tsc --noEmit && vite build`).

## Acceptance Criteria
- [ ] `npm --prefix apps/desktop audit --omit=dev` returns 0 vulnerabilities.
- [ ] `.github/workflows/security.yml` syntax is valid YAML and passes linting.
- [ ] `npm --prefix apps/desktop run build` compiles with 0 TypeScript errors.

## Verification Commands
```bash
npm --prefix apps/desktop audit --omit=dev
npm --prefix apps/desktop run build
```
```

---

## PROMPT CLUSTER 2: P1 CORE HARDENING & QA NETS

### PROMPT-P1-01: Implement Native Rust Core Unit Tests in Tauri (`src-tauri`)
```markdown
# TASK: Add Comprehensive Unit Test Suite for Rust Sidecar Lifecycle Management

## Context & Problem
The independent audit revealed that `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml` executes 0 tests. The critical lifecycle logic in `apps/desktop/src-tauri/src/sidecar.rs` (port fallback, token generation, process cleanup) is currently completely unverified by automated test suites.

## Scope & Affected Files
1. `apps/desktop/src-tauri/src/sidecar.rs`

## Requirements
1. Open `apps/desktop/src-tauri/src/sidecar.rs`.
2. Add a `#[cfg(test)] mod tests` block at the end of the file with the following unit tests:
   a. `test_allocate_loopback_port_prefers_unbound_port`:
      - Call `allocate_loopback_port(54321)` (or a known unused high port).
      - Assert that the returned port is equal to the preferred port.
   b. `test_allocate_loopback_port_fallback_when_busy`:
      - Bind a temporary `std::net::TcpListener` to `("127.0.0.1", 43120)`.
      - Call `allocate_loopback_port(43120)`.
      - Assert that the returned port is in the fallback range `43121..43199`.
      - Drop the temporary listener.
   c. `test_sidecar_state_initialization_and_token`:
      - Initialize `let state = SidecarState::new(43120);`
      - Lock `state.info` and assert that:
        - `auth_token` starts with `"aksa-"`.
        - `auth_token.len() == 69` (prefix `aksa-` + 64 hex characters from two simple UUIDv4s).
        - `host == "127.0.0.1"`.
        - `base_url` starts with `"http://127.0.0.1:"`.
        - `lifecycle_state == LifecycleState::Starting`.
   d. `test_sidecar_state_transitions`:
      - Test transitioning `state.set_state(LifecycleState::Ready)`.
      - Assert `state.get_state() == LifecycleState::Ready`.
      - Transition to `LifecycleState::Stopping`.
      - Assert `state.get_state() == LifecycleState::Stopping`.
3. Ensure no external network or privileged syscalls are required.

## Acceptance Criteria
- [ ] `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml` reports at least 4 tests passed.
- [ ] `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` passes with 0 warnings.

## Verification Commands
```bash
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml -- --nocapture
```
```

---

### PROMPT-P1-02: Setup Automated Frontend Unit & Integration Tests (Vitest)
```markdown
# TASK: Setup Vitest & Add Core Integration Tests for Engine Connection & Store

## Context & Problem
`apps/desktop` currently has no automated test runner configured in `package.json`. Testing is limited to compile-time checking (`tsc --noEmit`). This exposes the application to silent regressions in client-side authentication, HMAC verification, and Zustand store mutations.

## Scope & Affected Files
1. `apps/desktop/package.json`
2. `apps/desktop/vite.config.ts`
3. `apps/desktop/src/__tests__/engineConnection.test.ts` (New file)
4. `apps/desktop/src/__tests__/useAksaStore.test.ts` (New file)

## Requirements
1. Install `vitest` and `@testing-library/react` in `apps/desktop`:
   - Update `apps/desktop/package.json` scripts to include `"test": "vitest run"`.
2. Configure `vite.config.ts` to support Vitest test runner definitions:
   ```typescript
   /// <reference types="vitest" />
   ```
3. Implement `apps/desktop/src/__tests__/engineConnection.test.ts`:
   - Test `generateCryptographicNonce`: verify it produces a 32-character hex string.
   - Test `computeHmacSha256`: compute HMAC for a known key and message, asserting exact hex output.
   - Test `verifyEngineIdentity`: mock `fetch` returning `{ engine: "aksa-engine", nonce_hmac: ... }` and assert that genuine tokens pass while invalid tokens fail closed.
4. Implement `apps/desktop/src/__tests__/useAksaStore.test.ts`:
   - Test initializing store default values.
   - Test adding a message and updating execution steps.
   - Test switching active workspace and teams.

## Acceptance Criteria
- [ ] `npm --prefix apps/desktop run test` executes and passes all test scenarios.
- [ ] `npm --prefix apps/desktop run build` continues to build the production bundle cleanly.

## Verification Commands
```bash
npm --prefix apps/desktop run test
npm --prefix apps/desktop run build
```
```

---

### PROMPT-P1-03: Windows 11 Native Certification & Hardware Validation
```markdown
# TASK: Validate Native Windows 11 Compatibility, DPAPI Storage, and Failsafe Abort

## Context & Problem
AKSA was audited on macOS. Windows-specific code paths (`_dpapi_protect` in `credential_vault.py`, `_check_windows_screen_capture` in `permission_broker.py`, and `pyautogui` failsafe in `gui_agent.py`) require physical validation on Windows 11 PowerShell.

## Scope & Affected Files
1. `services/engine/app/core/credential_vault.py`
2. `services/engine/app/system/permission_broker.py`
3. `services/engine/app/tools/computer_use/gui_agent.py`
4. `scripts/dev.py`

## Requirements
1. Run the full pytest test suite in Windows 11 PowerShell:
   ```powershell
   $env:PYTHONPATH="."
   .\services\engine\.venv\Scripts\pytest services\engine\tests -v
   ```
2. Validate Windows DPAPI:
   - Ensure `ctypes.windll.crypt32.CryptProtectData` successfully encrypts and decrypts credentials without showing any UI prompt (`CRYPTPROTECT_UI_FORBIDDEN = 1`).
   - Verify secrets are stored in `%APPDATA%\AKSA\vault.enc`.
3. Validate Computer Use Failsafe:
   - Verify that moving the mouse cursor to the top-left screen corner `(0, 0)` immediately triggers `pyautogui.FailSafeException` and halts any active Tier 3 action.
4. Package and test the Windows installer:
   ```powershell
   npm --prefix apps/desktop run tauri build
   ```
   - Verify the generated `.msi` or `.exe` installer installs and launches cleanly without missing DLL errors.

## Acceptance Criteria
- [ ] 166/166 pytest cases pass in native Windows 11 environment.
- [ ] Windows DPAPI encryption/decryption roundtrip succeeds without fallback errors.
- [ ] Tauri build succeeds and generates clean installer.
```

---

## PROMPT CLUSTER 3: P2 & P3 OPERATIONAL EXCELLENCE

### PROMPT-P2-01: Implement Pluggable Neural Embedding Models in Hybrid RAG
```markdown
# TASK: Implement Pluggable Local Neural Embeddings (Ollama / ONNX) for RAG Store

## Context & Problem
The current default embedder (`LexicalNgramEmbedder` in `services/engine/app/rag/store.py`) uses a 128-dimensional MD5 n-gram hash projection with Indonesian synonym expansion. While completely offline and zero-download, it cannot capture deep semantic nuance for complex, conceptual queries.

## Scope & Affected Files
1. `services/engine/app/rag/store.py`
2. `services/engine/app/rag/ingest.py`
3. `services/engine/app/config.py`

## Requirements
1. In `services/engine/app/rag/store.py`, create an `AbstractEmbedder` base class and implement:
   - `LexicalNgramEmbedder`: The lightweight offline default (128-dim, MD5 hash).
   - `OllamaEmbedder`: Queries a local Ollama instance at `http://localhost:11434/api/embeddings` using models such as `bge-m3` or `nomic-embed-text`.
   - `OnnxEmbedder` (optional/pluggable): Loads a local quantized ONNX model using `onnxruntime` if model weights exist in `appdata/models/`.
2. Add a configuration setting in `settings.rag_embedding_mode` (`"lexical" | "ollama" | "onnx"`).
3. If `"ollama"` or `"onnx"` fails or is unreachable, fail safe by falling back to `LexicalNgramEmbedder` with a warning log, ensuring zero downtime.
4. Update `HybridRAGStore` to use the configured embedder dynamically.
5. Add unit tests in `services/engine/tests/test_p1_rag_semantic_and_persistence.py` verifying fallback behavior.

## Acceptance Criteria
- [ ] Default configuration remains 100% offline and zero-dependency (`lexical`).
- [ ] Switching to `ollama` with a running Ollama server computes dense float32 vectors.
- [ ] Unreachable Ollama server falls back cleanly to lexical without throwing unhandled exceptions.
- [ ] All existing RAG tests continue to pass.

## Verification Commands
```bash
PYTHONPATH=. ./services/engine/.venv/bin/pytest services/engine/tests/test_p0_rag_workspace_boundary.py services/engine/tests/test_p1_rag_semantic_and_persistence.py -v
```
```

---

### PROMPT-P3-01: Ephemeral OS Port 0 Allocation with Dynamic Handshake
```markdown
# TASK: Enhance Sidecar Loopback Binding with OS-Assigned Ephemeral Port (Port 0)

## Context & Problem
Currently, `SidecarState::new(43120)` in `apps/desktop/src-tauri/src/sidecar.rs` iterates through loopback ports 43121..43199 if 43120 is busy. In rare edge cases where a firewall or local service blocks or occupies this entire range, the sidecar may fail to launch.

## Scope & Affected Files
1. `apps/desktop/src-tauri/src/sidecar.rs`
2. `apps/desktop/src/services/engineConnection.ts`

## Requirements
1. Update `allocate_loopback_port` in `sidecar.rs`:
   - If preferred port `43120` is busy, bind to `("127.0.0.1", 0)`.
   - The OS kernel will instantly assign an available ephemeral port.
   - Extract the assigned port via `listener.local_addr().unwrap().port()`.
   - Drop the listener and return the dynamic port.
2. Verify that Tauri's `invoke("get_engine_connection_info")` seamlessly communicates the dynamically assigned port to the frontend webview.

## Acceptance Criteria
- [ ] The engine binds cleanly even if ports 43120..43199 are all occupied.
- [ ] Tauri IPC command `get_engine_connection_info` returns the dynamic port and the webview connects without issues.
- [ ] Rust unit tests pass.

## Verification Commands
```bash
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
```
```

