# AKSA — Independent Re-Audit Siklus 7
Tanggal: 19 November 2026  
Repository: https://github.com/yogijowo/aksa  
Branch: `main`  
Commit yang diaudit: `1ab8cfcdfe97ffea316f940b03a07eb14674a377`  
Commit pembanding Siklus 6: `f104d613f7699799aa64949cd8a4114e6614160b`

## 1. Ringkasan eksekutif

**Skor independen: 70/100**  
**Perubahan dari Siklus 6: +3 poin (67 → 70)**

Status rilis:
- Internal Alpha: dapat dilanjutkan dengan batasan.
- Private Beta: mungkin dengan kontrol ketat, terutama pembatasan skill pihak ketiga dan pengawasan eksekusi.
- Public Beta: belum direkomendasikan.
- Production GA: belum siap.

Audit ini menilai source code pada commit terbaru, bukan menerima klaim pada commit message atau dokumen proyek sebagai bukti. Perubahan Siklus 7 memperbaiki sejumlah masalah penting: Windows mulai memakai AppContainer, macOS beralih ke Seatbelt `deny default`, Linux memakai bubblewrap tanpa mount seluruh root host, handshake sidecar menjadi lebih ketat, serta runtime replay dan validasi artefak ditambahkan.

Namun, masih ada gap implementasi dan bukti runtime. Terutama: pembatasan handle inheritance di Windows, isolasi replay yang belum berada di batas OS, ACL runtime Windows yang sebagian best-effort, validasi path replay, serta tidak adanya hasil CI yang dapat diverifikasi pada saat audit.

## 2. Snapshot repository dan ruang lingkup

Commit terbaru yang ditemukan:
- `1ab8cfcdfe97ffea316f940b03a07eb14674a377`
- Pesan: `feat: implement independent reaudit cycle 6 security and sandboxing hardening`
- Commit ini satu commit di depan Siklus 6 (`f104d613...`).

File utama yang ditinjau:
- `services/engine/app/skills/windows_sandbox.py`
- `services/engine/app/skills/os_sandbox.py`
- `services/engine/app/skills/skill_manager.py`
- `services/engine/app/core/agent_learning.py`
- `services/engine/app/core/orchestrator.py`
- `services/engine/app/main.py`
- `services/engine/app/api/routes.py`
- `apps/desktop/src-tauri/src/sidecar.rs`
- `apps/desktop/src-tauri/src/lib.rs`
- `.github/workflows/ci.yml`
- `services/engine/tests/test_reaudit_cycle6_remediation.py`

Metode: inspeksi diff dan source file pada ref commit yang sama; menilai jalur eksekusi, kegagalan, validasi, dan cakupan test. Saya tidak menjalankan binary Windows/macOS/Linux dari lingkungan audit ini. Hasil CI remote untuk commit ini juga belum tersedia untuk diverifikasi.

## 3. Skor per domain

| Domain | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 78 | 15% |
| Fungsi inti | 75 | 15% |
| AI Agent & adaptive learning | 75 | 15% |
| Keamanan & isolasi | 63 | 20% |
| Privasi & kredensial | 72 | 10% |
| Desktop & integrasi OS | 66 | 10% |
| QA & pengujian | 70 | 10% |
| DevSecOps & release | 68 | 5% |
| **Total tertimbang** | **70.1 ≈ 70** | **100%** |

Skor adalah penilaian engineering independen berbasis source dan bukti yang tersedia, bukan sertifikasi formal atau klaim bahwa seluruh test telah dijalankan.

## 4. Perbaikan yang terkonfirmasi

### 4.1 Windows AppContainer + suspended Job Object

File: `services/engine/app/skills/windows_sandbox.py`

Perbaikan yang terlihat:
- Menggunakan AppContainer dengan zero declared capabilities.
- Menambahkan ACL untuk workspace dan read roots.
- Membuat proses dengan `CREATE_SUSPENDED` dan `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`.
- Memasang Job Object sebelum `ResumeThread`.
- Jika `AssignProcessToJobObject` gagal, proses dihentikan dan launcher melempar error.
- `wrap_command()` tidak lagi mengembalikan command mentah pada Windows.
- `execute_in_os_sandbox()` memanggil launcher native Windows.

Ini merupakan lompatan penting dibanding Siklus 6. Namun, implementasi belum dapat dinyatakan aman untuk seluruh skenario karena masih ada catatan P1 di bagian temuan.

### 4.2 macOS Seatbelt

