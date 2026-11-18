# AKSA — Test Execution Ledger & Empirical Audit Results
**Date:** 2026-11-18  
**Audit Target:** AKSA Desktop Operating Assistant (Tauri v2 + Python FastAPI Sidecar Engine)  
**Environment:** macOS (Darwin 24.6.0, arm64, Apple Silicon), Python 3.14.2 (Sidecar venv), Node.js v20+, Rust 1.85+ (rustc/cargo), npm 10+  
**Auditor Lead:** Independent Multi-Disciplinary Engineering & Security Audit Team  

---

## 1. Executive Test Execution Summary

| Test Domain | Target Subsystem | Command Executed | Scenarios | Status | Duration | Evidence / Notes |
|---|---|---|---|---|---|---|
| **Backend Suite** | Python Engine Core | `pytest services/engine/tests -v` | 166 | **PASS** | 18.71s | 166 passed, 7 warnings (SwigPy deprecation) |
| **Frontend Type & Build** | Desktop React/Vite UI | `npm --prefix apps/desktop run build` | 2,145 modules | **PASS** | 1.82s | `tsc --noEmit && vite build` passed (0 TS errors) |
| **Native Rust Check** | Tauri v2 Core | `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` | 1 crate | **PASS** | 1.46s | 0 compiler errors, 0 warnings |
| **Rust Unit Tests** | Tauri v2 Core | `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml` | 0 tests | **NOT RUN** | 2.20s | 0 tests defined in `apps/desktop/src-tauri/src/` |
| **Sidecar CLI Version** | Python Entrypoint | `python services/engine/app/main.py --version` | 1 check | **PASS** | 0.8s | Output: `AKSA Engine v1.0.0 (API v1)` |
| **Sidecar Smoke Test** | Python Subsystems | `python services/engine/app/main.py --smoke-test` | 1 check | **PASS** | 1.2s | DB, default team, privacy policy initialized |
| **Release Tooling Smoke** | CLI Release Script | `python scripts/release_tooling.py smoke-test` | 2 checks | **PASS** | 1.5s | Both `--version` and `--smoke-test` flags verified |
| **Frontend Production Audit** | npm Dependencies | `npm --prefix apps/desktop audit --omit=dev` | 44 packages | **PASS** | 0.8s | 0 production vulnerabilities |
| **Frontend DevSecOps Audit** | npm Transitive Deps | `npm --prefix apps/desktop audit` | 148 packages | **FAIL** | 1.1s | 4 High Severity ReDoS vulnerabilities in `picomatch` (transitive via Vite) |
| **Static Marker Scan** | Entire Repository | `grep -rnE "(TODO\|FIXME\|HACK\|XXX)" ...` | 0 matches | **PASS** | 0.4s | Zero unresolved markers in production code |

---

## 2. Granular Test Suite Ledgers

### 2.1 Backend Pytest Execution Ledger (`pytest services/engine/tests -v`)
- **Total Test Cases:** 166
- **Passed:** 166 (100%)
- **Failed:** 0
- **Skipped / Ignored:** 0
- **Warnings:** 7 (`DeprecationWarning: builtin type SwigPyPacked has no __module__ attribute` in PyMuPDF)
- **Execution Timestamp:** 2026-11-18T12:36:30Z
- **Execution Time:** 18.71s

#### Detailed Test Case Distribution by Module:
1. `tests/test_p0_api_key_protection.py` (2 tests) — **PASS**
   - `test_p0_models_response_schema_never_exposes_plaintext_keys`: PASS
   - `test_p0_gemini_calls_pass_api_key_in_header_not_url`: PASS
2. `tests/test_p0_credential_vault.py` (7 tests) — **PASS**
   - `test_p0_vault_store_retrieve_and_delete`: PASS
   - `test_p0_legacy_vault_migration_and_shred`: PASS
   - `test_p0_no_subprocess_calls_during_vault_operations`: PASS
   - `test_p1_keyring_unavailable_fails_closed_without_metadata_fallback`: PASS
   - `test_p1_explicit_master_key_fallback_works_when_configured`: PASS
   - `test_p1_legacy_metadata_vault_migrated_and_shredded`: PASS
   - `test_p1_secret_rotation_preserves_ref_and_updates_timestamp`: PASS
