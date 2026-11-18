# AKSA — QC Production-Readiness Audit & Remediation Instructions

**Audit date:** 2026-11-18
**Audited revision:** `origin/main` @ `e38252d` (feat(learning): adaptive agent learning…)
**Auditor role:** Senior System QC (static code review + local runtime checks on macOS arm64)
**Verdict:** **NOT production-ready.** The `PROGRESS.md` label "Release Candidate" is inaccurate. The test suite (41/41) passes, but it does not cover the packaged app, the real auth flow between UI and engine, or the agent's real behavior.

> [!IMPORTANT]
> **Scope and limitations.** This was a static review plus local runtime checks: `pytest`, `vite build`, `curl` against the dev engine. It was **not** a penetration test. It did **not** include a packaged `.dmg`/`.msi` run or a Windows host run. Every finding below cites a file and line from this revision. Fix the P0 items before any external user touches the app.

---

## How to use this document

1. Work strictly in priority order: **P0 → P1 → P2 → P3**.
2. Each item has a **Problem**, the **Evidence** for it, the **Fix** to make, and **Acceptance criteria** (how to prove it is fixed). Do not mark an item done until every acceptance check passes.
3. After each item, update `PROGRESS.md` (per `AGENTS.md` §4). Never write "Release Candidate" until every P0 and P1 item is closed.
4. Add a regression test for every fixed item under `services/engine/tests/` (or a frontend test where noted).

---

## Summary table

| ID | Severity | Area | Title |
|---|---|---|---|
| P0-1 | Critical | Security | `/system/open-path` can open or execute any file on the machine |
| P0-2 | Critical | Security / Arch | The packaged app has no working auth: UI never sends the token, and the sidecar is never spawned |
| P0-3 | Critical | Security | The engine starts in **no-auth dev mode** by default |
| P0-4 | Critical | Security | Raw API keys were exposed to the UI (check the regression), and the Gemini key is sent in the URL query |
| P0-5 | Critical | Crypto | Home-made encryption; the vault key sits next to the vault; the Keychain secret goes through argv |
| P0-6 | Critical | Data integrity | The orchestrator silently **overwrites user files** and reports fake success |
| P1-1 | High | Function | The agent has no real tool-calling: keyword heuristics decide what files get made |
| P1-2 | High | Security | Origin/Host allow-list contains test bypasses in production |
| P1-3 | High | Security | Token comparison is not constant-time; `/docs` and `/openapi.json` are public |
| P1-4 | High | Packaging | The sidecar binary is a dev shell script that depends on the repo `.venv` |
| P1-5 | High | Frontend | Hardcoded engine URL/port; the dynamic port from Tauri is ignored |
| P1-6 | High | Privacy | PDFs are auto-attached to cloud LLM calls on loose keyword matches |
| P1-7 | High | Function | The "semantic" RAG embedder is MD5 n-gram hashing, not semantic search |
| P1-8 | High | State | The Telegram whitelist and pairing live only in memory and are lost on restart |
| P2-1 | Medium | Function | Sub-agents produce text only; token "savings" numbers are simulated |
| P2-2 | Medium | Function | Ollama → cloud fallback breaks the "local/private" promise |
| P2-3 | Medium | Reliability | No request rate limiting or concurrency guard on `/orchestrate/execute` |
| P2-4 | Medium | Supply chain | No Python lockfile; unpinned dependency ranges |
| P2-5 | Medium | Frontend | Persistence in `localStorage` drifts from SQLite; hardcoded user paths |
| P2-6 | Medium | Observability | Error messages leak internal exceptions to the client |
| P2-7 | Medium | Testing | Tests do not cover the real UI↔engine auth, the packaged sidecar, or file-overwrite safety |
| P3-1 | Low | Code quality | `routes.py` (1014 LOC) and `models.py` (1015 LOC) are too large |
| P3-2 | Low | Frontend | 900 KB single JS chunk; no code splitting |
| P3-3 | Low | Docs | `PROGRESS.md` overstates release status |

---

