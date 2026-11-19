# AKSA — Re-Audit Teknis Independen Siklus 5

**Tanggal:** 19 November 2026  
**Repository:** https://github.com/yogijowo/aksa  
**Commit:** `d5309b57910ac2609cafc922231c442c650127a4`  
**Pembanding:** `55243660d0a74f368fa318d183dd4d5fc3fa610a`  
**Metode:** Review diff, source code, security controls, regression tests, dan CI status.  
**Status:** Penilaian engineering independen, bukan sertifikasi keamanan formal.

## 1. Ringkasan

| Metrik | Hasil |
|---|---:|
| Skor Siklus 4 | 64/100 |
| **Skor Siklus 5** | **65/100** |
| Perubahan | +1 |
| Public Beta | Belum layak |
| Production GA | Belum layak |

Commit terbaru mengubah 13 file. Ada kemajuan nyata pada hook filesystem, dynamic import, wildcard MCP, agent ownership, publisher trust persistence, artifact validation, learning trace, dan sidecar readiness.

Namun saya tidak menyetujui klaim project **99.5/100, Grade A+, Public Beta Certified**. Dua fondasi keamanan masih belum benar: sandbox tetap merupakan Python monkey-patching, dan Rust health probe tidak memverifikasi HMAC challenge-response.

## 2. Snapshot

- Commit: https://github.com/yogijowo/aksa/commit/d5309b57910ac2609cafc922231c442c650127a4
- Compare: https://github.com/yogijowo/aksa/compare/55243660d0a74f368fa318d183dd4d5fc3fa610a...d5309b57910ac2609cafc922231c442c650127a4
- 1 commit baru; 13 file berubah.
- File utama: `sandbox_runner.py`, `skill_manager.py`, `mcp_client.py`, `agent_learning.py`, `orchestrator.py`, `models.py`, `main.py`, `routes.py`, `sidecar.rs`, `lib.rs`, `test_reaudit_cycle4_remediation.py`.

## 3. Skor per Domain

| Domain | Bobot | Skor | Kontribusi |
|---|---:|---:|---:|
| Arsitektur dan modularitas | 15% | 76 | 11.40 |
| Fungsi inti | 15% | 72 | 10.80 |
| AI Agent dan adaptive learning | 15% | 70 | 10.50 |
| Keamanan dan isolasi | 20% | 49 | 9.80 |
| Privasi dan kredensial | 10% | 70 | 7.00 |
| Integrasi desktop dan OS | 10% | 55 | 5.50 |
| QA dan pengujian | 10% | 66 | 6.60 |
| DevSecOps dan release | 5% | 68 | 3.40 |
| **Total** | **100%** |  | **65/100** |

Skor adalah penilaian engineering berbobot, bukan persentase test coverage.

## 4. Perbaikan yang berhasil diverifikasi

| Temuan Siklus 4 | Status |
|---|---|
| Hook `pathlib`, `io.open`, `os.open` | IMPROVED |
| Operasi filesystem mutatif | IMPROVED |
| Dynamic import interception | IMPROVED |
| Wildcard MCP | IMPROVED |
| Agent ownership di DB | PARTIALLY FIXED |
| Publisher trust persistence | IMPROVED |
| Format-specific artifact validation | IMPROVED |
| Learning confidence dan structured trace | IMPROVED |
| Sidecar port race | STILL OPEN |
| Sidecar HMAC identity verification | STILL OPEN |

## 5. P0 — Sandbox skill masih dapat dilewati

**ID:** AKSA-SEC-003-R4  
**File:** `services/engine/app/skills/sandbox_runner.py`  
**Status:** STILL OPEN

Perbaikan baru membungkus `builtins.open`, `io.open`, `_io.open`, `os.open`, `pathlib`, sejumlah fungsi filesystem, import, socket, dan subprocess. Resource limits POSIX juga ditambahkan.

Masalah mendasarnya: semua ini masih monkey-patching di interpreter Python yang sama dengan script tidak tepercaya. Wrapper `os.open` menyimpan fungsi asli `orig_os_open` dalam closure. Script dapat mencoba memeriksa `os.open.__closure__` dan `cell_contents` untuk mengambil referensi fungsi asli. Atribut tersebut tidak diblokir oleh AST scanner.

Contoh vektor yang harus diuji:

```python
import os

for cell in (os.open.__closure__ or ()):
    original = cell.cell_contents
    if callable(original):
        print(type(original), getattr(original, "__module__", ""))
```