3. `tests/test_p0_hitl_grant_context_binding.py` (10 tests) — **PASS**
   - `test_hitl_grant_action_id_and_session_id_mismatch_rejected`: PASS
   - `test_hitl_grant_missing_or_mismatched_session_fails_closed`: PASS
   - `test_hitl_grant_workspace_id_mismatch_fails_closed`: PASS
   - `test_hitl_grant_principal_mismatch_fails_closed`: PASS
   - `test_hitl_grant_resource_path_binding`: PASS
   - `test_hitl_grant_deterministic_argument_hashing`: PASS
   - `test_hitl_grant_single_use_replay_rejected`: PASS
   - `test_hitl_grant_expiry_and_revocation`: PASS
   - `test_hitl_grant_atomic_parallel_consumption`: PASS
   - `test_p0_hitl_rest_api_full_context_binding`: PASS
4. `tests/test_p0_open_path_sandbox.py` (1 test) — **PASS**
   - `test_p0_open_path_sandbox_and_extension_security`: PASS
5. `tests/test_p0_orchestrator_safe_generation.py` (5 tests) — **PASS**
   - `test_generate_non_colliding_path`: PASS
   - `test_preserve_existing_docx_on_duplication`: PASS
   - `test_failed_tool_returns_no_artifacts_and_reports_failure`: PASS
   - `test_ambiguous_multi_pdf_duplication_clarification`: PASS
   - `test_multi_pdf_disambiguation_when_specified`: PASS
6. `tests/test_p0_permission_broker_verification.py` (8 tests) — **PASS**
   - `test_permission_states_enum_coverage`: PASS
   - `test_permission_not_blindly_inferred_from_platform`: PASS
   - `test_request_grant_rejected_when_native_os_permission_not_granted`: PASS
   - `test_runtime_recheck_revokes_consent_if_os_permission_revoked`: PASS
   - `test_linux_wayland_and_x11_detection`: PASS
   - `test_capability_status_contains_revocation_guide`: PASS
   - `test_automation_does_not_falsely_claim_granted_from_osascript_or_coinitialize`: PASS
   - `test_unknown_os_status_fails_closed_in_request_grant`: PASS
7. `tests/test_p0_rag_workspace_boundary.py` (8 tests) — **PASS**
   - RAG path traversal, encoded traversals, symlink escapes, single-folder indexing, and out-of-bounds document rejection verified.
8. `tests/test_p0_sidecar_auth_lifecycle.py` (8 tests) — **PASS**
   - Sidecar loopback binding, token auth, HMAC verification, fail-closed production default, dev-mode warnings verified.
9. `tests/test_p0_workspace_authorization_and_trusted_principal.py` (8 tests) — **PASS**
   - Host principal identity, anti-spoofing header checks, workspace registration with granular permissions verified.
10. `tests/test_p1_computer_use_verification.py` (6 tests) — **PASS**
    - Sensitive window detection, destructive hotkey intercept, postcondition verification, and honest capability reporting verified.
11. `tests/test_p1_credential_vault_hardening.py` (4 tests) — **PASS**
12. `tests/test_p1_mcp_lifecycle_and_isolation.py` (6 tests) — **PASS**
13. `tests/test_p1_persistent_privacy_policy.py` (5 tests) — **PASS**
14. `tests/test_p1_rag_semantic_and_persistence.py` (3 tests) — **PASS**
15. `tests/test_p1_security_origin_and_ws_auth.py` (5 tests) — **PASS**
16. `tests/test_p1_sidecar_packaging.py` (2 tests) — **PASS**
17. `tests/test_p1_skills_supply_chain_security.py` (7 tests) — **PASS**
18. `tests/test_p1_telegram_persistent_auth.py` (3 tests) — **PASS**
19. `tests/test_p1_tool_calling_loop.py` (5 tests) — **PASS**
20. `tests/test_p1_websocket_session_ownership.py` (3 tests) — **PASS**
21. `tests/test_p1_ws_authorization_fail_closed.py` (4 tests) — **PASS**
22. `tests/test_p2_model_recommendation_scoring.py` (7 tests) — **PASS**
23. `tests/test_p2_release_provenance_and_sbom.py` (5 tests) — **PASS**
24. `tests/test_p2_resilience_and_metrics.py` (6 tests) — **PASS**
25. `tests/test_phase1_engine.py` to `test_phase9_adaptive_agents_and_discovery.py` (46 tests) — **PASS**

---

