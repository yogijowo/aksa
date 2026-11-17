# AKSA --- Audit Delta, Adaptive Agent Learning, Dynamic Model Catalog & Skills Ecosystem

## Master Implementation Plan \| 17 November 2026

> **Status:** spesifikasi audit dan rencana implementasi berdasarkan
> static review source `main` yang tersedia pada 17 November 2026 serta
> dokumentasi provider/skills yang ditinjau pada tanggal yang sama.
> Dokumen ini bukan bukti bahwa perbaikan sudah diterapkan. Build, test
> suite, packaging, dan pengujian Windows/macOS belum dijalankan oleh
> penyusun dokumen ini.

------------------------------------------------------------------------

# 0. Ringkasan eksekutif

AKSA perlu dikembangkan menjadi desktop AI agent yang:

1.  **Secure by default:** backend tidak terbuka tanpa autentikasi,
    akses file mengikuti workspace dan permission, tindakan berisiko
    memerlukan persetujuan, dan rahasia disimpan melalui fasilitas OS.
2.  **Adaptif per agent:** setiap agent memiliki direktori, profil,
    memori, skill hasil pembelajaran, evaluasi, dan artefak sendiri di
    bawah root directory AKSA yang dipilih pengguna.
3.  **Belajar secara terkendali:** pola kerja berulang dan berhasil
    dapat menjadi candidate skill; AKSA tidak menyimpan semua percakapan
    mentah, kredensial, atau data sensitif sebagai "pembelajaran".
4.  **Dynamic model discovery:** model diambil dari API resmi provider,
    bukan daftar permanen di source code.
5.  **Skills marketplace:** mendukung Agent Skills format, sumber resmi,
    komunitas global, dan skill Bahasa Indonesia; semua paket masuk
    quarantine, dipindai, diberi provenance, dan dipasang dengan izin
    jelas.
6.  **Native OS permissions:** status permission tidak boleh dipalsukan;
    AKSA menggunakan native API/picker dan memverifikasi hasil tindakan.
7.  **Evidence-based release:** tidak mengklaim
    enterprise/production-ready sebelum bukti test dan OS verification
    tersedia.

## Keputusan arsitektur utama

  -----------------------------------------------------------------------
  Area                                Keputusan
  ----------------------------------- -----------------------------------
  Agent learning                      Folder terisolasi per agent di
                                      bawah root AKSA

  Memory                              Pisahkan episodic, semantic,
                                      preferences, dan learned skills

  Learned skill                       Candidate → validate →
                                      approve/promote → version →
                                      rollback

  Skill format                        Ikuti Agent Skills `SKILL.md`
                                      specification

  Shared skills                       Immutable, versioned shared catalog

  Provider models                     Provider adapters + live
                                      discovery + cache + normalized
                                      capabilities

  Model IDs                           Simpan ID asli provider; jangan
                                      menebak alias

  Permissions                         Native OS status terpisah dari AKSA
                                      consent

  File access                         Workspace registry + sandbox
                                      policy + path canonicalization

  HITL                                Grant terikat session, agent,
                                      workspace, tool, target, dan
                                      argument hash

  Secrets                             Windows Credential Manager/DPAPI
                                      dan macOS Keychain native

  External skills                     Quarantine → scan → inspect →
                                      approval → install

  Learning data                       Redacted task summary dan workflow
                                      metadata; bukan raw chat dump
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 1. Scope dan batas audit

Audit sebelumnya merupakan **static source review** atas repository
`main`. Audit tersebut tidak membuktikan bahwa aplikasi berhasil
dikompilasi, test lulus, sidecar berjalan di installer, permission OS
muncul, atau perilaku Windows/macOS sama. Setiap klaim `fixed`,
`tested`, atau `production ready` harus disertai commit, hasil CI, log
pengujian, dan matriks OS.

## 1.1 Temuan audit terbaru

### P0 --- Backend authentication dan sidecar lifecycle

**Source:** `services/engine/app/config.py`,
`services/engine/app/main.py`, `scripts/dev.py`,
`apps/desktop/src-tauri/src/lib.rs`,
`apps/desktop/src-tauri/src/sidecar.rs`.

Temuan: - Default config terlihat menggunakan `dev_mode=True` dan token
development statis. - HTTP dan WebSocket auth dapat dilewati ketika mode
development aktif. - Script development menjalankan Uvicorn tanpa flag
production. - Tauri setup belum terlihat mengelola
spawn/readiness/health/shutdown sidecar secara lengkap. - Token acak
dari Rust belum terlihat dipass secara aman ke Python sidecar.

Perbaikan wajib: 1. Release default harus `dev_mode=False`; dev mode
hanya melalui konfigurasi development eksplisit. 2. Release menolak
token kosong, statis, atau known development token. 3. Generate token
ephemeral dengan CSPRNG; pass melalui environment/IPC, bukan command
line. 4. Bind backend ke loopback saja. 5. Auth wajib untuk HTTP
sensitif dan WebSocket, tanpa bypass release. 6. Tauri supervisor
mengelola spawn, readiness, health, restart terbatas, graceful shutdown,
dan orphan cleanup. 7. Tambahkan integration tests untuk token
hilang/salah, release config, sidecar startup/shutdown, dan installer.
8. Jangan pernah menyimpan token ke log.

**Reproduction:** jalankan release engine, panggil route sensitif dan
WebSocket tanpa token atau token salah; semua harus ditolak. Jalankan
desktop app, pastikan sidecar siap dan berhenti ketika aplikasi ditutup.

### P0 --- Workspace/RAG authorization dan path traversal

**Source:** `api/routes/orchestrate.py`, `api/routes/workspaces.py`,
`api/routes/rag.py`, `api/routes/system.py`, `core/orchestrator.py`,
`core/sandbox.py`.

Temuan: - `workspace_path` dapat menunjuk folder existing yang belum
tentu terdaftar. - Jika workspace policy record tidak ditemukan, ada
jalur yang memberi read/write default. - Workspace creation menerima
arbitrary folder dan default permission read/write. - RAG indexing
menerima `workspace_id` dan `folder_path` yang belum tampak dipastikan
konsisten. - File listing belum terlihat memeriksa `allow_read`. -
`system/open-path` menerima absolute path tanpa scope workspace yang
memadai.

Perbaikan wajib: 1. Hapus fallback `allow_read=True` dan
`allow_write=True`. 2. Semua workspace dibuat melalui native folder
picker atau izin eksplisit. 3. Operasi file menerima `workspace_id`,
bukan path bebas dari model. 4. Resolve workspace ID ke canonical path
melalui repository tepercaya. 5. Validasi canonical path dan cegah
symlink/junction/reparse-point escape. 6. RAG path diturunkan dari
workspace record, bukan request bebas. 7. Semua
list/read/write/delete/move/execute/open melewati satu
`WorkspacePolicyGateway`. 8. Default deny; read, write, execute adalah
capability terpisah. 9. `system/open-path` hanya membuka resource yang
diizinkan. 10. Jangan izinkan agent mendaftarkan workspace tepercaya
sendiri.

