# AKSA — Re-Audit Teknis Independen Siklus 6

**Tanggal:** 19 November 2026  
**Repository:** https://github.com/yogijowo/aksa  
**Commit:** `f104d613f7699799aa64949cd8a4114e6614160b`  
**Pembanding:** `d5309b57910ac2609cafc922231c442c650127a4`  
**Metode:** Review commit diff, source code, sandbox, sidecar lifecycle, trust store, agent learning, artifact validation, tests, dan CI evidence.  
**Status:** Penilaian engineering independen, bukan sertifikasi keamanan formal.

## 1. Ringkasan Eksekutif

| Metrik | Hasil |
|---|---:|
| Skor Siklus 5 | 65/100 |
| **Skor Siklus 6** | **67/100** |
| Perubahan | **+2 poin** |
| Public Beta | **Belum layak** |
| Production GA | **Belum layak** |

Dua commit baru menambahkan OS sandbox, nonce-HMAC handshake, manifest port, agent identity enforcement, trust store fail-closed, artifact postcondition, dan candidate skill replay simulation.

Saya menaikkan skor dua poin karena perbaikan macOS/Linux dan HMAC handshake cukup berarti. Namun saya tidak menyetujui klaim 99/100, Grade A+, atau seluruh blocker selesai.

Temuan utama:
1. **Windows belum memiliki sandbox filesystem/network.** `wrap_command()` mengembalikan command mentah pada Windows. Job Object hanya membatasi proses dan memori, bukan file atau jaringan. Pemasangan dilakukan setelah proses dibuat dan hasilnya diabaikan.
2. **Manifest sidecar masih opsional.** Jika `engine_port.json` tidak ada atau gagal dibaca, Rust tetap melanjutkan HMAC health probe dan dapat menandai engine READY.
3. **macOS Seatbelt menggunakan `(allow default)`.** Ini bukan deny-by-default; beberapa direktori sensitif ditolak secara eksplisit, tetapi akses baca ke lokasi lain tetap mengikuti default allow.
4. **Candidate replay bukan replay eksekusi.** Implementasi hanya memeriksa nama tool, string input, dan status trace; output trace tidak digunakan.
5. **Semantic artifact gate auto-pass untuk ekstensi yang tidak dikenal.**

### Batasan audit

Saya memeriksa source dan diff, tetapi tidak menjalankan ulang 221 Pytest, 15 Cargo Test, 9 Vitest, atau menguji binary pada hardware Windows/macOS/Linux. Combined status commit dan workflow runs yang tersedia tidak mengembalikan status CI. Angka test di `PROGRESS.md` adalah klaim project, bukan eksekusi independen saya.

## 2. Snapshot

- Commit: https://github.com/yogijowo/aksa/commit/f104d613f7699799aa64949cd8a4114e6614160b
- Compare: https://github.com/yogijowo/aksa/compare/d5309b57910ac2609cafc922231c442c650127a4...f104d613f7699799aa64949cd8a4114e6614160b
- Dua commit baru sejak Siklus 5.
- File utama: `os_sandbox.py`, `sandbox_runner.py`, `skill_manager.py`, `orchestrator.py`, `agent_learning.py`, `main.py`, `sidecar.rs`, `lib.rs`, dan `test_reaudit_cycle5_remediation.py`.

## 3. Skor per Domain

| Domain | Bobot | Skor | Kontribusi |
|---|---:|---:|---:|
| Arsitektur dan modularitas | 15% | 77 | 11.55 |
| Fungsi inti | 15% | 73 | 10.95 |
| AI Agent dan adaptive learning | 15% | 71 | 10.65 |
| Keamanan dan isolasi | 20% | 52 | 10.40 |
| Privasi dan kredensial | 10% | 72 | 7.20 |
| Integrasi desktop dan OS | 10% | 57 | 5.70 |
| QA dan kualitas pengujian | 10% | 65 | 6.50 |
| DevSecOps dan release | 5% | 62 | 3.10 |
| **Total berbobot** | **100%** |  | **66.05/100** |

