# AKSA — Independent Re-Audit Siklus 12
**Tanggal:** 19 November 2026  
**Repository:** `yogijowo/aksa` · `main`  
**Commit:** `b3a8be90f439f50d7f372b168d0044ff53d7f38c`  
**Pembanding:** `52ffe4e470fbffe566f68bddf02f9f2b36d71d1a`

## 1. Kesimpulan

**Skor independen: 77/100**  
Siklus 11: 76/100 → Siklus 12: 77/100.

Perbaikan Siklus 11 secara substansial terkonfirmasi di source:
- regresi OpenBLAS akibat `RLIMIT_NPROC=0` diperbaiki;
- inisialisasi database kini membuat parent directory dan schema sebelum operasi;
- pembukaan artefak POSIX menggunakan chained `dir_fd` + `O_NOFOLLOW` pada setiap komponen, menutup celah symlink TOCTOU yang ditemukan sebelumnya.

Bukti CI jauh lebih baik untuk Python dan keamanan: pytest macOS lulus; pytest Ubuntu dan gate runtime Bubblewrap lulus; Security workflow lulus. Akan tetapi, CI matrix masih gagal pada tahap Rust native tests di macOS dan Ubuntu karena binary sidecar Tauri tidak tersedia. Windows masih berjalan pada saat audit ditutup. Dengan demikian, perbaikan keamanan sudah lebih meyakinkan, tetapi validasi desktop lintas-platform belum lengkap.

**Status rilis:** Internal Alpha dapat dilanjutkan; Private Beta tetap terbatas. Public Beta belum direkomendasikan sampai sidecar build diperbaiki dan ketiga runner CI selesai hijau.

## 2. Perubahan yang diperiksa

Commit `b3a8be90...` adalah satu commit di atas commit Siklus 11. Perubahan utama:
- `artifact_verifier_worker.py`
- `artifact_verifier.py`
- `app/db/models.py`
- `test_reaudit_cycle11_remediation.py`
- `.github/workflows/ci.yml`
- README, PROGRESS, dan laporan Siklus 11.

Dokumentasi dan klaim hasil tes lokal diperlakukan sebagai klaim pengembang, bukan bukti independen. Penilaian menggunakan source pada commit ini dan log Actions yang benar-benar tersedia.

## 3. Verifikasi temuan Siklus 11

### P1-01 — `RLIMIT_NPROC=0` / OpenBLAS
**Status: diperbaiki pada source dan didukung CI Linux.**

Source sekarang:
- tidak lagi menetapkan `RLIMIT_NPROC=0`;
- menetapkan batas positif;
- membatasi OpenBLAS/OMP/MKL/BLIS/NumExpr ke satu thread;
- membatasi address space ke 768 MiB;
- menambahkan guard Python untuk mencegah subprocess/fork dari worker;
- mempertahankan `RLIMIT_FSIZE=0`, CPU dan NOFILE limits.

Bukti runtime CI Ubuntu:
- seluruh pytest lulus;
- native Bubblewrap gate yang memaksa test tidak boleh skip lulus;
- test XLSX replay end-to-end termasuk dalam gate wajib.

Catatan residual: batas `RLIMIT_NPROC` dihitung dari snapshot jumlah task UID ditambah headroom 32. Ini jauh lebih baik daripada nol, tetapi masih berupa estimasi yang dapat kedaluwarsa jika beban proses host meningkat tajam di antara penghitungan dan pembuatan thread. Pertimbangkan headroom adaptif/konfigurasi serta telemetry kegagalan `EAGAIN`.

### P2-01 — SQLite parent directory
**Status: perbaikan source dan CI macOS terkonfirmasi.**

`DatabaseManager.ensure_ready()` membuat direktori induk dan memastikan schema tersedia sebelum operasi yang memerlukannya. Test yang relevan menggunakan `tmp_path`. Seluruh pytest pada macOS lulus, termasuk test yang sebelumnya gagal `unable to open database file`.

### P2-02 — Symlink TOCTOU pada path artefak
**Status: perbaikan POSIX source terkonfirmasi dan test regresi ditambahkan.**

`_open_verified_regular_fd()`:
- membuka anchor directory;
- membuka tiap komponen direktori melalui `dir_fd` dengan `O_DIRECTORY | O_NOFOLLOW`;
- membuka leaf dengan `O_NOFOLLOW`;
- memvalidasi descriptor melalui `fstat()` sebelum membaca.

Ini menghindari pola rentan “cek path lalu buka path” untuk POSIX. Test deterministik swap symlink dan stress test concurrent swap ditambahkan. Windows memakai handle final-path verification setelah open, tetapi mekanisme Windows berbeda dari jaminan chained dir_fd POSIX dan tetap perlu bukti runtime AppContainer pada runner Windows.

## 4. Temuan baru — P1 release/CI

### P1-01 — CI tidak membangun sidecar sebelum Cargo/Tauri test
**Lokasi:** `.github/workflows/ci.yml`, `scripts/build_sidecar.py`, `apps/desktop/src-tauri/tauri.conf.json`.

Workflow hanya menjalankan:
`python scripts/build_sidecar.py --dry-run`

