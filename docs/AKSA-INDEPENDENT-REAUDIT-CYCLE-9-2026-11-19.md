# AKSA — Independent Re-Audit Siklus 9

**Tanggal:** 19 November 2026  
**Repository:** https://github.com/yogijowo/aksa  
**Commit yang diaudit:** `4e8600d57ab64d667f1716c9bd171374490d5e15`  
**Commit pembanding:** `88024aa4f16384e347d6490192c3866bea40151e`  
**Perbandingan:** https://github.com/yogijowo/aksa/compare/88024aa4f16384e347d6490192c3866bea40151e...4e8600d57ab64d667f1716c9bd171374490d5e15

## 1. Kesimpulan eksekutif

**Skor independen: 75/100**  
Siklus 8: **73/100** — naik **2 poin**.

Commit ini memperbaiki dua temuan P1 Siklus 8 pada source yang diperiksa:
- Replay tidak lagi mengosongkan dan memulihkan dictionary workspace singleton global.
- Path `expected_artifacts` dan artefak hasil tool kini divalidasi sebelum verifier membacanya.
- Parameter `tool_executor` yang dapat mengganti jalur eksekusi replay telah dihapus.

Namun, belum semua klaim hardening dapat diterima tanpa catatan. Saya menemukan dua kelemahan P2 pada verifier:
1. Batas ukuran 25 MB dapat ditimpa oleh `expected_schema.max_bytes` dari fixture/API.
2. Evaluasi formula Excel hanya menghitung subset formula. Formula yang tidak didukung dapat lolos dengan mengandalkan cached value yang tidak diverifikasi.

**Status rilis:**
- Internal Alpha: dapat dilanjutkan dengan pembatasan.
- Private Beta: layak untuk pengujian tertutup terbatas setelah perbaikan P2 atau dengan fixture/replay hanya dari sumber tepercaya.
- Public Beta: belum direkomendasikan.
- Production GA: belum siap.

Skor ini adalah penilaian engineering dari inspeksi source/diff dan bukti yang tersedia, bukan sertifikasi keamanan.

## 2. Ruang lingkup dan metode

Commit terbaru ditemukan melalui pencarian commit repository, kemudian dibandingkan langsung dengan commit Siklus 8. File yang diperiksa pada ref commit terbaru:
- `services/engine/app/core/sandbox.py`
- `services/engine/app/core/agent_learning.py`
- `services/engine/app/tools/registry.py`
- `services/engine/app/core/orchestrator.py`
- `services/engine/app/api/routes.py`
- `services/engine/tests/test_reaudit_cycle8_remediation.py`
- `.github/workflows/ci.yml`

Metode:
- Memeriksa diff commit dan source pada SHA yang sama.
- Menelusuri alur replay dari API, evaluator, sandbox context, registry, sampai verifier artefak.
- Memeriksa apakah test baru benar-benar menguji jalur yang diklaim.
- Memeriksa status CI remote.

**Batas verifikasi:** saya tidak menjalankan test suite atau binary OS pada runner audit ini. Klaim test lokal dalam `PROGRESS.md` diperlakukan sebagai klaim dokumentasi proyek, bukan hasil eksekusi independen. GitHub combined status mengembalikan `statuses: []` dan workflow runs yang tersedia juga kosong; status CI commit ini karenanya **belum terverifikasi**, bukan dinyatakan gagal.

## 3. Skor per domain

| Domain | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 80 | 15% |
| Fungsi inti | 77 | 15% |
| AI Agent & adaptive learning | 78 | 15% |
| Keamanan & isolasi | 72 | 20% |
| Privasi & kredensial | 72 | 10% |
| Desktop & integrasi OS | 68 | 10% |
| QA & pengujian | 75 | 10% |
| DevSecOps & release | 68 | 5% |
| **Total tertimbang** | **74.55 ≈ 75** | **100%** |

Kenaikan terutama berasal dari perbaikan isolasi replay dan validasi path. Skor belum naik lebih tinggi karena verifier masih memiliki kelemahan batas sumber daya dan validasi formula, sedangkan pengujian lintas-OS belum dibuktikan oleh CI remote.

## 4. Temuan Siklus 8 yang telah ditangani

### 4.1 P1 — Mutasi singleton workspace global saat replay

**Status: Remediasi terkonfirmasi pada source yang diperiksa.**

`agent_learning.py` kini membuat `ReplayExecutionContext` per replay dengan `SandboxManager` baru dan `frozen=True`. Replay menggunakan `sandbox_manager.scoped(replay_ctx.sandbox_manager)`.

