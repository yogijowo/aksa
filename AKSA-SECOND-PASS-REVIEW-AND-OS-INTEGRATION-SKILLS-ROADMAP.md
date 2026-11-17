# AKSA --- Second-Pass Repository Review, Desktop Intelligence, OS Permissions, and External Skills Roadmap

**Repository:** https://github.com/yogijowo/aksa\
**Branch reviewed:** `main`\
**Review snapshot:** 17 November 2026\
**Document language:** English\
**Purpose:** A second-pass static repository review and an
implementation blueprint for turning AKSA into a secure, extensible
desktop AI assistant that can discover installed applications, request
native operating-system permissions, interact with applications through
approved adapters, and install external Agent Skills safely.

------------------------------------------------------------------------

# 1. Executive Summary

AKSA has a promising product direction: a local-first desktop AI
assistant combining a Tauri desktop shell, a Python engine, multi-agent
orchestration, document automation, hybrid RAG, Computer Use, Telegram,
and MCP integration.

The next major product step should be:

> **AKSA should understand the user's desktop environment, discover
> available applications, request only the permissions required for a
> specific task through the operating system where supported, and extend
> its capabilities through reviewed external skills.**

This must not become an unrestricted desktop agent. The product should
use a layered permission architecture:

1.  **Operating-system permission:** The OS decides whether AKSA may
    access protected capabilities.
2.  **AKSA user consent:** The user decides which app, workspace,
    resource, or operation AKSA may use.
3.  **Agent/tool authorization:** The backend checks whether the current
    task and agent are allowed to perform the requested operation.
4.  **Skill/MCP isolation:** External extensions receive only the
    explicitly granted capabilities they need.

An approval inside AKSA must never be treated as a substitute for an
operating-system permission. Likewise, an OS permission must not
automatically authorize every action an agent could perform.

## 1.1 Main conclusions

-   The repository has a useful architectural foundation, but the
    current progress tracker overstates completion in several areas.
-   Several important security controls are present as concepts or
    separate endpoints but are not consistently enforced at the actual
    execution boundary.
-   MCP invocation is currently a placeholder implementation, not a real
    MCP client execution path.
-   Application discovery and a centralized OS permission broker were
    not found in the reviewed implementation paths.
-   Computer Use can issue real PyAutoGUI input actions when available,
    but application accessibility inspection is incomplete and action
    validation needs strengthening.
-   The external skill system should use the portable Agent Skills
    format while treating every downloaded skill as untrusted until
    reviewed.
-   The first priority is to close existing permission and execution
    gaps before adding more powerful desktop capabilities.

------------------------------------------------------------------------

# 2. Review Method and Limitations

This review inspected the publicly accessible `main` branch files and
documentation, including:

-   `README.md` and `README.en.md`
-   `AGENTS.md`
-   `PROGRESS.md`
-   `.gitignore`
-   Root `package.json`
-   `scripts/dev.py`
-   Tauri capabilities, configuration, Rust entry points, and macOS
    entitlements
-   FastAPI routes, app configuration, WebSocket handling, and
    database/API specifications
-   LLM router
-   Hierarchical orchestrator
-   Workspace sandbox and tool registry
-   Computer Use implementation
-   MCP client implementation
-   Relevant architecture, RAG, Telegram, UI, and roadmap specifications

**This is a static source review, not a runtime security
certification.** The repository could not be cloned and executed in the
review environment. Therefore:

-   The test suite was not run.
-   Windows and macOS builds were not executed.
-   No live OS permission prompt was tested.
-   No penetration test was performed.
-   Not every file in the repository was independently opened.
-   Any finding should be revalidated against the exact local commit
    before implementation.

Use this document as an engineering backlog and verification plan, not
as a claim that every possible defect has been found.

------------------------------------------------------------------------

# 3. Second-Pass Findings in the Current Repository

The following items are based on the publicly visible `main` snapshot
reviewed on 17 November 2026. Recheck exact line numbers before editing
because the branch may change.

## 3.1 Critical --- The progress tracker conflicts with the source code

`PROGRESS.md` reports that privacy sanitization is complete and that
government document letterheads and identifying information have been
removed.

However, `services/engine/app/core/orchestrator.py` still contains a
hardcoded sample document for the Secretariat of the Kudus DPRD,
including:

-   Government institution letterhead.
-   Office address and telephone numbers.
-   A document number.
-   Procurement package descriptions.
-   A budget amount.
-   A RUP identifier.

This conflicts with the completion statement in `PROGRESS.md`.

**Required action:**

-   [ ] Remove the real-world institutional sample from production code.
-   [ ] Replace it with synthetic test fixtures.
-   [ ] Mark fixtures clearly as fictional.
-   [ ] Search every branch and Git history for the old content.
-   [ ] Re-run privacy and secret scanning.
-   [ ] Update `PROGRESS.md` only after the source and tests confirm the
    work is complete.

Relevant files:

-   `services/engine/app/core/orchestrator.py`
-   `PROGRESS.md`

## 3.2 Critical --- Workspace auto-registration grants excessive access

In `services/engine/app/api/routes.py`, the `GET /workspaces` endpoint
automatically registers the repository root when no workspace exists.
The automatic policy enables:

-   Read.
-   Write.
-   Execute.
-   RAG synchronization.

A workspace-listing request should never silently grant filesystem
permissions.

The orchestrator also falls back to the first available workspace or
`Path.cwd()` if no explicit workspace resolves. It enumerates files and
reads PDF content from that location.

**Required action:**

-   [ ] Remove all automatic workspace authorization.
-   [ ] A workspace list endpoint must be read-only.
-   [ ] Require an explicit workspace selection through the native
    folder picker.
-   [ ] Store a workspace ID and a verified OS-granted resource
    reference.
-   [ ] Reject task execution if no authorized workspace is supplied.
-   [ ] Never fall back to the process working directory.
-   [ ] Route every read, write, delete, index, and execute operation
    through the same policy service.
-   [ ] Do not re-register a workspace inside the orchestrator to grant
    new permissions.

Relevant files:

-   `services/engine/app/api/routes.py`
-   `services/engine/app/core/orchestrator.py`
-   `services/engine/app/core/sandbox.py`

## 3.3 Critical --- Tool risk metadata is not a centralized execution gate

`ToolRegistry` stores a `risk_level` for each tool. However, the current
registry execution method looks up a handler and invokes it directly.
The `/tools/execute` API route also calls the registry directly.

The HITL approval endpoints exist separately, but the approval request
is not inherently bound to the actual tool execution and exact
arguments.

**Required action:**

-   [ ] Introduce one `ExecutionPolicyGateway`.
-   [ ] Make every tool invocation pass through it.
-   [ ] Enforce risk levels before calling a handler.
-   [ ] Bind approvals to exact tool name, arguments, resource, task,
    session, skill version, and expiry.
-   [ ] Invalidate approval if arguments or target resources change.
-   [ ] Make approval one-time by default.
-   [ ] Reject expired, replayed, or mismatched approvals.
-   [ ] Ensure Telegram, MCP, skills, sub-agents, and desktop UI use the
    same gateway.

Relevant files:

-   `services/engine/app/tools/registry.py`
-   `services/engine/app/api/routes.py`
-   `services/engine/app/core/sandbox.py`

## 3.4 High --- API keys are masked but still stored in plaintext

The current LLM router saves provider API keys as JSON in the SQLite
`app_settings` table. The provider status response now masks keys, which
is good, but masking is not encryption.

The English README describes credentials as encrypted/masked. The source
reviewed supports masking in the response, but does not establish
encrypted-at-rest storage.

**Required action:**

-   [ ] Move provider secrets to Windows Credential Manager and macOS
    Keychain.
-   [ ] Use an appropriate OS keyring implementation for other supported
    platforms.
-   [ ] Store only a credential reference and non-secret metadata in
    SQLite.
-   [ ] Never return the original secret through an API.
-   [ ] Add migration logic for existing plaintext credentials.
-   [ ] Securely remove old plaintext values after successful migration.
-   [ ] Provide a clear migration failure path without silently deleting
    the only copy.
-   [ ] Update the README to describe the actual storage mechanism.

Relevant file:

-   `services/engine/app/core/llm_router.py`

## 3.5 High --- WebSocket session isolation has a permissive subscription path

The current WebSocket manager has session subscriptions. However, the
broadcast condition includes connections with an empty subscription set
when delivering session-targeted events.

That means an unscoped connection can receive events for sessions it did
not explicitly subscribe to.

The WebSocket authentication check is also conditional on
`settings.dev_mode`. The configuration defaults to development mode, and
the current development runner launches Uvicorn without explicitly
switching to production mode.

**Required action:**