## P0 — Critical (release blockers)

### P0-1 — `/system/open-path` can open or execute any file on the machine

**Problem.** The endpoint takes any absolute path and passes it to `open` (macOS), `os.startfile` (Windows), or `xdg-open`. Nothing restricts the path to authorized workspaces. Nothing filters file types. A malicious prompt, skill, MCP server, or any local process that can reach the port can do things like:
- run `.app`, `.command`, `.terminal`, `.sh`, `.bat`, `.exe`, `.lnk`, or `.url` files;
- open `file://` and URL handlers.

This bypasses the HITL gate and breaks the "workspace sandbox first" rule in `AGENTS.md`.

**Evidence.** `services/engine/app/api/routes.py` ~L300–330 (`open_system_path`). There is no call to `sandbox_manager.validate_path`.

**Fix.**
1. Resolve the path with `sandbox_manager.validate_path(req.path, operation="read")`. Reject with 403 if the result is outside the registered workspaces.
2. Reject symlinks whose real target is outside the workspace. Reject UNC/network paths.
3. Enforce an **allow-list of extensions**: `.docx .xlsx .pptx .pdf .txt .csv .md .png .jpg`. Return 400 for everything else. Never allow directories that are app bundles (`*.app`).
4. Only allow opening files that are recorded artifacts, or that were listed by `/workspaces/{id}/files`.
5. Write an audit entry for each open, using the existing observability/audit module.
6. Prefer moving this action to the Tauri side (`tauri-plugin-opener` with a scoped allow-list). That way the Python engine never launches GUI processes.

**Acceptance.**
- `POST /system/open-path {"path":"/Applications/Calculator.app"}` → 403.
- `{"path":"/etc/hosts"}` → 403.
- `{"path":"<workspace>/x.command"}` → 400.
- `{"path":"<workspace>/report.docx"}` → 200.
- New pytest file: `test_open_path_sandbox.py`.

---

### P0-2 — The packaged app has no working auth: UI never sends the token, and the sidecar is never spawned

**Problem.**
- `apps/desktop/src-tauri/src/sidecar.rs` generates a per-launch token and a port. But `child_process` is never assigned: **the engine is never spawned by Tauri**, and the token is never passed to the engine.
- `apps/desktop/src/services/engineClient.ts` never sends `X-AKSA-Auth-Token` and never calls `get_engine_connection_info`.

The result: in production mode (`dev_mode=False`) **every API call returns 401**. In dev mode there is no auth at all. Either the app is broken, or it is unauthenticated. There is no secure working state.

**Evidence.**
- `sidecar.rs` L37–60: `child_process: Mutex::new(None)`, with no spawn.
- `engineClient.ts` L12: `DEFAULT_BASE_URL` is hardcoded; there are no auth headers anywhere.
- `grep invoke( src` → no calls.

**Fix.**
1. In `lib.rs` `setup()`, spawn the sidecar with `tauri-plugin-shell` `Command::sidecar("aksa-engine")`. Pass these arguments:
   - `--port <allocated>`
   - `--production`
   - the token through an **environment variable** (`AKSA_AUTH_TOKEN`), not argv.
2. Store the `CommandChild` in `SidecarState.child_process`. Kill it on `RunEvent::Exit`.
3. Health-check `/api/v1/health` with retries (max ~15 s). Then emit an `engine-ready` event to the webview.
4. In the frontend, create `src/services/engineConnection.ts`:
   - On startup, `invoke("get_engine_connection_info")` (falling back to `import.meta.env` in browser dev).
   - Cache `{baseUrl, wsUrl, token}`.
5. Wrap every `fetch` in a single `apiFetch()` helper that adds the `X-AKSA-Auth-Token` header. Pass the WebSocket token as `?token=`. Better: send it as the first-message auth frame instead of the query string (see P1-3).
6. Remove the hardcoded `DEFAULT_BASE_URL` usage everywhere.

**Acceptance.**
- A packaged build (`npm run tauri build`) launches. The engine process appears and dies with the app.
- All views load data.
- `curl` without the token → 401.
- Killing the app leaves no orphan Python process.