Pada `sandbox.py`, `ContextVar` menyimpan manager yang berlaku untuk task saat ini. Pemanggilan method melalui singleton global akan diarahkan ke manager replay selama konteks aktif. Operasi perubahan workspace pada manager frozen ditolak. Operasi dictionary workspace juga menggunakan `RLock`.

Ini menghilangkan pola lama `clear_all_workspaces()` + snapshot restore yang dapat menghapus izin workspace milik request lain.

**Catatan batas:** ContextVar adalah isolasi konteks aplikasi, bukan isolasi proses/OS. Ia tidak menggantikan sandbox OS apabila suatu tool memiliki bug atau menjalankan kode yang tidak dipercaya.

### 4.2 P1 — Path `expected_artifacts` keluar dari workspace

**Status: Remediasi terkonfirmasi pada source yang diperiksa.**

`resolve_replay_path()` sekarang menolak:
- Path kosong dan null byte.
- UNC dan Alternate Data Stream.
- Komponen `..`.
- Absolute path untuk input/fixture yang tidak dipercaya.
- Target yang resolve ke luar workspace.
- Komponen symlink di dalam workspace.

`expected_artifacts` melewati `resolve_untrusted_path()` sebelum verifier dipanggil. Artefak yang dikembalikan tool juga melewati `resolve_tool_artifact()` dan containment check.

Saya juga memeriksa penolakan artefak symlink dan pengujian path escape yang ditambahkan.

### 4.3 P2 — Callback `tool_executor` sebagai jalur bypass

**Status: Remediasi terkonfirmasi.**

Parameter tersebut tidak lagi ada pada signature fungsi evaluator dan service. Replay menggunakan `tool_registry.execute_replay()`.

### 4.4 Workspace deletion synchronization

**Status: Perbaikan tampak diterapkan dan test regresi tersedia.**

Test baru memeriksa penghapusan workspace dari sandbox in-memory setelah endpoint DELETE. Ini menutup potensi izin workspace tertinggal setelah record database dihapus, dengan catatan test belum saya eksekusi sendiri.

## 5. Temuan baru

### P2-01 — `max_bytes` verifier dapat ditimpa oleh fixture

**Lokasi:** `services/engine/app/core/agent_learning.py`, sekitar blok pembentukan `bounded_schema` dan `_verify_bounded()`.

Kode saat ini:
```python
bounded_schema = dict(raw_schema) if isinstance(raw_schema, dict) else {}
bounded_schema.setdefault("max_bytes", replay_ctx.MAX_VERIFIER_FILE_BYTES)
```

`setdefault()` hanya mengisi nilai jika key belum ada. Karena `expected_schema` berasal dari fixture yang diterima API, pemanggil dapat memasukkan `max_bytes` lebih besar dari 25 MB. Nilai itu kemudian diteruskan ke `verify_artifact_postcondition()`.

Akibat:
- Batas 25 MB bukan batas maksimum yang dipaksakan server.
- Fixture dapat meminta verifier memproses artefak jauh lebih besar.
- Ini melemahkan mitigasi memory/CPU exhaustion yang baru ditambahkan.

**Rekomendasi:**
```python
requested_limit = bounded_schema.get("max_bytes", replay_ctx.MAX_VERIFIER_FILE_BYTES)
bounded_schema["max_bytes"] = min(
    max(1, int(requested_limit)),
    replay_ctx.MAX_VERIFIER_FILE_BYTES,
)
```
Lebih baik lagi, jangan izinkan fixture/API mengatur `max_bytes` sama sekali; jadikan konstanta kebijakan internal.

Tambahkan test API yang mengirim `max_bytes` sangat besar dan pastikan verifier tetap menolak file di atas batas server.

### P2-02 — Formula Excel yang tidak didukung dapat lolos dengan cached value

**Lokasi:** `services/engine/app/core/orchestrator.py`, sekitar pemanggilan `_evaluate_basic_excel_formula()` dan penentuan `effective_v`.

Verifier mencoba menghitung formula menggunakan evaluator terbatas. Jika evaluator mengembalikan `None` untuk formula yang tidak didukung, jalur saat ini tidak selalu menandai artefak gagal. Cached value dari workbook dapat tetap dipakai sebagai nilai efektif.

Artinya, formula di luar subset yang didukung—misalnya formula lookup/conditional tertentu—dapat memiliki cached value lama atau palsu yang tidak dibandingkan dengan hasil kalkulasi independen. Test baru membuktikan kasus `SUM`, tetapi belum membuktikan semua formula yang diterima aman diverifikasi.

