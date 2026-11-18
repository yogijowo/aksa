# AKSA — Audit Delta & Roadmap Perbaikan
**Tanggal audit:** 18 November 2026  
**Repository:** `yogijowo/aksa`  
**Branch:** `main`  
**Commit audit:** `4b8bccfc242400fddb368fd591a9a81d27ae88be`  
**Commit pembanding:** `e38252d81079a80550c51f166c93f360916fed6d`

> Dokumen tindak lanjut audit source code. Temuan merujuk pada snapshot commit di atas; verifikasi ulang HEAD sebelum implementasi.

## 1. Ringkasan eksekutif

AKSA menunjukkan kemajuan pada autentikasi engine, pengamanan endpoint tertentu, penyimpanan credential melalui OS keyring, sidecar spawn, pembatasan concurrency, dan workflow security regression. Namun, kontrol keamanan belum konsisten di seluruh jalur eksekusi agent.

**Status rekomendasi:** belum layak untuk distribusi publik luas sebelum seluruh P0 ditutup dan CI utama kembali hijau.

Temuan utama:
- **P0:** RAG workspace authorization belum membatasi path secara kuat.
- **P0:** HITL grant belum terikat penuh pada konteks aksi yang disetujui.
- **P0:** Sidecar readiness dan identity verification belum sepenuhnya fail-closed.
- **P0:** Native OS permission masih ada yang disimpulkan dari platform, bukan diverifikasi dari OS.
- **P1:** Credential vault fallback menggunakan metadata mesin yang dapat diprediksi.
- **P1:** Computer Use dapat melaporkan sukses tanpa memverifikasi hasil UI.
- **P1:** MCP lifecycle dan sandbox belum matang.
- **P1:** Privacy policy belum persisten.
- **P1:** API key input kembali terlihat sebagai teks biasa.
- **P1:** Skills marketplace belum memiliki supply-chain verification dan isolasi eksekusi yang cukup.
- **P1:** WebSocket session ownership perlu diikat ke principal.
- **P1:** CI utama gagal karena test harness.
- **P2:** Model recommendation dan release provenance perlu ditingkatkan.

## 2. Perbaikan positif yang sudah terkonfirmasi

| Area | Perubahan yang sudah masuk | Catatan |
|---|---|---|
| Engine startup | Production default dan token diwajibkan; development perlu konfigurasi eksplisit | Pertahankan fail-closed |
| API authentication | `secrets.compare_digest` | Pastikan semua endpoint privat memakai auth dependency |
| API docs | `/docs` dan OpenAPI dinonaktifkan di production | Periksa endpoint debug lain |
| Open path | Sandbox, extension allowlist, audit logging | Tambahkan test symlink/traversal/TOCTOU |
| Desktop sidecar | Tauri sudah memiliki mekanisme spawn dan token handoff | Readiness belum tuntas |
| Credential storage | OS keyring dan AES-GCM | Fallback key perlu diperbaiki |
| Telegram | Whitelist dipersistenkan ke database | Periksa revocation dan audit |
| Concurrency | Semaphore, session lock, daily budget | Uji konsistensi lintas proses/restart |
| Security CI | Workflow security regression tersedia dan sukses pada run yang diperiksa | Tidak menggantikan CI utama |
| Agent capabilities | Adaptive learning, per-agent folders, model discovery, katalog skills | Perlu uji isolasi dan lifecycle |

## 3. Temuan prioritas P0

### P0.1 — RAG indexing berpotensi melewati batas workspace

**Lokasi:** `services/engine/app/api/routes.py` endpoint `/rag/index-folder` (sekitar baris 718 pada snapshot audit); `services/engine/app/rag/store.py` fungsi `index_workspace_folder()` (sekitar baris 276).

**Temuan**
- Request menerima `workspace_id` dan `folder_path`.
- Path belum dipastikan merupakan turunan dari root workspace yang terdaftar dan diotorisasi.
- Indexing melakukan resolve dan pemindaian rekursif (`rglob("*")`) tanpa enforcement policy yang cukup.
- Symlink dapat berpotensi mengarahkan proses keluar workspace.
- Endpoint listing file workspace juga perlu memastikan `allow_read` ditegakkan.

**Risiko:** agent/pengguna yang hanya berhak pada satu workspace berpotensi meminta indexing file dari workspace atau lokasi lain.

**Perbaikan wajib**
1. Ambil root workspace dari registry/database berdasarkan `workspace_id` dan principal; jangan percaya root path dari client.
2. Validasi principal memiliki akses ke workspace.
3. Canonicalize path dan pastikan hasilnya tetap berada di bawah root workspace.
4. Tolak traversal, absolute path di luar root, symlink escape, junction/reparse point, dan file khusus.
5. Tegakkan `allow_read` pada list/read/index.
6. Lakukan pemeriksaan saat traversal dan sebelum membuka file untuk mengurangi TOCTOU.
7. Catat principal, workspace, relative path, keputusan, dan alasan penolakan tanpa merekam isi file.