**Skor akhir auditor: 67/100**, sebagai penilaian keseluruhan setelah mempertimbangkan kemajuan lintas domain. Ini indikator engineering, bukan ukuran ilmiah atau sertifikasi.

## 4. Status Temuan Siklus 5

| Temuan | Status Siklus 6 | Catatan |
|---|---|---|
| Python hooks sebagai satu-satunya sandbox | IMPROVED | OS sandbox ditambahkan untuk macOS/Linux |
| Windows sandbox | STILL OPEN | Job Object bukan filesystem/network isolation |
| Sidecar HMAC challenge-response | FIXED IN SOURCE | Rust mengirim nonce dan memverifikasi HMAC |
| Port bind-then-drop | IMPROVED | Engine diminta bind port 0; jalur allocator lama masih perlu diaudit |
| Manifest wajib | PARTIALLY FIXED | Manifest opsional di handshake |
| Agent-bound skill tanpa agent_id | FIXED IN SOURCE | Identitas kosong ditolak |
| Publisher trust persistence | IMPROVED | Rollback jika persist gagal, checksum dan file mode ditambahkan |
| MCP trusted identity | IMPROVED | Registry internal diperiksa |
| Candidate skill replay | PARTIALLY FIXED | Masih simulasi statis |
| Artifact semantic postcondition | PARTIALLY FIXED | Unknown extension auto-pass |

## 5. P0 — Windows Tidak Memiliki OS Sandbox Filesystem/Network

**ID:** AKSA-SEC-003-R5  
**File:** `services/engine/app/skills/os_sandbox.py`, `skill_manager.py`  
**Status:** STILL OPEN

Dalam `wrap_command()`:

```python
if sys.platform == "win32":
    return cmd
```

Artinya command skill dikembalikan tanpa pembungkus OS sandbox.

Setelah child process dibuat, `skill_manager.py` memanggil `apply_windows_job_object_limits(proc.pid)`, tetapi nilai boolean hasilnya tidak diperiksa. Jika fungsi gagal, eksekusi tetap berjalan.

Job Object hanya mengatur:
- `KILL_ON_JOB_CLOSE`
- `ACTIVE_PROCESS`
- `PROCESS_MEMORY`

Tidak ada pembatasan filesystem atau network. Job Object bukan pengganti AppContainer atau restricted token dengan capability minimum.

Masalah tambahan:
- Proses dibuat sebelum dimasukkan ke Job Object; kode dapat mulai berjalan sebelum assignment berhasil.
- Return value assignment tidak dipakai untuk menghentikan eksekusi.
- Lifecycle handle Job Object tidak dikelola secara jelas.

**Dampak:** script pihak ketiga di Windows masih berpotensi mewarisi akses filesystem dan jaringan dari akun pengguna AKSA.

**Rekomendasi:**
- Implementasikan AppContainer atau restricted token dengan ACL/capability minimum.
- Terapkan network isolation.
- Buat proses suspended, assign ke Job Object, baru resume.
- Jika assignment gagal, hentikan eksekusi.
- Kelola handle Job Object sampai proses selesai.
- Jika sandbox belum tersedia, `wrap_command()` harus melempar `SandboxUnavailableError`, bukan mengembalikan command mentah.

**Acceptance criteria:** skill tidak dapat membaca/menulis di luar workspace, membuka network, mengakses credential store, atau membuat proses turunan tanpa izin; kegagalan setup harus menghentikan eksekusi.

## 6. P1 — Manifest Sidecar Masih Opsional Sebelum READY

**ID:** AKSA-SEC-004-R5  
**File:** `apps/desktop/src-tauri/src/sidecar.rs`, `lib.rs`  
**Status:** PARTIALLY FIXED

Perbaikan yang benar-benar ada:
- Rust menghasilkan nonce acak.
- Rust mengirim `X-AKSA-Auth-Token`.
- Rust memeriksa status HTTP, JSON, marker `engine == "aksa-engine"`, dan `nonce_hmac`.
- HMAC dibandingkan secara constant-time.
- PID marker dibandingkan dengan child PID.
- Engine mendukung bind port 0 dan menulis manifest runtime.

