# AKSA — Independent Re-Audit Siklus 10

Tanggal: 19 November 2026  
Repository: https://github.com/yogijowo/aksa  
Commit diaudit: `a0a3695821ab1a1cdbab51bafed64770cf8ae01f`  
Pembanding: `4e8600d57ab64d667f1716c9bd171374490d5e15`  
Compare: https://github.com/yogijowo/aksa/compare/4e8600d57ab64d667f1716c9bd171374490d5e15...a0a3695821ab1a1cdbab51bafed64770cf8ae01f

## 1. Kesimpulan

**Skor independen: 77/100** (Siklus 9: 75/100, naik 2 poin).

Dua commit baru menutup temuan P2 Siklus 9 pada source yang diperiksa dan memperkeras Linux Bubblewrap setelah write leak ditemukan pada pengujian native. Tidak ditemukan P1 baru pada area yang diperiksa.

Dua catatan P2 tersisa:
1. Verifier worker dapat dihentikan, tetapi belum menjadi sandbox OS terpisah; ia berjalan sebagai subprocess dengan hak akses user yang sama.
2. Batas output worker baru diperiksa setelah `communicate()` mengumpulkan stdout/stderr. Ini bukan pembatasan memori saat proses berjalan.

**CI utama belum hijau.** Workflow matrix dijalankan pada SHA ini, tetapi ketiga job berhenti di `Set up job`; langkah checkout, build, dan test tidak berjalan. Ini tampak sebagai kegagalan provisioning/runner, bukan bukti test aplikasi gagal. Workflow Security terpisah berhasil.

Status rilis:
- Internal Alpha: dapat dilanjutkan dengan batasan.
- Private Beta: pengujian tertutup terbatas.
- Public Beta: belum direkomendasikan sampai CI lintas OS benar-benar dieksekusi dan P2 verifier ditangani atau risikonya diterima secara eksplisit.
- Production GA: belum siap.

## 2. Ruang lingkup

Source diperiksa pada SHA yang diaudit:
- `services/engine/app/skills/os_sandbox.py`
- `services/engine/app/core/agent_learning.py`
- `services/engine/app/core/artifact_verifier_worker.py`
- `services/engine/app/core/orchestrator.py`
- `services/engine/app/api/routes.py`
- `services/engine/tests/test_reaudit_cycle9_remediation.py`
- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`

Dua commit setelah Siklus 9:
- `f2825925186b0d9f69f2c55bf21210a751a5b0b9` — remediasi P2 Siklus 9 dan penguatan CI.
- `a0a3695821ab1a1cdbab51bafed64770cf8ae01f` — perbaikan write leak Linux Bubblewrap.

Inspeksi source/diff dan metadata CI dilakukan independen. Test suite tidak dijalankan ulang pada mesin audit ini; hasil lokal yang tercantum di dokumentasi proyek tidak saya klaim sebagai eksekusi independen.

## 3. Skor per domain

| Domain | Skor | Bobot |
|---|---:|---:|
| Arsitektur & modularitas | 81 | 15% |
| Fungsi inti | 80 | 15% |
| AI Agent & adaptive learning | 80 | 15% |
| Keamanan & isolasi | 75 | 20% |
| Privasi & kredensial | 73 | 10% |
| Desktop & integrasi OS | 70 | 10% |
| QA & pengujian | 77 | 10% |
| DevSecOps & release | 68 | 5% |
| **Total tertimbang** | **76.5 ≈ 77** | **100%** |

Kenaikan berasal dari perbaikan verifier, pembatasan input, dan penguatan Bubblewrap. DevSecOps belum naik karena matrix CI utama belum mencapai tahap pengujian.

## 4. Remediasi Siklus 9 yang terkonfirmasi

### P2-01 — Batas ukuran artefak tidak dapat dioverride
**Status: ditangani pada source yang diperiksa.**
- API membuang `expected_schema.max_bytes` dari caller.
- Replay menetapkan `bounded_schema["max_bytes"]` ke batas internal server.
- `sanitize_verifier_schema()` membatasi nilai ke rentang yang diizinkan.
- Test baru mengirim nilai sangat besar dan menguji penolakan artefak di atas batas.

### P2-02 — Formula Excel unsupported tidak lagi dipercaya dari cache
**Status: ditangani pada source yang diperiksa.**

Evaluator memperluas dukungan formula deterministik seperti `SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, `COUNTA`, `PRODUCT`, `ABS`, `ROUND`, dan aritmetika terbatas. Formula yang tidak dapat dihitung secara independen ditandai `unverified_formula` dan verifikasi gagal. Cached value tidak digunakan sebagai bukti kebenaran formula. Test memasukkan cached value palsu untuk formula `VLOOKUP` dan mengharapkan fail-closed.

