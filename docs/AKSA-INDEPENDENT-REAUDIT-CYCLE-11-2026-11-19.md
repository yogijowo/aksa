# AKSA — Independent Re-Audit Siklus 11
**Tanggal:** 19 November 2026  
**Repository:** `yogijowo/aksa`  
**Branch:** `main`  
**Commit diaudit:** `52ffe4e470fbffe566f68bddf02f9f2b36d71d1a`  
**Pembanding:** `a0a3695821ab1a1cdbab51bafed64770cf8ae01f`

## 1. Kesimpulan independen

**Skor: 76/100** (Siklus 10: 77/100).

Perubahan Siklus 11 arahnya benar: verifier dipindahkan ke worker yang berjalan melalui OS sandbox dengan workspace read-only, dan stdout/stderr kini dibaca secara streaming dengan batas keras. Dua temuan P2 sebelumnya ditangani secara substantif.

Namun, implementasi resource limit baru menimbulkan regresi nyata di Linux CI. Karena verifier dipakai pada alur replay dan pemeriksaan artefak, regresi ini memengaruhi fungsi inti.

**Status rilis:**
- Internal Alpha: lanjutkan hanya untuk pengujian terbatas setelah regresi Linux diperbaiki.
- Private Beta: belum layak diperluas; batasi pengguna, file, dan aktivitas berisiko.
- Public Beta: **belum direkomendasikan**.
- Production GA: belum siap.

## 2. Perubahan yang diperiksa

File penting yang diperiksa pada SHA terbaru:
- `services/engine/app/core/artifact_verifier.py`
- `services/engine/app/core/artifact_verifier_worker.py`
- `services/engine/app/skills/os_sandbox.py`
- `services/engine/app/skills/windows_sandbox.py`
- `services/engine/app/skills/skill_manager.py`
- `services/engine/tests/test_reaudit_cycle10_remediation.py`
- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `.github/workflows/release.yml`

Audit memeriksa source pada SHA tersebut, bukan mengandalkan README, badge, catatan progress, atau klaim hasil tes lokal.

## 3. Verifikasi perbaikan Siklus 10

### P2-01 — Worker verifier kini didelegasikan ke OS sandbox
**Status: secara desain diperbaiki; bukti runtime lintas-OS belum lengkap.**

Terkonfirmasi di source:
- `verify_artifact_in_worker()` memanggil `execute_in_os_sandbox()`.
- `read_only_workspace=True` diteruskan.
- stdout dan stderr memiliki hard limit.
- worker memakai modul verifier terpisah `app.core.artifact_verifier`.
- environment worker disaring dan HOME/TMPDIR diarahkan ke workspace.
- profil Seatbelt dan Bubblewrap mengunci workspace read-only; Windows memakai AppContainer dan Job Object.
- pembacaan artefak memakai `O_NOFOLLOW`, `os.fstat()`, dan pemeriksaan file reguler.

Pemanggilan OS sandbox di source membuktikan integrasi, tetapi bukan bukti semua mekanisme kernel bekerja benar pada setiap OS. Windows job masih berjalan ketika pemeriksaan terakhir dilakukan.

### P2-02 — Streaming stdout/stderr dengan hard cap
**Status: perbaikan source terkonfirmasi.**

- POSIX memakai pembaca chunked, bukan `proc.communicate()`.
- stdout dan stderr dihitung saat dibaca.
- proses tree dihentikan ketika batas terlampaui.
- stderr yang dipertahankan untuk diagnostik dibatasi terpisah.
- Windows memakai thread pembaca pipe dan `TerminateJobObject()` ketika melewati batas.

Ini mengatasi masalah buffering penuh sebelum batas diperiksa yang ditemukan pada Siklus 10.

## 4. Temuan baru

### P1-01 — `RLIMIT_NPROC=0` mematikan kebutuhan thread dependency verifier di Linux
**Lokasi:** `services/engine/app/core/artifact_verifier_worker.py`, fungsi `_apply_worker_resource_limits()`.

Kode menetapkan `RLIMIT_NPROC` ke `0`. Log Ubuntu menunjukkan OpenBLAS gagal membuat thread:
- `pthread_create failed`
- `RLIMIT_NPROC 0 current, 0 max`
- worker keluar dengan exit code `130`

Dampak yang teramati:
- test verifier artefak Excel gagal;
- beberapa test replay skill dari Siklus 6, 7, dan 8 ikut gagal karena artefak XLSX tidak dapat diverifikasi;
- suite Security juga gagal pada replay yang sama.

Ini bukan sekadar masalah runner. Kegagalan terjadi setelah pytest berjalan dan traceback menunjuk langsung ke worker verifier di bawah sandbox.

**Rekomendasi:**
1. Jangan menetapkan `RLIMIT_NPROC=0` untuk worker yang memuat dependency native yang mungkin membuat thread.
2. Gunakan batas proses/thread positif yang kecil dan terukur, lalu uji batas tersebut di Linux.
3. Tambahkan pengujian worker dengan dependency native/threaded yang benar-benar dipakai parser.
4. Pastikan batas resource tetap membatasi fork/process abuse tanpa mematikan operasi normal.
5. Jalankan ulang semua test replay lama, bukan hanya test baru Siklus 10.

### P2-01 — macOS CI memiliki satu kegagalan database pada instalasi curated skill
**Test:** `tests/test_audit_remediation_2026_11_18.py::test_curated_skill_manifest_synchrony_with_scripts`.