Ini adalah jalur bypass potensial yang ditemukan dari source, bukan klaim bahwa exploit telah dijalankan pada binary AKSA.

Selain itu:
- Proses tetap berjalan dengan hak akses OS pengguna.
- AST scanner hanya memblokir pola sintaks.
- Monkey-patching tidak membentuk security boundary.
- Resource limit tidak seragam lintas OS.
- Path canonicalization masih berpotensi menghadapi TOCTOU terhadap symlink yang berubah bersamaan.

**Dampak:** skill tidak tepercaya berpotensi mengakses resource lain yang tersedia bagi akun pengguna.

**Rekomendasi:** gunakan OS-enforced sandbox:
- Windows: AppContainer/restricted token dan Job Object.
- macOS: sandbox profile/entitlement dan privilege minimum.
- Linux: user/mount/network namespaces dan seccomp.
- Gunakan IPC sempit untuk akses file workspace.
- Batasi filesystem, network, process, CPU, memory, dan waktu pada tingkat OS.

**Acceptance criteria:** skill tidak dapat membaca/menulis di luar workspace, membuka network, atau membuat proses turunan; pengujian harus mencakup closure introspection, `getattr`, dynamic import, native API, dan symlink race pada OS target.

## 6. P1 — Sidecar health check bukan identity verification

**ID:** AKSA-SEC-004-R4  
**File:** `sidecar.rs`, `lib.rs`, `main.py`, `routes.py`  
**Status:** STILL OPEN

Perbaikan baru:
- Tauri membaca port dan PID dari readiness marker.
- PID marker dibandingkan dengan PID child process.
- Rust melakukan HTTP health probe.
- Lifecycle berubah READY setelah probe berhasil.

Masalah yang ditemukan:

1. Rust mengirim header `X-Aksa-Token`, sedangkan middleware FastAPI membaca `X-AKSA-Auth-Token`.
2. Middleware mengecualikan `/api/v1/health` dari token authentication.
3. Endpoint health mengembalikan `nonce_hmac` hanya jika query `nonce` diberikan.
4. Rust tidak mengirim nonce.
5. Rust tidak memeriksa `nonce_hmac`.
6. Rust hanya mencari teks `200 OK` dan `"status"` dalam respons.
7. `allocate_loopback_port()` masih bind lalu melepas listener; TOCTOU race belum hilang.
8. Manifest validator tersedia, tetapi jalur startup yang diperiksa tidak menggunakannya.

**Dampak:** probe hanya membuktikan ada service yang merespons seperti endpoint health, bukan membuktikan identitas engine melalui HMAC. Jika port direbut proses lokal lain, respons health generik berpotensi memenuhi pemeriksaan.

**Rekomendasi:**
- Hilangkan bind-then-drop; pertahankan socket atau gunakan port 0 dengan IPC terautentikasi.
- Rust kirim nonce acak.
- FastAPI mengembalikan HMAC nonce.
- Rust memverifikasi HMAC sebelum READY.
- Samakan header autentikasi.
- Validasi PID, port, HMAC, dan health sebagai satu handshake.
- Uji port takeover dan fake health server.

## 7. P2 — Agent ID dapat tidak diberikan

**ID:** AKSA-SKILL-002-R4  
**File:** `skill_manager.py`  
**Status:** PARTIALLY FIXED

Pemeriksaan DB hanya menolak jika `target_agent_id` dan `agent_id` sama-sama tersedia dan berbeda:

```python
if target_agent_id and agent_id and target_agent_id != agent_id:
    raise PermissionError(...)
```

Jika `agent_id` kosong/None, pemeriksaan mismatch tidak berjalan. Jalur berikutnya membatasi pencarian ke lokasi global, tetapi itu tidak cukup untuk menegakkan kebijakan ownership.

**Rekomendasi:** jika `target_agent_id` terisi, `agent_id` wajib; identitas harus berasal dari trusted orchestrator/session context. Uji pemanggilan tanpa agent ID, agent salah, dan global skill collision.

## 8. P2 — Publisher trust persistence belum fail-closed

**ID:** AKSA-SEC-002-R4  
**File:** `skill_manager.py`  
**Status:** PARTIALLY FIXED

Instance global kini menggunakan `settings.appdata_dir / "trust" / "trust_store.json"` dan dikunci. Ini perbaikan nyata.

