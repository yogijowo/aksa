# AKSA — Independent Re-Audit Siklus 8
Tanggal: 19 November 2026
Repository: https://github.com/yogijowo/aksa
Commit: `88024aa4f16384e347d6490192c3866bea40151e`
Pembanding Siklus 7: `1ab8cfcdfe97ffea316f940b03a07eb14674a377`

## 1. Ringkasan eksekutif

**Skor independen: 73/100** (Siklus 7: 70/100, naik 3 poin).

Status:
- Internal Alpha: dapat dilanjutkan dengan pembatasan.
- Private Beta: belum direkomendasikan untuk penggunaan luas sampai dua temuan P1 ditutup.
- Public Beta: belum siap.
- Production GA: belum siap.

Commit ini memperbaiki sebagian besar temuan Siklus 7: Windows explicit handle allowlist, replay melalui registry khusus, ACL required/optional, canonical path dan symlink checks, manifest per-launch, semantic artifact gates, serta mount Linux yang lebih sempit.

Namun, audit menemukan dua masalah baru:
1. Replay memodifikasi singleton `sandbox_manager` global dengan menghapus seluruh workspace policy sementara.
2. `expected_artifacts` dari fixture tidak dijail ke replay workspace sebelum dibaca verifier.

Status CI remote untuk commit ini juga belum dapat diverifikasi: combined status kosong dan workflow runs yang diperoleh kosong. Klaim test lokal di `PROGRESS.md` bukan bukti CI lintas-OS.

## 2. Snapshot dan ruang lingkup

File utama yang diperiksa:
- `services/engine/app/skills/windows_sandbox.py`
- `services/engine/app/skills/os_sandbox.py`
- `services/engine/app/tools/registry.py`
- `services/engine/app/core/agent_learning.py`
- `services/engine/app/core/sandbox.py`
- `services/engine/app/core/orchestrator.py`
- `services/engine/app/api/routes.py`
- `services/engine/app/main.py`
- `apps/desktop/src-tauri/src/sidecar.rs`
- `apps/desktop/src-tauri/src/lib.rs`
- `services/engine/tests/test_reaudit_cycle7_remediation.py`
- `.github/workflows/ci.yml`

Metode: inspeksi commit diff, source pada ref commit yang sama, jalur API yang menerima replay fixtures, tool handlers, dan test baru. Saya tidak menjalankan binary Windows/Linux/macOS dari lingkungan audit ini.

## 3. Skor per domain

| Domain | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 79 | 15% |
| Fungsi inti | 76 | 15% |
| AI Agent & adaptive learning | 77 | 15% |
| Keamanan & isolasi | 67 | 20% |
| Privasi & kredensial | 72 | 10% |
| Desktop & integrasi OS | 68 | 10% |
| QA & pengujian | 72 | 10% |
| DevSecOps & release | 68 | 5% |
| **Total tertimbang** | **72.8 ≈ 73** | **100%** |

Skor ini adalah penilaian engineering independen terhadap source dan bukti yang tersedia, bukan sertifikasi keamanan.

## 4. Remediasi Siklus 7 yang terkonfirmasi

### 4.1 Windows explicit handle inheritance allowlist

`windows_sandbox.py` sekarang:
- menggunakan `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`;
- menginisialisasi dua attribute: security capabilities dan handle list;
- membatasi inherited handles pada stdout/stderr write pipe;
- menonaktifkan inheritance pada read pipe;
- membuat stdin child null;
- membuat child suspended;
- memasang Job Object sebelum `ResumeThread`;
- menghentikan proses jika setup atau assignment gagal.

Ini memperbaiki temuan handle inheritance Siklus 7 secara substansial. Test mock memeriksa handle list, dan test Windows nyata ditambahkan. Namun hasil test Windows nyata belum terverifikasi pada CI remote.

### 4.2 Replay melalui ToolRegistry khusus