Namun `validate_and_sync_handshake()` masih memiliki fallback:

```rust
if let Some(content) = manifest_content {
    let manifest_port = self.read_and_validate_manifest(content, child_pid)?;
    if manifest_port != reported_port {
        return Err(...);
    }
} else {
    self.sync_port(reported_port);
}

verify_engine_health(reported_port, auth_token, 3000)?;
self.set_state(LifecycleState::Ready);
```

Jika manifest tidak ditemukan atau gagal dibaca, fungsi tetap melanjutkan HMAC health probe dan READY.

**Dampak:** HMAC membuktikan service mengetahui token, tetapi jalur startup tidak selalu membuktikan port dan PID sesuai manifest engine.

**Rekomendasi:**
- Manifest wajib pada production mode.
- File hilang, tidak terbaca, JSON rusak, host bukan loopback, port/PID mismatch, version mismatch harus menggagalkan startup.
- Jangan fallback ke `sync_port()` ketika manifest hilang.
- Validasi host harus memastikan `127.0.0.1`.
- Hapus manifest lama sebelum spawn atau gunakan launch ID/nonce untuk menolak stale manifest.

**Acceptance criteria:** READY hanya jika child PID, marker PID, manifest PID, port, host, launch identity, dan HMAC semuanya valid.

## 7. P1 — macOS Seatbelt Belum Least-Privilege Deny-by-Default

**ID:** AKSA-SEC-005-R5  
**File:** `services/engine/app/skills/os_sandbox.py`  
**Status:** PARTIALLY FIXED

Profile dimulai dengan:

```scheme
(allow default)
```

Lalu beberapa akses ditolak: network, process fork, write filesystem kecuali workspace, dan pembacaan data pada `/Users`, `/Volumes`, serta `/private/etc/ssh`.

Masalahnya, `allow default` tetap mengizinkan operasi default yang tidak ditolak secara eksplisit. Daftar deny read saat ini hanya meliputi beberapa lokasi sensitif.

**Rekomendasi:**
- Ubah ke profile least-privilege yang eksplisit mengizinkan operasi minimum.
- Batasi file read ke interpreter/runtime, engine code yang diperlukan, script, dan workspace.
- Audit metadata, device, IPC, temporary directory, dan resource OS.
- Uji secret di luar `/Users`, termasuk lokasi sistem dan application data.
- Verifikasi profile pada seluruh versi macOS yang didukung.

## 8. P2 — Linux Bubblewrap Perlu Verifikasi Runtime

**ID:** AKSA-SEC-006-R5  
**File:** `os_sandbox.py`  
**Status:** IMPLEMENTED, NOT INDEPENDENTLY VERIFIED

Implementasi memakai:
- `--unshare-all`;
- `--die-with-parent`;
- `--new-session`;
- root read-only;
- `/home` dan `/root` sebagai tmpfs;
- workspace writable;
- read roots tertentu.

Arah implementasinya baik, tetapi saya tidak menjalankan bwrap pada Linux. Root filesystem yang dipasang read-only tetap dapat dibaca secara luas. Perlu dipastikan tidak ada credential, socket, mount, atau metadata service sensitif yang terlihat.

**Rekomendasi:** uji pada distribusi Linux target dan audit `/run`, `/var`, `/etc`, `/proc`, `/sys`, `/dev`, socket, mount, dan fallback saat bwrap tidak tersedia.

## 9. P2 — Candidate Replay Belum Menjalankan Replay

**ID:** AKSA-AGENT-001-R5  
**File:** `services/engine/app/core/agent_learning.py`  
**Status:** PARTIALLY FIXED

`SkillEvaluator.evaluate()`:
- membaca `tool_name`;
- mengubah `input_summary` menjadi string;
- mencari beberapa substring berbahaya;
- memeriksa `..`;
- memeriksa status bukan `failed`;
- membuat trace passed/failed.

`output_summary` dibaca ke variabel `outp`, tetapi tidak digunakan. Tidak ada tool invocation, replay DAG, fixture execution, atau pembandingan hasil dengan expected postcondition.