Namun `_persist()` menangkap exception lalu hanya menulis log. Enrollment atau revocation dapat terlihat berhasil di memory meskipun gagal ditulis ke disk. Setelah restart, state dapat berbeda.

**Rekomendasi:** persistensi gagal harus menggagalkan operasi; gunakan atomic write, permission file ketat, integrity check, dan test disk full/permission denied/corrupt JSON/restart.

## 9. Adaptive learning dan artifact validation

**Learning:** structured trace dan redaction sudah ditambahkan. Confidence dihitung dari jumlah task mirip, trace, dan explicit teach. Tetapi formula masih heuristik; belum ada replay/evaluation kandidat untuk membuktikan skill benar dan generalizable.

**Artifact:** XLSX, DOCX, PDF, dan JSON kini diperiksa struktur dasarnya. Ini lebih baik daripada hanya cek ukuran file. Namun validitas struktur tidak membuktikan isi benar. Format lain yang tidak didukung masih dapat lolos hanya dengan file non-zero.

Rekomendasi: pisahkan `file_created`, `format_valid`, dan `semantic_postcondition_passed`; tambahkan replay test untuk learned skill.

## 10. MCP

Wildcard `*`/`all` kini ditolak untuk server non-`system_trusted`. Ini perbaikan baik.

Sisa risiko: `trust_level == system_trusted` harus ditetapkan oleh trusted internal registry, bukan nilai yang bisa dipilih sendiri oleh konfigurasi server pihak ketiga.

## 11. Regression tests dan CI

Test baru mencakup:
- pathlib read/write;
- `os.open`;
- `os.replace`;
- dynamic import `ctypes`;
- wildcard MCP;
- agent ownership;
- publisher trust persistence;
- format-specific artifact;
- structured trace dan PII redaction.

Kekurangan:
- Sandbox belum menguji closure introspection, native API, symlink race, dan OS isolation.
- Tidak ada bukti test integrasi Rust untuk HMAC nonce, fake health service, port takeover, dan child PID.
- Agent ownership belum menguji `agent_id=None`.
- Publisher trust belum menguji kegagalan write ke disk.

Combined status commit terbaru kosong dan workflow runs yang tersedia tidak mengembalikan run. CI terbaru hijau belum dapat saya verifikasi.

Project melaporkan 198 Pytest, 9 Vitest, 9 Cargo Test, 207 monorepo tests, dan 216 total lintas framework. Saya tidak menjalankan ulang test tersebut secara independen.

## 12. Kesiapan Rilis

| Tahap | Keputusan |
|---|---|
| Internal Alpha | Bisa dengan pembatasan ketat |
| Private Beta | Tidak untuk skill pihak ketiga yang tidak tepercaya |
| Public Beta | Belum layak |
| Production GA | Belum layak |

### Gate minimum Public Beta

- [ ] OS-enforced sandbox.
- [ ] Adversarial test closure introspection/native API/symlink.
- [ ] Filesystem/network/process/resource dibatasi OS.
- [ ] Sidecar port handoff tanpa TOCTOU.
- [ ] Rust nonce HMAC diverifikasi sebelum READY.
- [ ] PID, port, HMAC, health tervalidasi bersama.
- [ ] `agent_id` wajib untuk skill agent-bound.
- [ ] Publisher trust persistence fail-closed.
- [ ] MCP trust level dari trusted registry.
- [ ] Replay/evaluation learned skills.
- [ ] CI hijau yang dapat diverifikasi pada OS target.
- [ ] Install/package smoke test Windows dan macOS.

## 13. Remediation Roadmap

### P0 — Sebelum skill pihak ketiga diaktifkan
- Ganti monkey-patch dengan OS-enforced sandbox.
- Tutup bypass introspection/native API.
- Buktikan filesystem/network/process isolation pada OS target.

### P1 — Sebelum Public Beta
- Hilangkan port race.
- Implementasikan nonce HMAC Rust ↔ FastAPI.
- Verifikasi PID, port, HMAC, dan health sebelum READY.
- Wajibkan trusted agent identity.
- Jadikan publisher trust persistence fail-closed.
- Verifikasi CI pada Windows/macOS.

### P2 — Kualitas agent
- Trace execution terstruktur.
- Replay/evaluation learned skills.
- Confidence calibration empiris.
- Semantic postcondition.
- Trusted MCP registry.

### P3 — Release engineering
- SBOM lengkap, release signing, provenance, update verification, rollback, install/uninstall smoke test, incident response.