Hasil macOS:
- 266 passed
- 4 skipped
- 1 failed

Kegagalan terjadi saat `install_curated_skill()` memanggil `db_manager.upsert_installed_skill()` dan SQLite mengembalikan `unable to open database file`.

Belum ada bukti cukup untuk menyimpulkan ini disebabkan perubahan sandbox Siklus 11. Perlakukan ini sebagai kegagalan CI yang belum dijelaskan, bukan langsung sebagai regresi sandbox.

**Rekomendasi:**
- periksa `settings.db_path` dan pembuatan direktori induknya pada fixture CI macOS;
- pastikan parent directory dibuat sebelum koneksi SQLite;
- pastikan test memakai database sementara yang unik dan terisolasi;
- rerun test tersebut secara terpisah pada macOS.

### P2-02 — Pemeriksaan symlink komponen masih memiliki celah TOCTOU
**Lokasi:** `services/engine/app/core/artifact_verifier.py`, `check_no_symlink_components()` dan `_read_verified_regular_file()`.

Kode memeriksa komponen path, lalu membuka path menggunakan `O_NOFOLLOW`. `O_NOFOLLOW` melindungi komponen terakhir, tetapi tidak otomatis mencegah komponen direktori perantara diganti menjadi symlink di antara pemeriksaan dan `os.open()`.

Workspace read-only di dalam sandbox mengurangi kemampuan worker mengubahnya, tetapi tidak sepenuhnya mencegah proses host yang memiliki akses tulis ke direktori sumber mengganti komponen path secara bersamaan.

**Rekomendasi:**
- gunakan pembukaan berbasis directory file descriptor (`openat` berantai dengan `O_DIRECTORY | O_NOFOLLOW`) atau mekanisme setara;
- pada Linux, pertimbangkan `openat2()` dengan `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS`;
- jangan menganggap `Path.is_symlink()` sebelum `open()` sebagai perlindungan TOCTOU yang atomik;
- tambahkan test race yang mengganti direktori perantara saat verifier membuka file.

## 5. Bukti CI pada commit yang diaudit

### CI Matrix
Run: https://github.com/yogijowo/aksa/actions/runs/44474524990

Pada saat pemeriksaan:
- Ubuntu: **failed** — 258 passed, 8 skipped, 5 failed.
- macOS: **failed** — 266 passed, 4 skipped, 1 failed.
- Windows: masih **in progress** saat pemeriksaan terakhir; belum boleh dianggap lulus.

Kegagalan Ubuntu paling penting adalah `RLIMIT_NPROC=0`, yang menyebabkan OpenBLAS gagal membuat thread pada verifier worker dan beberapa replay test gagal.

### Security Regression
Run: https://github.com/yogijowo/aksa/actions/runs/44474524967

Status: **failed**. Log menunjukkan replay artefak XLSX gagal dengan akar masalah OpenBLAS / `RLIMIT_NPROC=0`.

### Batas verifikasi
- Source diperiksa pada commit yang tepat dan log GitHub Actions dibaca.
- Test suite tidak dijalankan ulang secara lokal dalam sesi audit ini.
- Klaim 267 pytest passed, 18 Cargo passed, 9 Vitest passed, dan build lokal berasal dari catatan repository; klaim tersebut tidak dianggap sebagai eksekusi independen.
- Test native yang dilewati pada macOS bukan bukti keberhasilan runtime Linux/Windows.

## 6. Skor independen

| Area | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 81 | 15% |
| Fungsi inti | 78 | 15% |
| AI agent & adaptive learning | 79 | 15% |
| Keamanan & isolasi | 80 | 20% |
| Privasi & kredensial | 73 | 10% |
| Integrasi desktop & OS | 70 | 10% |
| QA & testing | 66 | 10% |
| DevSecOps & release | 63 | 5% |
| **Total tertimbang** | **76/100** | **100%** |

Skor turun satu poin karena kualitas isolasi verifier dan streaming membaik, tetapi regresi runtime Linux memengaruhi verifier/replay, macOS CI masih gagal, dan bukti Windows belum tersedia.

## 7. Prioritas perbaikan berikutnya

1. **P1:** ganti `RLIMIT_NPROC=0` dengan strategi pembatasan proses/thread yang kompatibel dengan dependency parser.
2. **P1:** jalankan ulang seluruh verifier dan replay tests di Ubuntu; pastikan tidak ada kegagalan OpenBLAS.
3. **P2:** selesaikan kegagalan SQLite pada macOS CI dan buktikan test curated skill lulus.
4. **P2:** tutup TOCTOU komponen direktori dengan file-descriptor-based path resolution.
5. **P1 gate rilis:** tunggu hasil Windows AppContainer; pastikan test runtime wajib tidak skipped.
6. Setelah semua hijau, lakukan audit ulang pada commit baru sebelum menaikkan status ke Public Beta.

## 8. Referensi

- Commit: https://github.com/yogijowo/aksa/commit/52ffe4e470fbffe566f68bddf02f9f2b36d71d1a
- Compare: https://github.com/yogijowo/aksa/compare/a0a3695821ab1a1cdbab51bafed64770cf8ae01f...52ffe4e470fbffe566f68bddf02f9f2b36d71d1a
- CI Matrix: https://github.com/yogijowo/aksa/actions/runs/44474524990
- Security: https://github.com/yogijowo/aksa/actions/runs/44474524967
