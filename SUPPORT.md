# Operational Readiness & Support Runbook (`SUPPORT.md`)

This document provides structured troubleshooting procedures, standardized error codes, recovery steps, and diagnostic guidelines for AKSA Desktop (`Section 18`).

---

## 1. Standardized Error Codes & Recovery Procedures

| Scenario | Error Code | User-Facing Message (ID) | Recovery Steps | Safe Diagnostic Info |
|---|---|---|---|---|
| **1. Application Fails to Start** | `ERR_APP_STARTUP` | *Aplikasi gagal dijalankan pada perangkat ini.* | Verify WebView2 Runtime (Windows) or macOS 12+ compatibility; run `npm run dev` to inspect console output. | OS version, architecture, Tauri startup log |
| **2. Python Sidecar Not Ready** | `ERR_SIDECAR_UNAVAILABLE` | *Mesin Inti AKSA belum merespons di port lokal.* | Check if port `43120` is occupied (`scripts/dev.py` auto-frees dangling ports); verify `.venv` Python installation. | `/api/v1/health` status, sidecar port |
| **3. Local AI Provider Offline** | `ERR_LOCAL_PROVIDER_OFFLINE` | *Server AI Lokal (Ollama / LM Studio) tidak dapat dijangkau. Tidak ada data yang dikirim ke cloud.* | Start Ollama (`ollama serve`) or LM Studio local server; verify `http://127.0.0.1:11434/api/tags`. | `ollama_online` boolean, `base_url` |
| **4. Cloud Provider Auth Error** | `ERR_CLOUD_AUTH_FAILED` | *Kunci API penyedia cloud tidak valid atau belum dikonfigurasi.* | Open **Pengaturan**, re-enter or rotate the API key in the OS Credential Vault, and click **Uji Koneksi**. | `provider`, `configured` boolean, `credential_ref` |
| **5. OS / AKSA Permission Denied** | `ERR_PERMISSION_DENIED` | *Akses ditolak oleh kebijakan keamanan atau Sistem Operasi.* | Open **Izin & PC**, inspect both `os_status` and `aksa_consent_state`, and grant scoped access. | `capability_id`, `os_status`, `aksa_consent_state` |
| **6. Workspace Inaccessible / Outside Jail** | `ERR_SANDBOX_VIOLATION` | *Path berada di luar Folder Kerja yang diizinkan atau menggunakan path jaringan UNC.* | Select a valid local directory via **Ruang Kerja** and ensure `allow_read` / `allow_write` scopes match the task. | `workspace_id`, requested mode (`read`/`write`/`execute`) |
| **7. Database Migration Failure** | `ERR_DB_MIGRATION` | *Pembaruan skema database lokal gagal dijalankan.* | Restore `aksa.db` from backup in `%APPDATA%\com.aksa.desktop\data`, then restart the engine. | `schema_migrations` table output |
| **8. Skill Quarantine Scan Failed** | `ERR_SKILL_QUARANTINE_REJECTED` | *Arsip keahlian ditolak karena melanggar pemeriksaan keamanan statis.* | Inspect `security_warnings` in the scan report (e.g., `../` path traversal, symlinks, case collision, or `eval`/`exec`). | `package_hash`, `risk_level`, `security_warnings` |
| **9. MCP Server Crash / Invalid Protocol** | `ERR_MCP_PROTOCOL_ERROR` | *Server MCP tidak mengembalikan respons JSON-RPC 2.0 yang valid.* | Verify the MCP binary (`npx` / `uvx`) is installed and pinned; revoke and re-register the server if needed. | `server_id`, `status` (`missing_binary` / `rpc_error` / `timeout`) |
| **10. Updater Signature Invalid** | `ERR_UPDATER_SIGNATURE` | *Pembaruan dibatalkan karena tanda tangan kriptografi paket tidak valid.* | Do not install the package; download only signed releases from the official GitHub Releases page. | Target version, SHA-256 checksum |
| **11. Application Automation / Launch Failed** | `ERR_APP_NOT_LAUNCHABLE` | *Lokasi berkas aplikasi tidak ditemukan di disk (`InstallLocation` kosong).* | Click **Pindai Ulang Perangkat** in **Aplikasi PC** or verify the software is installed locally. | `app_id`, `launch_status`, `detection_sources` |
| **12. Data Restore / Backup Recovery** | `ERR_BACKUP_RESTORE` | *Pemulihan cadangan berkas gagal diverifikasi.* | Locate timestamped `.bak` files inside `<workspace>/.aksa_backup/` and copy back to the target filename. | Backup filename, timestamp, byte size |
| **13. Credential Compromise** | `ERR_CREDENTIAL_REVOKED` | *Kredensial penyedia telah dicabut dari brankas keamanan.* | Immediately revoke the key at the provider's console, then call `DELETE /api/v1/models/keys/{provider}` in AKSA. | `credential_ref`, revocation audit event ID |
| **14. Security Incident / Emergency Stop** | `ERR_EMERGENCY_STOP_ACTIVE` | *Operasi dihentikan seketika karena Tombol Darurat (Emergency Stop) aktif.* | Press `Ctrl+Shift+Q` or trigger **Revoke All Workspaces** (`POST /api/v1/workspaces/revoke-all`), review audit logs, then reset Emergency Stop when safe. | `permission_audit_events` ledger |

---

## 2. Generating a Safe Support Bundle

Before escalating an issue, generate a sanitized diagnostic report:

```bash
curl -s http://127.0.0.1:43120/api/v1/system/diagnostics/support-bundle
```

The support bundle automatically strips all API keys, bearer tokens, passwords, and document contents (`redaction_verified: true`). Always inspect the JSON output before attaching it to a support ticket.