**Acceptance criteria**
- Test `../`, absolute path, encoded traversal, symlink keluar root, nested symlink, junction/reparse point Windows, dan workspace milik principal lain.
- Tidak ada file di luar root workspace yang dapat dibaca atau diindeks.
- `allow_read=false` menolak list, read, dan indexing.
- Error tidak membocorkan keberadaan file privat.

### P0.2 — HITL grant belum terikat penuh pada aksi

**Lokasi:** `services/engine/app/core/sandbox.py`, `services/engine/app/api/routes.py`.

**Temuan**
- `CreateHITLRequest` belum membawa seluruh konteks, seperti `action_id`, `session_id`, `workspace_id`, dan arguments.
- Endpoint pembuatan grant belum meneruskan konteks aksi secara lengkap.
- `verify_and_consume_grant()` hanya membandingkan session/workspace bila kedua sisi memiliki nilai; konteks kosong dapat melewati pemeriksaan.
- `resource_path` tersimpan tetapi belum dibandingkan secara eksplisit saat verifikasi.

**Risiko:** approval untuk satu aksi dapat digunakan ulang atau dipasangkan dengan aksi/resource lain.

**Perbaikan wajib**
1. Ikat grant pada `principal_id`, `session_id`, `workspace_id`, `action_id`, `tool_name`, `tool_version`, `arguments_hash`, `resource_id` atau canonical `resource_path`, waktu pembuatan, expiry, dan status konsumsi.
2. Konteks wajib tidak boleh null/kosong; fail-closed jika tidak lengkap.
3. Hash arguments dari canonical JSON deterministik.
4. Verifikasi seluruh konteks terhadap aksi aktual.
5. Konsumsi grant atomik dan sekali pakai.
6. Expiry singkat dan invalidasi saat sesi berakhir, aksi berubah, atau principal dicabut.
7. Jangan mencatat secret mentah ke audit log.

**Acceptance criteria**
- Grant aksi A tidak dapat dipakai untuk aksi B.
- Mismatch arguments/tool/resource/session/workspace/principal selalu ditolak.
- Grant expired atau sudah dipakai ditolak.
- Dua request paralel tidak dapat mengonsumsi grant yang sama.
- Test konteks hilang/null seluruhnya fail-closed.

### P0.3 — Sidecar readiness dan engine identity belum fail-closed

**Lokasi:** `apps/desktop/src-tauri/src/lib.rs`, `apps/desktop/src-tauri/src/sidecar.rs`, `apps/desktop/src/services/engineConnection.ts`.

**Temuan**
- Spawn sidecar sudah ada, tetapi kegagalan spawn hanya dicatat dan desktop dapat melanjutkan startup.
- Belum ada readiness loop yang memastikan engine siap sebelum UI dianggap terhubung.
- `verifyEngineIdentity()` dapat menghasilkan `verified=false`, tetapi `apiFetch()` masih dapat melanjutkan request.
- Port allocator bind lalu melepas socket sebelum sidecar bind, sehingga ada port race.
- Nonce frontend menggunakan `Math.random`, bukan cryptographic randomness.

**Perbaikan wajib**
1. Lifecycle state eksplisit: `starting`, `ready`, `failed`, `stopping`.
2. Blokir request sensitif sebelum health check dan identity verification berhasil.
3. Spawn failure, token mismatch, nonce mismatch, atau identity mismatch harus menghentikan koneksi secara fail-closed.
4. Gunakan `crypto.getRandomValues()` di frontend dan CSPRNG Rust di backend.
5. Hilangkan pola bind-then-release; gunakan mekanisme port yang aman.
6. Tambahkan timeout, retry terbatas, graceful shutdown, cleanup child process, dan crash recovery.
7. Jangan pernah menulis token ke log.

**Acceptance criteria**
- UI tidak menyatakan engine ready sebelum health dan identity check berhasil.
- API request gagal tertutup ketika engine belum verified.
- Uji spawn failure, port conflict, timeout, token mismatch, crash, restart, dan shutdown.
- Tidak ada orphan sidecar.

### P0.4 — Native OS permission belum memverifikasi izin aktual

**Lokasi:** `services/engine/app/system/permission_broker.py`.

**Temuan**
- Beberapa capability Windows dapat berstatus `GRANTED` hanya berdasarkan platform: screen capture, accessibility, mouse/keyboard, app discovery/launch, dan process spawn.
- Di macOS, `NEEDS_USER_ACTION` berpotensi berubah menjadi grant AKSA tanpa verifikasi TCC aktual.