---

### P0-3 — The engine starts in no-auth dev mode by default

**Problem.**
- In `app/main.py` `__main__`: `--auth-token` defaults to `"dev-aksa-local-token"`, and `settings.dev_mode = not args.production`. Running `python -m app.main` (which is exactly what the sidecar wrapper does) therefore starts **unauthenticated**.
- `scripts/dev.js` also forces `AKSA_DEV_MODE=1`.
- Any local process or malicious web page can drive the agent. DNS-rebinding is mitigated only by the Host check, which has its own bypass (P1-2).

**Evidence.** `main.py` L125–137; `config.py` `_resolve_auth_token`.

**Fix.**
1. Invert the default: production is the default; dev requires an explicit `--dev` flag **and** `AKSA_DEV_MODE=1`.
2. Remove the static token default. If no token is provided in production, refuse to start. Do not auto-generate a token nobody knows.
3. Even in dev mode, keep auth on and use a random token that `scripts/dev.py` passes to Vite via `VITE_AKSA_TOKEN`. Dev and prod then exercise the same code path.
4. Log a loud warning banner if dev mode is ever active.

**Acceptance.**
- `python -m app.main` with no env → exits with a clear error.
- `npm run dev` still works end-to-end, with auth headers present.

---

### P0-4 — Raw API keys were exposed to the UI (check the regression), and the Gemini key is sent in the URL query

**Problem.**
- An earlier local change made `/api/v1/models/providers` return the plaintext `api_key` so the UI could display it. Upstream now uses `masked_preview`. **Verify this regression cannot come back.** The browser must never receive a full secret. Any XSS, extension, or local process could read it from the unauthenticated endpoint.
- Gemini calls put the key in the URL: `?key={api_key}`. URLs end up in proxy logs, httpx debug logs, and exception messages, for example `httpx.HTTPStatusError` includes the URL.

**Evidence.**
- `core/llm_router.py` L450.
- `core/model_discovery.py` L153.

**Fix.**
1. Send the Gemini key in the `x-goog-api-key` header for both the completion and the discovery calls.
2. Add a response-schema test that asserts **no field** of any `/models/*` response matches `^(sk-|AIza|gsk_|sk-ant-)` or is longer than 12 characters for a key field.
3. The UI shows only `masked_preview` plus a "Replace key" action. A "reveal" button must not exist. If the business really requires one, implement it as a Tauri command that reads from the OS keychain after OS re-authentication, never over HTTP.
4. Scrub URLs and query strings in every logged or returned exception (`observability.redact`).

**Acceptance.**
- `grep -rn "?key=" services/engine/app` → no results.
- The new test passes.
- An exception path returns no key material.

---

### P0-5 — Home-made encryption; the vault key sits next to the vault; the Keychain secret goes through argv

**Problem.** `core/credential_vault.py`:
- The fallback "sealed_local_vault" is a home-made HMAC-CTR stream cipher. **The same key is used for encryption and for the MAC.** The master key is stored in plaintext as `.vault_master_key` next to the vault file. This is obfuscation, not protection.
- On macOS the secret is written to the Keychain **and also** to the file vault. That defeats the purpose of the Keychain.
- The Keychain write passes the secret on the command line (`security add-generic-password … -w <secret>`), where any user can see it via `ps`.

**Fix.**
1. Replace everything with the `keyring` library: macOS Keychain, Windows Credential Manager/DPAPI, Linux Secret Service. Store the secret **only** in the OS store. In SQLite, keep only `credential_ref` and `masked_preview`.
2. If a file fallback is unavoidable on Linux with no Secret Service, use `cryptography`'s `AESGCM` with a key derived from an OS-protected source. Show a visible "reduced security" warning in Settings.
3. Remove every `subprocess` call to `security`.
4. Migrate existing entries: read old ones, re-store them via `keyring`, then securely delete `vault.json` and `.vault_master_key`.
5. Add `keyring` and `cryptography` to `pyproject.toml`.

