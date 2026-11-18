# AKSA — Remediation Roadmap & Technical Implementation Sequence
**Document ID:** `AKSA-REMEDIATION-ROADMAP-2026-11-18`  
**Date:** 2026-11-18  
**Target:** Engineering, Security, and Quality Assurance Teams  
**Companion Documents:**
- Audit Report: [`docs/audit/AKSA-COMPREHENSIVE-AUDIT-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-COMPREHENSIVE-AUDIT-2026-11-18.md)
- Test Ledger: [`docs/audit/AKSA-AUDIT-TEST-RESULTS-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-AUDIT-TEST-RESULTS-2026-11-18.md)
- Implementation Prompts: [`docs/audit/AKSA-IMPLEMENTATION-PROMPTS-2026-11-18.md`](file:///Users/lpsekudus/Project/aksa/docs/audit/AKSA-IMPLEMENTATION-PROMPTS-2026-11-18.md)

---

## 1. Roadmap Architecture & Priority Taxonomy

Remediation work is strictly sequenced based on technical dependencies and release stage requirements:

```text
Phase 1: P0 Blockers ──────► Phase 2: P1 Core Hardening ──────► Phase 3: P2 & P3 Production GA
 (CI/CD & Supply Chain)       (Rust & Frontend Test Void)        (Neural RAG & Ephemeral OS Ports)
 [Public Beta Unblock]        [Regression Safety Net]            [GA Excellence]
```

### Priority Definitions
- **P0 (Critical / Release Blocker):** Must be resolved immediately before tagging any Public Beta release. Directly breaks automated security pipelines or exposes security vulnerabilities.
- **P1 (High / Architecture & Testing):** Must be resolved before opening to wide unmonitored external beta testing. Fills testing voids and hardens core native logic.
- **P2 (Medium / Enhancements):** Improves user experience, ML retrieval fidelity, and operational telemetry.
- **P3 (Low / Polish & Optimization):** Long-term architectural refinement and edge-case resilience.

---

## 2. Granular Remediation Tasks

### Phase 1: P0 Release Blockers (Immediate Action)

#### Task P0-01: Resolve npm Supply Chain Audit Discrepancy in Security Pipeline
- **Problem Statement:**  
  `.github/workflows/security.yml` line 47 executes `npm audit --audit-level=high` in `apps/desktop`. This command fails with exit code 1 due to 4 high-severity ReDoS vulnerabilities in transitive devDependency `picomatch` (via Vite/fdir/tinyglobby). Meanwhile, production dependencies (`npm audit --omit=dev`) are completely clean (0 vulnerabilities).
- **Affected Files:**
  - [`.github/workflows/security.yml`](file:///Users/lpsekudus/Project/aksa/.github/workflows/security.yml#L45-L47)
  - [`apps/desktop/package.json`](file:///Users/lpsekudus/Project/aksa/apps/desktop/package.json)
- **Technical Remediation:**
  1. Update `.github/workflows/security.yml` to split the audit into two distinct checks:
     - Production scope: `npm audit --omit=dev --audit-level=high` (Strict blocking failure if > 0).
     - Development scope: Run `npm audit fix` in desktop or add an `overrides` section in `package.json` to force `picomatch` to a patched version (`>=2.3.1` or latest fixed release).
- **Acceptance Criteria:**
  - Running `npm audit --prefix apps/desktop --omit=dev` returns 0 vulnerabilities.
  - The security GitHub Actions workflow completes with a green (PASS) status on `push` and `pull_request`.
- **Regression Test:**
  - `npm --prefix apps/desktop run build` continues to build cleanly without bundle size inflation.

---

### Phase 2: P1 Quality Assurance & Native Hardening (Pre-Public Beta)

#### Task P1-01: Native Rust Core Unit Tests (`src-tauri`)
- **Problem Statement:**  
  `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml` currently executes 0 tests. The lifecycle management in `sidecar.rs` (port binding fallback, CSPRNG token creation, child process kill on drop) is completely untested by automated suites.
- **Affected Files:**
  - [`apps/desktop/src-tauri/src/sidecar.rs`](file:///Users/lpsekudus/Project/aksa/apps/desktop/src-tauri/src/sidecar.rs)
  - [`apps/desktop/src-tauri/src/lib.rs`](file:///Users/lpsekudus/Project/aksa/apps/desktop/src-tauri/src/lib.rs)
- **Technical Remediation:**
  1. Add native Rust unit tests in `apps/desktop/src-tauri/src/sidecar.rs` inside a `#[cfg(test)] mod tests` block.
  2. Implement test cases for:
     - `test_allocate_loopback_port_prefers_free_port`: Verifies preferred port is returned when unbound.
     - `test_allocate_loopback_port_fallback_when_busy`: Binds a mock listener to preferred port and asserts fallback port is in range 43121..43199.
     - `test_csprng_token_length_and_prefix`: Verifies token starts with `aksa-` and has expected hex entropy length.
     - `test_lifecycle_state_transitions`: Verifies transitions between `Starting`, `Ready`, `Stopping`, and `Failed`.
- **Acceptance Criteria:**
  - `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml` executes and passes at least 4 unit tests.
- **Regression Test:**
  - `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` continues to compile without warnings.

#### Task P1-02: Automated Frontend Component & Integration Testing (Vitest)
- **Problem Statement:**  
  The desktop frontend relies solely on `tsc --noEmit` and manual verification. There are no automated tests verifying that Zustand stores, chat components, or HMAC challenge handshakes behave properly under error conditions.
- **Affected Files:**
  - [`apps/desktop/package.json`](file:///Users/lpsekudus/Project/aksa/apps/desktop/package.json)
  - [`apps/desktop/vite.config.ts`](file:///Users/lpsekudus/Project/aksa/apps/desktop/vite.config.ts)
  - New test directory: `apps/desktop/src/__tests__/`
- **Technical Remediation:**
  1. Add `vitest` and `@testing-library/react` to `devDependencies` in `apps/desktop/package.json`.
  2. Create automated tests for:
     - `engineConnection.test.ts`: Verifies HMAC challenge-response computation, nonce generation, and fail-closed behavior when token mismatches.
     - `useAksaStore.test.ts`: Verifies message streaming state, step card addition, and active workspace switching.
- **Acceptance Criteria:**
  - `npm --prefix apps/desktop test` executes Vitest and passes 100% of defined scenarios in CI.
- **Regression Test:**
  - Vite production bundle size remains unaffected (dev tools excluded from build).

#### Task P1-03: Physical Hardware Certification on Windows 11
- **Problem Statement:**  
  Auditing was executed on macOS Apple Silicon. Although Windows APIs are thoroughly covered via Python ctypes simulation in `tests/`, actual Win32 DPAPI encryption and COM automation must be validated on physical Windows hardware.
- **Affected Files:**
  - [`services/engine/app/core/credential_vault.py`](file:///Users/lpsekudus/Project/aksa/services/engine/app/core/credential_vault.py)
  - [`services/engine/app/system/permission_broker.py`](file:///Users/lpsekudus/Project/aksa/services/engine/app/system/permission_broker.py)
  - [`services/engine/app/tools/computer_use/gui_agent.py`](file:///Users/lpsekudus/Project/aksa/services/engine/app/tools/computer_use/gui_agent.py)
- **Technical Remediation:**
  1. Execute the full pytest suite and Tauri desktop runner on a physical Windows 11 machine.
  2. Verify that Windows DPAPI (`crypt32.dll:CryptProtectData`) stores credentials securely in `%APPDATA%\AKSA\vault.enc`.
  3. Verify that `pyautogui` mouse/keyboard failsafe behaves properly on multi-monitor high-DPI scaling.
- **Acceptance Criteria:**
  - 166/166 pytest cases pass natively on Windows 11 PowerShell.
  - Windows installer `.msi` installs and runs without DLL loading errors.

---

### Phase 3: P2 & P3 Operational Excellence (Pre-GA)

#### Task P2-01: Pluggable Neural Embedding Models for Local Offline RAG
- **Problem Statement:**  
  The current default offline embedder in `app/rag/store.py` uses lexical n-gram hash projections (`EMBEDDING_DIM = 128`). While lightweight and dependency-free, it has limited abstraction capability for semantic similarity compared to modern transformer models.
- **Affected Files:**
  - [`services/engine/app/rag/store.py`](file:///Users/lpsekudus/Project/aksa/services/engine/app/rag/store.py#L48-L89)
  - [`services/engine/app/rag/ingest.py`](file:///Users/lpsekudus/Project/aksa/services/engine/app/rag/ingest.py)
- **Technical Remediation:**
  1. Implement a pluggable embedding adapter supporting:
     - `lexical` (Current default, zero weight download).
     - `ollama` (Auto-detects running Ollama with `nomic-embed-text` or `bge-m3`).
     - `onnx` (Optional local quantized `bge-small-en-v1.5` or `multilingual-e5-small` via `onnxruntime`).
  2. Allow the user to toggle embedding providers in the RAG Settings view.
- **Acceptance Criteria:**
  - RAG search falls back gracefully to lexical if neural models are unavailable.
  - Semantic retrieval precision increases for paraphrased Indonesian queries.

#### Task P3-01: Ephemeral Port Allocation (Port 0) with Atomic Handshake
- **Problem Statement:**  
  `allocate_loopback_port` in `apps/desktop/src-tauri/src/sidecar.rs` iterates through ports 43121..43199. If all ports in this range are occupied, it returns the preferred port regardless of availability.
- **Affected Files:**
  - [`apps/desktop/src-tauri/src/sidecar.rs`](file:///Users/lpsekudus/Project/aksa/apps/desktop/src-tauri/src/sidecar.rs#L34-L46)
- **Technical Remediation:**
  1. Bind to port `0` (`TcpListener::bind(("127.0.0.1", 0))`), allowing the operating system to assign an available ephemeral port atomically.
  2. Read `listener.local_addr().unwrap().port()` and pass that port to the sidecar process.
- **Acceptance Criteria:**
  - Zero chance of port collisions even if multiple instances or external services run on port 43120..43199.