**Perbaikan wajib**
1. Standarkan status: `UNSUPPORTED`, `NOT_REQUESTED`, `NEEDS_USER_ACTION`, `PENDING`, `GRANTED`, `DENIED`, `REVOKED`, `ERROR`.
2. `GRANTED` hanya setelah API OS membuktikan capability tersedia.
3. macOS: verifikasi TCC untuk Accessibility, Screen Recording, Automation, dan permission relevan.
4. Windows: verifikasi capability melalui API yang sesuai.
5. Linux: deteksi Wayland/X11, portal, sandbox, dan keterbatasan runtime.
6. Re-check saat runtime karena permission dapat dicabut.
7. UI menjelaskan tujuan, cakupan, dan cara mencabut izin.

**Acceptance criteria**
- Tidak ada `GRANTED` hanya berdasarkan jenis OS.
- Operasi ditolak bila permission belum terverifikasi.
- Test mock granted/denied/revoked/error lintas platform.
- UI mengikuti perubahan status permission dari OS.

## 4. Temuan prioritas P1

### P1.1 — Credential vault fallback lemah

**Lokasi:** `services/engine/app/core/credential_vault.py`.

OS keyring dan AES-GCM sudah digunakan, tetapi fallback key diturunkan dari metadata mesin (hostname, username, home directory, platform) dengan salt statis. Metadata tersebut bukan secret kriptografis.

**Tindakan**
- Jangan menyimpan API key cloud menggunakan fallback berbasis metadata mesin.
- Jika OS keyring tidak tersedia, fail-closed atau gunakan mekanisme OS-backed yang setara dan teruji.
- Buat migrasi aman untuk secret yang terlanjur tersimpan dengan fallback lama.
- Pisahkan data non-sensitif dari credential.
- Pastikan secret tidak muncul di log, exception, telemetry, crash report, atau response UI.

**Acceptance:** tidak ada credential baru yang memakai key turunan metadata; test keyring unavailable/locked/permission denied/recovery lulus.

### P1.2 — Computer Use mengklaim sukses tanpa verifikasi postcondition

**Lokasi:** `services/engine/app/tools/computer_use/gui_agent.py`.

Windows melaporkan `ui_automation_tree=true` berdasarkan platform, sementara implementasi lebih banyak memakai foreground window Win32. macOS belum memiliki accessibility tree yang lengkap. `visual_screen_action()` dapat menyatakan `postcondition_verified: true` hanya karena input terkirim.

**Tindakan**
- Pisahkan `capability_available` dari `capability_implemented`.
- Implementasikan UI Automation Windows dan Accessibility API macOS secara nyata, atau laporkan keterbatasan.
- Setelah aksi, ambil state UI/screenshot baru dan verifikasi postcondition.
- Jika hanya input terkirim, gunakan status `submitted_unverified`, bukan `success`.
- Aksi destruktif wajib melalui HITL.
- Tambahkan timeout, cancellation, dan validasi target window.

**Acceptance:** status sukses hanya setelah postcondition terbukti; uji target tidak ditemukan, window berganti, dialog tak terduga, permission dicabut, dan aksi gagal.

### P1.3 — MCP lifecycle belum lengkap

**Lokasi:** `services/engine/app/tools/mcp/mcp_client.py`.

Client mengirim `initialize`, `notifications/initialized`, dan `tools/call` tanpa menunggu response initialize serta discovery `tools/list` secara benar. Process per invocation dan dependency `npx -y`/`uvx` juga perlu dikendalikan.

**Tindakan**
1. Implementasikan handshake sesuai versi protokol MCP yang didukung.
2. Tunggu response `initialize`, validasi protocol version/capabilities, baru kirim `notifications/initialized`.
3. Jalankan `tools/list` dan validasi schema sebelum tool tersedia.
4. Validasi input/output dan batas payload.
5. Kelola start/ready/timeout/cancel/restart/shutdown.
6. Pin versi dependency dan verifikasi integritas sumber.
7. Jalankan server dengan least privilege, sandbox, environment allowlist, dan network policy.
8. Tampilkan source, publisher, tools, dan permission sebelum aktivasi.

**Acceptance:** handshake invalid, tool tak terdaftar, schema invalid, timeout, dan process crash ditolak/ditangani; tidak ada dependency production tanpa versi terkunci.

### P1.4 — Privacy policy belum persisten

**Lokasi:** `services/engine/app/core/privacy_gate.py`.

Policy mencakup `CLOUD_BY_CHOICE` dan `INTERNAL`, tetapi konfigurasi masih in-memory.

**Tindakan**
- Simpan policy per user/profile secara persisten.
- Tetapkan default aman untuk data sensitif.
- Klasifikasikan data sebelum dikirim ke provider cloud.
- Jika policy tidak terbaca/storage error, blokir pengiriman data sensitif.
- Jangan fallback diam-diam ke cloud.
- Catat keputusan tanpa konten sensitif.