**Acceptance.**
- After saving a key, there is no secret anywhere under the AppData dir: `grep -r AIza ~/Library/Application\ Support/com.aksa.desktop` → nothing.
- `ps` never shows the secret.
- A migration test passes.

---

### P0-6 — The orchestrator silently overwrites user files and reports fake success

**Problem.** `core/orchestrator.py` L401–520:
- **Duplication writes `<pdf_stem>.docx` without checking whether it exists.** A user's real, hand-edited `Report.docx` is destroyed without warning. The fixed names `Dokumen_Resmi_AKSA.docx`, `Rekap_Otomatis_AKSA.xlsx`, and others are overwritten on every request.
- If the tool fails, the artifact is still reported, with a hardcoded `size_label = "42 KB"`. The LLM is then instructed to "confirm confidently" that the file is ready (`action_confirmation_note`).
- "Duplicate" always picks the **first** PDF in the folder, not the one the user meant.
- Generic requests produce a **blank template** document that has nothing to do with what the user asked for.

**Fix.**
1. Never overwrite. Generate a unique name: `name (1).docx`, or `name_YYYYMMDD-HHMMSS.docx`. If overwriting really is intended, require HITL approval and rely on the existing auto-backup.
2. Report an artifact **only** if `res.success and target.exists() and target.stat().st_size > 0`. Otherwise return a structured failure, and tell the LLM the operation failed so it explains the failure honestly.
3. Delete the hardcoded size labels; always compute the size from the file.
4. Source selection:
   - if exactly one PDF exists, use it;
   - if more than one exists, match against filenames in the prompt;
   - if still ambiguous, return a clarification question **and create nothing**.
5. Remove the blank-template generation path entirely. Either the agent produces real content (P1-1), or it creates nothing.

**Acceptance.** New tests:
- An existing `X.docx` is preserved after a duplication request.
- A failed tool returns no artifact, and the reply contains a failure message.
- With two PDFs and an ambiguous prompt, a clarification is returned and the workspace is unchanged.

---

## P1 — High

### P1-1 — The agent has no real tool-calling: keyword heuristics decide what files get made

**Problem.** The LLM never chooses or calls tools. The orchestrator scans the prompt for substrings ("buat", "word", "ubah", "rekap"…) and runs fixed tools with fixed arguments. Consequences:
- "ubah" ("change") or "salin" ("copy") in any sentence triggers file generation.
- Real requests ("buat tabel penjualan dari data.csv", "make a sales table from data.csv") produce an empty workbook.
- The `ToolRegistry` and its lazy loading exist, but the model never sees them.

This is the core functional gap between the product promise (an autonomous agent) and the actual behavior.

**Fix.**
1. Implement native function-calling in `UnifiedLLMRouter.complete(..., tools=[...])`:
   - Gemini: `tools.functionDeclarations`
   - OpenAI/DeepSeek/Groq/OpenRouter: `tools`
   - Anthropic: `tools`
   - Ollama: `tools`, for models that support it
2. Build schemas from the `ToolRegistry`, which already has Pydantic models. Respect lazy loading: expose only the agent's `tool_categories`.
3. Write the orchestrator loop:

   ```text
   LLM → tool_calls → sandbox/HITL check → execute → ToolResult (compact) → LLM … (max N steps, budget guard)
   ```

4. Route every tool call through `sandbox_manager` and the HITL gate. Risky tools (write/overwrite/delete/execute/computer-use) require approval.
5. Delete the keyword heuristic block (L401–520).
6. Stream each step over the WebSocket (`tool_started`, `tool_finished`, `approval_required`).

**Acceptance.** End-to-end tests with a mocked LLM that emits tool calls:
- A CSV becomes an Excel file with a SUM row.
- "ubah nada jawabanmu" ("change your tone") creates no file.
- A write outside the workspace is denied.

---

### P1-2 — Origin/Host allow-list contains test bypasses in production