`agent_learning.py` tidak lagi mengakses `tool_registry._handlers` secara langsung. `registry.py` menambahkan `REPLAY_ALLOWED_TOOLS`, menolak MCP, live computer use, shell/python execution, memory mutation, dan tool side-effect lain, memeriksa parameter, serta mengharuskan workspace policy tunggal yang sesuai replay workspace dan `allow_execute=False`.

Catatan: `execute_replay()` masih memanggil handler built-in secara langsung setelah pemeriksaan policy, bukan melalui `ExecutionPolicyGateway`. Ini hanya aman jika allowlist tetap deterministik dan semua handler menjaga batas workspace sendiri. Parameter `tool_executor` opsional juga masih dapat menggantikan jalur registry pada service internal; route API saat ini tidak mengirim parameter tersebut, tetapi interface ini sebaiknya dihapus atau dibatasi.

### 4.3 Required vs optional read roots

Required roots harus ada dan ACL read/execute harus berhasil. Optional roots dapat dilewati dengan log redacted. Root filesystem, drive root, dan home/profile directories ditolak. Validasi broad root juga diterapkan saat membangun profil macOS/Linux.

### 4.4 Canonical path dan symlink replay

`resolve_replay_path()` menolak `..`, UNC, null byte, ADS, symlink components, serta hasil resolve yang keluar dari workspace. Argumen path dalam struktur list/dict diproses rekursif. Ini memperbaiki traversal pada input dan argumen tool, tetapi tahap postcondition artefak belum menggunakan helper ini.

### 4.5 Sidecar manifest per-launch

Rust membuat nama manifest unik per launch, membersihkan stale manifest secara fail-closed, menolak runtime directory symlink, dan mengunci permission Unix ke `0700`. Handshake tetap memvalidasi PID, port, host, version, launch ID, dan HMAC sebelum Ready.

Python mendukung `AKSA_MANIFEST_PATH`, memastikan manifest berada langsung di runtime directory, menolak target manifest symlink, menulis file sementara lalu `os.replace`, dan menggunakan permission `0600` pada POSIX.

### 4.6 Linux bubblewrap

Mount system runtime dipersempit ke subpath seperti `/usr/bin`, `/usr/lib`, `/usr/libexec`, `/usr/share`, `/lib`, `/bin`, dan beberapa direktori sertifikat. Root `/usr`, `/usr/local`, `/home`, `/root`, `/run`, `/var`, dan `/sys` tidak lagi dipasang secara luas. Test Linux khusus ditambahkan, tetapi masih menunggu hasil CI runtime yang sebenarnya.

### 4.7 Artifact postconditions

Pemeriksaan memisahkan `format_valid`, `content_detected`, `task_requirement_satisfied`, dan `semantic_postcondition_passed`. Prompt dapat diturunkan menjadi required columns, formulas, sections, keys, minimum rows/paragraphs, dan keywords. Ini mengurangi false positive, tetapi parser prompt tetap heuristik.

## 5. Temuan baru

### P1-01 — Replay mengubah global workspace policy dan menimbulkan race antar-request

File: `services/engine/app/core/agent_learning.py`, `replay_candidate_in_sandbox()`.

Urutan kode:
1. Menyimpan snapshot `prior_workspaces = dict(sandbox_manager._workspaces)`.
2. Menjalankan `sandbox_manager.clear_all_workspaces()`.
3. Mendaftarkan temporary replay workspace sebagai satu-satunya policy.
4. Menjalankan tool replay secara asynchronous.
5. Pada `finally`, memulihkan snapshot dengan assignment langsung ke `sandbox_manager._workspaces`.

`SandboxManager` adalah singleton global yang juga dipakai tool dan request lain. Selama replay berlangsung, request pengguna lain yang sedang membaca/menulis workspace dapat gagal karena policy mereka dihapus sementara.

Race yang lebih serius:
- Request A memulai replay dan menyimpan snapshot workspace lama.
- Replay menghapus seluruh policy.
- Request B mendaftarkan workspace baru atau mengubah permission.
- Replay A selesai lalu memulihkan snapshot lama.
- Perubahan workspace dari request B dapat hilang karena snapshot lama menimpa state global.