**Acceptance:** pilihan tetap ada setelah restart; storage error fail-closed; uji public/internal/personal/credential pada seluruh mode.

### P1.5 — API key terlihat sebagai teks biasa

**Lokasi:** `apps/desktop/src/components/settings/FeatureSectionsView.tsx` sekitar baris 625–700 pada snapshot audit.

Field API key menggunakan `type="text"`.

**Tindakan**
- Default `type="password"`.
- Tambahkan show/hide toggle eksplisit.
- Backend tidak mengembalikan secret penuh setelah disimpan.
- Tampilkan status configured dan masked suffix.
- Cegah secret masuk console, telemetry, error, atau clipboard otomatis.

**Acceptance:** tersembunyi secara default; secret tidak muncul di response settings; test UI show/hide/save/reload.

### P1.6 — Skills marketplace belum cukup aman

Katalog, curated install, dan ZIP scanner/quarantine sudah ada, tetapi belum terlihat pipeline penuh untuk upload/install ZIP atau URL arbitrer. Curated install membangun `SKILL.md` dari preview, bukan memasang paket lengkap terverifikasi. `publisher.verified=true` belum didukung bukti kuat. Hash dapat berasal dari `skill_id`, bukan artefak sebenarnya.

**Tindakan**
1. Definisikan format paket dan manifest berversi.
2. Hitung SHA-256 dari byte artefak sebenarnya.
3. Verifikasi signature/provenance publisher; jangan percaya boolean `verified`.
4. Cegah zip-slip, traversal, symlink escape, archive bomb, oversized file, dan executable tak diizinkan.
5. Install ke staging, validasi, lalu atomic promote.
6. Simpan versi, hash, publisher, source, permission, scan result, dan audit trail.
7. Jalankan skill di sandbox least-privilege.
8. Sediakan disable, uninstall, update, rollback.
9. Permission eksternal harus eksplisit dan dapat dicabut.

**Acceptance:** hash cocok dengan artefak; signature invalid ditolak; archive berbahaya teruji; skill tidak dapat mengakses filesystem/network di luar izin; rollback berfungsi.

### P1.7 — WebSocket session ownership

Ownership session masih perlu diikat ke principal terautentikasi dan sumber data persisten.

**Tindakan**
- Validasi session ownership saat connect, subscribe, send, resume, dan reconnect.
- Client tidak boleh menentukan principal atau mengklaim session sepihak.
- Terapkan expiry, revocation, session transfer, rate limit, dan batas ukuran message.
- Jangan hanya mengandalkan in-memory ownership.

**Acceptance:** principal A tidak dapat membaca/mengirim event session principal B; reconnect/resume tetap tervalidasi; restart engine tidak menghilangkan kontrol.

### P1.8 — CI utama gagal karena test harness

**Workflow yang diperiksa**
- Windows CI: https://github.com/yogijowo/aksa/actions/runs/44220856638
- Security Regression & Supply Chain Audit: https://github.com/yogijowo/aksa/actions/runs/44220857044

**Status saat audit**
- Security Regression & Supply Chain Audit: sukses.
- CI utama Windows dan macOS: gagal pada `77 passed, 1 failed`.
- Test gagal: `test_p0_engine_refuses_to_start_without_token_in_production`.

**Akar masalah yang ditemukan**
- `services/engine/tests/test_p0_sidecar_auth_lifecycle.py` sekitar baris 64 memakai `cwd="services/engine"` sementara workflow sudah berjalan dari working directory `services/engine`, sehingga path relatif menjadi ganda.
- Sekitar baris 67, environment subprocess dibuat dari `dict().items()` sehingga environment kosong dan menghilangkan `PATH`, `SystemRoot`, serta variabel penting lainnya.

**Tindakan**
- Gunakan path absolut dari lokasi test/repository root atau path relatif terhadap cwd secara konsisten.
- Gunakan `os.environ.copy()`, lalu hapus hanya variabel yang memang perlu untuk skenario test.
- Pastikan test membuktikan engine menolak startup production tanpa token, bukan gagal karena path/environment.
- Jalankan ulang Windows dan macOS.
- Pastikan langkah berikutnya kembali berjalan: sidecar dry-run, npm install/audit, frontend typecheck/build, dan Rust checks.

**Acceptance:** test lulus pada Windows/macOS; error assertion jelas; seluruh job CI selesai.

## 5. Temuan P2 — Kualitas dan release readiness

### P2.1 — Model recommendation perlu scoring multi-kriteria

Discovery dan provider adapter/cache tersedia, tetapi rekomendasi masih cenderung memilih model pertama yang memenuhi capability.