**Tests:** `../`, absolute path, UNC path, symlink, Windows junction,
path mismatch, `allow_read=false`, `allow_write=false`, dan RAG folder
di luar workspace harus ditolak.

### P0 --- Native OS permission masih disimulasikan

**Source:** `core/permission_broker.py`, Tauri native adapters.

Temuan: - Beberapa Windows capabilities terlihat hardcoded `GRANTED`. -
macOS `NEEDS_USER_ACTION` masih dapat menghasilkan AKSA grant sukses
tanpa verifikasi OS. - Belum terlihat integrasi penuh TCC, native folder
picker, atau security-scoped bookmarks.

Perbaikan wajib: 1. Pisahkan `os_permission_status`,
`aksa_consent_status`, dan `capability_effective_status`. 2.
`NEEDS_USER_ACTION` tidak boleh dianggap effective `GRANTED`. 3. Jangan
mengarang OS permission prompt untuk capability yang memang tidak
memiliki prompt global. 4. macOS: Screen Recording/TCC, Accessibility,
NSOpenPanel, security-scoped bookmarks. 5. Windows: supported capture
API, UI Automation API, native folder picker; sebagian capability
mungkin hanya memerlukan AKSA consent, bukan global OS prompt. 6.
Verifikasi capability secara nyata sebelum UI menampilkan "Aktif". 7.
Revocation menghentikan job terkait dan membersihkan handle/session.

### P0 --- HITL grant tidak terikat penuh ke tindakan

**Source:** `api/routes/hitl.py`, HITL request models,
`core/sandbox.py`, `core/tool_registry.py`, MCP execution.

Temuan: - Request HITL belum terlihat menerima seluruh konteks action:
arguments, session, workspace, action ID. - Grant dapat dibuat tanpa
binding yang cukup. - `resource_path` tersimpan tetapi belum terlihat
diverifikasi ulang. - Session/workspace validation dapat terlewati bila
konteks kosong. - MCP side-effecting tool berisiko `MEDIUM` dapat lolos
dari approval.

Perbaikan wajib: 1. Buat immutable `ActionIntent`: `action_id`,
`session_id`, `agent_id`, `workspace_id`, `tool_name`,
`canonical_target`, `arguments_hash`, `risk_level`, `expires_at`. 2.
Approval menampilkan target dan dampak yang jelas. 3. Grant single-use,
short-lived, dan mengikat seluruh field. 4. Hash arguments dihitung
ulang saat eksekusi; target/payload berubah → grant invalid. 5. Missing
context/mismatch → fail closed. 6. Risk level ditentukan tool policy,
bukan klaim model. 7. External MCP tool default approval-required. 8.
Semua side-effecting tools melewati satu gateway. 9. Pisahkan
`action_submitted`, `action_completed`, `postcondition_verified`.

### P0 --- Privacy policy belum persistent/fail-closed

**Source:** `core/privacy_gate.py`, `main.py`, settings repository, LLM
router.

Temuan: - Privacy gate memiliki default cloud mode. - `configure()`
terlihat mengubah in-memory state; persistence/restore belum tampak. -
Confidential data belum selalu memerlukan consent spesifik. -
Classification berbasis marker teks tidak cukup.

Perbaikan wajib: 1. Persist privacy settings dan load sebelum menerima
request. 2. Jika settings gagal dibaca, default ke mode paling
konservatif (`LOCAL_ONLY`). 3. Tampilkan provider/model/data category
sebelum data sensitif dikirim. 4. Consent harus spesifik terhadap data
dan tindakan. 5. Klasifikasi: public, internal, confidential,
restricted/personal. 6. Gabungkan metadata file, workspace labels, user
labels, dan content inspection. 7. Jangan hanya mengandalkan marker
NIK/NPWP. 8. Redact secret/PII sebelum prompt, log, analytics, memory,
dan learned skill. 9. LOCAL_ONLY harus memblokir semua cloud routing;
tidak boleh fallback diam-diam.

### P0/P1 --- Credential vault bukan native-only

**Source:** `core/credential_vault.py`.

Temuan: - macOS Keychain command terlihat masih disertai penyimpanan
lokal. - Secret dikirim sebagai command-line argument pada sebagian
alur. - Master key disimpan dekat ciphertext. - Ada custom crypto scheme
yang tidak layak menjadi pengganti crypto standard.

Perbaikan: - Hapus custom crypto. - Windows: Credential Manager/DPAPI
native. - macOS: Keychain Services API. - Jangan pass secret melalui
command line. - Jika OS secure store gagal, fail closed untuk credential
cloud. - Database hanya menyimpan credential reference/handle. - Redact
key dari logs, exception, crash report, telemetry. - Migration
credential lama harus aman; jika tidak bisa, minta user memasukkan
ulang.

### P1 --- External skills installer belum lengkap

**Source:** `core/skill_manager.py`, skills API routes, UI marketplace,
orchestrator.

Temuan: - Route upload/scan/install external ZIP/repository belum
terlihat lengkap. - Curated install tampak membuat SKILL.md dari
preview, bukan memasang paket penuh. - Hash skill tampak berasal dari
ID, bukan bytes paket. - `publisher.verified` dapat berasal dari
manifest tanpa bukti. - Runtime skill belum terlihat terhubung penuh ke
orchestrator. - Static scan beberapa string Python tidak cukup menjadi
security boundary.

Perbaikan: 1. Dukung official registry, Git repo, ZIP, direct SKILL.md
URL, local folder. 2. Semua paket masuk quarantine. 3. Batasi ukuran,
timeout, redirect, host, dan content type. 4. Hash SHA-256 dari bytes
paket aktual. 5. Catat exact commit/tag, publisher, license, provenance.
6. `verified` hanya dari trust verification service. 7. Scan seluruh
file type/dependency; jangan mengandalkan string scan sederhana. 8.
Jangan jalankan script saat install. 9. Tampilkan scripts,
network/filesystem requirements, license, publisher, version, hash, risk
report. 10. Minta persetujuan user. 11. Script skill hanya berjalan di
sandbox dengan permission minimal. 12. Dukung lifecycle
installed/enabled/disabled/quarantined/update/revoked. 13. Runtime
menggunakan progressive disclosure. 14. Catat skill yang digunakan pada
task.

### P1 --- MCP lifecycle/protocol belum lengkap

**Source:** `core/mcp_client.py`, tool registry, MCP server config.

Perbaikan: - Implement initialize request → tunggu response →
initialized notification → tools/list → schema validation → tool call →
cancellation → shutdown. - Long-lived process dengan restart policy. -
Pin package version/commit/checksum; hindari `npx -y`/`uvx` tanpa
pinning. - Environment allowlist; jangan wariskan seluruh env. - Tool
per-server/per-tool risk policy. - Timeout, output limit, rate limit,
cancellation, audit. - Default disabled dan approval-required untuk side
effects.