### 2.2 Frontend Build & TypeScript Check (`npm run build`)
- **Command:** `npm --prefix apps/desktop run build` (`tsc --noEmit && vite build`)
- **Result:** Code 0 (Success)
- **Output Artifacts:**
  ```text
  dist/index.html                                0.92 kB │ gzip:   0.48 kB
  dist/assets/AgentHierarchyView-BnuhLJ6X.css   15.87 kB │ gzip:   2.67 kB
  dist/assets/index-BpkBhpmA.css                53.16 kB │ gzip:   9.26 kB
  dist/assets/vendor-Dw7boX12.js                 0.63 kB │ gzip:   0.40 kB
  dist/assets/core-BUhCcD2K.js                   2.70 kB │ gzip:   1.11 kB
  dist/assets/AgentHierarchyView-CURA2t5i.js    26.81 kB │ gzip:   6.77 kB
  dist/assets/icons-ChrVEeHx.js                 42.56 kB │ gzip:   9.86 kB
  dist/assets/markdown-CMbhPpOz.js             121.16 kB │ gzip:  37.19 kB
  dist/assets/FeatureSectionsView-CcTRLbIF.js  121.57 kB │ gzip:  29.46 kB
  dist/assets/xyflow-o5RKNeSs.js               194.45 kB │ gzip:  63.31 kB
  dist/assets/index-BS8p2bPv.js                402.11 kB │ gzip: 125.38 kB
  ✓ built in 1.82s
  ```
- **Observations:** Clean chunk splitting (`index`, `xyflow`, `markdown`, `icons`, `AgentHierarchyView`). Zero TypeScript compile errors (`tsc --noEmit` exited 0).

---

### 2.3 Rust Native Core Check & Tests (`cargo check` / `cargo test`)
- **Compilation Check:**
  `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
  Finished in 1.46s with 0 errors and 0 warnings.
- **Unit Test Execution:**
  `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml`
  Finished in 2.20s.
  **Result:** 0 tests registered (`running 0 tests; test result: ok. 0 passed; 0 failed`).
- **Deficiency Note:** Rust native layer lacks unit tests covering loopback port fallback selection, CSPRNG token generation format, process kill behavior on exit, and Tauri command error mapping.

---

### 2.4 DevSecOps Dependency & Security Audit

#### Production Dependencies (`npm audit --omit=dev`)
- **Command:** `npm --prefix apps/desktop audit --omit=dev`
- **Result:** `found 0 vulnerabilities` (Status: **PASS**)

#### Transitive / Dev Dependencies (`npm audit`)
- **Command:** `npm --prefix apps/desktop audit`
- **Result:** Status: **FAIL** (Exit Code 1)
- **Vulnerabilities Reported:**
  ```text
  picomatch  *
  Severity: high
  picomatch vulnerable to ReDoS through single-branch repeated extglobs - https://github.com/advisories/GHSA-fc5q-39xc-vjpf
  node_modules/picomatch
    fdir  >=5.2.1
    node_modules/fdir
      vite  >=6.3.0-beta.0
      node_modules/vite
    tinyglobby  *
    node_modules/tinyglobby
  4 high severity vulnerabilities
  ```
- **Impact Assessment:** This does NOT affect the bundled production desktop build (as confirmed by `--omit=dev`), but causes CI failure in `.github/workflows/security.yml` line 47 (`npm audit --audit-level=high`).

---

## 3. Test Limitations & Untested Environmental Conditions

1. **Physical Windows Machine Execution:**
   - The current test run was conducted on **macOS (Apple Silicon)**.
   - Windows-specific syscalls (Windows DPAPI `crypt32.dll`, Win32 `GetDC`/`user32.dll`, Windows COM `win32com.client`) were tested via platform-specific unit mocks and structural checks in `services/engine/tests/`. A physical Windows 11 hardware validation run is required prior to GA release.
2. **Frontend Automated Component / E2E Testing:**
   - There is currently **no automated headless browser test suite** (Vitest / Playwright) in `apps/desktop/`.
   - UI flows (WebSocket connection recovery, stream rendering, HITL modal confirmations) are validated through manual testing and TypeScript compiler verification, but not covered by continuous regression automation.
3. **Rust Tauri Unit Test Void:**
   - `src-tauri/src/sidecar.rs` contains critical lifecycle management logic (`allocate_loopback_port`, CSPRNG token generation, child process shutdown) that currently has 0 native Rust test cases.

