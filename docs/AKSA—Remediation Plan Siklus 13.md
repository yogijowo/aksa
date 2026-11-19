# AKSA — Remediation Plan Siklus 13

**Target:** Menindaklanjuti audit independen AKSA Siklus 13  
**Commit audit:** `9dfc4ef95e077645f4dc07edcda77a276fa6a9d8`  
**Repository:** `yogijowo/aksa`  
**Prioritas:** P1 dan P2  
**Tujuan:** Memperkuat reliabilitas worker sandbox, memastikan konsistensi build lintas platform, dan meningkatkan kesiapan AKSA menuju Public Beta.

---

## 1. Instruksi untuk AI Coding Agent

Bertindak sebagai:

- Senior Software Architect.
- Senior Python Systems Engineer.
- Rust/Tauri Desktop Engineer.
- Application Security Engineer.
- DevSecOps dan CI/CD Engineer.
- Independent QA Engineer.

Lakukan pekerjaan langsung pada folder project AKSA yang sedang terbuka.

### Aturan wajib

1. Audit source code aktual sebelum melakukan perubahan.
2. Jangan menganggap deskripsi audit atau dokumentasi sebagai bukti implementasi.
3. Jangan mengubah atau melemahkan mekanisme keamanan hanya agar test lulus.
4. Jangan menggunakan dummy executable untuk melewati validasi build.
5. Pertahankan kompatibilitas Windows, macOS, dan Linux.
6. Semua perubahan harus memiliki regression test.
7. Jangan menghapus test yang gagal untuk mendapatkan hasil hijau.
8. Jangan mengklaim test berhasil jika belum benar-benar dijalankan.
9. Perubahan harus mengikuti arsitektur dan konvensi project yang sudah ada.
10. Hindari refactoring besar yang tidak berhubungan dengan temuan audit.

---

# 2. P2 — Perbaiki Adaptive RLIMIT_NPROC Retry

## Masalah

File:

`services/engine/app/core/artifact_verifier_worker.py`

Fungsi yang relevan:

- `_estimate_current_uid_tasks()`
- `_resolve_worker_nproc_headroom()`
- `verify_artifact_in_worker()`

Implementasi saat ini menghitung jumlah task/thread UID melalui `/proc`.

Namun, ketika estimasi menghasilkan `None`, kode tidak menyetel `AKSA_VERIFIER_MAX_NPROC`.

Akibatnya, saat terjadi `EAGAIN` atau `pthread_create failed`, retry menaikkan variabel `headroom` tetapi tidak benar-benar meningkatkan batas NPROC.

Retry kedua akhirnya berpotensi menggunakan batas default yang sama.

## Target perbaikan

Mekanisme retry harus benar-benar meningkatkan batas NPROC pada setiap percobaan, termasuk ketika estimasi task UID tidak tersedia.

### Implementasi yang diharapkan

1. Buat mekanisme fallback yang deterministik.
2. Pastikan batas awal selalu positif dan tidak lebih rendah dari batas minimum yang ditetapkan.
3. Jika estimasi UID berhasil, gunakan jumlah task aktual ditambah headroom.
4. Jika estimasi UID gagal, gunakan fallback baseline yang eksplisit.
5. Pada retry setelah EAGAIN, hitung ulang batas berdasarkan nilai percobaan sebelumnya.
6. Pastikan batas tidak melebihi hard limit sistem.
7. Jangan mengandalkan perubahan variabel headroom saja. Pastikan environment yang dikirim ke worker benar-benar berubah.
8. Tambahkan logging yang cukup untuk mendiagnosis retry tanpa membocorkan informasi sensitif.

### Regression tests wajib

Buat test untuk skenario:

- Estimasi UID berhasil.
- Estimasi UID menghasilkan `None`.
- `/proc` tidak tersedia.
- `/proc` tidak dapat dibaca.
- Worker menghasilkan `pthread_create failed`.
- Worker menghasilkan `Resource temporarily unavailable`.
- Retry pertama gagal dan retry kedua berhasil.
- Retry kedua tetap gagal.
- Environment NPROC pada retry kedua benar-benar lebih tinggi.
- Batas NPROC tidak melampaui batas maksimum yang diperbolehkan.

### Kriteria penerimaan