Tingkatkan ranking berdasarkan:
- Capability terverifikasi (text, vision, audio, tool calling, structured output).
- Context window.
- Biaya input/output.
- Latency dan availability/rate limit.
- Privacy policy dan lokasi pemrosesan bila diketahui.
- Reliability dan kebutuhan tugas.

Jangan menyimpulkan capability hanya dari nama model. Simpan sumber dan waktu verifikasi metadata. Tampilkan alasan rekomendasi dan alternatif.

### P2.2 — Release signing, SBOM, provenance

Commit yang diperiksa belum signed (`verified: false`) dan belum ada GitHub Release yang dipublikasikan pada saat audit. Workflow release berkembang, tetapi belum ada bukti smoke test installer lengkap.

Tindakan:
- Signed commit/tag sesuai proses proyek.
- SBOM dan provenance/attestation untuk artefak.
- Pin GitHub Actions dan dependency kritis.
- Installer smoke test Windows/macOS (dan Linux jika menjadi target).
- Checksum dan signature setiap artefak.
- Release notes mencantumkan known limitations.
- Jangan menyebut RC/stable sebelum seluruh platform matrix hijau.

## 6. Ketidaksesuaian dokumentasi dan CI

`PROGRESS.md` menyatakan Phase 11 selesai, RC-1, tidak ada known limitations, 78 test lulus pada macOS Python 3.14.2, serta frontend/Rust build berhasil.

Namun workflow yang diperiksa pada snapshot audit menggunakan Python 3.12 dan gagal pada Windows serta macOS dengan satu test gagal. Karena test step gagal, langkah setelahnya berpotensi tidak dijalankan.

**Tindakan dokumentasi**
- Ubah status menjadi “CI remediation in progress” sampai workflow utama hijau.
- Pisahkan hasil lokal dan hasil CI.
- Catat OS, Python, Node, Rust, commit SHA, workflow run, command, dan hasil.
- Daftarkan P0/P1 terbuka sebagai known limitations.
- Security workflow hijau bukan pengganti CI build utama.

## 7. Urutan implementasi yang direkomendasikan

| Urutan | Pekerjaan | Prioritas | Alasan |
|---:|---|---|---|
| 1 | Perbaiki test harness CI | P0 | Baseline test harus dapat dipercaya |
| 2 | Tutup RAG workspace boundary | P0 | Mencegah akses/indexing lintas workspace |
| 3 | Ikat HITL grant ke konteks aksi | P0 | Mencegah approval reuse/cross-action |
| 4 | Fail-closed sidecar readiness/identity | P0 | Hanya terhubung ke engine tepercaya |
| 5 | Verifikasi native OS permission | P0 | Mencegah akses perangkat tanpa izin |
| 6 | Hilangkan credential fallback lemah | P1 | Melindungi API key |
| 7 | Perbaiki API key masking | P1 | Mengurangi kebocoran visual |
| 8 | Verifikasi Computer Use postcondition | P1 | Mencegah klaim aksi palsu |
| 9 | Selesaikan MCP lifecycle/sandbox | P1 | Mengurangi risiko tool eksternal |
| 10 | Persist privacy policy | P1 | Pilihan privasi konsisten |
| 11 | Perkuat skills marketplace | P1 | Cegah skill tampered/berbahaya |
| 12 | Ikat WebSocket ke principal | P1 | Mencegah akses lintas session |
| 13 | Model scoring | P2 | Kualitas pemilihan model |
| 14 | Signing, SBOM, provenance, installer tests | P2 | Kepercayaan distribusi |

## 8. Prompt coding agent — jalankan satu per satu

Gunakan prompt secara berurutan. Minta coding agent membaca source aktual dan seluruh caller sebelum mengedit. Satu prompt sebaiknya menjadi satu PR/commit terpisah. Tambahkan regression test sebelum atau bersama implementasi. Jangan melemahkan security behavior demi membuat test lulus.

### Prompt 1 — Pulihkan CI test harness

```text
Audit dan perbaiki kegagalan test:
services/engine/tests/test_p0_sidecar_auth_lifecycle.py
test_p0_engine_refuses_to_start_without_token_in_production

Temuan:
- Workflow sudah berjalan dari working-directory services/engine.
- Test memakai cwd="services/engine", sehingga path dapat menjadi relatif ganda.
- Environment subprocess dibuat dari dict kosong sehingga PATH/SystemRoot hilang.

Tugas:
1. Periksa workflow YAML dan test aktual.
2. Perbaiki cwd/path agar konsisten di Windows dan macOS.
3. Bangun environment dari os.environ.copy(), lalu hapus hanya variabel yang memang perlu.
4. Pastikan test membuktikan engine menolak startup production tanpa token, bukan gagal karena path/executable.
5. Tambahkan assertion dan error message yang jelas.
6. Jalankan test terkait dan seluruh test engine relevan.
7. Jangan mengubah production security behavior untuk membuat test lulus.

Laporkan akar masalah, file berubah, command, hasil test, dan risiko tersisa.
```