Jadi ini lebih tepat disebut **static trace screening/replay simulation**, bukan replay yang membuktikan generalisasi skill.

**Rekomendasi:** jalankan kandidat di environment terisolasi dengan fixture, validasi dependency DAG dan schema parameter, bandingkan output dengan expected postcondition, uji variasi input, dan ukur pass/failure rate.

## 10. P2 — Artifact Semantic Gate Belum Semantic untuk Semua Format

**ID:** AKSA-AGENT-003-R5  
**File:** `services/engine/app/core/orchestrator.py`  
**Status:** PARTIALLY FIXED

Perbaikan:
- XLSX memeriksa sel terisi.
- DOCX memeriksa teks paragraf/tabel.
- PDF memeriksa halaman dan teks/vector drawing.
- JSON memeriksa parsing dan non-empty.
- File teks memeriksa konten.

Keterbatasan:
- Ekstensi tidak dikenal langsung mendapat `format_valid=True` dan `semantic_postcondition_passed=True`.
- JSON scalar non-empty dapat lolos.
- PDF dengan drawing kosong/ornamental dapat lolos.
- XLSX dengan satu sel placeholder dapat lolos.
- Hasil tidak dibandingkan dengan instruksi atau expected output task.

**Rekomendasi:** unknown extension harus `unsupported`, bukan semantic pass. Gunakan schema sesuai task: row/kolom wajib, formula, rentang data, section dokumen, dan expected content.

## 11. Publisher Trust Store

**Status:** IMPROVED

Perbaikan:
- File mode 0600.
- Checksum SHA-256.
- Temp file dan `fsync`.
- Enrollment melakukan rollback jika persist gagal.
- File corrupt/tampered masuk fail-closed.

Sisa pekerjaan:
- SHA-256 yang disimpan dalam file yang sama bukan tanda tangan digital; pihak yang dapat mengubah file dapat menghitung ulang checksum.
- Validasi permission direktori induk dan symlink/hardlink perlu diperkuat.
- Perlu fsync direktori setelah rename untuk durability.
- Root key rotation dan revocation perlu prosedur yang dapat diaudit.
- Migrasi file legacy tanpa checksum perlu kebijakan eksplisit.

## 12. MCP dan Agent Ownership

**MCP:** Registry internal untuk `system_trusted` adalah kemajuan. Pastikan ID trusted tidak dapat dipilih sendiri oleh konfigurasi server pihak ketiga.

**Agent ownership:** `execute_skill_script()` sekarang menolak pemanggilan tanpa `agent_id` untuk skill agent-bound. Ini memperbaiki temuan sebelumnya. Masih perlu diuji apakah agent ID berasal dari principal/session tepercaya, apakah caller dapat menyamar sebagai agent lain, dan apakah seluruh jalur eksekusi melewati pemeriksaan yang sama.

## 13. Regression Tests dan CI

Test baru yang terlihat:
- AST introspection vectors.
- macOS Seatbelt: network, write outside workspace, read home, fork.
- Unsupported platform fail-closed.
- Engine port 0 dan HMAC response.
- Agent-bound skill tanpa agent ID.
- Publisher trust persist failure, file mode, checksum, tamper/corrupt.
- MCP self-declared system trusted.
- Symlink escape.
- Artifact empty workbook/DOCX.
- Candidate trace screening.

Kesenjangan:
| Area | Kekurangan |
|---|---|
| macOS | Test belum membuktikan seluruh filesystem deny-by-default |
| Linux | Tidak ada bukti eksekusi Linux dari test yang diperiksa |
| Windows | Tidak ada OS filesystem/network sandbox test |
| Sidecar | Manifest missing/stale belum diuji sebagai hard failure |
| Candidate replay | Screening trace, bukan runtime replay |
| Artifact | Unknown extension dan task-specific semantics belum diuji |

Combined status untuk commit terbaru tidak memuat status checks dan workflow runs yang tersedia kosong. CI terbaru hijau belum dapat saya verifikasi.