`build_seatbelt_profile()` kini memulai profil dengan `(deny default)` dan secara eksplisit mengizinkan akses yang dibutuhkan runtime. Profil juga menolak network dan process-fork serta membatasi penulisan ke workspace.

Arah ini lebih baik daripada kebijakan allow-default. Tetap diperlukan pengujian nyata pada versi macOS yang didukung karena kompatibilitas runtime Python, framework, dan dynamic library dapat berbeda.

### 4.3 Linux bubblewrap

`build_linux_bwrap_args()`:
- memakai `--unshare-all`, `--die-with-parent`, `--new-session`;
- menjatuhkan capability dengan `--cap-drop ALL`;
- tidak lagi melakukan `--ro-bind / /`;
- memasang beberapa direktori runtime sistem read-only;
- membatasi workspace sebagai lokasi tulis.

Ini mempersempit paparan host. Namun, mount `/usr` dan direktori sistem lainnya masih perlu ditinjau terhadap data sensitif yang mungkin ditempatkan aplikasi lain di lokasi tersebut.

### 4.4 Sidecar handshake

File: `apps/desktop/src-tauri/src/sidecar.rs`, `lib.rs`; `services/engine/app/main.py`

Perbaikan yang terkonfirmasi:
- manifest menjadi wajib sebelum lifecycle `Ready`;
- validasi host `127.0.0.1`;
- validasi port bukan nol dan sama dengan readiness marker;
- validasi PID terhadap child process;
- validasi versi engine;
- validasi `launch_id` pada marker dan manifest;
- HMAC health challenge tetap menjadi bagian dari handshake;
- kegagalan validasi memindahkan lifecycle ke `Failed`.

`main.py` menulis manifest secara atomik melalui file sementara, flush, dan fsync file, kemudian `os.replace`. Ini memperbaiki temuan manifest opsional dari Siklus 6.

Catatan: mode file `0600` adalah perilaku POSIX; Windows membutuhkan pemeriksaan ACL yang setara. Penghapusan manifest stale di Tauri juga mengabaikan error penghapusan (`let _ = ...`), sehingga perlu dipastikan kegagalan membersihkan manifest lama tidak dapat mengakibatkan startup ambigu. `launch_id` baru membantu menghalangi manifest stale, tetapi lebih baik gagal jika stale manifest tidak dapat dibersihkan.

### 4.5 Runtime replay skill dan DAG/schema

File: `services/engine/app/core/agent_learning.py`

Perbaikan:
- validasi dependency DAG;
- pemeriksaan parameter terhadap JSON schema tool jika schema tersedia;
- replay dengan beberapa fixture;
- temporary workspace per fixture;
- pemeriksaan artefak hasil;
- penghitungan `replay_pass_rate` dan `calibrated_confidence`.

Ini lebih baik daripada static trace screening Siklus 6. Akan tetapi, cara eksekusi handler masih menyisakan masalah isolasi (P1).

### 4.6 Artifact postcondition

File: `services/engine/app/core/orchestrator.py`

Perbaikan:
- ekstensi tidak dikenal menjadi `unsupported`, tidak auto-pass;
- JSON scalar dan container kosong ditolak;
- XLSX placeholder satu sel ditolak;
- PDF tanpa teks/isi bermakna ditolak;
- beberapa format mendukung pemeriksaan schema seperti required columns, keywords, formula, dan minimum rows;
- hasil yang tidak lolos dapat ditandai `UNVERIFIED`.

Ini mengurangi false positive, tetapi belum setara validasi semantik menyeluruh atas maksud pengguna.

### 4.7 CI matrix

`.github/workflows/ci.yml` kini memiliki matrix Windows, macOS, dan Ubuntu. Ubuntu memasang bubblewrap dan dependensi Tauri. Workflow menjalankan pytest, smoke test sidecar, npm test/build, Cargo test/check, serta SBOM.

Perlu dibedakan antara konfigurasi workflow dan hasil eksekusi: pada saat audit, combined status yang diperoleh tidak memuat status check dan daftar workflow run yang diperoleh kosong. Maka CI commit ini **belum dapat dinyatakan hijau**.

## 5. Temuan audit yang masih terbuka

### P1-01 — Windows: handle inheritance belum dibatasi eksplisit

File: `services/engine/app/skills/windows_sandbox.py`, sekitar pemanggilan `CreateProcessW`.