- Tidak ada retry semu.
- Retry kedua benar-benar menggunakan nilai NPROC yang lebih tinggi.
- Tidak ada nilai NPROC nol.
- Jika fallback tidak dapat diterapkan, sistem harus gagal secara terkontrol dan memberikan telemetry yang jelas.
- Tidak ada regresi pada Linux, macOS, atau Windows.

---

# 3. P2 — Tambahkan Linux ke Release Workflow

## Masalah

File:

`.github/workflows/release.yml`

CI sudah menguji Linux, tetapi Release workflow belum menyediakan job distribusi Linux.

Saat ini target Release mencakup macOS dan Windows, sementara Linux belum menjadi bagian dari proses packaging.

## Target perbaikan

Jika Linux merupakan platform distribusi resmi AKSA, tambahkan pipeline release Linux secara menyeluruh.

### Hal yang harus diperiksa

1. Struktur matrix release yang sudah ada.
2. Target triple Linux yang digunakan oleh Tauri.
3. Konfigurasi `bundle.externalBin`.
4. Script `scripts/build_sidecar.py`.
5. Konfigurasi PyInstaller.
6. Dependency native Tauri Linux.
7. Proses signing dan packaging yang sudah tersedia.

### Pipeline Linux yang diharapkan

Urutan proses:

1. Checkout source.
2. Setup Python.
3. Setup Node.js.
4. Setup Rust.
5. Install dependency sistem Tauri Linux.
6. Install dependency Python.
7. Jalankan Python tests.
8. Jalankan mandatory Bubblewrap runtime tests.
9. Build PyInstaller sidecar untuk target Linux.
10. Verifikasi executable target triple.
11. Jalankan smoke test executable.
12. Install frontend dependencies.
13. Jalankan Vitest.
14. Jalankan TypeScript typecheck.
15. Jalankan Vite production build.
16. Jalankan Rust tests.
17. Jalankan Tauri build.
18. Generate CycloneDX SBOM.
19. Generate SHA-256 checksum.
20. Simpan artifact release.

### Kriteria penerimaan

- Linux sidecar dibangun secara native pada runner Linux.
- Binary tidak boleh berupa dummy executable.
- Target triple harus sesuai dengan arsitektur runner.
- Tauri packaging harus berhasil.
- SBOM dan checksum tersedia.
- Artifact release dapat diverifikasi.
- Kegagalan salah satu tahap harus menggagalkan pipeline.

Jika Linux belum menjadi target distribusi resmi, jangan memaksakan penambahan pipeline. Sebagai gantinya, dokumentasikan dengan jelas bahwa Linux hanya didukung untuk pengembangan atau pengujian.

---

# 4. P3 — Perkuat Validasi Binary Sidecar

## Masalah

File:

`scripts/release_tooling.py`

Fungsi:

`smoke_test_sidecar()`

Validasi saat ini memeriksa:

- File tersedia.
- File bukan symlink.
- File memiliki execute permission pada sistem Unix.
- Ukuran binary minimal 1 MB.
- Binary dapat menjalankan `--version`.
- Binary dapat menjalankan `--smoke-test`.

Ukuran file bukan bukti bahwa executable benar-benar binary native dengan format dan arsitektur yang sesuai.

## Target perbaikan

Tambahkan validasi format dan arsitektur executable.

### Validasi yang diharapkan

**Linux**
- Format ELF.
- Arsitektur sesuai target triple.
- Tidak menerima file teks atau script sebagai executable release.

**macOS**
- Format Mach-O.
- Arsitektur sesuai target triple.
- Mendukung target Apple Silicon dan target lain yang memang dinyatakan didukung.

**Windows**
- Format PE.
- Arsitektur sesuai target triple.
- Tidak menerima file teks atau script sebagai executable release.

### Ketentuan implementasi

1. Gunakan parser atau mekanisme pemeriksaan binary yang dapat dipercaya.
2. Hindari hanya mengandalkan ekstensi file.
3. Hindari pemeriksaan string sederhana yang mudah dipalsukan.
4. Pertahankan smoke test sebagai validasi perilaku.
5. Pisahkan validasi format binary dan validasi fungsi executable.

### Regression tests

- Binary ELF valid.
- Binary Mach-O valid.
- Binary PE valid.
- Binary dengan arsitektur salah.
- File teks yang diganti ekstensi executable.
- Script shell yang menyamar sebagai binary.
- File kosong.
- File terlalu kecil.
- Symlink.
- Executable yang valid tetapi gagal menjalankan smoke test.