### Prompt 2 — Amankan RAG workspace boundary

```text
Tutup temuan P0 pada RAG indexing dan workspace file access.

Periksa routes.py, rag/store.py, workspace registry, sandbox/path validator, dan authorization dependencies.

Persyaratan:
1. Resolve workspace_id dari registry/database; jangan percaya root path dari client.
2. Validasi principal memiliki akses ke workspace.
3. Canonicalize path dan pastikan tetap di bawah root workspace.
4. Tolak traversal, absolute path di luar root, symlink escape, junction/reparse point, dan file khusus.
5. Tegakkan allow_read pada list/read/index.
6. Cegah TOCTOU semaksimal mungkin.
7. Audit log mencatat principal, workspace, relative path, keputusan tanpa isi file.
8. Error tidak membocorkan keberadaan file privat.

Tambahkan test traversal, encoded traversal, absolute path, symlink, nested symlink, junction Windows, principal berbeda, allow_read=false, dan file tidak didukung.

Jangan menurunkan kontrol keamanan yang ada. Jalankan seluruh test relevan dan laporkan bukti file di luar workspace tidak dapat diakses.
```

### Prompt 3 — Ikat HITL grant ke aksi yang tepat

```text
Perkuat HITL agar grant hanya dapat digunakan untuk aksi persis yang disetujui.

Periksa sandbox.py, routes.py, seluruh caller HITL, model dan database.

Setiap grant harus terikat pada principal_id, session_id, workspace_id, action_id, tool_name, tool_version, canonical arguments_hash, resource_id/canonical resource_path, created_at, expires_at, dan status konsumsi.

Persyaratan:
1. Konteks wajib tidak boleh null/kosong; fail-closed.
2. Hash arguments dari canonical JSON deterministik.
3. Verifikasi semua konteks terhadap aksi aktual saat konsumsi.
4. Grant sekali pakai dan konsumsi atomik.
5. Tolak expired, revoked, consumed, atau mismatch principal/session/workspace/action/resource.
6. Hindari secret mentah dalam audit log.
7. Buat migrasi database yang kompatibel dan aman.

Tambahkan test mismatch, missing context, replay, expiry, revocation, dan dua konsumsi paralel. Jangan membuat fallback permissive untuk grant lama.
```

### Prompt 4 — Sidecar readiness dan identity fail-closed

```text
Selesaikan lifecycle sidecar Tauri dan verifikasi identitas engine.

Periksa lib.rs, sidecar.rs, engineConnection.ts, health/identity endpoint, dan token configuration.

Persyaratan:
1. Definisikan state starting/ready/failed/stopping.
2. apiFetch dan UI tidak boleh mengirim request privat sebelum health check dan identity verification sukses.
3. Spawn failure atau identity mismatch harus memblokir koneksi.
4. Ganti Math.random untuk nonce dengan crypto.getRandomValues; gunakan CSPRNG di Rust.
5. Hilangkan port allocation bind-then-release race.
6. Tambahkan timeout, retry terbatas, graceful shutdown, crash handling, dan child-process cleanup.
7. Jangan pernah log token.

Test spawn failure, port conflict, timeout, token mismatch, identity mismatch, crash, restart, dan shutdown. Pastikan tidak ada orphan process.
```

### Prompt 5 — Native OS permission broker

```text
Audit permission broker agar GRANTED hanya diberikan setelah izin OS benar-benar diverifikasi.

Periksa permission_broker.py dan semua pemanggil capability.

Gunakan status:
UNSUPPORTED, NOT_REQUESTED, NEEDS_USER_ACTION, PENDING, GRANTED, DENIED, REVOKED, ERROR.

Persyaratan:
1. Jangan menyimpulkan GRANTED hanya dari platform.
2. macOS: verifikasi TCC untuk Accessibility, Screen Recording, Automation.
3. Windows: verifikasi capability aktual melalui API sesuai.
4. Linux: deteksi Wayland/X11, portal, sandbox, keterbatasan runtime.
5. Re-check status saat runtime.
6. Operasi ditolak jika permission belum terverifikasi.
7. UI menjelaskan tujuan, cakupan, dan cara revoke.

Buat test mock lintas platform. Dokumentasikan bagian yang belum dapat diverifikasi otomatis. Jangan ubah NEEDS_USER_ACTION menjadi GRANTED hanya karena user melihat instruksi.
```

### Prompt 6 — Credential vault fail-closed