`CreateProcessW` dipanggil dengan `bInheritHandles=True`. Kode membuat pipe stdout/stderr dan menonaktifkan inheritance pada read end, tetapi belum terlihat penggunaan `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` untuk allowlist handle yang boleh diwariskan.

Dampak:
- proses skill dapat menerima handle inheritable lain yang dimiliki proses induk;
- jika proses desktop/engine atau library membuka handle sensitif dengan inheritance aktif, batas isolasi bisa bocor melalui handle tersebut;
- hal ini memperluas kemampuan child process di luar kebutuhan output pipe.

Rekomendasi:
1. Tambahkan `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`.
2. Hanya izinkan handle stdin/stdout/stderr yang memang diperlukan.
3. Set inheritance flag secara eksplisit untuk setiap handle.
4. Tambahkan test Win32 mock untuk memastikan handle list dipasang.
5. Tambahkan test Windows nyata yang memverifikasi child tidak dapat menggunakan handle induk yang tidak diizinkan.

Severity: **P1**. Ini bukan bukti eksploitasi yang telah berhasil, tetapi celah hardening yang penting pada boundary proses.

### P1-02 — Runtime replay menjalankan handler di proses engine yang sama

File: `services/engine/app/core/agent_learning.py`, method `replay_candidate_in_sandbox()`.

Walaupun fungsi membuat `TemporaryDirectory` dan mendaftarkan `WorkspacePolicy`, jalur default memanggil:

`handler = tool_registry._handlers.get(tool_name)`  
`res = await handler(**resolved_args)`

Dengan demikian:
- handler berjalan langsung di proses engine;
- jalur `tool_registry.execute()` dilewati;
- wrapper permission/HITL dan validasi terpusat yang mungkin ada pada jalur registry tidak otomatis dijalankan;
- temporary workspace bukan isolasi OS untuk kode handler;
- handler yang melakukan network, membaca file, mengubah state, atau menjalankan efek samping dapat melampaui ekspektasi replay jika implementasinya tidak secara mandiri menegakkan policy.

Klaim “isolated runtime replay” terlalu kuat untuk desain saat ini. Ini adalah replay tool handler dengan workspace sementara, bukan eksekusi terisolasi OS.

Rekomendasi:
1. Jangan panggil private `_handlers` secara langsung.
2. Buat interface replay/dry-run khusus di ToolRegistry dengan policy yang eksplisit.
3. Tool replay harus dibatasi ke allowlist tool yang deterministik dan tidak memiliki efek samping eksternal.
4. Jalankan tool yang berpotensi mengeksekusi kode di worker process terisolasi OS.
5. Tambahkan test bahwa handler yang mencoba network, membaca file di luar workspace, mengakses credential store, atau memodifikasi state produksi akan ditolak.
6. Jangan menganggap pass rate fixture sebagai bukti keamanan eksekusi.

Severity: **P1**.

### P1-03 — Windows read_roots ACL masih best-effort

File: `services/engine/app/skills/windows_sandbox.py`, bagian pemasangan ACL.

Workspace ACL wajib dan jika gagal akan menghentikan eksekusi. Namun ACL pada `read_roots` hanya ditambahkan ke daftar cleanup jika berhasil; kegagalan pemasangan tidak selalu menyebabkan error.

Konsekuensi:
- runtime dependency bisa tidak terbaca dan eksekusi gagal dengan error yang sulit didiagnosis;
- lebih penting, sistem tidak membedakan dependency wajib dari path opsional;
- kontrak least-privilege menjadi tidak deterministik.

Rekomendasi:
- pisahkan `required_read_roots` dan `optional_read_roots`;
- jika root runtime wajib gagal diberi ACL, hentikan eksekusi;
- validasi bahwa root tidak mengandung direktori terlalu luas atau path yang tidak diperlukan;
- catat keputusan ACL tanpa membocorkan path sensitif ke log publik.

Severity: **P1** untuk reliability/security contract.

### P2-01 — Validasi path hasil substitusi replay belum lengkap

File: `services/engine/app/core/agent_learning.py`, fungsi lokal `_resolve_val()` dalam `replay_candidate_in_sandbox()`.

Fixture input file memeriksa absolute path dan `..`, tetapi untuk argumen tool yang dianggap path, kode membentuk `ws / vp` tanpa canonical containment check yang terlihat pada fungsi tersebut.

Contoh pola yang harus ditolak:
- `../outside.txt`
- `subdir/../../outside.txt`
- symlink di dalam workspace yang menunjuk keluar workspace.