Evaluator tetap merupakan subset Excel, bukan mesin kalkulasi Excel penuh. Formula di luar subset harus tetap gagal secara aman.

### P2-03 — Timeout verifier dapat menghentikan proses
**Status: perbaikan timeout terkonfirmasi; isolasi keamanan masih terbatas.**

`artifact_verifier_worker.py` menjalankan parser pada child process. Pada Unix, worker dibuat dalam session tersendiri dan timeout memicu `SIGKILL` pada process group. Ini mengatasi thread `asyncio.to_thread` yang tidak dapat dihentikan.

Namun, proses tersebut belum dijalankan dalam AppContainer, Bubblewrap, atau Seatbelt. Jadi ini adalah **killable subprocess**, bukan OS security sandbox. Worker tetap memiliki hak akses user yang menjalankan AKSA.

### P2-04 — Batas payload replay
**Status: ditangani pada source yang diperiksa.**

Batas service:
- Maksimal 20 fixture.
- Maksimal 10 expected artifacts per fixture.
- Maksimal 10 input files per fixture.
- Maksimal 256 KB per input file.
- Maksimal 2 MB total payload replay.

API juga memeriksa ukuran raw request dan memvalidasi budget sebelum replay.

### Office ZIP pre-parser guard
**Status: peningkatan nyata.**

Sebelum parser Office dipanggil, validator memeriksa ZIP valid, maksimal 2.000 entry, path traversal, maksimal 50 MB dekompresi, compression ratio maksimal 50:1, maksimal 50 sheet Excel, dimensi worksheet maksimal 250.000 sel, dan ekstraksi teks PDF dibatasi. Ini mengurangi risiko ZIP bomb dan dokumen Office yang sangat kompleks. Tetap perlu fuzzing parser dengan file malformed/adversarial.

## 5. Perbaikan Linux Bubblewrap

**Status: source menunjukkan perbaikan yang masuk akal; native runtime belum terkonfirmasi berhasil.**

`build_linux_bwrap_args()` menghapus `--tmpfs /tmp`, memasang workspace dengan `--bind`, mengunci root container dengan `--remount-ro /`, lalu mengarahkan `TMPDIR` ke workspace. Urutan ini dimaksudkan agar workspace tetap writable sementara root dan direktori sementara lain tidak menjadi jalur tulis di luar workspace.

Test native Linux ditambah untuk membuktikan workspace tetap writable, sedangkan network dan penulisan di luar workspace ditolak.

## 6. CI remote — hasil aktual

### CI — Multi-Platform Verification Matrix
Run: https://github.com/yogijowo/aksa/actions/runs/44471418108

Hasil:
- macOS: `failure`
- Windows: `failure`
- Ubuntu: `failure`

Ketiga job hanya menunjukkan langkah `Set up job` yang gagal. Tidak ada checkout, instalasi dependency, pytest, atau test native yang berjalan. Jadi ini **bukan bukti test aplikasi gagal**, tetapi juga bukan bukti CI hijau.

### Security — Dependency Audit, Secret Scan & SAST
Run: https://github.com/yogijowo/aksa/actions/runs/44471418100

Hasil: **success**. Workflow ini berhasil menyelesaikan security regression suite dan audit dependency sesuai konfigurasi workflow.

### Keputusan CI
Matrix lintas OS belum verified. Jalankan ulang workflow ketika runner tersedia. Periksa JUnit summary pada SHA yang sama atau commit penerus. Dua test Bubblewrap Ubuntu dan dua test AppContainer Windows harus benar-benar `passed`, bukan skipped.

## 7. Temuan baru