### P1 --- Computer Use belum memverifikasi hasil

**Source:** `core/computer_use.py`, Windows/macOS adapters.

Perbaikan: - Windows UIA tree harus nyata, bukan kesimpulan dari
`sys.platform`. - macOS gunakan Accessibility API. - Screen capture
memeriksa native permission. - `postcondition_verified=true` hanya jika
postcondition teramati. - Jika tidak bisa diverifikasi, status
`unknown`, bukan success. - Emergency stop menghentikan input queue,
job, subprocess. - Approval untuk submit/send/delete/purchase/config
change.

### P1 --- App discovery belum menyeluruh

**Source:** `core/app_discovery.py`, permission broker, apps routes.

Perbaikan: - Windows: uninstall registry, Start Menu, MSIX/packaged
apps, AppUserModelID. - macOS: Launch Services, app bundle metadata,
standard application directories. - Validasi executable path dan code
signature bila tersedia. - Pisahkan `discovered`, `signature_valid`,
`launchable`, `automation_supported`, `connected`,
`permission_granted`. - Toggle DB tidak boleh mengklaim native
permission sudah diberikan.

### P1 --- WebSocket session ownership

Subscription ownership yang hanya berada di memory belum cukup. Setiap
session harus memiliki owner identity yang diverifikasi terhadap
principal/database. Reconnect hanya untuk owner atau delegated identity
yang valid.

### P2 --- Test coverage dan klaim release

Progress file mengklaim 100%/16 tests/production ready, tetapi test yang
terlihat belum menutup P0 di atas dan belum ada bukti OS matrix. Ganti
klaim progress dengan status berbasis bukti: implemented, unit-tested,
integration-tested, os-verified, release-verified.

------------------------------------------------------------------------

# 2. Arsitektur Adaptive Agent Learning

## 2.1 Tujuan

Setiap agent semakin memahami pekerjaan yang menjadi tanggung jawabnya.
Contoh: - Agent Video: visual style, pacing, typography, Remotion
workflow, export profile. - Agent Design: design system, warna, layout,
tone visual, ukuran asset, pola revisi. - Agent Coding: stack project,
conventions, testing commands, deployment patterns. - Agent
PBJ/administrasi: format dokumen, alur pemeriksaan, checklist,
terminologi.

Pembelajaran harus spesifik per agent. Jangan mencampur memori Agent
Video ke Agent PBJ kecuali pengguna secara eksplisit membagikan skill.

## 2.2 Root directory pilihan pengguna

Saat first-run atau Settings → Storage & Data: 1. Minta user memilih
root directory melalui native folder picker. 2. Periksa write
permission, free space, filesystem, removable/network volume. 3.
Tampilkan struktur yang akan dibuat. 4. Izinkan migrasi root directory
secara terkontrol. 5. Jangan fallback ke `Path.cwd()` atau first
workspace. 6. Root folder bukan berarti semua subfolder otomatis
trusted.

### Struktur folder

``` text
<AKSA_ROOT>/
├── system/
│   ├── registry/
│   ├── provider-cache/
│   ├── skill-catalog-cache/
│   └── migrations/
├── shared/
│   ├── skills/<skill-name>/<version>/
│   └── templates/
├── agents/
│   ├── <agent-uuid>/
│   │   ├── agent.json
│   │   ├── PROFILE.md
│   │   ├── memory/
│   │   │   ├── episodic/
│   │   │   ├── semantic/
│   │   │   ├── preferences/
│   │   │   └── indexes/
│   │   ├── skills/
│   │   │   ├── installed/
│   │   │   ├── learned/
│   │   │   ├── candidates/
│   │   │   ├── disabled/
│   │   │   └── evaluations/
│   │   ├── workflows/
│   │   ├── knowledge/
│   │   ├── projects/
│   │   ├── artifacts/
│   │   ├── evaluations/
│   │   ├── state/
│   │   └── logs/
│   └── <another-agent-uuid>/
├── workspaces/
├── quarantine/
│   ├── skills/
│   ├── mcp/
│   └── files/
├── backups/
└── exports/
```

Aturan: - Agent ID adalah UUID internal. - Folder dibuat melalui storage
service, bukan model. - Canonicalize path dan cegah symlink/junction
escape. - Folder logs tidak menyimpan raw prompt, token, atau sensitive
file content secara default. - `shared/skills` immutable per versi. -
Learned skill tetap di folder agent pemilik kecuali user
mempromosikannya menjadi shared skill.

## 2.3 Pisahkan empat jenis pembelajaran

### Episodic memory

Ringkasan task: intent, waktu/status, agent, skills/tools, outcome,
feedback, error/recovery. Simpan ringkasan teredaksi, bukan full
conversation.

### Semantic memory

Fakta stabil dan pengetahuan domain yang diverifikasi: project
conventions, SOP, istilah, keputusan desain, constraints, sumber. Setiap
item memiliki provenance, timestamp, confidence, review/expiry policy.

### Preference profile

Preferensi format dokumen, bahasa, visual style, output dimensions,
preferred tools, workflow. Jangan menyimpulkan preferensi sensitif tanpa
dasar; perubahan penting dapat meminta konfirmasi.

### Learned skills

Prosedur berulang: preconditions, langkah, tools, decision rules, output
validation, recovery, test cases. Skill bukan catatan chat; skill harus
menjadi prosedur yang bisa dipakai ulang.

## 2.4 Learning pipeline

``` text
Task started
  -> capture minimal task metadata
  -> execute through policy gateway
  -> collect outcome, validation, and user feedback
  -> redact secrets, PII, and confidential payloads
  -> extract reusable pattern
  -> detect duplicate and confidence
  -> create candidate skill in agent/skills/candidates/
  -> validate structure and evaluate in sandbox
  -> user review (or safe instruction-only auto-approval policy)
  -> promote to learned/<skill>/<version>/
  -> record evaluation, version, and rollback pointer
```

Ambang awal: - Pola muncul minimal 3 kali pada pekerjaan berbeda, atau
user secara eksplisit meminta "jadikan skill". - Minimal dua hasil
berhasil/feedback positif. - Tidak ada unresolved policy violation. -
Tidak bergantung pada secret/PII/confidential content. - Memiliki
langkah dan output validation. - Satu pekerjaan saja masuk episodic
memory, bukan otomatis menjadi skill.

## 2.5 Contoh struktur learned skill

``` text
agents/<agent-id>/skills/learned/
└── short-video-workflow/
    └── 1.0.0/
        ├── SKILL.md
        ├── references/
        ├── assets/
        ├── tests/
        └── provenance.json
```

Contoh `SKILL.md`:

``` markdown
---
name: short-video-workflow
description: Creates short-form videos using the approved workflow for this agent. Use for recurring short-video production tasks.
metadata:
  owner-agent: "<agent-id>"
  source: "learned"
  version: "1.0.0"
---

# Workflow
1. Confirm platform, aspect ratio, and duration.
2. Prepare narrative outline and source list.
3. Divide story into scenes and create shot list.
4. Draft voice-over and on-screen text.
5. Validate factual claims.
6. Build composition using approved toolchain.
7. Render preview.
8. Check pacing, legibility, audio balance, and safe margins.
9. Request review before final export when required.

# Validation
- Output dimensions and duration.
- Text safe margins.
- Audio peak and speech intelligibility.
- No unsupported factual claims.
```

Ini contoh format, bukan klaim preferensi yang sudah diketahui agent.
Isi skill harus berasal dari pola pekerjaan nyata yang telah dievaluasi.

## 2.6 Skill lifecycle dan safety

Status: `candidate`, `validated`, `active`, `disabled`, `deprecated`,
`quarantined`, `revoked`.

Setiap versi immutable. Sediakan diff, evaluation history, usage,
success rate, feedback, source task references, rollback, delete/export.

Jangan simpan ke learned skill: - API keys, password, cookies, session
tokens, private keys; - NIK, NPWP, rekening, alamat pribadi, PII; -
confidential/restricted data tanpa izin eksplisit; - full raw
conversation sebagai default; - prompt injection dari web/PDF/email yang
berusaha mengubah policy.

Semua file, web pages, emails, PDFs, skills, dan tool output adalah
**untrusted data**.

Learning mode: - Off - Suggest only - Learn approved workflows
(recommended) - Advanced auto-learning (instruction-only candidate,
rollback/audit tetap wajib)

Default yang disarankan: **Suggest only** atau **Learn approved
workflows**. Jangan auto-run arbitrary code.

## 2.7 Service dan API

Service: - `AgentDirectoryService` - `AgentProfileService` -
`AgentMemoryService` - `AgentLearningService` -
`SkillCandidateExtractor` - `SkillEvaluator` - `SkillVersionService` -
`AgentIsolationPolicy` - `LearningPrivacyFilter`

Endpoint usulan: - `GET/POST /agents` -
`GET/PATCH/DELETE /agents/{agent_id}` -
`GET /agents/{agent_id}/memory` -
`POST /agents/{agent_id}/memory/search` -
`GET /agents/{agent_id}/skills` -
`POST /agents/{agent_id}/skills/candidates` -
`POST /agents/{agent_id}/skills/{skill_id}/evaluate` -
`POST /agents/{agent_id}/skills/{skill_id}/promote` -
`POST /agents/{agent_id}/skills/{skill_id}/rollback` -
`POST /agents/{agent_id}/skills/{skill_id}/disable`

Semua endpoint memakai auth, ownership, path policy, dan audit trail.

------------------------------------------------------------------------

# 3. Dynamic Provider Model Discovery

## 3.1 Prinsip

Setelah API key tersimpan, AKSA: 1. Memanggil model-list endpoint resmi.
2. Menyimpan cache dan metadata. 3. Menormalisasi capabilities. 4.
Memeriksa lifecycle, pricing, availability. 5. Menampilkan model yang
dapat diakses API key. 6. Refresh manual/berkala. 7. Menandai model
deprecated/retired tanpa mengganti model aktif diam-diam.

Daftar berikut adalah **contoh model yang terlihat di dokumentasi saat
riset 17 November 2026**, bukan daftar permanen yang harus ditanam di
kode.

## 3.2 Provider dan discovery

  ---------------------------------------------------------------------------------------------------------------
  Provider                Contoh katalog saat     Discovery
                          riset                   
  ----------------------- ----------------------- ---------------------------------------------------------------
  OpenAI                  GPT-6 Astra, GPT-6.1    `GET https://api.openai.com/v1/models`
                          Sol, GPT-6.1 Terra,     
                          GPT-6 Luna;             
                          GPT-Image-2.6;          
                          audio/realtime          

  Anthropic               Claude Opus 5.5, Sonnet `GET https://api.anthropic.com/v1/models`
                          5.5, Haiku 5.5, Fable   
                          5.2                     

  Google Gemini           Gemini 4 Carbon, Argon, `GET https://generativelanguage.googleapis.com/v1beta/models`
                          Hydrogen; media models  
                          sesuai akses            

  xAI                     Grok 4.7;               Gunakan official model endpoint dari API account
                          image/video/voice APIs  
                          terpisah                

  Mistral                 Mistral Large 4, Small  `GET https://api.mistral.ai/v1/models`
                          4, Voxtral, OCR 4.1,    
                          embeddings/moderation   

  DeepSeek                V4-Pro, V4-Flash,       Official model list endpoint; simpan exact IDs
                          V4-Flash-Vision-Exp     

  Groq                    GPT-OSS 120B/20B,       `GET https://api.groq.com/openai/v1/models`
                          Llama, Whisper, preview 
                          models bila tersedia    

  OpenRouter              Multi-provider catalog  `GET https://openrouter.ai/api/v1/models`; `/models/user` untuk
                          dan model               akses API key
                          image/video/embedding   

  Ollama                  Model lokal yang sudah  `GET http://localhost:11434/api/tags`
                          di-pull                 

  LM Studio               Model server lokal      OpenAI-compatible `/v1/models` pada base URL lokal
  ---------------------------------------------------------------------------------------------------------------

Provider tahap berikutnya: Together AI, Fireworks, Cerebras, NVIDIA NIM,
Azure OpenAI, AWS Bedrock, Vertex AI, Hugging Face Inference Providers,
dan custom local endpoints.

Catatan: - Provider docs dan API responses menjadi source of truth. -
Gemini API dan Vertex AI dapat memerlukan adapter berbeda. -
OpenAI-compatible API tidak berarti semua fitur kompatibel identik. -
Jangan menebak model ID atau capability. - Simpan timestamp dan sumber
metadata.

## 3.3 Internal model schema

``` typescript
type ModelCapability =
  | "text_input" | "image_input" | "audio_input" | "video_input" | "pdf_input"
  | "text_output" | "image_output" | "audio_output" | "video_output"
  | "tool_calling" | "json_schema" | "streaming" | "reasoning"
  | "computer_use" | "embeddings" | "transcription" | "moderation";

interface DiscoveredModel {
  provider_id: string;
  provider_model_id: string; // exact ID returned by provider
  display_name: string;
  description?: string;
  capabilities: ModelCapability[];
  context_window?: number;
  max_output_tokens?: number;
  input_modalities: string[];
  output_modalities: string[];
  pricing?: {
    input_per_million?: number;
    output_per_million?: number;
    currency: string;
    source: "provider" | "catalog" | "unknown";
    checked_at: string;
  };
  lifecycle: "active" | "preview" | "deprecated" | "retired" | "unknown";
  availability: "available" | "unavailable" | "requires_access" | "unknown";
  provider_metadata: Record<string, unknown>;
  discovered_at: string;
  last_verified_at: string;
}
```