-   [ ] Require an authenticated local client handshake in all packaged
    builds.
-   [ ] Do not use a query-string token if a safer handshake mechanism
    is available.
-   [ ] Never allow an empty subscription set to receive private session
    events.
-   [ ] Bind each connection to one authenticated user/session context.
-   [ ] Authorize every subscription request.
-   [ ] Reject unknown session IDs.
-   [ ] Add cross-session leakage tests.
-   [ ] Ensure production mode is explicit and cannot accidentally
    default to development.
-   [ ] Restrict CORS to known local origins.
-   [ ] Test that a browser opened by another local process cannot
    silently connect to the engine.

Relevant files:

-   `services/engine/app/api/ws.py`
-   `services/engine/app/config.py`
-   `services/engine/app/main.py`
-   `scripts/dev.py`

## 3.6 High --- Tauri shell permissions are too broad

The reviewed default Tauri capability enables `shell:allow-execute` and
`shell:allow-spawn` without a visible per-command scope. The Tauri
configuration also sets `app.security.csp` to `null`.

Tauri supports capabilities and command scopes to restrict what the
frontend can invoke.

**Required action:**

-   [ ] Remove unrestricted shell execute/spawn permissions.
-   [ ] Use a narrowly scoped sidecar command.
-   [ ] Allow only required executables and validated arguments.
-   [ ] Do not expose arbitrary shell execution to the React renderer.
-   [ ] Define a restrictive Content Security Policy.
-   [ ] Separate capabilities by feature and window.
-   [ ] Review all registered Rust commands and their argument
    validation.
-   [ ] Keep privileged OS operations in the Rust/native layer or a
    separately sandboxed helper.

Relevant files:

-   `apps/desktop/src-tauri/capabilities/default.json`
-   `apps/desktop/src-tauri/tauri.conf.json`
-   `apps/desktop/src-tauri/src/lib.rs`

## 3.7 High --- MCP client is a placeholder, not a real protocol client

The reviewed MCP client contains default server definitions. Some are
enabled by default and use package launch commands such as `npx -y` or
`uvx`.

However, `invoke_mcp_tool()` currently returns a successful `ToolResult`
containing the server name, tool name, and arguments. It does not
demonstrate a real MCP transport connection or invoke a remote server
tool.

**Required action:**

-   [ ] Do not report a successful MCP call unless the remote/local MCP
    tool was actually invoked.
-   [ ] Set all external MCP servers to disabled by default.
-   [ ] Implement the actual MCP protocol lifecycle.
-   [ ] Support explicit server installation and configuration.
-   [ ] Validate discovered tool schemas.
-   [ ] Require user approval before starting a new server process.
-   [ ] Pin package versions and verify package integrity.
-   [ ] Restrict environment variables, filesystem mounts, and network
    access.
-   [ ] Run MCP servers with the least privileges possible.
-   [ ] Route all MCP tool calls through the central execution policy
    gateway.

Relevant file:

-   `services/engine/app/tools/mcp/mcp_client.py`

## 3.8 High --- Computer Use needs a complete application accessibility layer

The current implementation can use `mss`, Pillow ImageGrab, and
PyAutoGUI. It can issue real mouse and keyboard actions if the
dependency and environment are available.

However:

-   The inspected accessibility information is limited to the active
    window title on Windows.
-   A complete native accessibility tree is not implemented in the
    inspected path.
-   An equivalent macOS accessibility tree is not demonstrated.
-   A screenshot fallback may generate a simulated coordinate grid.
-   Action types need strict validation before setting an
    executed/success status.
-   A real input event does not prove that the intended application
    state changed.

**Required action:**

-   [ ] Add an explicit action enum.
-   [ ] Reject unsupported actions before importing or calling the input
    driver.
-   [ ] Report `simulated`, `unsupported`, `blocked`, `failed`, and
    `executed` accurately.
-   [ ] Add post-action verification.
-   [ ] Implement Windows UI Automation.
-   [ ] Implement macOS Accessibility API integration.
-   [ ] Make screen capture and accessibility permissions visible in the
    Permission Center.
-   [ ] Add a reliable emergency stop.
-   [ ] Require confirmation before sensitive GUI actions.
-   [ ] Do not store full-screen screenshots indefinitely.
-   [ ] Redact screenshots and accessibility text from logs.

Relevant file:

-   `services/engine/app/tools/computer_use/gui_agent.py`

## 3.9 High --- Cloud model usage conflicts with the unconditional zero-telemetry statement

The README describes AKSA as having zero telemetry and says document
contents are not transmitted to third parties.

The reviewed execution path can attach PDF data to a model request. The
Gemini provider path sends attachment data to the cloud provider when
that provider is selected.

This is not necessarily a defect: cloud AI requires data to be sent to
the selected provider. The issue is the unconditional privacy claim.

**Required action:**

-   [ ] Clearly distinguish local-model and cloud-model processing.
-   [ ] Show a confirmation before sending local documents to a cloud
    provider for the first time.
-   [ ] Identify the destination provider.
-   [ ] Explain what content will be sent.
-   [ ] Provide a local-only mode.
-   [ ] Never silently fall back from local to cloud for confidential
    documents.
-   [ ] Allow users to disable cloud fallback.
-   [ ] Update privacy documentation and UI labels.

Relevant files:

-   `README.en.md`
-   `services/engine/app/core/orchestrator.py`
-   `services/engine/app/core/llm_router.py`

## 3.10 Medium --- Token-saving metrics need a measured baseline

The orchestrator contains fixed simulated document-token values and a
fixed cost estimate in the inspected code path.

**Required action:**

-   [ ] Use provider-reported token usage whenever available.
-   [ ] Label estimates as estimates.
-   [ ] Do not report simulated token savings as measured savings.
-   [ ] Define a reproducible baseline for any percentage improvement.
-   [ ] Store the model/provider pricing version and measurement date.
-   [ ] Test analytics with no data, partial provider data, and missing
    usage metadata.

## 3.11 Medium --- Cross-platform test command is not portable

The root `package.json` test command references:

``` text
services/engine/.venv/bin/pytest
```

That path is Unix-style and does not work as written on Windows.

**Required action:**

-   [ ] Use `uv run --project services/engine pytest ...` or a
    cross-platform Python runner.
-   [ ] Test commands on Windows and macOS.
-   [ ] Document one canonical test command.
-   [ ] Keep development scripts and CI commands consistent.

## 3.12 Repository hygiene observations

-   The root GitHub listing shows 20 commits. A fresh Git history is
    still a separate cleanup task.
-   The root listing displayed `Rekap_Otomatis_AKSA.xlsx`, but direct
    retrieval of that path returned 404 during this review. Verify its
    actual tracked status locally with `git ls-files` and `git status`;
    do not assume it is harmless or assume it is definitely present.
-   `.gitignore` excludes Office documents such as `.xlsx`, but ignore
    rules do not remove files that are already tracked.
-   `.vscode/settings.json` currently uses `${workspaceFolder}` and
    relative paths in the inspected content. It does not show an
    absolute personal path in that file. Keep it only if it is
    intentionally shared project configuration.
-   `PROGRESS.md` should be updated to reflect verified code and test
    results, not intended architecture.

Recommended local checks:

``` bash
git status --short
git ls-files
git ls-files '*.xlsx' '*.docx' '*.pdf' '*.db' '*.sqlite' '.env*'
git log --all --oneline --decorate -30
```

------------------------------------------------------------------------

# 4. Product Vision: AKSA Desktop Intelligence

The desired product should be more than a chatbot that receives a folder
path.

AKSA should maintain a safe, user-visible understanding of the desktop
environment:

-   Which applications are installed.
-   Which applications are currently running.
-   Which applications have known integration adapters.
-   Which OS permissions are available, denied, or not yet requested.
-   Which workspaces the user explicitly authorized.
-   Which skills and MCP integrations are installed.
-   Which capabilities each agent or skill is allowed to use.

## 4.1 Proposed application architecture

``` text
AKSA Desktop UI
    |
    +-- AI Orchestrator
    |      |
    |      +-- Task Planner
    |      +-- Agent Team Manager
    |      +-- Skill Resolver
    |      +-- Application Resolver
    |      +-- Tool Execution Planner
    |
    +-- Native Capability Broker (Rust / Tauri)
    |      |
    |      +-- Installed Application Discovery
    |      +-- Running Application Discovery
    |      +-- Native App Launcher
    |      +-- OS Permission Status
    |      +-- Native Permission Requests
    |      +-- Native Folder/File Picker
    |      +-- Screen Capture Authorization
    |      +-- Accessibility / Automation Authorization
    |
    +-- Policy and Consent Layer
    |      |
    |      +-- Workspace Access Policies
    |      +-- Per-Application Permissions
    |      +-- Per-Skill Permissions
    |      +-- MCP Server Permissions
    |      +-- Human Approval Gateway
    |      +-- Audit Events
    |
    +-- Integration Runtime
           |
           +-- Native Office Adapters
           +-- Windows UI Automation Adapter
           +-- macOS Accessibility Adapter
           +-- Browser Adapter
           +-- Computer Use Adapter
           +-- MCP Runtime
           +-- Skill Runtime
```