Dampak: denial of service sementara, kehilangan perubahan izin workspace yang terjadi bersamaan, dan perilaku lintas-agent/session yang tidak deterministik.

Rekomendasi:
1. Jangan panggil `clear_all_workspaces()` untuk replay.
2. Gunakan instance `SandboxManager` khusus replay yang tidak berbagi singleton produksi.
3. Inject manager ke tool handlers melalui execution context, bukan global import.
4. Alternatif: context-local policy registry yang benar-benar terisolasi per async task.
5. Tambahkan test concurrency dengan replay, operasi file, dan perubahan permission berjalan bersamaan.

Severity: **P1**.

### P1-02 — `expected_artifacts` dapat keluar dari replay workspace saat verifier membaca file

File: `services/engine/app/core/agent_learning.py`, bagian postcondition.

Kode membangun target dengan pola `target_art = ws / exp_f`, lalu memanggil `verify_artifact_postcondition(target_art, expected_schema=fixture.get("expected_schema"))`. Tidak terlihat pemanggilan `resolve_replay_path()` pada `exp_f`.

`Path` mengizinkan `../../private/file.pdf` keluar dari workspace; absolute path juga menggantikan prefix `ws` saat digabungkan.

Route API menerima `replay_fixtures` dari request (`EvaluateCandidateRequest`) dan meneruskannya ke service. Fixture karenanya tidak boleh dianggap selalu trusted.

Dampak:
- verifier dapat membuka file di luar workspace;
- schema dapat berisi `required_keywords`, sehingga hasil evaluasi berpotensi menjadi oracle apakah string tertentu terdapat dalam file target;
- verifier membaca dan memproses data yang bukan bagian dari replay workspace;
- file besar/format kompleks dapat membebani parser.

Ini melewati perbaikan path containment pada argumen tool. Validasi tool input tidak cukup jika tahap postcondition menerima path eksternal.

Rekomendasi:
1. Validasi setiap `expected_artifacts` dengan `resolve_replay_path(exp_f, ws)`.
2. Tolak absolute path dan traversal.
3. Pastikan resolved path berada di bawah workspace sebelum verifier dipanggil.
4. Validasi juga path pada `run_artifacts` yang dikembalikan tool.
5. Batasi ukuran file dan waktu parsing.
6. Tambahkan test API-level untuk absolute path dan `../../`, dan pastikan verifier tidak membuka file eksternal.

Severity: **P1**.

### P2-01 — `tool_executor` masih menjadi extension point yang dapat melewati registry

File: `services/engine/app/core/agent_learning.py`.

`replay_candidate_in_sandbox()` menerima `tool_executor` opsional. Jika diberikan, fungsi memanggil callback itu alih-alih `tool_registry.execute_replay()`. Route API saat ini tidak mengirim callback ini, sehingga saya tidak menyimpulkan ada jalur bypass remote yang sudah terbukti. Namun interface ini berisiko jika dipakai service lain atau plugin di masa depan.

Rekomendasi: hapus parameter callback dari production service; jika diperlukan untuk test, inject hanya di test fixture atau gunakan protocol yang tetap memaksa allowlist, schema, dan workspace policy.

Severity: **P2**.

### P2-02 — Runtime replay masih mengandalkan singleton/global mutation

Penggunaan `sandbox_manager._workspaces` secara langsung mengikat evaluator ke detail internal manager. Ini memperbesar risiko concurrency dan membuat evolusi policy sulit. Akar masalahnya sama dengan P1-01; jangan dihitung sebagai risiko terpisah.

Rekomendasi: replay execution context khusus yang memegang workspace, tool allowlist, policy, dan artifact root sendiri.

### P2-03 — Semantic verification masih heuristik

Schema derivation dari prompt tidak membuktikan formula Excel benar secara numerik, relasi antar kolom benar, atau isi dokumen memenuhi maksud pengguna. `task_requirement_satisfied` harus dipahami sebagai rule checks yang berhasil, bukan jaminan kebenaran semantik penuh.

Rekomendasi: postcondition terstruktur dari planner, expected values, formula evaluation, schema eksplisit, dan independent verifier.