Rekomendasi:
- gunakan satu helper canonicalize/resolve path;
- validasi hasil `resolve(strict=False)` tetap berada di bawah root workspace;
- tolak symlink escape dan traversal;
- terapkan untuk semua key path, bukan hanya `input_files`.

Severity: **P2**, dapat naik menjadi P1 jika handler menerima path dari sumber tidak tepercaya dan tidak memvalidasinya lagi.

### P2-02 — Manifest stale: kegagalan penghapusan diabaikan

File: `apps/desktop/src-tauri/src/lib.rs`.

Penghapusan manifest lama menggunakan best-effort. Validasi `launch_id` yang baru adalah pertahanan tambahan yang baik, tetapi startup lebih deterministik jika aplikasi memastikan file lama benar-benar dibersihkan atau menolak startup.

Rekomendasi:
- bila manifest lama ada dan tidak dapat dihapus, jangan lanjut spawn sidecar;
- pastikan direktori runtime memiliki ACL/permission yang tepat;
- pertimbangkan file manifest per-launch yang unik, bukan satu nama tetap;
- lakukan test race antara proses lama dan proses baru.

Severity: **P2**.

### P2-03 — Semantic artifact validation masih heuristik

File: `services/engine/app/core/orchestrator.py`.

Validasi format lebih baik, tetapi schema yang diturunkan dari prompt masih sangat terbatas. Contohnya, deteksi formula Excel bergantung pada kata seperti “rumus”, “formula”, `=sum`, atau `=average`.

File dapat valid secara struktur tetapi tetap salah dari sisi kebutuhan:
- kolom/angka yang diminta tidak sesuai;
- formula ada tetapi salah;
- dokumen berisi teks namun tidak memenuhi struktur yang diminta;
- PDF berisi teks tetapi isi tidak benar.

Rekomendasi:
- turunkan postcondition terstruktur dari rencana tugas sebelum eksekusi;
- verifikasi nilai, formula, jumlah baris, section, dan relasi antar data;
- untuk hasil penting, minta agent verifier terpisah membandingkan output terhadap spesifikasi;
- bedakan “format valid”, “konten terdeteksi”, dan “task requirement satisfied”.

Severity: **P2**.

### P2-04 — Linux bwrap masih perlu audit mount dan runtime nyata

Kode tidak lagi mengekspos seluruh root host dan telah mengaktifkan namespace isolation. Namun `/usr`, `/lib`, `/bin`, dan beberapa direktori sistem tetap dipasang read-only. Perlu pengujian terhadap data aplikasi atau credential yang mungkin berada di lokasi tersebut, socket, `/proc`, dan perilaku versi distro.

Rekomendasi:
- audit isi mount pada target distro;
- pertimbangkan root filesystem minimal/runtime image;
- test socket, procfs, symlink, mount, dan path traversal;
- pastikan CI Ubuntu menjalankan test bwrap nyata dan bukan hanya test pembentukan argumen.

Severity: **P2**.

## 6. Test dan bukti CI

Test baru mencakup:
- mock urutan Windows suspended process dan Job Object;
- test runtime Windows AppContainer yang hanya berjalan pada Windows;
- test macOS Seatbelt yang hanya berjalan pada macOS;
- test Linux bwrap nyata bila `bwrap` tersedia;
- manifest `launch_id`;
- unknown extension, JSON scalar, placeholder XLSX, PDF ornamental;
- runtime replay fixture;
- trust store dan MCP spoofing.

Kualitas cakupan test meningkat. Namun mock Win32 tidak menggantikan test API Windows nyata. Test runtime platform-spesifik baru membuktikan sesuatu jika workflow platform tersebut benar-benar berjalan dan lulus.

Status yang dapat diverifikasi saat audit:
- Combined commit status: tidak mengembalikan status check.
- Workflow runs: tidak mengembalikan run yang dapat diverifikasi.

Kesimpulan: **CI belum terverifikasi**, bukan berarti gagal. Jangan tulis “semua test lulus” sampai bukti run tersedia.

## 7. Roadmap remediasi prioritas

### Gate 1 — sebelum Private Beta lebih luas
1. Tambahkan explicit handle inheritance allowlist pada Windows.
2. Pisahkan replay tool aman dan tool yang berpotensi memiliki efek samping.
3. Hentikan pemanggilan handler private secara langsung atau buat replay executor dengan policy eksplisit.
4. Jadikan ACL read root yang wajib bersifat fail-closed.
5. Perketat canonical path dan symlink containment pada replay.