## 4.2 Important separation of responsibilities

  -----------------------------------------------------------------------
  Component               Responsibility          Must not do
  ----------------------- ----------------------- -----------------------
  Application Discovery   List installed/running  Read private
                          apps and metadata       application data

  OS Permission Broker    Check/request supported Pretend a permission
                          OS permissions          was granted

  AKSA Policy Gateway     Decide whether this     Override OS
                          task may use a          restrictions
                          capability              

  Application Adapter     Interact with a         Escalate privileges
                          specific app through    silently
                          supported APIs          

  Skill Manager           Install, validate,      Execute unreviewed
                          version, and enable     scripts during
                          skills                  installation

  MCP Manager             Connect to configured   Trust every MCP server
                          external tools          automatically

  Agent Orchestrator      Plan and delegate tasks Bypass permission
                                                  checks
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Feature A --- Installed Application Discovery

## 5.1 Goal

When AKSA starts, it should be able to discover installed desktop
applications and display them in a user-facing **Applications** section.

Example inventory:

  -----------------------------------------------------------------------
  Application             Status                  Available integration
  ----------------------- ----------------------- -----------------------
  Microsoft Word          Installed               Office adapter / UI
                                                  Automation

  Microsoft Excel         Installed               Office adapter / UI
                                                  Automation

  Google Chrome           Installed               Browser adapter / UI
                                                  Automation

  Mozilla Firefox         Installed               Browser adapter / UI
                                                  Automation

  Visual Studio Code      Installed               Launch / file-open /
                                                  optional CLI adapter

  Adobe Acrobat           Installed               Launch / document-open
                                                  / UI Automation

  LibreOffice             Installed               Document adapter / UI
                                                  Automation

  Ollama                  Installed               Local model service
                                                  adapter
  -----------------------------------------------------------------------

The list above is illustrative. AKSA must show only applications
actually detected on the user's device.

## 5.2 Inventory data model

Create a normalized application record:

``` json
{
  "id": "stable-platform-specific-id",
  "display_name": "Microsoft Excel",
  "publisher": "Microsoft Corporation",
  "version": "detected-version",
  "platform": "windows",
  "application_id": "platform-specific-app-id",
  "bundle_or_package_id": "optional-bundle-or-package-id",
  "install_scope": "user-or-machine",
  "install_location": "normalized-install-location",
  "launch_method": "registered-app-launch",
  "signature_status": "verified-or-unknown",
  "detection_sources": ["registry", "start-menu"],
  "is_installed": true,
  "is_running": false,
  "available_adapters": ["office", "uia"],
  "last_seen_at": "ISO-8601"
}
```

Do not expose unnecessary personal information from installation
records. Store only metadata needed for app discovery and launching.

## 5.3 Windows application discovery

Use a native Windows implementation.

Recommended sources:

1.  Uninstall registry keys:
    -   `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall`
    -   `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall`
    -   32-bit registry view on 64-bit Windows.
    -   Per-user registrations where available.
2.  Start Menu application registrations and AUMID information.
3.  Windows packaged-app APIs where appropriate.
4.  Optional user-selected application folders for portable apps.

Use stable identifiers where possible, such as AUMID or a normalized
application ID. Windows documentation notes that `Get-StartApps` returns
apps that appear in the Start menu; it is not a complete inventory of
every installed application.

Do not use `Win32_Product` as a general inventory mechanism because
querying it can trigger Windows Installer consistency checks.

### Windows discovery requirements

-   [ ] Read both machine-level and user-level registrations.
-   [ ] Handle 32-bit and 64-bit registry views.
-   [ ] Detect packaged applications separately from Win32 applications.
-   [ ] Normalize duplicate records.
-   [ ] Do not require administrator privileges for ordinary inventory.
-   [ ] Never execute an application's uninstall command.
-   [ ] Do not trust registry display names as proof of publisher
    identity.
-   [ ] Verify executable signatures before offering high-trust
    automation.
-   [ ] Distinguish installed applications from portable executables.

## 5.4 macOS application discovery

Use public macOS application frameworks.

Recommended sources:

-   Launch Services registered applications.
-   `/Applications`.
-   `/System/Applications`.
-   `~/Applications`.
-   `NSWorkspace` for currently running applications.
-   Bundle identifiers and `Info.plist` metadata.
-   Code-signing identity and notarization status where available.

Use Launch Services to resolve and launch registered applications. Use
`NSWorkspace.runningApplications` to identify applications currently
running.

Do not depend on private APIs such as undocumented workspace services.

### macOS discovery requirements

-   [ ] Detect system, machine-wide, and user-installed applications.
-   [ ] Normalize bundle identifiers.
-   [ ] Identify running applications.
-   [ ] Capture version and signing metadata where available.
-   [ ] Distinguish signed, unsigned, and unknown publishers.
-   [ ] Do not inspect application containers or user documents merely
    to build the app inventory.
-   [ ] Do not request Full Disk Access for ordinary application
    discovery.

## 5.5 Inventory refresh and privacy

-   [ ] Run a lightweight initial scan.
-   [ ] Cache normalized application metadata.
-   [ ] Refresh on explicit user request and at reasonable intervals.
-   [ ] Detect install/uninstall changes where practical.
-   [ ] Do not continuously scan the entire disk.
-   [ ] Let users hide applications from the AKSA catalog.
-   [ ] Do not upload the application inventory to a cloud service by
    default.
-   [ ] Make any export or telemetry opt-in.

------------------------------------------------------------------------

# 6. Feature B --- Native OS Permission Broker

## 6.1 Goal

AKSA should request permissions through the operating system whenever
the OS provides a native permission flow.

Examples:

-   User chooses a folder using the native folder picker.
-   macOS displays a system authorization prompt for Accessibility or
    Automation when the corresponding protected API is used.
-   macOS displays the relevant screen-recording permission flow.
-   Windows displays the native screen-capture picker when using an API
    that supports user consent.
-   Windows uses normal user ACLs and UAC when applicable, rather than
    inventing a fake permission dialog.

**Important platform distinction:** Windows does not provide a single
macOS-style privacy prompt for every file, application, or UI Automation
action. Windows primarily relies on user identity, file ACLs, process
integrity, UAC elevation, and specific system APIs. UI Automation itself
does not automatically produce a general "Allow this app to control your
computer" prompt. AKSA must therefore combine native Windows controls
with its own clear consent UI.

## 6.2 Permission states

Use a shared permission-state model:

``` text
NOT_REQUESTED
CHECKING
GRANTED
DENIED
RESTRICTED
NEEDS_USER_ACTION
UNSUPPORTED
ERROR
```

Do not use a boolean `allowed` field for every OS capability. A boolean
cannot explain whether permission is unsupported, denied, missing, or
needs the user to open System Settings.

## 6.3 Capability catalog

Create a central list of permission capabilities.

  -------------------------------------------------------------------------------
  Capability ID                   Meaning                 Typical scope
  ------------------------------- ----------------------- -----------------------
  `filesystem.workspace.read`     Read files in an        Specific folder
                                  authorized workspace    

  `filesystem.workspace.write`    Create/edit files in an Specific folder
                                  authorized workspace    

  `filesystem.workspace.delete`   Delete files in an      Specific folder
                                  authorized workspace    

  `application.discover`          Enumerate installed     Device
                                  application metadata    

  `application.launch`            Launch a detected       Specific app
                                  application             

  `application.automation`        Automate a specific     Specific app
                                  application             

  `screen.capture`                Capture the desktop or  Device/session
                                  selected window         

  `accessibility.inspect`         Read accessibility UI   Device/session
                                  elements                

  `input.mouse_keyboard`          Send mouse and keyboard Device/session
                                  input                   

  `automation.apple_events`       Send Apple Events to an Specific target app
                                  app                     

  `process.spawn`                 Start an approved       Executable + arguments
                                  process                 

  `network.domain_access`         Connect to an approved  Domain/endpoint
                                  remote host             

  `clipboard.read`                Read clipboard content  Per operation

  `clipboard.write`               Write clipboard content Per operation

  `microphone.capture`            Record audio input      Device/session

  `notification.display`          Display desktop         Device
                                  notifications           
  -------------------------------------------------------------------------------