**Rekomendasi:**
- Jika formula tidak didukung evaluator, tandai sebagai `unverified_formula` dan gagal untuk task yang mensyaratkan kebenaran formula.
- Jangan menganggap cached value sebagai bukti kalkulasi benar.
- Untuk formula yang harus diverifikasi, gunakan evaluator yang benar-benar kompatibel atau buka workbook melalui engine spreadsheet terisolasi.
- Tambahkan test cached value palsu untuk formula yang tidak didukung.

## 6. Catatan arsitektur dan hardening lanjutan

1. **Replay masih berjalan dalam proses Python yang sama.** ContextVar dan path jail melindungi jalur tool yang patuh pada sandbox manager, tetapi bukan batas keamanan OS. Untuk model ancaman yang memasukkan bug/kompromi pada handler, pertimbangkan worker proses terpisah dengan OS sandbox dan IPC terbatas.
2. **Timeout `asyncio.wait_for(asyncio.to_thread(...))` bukan penghentian thread.** Ketika timeout terjadi, coroutine dapat berhenti menunggu, tetapi pekerjaan thread yang sudah berjalan tidak otomatis dibatalkan. Gunakan worker process yang dapat dihentikan atau mekanisme parser dengan batas sumber daya nyata.
3. **Validasi ukuran harus dilakukan sebelum parser membuka file.** Selain byte size, pertimbangkan batas ukuran hasil dekompresi ZIP, jumlah entry, rasio kompresi, jumlah sheet, dimensi worksheet, dan kompleksitas PDF.
4. **API fixture perlu batas ukuran yang tegas.** Saat ini route membatasi jumlah fixture menjadi 20, tetapi schema yang diperiksa tidak menetapkan batas jumlah `expected_artifacts`, panjang `input_files`, ukuran tiap konten, atau total payload replay.
5. **CI lintas OS masih gate rilis.** Pastikan empat pengujian native Windows AppContainer dan Linux Bubblewrap benar-benar berjalan pada runner masing-masing, bukan hanya ter-skip pada macOS.

## 7. Prioritas perbaikan

| Prioritas | Tindakan | Kriteria selesai |
|---|---|---|
| P2-01 | Paksa `max_bytes` menjadi batas internal server | Fixture tidak bisa menaikkan limit; test API membuktikan |
| P2-02 | Gagalkan formula yang tidak dapat dievaluasi | Cached value formula unsupported tidak dapat meloloskan verifier |
| P2-03 | Ganti timeout thread dengan worker yang dapat dihentikan | Timeout benar-benar menghentikan pekerjaan parser |
| P2-04 | Batasi ukuran total fixture dan jumlah artefak | Request besar ditolak sebelum replay berjalan |
| Release gate | Verifikasi CI Windows/macOS/Linux | Run pada commit yang sama berstatus hijau dan artefak log tersedia |

## 8. Keputusan rilis

**Internal Alpha:** lanjut dengan batasan, khususnya replay hanya untuk skill dan fixture tepercaya.

**Private Beta:** dapat dilakukan secara terbatas setelah P2-01 ditutup atau endpoint evaluasi dibatasi untuk pengguna internal. P2-02 juga perlu ditutup sebelum hasil evaluasi Excel dipakai sebagai klaim kualitas yang kuat.

**Public Beta:** belum direkomendasikan sampai:
- Batas ukuran benar-benar tidak dapat dioverride.
- Formula unsupported tidak dianggap tervalidasi.
- CI native Windows dan Linux terverifikasi.
- Uji adversarial replay dan resource exhaustion lulus.

## 9. Referensi commit

- Commit Siklus 9: https://github.com/yogijowo/aksa/commit/4e8600d57ab64d667f1716c9bd171374490d5e15
- Compare Siklus 8 → 9: https://github.com/yogijowo/aksa/compare/88024aa4f16384e347d6490192c3866bea40151e...4e8600d57ab64d667f1716c9bd171374490d5e15


---

## 10. Log Remediasi Teknis & Verifikasi Lokal (Post-Cycle 9)

