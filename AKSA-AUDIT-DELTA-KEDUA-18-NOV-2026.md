# AKSA — Audit Delta Kedua & Roadmap Perbaikan

**Tanggal audit:** 18 November 2026  
**Repository:** https://github.com/yogijowo/aksa  
**Commit yang diaudit:** `e5ae5472896e5911e1c2d5c05b9e1c1c4128b726`  
**Commit pembanding:** `4b8bccfc242400fddb368fd591a9a81d27ae88be`

> Audit delta berdasarkan pemeriksaan source code dan status GitHub Actions pada commit di atas. Temuan harus diverifikasi kembali setelah commit baru. Dokumen ini bukan sertifikasi keamanan atau penetration test menyeluruh.

## 1. Ringkasan eksekutif

Perbaikan terbaru menunjukkan kemajuan nyata: otorisasi indexing RAG diperkuat, konteks HITL grant diperluas, OS keyring diprioritaskan, privacy policy dipersistenkan, hasil Computer Use tidak langsung dianggap sukses, paket skill dipindai dan di-hash, kepemilikan WebSocket dipersistenkan, scoring rekomendasi model ditingkatkan, serta tooling SBOM/checksum/provenance ditambahkan.

Namun **AKSA belum layak dipublikasikan untuk pengguna umum**. P0 yang masih perlu ditutup:

1. Token sidecar dikirim sebelum identitas server diverifikasi.
2. `/rag/search` belum memeriksa otorisasi workspace.
3. Principal belum berasal dari trusted authentication context.
4. Validasi HITL masih dapat dilewati jika `action_id` aktual tidak disertakan.
5. Permission OS masih dapat menghasilkan status `GRANTED` tanpa membuktikan kapabilitas sebenarnya.
6. CI gagal sebelum test berjalan karena pin `actions/setup-node` tidak dapat di-resolve.

**Status yang disarankan:** private beta/internal testing dengan data non-rahasia sampai P0 selesai dan CI hijau.

## 2. Perbaikan positif yang terkonfirmasi

| Area | Perubahan | Catatan |
|---|---|---|
| Test harness | Working directory dan environment test sidecar diperbaiki | Source membaik; belum terbukti di CI |
| RAG indexing | Owner, `allow_read`, canonical path, symlink, traversal diperiksa | Meningkat |
| HITL grant | Action ID, hash argumen, session/workspace/principal/resource, one-time use | Meningkat, masih ada celah |
| macOS permissions | Pemeriksaan TCC ditingkatkan | Meningkat |
| Credential vault | OS keyring diprioritaskan; fallback AES-GCM/random key | Fallback masih perlu diperkuat |
| API key UI | Input dimasking secara default | Meningkat |
| Privacy policy | Persisten di SQLite | Meningkat |
| Computer Use | Ada status submitted/unverified; input terkirim tidak otomatis dianggap sukses | Meningkat |
| Skills | ZIP scanning, staging, SHA-256 artefak aktual | Belum membuktikan publisher |
| WebSocket | Ownership session persisten | Masih perlu fail-closed |
| Model recommendation | Multi-criteria scoring | Metadata masih perlu transparansi |
| Release tooling | SBOM, checksum, provenance | Cargo dan code signing belum lengkap |

## 3. Temuan P0 — wajib diperbaiki sebelum distribusi

### P0-01 — Kebocoran token sidecar melalui identity check dan port race

**File:** `apps/desktop/src-tauri/src/sidecar.rs`, `apps/desktop/src/services/engineConnection.ts`

Temuan:
- `allocate_loopback_port()` melakukan bind sementara lalu melepas socket sebelum sidecar bind. Proses lain dapat mengambil port tersebut.
- Sidecar ditandai ready segera setelah spawn, bukan setelah health check selesai.
- `verifyEngineIdentity()` mengirim `X-AKSA-Auth-Token` sebelum identitas server diverifikasi.
- Proses lokal palsu yang mengambil port berpotensi menerima token.