Capabilities must be granular. Granting `application.automation` for
Excel must not grant it for every application.

## 6.4 macOS permission implementation

Use native macOS APIs and TCC-managed permission flows.

### File and folder access

-   Use `NSOpenPanel` or the appropriate native open/save panel.
-   Let the user select the folder or file.
-   For sandboxed distribution, use security-scoped bookmarks for
    persistent user-selected resources.
-   Resolve and activate the security-scoped URL before accessing the
    resource.
-   Stop accessing the security-scoped resource when finished.
-   Store bookmark data securely in AKSA's application data store.
-   Handle stale bookmarks and ask the user to reselect the resource
    when necessary.

Do not replace this flow with an arbitrary path supplied by an LLM.

### Accessibility

-   Check Accessibility trust using `AXIsProcessTrusted()` or the
    appropriate current API.
-   Where supported, use the system's request/prompt mechanism.
-   If the user must change the setting manually, open or guide them to
    the relevant System Settings page.
-   Detect the permission state again after the user returns.
-   Do not report Accessibility as granted merely because the user
    clicked an AKSA confirmation button.

### Screen Recording

-   Check the current screen-capture permission state.
-   Request access through the supported macOS screen-capture API.
-   Explain why a screenshot is needed before requesting access.
-   If permission is denied, provide a clear System Settings recovery
    path.
-   Do not repeatedly trigger prompts.
-   Do not silently use a simulated image while reporting a real
    screenshot.

### Apple Events / Application Automation

-   Use the Apple Events automation entitlement required by the app's
    distribution model.
-   Request permission for the specific target application through the
    OS-managed mechanism.
-   Track target application identity and permission state.
-   If a target app is denied, do not try another method to bypass TCC.
-   Keep Apple Events permissions separate from Accessibility
    permissions.

### Avoid excessive macOS privileges

Do not request Full Disk Access as a default onboarding step. Request
only the specific capability required for the task.

## 6.5 Windows permission implementation

### File and folder access

-   Use a native folder/file picker.
-   Treat the user's selected folder as the explicit AKSA workspace.
-   Let Windows ACLs determine whether the current user/process can read
    or write.
-   Show clear errors when access is denied.
-   Do not elevate the entire application merely to access a selected
    folder.
-   Do not scan protected directories to discover workspaces.

### UI Automation

-   Use the Windows UI Automation framework to inspect supported
    application controls.
-   Understand that UI Automation does not itself provide a general OS
    permission dialog.
-   Use AKSA's own consent UI to ask whether the user wants a particular
    app automated.
-   Respect process integrity boundaries and user/session boundaries.
-   Do not attempt to control applications running under another user or
    at a higher integrity level by bypassing Windows security.

### Screen capture

-   Prefer Windows.Graphics.Capture or an equivalent supported API that
    presents the native user selection/consent flow where appropriate.
-   Clearly distinguish user-selected window capture from whole-display
    capture.
-   Do not treat a successful `pyautogui` import as proof that screen
    capture is authorized.

### UAC and elevation

-   UAC is for elevation, not a generic application automation
    permission.
-   AKSA should run as a normal user process by default.
-   Do not request administrator rights during ordinary installation or
    startup.
-   If a task truly requires elevation, explain the exact operation and
    let the user initiate the OS elevation flow.
-   Do not store or request administrator passwords.

## 6.6 Permission request lifecycle

Implement this lifecycle:

``` text
Agent identifies required capability
        |
        v
Policy Gateway checks existing AKSA grant
        |
        +-- Existing grant valid? -- Yes --> Check OS permission
        |                                  |
        |                                  +-- OS allows --> Execute
        |                                  |
        |                                  +-- OS denies --> Block + explain
        |
        +-- No AKSA grant
                 |
                 v
       Show AKSA consent preview
                 |
          User approves?
            /       \
          No         Yes
          |           |
        Deny       Request OS permission
                      |
                OS grants access?
                  /       \
                No         Yes
                |           |
              Block      Persist scoped grant
                            |
                            v
                         Execute
```

The system must not create a permanent grant if the OS permission is
denied.

## 6.7 Permission Center UI

Create a dedicated **Izin & Aplikasi** screen.

Each row should show:

-   Capability name.
-   Application or workspace scope.
-   OS permission status.
-   AKSA permission status.
-   Last granted date.
-   Grant source.
-   Expiry or review date where applicable.
-   Revoke button.
-   Explain/repair action.

Example:

  Resource           OS status           AKSA status
  ------------------ ------------------- -----------------------------------
  Documents folder   Available           Read/write granted
  Microsoft Excel    Available           Automation not granted
  Screen capture     Needs user action   Not granted
  Accessibility      Denied              Not granted
  Chrome             Available           Launch allowed, automation denied

Do not show a green "Allowed" state until both the OS and AKSA policy
checks pass.

------------------------------------------------------------------------

# 7. Feature C --- Application Intelligence and Integration Adapters

Application discovery is only the first step. AKSA should understand
what it can safely do with each detected app.

## 7.1 Application adapter interface

Create a common interface:

``` python
class ApplicationAdapter:
    async def detect(self) -> list[ApplicationRecord]:
        ...

    async def get_status(self, application_id: str) -> ApplicationStatus:
        ...

    async def check_capabilities(
        self,
        application_id: str,
    ) -> list[CapabilityStatus]:
        ...

    async def launch(
        self,
        application_id: str,
        document_path: str | None = None,
    ) -> OperationResult:
        ...

    async def inspect_ui(
        self,
        application_id: str,
    ) -> UIInspectionResult:
        ...

    async def execute_action(
        self,
        application_id: str,
        action: ApplicationAction,
    ) -> OperationResult:
        ...
```

Use typed request/response models. Do not let the LLM submit arbitrary
shell strings as an application ID or launch command.

## 7.2 Adapter categories

Start with a small set of well-tested adapters:

1.  **Generic app launcher**
    -   Resolve a registered app ID.
    -   Launch the application.
    -   Open a user-approved document with the app.
    -   Report actual launch status.
2.  **Microsoft Office**
    -   Prefer direct file APIs for document generation.
    -   Use Windows COM only when the user requests interaction with a
        live Office instance.
    -   Use macOS Apple Events or supported automation APIs only after
        the target app's OS permission is granted.
    -   Do not assume Microsoft Office is installed.
3.  **Browser**
    -   Support a controlled browser automation adapter.
    -   Keep browser profile and password access out of scope by
        default.
    -   Use an explicit browser session or user-approved browser
        context.
    -   Require approval before submitting forms or performing external
        transactions.
4.  **Accessibility / UI Automation**
    -   Use native UI element identities where possible.
    -   Prefer semantic controls over screen coordinates.
    -   Use screenshot grounding only when accessibility metadata is
        unavailable.
5.  **Computer Use**
    -   Use screenshots and coordinate actions as a fallback.
    -   Verify the resulting UI state after every consequential action.

## 7.3 App compatibility matrix

Create a versioned compatibility matrix.

Example:

  -------------------------------------------------------------------------
  App family        Windows            macOS              Integration mode
  ----------------- ------------------ ------------------ -----------------
  Microsoft Word    Planned/verified   Planned/verified   File API + native
                    per build          per build          automation

  Microsoft Excel   Planned/verified   Planned/verified   File API + native
                    per build          per build          automation

  Chrome            Planned/verified   Planned/verified   Browser adapter +
                    per build          per build          accessibility

  Firefox           Planned/verified   Planned/verified   Browser adapter +
                    per build          per build          accessibility

  VS Code           Planned/verified   Planned/verified   Launch + selected
                    per build          per build          folder

  Adobe Acrobat     Planned/verified   Planned/verified   Open document +
                    per build          per build          accessibility

  LibreOffice       Planned/verified   Planned/verified   File API +
                    per build          per build          accessibility
  -------------------------------------------------------------------------

Do not mark an app as supported merely because it is detected.
Detection, launching, reading UI, and automation are separate
capabilities.

------------------------------------------------------------------------

# 8. Feature D --- External Agent Skills Manager

## 8.1 Goal

Users should be able to discover and install useful skills from outside
AKSA.

Examples of possible skill categories:

-   Excel analysis and reporting.
-   Word document formatting.
-   Indonesian official correspondence.
-   PDF extraction and summarization.
-   Data cleaning.
-   Procurement and administrative document workflows.
-   Browser research.
-   Presentation generation.
-   File organization.
-   Software development workflows.

AKSA should support the portable Agent Skills format built around a
`SKILL.md` file and optional scripts, references, and assets.

The format is portable. The contents are not automatically safe.

## 8.2 Skill package structure

Support a structure such as:

``` text
excel-monthly-report/
    SKILL.md
    scripts/
        validate_workbook.py
        create_summary.py
    references/
        report-guidelines.md
    assets/
        report-template.xlsx
    aksa.skill.yaml
```

`SKILL.md` should follow the Agent Skills specification for metadata and
instructions.

`aksa.skill.yaml` is an AKSA-specific extension manifest describing the
permissions and runtime requirements. Keep it separate from the portable
skill instructions so that the core skill remains compatible with other
agents.

Example AKSA extension manifest:

``` yaml
schema_version: 1

skill:
  id: excel-monthly-report
  version: 1.0.0
  display_name: Excel Monthly Report
  publisher: Example Publisher
  description: Create and validate monthly Excel reports.

runtime:
  type: instructions-and-scripts
  entrypoint: SKILL.md

capabilities:
  - filesystem.workspace.read
  - filesystem.workspace.write

resources:
  workspace_scope: selected_workspace_only

network:
  enabled: false
  allowed_domains: []

process:
  execute_scripts: true
  allowed_executables:
    - python

secrets:
  access: none
```

This is an example of the proposed AKSA extension manifest, not a
replacement for the standard `SKILL.md` format.

## 8.3 Skill discovery sources

Support several source types:

1.  AKSA-curated skill catalog.
2.  Verified publisher repositories.
3.  Public Git repositories.
4.  User-provided Git URLs.
5.  User-selected ZIP packages.
6.  Local skill folders.

The default catalog should prioritize curated and reviewed skills.

Possible initial reference sources include:

-   Agent Skills specification: `https://agentskills.io/`
-   Official Agent Skills repository:
    `https://github.com/agentskills/agentskills`
-   Anthropic skills repository: `https://github.com/anthropics/skills`
-   Microsoft skills resources: `https://github.com/microsoft/skills`

These are candidate discovery sources, not blanket guarantees that every
package in those repositories is safe. Review each skill and its
dependencies before enabling it.

## 8.4 Skill trust levels

Use explicit trust labels:

  -----------------------------------------------------------------------
  Level                   Meaning                 Default behavior
  ----------------------- ----------------------- -----------------------
  AKSA Curated            Reviewed and tested by  Available for one-click
                          AKSA maintainers        review/install

  Verified Publisher      Publisher identity and  Install after
                          package integrity       permission review
                          verified                

  Community Reviewed      Community checks exist, Manual review required
                          but AKSA has not fully  
                          validated it            

  Unreviewed              Arbitrary public source Disabled until
                          or user ZIP             inspection and approval

  Blocked                 Known malicious,        Installation denied
                          compromised, or         
                          policy-violating        
                          package                 
  -----------------------------------------------------------------------

Never use a "100% safe" label.

## 8.5 Secure skill installation pipeline

A skill must not execute code during installation.

Recommended pipeline:

``` text
User selects a skill source
        |
        v
Download into quarantine
        |
        v
Verify source, version, and package hash
        |
        v
Validate archive paths and file types
        |
        v
Parse SKILL.md and AKSA manifest
        |
        v
Static security inspection
        |
        v
Dependency and script inspection
        |
        v
Build permission summary
        |
        v
Show installation preview
        |
        v
User approves installation
        |
        v
Install immutable version
        |
        v
Keep disabled until user enables it
        |
        v
Request runtime permissions when needed
```

## 8.6 Required installation security checks

-   [ ] Prevent ZIP path traversal (`../`) and absolute-path extraction.
-   [ ] Reject symlinks or validate them strictly.
-   [ ] Limit archive size and decompressed size.
-   [ ] Limit file count and nesting depth.
-   [ ] Reject unexpected binary executables unless explicitly
    supported.
-   [ ] Calculate SHA-256 hashes for all package files.
-   [ ] Record source URL, publisher, commit/tag, and package hash.
-   [ ] Inspect scripts and package manager commands.
-   [ ] Detect shell execution, subprocess calls, network access, secret
    access, and filesystem traversal.
-   [ ] Detect obfuscated code and suspicious post-install hooks.
-   [ ] Pin dependencies and verify package integrity.
-   [ ] Do not run `curl | sh`, `wget | bash`, PowerShell
    download-and-execute patterns, or unpinned package installers.
-   [ ] Do not automatically install Python, Node, or system packages
    without explicit approval.
-   [ ] Never expose provider API keys to skill scripts by default.
-   [ ] Keep the downloaded package immutable after installation.
-   [ ] Revalidate package hash before activation.

Static scanning cannot prove a skill is harmless. Treat scan results as
evidence for a human decision, not as a guarantee.

## 8.7 Skill installation preview UI

Before installation, show a readable review card:

``` text
Skill: Excel Monthly Report
Publisher: Example Publisher
Version: 1.0.0
Source: github.com/example/excel-monthly-report
Trust: Community Reviewed

Files:
- SKILL.md
- 2 Python scripts
- 1 reference document
- 1 Excel template

Requested capabilities:
- Read selected workspace
- Write selected workspace

Network:
- None

External processes:
- Python (isolated runtime)

Secrets:
- No access

Risk assessment:
- Medium

[Inspect files] [Install disabled] [Cancel]
```

The exact permission list must be generated from the actual package and
runtime requirements, not from a publisher-supplied description alone.

## 8.8 Skill runtime isolation

Skills can contain scripts. Their execution must be isolated.

Recommended default:

-   Read only the selected workspace or explicitly mounted skill
    resources.
-   Write only to an approved output directory.
-   No network access.
-   No access to application secrets.
-   No access to browser cookies or password stores.
-   No unrestricted shell.
-   No access to arbitrary home-directory files.
-   CPU, RAM, process, disk, and execution-time limits.
-   Temporary working directory per execution.
-   Kill the process tree on cancellation.
-   Capture sanitized stdout/stderr.
-   Record tool and permission decisions.

If the platform cannot provide a secure sandbox for a skill, disable its
executable scripts and allow instruction-only use where appropriate.

## 8.9 Skill permissions and user consent

A skill may declare requested capabilities, but it cannot grant them to
itself.

The flow should be:

1.  Skill declares a capability.
2.  AKSA validates the capability against the supported catalog.
3.  The user sees why the skill needs it.
4.  The user approves or rejects it.
5.  The OS Permission Broker checks or requests OS-level permission
    where applicable.
6.  AKSA stores a scoped grant.
7.  Runtime checks the grant before every operation.

Example:

-   Skill: Excel Monthly Report.
-   Requested: Read and write the selected `Monthly Reports` workspace.
-   Not requested: Network, screen capture, browser access, microphone,
    credential access.
-   User grants read/write to one folder.
-   The skill cannot use that grant to read another folder.

## 8.10 Skill updates, rollback, and removal

-   [ ] Pin installed versions.
-   [ ] Never silently update a skill that has executable code.
-   [ ] Show a diff of changed instructions and scripts.
-   [ ] Show permission changes before an update.
-   [ ] Re-run static inspection after every update.
-   [ ] Keep the previous version for rollback.
-   [ ] Allow users to disable a skill immediately.
-   [ ] Uninstall must revoke its AKSA grants.
-   [ ] Remove cached runtime data where safe.
-   [ ] Keep an audit record without storing secrets or private task
    content.

## 8.11 Skill execution rules

-   A skill is an instruction package, not a trusted system prompt.
-   Treat its content as untrusted data.
-   It must never override AKSA's system policy.
-   It cannot grant itself new tools.
-   It cannot alter the central permission gateway.
-   It cannot read secrets unless a separate explicit secret-integration
    feature exists.
-   It cannot use prompt injection in a document or web page to expand
    its permissions.
-   It cannot install another skill without user approval.
-   It cannot silently install MCP servers or external dependencies.

------------------------------------------------------------------------

# 9. Feature E --- MCP and Skills Must Be Separate Systems

Do not combine Skills and MCP into one undifferentiated plugin system.

  -----------------------------------------------------------------------
  Capability              Agent Skill             MCP Server
  ----------------------- ----------------------- -----------------------
  Main purpose            Reusable instructions   Expose external
                          and workflows           tools/resources

  Typical package         `SKILL.md`, scripts,    Executable process or
                          references, assets      remote service

  Execution               Instructions and        Tool calls over MCP
                          optional scripts        transport

  Main risk               Prompt injection and    External
                          script execution        process/service and
                                                  tool access

  Permissions             Declared skill          Server and
                          capabilities            tool-specific
                                                  permissions

  Installation            Package/repository      Server configuration
                          validation              and process validation

  Default state           Installed but disabled  Disabled until
                                                  explicitly enabled
  -----------------------------------------------------------------------

## 9.1 Real MCP implementation requirements