`PROGRESS.md` melaporkan 221 Pytest, 15 Cargo Test, 9 Vitest, Vite build OK, dan npm audit 0 vulnerabilities. Saya memperlakukan ini sebagai laporan project, bukan hasil eksekusi independen.

## 14. Kesiapan Rilis

| Tahap | Keputusan |
|---|---|
| Internal Alpha | Layak dengan pembatasan fitur dan pengguna tepercaya |
| Private Beta | Hanya dengan skill pihak ketiga dinonaktifkan pada Windows dan pembatasan ketat di platform lain |
| Public Beta | Belum layak |
| Production GA | Belum layak |

### Gate minimum sebelum Public Beta

- [ ] Windows AppContainer/restricted-token sandbox untuk filesystem dan network.
- [ ] Sandbox setup gagal = eksekusi dihentikan.
- [ ] macOS Seatbelt least-privilege.
- [ ] Linux bwrap diuji pada runner dan distribusi target.
- [ ] Manifest wajib; stale manifest ditolak.
- [ ] PID, port, host, launch identity, dan HMAC diverifikasi sebelum READY.
- [ ] Candidate skill replay menjalankan evaluasi prosedur terisolasi.
- [ ] Unknown artifact extension tidak auto-pass.
- [ ] Semantic validation mengikuti expected task output.
- [ ] CI matrix Windows/macOS/Linux hijau dan dapat diverifikasi.
- [ ] Install/package smoke test lintas OS.

## 15. Remediation Roadmap

### P0 — Sebelum skill pihak ketiga tersedia di Windows
1. Implementasikan Windows AppContainer/restricted token dengan filesystem/network isolation.
2. Jangan jalankan script jika sandbox tidak dapat dibuat.
3. Buat proses suspended, assign ke Job Object sebelum resume.
4. Periksa return value dan lifecycle handle Job Object.

### P1 — Sebelum Public Beta
1. Wajibkan manifest pada sidecar production startup.
2. Tolak manifest missing, corrupt, stale, host mismatch, port mismatch, dan PID mismatch.
3. Ubah macOS Seatbelt menjadi least-privilege.
4. Verifikasi Linux bwrap pada CI Linux.
5. Tambahkan adversarial tests lintas OS.

### P2 — Kualitas Agent
1. Ganti replay simulation menjadi replay runtime terisolasi.
2. Validasi output dengan expected postcondition.
3. Tolak semantic pass untuk format tidak didukung.
4. Terapkan task-specific semantic schema.
5. Kalibrasi confidence berdasarkan hasil replay nyata.

### P3 — Release Engineering
SBOM lengkap, release signing/provenance, update verification/rollback, install smoke test, security disclosure, dan incident response.

## 16. Kesimpulan Auditor

AKSA naik dari **65 menjadi 67/100**. Ada kemajuan nyata pada macOS/Linux sandbox direction, HMAC handshake, trust store, dan agent ownership.

Tetapi **fitur sudah ditulis** tidak sama dengan **security boundary sudah terbukti**.

Saya belum menyetujui klaim 99/100 atau Public Beta Certified karena:
- Windows belum memiliki filesystem/network sandbox.
- Job Object dipasang setelah proses dibuat dan kegagalannya diabaikan.
- Sidecar masih dapat READY tanpa manifest.
- macOS policy belum deny-by-default.
- Candidate replay masih screening trace, bukan replay runtime.

**Rekomendasi:** prioritaskan Windows sandbox fail-closed, manifest wajib, dan pengujian OS sandbox lintas platform. Jangan aktifkan pemasangan/eksekusi skill eksternal secara umum sampai platform yang didukung memiliki boundary yang benar-benar diuji.

## 17. Batasan

Ini review engineering atas source snapshot yang disebutkan, bukan penetration test menyeluruh, audit binary, atau sertifikasi keamanan formal. Saya tidak menjalankan ulang test suite atau menguji hardware lintas OS pada audit ini. Skor 67/100 merupakan penilaian berbobot dan bersifat indikatif.

**Akhir laporan.**