## 6. Bukti pengujian dan CI

`PROGRESS.md` pada commit ini mengklaim verifikasi lokal macOS:
- Pytest: 243 passed, 4 skipped;
- Cargo: 18 passed;
- Vitest: 9 passed;
- `cargo check`: clean;
- TypeScript/Vite build: clean;
- sidecar smoke test: passed;
- `npm audit --omit=dev`: 0 vulnerabilities.

Empat test yang dilewati adalah test runtime Windows AppContainer dan Linux bubblewrap yang hanya dapat dijalankan pada OS masing-masing. Klaim lokal ini bukan pengganti bukti CI remote.

Workflow `.github/workflows/ci.yml` memiliki matrix `windows-latest`, `macos-latest`, dan `ubuntu-latest`.

Status yang diperoleh untuk commit ini:
- Combined status: `statuses: []`;
- Workflow runs: `[]`.

Kesimpulan: **CI lintas-OS belum terverifikasi dari GitHub saat audit**. Ini bukan berarti test gagal; saya tidak memiliki bukti run yang dapat dinyatakan hijau.

## 7. Roadmap remediasi

### Gate 1 — sebelum Private Beta lebih luas
1. Pisahkan replay `SandboxManager` dari singleton global produksi.
2. Validasi `expected_artifacts` dan `run_artifacts` dengan canonical workspace containment.
3. Hapus atau batasi `tool_executor` agar tidak menjadi bypass replay.
4. Tambahkan test concurrency dan API path traversal untuk verifier.

### Gate 2 — sebelum Public Beta
1. Jalankan dan simpan bukti CI Windows/macOS/Linux pada commit yang sama.
2. Verifikasi runtime AppContainer di Windows runner.
3. Verifikasi bwrap runtime dan adversarial test di Ubuntu runner.
4. Tambahkan test arbitrary artifact path, symlink, large files, malformed documents, dan race workspace.
5. Audit seluruh jalur yang mengubah singleton `sandbox_manager`, termasuk revoke-all, registration, replay, dan task execution.

### Gate 3 — sebelum Production GA
1. Threat model formal untuk sidecar, skills, MCP, multi-agent, dan replay evaluator.
2. Penetration test independen pada build rilis.
3. Upgrade/rollback/uninstall/permission revocation/crash recovery tests.
4. Release signing, provenance, dan supply-chain verification.
5. Security observability dengan redaksi data sensitif dan audit trail yang tahan manipulasi.

## 8. Keputusan akhir

Siklus 8 menunjukkan kemajuan nyata. Windows explicit handle allowlist, fail-closed ACL, manifest per-launch, replay allowlist, canonical path helper, dan Linux mount yang lebih sempit merupakan peningkatan penting.

Namun ada dua temuan P1 baru:
- mutasi global workspace policy selama replay dapat merusak operasi concurrent dan kehilangan perubahan izin;
- verifier artefak dapat membaca file di luar replay workspace melalui `expected_artifacts`.

Karena keduanya menyentuh isolasi dan authorization boundary, saya belum merekomendasikan Public Beta.

**Skor akhir independen: 73/100.** Skor ini mengakui kemajuan source code, tetapi menahan nilai karena race global dan path escape verifier belum ditutup, serta CI remote belum terbukti hijau.

## 9. Referensi
- Commit Siklus 8: https://github.com/yogijowo/aksa/commit/88024aa4f16384e347d6490192c3866bea40151e
- Compare Siklus 7 → 8: https://github.com/yogijowo/aksa/compare/1ab8cfcdfe97ffea316f940b03a07eb14674a377...88024aa4f16384e


---

## 10. Log Remediasi Teknis & Verifikasi Lokal (Post-Cycle 8)