**Problem.**
- `ALLOWED_HOSTS` includes `"test"` and `"testserver"`.
- The Origin check accepts **any** origin that starts with `http://test`. For example, `http://test.attacker.com` is accepted. That re-opens CSRF/DNS-rebinding paths.
- Requests with no Origin header are accepted.

**Evidence.** `app/main.py` L31–38 and L71–80.

**Fix.**
- Build the allow-lists from settings. Add the test hosts and origins only when `settings.testing` is true (set it in the pytest `conftest`, never at runtime).
- In production, require an Origin that exactly matches the Tauri origins for state-changing methods (`POST`, `PUT`, `PATCH`, `DELETE`). The token still guards non-browser callers.

**Acceptance.**
- `Origin: http://test.evil.com` → 403 in production mode.
- The existing tests still pass with the testing flag.

---

### P1-3 — Token comparison is not constant-time; `/docs` and `/openapi.json` are public

**Fix.**
- Use `secrets.compare_digest(token, settings.auth_token)` in both the HTTP middleware and the WebSocket handler.
- Disable `docs_url`, `redoc_url`, and `openapi_url` when not in dev mode.
- Stop sending the WebSocket token in the query string, because query strings are logged. Authenticate with the first JSON frame within 3 s, or close with code 4001.

**Acceptance.**
- `/docs` → 404 in production.
- The WebSocket works with frame auth.
- `grep -n "token != settings" app` → no results.

---

### P1-4 — The sidecar binary is a dev shell script that depends on the repo `.venv`

**Problem.** `src-tauri/binaries/aksa-engine-aarch64-apple-darwin` is a bash script that walks up four directories to find `services/engine/.venv`. A shipped `.dmg`/`.msi` has no such path. The app cannot work on any other machine. Also, no Windows (`x86_64-pc-windows-msvc.exe`) or Intel macOS binary exists.

**Fix.**
1. Build a frozen engine with PyInstaller or Nuitka (`--onefile` or `--onedir`) for each target triple in CI:
   - `aarch64-apple-darwin`
   - `x86_64-apple-darwin`
   - `x86_64-pc-windows-msvc`
2. Add a `scripts/build_sidecar.py` and a GitHub Actions matrix job. Upload the binaries as build inputs to `tauri build`.
3. Code-sign and notarize the sidecar together with the app (macOS hardened runtime entitlements; Windows Authenticode).

**Acceptance.** A fresh macOS VM with no Python installed can run the `.dmg`, and chat works.

---

### P1-5 — Hardcoded engine URL/port; the dynamic port from Tauri is ignored

**Problem.** `engineClient.ts` hardcodes `http://127.0.0.1:43120`. `sidecar.rs` allocates a different free port when 43120 is busy, which leaves the UI pointing at a dead or foreign port. A foreign process on 43120 could also impersonate the engine and receive prompts and documents.

**Fix.**
- Covered by the P0-2 connection service.
- Additionally, verify engine identity: `/api/v1/health` should return an HMAC of a nonce computed with the shared token. The UI rejects mismatches.

**Acceptance.** Occupy port 43120 with `nc -l 43120`, launch the app → it works on another port.

---

### P1-6 — PDFs are auto-attached to cloud LLM calls on loose keyword matches

**Problem.** The orchestrator attaches up to two workspace PDFs as base64 when the prompt contains words like "apa" ("what"), "isi" ("contents"), "cek" ("check"), "dokumen" ("document"). Upstream added a privacy gate; verify it is applied. Even so, a plain "apa kabar?" ("how are you?") can upload confidential government documents to a cloud provider without explicit consent.

**Evidence.** `core/orchestrator.py` ~L280–300 (`attachments.append`).

**Fix.**
1. Never auto-attach. Attach only files the user explicitly selected (an attachment chip in the composer), or files a tool call explicitly requests via `read_document`.
2. Before sending any file to a **cloud** provider, enforce the data-classification gate:
   - Confidential or Restricted files → blocked, or require a per-file approval dialog.
   - Local-only mode → hard block.
3. Prefer sending extracted text plus page references over the raw PDF bytes.