### P2-01 — Verifier worker killable tetapi belum diisolasi oleh OS
**Lokasi:** `services/engine/app/core/artifact_verifier_worker.py`.

Worker dibuat dengan `asyncio.create_subprocess_exec()` dan environment yang disaring, tetapi tidak memakai OS sandbox. Ia tetap berjalan sebagai user yang sama, dengan akses filesystem dan kemampuan proses yang dimiliki user tersebut.

Dampak: jika parser native atau library dokumen memiliki vulnerability yang dapat dieksploitasi melalui file berbahaya, kompromi worker tidak otomatis terkurung pada workspace. Pemisahan proses dan timeout melindungi availability, bukan containment eksploitasi parser.

Konteks risiko: jalur replay yang diperiksa menggunakan temporary workspace dan tool allowlist, sehingga ini bukan bukti eksploit jarak jauh langsung. Namun, jangan menyebut worker ini sebagai sandbox keamanan.

Rekomendasi:
- Jalankan verifier di bawah OS sandbox yang sama ketatnya dengan skill worker, dengan workspace read-only dan tanpa network.
- Berikan akses hanya ke artefak dan dependency runtime yang dibutuhkan.
- Terapkan batas CPU, memory, file size, dan process count jika platform mendukung.
- Jika OS sandbox belum tersedia, dokumentasikan worker sebagai proses isolasi availability saja dan batasi sumber/format artefak.

### P2-02 — Batas stdout/stderr diperiksa setelah buffer terkumpul
**Lokasi:** `artifact_verifier_worker.py`, fungsi `verify_artifact_in_worker()`.

Kode memanggil `proc.communicate()` terlebih dahulu, baru memeriksa `len(stdout_b) > MAX_WORKER_STDOUT_BYTES`. `stderr` juga ditangkap penuh, tanpa batas eksplisit.

Akibat: batas 512 KB tidak mencegah child process menghasilkan output besar yang sudah ter-buffer di parent. Jika child/parser menghasilkan output besar, parent tetap dapat mengalokasikan memori besar sebelum menolak output.

Rekomendasi:
- Baca stdout/stderr secara streaming dengan hard cap.
- Begitu batas terlampaui, hentikan process group dan kembalikan error.
- Simpan hanya potongan stderr untuk diagnosis.
- Tambahkan test worker yang sengaja menulis output jauh melebihi batas dan buktikan proses dihentikan sebelum seluruh output dibuffer.

## 8. Prioritas tindakan

| Prioritas | Tindakan | Kriteria selesai |
|---|---|---|
| P2-01 | Jalankan verifier di OS sandbox | Parser tidak dapat membaca host files atau mengakses network |
| P2-02 | Terapkan streaming output cap | Output besar menghentikan worker tanpa buffer tak terbatas |
| Release gate | Ulangi CI matrix | macOS, Windows, Ubuntu menyelesaikan test steps |
| Hardening | Fuzz ZIP/OOXML/PDF | Parser guard diuji dengan corpus malformed/adversarial |
| Hardening | Uji race path verifier | Tidak ada path swap/symlink antara validasi dan pembukaan file |

## 9. Keputusan rilis

- **Internal Alpha:** dapat dilanjutkan.
- **Private Beta:** terbatas, untuk pengguna tepercaya dan file dengan sumber diketahui.
- **Public Beta:** belum direkomendasikan sebelum P2 verifier dan CI matrix ditutup.
- **Production GA:** belum siap.

Perbaikan Siklus 9 cukup substantif. Namun, jangan menyamakan proses yang dapat dibunuh dengan proses yang terisolasi secara keamanan. Jangan pula menandai dukungan Windows/Linux selesai sebelum test native benar-benar berjalan.

## 10. Referensi

- Commit terbaru: https://github.com/yogijowo/aksa/commit/a0a3695821ab1a1cdbab51bafed64770cf8ae01f
- Compare Siklus 9 → 10: https://github.com/yogijowo/aksa/compare/4e8600d57ab64d667f1716c9bd171374490d5e15...a0a3695821ab1a1cdbab51bafed64770cf8ae01f
- CI Matrix run: https://github.com/yogijowo/aksa/actions/runs/44471418108
- Security workflow run: https://github.com/yogijowo/aksa/actions/runs/44471418100