Seluruh temuan **P2 (`P2-01`–`P2-04`)** serta catatan hardening Bagian 6 dan CI verifiability pada laporan Siklus 9 telah diremediasi di kode sumber dan diuji dalam [`services/engine/tests/test_reaudit_cycle9_remediation.py`](file:///Users/lpsekudus/Project/aksa/services/engine/tests/test_reaudit_cycle9_remediation.py):

| ID | Status Remediasi | Perubahan Kode Utama | Bukti Uji & Verifikasi |
| :--- | :--- | :--- | :--- |
| **`P2-01`** | **Selesai & Terverifikasi** | `routes.py` menghapus `max_bytes` dari input `expected_schema`; `agent_learning.py` memaksa `bounded_schema["max_bytes"] = MAX_VERIFIER_FILE_BYTES`; `orchestrator.py` (`sanitize_verifier_schema`) mengunci batas di `[1, MAX_ARTIFACT_VERIFY_BYTES]`. | `test_p2_01_sanitize_verifier_schema_clamps_max_bytes_strictly` & `test_p2_01_api_ignores_large_max_bytes_override_and_rejects_oversize_artifact` (`PASSED`). |
| **`P2-02`** | **Selesai & Terverifikasi** | `orchestrator.py`: memperluas evaluator formula deterministik (`ROUND`, `ABS`, `COUNTA`, `PRODUCT`, nested expressions, AST aritmetika aman) sekaligus **menolak fail-closed** dengan `semantic_status="unverified_formula"` bila terdapat formula yang tidak didukung (`VLOOKUP`, `IF`, dll.) tanpa pernah mempercayai cached `<v>`. | `test_p2_02_unsupported_excel_formulas_reject_forged_or_unverified_cached_values` & `test_p2_02_extended_supported_formulas_evaluate_accurately` (`PASSED`). |
| **`P2-03`** | **Selesai & Terverifikasi** | `services/engine/app/core/artifact_verifier_worker.py` + `agent_learning.py`: memindahkan verifikasi artefak replay ke subprocess worker terpisah (`verify_artifact_in_worker`) dengan environment tersanitasi dan penghentian paksa (`os.killpg(..., SIGKILL)` / `proc.kill()`) saat timeout. | `test_p2_03_worker_subprocess_kills_stalled_parser_process` (`PASSED`, membuktikan PID child mati dengan `ProcessLookupError`). |
| **`P2-04`** | **Selesai & Terverifikasi** | `agent_learning.py` (`validate_replay_fixtures_budget`) + `routes.py`: membatasi raw request HTTP, maksimal `20` fixture, `10` `expected_artifacts`, `10` `input_files`, `256 KB` per file input, dan total payload replay `2 MB` sebelum eksekusi dimulai. | `test_p2_04_replay_budget_and_api_reject_oversized_fixtures` (`PASSED`). |
| **Bagian 6 #3** | **Selesai & Terverifikasi** | `orchestrator.py` (`_validate_office_zip_container`): memvalidasi rasio kompresi (`<= 50:1`), ukuran dekompresi (`<= 50 MB`), jumlah entry (`<= 2000`), path entry `..`, jumlah sheet (`<= 50`), dan dimensi `<dimension>` worksheet (`<= 250.000` sel) sebelum `openpyxl`/`python-docx`/`python-pptx` dibuka, plus batas teks PDF `5M` karakter. | `test_section6_office_zip_bomb_and_huge_sheet_dimension_rejected_before_openpyxl` (`PASSED`). |
| **CI Matrix (Gate 2)** | **Diperbarui pada Source; Menunggu Push CI Remote** | `.github/workflows/ci.yml` & `security.yml`: dipicu pada `push` dan `workflow_dispatch`, mengekspor JUnit XML + `$GITHUB_STEP_SUMMARY`, dan menggagalkan workflow jika test native `@win32_only` / `@linux_bwrap_only` berstatus skipped pada runner Windows/Linux. | Siap diverifikasi langsung pada check runs GitHub Actions begitu commit di-push. |

### Catatan Kejujuran CI & Status Kesiapan
- **Verifikasi Lokal Pasca-Edit (macOS `darwin`):** Pytest **259 passed, 4 skipped** (`@win32_only` / `@linux_bwrap_only`), Cargo **18 passed**, Vitest **9 passed**, `cargo check` bersih, `tsc --noEmit && vite build` bersih, `npm audit --omit=dev --audit-level=high` **0 vulnerabilities**, dan `release_tooling.py smoke-test` lulus.
- **Agar Auditor Eksternal Memperoleh Bukti CI Tanpa Bergantung `PROGRESS.md`:** Setelah perubahan ini di-commit & di-push ke GitHub, workflow `.github/workflows/ci.yml` dan `.github/workflows/security.yml` akan otomatis berjalan pada SHA commit terbaru dan menulis ringkasan JUnit/hasil test lintas-OS ke GitHub Actions Summary & Check Runs.