```text
Perbaiki credential vault agar tidak menggunakan key turunan hostname, username, home directory, platform, atau metadata mesin untuk melindungi API key.

Periksa credential_vault.py dan seluruh caller.

Persyaratan:
1. OS keyring menjadi jalur utama.
2. Jika keyring unavailable/locked/ditolak, jangan diam-diam menyimpan credential dengan fallback lemah.
3. Gunakan mekanisme OS-backed yang aman atau fail-closed.
4. Buat migrasi aman untuk credential yang tersimpan dengan fallback lama.
5. Secret tidak boleh muncul pada log, exception, telemetry, UI response, atau crash report.
6. Test unavailable, locked, permission denied, migration, rotation, dan recovery.

Laporkan skema lama/baru dan langkah migrasi.
```

### Prompt 7 — API key masking

```text
Perbaiki API key UI di FeatureSectionsView.tsx.

1. Default input type=password.
2. Tambahkan show/hide toggle eksplisit.
3. Backend tidak boleh mengembalikan secret penuh setelah tersimpan.
4. Tampilkan configured/masked state saja.
5. Cegah secret bocor ke console, telemetry, error, clipboard otomatis, atau debug state.
6. Tambahkan test default hidden, reveal, hide, save, dan reload.

Jangan membuat breaking API contract tanpa memperbarui seluruh caller.
```

### Prompt 8 — Computer Use postcondition verification

```text
Audit Computer Use agar status sukses hanya diberikan setelah hasil UI diverifikasi.

Periksa gui_agent.py dan seluruh OS adapter.

1. Pisahkan capability_available dan capability_implemented.
2. Jangan mengklaim UI Automation tree tersedia hanya karena OS Windows.
3. Implementasikan UI Automation Windows dan Accessibility API macOS, atau laporkan keterbatasan.
4. Setelah input, ambil state UI/screenshot baru dan verifikasi postcondition.
5. Jika input terkirim tetapi hasil belum terbukti, gunakan submitted_unverified, bukan success.
6. Aksi destruktif wajib melalui HITL.
7. Terapkan timeout, cancellation, dan target-window validation.

Test target tidak ditemukan, window berganti, dialog tak terduga, permission dicabut, aksi gagal, dan postcondition tidak tercapai.
```

### Prompt 9 — MCP lifecycle dan isolation

```text
Selesaikan MCP client lifecycle dan keamanan server eksternal.

Periksa mcp_client.py dan konfigurasi server MCP.

1. Implementasikan initialize handshake dan tunggu response.
2. Validasi protocol version/capabilities.
3. Kirim notifications/initialized setelah initialize sukses.
4. Jalankan tools/list dan validasi schema sebelum tool tersedia.
5. Validasi input/output, payload size, timeout, cancellation, error.
6. Kelola start/ready/shutdown dan cleanup process.
7. Pin versi package/dependency; hindari npx -y/uvx tanpa versi/integrity di production.
8. Terapkan least privilege, environment allowlist, filesystem/network sandbox.
9. Tampilkan publisher/source, tools, permission sebelum aktivasi.

Test handshake invalid, schema invalid, tool tidak terdaftar, timeout, crash, dan cleanup.
```

### Prompt 10 — Persist privacy policy

```text
Jadikan privacy policy persisten dan fail-closed.

Periksa privacy_gate.py, storage/config layer, dan seluruh jalur provider/cloud.

1. Simpan policy per user/profile.
2. Tentukan default aman untuk data sensitif.
3. Klasifikasikan data sebelum dikirim ke provider.
4. Jika policy tidak terbaca atau storage error, blokir cloud transmission data sensitif.
5. Jangan fallback diam-diam ke cloud.
6. Audit keputusan tanpa merekam konten sensitif.
7. UI menjelaskan policy aktif dan dampaknya.

Test restart persistence, storage failure, public/internal/personal/credential data, dan semua mode privacy.
```

### Prompt 11 — Skills marketplace supply-chain security

```text
Perkuat skills marketplace agar skill eksternal tidak dipercaya hanya dari metadata publisher.

1. Definisikan package format dan manifest versioned.
2. Hitung SHA-256 dari artefak sebenarnya.
3. Verifikasi signature/provenance publisher; jangan percaya publisher.verified tanpa bukti.
4. Cegah zip-slip, traversal, symlink escape, archive bomb, oversized file, executable tak diizinkan.
5. Install ke staging, validasi, lalu atomic promote.
6. Simpan source, publisher, version, hash, permission, scan result, audit trail.
7. Jalankan skill dalam sandbox least-privilege.
8. Sediakan disable, uninstall, update, rollback.
9. Permission skill eksplisit dan dapat dicabut.

Test malicious archive, hash mismatch, signature invalid, permission escalation, filesystem escape, network denied, dan rollback.
```

### Prompt 12 — WebSocket session ownership