Namun `tauri.conf.json` mendeklarasikan `bundle.externalBin: ["binaries/aksa-engine"]`. Saat `cargo test` menjalankan `tauri_build::build()`, Tauri mencari binary target-spesifik:
- macOS: `binaries/aksa-engine-aarch64-apple-darwin`
- Ubuntu: `binaries/aksa-engine-x86_64-unknown-linux-gnu`

Kedua file tidak ada, sehingga build script Tauri gagal. Log macOS dan Ubuntu menyatakan secara eksplisit `resource path ... doesn't exist`. Akibatnya `cargo test` gagal dan `cargo check` serta SBOM step setelahnya ter-skip.

Ini bukan kegagalan Rust test assertion; test belum dapat melewati validasi resource Tauri. Tetapi tetap merupakan blocker nyata: CI tidak memvalidasi desktop shell secara penuh dan pipeline packaging belum reproducible pada clean runner.

**Rekomendasi:**
1. Tambahkan langkah build sidecar sungguhan sebelum Cargo, bukan `--dry-run`.
2. Pastikan PyInstaller tersedia dan dependencies produksi lengkap pada runner.
3. Alternatif untuk unit test Rust: pisahkan library test dari bundle build dengan konfigurasi Tauri test yang benar-benar tidak mensyaratkan externalBin; jangan membuat dummy binary kosong yang dapat menyamarkan masalah packaging.
4. Tambahkan pemeriksaan eksplisit bahwa file sidecar target triple benar-benar ada dan executable sebelum `cargo test`/bundle.
5. Jalankan ulang matrix pada Windows, macOS, dan Ubuntu; pastikan langkah `cargo test`, `cargo check`, dan packaging berjalan.

## 5. Bukti CI

Commit yang diuji: `b3a8be90f439f50d7f372b168d0044ff53d7f38c`.

### CI Matrix
Run: https://github.com/yogijowo/aksa/actions/runs/44477126634

Pada pemeriksaan terakhir:
- **macOS:** pytest lulus; smoke test, sidecar dry-run, npm audit, Vitest, dan Vite build lulus. `cargo test` gagal karena binary sidecar target triple tidak ada.
- **Ubuntu:** pytest lulus; native Bubblewrap runtime gate lulus; smoke test, sidecar dry-run, npm audit, Vitest, dan Vite build lulus. `cargo test` gagal karena binary sidecar target triple tidak ada.
- **Windows:** masih `in_progress` saat audit ditutup; belum dapat diberi status lulus/gagal.

### Security Regression
Run: https://github.com/yogijowo/aksa/actions/runs/44477126715  
Status: **success**. Seluruh langkah regression/security dan audit dependency yang diwajibkan workflow selesai sukses.

### Batas bukti
- Saya memeriksa source dan log Actions pada commit yang tepat.
- Saya tidak menjalankan ulang test suite secara lokal.
- Angka local pytest/Cargo/Vitest yang tercantum dalam README/PROGRESS tidak saya klaim sebagai eksekusi independen.
- Keberhasilan pytest Ubuntu dan macOS adalah bukti remote CI; native Windows belum terkonfirmasi.

## 6. Skor independen

| Area | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 81 | 15% |
| Fungsi inti | 79 | 15% |
| AI agent & adaptive learning | 79 | 15% |
| Keamanan & isolasi | 82 | 20% |
| Privasi & kredensial | 73 | 10% |
| Integrasi desktop & OS | 70 | 10% |
| QA & testing | 70 | 10% |
| DevSecOps & release | 66 | 5% |
| **Total tertimbang** | **77/100** | **100%** |

Kenaikan satu poin mencerminkan penutupan tiga temuan Siklus 11 dan keberhasilan Python/security CI pada macOS/Linux. Nilai tetap tertahan oleh kegagalan integrasi sidecar/Tauri dan bukti Windows yang belum selesai.

## 7. Prioritas selanjutnya

1. **P1:** perbaiki urutan CI agar sidecar benar-benar dibangun atau strategi test Tauri dipisahkan dengan benar.
2. **P1:** tunggu dan evaluasi hasil Windows CI, terutama AppContainer, handle inheritance, XLSX replay, Cargo, dan Tauri build.
3. **P1 gate rilis:** ulangi seluruh CI matrix pada commit setelah perbaikan; semua job harus hijau.
4. **P2:** evaluasi headroom `RLIMIT_NPROC` untuk kondisi host dengan beban tinggi.
5. Setelah matrix hijau, lakukan audit independen Siklus 13 sebelum mempertimbangkan Public Beta.

## 8. Referensi
- Commit: https://github.com/yogijowo/aksa/commit/b3a8be90f439f50d7f372b168d0044ff53d7f38c
- Compare: https://github.com/yogijowo/aksa/compare/52ffe4e470fbffe566f68bddf02f9f2b36d71d1a...b3a8be90f439f50d7f372b168d0044ff53d7f38c
- CI Matrix: https://github.com/yogijowo/aksa/actions/runs/44477126634
- Security: https://github.com/yogijowo/aksa/actions/runs/44477126715