**Perbaikan:**
1. Gunakan challenge-response berbasis nonce acak dan HMAC.
2. Identity/health challenge tidak boleh mengirim token autentikasi.
3. Verifikasi HMAC server terlebih dahulu; baru kirim token API.
4. Hilangkan pola bind-port-lalu-release atau gunakan mekanisme socket/port ownership yang aman.
5. Status ready hanya setelah health, identity, dan auth terverifikasi.
6. Build production harus fail-closed jika token dari Tauri tidak tersedia.
7. Hilangkan fallback secret development dari jalur production.

**Acceptance test:** server palsu tidak pernah menerima token; nonce/HMAC salah ditolak; port conflict gagal dengan aman; tidak ada token pada request sebelum identity verified.

### P0-02 — `/rag/search` belum memeriksa otorisasi workspace

**File:** `services/engine/app/api/routes.py`

Endpoint `/rag/search` memanggil `rag_store.hybrid_search()` berdasarkan `workspace_id` tanpa pemeriksaan principal, owner, atau `allow_read`. ID workspace yang diketahui/tertebak dapat digunakan untuk mencoba membaca data milik principal lain. Perilaku `workspace_id` kosong juga harus ditetapkan eksplisit.

Audit juga perlu mencakup:
- `GET /workspaces` — daftar harus dibatasi sesuai hak akses.
- `DELETE /workspaces/{id}` — penghapusan wajib memeriksa owner/permission.
- `/orchestrate/execute` — workspace harus diotorisasi sebelum konteks diberikan kepada agent.
- Semua endpoint baca/tulis/hapus/index/search/execute dan background job.

**Perbaikan:** buat dependency `authorize_workspace` terpusat; validasi permission sesuai operasi; jangan anggap ID sebagai bukti otorisasi; tolak workspace kosong kecuali ada izin global eksplisit; teruskan principal terverifikasi ke background job.

**Acceptance test:** Principal A tidak dapat membaca, mencari, mengindeks, mengubah, menghapus, atau mengeksekusi workspace Principal B.

### P0-03 — Principal ID belum terikat pada identitas terautentikasi

**File:** `services/engine/app/main.py`, `routes.py`, `ws.py`

Principal kadang berasal dari header `X-Principal-ID` atau body `owner_id` yang dikendalikan pemanggil. `ws.py` menggunakan `default_user`. Shared sidecar token tidak otomatis membuktikan identitas pengguna akhir.

**Perbaikan:**
1. Tetapkan model keamanan single-user lokal atau multi-principal.
2. Untuk single-user, principal berasal dari trusted runtime identity desktop host.
3. Untuk multi-user, principal dibuat middleware autentikasi yang tervalidasi.
4. Jangan menerima principal dari header/body tanpa verifikasi.
5. Hapus `default_user` dan gunakan principal konsisten pada REST, WebSocket, job, HITL, workspace, dan audit log.

**Acceptance test:** spoofing principal melalui header/body ditolak; semua jalur memakai trusted auth context.

### P0-04 — HITL masih dapat dilewati jika action ID tidak dikirim

**File:** `services/engine/app/core/sandbox.py` dan alur create/resolve HITL.

Pola pemeriksaan saat ini melewati perbandingan bila `action_id` aktual kosong:

```python
if grant.action_id and action_id:
    if grant.action_id != action_id:
        return False
```

`create_hitl_request()` menerima `principal_id`, tetapi principal pembuat belum disimpan konsisten. `resolve_hitl_request()` belum memastikan approver berhak menyelesaikan request. Listing approval juga perlu difilter.

**Perbaikan:**
1. Jika grant mengikat `action_id`, nilai aktual wajib ada dan harus sama.
2. Simpan `creator_principal_id`, workspace, session, resource, action, dan hash argumen.
3. Validasi hak approver sebelum resolve.
4. Filter daftar approval sesuai principal/permission.
5. Konsumsi grant secara atomik dan one-time.
6. Validasi ulang konteks tepat sebelum eksekusi.