## 3.4 Services dan UX

Services: - `ProviderRegistry` - `ProviderAdapter` -
`ModelDiscoveryService` - `ModelCapabilityNormalizer` -
`ModelLifecycleService` - `ModelPricingCache` - `ModelHealthProbe` -
`ModelRecommendationService`

UI provider: - Provider/key status (key tidak pernah ditampilkan
penuh). - Test connection. - Refresh models. - Last refreshed. - Model
count dan error status.

UI catalog: - Search/filter by provider, capability, local/cloud,
free/paid. - Sort by recommended, cost, latency, context, newest. -
Lifecycle: Stable, Preview, Deprecated. - Price estimate, context,
provider origin. - Set default per role/task.

Role-based routing: - General conversation. - Coding. -
Planning/reasoning. - Vision/computer use. - Image generation. - Video
generation. - Speech/transcription. - Embeddings/RAG. - Lightweight
routing/classification.

Jangan menggunakan satu model default untuk semua pekerjaan. Pilih
berdasarkan capability, privacy, cost, latency, dan preference.

## 3.5 Discovery lifecycle

-   Cache 6--24 jam, manual refresh tersedia.
-   Retry exponential backoff dan rate limit per provider.
-   Provider failure tidak menghapus cache.
-   Model yang hilang diberi `unknown/unavailable` sampai diverifikasi.
-   Preview bukan default.
-   Deprecated/retired tidak digunakan untuk task baru tanpa override.
-   Jangan silently remap pinned model.
-   Jika default model retired, tampilkan warning dan minta konfirmasi.

## 3.6 Security

-   API key hanya di native secure storage.
-   Provider request melalui backend.
-   Redact error bodies.
-   TLS verification.
-   Custom base URL harus dibatasi dan dilindungi dari SSRF.
-   Jangan fetch arbitrary URL dari metadata model.
-   LOCAL_ONLY memblokir seluruh cloud providers.

------------------------------------------------------------------------

# 4. Agent Skills marketplace

## 4.1 Format standar

Satu skill minimal:

``` text
skill-name/
├── SKILL.md
├── scripts/       # optional
├── references/    # optional
├── assets/        # optional
└── LICENSE        # recommended
```

`SKILL.md` berisi YAML frontmatter minimal `name` dan `description`.
Nama harus sesuai aturan specification dan folder. Implementasikan
progressive disclosure: metadata saat startup, full instructions ketika
relevan, resources saat diperlukan.

## 4.2 Sumber global

-   `https://skills.sh/` --- leaderboard, trending, official skills,
    packs.
-   `https://agentskills.io/` --- Agent Skills specification.
-   `https://github.com/anthropics/skills` --- official Anthropic
    skills.
-   `https://github.com/vercel/agent-skills` --- frontend/design/web
    guidelines.
-   `https://github.com/remotion-dev/skills` --- official Remotion
    skills.
-   `https://github.com/remotion-dev/agent-plugin` --- Remotion agent
    plugin.
-   `https://github.com/heygen-com/hyperframes` --- HyperFrames
    video/motion workflows.
-   `https://github.com/vercel-labs/agent-browser` --- browser
    automation.
-   `https://github.com/microsoft/skills` --- Microsoft ecosystem
    skills.

## 4.3 Sumber Indonesia/Bahasa Indonesia

-   `https://github.com/prisma-ddti/skills` --- Agent Skills Bahasa
    Indonesia untuk pekerjaan teknis/nonteknis perpustakaan.
-   `https://github.com/iizcm/find-skills-skill` --- Find Skills dengan
    instruksi Bahasa Indonesia.
-   `https://github.com/iizcm/web-design-guidelines-skill` --- web
    design guidelines berbahasa Indonesia.
-   `https://github.com/nothinx/naskah-id` --- penulisan/penyuntingan
    karya ilmiah Bahasa Indonesia.
-   `https://github.com/flaqai/awesome_codex_skills` --- katalog skill
    dengan README Bahasa Indonesia.

Daftar tersebut adalah sumber yang perlu dikurasi, bukan jaminan paket
aman/aktif. Popularitas global tidak sama dengan popularitas Indonesia.
Tampilkan source, timestamp, stars/downloads jika tersedia, dan license
secara transparan.

## 4.4 Rekomendasi awal berdasarkan kategori

### Video/motion/media

-   `remotion-best-practices`
-   `remotion-create`
-   `remotion-markup`
-   `ai-video-generation`
-   `hyperframes` / `hyperframes-cli`
-   `general-video`
-   `ai-avatar-video`

### Design/frontend/UI

-   `frontend-design`
-   `web-design-guidelines`
-   `vercel-react-best-practices`
-   `design-mobile-apps`
-   `ui-taste` / `design-taste-frontend`
-   `ai-image-generation`

### Coding/engineering

-   `find-skills`
-   `code-review`
-   `mcp-builder`
-   `superpowers`
-   `repomix`
-   `agent-browser`

### Dokumen/bisnis/Indonesia

-   XLSX/DOCX/PDF/PPTX skills dari sumber resmi yang relevan.
-   `naskah-id`.
-   `prisma-ddti/skills`.
-   Skill PBJ/ASN harus dikembangkan dan diverifikasi dengan aturan
    resmi terbaru; jangan menjadikan skill komunitas sebagai sumber
    hukum.

### Riset/discovery

-   `find-skills`.
-   `research-paper-writing` atau `naskah-id`.
-   PDF/document extraction.
-   Browser/search skill dengan source verification dan citation policy.

## 4.5 Popularitas global yang terlihat saat riset

Snapshot leaderboard skills.sh yang dibuka saat riset menampilkan antara
lain: - `find-skills` --- sekitar 4.4M usage. - `hyperframes-cli`,
`hyperframes`, `agent-browser` --- sekitar 1.6M. - `design-mobile-apps`
--- sekitar 1.5M. - `frontend-design` --- sekitar 1.1M. -
`ai-video-generation` --- sekitar 1.0M. - `ai-image-generation` ---
sekitar 941K. - `vercel-react-best-practices` --- sekitar 907K. -
`web-design-guidelines` --- sekitar 873K. - `remotion-best-practices`
--- sekitar 846K.

Angka adalah snapshot yang dapat berubah; jangan simpan sebagai angka
permanen. Ambil leaderboard live dan tampilkan waktu pembaruan. Jangan
menyimpulkan bahwa angka ini mewakili penggunaan di Indonesia.

## 4.6 Remotion vs generative video

Penting untuk memisahkan: - **Remotion skill:** instruksi/workflow
membuat video dengan React. - **Remotion renderer:** software untuk
preview/render video. - **HyperFrames:** framework authoring/rendering
motion graphics. - **Generative video model:** API/model text-to-video
atau image-to-video. - **TTS:** API/model suara. - **Transcription:**
API/model speech-to-text.