Seluruh temuan **P1 (`P1-01`, `P1-02`)** dan **P2 (`P2-01`–`P2-03`)** serta butir audit singleton `sandbox_manager` (Gate 2 #5) pada laporan Siklus 8 ini telah diremediasi beserta pengujian adversarial di `services/engine/tests/test_reaudit_cycle8_remediation.py`:

| ID | Status Remediasi | Perubahan Kode Utama | Bukti Uji & Batasan |
| :--- | :--- | :--- | :--- |
| **`P1-01` & `P2-02`** | **Selesai & Terverifikasi** | `sandbox.py`, `registry.py`, `agent_learning.py`: menghapus seluruh mutasi singleton `sandbox_manager._workspaces` & `clear_all_workspaces()`; menambahkan isolasi `contextvars.ContextVar` per async task (`sandbox_manager.scoped(...)`), `ReplayExecutionContext`, `SandboxManager(..., frozen=True)`, dan `threading.RLock()` di `SandboxManager`. | `test_p2_01_and_p2_02_static_replay_isolation_invariants`, `test_p2_02_replay_context_sandbox_is_frozen_and_isolated`, `test_p1_01_replay_never_mutates_global_sandbox_and_runs_concurrently_without_race` (`PASSED`). |
| **`P1-02`** | **Selesai & Terverifikasi** | `agent_learning.py`, `orchestrator.py`, `routes.py`: memvalidasi seluruh `expected_artifacts`, `input_files`, dan argumen dengan `resolve_replay_path(..., allow_in_workspace_absolute=False)` (menolak traversal, absolute path, dan symlink) serta `run_artifacts` hasil tool sebelum verifier membuka file. Menambahkan batas ukuran file (25 MB), batas sel Excel/halaman PDF, penolakan symlink di verifier, timeout 10s, dan batas 20 fixture per request API. | `test_p1_02_replay_blocks_expected_artifacts_escape_and_never_opens_outside_file`, `test_p1_02_api_evaluate_candidate_blocks_fixture_path_escape`, `test_p1_02_verifier_rejects_symlinks_and_oversized_artifacts`, `test_p1_02_replay_rejects_escaped_run_artifacts_returned_by_tool` (`PASSED`). |
| **`P2-01`** | **Selesai & Terverifikasi** | `agent_learning.py`: menghapus parameter callback `tool_executor` dari `SkillEvaluator.replay_candidate_in_sandbox()` dan `SkillVersionService.evaluate_and_replay_candidate()`. | `test_p2_01_and_p2_02_static_replay_isolation_invariants` (`PASSED`). |
| **`P2-03`** | **Selesai & Terverifikasi** | `orchestrator.py`: menambahkan `_evaluate_basic_excel_formula()` (`SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, operasi aritmetika sel), penolakan token error rumus Excel (`#REF!`, `#DIV/0!`, dll.), verifikasi konsistensi nilai cache XML `<v>` vs kalkulasi rumus, serta pemeriksaan `expected_values` & `required_formula_functions`. | `test_p2_03_excel_verifier_evaluates_formulas_catches_errors_and_forged_caches` (`PASSED`, termasuk uji manipulasi XML `<v>9999</v>`). |
| **Gate 2 #5** | **Selesai & Terverifikasi** | `routes.py`: `DELETE /api/v1/workspaces/{workspace_id}` kini ikut menghapus policy terkait dari `sandbox_manager` di memori selain menghapus dari SQLite. | `test_gate2_delete_workspace_syncs_removal_from_sandbox_manager` (`PASSED`). |

### Catatan Kejujuran CI & Kesiapan
- **Verifikasi Lokal (Host macOS `darwin`):** Pytest **252 passed, 4 skipped** (`@win32_only` & `@linux_bwrap_only`), Cargo test **18 passed**, Vitest **9 passed**, `cargo check` bersih, `tsc --noEmit && vite build` bersih, `npm audit --omit=dev --audit-level=high` 0 kerentanan, dan `release_tooling.py smoke-test` lulus.
- **Belum Terverifikasi di Remote CI dari Sesi Lokal:** Karena perubahan ini belum di-push/dijalankan di runner remote GitHub Actions, bukti CI lintas-OS (`windows-latest` & `ubuntu-latest`) untuk 4 test OS nyata tersebut tetap ditandai sebagai **pending CI verification**.