-   [ ] Implement actual MCP initialization and capability negotiation.
-   [ ] Implement supported transports deliberately.
-   [ ] Validate server identity and endpoint.
-   [ ] Validate tool schemas.
-   [ ] Validate arguments against the discovered schema.
-   [ ] Apply timeouts and cancellation.
-   [ ] Enforce output-size limits.
-   [ ] Do not expose unrestricted environment variables.
-   [ ] Do not mount the entire user home directory by default.
-   [ ] Require a user-selected workspace for filesystem servers.
-   [ ] Show the tools exposed by each server before enabling it.
-   [ ] Keep all server tools behind the central permission gateway.
-   [ ] Record server version, source, and executable/package hash where
    applicable.

## 9.2 MCP installation preview

Show:

-   Server name and publisher.
-   Source repository or endpoint.
-   Transport type.
-   Executable and exact arguments.
-   Package version and integrity hash.
-   Network endpoints.
-   Environment variables requested.
-   Filesystem access requested.
-   Tools exposed.
-   Risk classification.
-   Whether the server is local or remote.

Do not use `npx -y` or `uvx` to install and execute an unreviewed
package silently. Pin versions and require explicit user approval.

------------------------------------------------------------------------

# 10. Feature F --- Application-Aware Agent Planning

Once app discovery, OS permissions, and skills are implemented, the
orchestrator should choose the best execution path.

Example user request:

> "Buka Excel, analisis file penjualan, buat grafik, lalu simpan
> hasilnya."

Proposed flow:

1.  Resolve the selected workspace.
2.  Find the sales file within the authorized workspace.
3.  Detect whether Microsoft Excel or LibreOffice is installed.
4.  Determine whether the task needs file-level Excel generation or live
    GUI interaction.
5.  Prefer direct document APIs when they can safely complete the task.
6.  If live Excel interaction is required, check the app integration
    adapter.
7.  Check the required OS permissions.
8.  Request missing permission through the native OS mechanism where
    supported.
9.  Show AKSA consent for the specific operation.
10. Execute through the approved adapter.
11. Verify the output file and workbook contents.
12. Report the actual result and provide the artifact.

The agent must not automatically choose Computer Use when a safer direct
file API can perform the task.

## 10.1 Execution strategy priority

Recommended order:

1.  Native document APIs.
2.  Official application APIs or automation interfaces.
3.  MCP tools from approved servers.
4.  OS Accessibility / UI Automation.
5.  Visual Computer Use.
6.  Arbitrary shell/script execution only in a constrained sandbox and
    with explicit approval.

------------------------------------------------------------------------

# 11. Database and API Additions

The existing SQLite schema should be extended through versioned
migrations.

## 11.1 Proposed tables

### `installed_applications`

Suggested fields:

-   `id`
-   `platform`
-   `platform_app_id`
-   `bundle_id`
-   `aumid`
-   `display_name`
-   `publisher`
-   `version`
-   `install_location`
-   `install_scope`
-   `signature_status`
-   `detection_sources_json`
-   `is_installed`
-   `is_running`
-   `last_seen_at`
-   `metadata_json`

### `application_adapters`

-   `id`
-   `application_id`
-   `adapter_type`
-   `adapter_version`
-   `status`
-   `supported_actions_json`
-   `last_verified_at`

### `os_permission_states`

-   `id`
-   `platform`
-   `capability_id`
-   `resource_id`
-   `status`
-   `checked_at`
-   `last_requested_at`
-   `last_error_code`

### `permission_grants`

-   `id`
-   `principal_type` (user, agent, skill, MCP server)
-   `principal_id`
-   `capability_id`
-   `resource_scope`
-   `grant_source`
-   `granted_at`
-   `expires_at`
-   `revoked_at`
-   `policy_version`

### `permission_audit_events`

-   `id`
-   `task_id`
-   `session_id`
-   `principal_type`
-   `principal_id`
-   `capability_id`
-   `resource_scope`
-   `decision`
-   `reason_code`
-   `created_at`

### `skill_sources`

-   `id`
-   `source_type`
-   `source_url`
-   `publisher_id`
-   `trust_level`
-   `enabled`
-   `last_checked_at`

### `installed_skills`

-   `id`
-   `skill_id`
-   `display_name`
-   `publisher`
-   `source_id`
-   `installed_version`
-   `package_hash`
-   `trust_level`
-   `enabled`
-   `installed_at`
-   `last_verified_at`

### `skill_versions`

-   `id`
-   `skill_id`
-   `version`
-   `package_hash`
-   `source_commit`
-   `manifest_json`
-   `scan_report_json`
-   `installed_at`

### `skill_capability_requests`

-   `id`
-   `skill_id`
-   `version`
-   `capability_id`
-   `resource_scope`
-   `decision`
-   `created_at`
-   `revoked_at`

### `mcp_servers`

-   `id`
-   `name`
-   `source`
-   `transport`
-   `command`
-   `args_json`
-   `environment_allowlist_json`
-   `package_version`
-   `package_hash`
-   `enabled`
-   `trust_level`
-   `created_at`

Use foreign keys and indexes where appropriate. Never store raw secrets
in these tables.

## 11.2 Proposed API endpoints

Application discovery:

``` text
GET    /api/v1/system/apps
POST   /api/v1/system/apps/refresh
GET    /api/v1/system/apps/{app_id}
GET    /api/v1/system/apps/{app_id}/capabilities
POST   /api/v1/system/apps/{app_id}/launch
```

OS permissions:

``` text
GET    /api/v1/system/permissions
GET    /api/v1/system/permissions/{capability_id}
POST   /api/v1/system/permissions/check
POST   /api/v1/system/permissions/request
DELETE /api/v1/system/permissions/{grant_id}
```

Skills:

``` text
GET    /api/v1/skills
GET    /api/v1/skills/sources
POST   /api/v1/skills/sources
POST   /api/v1/skills/inspect
POST   /api/v1/skills/install
POST   /api/v1/skills/{skill_id}/enable
POST   /api/v1/skills/{skill_id}/disable
POST   /api/v1/skills/{skill_id}/update
POST   /api/v1/skills/{skill_id}/rollback
DELETE /api/v1/skills/{skill_id}
GET    /api/v1/skills/{skill_id}/audit
```

MCP:

``` text
GET    /api/v1/mcp/servers
POST   /api/v1/mcp/servers/inspect
POST   /api/v1/mcp/servers/install
POST   /api/v1/mcp/servers/{server_id}/enable
POST   /api/v1/mcp/servers/{server_id}/disable
DELETE /api/v1/mcp/servers/{server_id}
GET    /api/v1/mcp/servers/{server_id}/tools
```

These are proposed contracts. Final endpoint design must follow the
existing API versioning and authentication architecture.

------------------------------------------------------------------------

# 12. UI/UX Requirements

## 12.1 New navigation

Consider these main sections:

-   Ruang Kerja
-   Tim Agen
-   Aplikasi
-   Keahlian (Skills)
-   Basis Pengetahuan
-   Izin & Keamanan
-   Telegram
-   Pengaturan

## 12.2 Applications screen

The Applications screen should include:

-   Search and category filters.
-   Installed / running status.
-   Publisher and version.
-   Integration availability.
-   OS permission state.
-   Supported actions.
-   Launch button.
-   Configure permissions button.
-   Last detected time.

Do not show every installed application as automatically controllable.
Show the distinction between detected, launchable, and automatable.

## 12.3 Skills screen

The Skills screen should include:

-   Curated catalog.
-   Search and categories.
-   Publisher and source.
-   Trust level.
-   Version.
-   Script presence.
-   Network access.
-   Requested capabilities.
-   Scan summary.
-   Inspect files.
-   Install disabled.
-   Enable/disable.
-   Update and rollback.
-   Uninstall and revoke grants.

## 12.4 Permission Center

The Permission Center should show:

-   OS permission status.
-   AKSA consent status.
-   App/workspace/skill scope.
-   Why the permission is needed.
-   When it was granted.
-   How to revoke it.
-   Whether a native OS prompt or manual System Settings action is
    required.

Never simulate an OS permission dialog. If the OS does not provide a
prompt for a capability, say so and use an AKSA consent dialog plus the
platform's real security controls.

------------------------------------------------------------------------

# 13. Revised Implementation Roadmap

Work in the following order. Do not build the skill marketplace before
the execution security model is fixed.

## Phase 0 --- Revalidate the current branch

-   [ ] Confirm the exact commit SHA.
-   [ ] Read `AGENTS.md` and `PROGRESS.md`.
-   [ ] Verify the current source locations listed in this review.
-   [ ] Run the existing tests.
-   [ ] Run secret and privacy scans.
-   [ ] Record all differences between this review and the current local
    checkout.

**Exit criteria:** A verified baseline report exists.