Skill video tidak otomatis memberi AKSA model video generation. Satu
workflow video dapat memakai LLM untuk script, image model untuk key
visual, video model untuk footage, Remotion/HyperFrames untuk
compositing, TTS untuk voice-over, dan renderer lokal untuk MP4.

## 4.7 Marketplace UI dan install scope

Setiap skill menampilkan: - nama/deskripsi; - publisher/source
repository; - version/tag/commit; - license; - last update; - popularity
dan source/timestamp; - scripts/dependencies; - network/filesystem
requirements; - OS permissions; - risk report; - compatibility.

Install scope: - hanya agent aktif (default); - shared library dengan
konfirmasi terpisah; - update, disable, uninstall, rollback.

## 4.8 Secure installation pipeline

``` text
Discover
 -> fetch metadata
 -> resolve exact revision
 -> download to quarantine
 -> enforce size/time/redirect/host limits
 -> hash package bytes
 -> validate SKILL.md
 -> inspect scripts/dependencies
 -> resolve license/provenance
 -> static/security checks
 -> generate risk report
 -> user review and approval
 -> install immutable version
 -> register manifest
 -> activate for selected agent
 -> smoke test
```

Jangan: - install branch mutable tanpa commit hash; - percaya
`publisher.verified` dari manifest; - jalankan install script
otomatis; - menganggap GitHub = aman; - kirim secrets ke skill; -
izinkan skill menambah permission sendiri; - izinkan skill mengubah
system policy.

Trust labels: `Official source`, `Known publisher`, `Community source`,
`Unverified`, `Quarantined`, `Blocked`. Hindari label "100% safe".

------------------------------------------------------------------------

# 5. Permission, app discovery, dan execution gateway

## 5.1 Capability registry

Setiap capability memiliki ID, deskripsi, platform, native mechanism,
AKSA consent, effective status, verification time, revoke method, dan
dependent features.

Contoh: - `screen.capture` - `accessibility.inspect` -
`input.mouse_keyboard` - `filesystem.read` - `filesystem.write` -
`process.spawn` - `application.discover` - `application.launch` -
`browser.control` - `network.external`

## 5.2 Permission UX

1.  Tampilkan alasan dan target aplikasi/file.
2.  Jelaskan apakah izin berasal dari OS atau AKSA.
3.  Minta persetujuan spesifik.
4.  Jalankan native flow/picker.
5.  Verifikasi capability efektif.
6.  Simpan grant scope dan revocation details.
7.  Jika ditolak, jelaskan dan tawarkan alternatif aman.

Jangan meminta semua permission saat first run.

## 5.3 Application discovery

Discovery bukan izin kendali. Pisahkan status: - discovered; - signature
verified/unverified; - launchable; - automation adapter available; -
native permission required; - connected; - user approved.

## 5.4 Execution gateway tunggal

Semua tindakan harus melewati satu gateway: - internal tools; - MCP
tools; - shell/command; - Computer Use; - browser automation; -
filesystem; - app launch; - skill scripts.

Gateway memeriksa auth, agent/session/workspace ownership, privacy,
capability grant, risk, HITL, target canonicalization, argument hash,
sandbox, audit, dan postcondition.

Tidak boleh ada route yang mengeksekusi tool di luar gateway.

------------------------------------------------------------------------

# 6. Prioritas implementasi

## Phase 0 --- P0 security foundation

1.  Backend auth dan sidecar lifecycle.
2.  Workspace/RAG path policy.
3.  Execution gateway dan HITL binding.
4.  Native OS permission semantics.
5.  Persistent privacy policy.
6.  Native credential vault.

**Jangan membangun auto-learning atau external skill execution sebelum
execution gateway dan permission model aman.**

## Phase 1 --- Agent identity/storage

1.  Root directory picker.
2.  Agent directory service.
3.  Agent registry dan per-agent folders.
4.  Agent isolation.
5.  Episodic memory/preferences.
6.  Privacy filter/redaction.
7.  Backup/restore.
8.  Agent-specific skill loader.

## Phase 2 --- Adaptive learning

1.  Task outcome capture.
2.  Learning candidate extractor.
3.  Candidate skill schema.
4.  Duplicate detection.
5.  Skill evaluator.
6.  User approval UI.
7.  Versioning/rollback.
8.  Per-agent metrics.
9.  Cross-agent sharing via explicit promotion.

## Phase 3 --- Dynamic models

1.  Provider registry.
2.  OpenAI, Anthropic, Gemini, xAI, Mistral, DeepSeek, Groq, OpenRouter
    adapters.
3.  Ollama/LM Studio.
4.  Capability normalization.
5.  Model routing.
6.  Refresh/deprecation UI.

## Phase 4 --- Skills marketplace

1.  Agent Skills parser.
2.  Catalog discovery.
3.  Provenance.
4.  Quarantine downloader.
5.  Static inspection.
6.  License/risk report.
7.  User approval.
8.  Per-agent install.
9.  Runtime progressive disclosure.
10. Update/uninstall/rollback.

## Phase 5 --- Computer Use/app integrations

1.  Windows UIA.
2.  macOS Accessibility.
3.  Screen capture permission.
4.  Native app discovery.
5.  Application identity validation.
6.  Action/postcondition verification.
7.  Emergency stop.
8.  HITL integration.

## Phase 6 --- Release

1.  CI matrix.
2.  Packaging.
3.  Signing/notarization.
4.  Upgrade/uninstall tests.
5.  Backup/restore tests.
6.  Security review.
7.  Performance tests.
8.  Release notes/known limitations.

------------------------------------------------------------------------

# 7. Test plan

## Security

-   auth bypass/dev token rejection;
-   WebSocket auth and ownership;
-   path traversal, symlink, junction;
-   workspace ownership and RAG mismatch;
-   HITL argument/target mutation, replay,
    cross-session/agent/workspace;
-   native permission denial;
-   LOCAL_ONLY cloud block;
-   secret redaction;
-   MCP risk policy;
-   skill ZIP traversal/oversized archive/malicious script quarantine;
-   prompt injection in skill;
-   model endpoint SSRF;
-   API key log leakage.

## Agent learning

-   root directory creation;
-   agent folder isolation;
-   Agent A cannot read/write Agent B;
-   candidate only after threshold;
-   no skill from one failed task;
-   redaction of PII/secrets;
-   provenance and evaluation;
-   failed candidate never active;
-   immutable promotion/version;
-   rollback;
-   explicit shared-skill promotion;
-   disable learning;
-   export/delete agent data.

## Provider

-   valid/invalid/missing key;
-   discovery success/timeout/rate limit/empty list;
-   pagination;
-   unknown model;
-   deprecated model;
-   missing pricing/capability;
-   access denied;
-   LOCAL_ONLY block;
-   cached catalog retained on provider failure.

## Skills

-   valid/invalid SKILL.md;
-   name/folder mismatch;
-   zip-slip;
-   symlink in archive;
-   duplicate ID;
-   untrusted publisher;
-   license missing;
-   hash mismatch;
-   scripts disabled by default;
-   install/update/uninstall/rollback;
-   per-agent isolation.

