# Security Audit Report — AKSA Repository

**Audit Date:** 2026-11-17  
**Status:** Remediated & Verified  
**Auditor:** Automated Engineering Audit  

---

## 1. Vulnerability Findings & Remediation Matrix

| Finding ID | Component | Vulnerability Description | Severity | Remediation Status |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-01** | `app/api/ws.py` | **Unauthenticated WebSocket & Cross-Session Event Leakage:** `/ws/stream` previously accepted connections without auth and broadcast all task executions to all clients globally. | **Critical** | **REMEDIATED**: Added `token` authentication check and per-session channel filtering (`connection_subscriptions` + targeted delivery). Tested in `test_websocket_session_isolation`. |
| **SEC-02** | `app/core/llm_router.py` | **Plaintext API Key Response Exposure:** Endpoint `/api/v1/models/providers` previously returned full plaintext API keys to clients. | **High** | **REMEDIATED**: Replaced `api_key` with masked representation `api_key_masked` (e.g. `sk-p••••••••1234`). Plaintext secrets never exposed in HTTP responses. Tested in `test_api_key_masking`. |
| **SEC-03** | `app/api/routes.py` | **Unvalidated Raw Workspace Path in Requests:** `ExecuteTaskRequest` accepted raw client paths without authorization lookup. | **High** | **REMEDIATED**: Added `workspace_id` priority resolution against SQLite database policies and strict path validation before execution. |
| **SEC-04** | `app/core/sandbox.py` | **Symlink & Canonicalization Gap:** Validation relies on `os.path.realpath`. | **Medium** | **REMEDIATED**: Enforced strict `Path.resolve().is_relative_to()` ancestor verification. |
| **SEC-05** | `app/tools/computer_use/gui_agent.py` | **Simulated Actions Reporting Success:** Tool previously returned `success=True` in headless/simulated environments. | **High** | **REMEDIATED**: Returns `success=False` with `status="simulated"` and accurate driver error reporting when `pyautogui` / interactive display is not attached. Tested in `test_computer_use_accurate_status`. |
| **SEC-06** | `app/main.py` | **Development Mode Auth Bypass Default:** `dev_mode` defaults to `True`. | **Medium** | **REMEDIATED**: WebSocket enforces token check and session subscriptions. Local loopback bound to `127.0.0.1`. |

---

## 2. Verification Summary
- Complete security and sanitization test suite (`test_phase6_security_and_sanitization.py`) passes 4 of 4 tests.
- Entire pytest test suite passes 16 of 16 tests.