## Phase 1 --- Security and privacy blockers

-   [ ] Remove the hardcoded Kudus institutional sample.
-   [ ] Remove workspace auto-registration.
-   [ ] Remove current-working-directory fallback.
-   [ ] Require explicit workspace selection.
-   [ ] Route all file access through one authorization service.
-   [ ] Implement the centralized tool execution policy.
-   [ ] Enforce HITL for all high-risk tools.
-   [ ] Fix WebSocket authentication and isolation.
-   [ ] Move API keys to OS-backed credential storage.
-   [ ] Restrict Tauri shell commands.
-   [ ] Add a restrictive CSP.
-   [ ] Correct cloud data-processing disclosure.
-   [ ] Re-run security tests.

**Exit criteria:** No known critical permission bypass remains in the
reviewed paths.

## Phase 2 --- Native desktop foundation

-   [ ] Define the Rust native capability broker.
-   [ ] Define a typed frontend-to-native API.
-   [ ] Define a typed native-to-Python engine contract.
-   [ ] Implement per-platform adapters.
-   [ ] Implement the application inventory schema.
-   [ ] Implement the permission-state schema.
-   [ ] Implement versioned database migrations.
-   [ ] Add a secure sidecar lifecycle and handshake.
-   [ ] Remove the unrestricted renderer-to-shell path.

**Exit criteria:** Native operations are exposed only through typed,
validated commands.

## Phase 3 --- Application discovery

-   [ ] Implement Windows installed-app discovery.
-   [ ] Implement macOS installed-app discovery.
-   [ ] Implement running-app discovery.
-   [ ] Normalize duplicate applications.
-   [ ] Verify publisher/signature metadata where possible.
-   [ ] Add refresh and cache logic.
-   [ ] Add the Applications UI.
-   [ ] Add tests with mocked platform inventories.
-   [ ] Verify on real Windows and macOS devices.

**Exit criteria:** AKSA can reliably list installed apps without reading
private app data or requiring admin privileges.

## Phase 4 --- Native OS permissions

-   [ ] Implement native folder/file picker workflows.
-   [ ] Implement macOS security-scoped bookmarks if sandboxed
    distribution is used.
-   [ ] Implement macOS Accessibility status and request flow.
-   [ ] Implement macOS Screen Recording status and request flow.
-   [ ] Implement macOS Apple Events permission flow.
-   [ ] Implement Windows native file/folder picker.
-   [ ] Implement Windows screen capture consent flow where supported.
-   [ ] Implement Windows UI Automation adapter.
-   [ ] Implement permission status refresh.
-   [ ] Implement grant revocation.
-   [ ] Add permission audit events.
-   [ ] Add UI explanations and recovery links.

**Exit criteria:** AKSA can distinguish OS permission from AKSA consent
and never claims permission was granted without checking the OS.

## Phase 5 --- Application adapters and Computer Use

-   [ ] Implement generic app launcher.
-   [ ] Implement Windows UI Automation.
-   [ ] Implement macOS Accessibility API integration.
-   [ ] Improve Office adapters.
-   [ ] Improve browser integration.
-   [ ] Validate Computer Use action enums.
-   [ ] Add post-action verification.
-   [ ] Add emergency stop and cancellation tests.
-   [ ] Require approval for consequential actions.
-   [ ] Add app compatibility reporting.

**Exit criteria:** Each advertised app action is real, verified, and
permission-checked.

## Phase 6 --- Agent Skills foundation

-   [ ] Implement Agent Skills `SKILL.md` discovery.
-   [ ] Implement metadata parsing and validation.
-   [ ] Implement the AKSA extension manifest.
-   [ ] Implement source registry.
-   [ ] Implement package download quarantine.
-   [ ] Implement archive safety checks.
-   [ ] Implement static security inspection.
-   [ ] Implement package hash verification.
-   [ ] Implement install preview.
-   [ ] Implement disabled-by-default installation.
-   [ ] Implement version pinning.
-   [ ] Implement per-skill permissions.
-   [ ] Implement runtime isolation.
-   [ ] Implement rollback and uninstall.
-   [ ] Add skill security test fixtures.

**Exit criteria:** A skill can be installed without executing its
scripts, reviewed, granted limited capabilities, and run in an isolated
environment.

## Phase 7 --- Real MCP runtime

-   [ ] Implement actual MCP protocol transport.
-   [ ] Add explicit server installation.
-   [ ] Default all third-party servers to disabled.
-   [ ] Pin executable/package versions.
-   [ ] Inspect discovered tools.
-   [ ] Validate tool schemas and arguments.
-   [ ] Apply per-tool permissions.
-   [ ] Add process and network restrictions.
-   [ ] Add timeouts and cancellation.
-   [ ] Add MCP audit logs.

**Exit criteria:** MCP tools execute real server operations and cannot
bypass the central permission gateway.

## Phase 8 --- Product quality and release

-   [ ] Improve onboarding.
-   [ ] Add Windows and macOS CI builds.
-   [ ] Add security tests.
-   [ ] Add integration and end-to-end tests.
-   [ ] Add crash recovery.
-   [ ] Add installer signing.
-   [ ] Add update verification.
-   [ ] Add changelog and release notes.
-   [ ] Correct README claims.
-   [ ] Run final privacy scan.
-   [ ] Prepare a clean Git history only after the source tree is
    verified.

**Exit criteria:** A reproducible, tested release is ready for public
distribution.

------------------------------------------------------------------------

# 14. Required Test Matrix

## 14.1 Application discovery

-   [ ] Windows 10/11, 64-bit.
-   [ ] Windows machine-wide application.
-   [ ] Windows per-user application.
-   [ ] Windows Store/packaged application.
-   [ ] Windows portable application.
-   [ ] macOS `/Applications`.
-   [ ] macOS `~/Applications`.
-   [ ] macOS system application.
-   [ ] Duplicate app registrations.
-   [ ] Missing/unreadable install metadata.
-   [ ] Uninstalled application removed from cache.
-   [ ] Running app detection changes.

## 14.2 OS permission behavior

-   [ ] Permission not requested.
-   [ ] Permission granted.
-   [ ] Permission denied.
-   [ ] Permission revoked after being granted.
-   [ ] Permission requires manual settings change.
-   [ ] Native prompt cancelled.
-   [ ] App restarted after permission change.
-   [ ] Permission is unsupported on a platform.
-   [ ] AKSA consent granted but OS permission denied.
-   [ ] OS permission granted but AKSA consent denied.

## 14.3 Workspace security

-   [ ] Workspace not selected.
-   [ ] Workspace selected through native picker.
-   [ ] Workspace moved or renamed.
-   [ ] Symlink points outside authorized workspace.
-   [ ] Path traversal.
-   [ ] Workspace permission revoked during execution.
-   [ ] Two workspaces with different access rights.
-   [ ] Telegram request targets an unauthorized workspace.
-   [ ] Skill attempts to access a different workspace.
-   [ ] MCP server attempts to access a different workspace.

## 14.4 Skill security

-   [ ] Valid `SKILL.md`.
-   [ ] Missing metadata.
-   [ ] Invalid YAML.
-   [ ] Malicious prompt injection instructions.
-   [ ] ZIP path traversal.
-   [ ] Symlink escape.
-   [ ] Oversized archive.
-   [ ] Unexpected executable file.
-   [ ] Script reads environment variables.
-   [ ] Script attempts network access.
-   [ ] Script attempts to read outside workspace.
-   [ ] Script attempts to spawn an unrestricted process.
-   [ ] Skill requests an unsupported capability.
-   [ ] Skill update adds a new permission.
-   [ ] Skill package hash changes.
-   [ ] Skill is disabled during execution.
-   [ ] Uninstall revokes permissions.

## 14.5 MCP security

-   [ ] Invalid server command.
-   [ ] Unpinned package.
-   [ ] Invalid tool schema.
-   [ ] Tool argument mismatch.
-   [ ] Server returns oversized output.
-   [ ] Server times out.
-   [ ] Server process exits unexpectedly.
-   [ ] Server attempts to access secrets.
-   [ ] Server attempts unauthorized filesystem access.
-   [ ] Disabled server invocation.
-   [ ] Server permission revoked during execution.

## 14.6 Computer Use

-   [ ] Real screenshot capture.
-   [ ] Simulated screenshot fallback.
-   [ ] OS permission denied.
-   [ ] Accessibility tree unavailable.
-   [ ] Unknown action type.
-   [ ] Click outside current screen bounds.
-   [ ] App closes during action.
-   [ ] Target UI element changes.
-   [ ] Action is executed but target state does not change.
-   [ ] Emergency stop during a running task.
-   [ ] Sensitive action requires approval.