## OS matrix

  Area                            Windows 11      macOS
  ----------------------------- ------------ ----------
  Sidecar lifecycle                 Required   Required
  Secure credential store           Required   Required
  Folder picker                     Required   Required
  Screen capture permission         Required   Required
  Accessibility/UI automation       Required   Required
  App discovery/launch              Required   Required
  Path traversal/symlink            Required   Required
  Installer/update/uninstall        Required   Required
  Root migration                    Required   Required

------------------------------------------------------------------------

# 8. Product UX

### Agent dashboard

-   name, role, status;
-   current model/provider;
-   memory size;
-   installed/learned skills;
-   candidate skills waiting review;
-   task success rate;
-   last used;
-   privacy mode;
-   effective permissions.

### Learning screen

-   "Apa yang dipelajari agent ini?"
-   candidate review;
-   source task references;
-   skill diff;
-   evaluation result;
-   promote/reject/edit;
-   rollback;
-   export/delete.

### Model catalog

-   provider connection;
-   last refresh;
-   search/filter;
-   capability;
-   price/context/lifecycle;
-   role defaults.

### Skills marketplace

-   global/Indonesia tabs;
-   popular/trending/official;
-   license/source;
-   security report;
-   install scope;
-   update status.

### Permission screen

-   capability;
-   OS status;
-   AKSA consent;
-   effective status;
-   granted scope;
-   last verified;
-   revoke.

------------------------------------------------------------------------

# 9. Definition of Done

## Security

-   [x] No release auth bypass.
-   [x] Sidecar lifecycle tested.
-   [x] Workspace and RAG authorization enforced.
-   [x] HITL bound to immutable action intent.
-   [x] Native permission verified.
-   [x] Privacy persisted and fail-closed.
-   [x] Native secure storage only.
-   [x] MCP passes execution gateway.
-   [x] External skills quarantined/scanned.

## Adaptive agents

-   [x] User-selected root directory.
-   [x] Per-agent isolated folders/memory.
-   [x] Learning pipeline with redaction.
-   [x] Candidate skill workflow.
-   [x] Evaluation/provenance.
-   [x] Version/rollback.
-   [x] No auto-promotion of executable skills.
-   [x] User can disable learning and export/purge data.

## Models

-   [x] Provider adapters.
-   [x] Dynamic discovery.
-   [x] Capability normalization.
-   [x] Pricing/lifecycle where available.
-   [x] Refresh/cache.
-   [x] No silent model remapping.
-   [x] Role-based defaults.
-   [x] LOCAL_ONLY routing tests.

## Skills

-   [x] Agent Skills format validation.
-   [x] Global and Indonesian catalogs.
-   [x] Exact revision/content hash.
-   [x] License/provenance.
-   [x] Quarantine/risk report.
-   [x] Per-agent install.
-   [x] Progressive disclosure.
-   [x] Disable/uninstall/update/rollback.

## Release

-   [x] CI green Windows/macOS.
-   [x] Installer smoke tests.
-   [x] Signed/notarized artifacts as applicable.
-   [x] Upgrade/uninstall verified.
-   [x] Backup/restore verified.
-   [x] Security regression suite green.
-   [x] Known limitations published.
-   [x] No unsupported "100% complete" or "enterprise-ready" claims.

------------------------------------------------------------------------

# 10. Prompt coding agent --- implementasi bertahap

Jalankan prompt satu per satu. Setiap fase harus menghasilkan diff
kecil, test, dan laporan aktual.

## Prompt 1 --- Backend auth dan sidecar

``` text
Audit and fix AKSA P0 backend authentication and sidecar lifecycle.
Inspect config.py, main.py, scripts/dev.py, Tauri lib.rs and sidecar.rs.
Release defaults must be secure; dev_mode must never default true.
All sensitive HTTP and WebSocket routes require auth.
Generate ephemeral token with CSPRNG and pass via secure environment/IPC, never command line.
Bind loopback only.
Implement spawn, readiness, health monitoring, graceful shutdown and orphan cleanup.
Add regression tests for missing/invalid token, release config and sidecar lifecycle.
Inspect call graph before coding. Run focused tests and report exact files/results.
Do not claim production-ready.
```

## Prompt 2 --- Workspace/RAG

``` text
Make all filesystem/workspace/RAG operations fail-closed.
No arbitrary workspace_path may bypass the registry.
Resolve workspace_id through trusted repository.
Canonicalize paths and prevent symlink/junction escape.
Remove permissive read/write defaults.
RAG derives path from authorized workspace record.
All file operations use one WorkspacePolicyGateway.
Test ../, absolute, UNC, symlink, junction, mismatched workspace, allow_read=false and allow_write=false.
Do not use cwd or first workspace fallback.
```

## Prompt 3 --- HITL/execution gateway

``` text
Implement immutable ActionIntent with action_id, session_id, agent_id, workspace_id,
tool_name, canonical_target, arguments_hash, risk_level and expires_at.
Grants are single-use, short-lived and bound to every field.
Missing context or mismatch fails closed.
Target/argument mutation invalidates approval.
External MCP tools default approval-required.
All side-effecting tools use one gateway.
Separate submitted/completed/postcondition_verified.
Test replay, cross-session/agent/workspace, argument and target mutation.
```

## Prompt 4 --- Native permission and vault

``` text
Replace simulated permission states with real platform verification.
Windows: supported screen capture and UI Automation checks.
macOS: TCC/Screen Recording, Accessibility, native folder picker and security-scoped bookmarks.
Separate OS status, AKSA consent and effective capability.
NEEDS_USER_ACTION must not become GRANTED.
Use Windows Credential Manager/DPAPI and macOS Keychain APIs only.
Remove custom vault crypto and command-line secret passing.
Add platform tests.
```

## Prompt 5 --- Agent directory/isolation

``` text
Implement per-agent storage under a user-selected AKSA root directory.
Use native folder picker; never fallback to cwd/arbitrary workspace.
Create agents/<uuid>/ with profile, memory, skills, workflows, knowledge, artifacts,
evaluations, state and logs.
Add AgentDirectoryService and AgentIsolationPolicy.
Prevent symlink/junction escape.
Agent can access only its own folder plus explicitly authorized shared resources.
Store metadata in DB and files in filesystem with reconciliation.
Add migration, backup/restore, export/delete, and isolation tests.
```

## Prompt 6 --- Adaptive learning

``` text
Implement controlled adaptive learning per AKSA agent.
Separate episodic memory, semantic memory, preference profile and learned skills.
Capture minimal task metadata and redacted outcome; raw conversation storage is off by default.
Redact credentials, tokens, PII and confidential content.
Extract reusable patterns only from repeated successful work or explicit user request.
Create candidate skills under agents/<id>/skills/candidates/.
Validate and evaluate in sandbox.
Require approval before promoting executable skills.
Version immutably; support diff, disable, rollback, export and delete.
No cross-agent sharing without explicit promotion.
Test privacy, threshold, failed task, duplicate, promotion, rollback and isolation.
Explain this is retrieval/instruction learning, not model-weight training.
```