**Acceptance test:** missing action ID, principal mismatch, perubahan argumen/resource, replay, dan concurrent use semuanya ditolak.

### P0-05 — Permission OS masih berpotensi memberi status GRANTED palsu

**File:** `services/engine/app/system/permission_broker.py`

Contoh pemeriksaan yang tidak cukup:
- Windows `GetDC(0)` tidak membuktikan seluruh screen capture diizinkan.
- `GetDesktopWindow()`/`GetSystemMetrics()` tidak membuktikan input automation/UI Automation.
- `pythoncom.CoInitialize()` hanya membuktikan COM dapat diinisialisasi.
- Keberadaan `osascript` bukan bukti AppleEvents/TCC permission.
- `DISPLAY` bukan bukti izin capture/input Linux.

**Perbaikan:**
1. Pisahkan `GRANTED`, `DENIED`, `NEEDS_USER_ACTION`, `UNSUPPORTED`, `UNKNOWN`.
2. `GRANTED` hanya setelah uji kapabilitas aktual dan spesifik.
3. Jika tidak bisa diverifikasi, jangan klaim `GRANTED`.
4. Pisahkan screen capture, accessibility/UI automation, input control, microphone, camera, filesystem.
5. Beri instruksi melalui Settings/dialog resmi OS.
6. Jangan memakai uji destruktif.

**Acceptance test:** kondisi permission belum diberikan, ditolak, dicabut, dan diberikan terdeteksi secara benar.

## 4. Temuan P1 — wajib sebelum beta publik

### P1-01 — Fallback credential vault masih lemah

**File:** `services/engine/app/core/credential_vault.py`

OS keyring sudah diprioritaskan. Namun fallback menyimpan `.vault_key_v2` berdekatan dengan `credentials.aesgcm.vault`. Mode `0o600` hanya diterapkan eksplisit non-Windows; ACL Windows perlu diperiksa. Key dan ciphertext yang tersimpan bersama bukan pengganti secure storage OS.

**Perbaikan:** gunakan Keychain (macOS), DPAPI/Credential Manager (Windows), Secret Service (Linux); hindari key plaintext bersebelahan dengan ciphertext; fail-closed atau minta opt-in eksplisit jika secure backend tidak tersedia; perkuat ACL; uji migrasi dan pemulihan.

### P1-02 — Lifecycle MCP belum mengikuti handshake secara ketat

**File:** `services/engine/app/tools/mcp/mcp_client.py`

Alur perlu memastikan `initialize` mendapat respons valid sebelum `notifications/initialized`, `tools/list`, atau `tools/call`. `handshake_ok` harus menjadi syarat wajib; schema argumen harus divalidasi sebelum invocation.

**Perbaikan:** urutan initialize → tunggu/validasi respons → initialized notification → tools/list → schema validation → tools/call. Tambahkan timeout, batas ukuran pesan, cleanup proses, dan sandbox filesystem/process/network.

### P1-03 — Skills marketplace belum membuktikan publisher dan sandbox runtime

**File:** `services/engine/app/skills/skill_manager.py`

ZIP scanning, staging, dan SHA-256 sudah ditambahkan, tetapi `expected_hash` opsional; hash tidak membuktikan identitas publisher; `publisher.verified` dapat berasal dari metadata; curated installer dapat memakai `instructions_preview`; sandbox runtime belum terbukti.

**Perbaikan:** tanda tangan digital paket; verifikasi signature terhadap trust store; manifest/hash tepercaya; tampilkan publisher/source/permission/hash; pisahkan install dan execute; sandbox least-privilege untuk filesystem/process/network; tolak path traversal, symlink berbahaya, archive bomb, dan manifest invalid.

### P1-04 — WebSocket belum fail-closed untuk session tidak ditemukan

**File:** `services/engine/app/api/ws.py`