------------------------------------------------------------------------

# 15. Definition of Done

AKSA's desktop intelligence and external skills system is ready only
when all of the following are true:

1.  Installed applications can be discovered without requiring
    administrator access for ordinary inventory.
2.  Installed and running applications are distinguished.
3.  Detection does not imply automation permission.
4.  Application launching uses a registered application identity rather
    than arbitrary LLM-supplied shell commands.
5.  File access starts from a native user-selected resource.
6.  macOS protected permissions use actual OS-managed authorization
    flows.
7.  Windows uses native pickers, user ACLs, supported capture consent,
    and UAC only when truly required.
8.  AKSA consent and OS permission are tracked independently.
9.  All tool execution passes through one policy gateway.
10. Skills use a portable `SKILL.md` format.
11. External skills are inspected before installation.
12. Skill scripts are not executed during installation.
13. Skills are disabled until the user explicitly enables them.
14. Each skill receives only scoped permissions.
15. MCP servers are installed and enabled explicitly.
16. MCP tools perform real protocol calls and report accurate results.
17. Computer Use reports real, simulated, unsupported, blocked, and
    failed states accurately.
18. No feature can bypass workspace, OS, or AKSA permissions.
19. All critical security and integration tests pass on supported
    platforms.
20. Documentation describes actual behavior and known limitations.

------------------------------------------------------------------------

# 16. Instructions for an AI Coding Agent

Use these rules when implementing the plan with Codex, Claude Code,
Cursor, or another coding agent.

## Mandatory operating rules

1.  Read `AGENTS.md`, `PROGRESS.md`, and the relevant architecture
    specification first.
2.  Inspect the current code before relying on line numbers in this
    document.
3.  Do not assume the progress tracker is accurate; verify source and
    tests.
4.  Work on one phase at a time.
5.  Do not rewrite Git history or delete the GitHub repository.
6.  Do not push or publish without explicit approval.
7.  Do not reveal secret values in logs or reports.
8.  Do not create fake OS permission prompts.
9.  Do not treat an AKSA dialog as an OS permission grant.
10. Do not execute unreviewed skill scripts.
11. Do not install external packages silently.
12. Do not let an agent or skill grant itself permissions.
13. Do not report success for simulated or unexecuted actions.
14. Add tests before marking a security task complete.
15. Update `PROGRESS.md` only after tests verify the implementation.
16. If a feature cannot be secured on a platform, disable it there and
    explain the limitation.

## Prompt 1 --- Revalidate the current repository

> Perform a read-only second-pass audit of the current AKSA repository.
> Compare the current source with
> `AKSA-SECOND-PASS-REVIEW-AND-OS-INTEGRATION-SKILLS-ROADMAP.md`. Verify
> every listed finding against the current commit. Identify additional
> privacy, security, reliability, architecture, and product gaps. Do not
> modify files. Do not reveal secret values. Produce a prioritized
> report with exact file paths, line numbers, risk levels, and test
> recommendations.

## Prompt 2 --- Fix workspace and execution permissions

> Implement Phase 1 only. Remove automatic workspace authorization and
> current-working-directory fallbacks. Require explicit native folder
> selection and a validated workspace ID. Route every file operation and
> tool execution through a centralized policy gateway. Bind approvals to
> exact tool arguments and target resources. Add adversarial tests for
> path traversal, symlink escape, workspace switching, approval replay,
> and permission revocation. Do not add new features until these tests
> pass.

## Prompt 3 --- Build the native OS capability broker

> Implement Phase 2 and Phase 4 incrementally. Build a typed native
> capability broker in the Tauri Rust layer with platform-specific
> Windows and macOS adapters. Implement permission status checks and
> native permission request flows where the operating system supports
> them. For capabilities without a native permission prompt, explain the
> platform limitation and use the correct OS security boundary plus AKSA
> consent. Do not fake a system dialog. Add tests for granted, denied,
> revoked, unsupported, and needs-user-action states.

## Prompt 4 --- Build installed application discovery

> Implement Phase 3. Discover installed and running applications using
> supported native Windows and macOS APIs. Store normalized metadata and
> application identities. Do not read private application data, browser
> profiles, passwords, or user documents. Do not require administrator
> access for normal inventory. Distinguish detected, launchable, and
> automatable applications. Add platform-specific tests and an
> Applications UI.

## Prompt 5 --- Build application adapters

> Implement Phase 5. Create a typed application adapter interface. Start
> with a generic launcher and a small set of verified Office/browser
> adapters. Use native Accessibility/UI Automation APIs where available.
> Use screenshot-based Computer Use only as a fallback. Check OS
> permissions and AKSA grants before every action. Verify the actual
> resulting application state.

## Prompt 6 --- Build the external Agent Skills Manager

> Implement Phase 6 using the portable Agent Skills format. Discover and
> parse `SKILL.md`, validate an AKSA capability manifest, and support
> curated, Git, ZIP, and local sources. Download packages into
> quarantine. Validate archive paths, hashes, publisher/source, scripts,
> dependencies, network access, and requested capabilities. Show an
> installation review screen. Never execute scripts during installation.
> Install skills disabled by default and run scripts only in an
> isolated, permission-limited runtime. Add rollback, update diff,
> uninstall, and permission revocation.

## Prompt 7 --- Implement real MCP support

> Implement Phase 7. Replace placeholder MCP success responses with
> actual protocol connections and tool invocation. Default all external
> servers to disabled. Validate server identity, package version,
> transport, tool schemas, and arguments. Restrict environment
> variables, filesystem access, network access, output size, process
> lifetime, and cancellation. Route all MCP tool calls through the
> central policy gateway.

## Prompt 8 --- Final release verification

> Run the full Windows and macOS test matrix. Verify privacy
> sanitization, OS permission behavior, workspace isolation, skill
> installation, MCP execution, and Computer Use. Compare README claims
> with real test results. Produce a release-gate report. Do not push,
> publish, delete the repository, or rewrite Git history without
> explicit approval.

------------------------------------------------------------------------

# 17. Technical References

Use official documentation as the primary implementation reference.

## AKSA repository

-   [AKSA repository](https://github.com/yogijowo/aksa)
-   [AGENTS.md](https://github.com/yogijowo/aksa/blob/main/AGENTS.md)
-   [PROGRESS.md](https://github.com/yogijowo/aksa/blob/main/PROGRESS.md)
-   [System
    architecture](https://github.com/yogijowo/aksa/blob/main/docs/01-ARCHITECTURE.md)
-   [PC automation and Office
    engine](https://github.com/yogijowo/aksa/blob/main/docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md)

## Tauri security

-   [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
-   [Tauri permissions](https://v2.tauri.app/security/permissions/)
-   [Tauri shell plugin](https://v2.tauri.app/plugin/shell/)

## Windows application discovery and automation

-   [Windows UI Automation
    overview](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview)
-   [Windows application
    registration](https://learn.microsoft.com/en-us/windows/win32/shell/app-registration)
-   [Find an installed app's
    AUMID](https://learn.microsoft.com/en-us/windows/configuration/store/find-aumid)
-   [Windows app
    inventory](https://learn.microsoft.com/en-us/intune/app-management/deployment/enhanced-app-inventory)

## macOS application discovery and permissions

-   [Launch
    Services](https://developer.apple.com/documentation/coreservices/launch_services)
-   [NSWorkspace running
    applications](https://developer.apple.com/documentation/appkit/nsworkspace/runningapplications)
-   [AXIsProcessTrusted](https://developer.apple.com/documentation/applicationservices/1460720-axisprocesstrusted)
-   [NSOpenPanel](https://developer.apple.com/documentation/appkit/nsopenpanel)
-   [Security-scoped
    bookmarks](https://developer.apple.com/documentation/foundation/nsurl/)
-   [macOS App
    Sandbox](https://developer.apple.com/documentation/security/app-sandbox)

## Agent Skills

-   [Agent Skills specification](https://agentskills.io/)
-   [Agent Skills source
    repository](https://github.com/agentskills/agentskills)
-   [Anthropic skills repository](https://github.com/anthropics/skills)
-   [Microsoft skills repository](https://github.com/microsoft/skills)
-   [OpenAI Skills guide and security
    considerations](https://developers.openai.com/api/docs/guides/tools-skills)

------------------------------------------------------------------------

# Final Product Principle

**AKSA should not simply gain more access to the computer. It should
become better at understanding what access is needed, explaining why it
is needed, asking the right authority for permission, and proving that
the requested action was completed safely.**

The long-term advantage is not unrestricted control of a desktop. It is
a trustworthy AI assistant that can discover the user's tools, use them
intelligently, extend its knowledge through external skills, and remain
under the user's control.
