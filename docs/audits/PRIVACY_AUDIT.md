# Privacy Audit Report — AKSA Repository

**Audit Date:** 2026-11-17  
**Status:** Completed  
**Auditor:** Automated Engineering Audit  

---

## 1. Summary of Identified Privacy & Personal Data Candidates

| Item | Found Location | Severity | Category | Remediation Status |
| :--- | :--- | :--- | :--- | :--- |
| Machine-specific path `/Users/lpsekudus/agent` | `services/engine/app/api/routes.py` | **Critical** | Machine Path / Auto-registration | **REMEDIATED**: Removed machine auto-registration; workspaces resolved strictly via DB |
| Machine-specific paths `/Users/lpsekudus/...` | `apps/desktop/src/stores/useAksaStore.ts`, `TelegramGatewayView.tsx`, `FeatureSectionsView.tsx` | **Critical** | Machine Path / Developer Username | **REMEDIATED**: Replaced with clean dynamic fallbacks and generic examples |
| Real Person Name & NIP (`DWI YUSI SASEPTI, S.Sos., MM.`, `NIP. 19740919 199303 2 002`) | `services/engine/app/core/orchestrator.py` | **Critical** | Personal Identifiable Info (PII) / Government Official | **REMEDIATED**: Replaced with generic dynamic PyMuPDF + python-docx extractor |
| Real Institution Letterhead & Contact Info (`PEMERINTAH KABUPATEN KUDUS`, `Jl. R. Agil Kusumadya No. 1`, `(0291) 438119`) | `services/engine/app/core/orchestrator.py` | **High** | Real Organizational Identity | **REMEDIATED**: Removed all hardcoded institutional data |
| Hardcoded Procurement Data (`Sounding Market`, `Rp 100.497.593`, `ID RUP 68951579`) | `services/engine/app/core/orchestrator.py` & `PROGRESS.md` | **High** | Real Document Content | **REMEDIATED**: Removed hardcoded procurement tables; dynamically extracted from PDF |
| Developer path `D:\projects\aksa` | `services/engine/app/api/routes.py`, `orchestrator.py`, `telegram/handlers.py`, `useAksaStore.ts` | **Medium** | Machine Path | **REMEDIATED**: Replaced with dynamic `workspace_id` resolution |
| Simulation Telegram username `budi_santoso` | `services/engine/app/api/routes.py` | **Low** | Personal Name in Demo | **REMEDIATED**: Replaced with neutral identifier `pengguna_demo` |
| Tracked Excel Artifact `Rekap_Otomatis_AKSA.xlsx` | Root workspace directory (`/Rekap_Otomatis_AKSA.xlsx`) | **Medium** | Tracked Binary Output | **REMEDIATED**: Untracked via `git rm --cached`; ignored in `.gitignore` |

---

## 2. Detailed Findings & Actions

### 2.1 Developer Username & Path Removal
- **File:** `services/engine/app/api/routes.py`
  - **Issue:** Endpoint `/api/v1/workspaces` inspected `/Users/lpsekudus/agent` on disk and automatically registered it into the database.
  - **Action:** Delete the entire auto-registration block. Workspaces must only be registered through explicit user interaction via the UI folder picker or API.
- **File:** `apps/desktop/src/stores/useAksaStore.ts`
  - **Issue:** Initial workspaces and fallback paths defaulted to `/Users/lpsekudus/agent` or `D:\projects\aksa`.
  - **Action:** Replace with dynamic workspace detection or empty initial list with clear empty state.

### 2.2 Removal of Real Government Procurement Records
- **File:** `services/engine/app/core/orchestrator.py`
  - **Issue:** Function `_create_word_duplicate_from_pdf` hardcoded an entire 11-row procurement sounding document containing official letterhead, phone numbers, addresses, and the name, title, and NIP of a civil servant.
  - **Action:** Remove the `if "sounding" in source_pdf.name.lower():` branch entirely. Convert PDF to Word dynamically by extracting structured text and tables using PyMuPDF and `python-docx` without any hardcoded institutional or personal data.

### 2.3 Secret Scanning
- Scanned repository for live tokens, private keys, and passwords.
- No live cloud API keys were committed in plaintext tracked files, but `/api/v1/models/providers` previously exposed plaintext API keys to clients, and `services/engine/tests/test_phase2_orchestrator.py` used synthetic dummy keys (`sk-test-key-123`).
- API key masking must be enforced on all provider responses.