`subscribe_session()` perlu menolak session yang tidak ditemukan. Database error/timeout harus menolak akses. Hapus `default_user`, validasi ulang ownership saat reconnect dan pergantian session, serta terapkan batas pesan/rate limit.

### P1-05 — Privacy gate belum cukup ketat untuk data CONFIDENTIAL

**File:** `services/engine/app/core/privacy_gate.py`

Policy sudah persisten, tetapi data `CONFIDENTIAL` tampak dapat dikirim tanpa consent per request pada mode tertentu. Klasifikasi berbasis keyword tidak cukup sebagai kontrol tunggal.

**Perbaikan:** data confidential wajib consent eksplisit per request atau diblokir dari cloud; consent terikat provider/model/tujuan/scope; mode global bukan consent otomatis; tampilkan preview dan redaksi secret/PII; audit keputusan tanpa menyimpan konten sensitif yang tidak perlu.

### P1-06 — Security workflow belum menjalankan regression test terbaru

**File:** `.github/workflows/security.yml`

Workflow masih menjalankan test fase lama:
- `test_phase6_security_and_sanitization.py`
- `test_phase7_os_integration_and_skills.py`
- `test_phase8_enterprise_readiness.py`

Masukkan test P0/P1/P2 baru ke workflow, pastikan exit code non-zero saat gagal, dan upload log/artifact tanpa secret.

## 5. CI blocker