### Gate 2 — sebelum Public Beta
1. Dapatkan hasil CI hijau untuk Windows, macOS, dan Ubuntu pada commit yang sama.
2. Jalankan test boundary nyata untuk Windows AppContainer, macOS Seatbelt, dan Linux bubblewrap.
3. Tambahkan adversarial tests untuk handle inheritance, symlink escape, credential access, network, process spawn, dan timeout.
4. Perkuat task-specific semantic validation artefak.
5. Pastikan manifest stale tidak bisa menyebabkan startup ambigu.

### Gate 3 — sebelum Production GA
1. Threat model formal untuk local sidecar, plugin, MCP, skills, dan multi-agent.
2. Penetration test independen pada build rilis.
3. Uji upgrade, rollback, uninstall, permission revocation, dan crash recovery.
4. Audit supply-chain signing dan release provenance.
5. Observability keamanan dengan redaksi data sensitif dan audit trail yang tidak dapat dimodifikasi sembarang.

## 8. Keputusan akhir

AKSA mengalami kemajuan yang substansial pada Siklus 7. Implementasi Windows AppContainer, Seatbelt deny-default, bubblewrap, manifest wajib, dan runtime replay menunjukkan arah arsitektur yang lebih matang.

Namun, saya belum merekomendasikan Public Beta. Dua prioritas terbesar saat ini adalah:
1. menyelesaikan boundary Windows (khususnya handle inheritance dan ACL);
2. mengubah replay skill menjadi eksekusi yang benar-benar dibatasi, bukan sekadar handler yang dijalankan dalam temporary workspace.

Skor **70/100** adalah penilaian kondisi source yang terlihat. Skor ini bukan sertifikasi keamanan, dan tidak mengasumsikan test platform telah lulus.

## 9. Referensi commit

- Commit Siklus 7: https://github.com/yogijowo/aksa/commit/1ab8cfcdfe97ffea316f940b03a07eb14674a377
- Compare Siklus 6 → 7: https://github.com/yogijowo/aksa/compare/f104d613f7699799aa64949cd8a4114e6614160b...1ab8cfcdfe97ffea316f940b03a07eb14674a377


---

## 10. Log Remediasi Teknis & Verifikasi Lokal (Post-Cycle 7)

Seluruh temuan **P1 (`P1-01` s.d. `P1-03`)** dan **P2 (`P2-01` s.d. `P2-04`)** pada laporan Siklus 7 ini telah diremediasi beserta pengujian adversarial di `services/engine/tests/test_reaudit_cycle7_remediation.py` dan unit test Rust `apps/desktop/src-tauri/src/sidecar.rs`:

| ID | Status Remediasi | Perubahan Kode Utama | Bukti Uji & Batasan OS |
| :--- | :--- | :--- | :--- |
| **`P1-01`** | **Selesai (Mock macOS hijau; Nyata di Windows CI)** | `services/engine/app/skills/windows_sandbox.py`: `CreatePipe` + `SetHandleInformation` (`read=0`, `write=1`), `InitializeProcThreadAttributeList(..., 2, ...)`, `PROC_THREAD_ATTRIBUTE_HANDLE_LIST (0x00020002)` eksklusif `[h_out_w, h_err_w]`, `hStdInput = null`. | `test_p1_01_windows_appcontainer_uses_explicit_handle_list_only_for_stdio_pipes` (`PASSED`); `test_p1_01_real_windows_child_cannot_inherit_unrelated_parent_handle` (`@win32_only`, `SKIPPED` di macOS, target Windows CI). |
| **`P1-02`** | **Selesai & Terverifikasi** | `services/engine/app/tools/registry.py` & `agent_learning.py`: menghapus seluruh akses `tool_registry._handlers`; menambahkan `REPLAY_ALLOWED_TOOLS` & `ToolRegistry.execute_replay(...)` (validasi allowlist, skema argumen, penolakan override kebijakan, dan jail `SandboxManager` `allow_execute=False` ke 1 `replay_workspace`). | `test_p1_02_agent_learning_never_accesses_private_tool_handlers`, `test_p1_02_execute_replay_blocks_side_effectful_and_disallowed_tools`, `test_p1_02_replay_candidate_routes_via_execute_replay_and_rejects_side_effects` (`PASSED`). |
| **`P1-03`** | **Selesai (Mock macOS hijau; Nyata di Windows CI)** | `windows_sandbox.py`, `os_sandbox.py`, `skill_manager.py`: memisahkan `required_read_roots` (fail-closed) vs `optional_read_roots` (diaudit ter-redaksi via `redact_path_for_log`); menambahkan `validate_sandbox_read_root()` untuk menolak root luas (`/`, `C:\`, `C:\Users`, `/Users`, `/home`, `~`). | `test_p1_03_rejects_overly_broad_read_roots_and_aborts_on_required_acl_failure`, `test_p1_03_optional_read_root_acl_failure_logs_redacted_summary` (`PASSED`). |
| **`P2-01`** | **Selesai & Terverifikasi** | `services/engine/app/core/agent_learning.py`: menambahkan `resolve_replay_path()` kanonis (`resolve(strict=False)`, tolak `..`, UNC/ADS, dan symlink di tiap segmen path untuk argumen top-level maupun nested dict/list). | `test_p2_01_resolve_replay_path_blocks_traversal_and_symlinks` (`PASSED`). |
| **`P2-02`** | **Selesai & Terverifikasi (Rust + Python)** | `apps/desktop/src-tauri/src/sidecar.rs`, `lib.rs`, `services/engine/app/main.py`: `prepare_runtime_manifest_slot()` mengunci izin `0o700`, menolak direktori runtime symlink, gagal tertutup bila stale manifest tak dapat dihapus, dan menggunakan manifest unik `engine_port_<launch_id>.json` (`AKSA_MANIFEST_PATH`). | 3 unit test baru `sidecar.rs` (`cargo test`: 18/18 `PASSED`) + `test_p2_02_engine_honors_per_launch_aksa_manifest_path` (`PASSED`). |
| **`P2-03`** | **Selesai & Terverifikasi** | `services/engine/app/core/orchestrator.py`: `derive_expected_artifact_schema()` menurunkan ekspektasi terstruktur pra-eksekusi (`required_columns`, `require_formulas`, `required_sections`, `required_keys`, `min_rows`, `min_paragraphs`, `required_keywords`); `get_artifact_postcondition_breakdown()` memisahkan `format_valid`, `content_detected`, dan `task_requirement_satisfied`. | `test_p2_03_pre_execution_schema_and_orthogonal_gates_catch_wrong_content` (`PASSED`). |
| **`P2-04`** | **Selesai (Args macOS hijau; Nyata di Linux CI)** | `services/engine/app/skills/os_sandbox.py`: mempersempit mount `bwrap` ke subpath runtime (`/usr/bin`, `/usr/lib`, `/usr/lib64`, `/usr/libexec`, `/usr/share`, `/lib`, `/lib64`, `/bin`, `/etc/alternatives`, `/etc/ld.so.cache`, `/etc/ssl/certs`), tidak me-mount `/usr` mentah (menghindari `/usr/local`), menambah `--hostname aksa-sandbox`. | `test_p2_04_linux_bwrap_excludes_broad_usr_and_usr_local` (`PASSED`); `test_p2_04_real_linux_bwrap_blocks_network_proc_symlinks_and_traversal` (`@linux_bwrap_only`, `SKIPPED` di macOS, target Ubuntu CI). |

### Catatan Kejujuran Status Kesiapan
- **Perbaikan Regresi Siklus 5 yang Ditemukan Saat Verifikasi:** (1) `test_engine_owns_port_and_answers_nonce_hmac` pada `test_reaudit_cycle5_remediation.py` diperbarui agar regex siap menerima akhiran `:launch_id=...` (mencegah deadlock `readline()` tanpa batas), dan (2) `PublisherTrustStore._persist()` pada `skill_manager.py` hanya menjalankan `os.chmod(..., 0o700)` saat membuat direktori baru agar direktori yang dikunci `0o500` tetap fail-closed.
- **Hasil Uji Lokal pada Host macOS (`darwin`):** Pytest **243 passed, 4 skipped** (`@win32_only` / `@linux_bwrap_only`), Cargo test **18 passed**, Vitest **9 passed**, `cargo check` bersih, `tsc --noEmit && vite build` bersih, `npm audit --omit=dev --audit-level=high` 0 kerentanan, dan `release_tooling.py smoke-test` lulus.
- **Syarat Menuju Public Beta:** Eksekusi pipeline GitHub Actions hijau di `windows-latest` & `ubuntu-latest` untuk 4 pengujian sandbox OS nyata yang berstatus skipped di macOS, serta pelaksanaan **Re-Audit Independen Siklus 8**.