```text
Audit WebSocket authorization dan session ownership.

1. Setiap koneksi memiliki principal hasil autentikasi.
2. Validasi ownership saat connect, subscribe, send, resume, reconnect.
3. Client tidak boleh menentukan principal atau mengklaim session sepihak.
4. Terapkan expiry, revocation, dan session transfer secara eksplisit.
5. Jangan bergantung hanya pada in-memory ownership.
6. Terapkan rate limit dan batas ukuran message.
7. Error tidak membocorkan session milik principal lain.

Test cross-principal, reconnect, resume, expired session, revoked user, dan engine restart.
```

### Prompt 13 — Model recommendation scoring

```text
Tingkatkan model discovery/recommendation menjadi ranking multi-kriteria, bukan memilih model pertama yang memenuhi capability.

Gunakan metadata provider terverifikasi, bukan inferensi dari nama model.

Pertimbangkan capability, context window, biaya input/output, latency, availability/rate limit, privacy policy, reliability, dan task requirements.

Tampilkan alasan rekomendasi, trade-off, alternatif, sumber dan timestamp metadata. Tambahkan fallback saat provider unavailable.

Test ranking, capability mismatch, cost limit, privacy restriction, dan provider outage.
```

### Prompt 14 — Release signing, SBOM, provenance

```text
Perkuat release pipeline AKSA.

1. Signed commit/tag sesuai proses proyek.
2. Generate SBOM setiap artefak.
3. Generate provenance/attestation yang mengikat artefak ke commit dan workflow.
4. Pin GitHub Actions dan dependency kritis.
5. Installer smoke test Windows/macOS (Linux jika target).
6. Uji install, launch, sidecar startup, update, uninstall, cleanup.
7. Publikasikan checksum dan signature.
8. Release notes menyebut known limitations.
9. Jangan publish stable/RC jika CI utama belum hijau atau P0 masih terbuka.

Laporkan artefak dan bukti workflow serta langkah verifikasi checksum/signature.
```

## 9. Definition of Done sebelum rilis

### Security
- [ ] Seluruh P0 ditutup dengan regression test.
- [ ] Tidak ada akses lintas workspace pada RAG/filesystem.
- [ ] HITL grant terikat ke aksi dan sekali pakai.
- [ ] Sidecar identity/readiness fail-closed.
- [ ] Native OS permission terverifikasi.
- [ ] Credential vault tidak memakai fallback key yang dapat diprediksi.
- [ ] WebSocket ownership tervalidasi.
- [ ] Skill/MCP berjalan dengan least privilege dan sandbox.

### Reliability
- [ ] CI Windows dan macOS hijau.
- [ ] Engine, frontend, Rust, dan packaging diuji pipeline.
- [ ] Sidecar crash/restart/shutdown teruji.
- [ ] Timeout/cancellation tersedia untuk provider, MCP, dan Computer Use.
- [ ] Tidak ada orphan process.

### Privacy
- [ ] Privacy policy persisten.
- [ ] Cloud transmission mengikuti policy dan fail-closed.
- [ ] Secret tidak bocor ke UI response/log/telemetry.
- [ ] Permission dan data access dapat dilihat serta dicabut.

### Release
- [ ] SBOM dan provenance tersedia.
- [ ] Checksum/signature tersedia.
- [ ] Installer smoke test lulus pada seluruh OS target.
- [ ] Release notes mencantumkan known limitations.
- [ ] Klaim RC/stable sesuai bukti CI dan pengujian.

## 10. Catatan untuk coding agent

1. Audit source aktual dan seluruh caller sebelum mengedit.
2. Satu prioritas per PR/commit.
3. Tambahkan regression test yang gagal pada perilaku lama.
4. Jangan melemahkan security untuk meluluskan test.
5. Sertakan migrasi dan rollback untuk credential, grant, policy, dan skill package.
6. Fail-closed bila principal, permission, identity, atau policy tidak dapat diverifikasi.
7. Bedakan status `requested`, `submitted`, `completed`, dan `verified`.
8. Update dokumentasi setelah CI hijau; catat commit SHA, environment, command, dan hasil.

## 11. Kesimpulan

AKSA sudah bergerak dari prototipe menuju desktop agent yang lebih serius. Autentikasi engine, keyring, sidecar, concurrency controls, dan security regression merupakan fondasi positif. Namun keamanan agent harus konsisten sampai ke RAG, HITL, WebSocket, MCP, Computer Use, dan skills eksternal.

Urutan paling tepat: **pulihkan CI → tutup RAG boundary → ikat HITL → fail-closed sidecar → verifikasi OS permission**. Setelah P0 selesai, lanjutkan credential vault, Computer Use, MCP, privacy persistence, marketplace isolation, dan release provenance.

Sampai P0 ditutup dan CI utama hijau, rekomendasinya adalah **development/beta internal, belum untuk distribusi publik secara luas**.