**Acceptance.** "apa kabar?" sends zero attachments (assert on a mocked router). A Confidential PDF to a cloud provider → approval required.

---

### P1-7 — The "semantic" RAG embedder is MD5 n-gram hashing, not semantic search

**Problem.** `rag/store.py` `MultilingualEmbedder` hashes character n-grams with MD5 into a vector. That is lexical similarity, not semantic. The "vector store" is a JSON file (`vectors_index.json`) loaded fully into memory: O(n) scan, no concurrency safety, corruption risk on crash. The docs and UI promise LanceDB hybrid semantic search.

**Fix.**
1. Use a real embedding model:
   - Local: `bge-m3`, `multilingual-e5-small`, or `nomic-embed-text` via Ollama, or `fastembed` (ONNX) to ship offline.
   - Cloud: optional and classification-gated.
2. Store vectors in LanceDB, as specified in `docs/04-RAG-AND-MEMORY-SYSTEM.md`, or in `sqlite-vec`. Write atomically.
3. Keep FTS5 for keywords plus RRF fusion (already present).
4. If you ship the hashing embedder as an interim step, **rename it** and stop calling it "semantic" in the UI and docs.

**Acceptance.** A test query using synonyms ("anggaran" ↔ "pagu", both meaning "budget") retrieves the right chunk. A crash mid-ingest leaves a consistent index.

---

### P1-8 — The Telegram whitelist and pairing live only in memory and are lost on restart

**Problem.** `telegram/auth.py` keeps `_allowed_user_ids` in a Python `set`. After a restart, paired users are dropped, and pairing may silently re-open.

**Fix.**
- Persist the whitelist in SQLite (`telegram_allowed_users`).
- Make pairing codes single-use, valid for 5 minutes, limited to 5 attempts, then locked.
- Log every pair and unpair action to the audit log.
- Require desktop-side confirmation for a new pairing.

**Acceptance.** Pair, restart the engine, and the user is still authorized. A brute-force of 6 attempts results in a lockout.

---

## P2 — Medium

### P2-1 — Sub-agents produce text only; token "savings" numbers are simulated
`compact_subagent_handback(..., Simulated_document_tokens_processed=3800 if … else 1800)` reports invented savings. The UI shows "Hemat 90%" ("90% saved") based on constants.

**Fix.** Compute savings from real measured token counts (provider usage fields) versus a baseline that is defined and documented. Rename the parameter. Hide the metric until it is real.

**Acceptance.** The numbers equal the sum of real `usage` values in the logs.

### P2-2 — Ollama → cloud fallback breaks the "local/private" promise
When Ollama is offline, a request for an agent configured as local can be routed to a cloud provider (the router fallback logic). Users choose local models specifically for privacy.

**Fix.**
- Never fall back from local to cloud.
- Fail with a clear Indonesian message: "Ollama belum berjalan…" ("Ollama is not running yet…").
- Cloud-to-cloud fallback is allowed only if the user enables it in Settings, and it is shown in the step trace.
- Verify `PrivacyPolicyGate` covers every path.

**Acceptance.** A test with Ollama down, a local agent, and a Gemini key present → error, with zero cloud calls.

### P2-3 — No rate limiting or concurrency guard
`/orchestrate/execute` can run unbounded parallel LLM and tool jobs, which burns API quota and causes file races.

**Fix.**
- Add a per-session `asyncio.Semaphore(1)` and a global limit (e.g. 3).
- Add a request timeout and cancellation (the emergency-stop endpoint must cancel running tasks).
- Add a per-day token budget in Settings.

### P2-4 — No Python lockfile; unpinned dependency ranges
There is no `uv.lock` or `requirements.lock`. `pip install -e .` pulled `litellm 1.109`, `openai 3.x`, and others. Builds are not reproducible, and the supply-chain risk is high (litellm is large and changes often; it is barely used now that native REST connectors exist).