Workflow:
- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/release.yml`

Ketiganya menggunakan pin `actions/setup-node`:

```text
60edb5dd545a775178f52524783379cf857dbb06
```

GitHub Actions melaporkan:

```text
Unable to resolve action actions/setup-node@60edb5dd545a775178f52524783379cf857dbb06
unable to find version ...
```

Workflow berhenti sebelum test/build berjalan. Karena itu, perbaikan test harness belum memiliki bukti CI lulus.

**Tindakan:**
1. Verifikasi full commit SHA `actions/setup-node` dari repository resmi.
2. Periksa semua action pin pada ketiga workflow.
3. Pertahankan immutable SHA pinning.
4. Jalankan ulang CI, security, dan release workflow.
5. Jangan menyatakan test lulus sebelum run benar-benar selesai.

Run yang diperiksa:
- CI: https://github.com/yogijowo/aksa/actions/runs/44229243950
- Security: https://github.com/yogijowo/aksa/actions/runs/44229244034

## 6. Temuan P2 — kualitas dan kesiapan rilis

### P2-01 — Metadata model sebagian masih berbasis inferensi

Sebagian adapter menyimpulkan capability dari nama model (`vision`, `coder`, `reasoner`, `pro`) atau memakai default hardcoded. Label `verified_provider_metadata` harus benar-benar berasal dari verifikasi provider. `cap_score` juga dapat melampaui 100 meski ditampilkan `/100`.

**Perbaikan:** bedakan `provider_verified`, `inferred`, `user_override`, `unknown`; simpan sumber/timestamp; normalisasi skor; masukkan freshness, latency, availability, cost, health check; sediakan refresh dan invalidasi metadata usang.

### P2-02 — SBOM belum mencakup dependency Rust/Cargo

SBOM saat ini mencakup Python dan npm, tetapi perlu memasukkan dependency dari `Cargo.lock`. Gunakan SPDX atau CycloneDX dan pastikan SBOM merepresentasikan artefak rilis aktual.

### P2-03 — Signing dan validasi installer belum lengkap

Commit terbaru unsigned (`verified: false`) dan belum ada GitHub Release saat audit. Provenance attestation bukan code signing.

**Perbaikan:** code signing per platform; verifikasi checksum/signature; verifikasi provenance terpisah; smoke test install, launch, upgrade, uninstall; uji sidecar, permission prompt, update flow; publikasikan release notes, SBOM, checksum, signature.

## 7. Urutan pengerjaan

| Urutan | Prioritas | Pekerjaan |
|---:|---|---|
| 1 | P0 | Perbaiki pin action CI dan jalankan workflow |
| 2 | P0 | Amankan sidecar identity handshake dan token |
| 3 | P0 | Otorisasi workspace seluruh endpoint |
| 4 | P0 | Trusted principal untuk REST/WebSocket |
| 5 | P0 | HITL fail-closed dan ownership approval |
| 6 | P0 | Koreksi status permission OS |
| 7 | P1 | Perkuat credential vault |
| 8 | P1 | Selesaikan MCP handshake/schema |
| 9 | P1 | Publisher verification dan sandbox skills |
| 10 | P1 | WebSocket fail-closed |
| 11 | P1 | Privacy gate confidential |
| 12 | P1 | Regression tests pada security workflow |
| 13 | P2 | Transparansi metadata model |
| 14 | P2 | SBOM Cargo, signing, installer smoke test |

---

# 8. Prompt coding agent — jalankan berurutan

Jalankan satu prompt per tahap. Minta agent memeriksa source aktual, membuat perubahan minimal, menambahkan regression test, menjalankan test terkait, dan melaporkan file yang berubah. Jangan menganggap selesai hanya karena kode berhasil dikompilasi.

## Prompt 1 — Perbaiki CI

```text
Audit dan perbaiki .github/workflows/ci.yml, security.yml, dan release.yml.
Pin actions/setup-node SHA 60edb5dd545a775178f52524783379cf857dbb06 gagal di-resolve.
Verifikasi full commit SHA action dari repository resmi; jangan menebak SHA.
Periksa seluruh action pin, konsistensi versi Node/Python/Rust, dan masukkan seluruh regression test P0/P1/P2 ke security workflow.
Pastikan test failure menghasilkan exit code non-zero. Jalankan test lokal yang tersedia.
Laporkan file berubah, test yang benar-benar dijalankan, dan hal yang belum dapat diverifikasi.
Jangan mengubah fitur aplikasi di luar kebutuhan CI.
```

## Prompt 2 — Sidecar identity dan token

```text
Hardening apps/desktop/src-tauri/src/sidecar.rs dan apps/desktop/src/services/engineConnection.ts.
Hilangkan port race dari pola bind lalu release. Sidecar tidak boleh ready hanya karena process spawn.
Rancang nonce + HMAC challenge-response: jangan kirim X-AKSA-Auth-Token sebelum identitas server terbukti.
Verifikasi identity lebih dahulu, baru kirim token API. Production harus fail-closed jika token dari Tauri tidak tersedia; hapus fallback secret development dari jalur production.
Tambahkan test rogue server, HMAC/nonce invalid, port conflict, dan bukti token tidak dikirim sebelum identity verified.
Jangan melemahkan validasi keamanan.
```

## Prompt 3 — Workspace authorization

```text
Audit semua endpoint workspace/RAG/execute, termasuk GET /workspaces, DELETE /workspaces/{id}, /rag/index-folder, /rag/search, dan /orchestrate/execute.
Buat authorize_workspace terpusat. Validasi principal dari trusted auth context dan permission read/write/delete/index/search/execute sesuai operasi.
Jangan anggap workspace_id dari request sebagai bukti izin. Tolak workspace kosong kecuali ada izin global eksplisit. Pastikan background job membawa principal dan authorization context.
Tambahkan regression test lintas principal untuk seluruh operasi. Jangan hanya memperbaiki /rag/search.
```

## Prompt 4 — Trusted principal

```text
Audit sumber principal_id di main.py, routes.py, ws.py, jobs, HITL, workspace, session, dan audit log.
Principal tidak boleh dipercaya dari X-Principal-ID atau owner_id request tanpa verifikasi. Hapus default_user.
Tentukan model single-user lokal atau multi-principal. Implementasikan trusted auth context dari desktop host/middleware dan gunakan konsisten di semua jalur.
Tambahkan test spoofing header/body principal dan pastikan semua kegagalan auth ditolak.
Jangan menganggap UUID/header acak sebagai autentikasi.
```

## Prompt 5 — HITL fail-closed

```text
Audit sandbox.py dan seluruh create/resolve/list HITL.
Jika grant memiliki action_id, action_id aktual wajib ada dan harus sama persis. Simpan creator_principal_id serta workspace/session/resource/action/hash argumen.
Validasi hak approver; filter listing approval; konsumsi grant atomik dan one-time; validasi ulang konteks tepat sebelum eksekusi.
Tambahkan test missing action_id, principal mismatch, argument tampering, replay, dan concurrent use.
Semua kondisi ambigu harus ditolak.
```

## Prompt 6 — OS permission broker

```text
Audit services/engine/app/system/permission_broker.py.
Pisahkan GRANTED, DENIED, NEEDS_USER_ACTION, UNSUPPORTED, UNKNOWN. GRANTED hanya setelah kapabilitas aktual terbukti.
GetDC, CoInitialize, keberadaan osascript, atau DISPLAY tidak cukup sebagai bukti semua permission.
Pisahkan screen capture, accessibility/UI automation, input control, microphone, camera, filesystem.
Gunakan verifikasi native per OS dan instruksi Settings resmi. Tambahkan test izin belum diberikan, ditolak, dicabut, dan diberikan. Jangan lakukan aksi destruktif.
```

## Prompt 7 — Credential vault

```text
Audit services/engine/app/core/credential_vault.py.
Prioritaskan Keychain, DPAPI/Credential Manager, dan Secret Service. Jangan menyimpan key plaintext berdekatan dengan ciphertext.
Tentukan fail-closed atau opt-in fallback yang diperingatkan jika secure backend tidak tersedia. Perkuat ACL Windows dan permission lintas OS.
Buat migrasi aman dan test decrypt, corruption, permission, migration, backend unavailable. Jangan pernah log secret.
```

## Prompt 8 — MCP lifecycle

```text
Audit services/engine/app/tools/mcp/mcp_client.py.
Terapkan initialize -> tunggu/validasi response -> notifications/initialized -> tools/list -> schema validation -> tools/call.
handshake_ok wajib sebelum tool dipanggil atau hasil diterima. Validasi argumen terhadap schema.
Tambahkan timeout, message size limit, process cleanup, least privilege dan sandbox filesystem/process/network.
Test handshake gagal, schema invalid, timeout, crash, dan argument mismatch.
```

## Prompt 9 — Skills security

```text
Hardening skill_manager.py dan runtime skills.
Skill pihak ketiga tidak tepercaya secara default. Implementasikan manifest dan tanda tangan digital publisher; verifikasi signature terhadap trust store, bukan metadata publisher. Wajibkan hash tepercaya.
Tampilkan publisher/source/permission/hash sebelum install. Pisahkan install, enable, execute. Terapkan sandbox filesystem/process/network least privilege.
Tolak path traversal, symlink berbahaya, archive bomb, executable tak terduga, manifest invalid. Jangan samakan instructions_preview dengan paket lengkap.
Tambahkan test malicious ZIP, tampered package, invalid signature, dan sandbox escape.
```

## Prompt 10 — WebSocket authorization

```text
Audit services/engine/app/api/ws.py.
Session wajib ditemukan sebelum subscribe. Cocokkan owner dengan trusted principal. Database error, timeout, atau lookup ambigu harus menolak akses.
Hapus default_user. Validasi ownership saat reconnect/session switch. Terapkan rate limit, message size limit, lifecycle cleanup.
Tambahkan test missing session, wrong owner, DB failure, reconnect, dan spoofed principal.
Tidak boleh ada fallback yang memberi akses saat ownership tidak dapat diverifikasi.
```

## Prompt 11 — Privacy gate

```text
Audit privacy_gate.py dan semua jalur pengiriman data ke cloud.
Data CONFIDENTIAL wajib consent eksplisit per request atau diblokir dari cloud. Consent harus terikat provider/model/tujuan/scope; mode global bukan consent otomatis.
Tambahkan preview dan redaction secret/PII. Perkuat klasifikasi; keyword hanya sinyal awal. Catat keputusan tanpa menyimpan konten sensitif yang tidak perlu.
Buat test seluruh privacy mode, classification, consent, dan provider routing. Default harus lokal jika kebijakan tidak jelas.
```

## Prompt 12 — Security regression CI

```text
Inventarisasi semua test security lama dan baru. Pastikan test P0/P1/P2 dijalankan di security.yml.
Kelompokkan unit, integration, platform-specific, security regression. Test harus independen dari urutan dan environment developer; gunakan temporary directory dan cleanup.
Jangan gunakan secret production. Failure harus exit non-zero. Jalankan workflow dan laporkan run yang benar-benar selesai.
Buat matriks temuan -> test -> workflow -> hasil. Jangan menyatakan lulus jika belum dieksekusi.
```

## Prompt 13 — Model discovery

```text
Audit model discovery, provider adapters, dan recommendation scoring.
Bedakan provider_verified, inferred, user_override, unknown; simpan source dan timestamp. Jangan klaim verified dari inferensi nama.
Normalisasi cap_score agar sesuai skala UI. Masukkan freshness, latency, availability, cost, health check. Sediakan refresh dan invalidasi metadata usang.
Tambahkan test skor, metadata tidak lengkap, provider unavailable. Jangan mengarang capability model.
```

## Prompt 14 — Release engineering

```text
Audit release tooling Windows/macOS.
Lengkapi SBOM dari Cargo.lock, Python lockfile, npm lockfile menggunakan SPDX/CycloneDX. Terapkan code signing per platform; verifikasi checksum/signature dan provenance secara terpisah.
Buat smoke test install, launch, upgrade, uninstall; uji sidecar, permission prompt, update flow.
Publikasikan release notes, SBOM, checksum, signature, dan instruksi verifikasi.
Jangan menyebut provenance attestation sebagai code signing.
```

## 9. Definition of Done sebelum public beta

- [ ] Seluruh P0 ditutup dengan source change dan regression test.
- [ ] CI, security workflow, build Windows/macOS hijau.
- [ ] Token tidak dikirim sebelum sidecar identity tervalidasi.
- [ ] Semua endpoint workspace/RAG/execute memakai authorization terpusat.
- [ ] Principal berasal dari trusted auth context.
- [ ] HITL fail-closed, terikat principal/konteks aksi, dan anti-replay.
- [ ] Permission OS tidak memberi `GRANTED` palsu.
- [ ] Credential vault memakai secure storage native atau fallback opt-in yang aman.
- [ ] MCP handshake dan schema validation wajib.
- [ ] Skills pihak ketiga diverifikasi dan disandbox.
- [ ] WebSocket menolak session missing dan ownership yang tidak pasti.
- [ ] Data CONFIDENTIAL tidak dikirim ke cloud tanpa consent eksplisit.
- [ ] Regression tests berjalan otomatis di CI.
- [ ] SBOM mencakup Python, npm, dan Cargo.
- [ ] Installer ditandatangani dan diuji install/launch/update/uninstall.
- [ ] Dokumentasi menjelaskan telemetry, data retention, permission, threat model, dan batas keamanan.

## 10. Kesimpulan

Commit `e5ae547` menunjukkan kemajuan berarti, tetapi akar masalah trust boundary dan otorisasi belum seluruhnya tertutup. Prioritas utama bukan menambah fitur agent/skill/model, melainkan memastikan identitas, izin, workspace, approval, dan eksekusi tool tidak dapat dipalsukan atau dilewati.

Urutan paling aman: perbaiki CI, tutup P0, buktikan dengan regression test, selesaikan P1, lalu lakukan pengujian installer dan rilis bertanda tangan. Sampai itu selesai, batasi AKSA pada pengujian internal dengan data non-rahasia.