---

# 5. P1 — Verifikasi Final Windows CI

Pada saat audit Siklus 13 ditutup, job Windows masih berjalan.

Jangan menganggap Windows sudah lulus hanya berdasarkan hasil Linux dan macOS.

### Wajib diverifikasi

- Python unit/integration/security tests.
- Native Windows AppContainer runtime tests.
- Sidecar module smoke test.
- PyInstaller native Windows build.
- Target-triple executable verification.
- Compiled sidecar smoke test.
- Vitest.
- TypeScript typecheck.
- Vite production build.
- Rust native tests.
- Tauri build validation.
- SBOM generation.

### Kriteria penerimaan

Semua tahapan wajib berhasil.

Jika ada tahapan yang dilewati, jelaskan apakah memang tidak berlaku untuk Windows atau merupakan kekurangan pipeline.

Jangan menganggap status `skipped` sebagai `success` tanpa memeriksa alasan dan kondisi workflow.

---

# 6. Audit Keamanan Setelah Perbaikan

Setelah seluruh perubahan selesai, lakukan pemeriksaan terhadap:

## Worker dan sandbox

- Isolasi filesystem.
- Pembatasan jaringan.
- Resource limits.
- Process creation guards.
- Timeout dan process termination.
- Output size limits.
- Symlink protection.
- Race condition.
- Fail-closed behavior.

## Sidecar

- Target triple.
- Binary integrity.
- Startup lifecycle.
- Runtime manifest.
- PID dan launch ID validation.
- HMAC handshake.
- Cleanup saat shutdown.
- Permission direktori runtime.

## Release

- SBOM completeness.
- SHA-256 checksum.
- Dependency audit.
- Binary target validation.
- Reproducibility dan provenance.
- Tidak ada secret yang ikut terpaket.

---

# 7. QA dan Pengujian

Jalankan test sesuai platform dan lingkungan yang tersedia.

Jangan mengubah test agar sekadar menghasilkan status hijau.

Buat laporan:

| Area | Hasil | Bukti |
|---|---|---|
| Python tests | | |
| NPROC fallback | | |
| Linux sandbox | | |
| macOS sandbox | | |
| Windows AppContainer | | |
| Sidecar Linux | | |
| Sidecar macOS | | |
| Sidecar Windows | | |
| Frontend tests | | |
| TypeScript | | |
| Rust tests | | |
| Tauri build | | |
| SBOM | | |
| Dependency audit | | |

Jika pengujian tidak dapat dijalankan, tulis `NOT VERIFIED`, bukan `PASS`.

---

# 8. Deliverables

Setelah pekerjaan selesai, hasilkan:

1. Implementasi perbaikan source code.
2. Regression tests baru.
3. Update CI workflow jika diperlukan.
4. Update dokumentasi teknis yang relevan.
5. Laporan perubahan.
6. Laporan test.
7. Daftar risiko yang belum terselesaikan.
8. Daftar file yang berubah.

Buat dokumen:

`docs/audits/AKSA-REMEDIATION-CYCLE-13.md`

Dokumen harus memuat:
- Temuan awal.
- Root cause.
- Perubahan implementasi.
- Test yang ditambahkan.
- Hasil pengujian.
- Bukti CI.
- Risiko residual.
- Status setiap temuan.

---

# 9. Aturan Penutupan Pekerjaan

Jangan berhenti setelah perubahan source selesai.

Pekerjaan hanya dianggap selesai jika:

- Implementasi sudah diperiksa.
- Regression tests tersedia.
- Test yang relevan berhasil.
- Tidak ada security regression.
- CI sudah diverifikasi.
- Dokumentasi diperbarui.

Berikan kesimpulan akhir dengan salah satu status:

- `FIXED AND VERIFIED`
- `FIXED — CI PENDING`
- `PARTIALLY FIXED`
- `NOT FIXED`
- `BLOCKED`

Jangan memberikan klaim keberhasilan yang tidak didukung bukti.

**Prioritas utama:** jangan melemahkan keamanan AKSA demi mempercepat kelulusan CI. Stabilitas, keamanan, dan kemampuan aplikasi yang benar-benar bekerja lebih penting daripada sekadar skor audit.