**Fix.**
- `uv lock` and commit `uv.lock`.
- Pin upper bounds.
- Remove `litellm` if it is unused.
- Add `pip-audit` and `npm audit --omit=dev` to CI.
- Pin the Python version used to build the sidecar (3.12 LTS, not 3.14).

### P2-5 — Persistence in `localStorage` drifts from SQLite; hardcoded user paths
Active workspace and nav were stored in `localStorage` while workspaces live in SQLite, so the IDs can drift. Earlier commits hardcoded `/Users/lpsekudus/agent` and `D:\projects\aksa` defaults; make sure none of them survive.

**Fix.**
- Keep a single source of truth in SQLite `app_settings` (`active_workspace_id`, UI prefs).
- Run `grep -rn "lpsekudus\|D:\\\\projects" apps services` → must be empty.
- With no workspace, show a first-run onboarding to pick a folder instead of a hardcoded default.

### P2-6 — Error messages leak internal exceptions to the client
Patterns like `HTTPException(500, detail=f"Gagal membuka berkas: {e}")` ("Failed to open file: {e}") return raw exception text, which can include paths and URLs with keys.

**Fix.**
- Add a global exception handler that returns `{code, detail_id (Indonesian, user-facing), request_id}`.
- Log the full error server-side, redacted.

### P2-7 — Tests do not cover the real risk surface
The 41 tests pass, but none of them:
- run the real UI → engine auth;
- launch the packaged sidecar;
- assert no-overwrite;
- assert no keys in responses;
- test origin bypasses.

**Fix.**
- Add the tests listed in each item's acceptance criteria.
- Add Playwright E2E tests against `npm run dev` with auth on.
- Add a CI matrix (macOS + Windows) that builds the sidecar and runs a smoke test of the packaged app.
- Fail CI on coverage below 70% for `core/` and `api/`.

---

## P3 — Low

- **P3-1.** Split `api/routes.py` into routers: `models`, `workspaces`, `agents`, `rag`, `telegram`, `system`, `skills`. Split `db/models.py` into repositories. This follows `AGENTS.md` modularity.
- **P3-2.** Code-split the frontend with `React.lazy` per view (Agents canvas/xyflow, Skills, Settings). Target an initial chunk under 400 KB.
- **P3-3.** Rewrite the `PROGRESS.md` status honestly: "Beta — security hardening in progress". Link to this file and track each ID as a checklist item.

---

## Things that are already good (keep them)

- The sidecar refuses to bind to non-loopback hosts (`main.py` L131).
- Host-header DNS-rebinding check and a 10 MB request size limit exist (fix the bypasses in P1-2).
- `sandbox.validate_path` uses `realpath` + `is_relative_to` and rejects UNC paths. Reuse it everywhere (P0-1, P1-1).
- WebSocket session ownership and isolation exist.
- No `shell=True`, `eval`, `pickle`, or `yaml.load` in the engine. `subprocess` uses arg lists.
- Skill quarantine scanning and "disabled by default" for MCP and skills.
- The Tauri CSP is restrictive (`script-src 'self'`).
- `.gitignore` correctly excludes DBs, venvs, binaries, and generated Office files. No secrets or `.pyc` files are tracked.
- Frontend `npm audit --omit=dev` → 0 vulnerabilities. The backend passes 41/41 tests on Python 3.14 (macOS).

---

## Definition of Done for "Production Ready"

All of the following must be true and evidenced in `PROGRESS.md`:

1. Every P0 and P1 item is closed, with its regression test merged.
2. A packaged app runs on clean macOS (arm64 + x64) and Windows 11 VMs with **no** Python or Node installed: onboarding → add key → chat → create a real Excel file from a CSV → open it.
3. With auth on, `curl` without the token gets 401 on every route except `/health`.
4. No plaintext secrets on disk, in logs, in argv, or in any HTTP response.
5. Zero files are overwritten without explicit approval.
6. A local-only agent never triggers a network call to a cloud LLM.
7. CI is green on the macOS + Windows matrix: lint, type-check, pytest, Playwright E2E, `pip-audit`, `npm audit`, sidecar build, signed artifacts.