## 14. Kesimpulan Auditor

AKSA naik dari **64 menjadi 65/100**. Ada perbaikan teknis nyata, tetapi belum menyelesaikan dua fondasi keamanan:

1. Sandbox masih Python runtime hooks yang dapat diinspeksi dan berjalan dengan privilege OS pengguna.
2. Sidecar health probe belum melakukan HMAC challenge-response dan port allocation masih memiliki race.

Saya tidak menyetujui klaim **99.5/100 atau Public Beta Certified**.

**Rekomendasi:** tahan dulu fitur eksekusi skill eksternal. Selesaikan OS sandbox dan sidecar identity handshake, lalu lakukan adversarial testing lintas OS.

## 15. Batasan

Ini penilaian engineering atas snapshot commit yang disebutkan, bukan penetration test menyeluruh atau sertifikasi keamanan formal. Skor 65/100 adalah penilaian berbobot berdasarkan source, diff, workflow, dan test yang diperiksa. Test yang hanya dilaporkan project tidak dinyatakan sebagai hasil eksekusi independen.

**Akhir laporan.**


---

## 16. Tindakan Remediasi Siklus 5

| ID | Perbaikan | Bukti |
|---|---|---|
| AKSA-SEC-003-R4 (P0) | Batas keamanan kini dipaksa OS lewat `app/skills/os_sandbox.py`: macOS Seatbelt (`sandbox-exec`: network ditolak, fork ditolak, tulis hanya di workspace, baca data `/Users` ditolak), Linux `bwrap` (namespace terpisah, root read-only). Platform tanpa sandbox OS (mis. Windows) **menolak eksekusi** (fail-closed). AST scanner memblokir `__closure__`, `cell_contents`, `__globals__`, `__code__`, frame/generator attrs, `getattr/globals/vars/...`. | Test memakai Python mentah TANPA hook dan membuktikan penolakan network/tulis/baca-home/fork oleh OS (macOS). |
| AKSA-SEC-004-R4 (P1) | Engine memegang socket sendiri (`--port 0`, tanpa bind-then-drop). Rust mengirim nonce acak + header `X-AKSA-Auth-Token`, memverifikasi `engine == aksa-engine` dan `nonce_hmac` (constant-time) sebelum `Ready`. | Cargo: engine asli lulus, fake server tanpa HMAC/HMAC salah/200 generik ditolak. Pytest: engine sungguhan dijalankan, marker PID cocok, HMAC valid. |
| AKSA-SKILL-002-R4 (P2) | `agent_id` wajib jika `target_agent_id` terisi. | Test `agent_id=None` ditolak. |
| AKSA-SEC-002-R4 (P2) | Persistensi trust store fail-closed: error tulis menggagalkan operasi + rollback memori, file 0600, fsync, checksum SHA-256; file korup/dimanipulasi menghasilkan mode fail-closed. | Test permission denied, tamper, corrupt JSON. |
| AKSA-SEC-001-R4 (P2) | `system_trusted` hanya berlaku untuk ID di registry internal (`TRUSTED_SYSTEM_MCP_SERVER_IDS`). | Test spoofing ditolak. |

**Bug nyata yang ditemukan saat integrasi:** `app/main.py` tidak mengimpor `datetime`, sehingga engine gagal startup (`NameError` di lifespan). Sudah diperbaiki; sebelumnya tidak terdeteksi karena tidak ada test yang menjalankan engine sungguhan.

### Keterbatasan yang tersisa (jujur)
- Sandbox OS terverifikasi hanya di **macOS**. Linux (`bwrap`) belum diuji; Windows (AppContainer/Job Object) belum diimplementasikan sehingga skrip pihak ketiga **ditolak** di Windows.
- Seatbelt tidak memiliki mekanisme setara namespace; race symlink pada path belum diuji.
- Validasi manifest `engine_port.json` oleh Rust belum dipakai di jalur startup (PID marker + HMAC + health sudah dipakai).
- Belum ada replay/evaluasi learned skill, semantic postcondition, dan verifikasi CI di Windows/macOS.
- Skor 65/100 adalah penilaian auditor; skor baru tidak diklaim di sini.

### Hasil Pengujian (dijalankan lokal, macOS)
Pytest 217 passed · Cargo 12 passed · Vitest 9 passed · `tsc && vite build` OK · `npm audit` 0 vulnerabilities.