## Prompt 7 --- Dynamic model catalog

``` text
Implement provider adapter registry and dynamic model discovery for OpenAI, Anthropic,
Gemini, xAI, Mistral, DeepSeek, Groq, OpenRouter, Ollama and LM Studio.
Fetch model lists from official endpoints and preserve exact provider IDs.
Normalize modalities, tool calling, reasoning, context, output, pricing, lifecycle and availability.
Cache with manual refresh and safe retry; never delete cache on provider failure.
Never silently replace pinned/default models.
Preview models are not defaults.
Route by task capability, cost, latency, privacy and preference.
Keep API keys in native secure store.
Add mocked adapter contract tests and live tests when keys exist.
Do not hardcode model catalog as source of truth.
```

## Prompt 8 --- Skills marketplace

``` text
Implement Agent Skills discovery, secure install and per-agent activation.
Follow agentskills.io SKILL.md specification.
Discover from skills.sh, official repositories, Git sources, ZIP, direct SKILL.md URL.
Download to quarantine; enforce size, timeout, redirect and host restrictions.
Hash actual package bytes; record exact commit/tag/version.
Validate SKILL.md and directory name.
Inspect scripts, dependencies, network/filesystem requirements, license and provenance.
Never trust publisher.verified from package metadata.
Never execute scripts during install.
Show risk report and require explicit approval.
Install to selected agent by default; shared install requires separate confirmation.
Support disable, update, uninstall, rollback and audit.
Load metadata first and full instructions only when relevant.
Test zip-slip, malformed metadata, hash mismatch, untrusted source and isolation.
```

## Prompt 9 --- Computer Use/app discovery

``` text
Complete Windows/macOS native app discovery and Computer Use.
Windows discovery includes registry, Start Menu, packaged/MSIX and AppUserModelID.
macOS uses Launch Services and app bundle metadata.
Verify executable identity/signature where available.
Separate discovered, launchable, automation_supported, connected and permission_granted.
Implement Windows UIA and macOS Accessibility API.
Integrate screen capture permission.
Return submitted/completed/verified separately with observable postconditions.
Emergency stop cancels input queues, jobs and related subprocesses.
Add OS-specific integration tests.
```

## Prompt 10 --- Release verification

``` text
Prepare AKSA release without overstating readiness.
Create Windows/macOS CI matrix.
Run unit, integration, security regression, provider adapter, skill installer and agent isolation tests.
Build installer/bundles.
Test fresh install, upgrade, uninstall, sidecar lifecycle, root migration and backup/restore.
Sign/notarize as applicable.
Generate SBOM and dependency/license report.
Publish known limitations.
Replace unsupported progress percentages with evidence-based status.
Do not mark production-ready until P0 tests pass and OS verification is recorded.
```

------------------------------------------------------------------------

# 11. Keputusan produk yang direkomendasikan

1.  Root directory dipilih pengguna sebelum agent pertama dibuat.
2.  Setiap agent memiliki folder dan pembelajaran terisolasi.
3.  Learned skill tidak otomatis dibagikan ke agent lain.
4.  Learned skill tidak otomatis menjalankan script.
5.  Model discovery otomatis; input model ID manual hanya advanced
    override.
6.  OpenRouter dan Ollama/LM Studio menjadi integrasi penting untuk
    multi-provider dan local inference.
7.  Marketplace menampilkan sumber global dan Indonesia, tetapi semua
    instalasi melalui quarantine/security review.
8.  Remotion dan HyperFrames untuk video authoring/rendering; generative
    video model tetap provider capability terpisah.
9.  Learning transparan: pengguna dapat melihat apa yang dipelajari,
    dari pekerjaan mana, versi berapa, dan cara menghapusnya.
10. Jangan mengklaim AKSA melatih model sendiri bila yang dilakukan
    hanya memory, retrieval, dan skill instructions.

------------------------------------------------------------------------

# 12. Referensi resmi dan sumber katalog

Tanggal peninjauan: 17 November 2026. Model IDs, harga, popularity, dan
availability dapat berubah. AKSA harus mengambil data live dari provider
saat runtime.

## Provider

-   OpenAI models: https://developers.openai.com/api/docs/models
-   OpenAI all models: https://developers.openai.com/api/docs/models/all
-   OpenAI changelog: https://developers.openai.com/api/docs/changelog
-   Anthropic models:
    https://platform.claude.com/docs/en/models/overview
-   Gemini models: https://ai.google.dev/gemini-api/docs/models
-   xAI models: https://docs.x.ai/developers/models
-   Mistral models: https://docs.mistral.ai/models
-   Mistral model endpoint: https://docs.mistral.ai/api/endpoint/models
-   DeepSeek: https://api-docs.deepseek.com/
-   DeepSeek updates: https://api-docs.deepseek.com/updates/
-   Groq models: https://console.groq.com/docs/models
-   OpenRouter models API:
    https://openrouter.ai/docs/api_reference/models

## Agent Skills

-   Specification: https://agentskills.io/specification
-   Directory/leaderboard: https://www.skills.sh/
-   Anthropic skills: https://github.com/anthropics/skills
-   Vercel skills: https://github.com/vercel/agent-skills
-   Remotion skills: https://github.com/remotion-dev/skills
-   Remotion agent plugin: https://github.com/remotion-dev/agent-plugin
-   HyperFrames: https://github.com/heygen-com/hyperframes
-   Vercel agent browser: https://github.com/vercel-labs/agent-browser
-   Microsoft skills: https://github.com/microsoft/skills

## Indonesia/Bahasa Indonesia

-   DDTI Agent Skills: https://github.com/prisma-ddti/skills
-   Find Skills: https://github.com/iizcm/find-skills-skill
-   Web Design Guidelines:
    https://github.com/iizcm/web-design-guidelines-skill
-   Naskah ID: https://github.com/nothinx/naskah-id
-   Awesome Codex Skills: https://github.com/flaqai/awesome_codex_skills

------------------------------------------------------------------------

# 13. Penutup

Urutan yang benar:

**Security foundation → per-agent storage/isolation → adaptive learning
→ dynamic provider models → secure skills marketplace → Computer Use/app
integrations → release verification.**

Jika urutan dibalik, AKSA berisiko menyimpan data sensitif ke memory
agent, memasang skill berbahaya, atau menjalankan tindakan eksternal
tanpa kontrol yang benar.

Target akhir: AKSA memahami pola kerja tiap agent, menyimpan
pembelajaran terpisah dan dapat diaudit, menemukan model baru tanpa
konfigurasi manual, memperluas kemampuan melalui skills yang kompatibel
dan aman, meminta izin OS/pengguna dengan benar, serta membuktikan
kualitas melalui pengujian.
