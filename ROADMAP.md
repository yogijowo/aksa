# ROADMAP — Peta Jalan Pengembangan AKSA (Phased Engineering Blueprint)

**Dokumen Versi:** 2.1.0  
**Status Saat Ini:** Fase 37 Selesai — Menuju Fase 38+  
**Target Rilis:** v0.0.2 (Pre-Beta Alpha) $\rightarrow$ v0.1.0 (Public Beta) $\rightarrow$ v1.0.0 (Production LTS)  
**Terakhir Diperbarui:** 20 November 2026  

---

## 1. Ikhtisar Visi & Topologi Arsitektur Terdistribusi

AKSA dirancang sebagai **Sistem Operasi Kerja AI Otonom & Digital Headquarters** yang beroperasi dengan kedaulatan lokal 100% (*local-first*). Arsitektur sistem memisahkan secara tegas antara **Mesin Server Otonom (AKSA Core Server)**, **Aplikasi Klien Dedicated (Desktop & Mobile)**, dan **Pusat Akses Jarak Jauh Multi-Kanal (Omni-Channel Gateway)**:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TOPOLOGI SERVER & KLIEN TERDISTRIBUSI                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌───────────────────────────┐             ┌─────────────────────────┐    │
│    │    AKSA DESKTOP CLIENT    │             │   AKSA MOBILE CLIENT    │    │
│    │ (Tauri v2 + React 19 GUI) │             │  (Roadmap: iOS/Android) │    │
│    │ • Windows, macOS, Linux   │             │ • Biometric One-Tap HITL│    │
│    │ • Visual Office Canvas    │             │ • Real-time Monitoring  │    │
│    └─────────────┬─────────────┘             └────────────┬────────────┘    │
│                  │                                        │                 │
│                  │       TLS Terenkripsi / E2EE Lokal     │                 │
│                  └───────────────────┬────────────────────┘                 │
│                                      │                                      │
│                                      ▼                                      │
│               ┌──────────────────────────────────────────────┐              │
│               │               AKSA CORE SERVER               │              │
│               │ (Python FastAPI + SQLite + LLM Router + OS)  │              │
│               │ • Mesin Utama: Office, RAG, Sandbox, Rules   │              │
│               │ • Berjalan di PC Lokal, Homelab, atau VPS    │              │
│               │ • Mode Headless CLI Linux 24/7               │              │
│               └──────────────────────┬───────────────────────┘              │
│                                      │                                      │
│                   ┌──────────────────┴──────────────────┐                   │
│                   ▼                                     ▼                   │
│     ┌───────────────────────────┐         ┌───────────────────────────┐     │
│     │   OMNI-CHANNEL GATEWAY    │         │    KONEKTOR EKOSISTEM     │     │
│     │ (Perpesanan Jarak Jauh)   │         │ (Google Workspace, Medsos)│     │
│     └───────────────────────────┘         └───────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **AKSA Core Server (Mesin Server Otonom):**
   * Mesin inti berbasis Python FastAPI, SQLite, dan sandbox terisolasi. Mengeksekusi orkestrasi tim multi-agen, automasi dokumen Office nyata, RAG semantik hibrida, mesin penjadwal otonom, dan ledger audit kriptografis.
   * Fleksibel dijalankan langsung di workstation pengguna (Windows, macOS, Linux) maupun dijalankan 24/7 sebagai *headless daemon / service* di Linux Server, homelab, VPS, atau container Docker tanpa display grafis.
2. **AKSA Desktop Client (Windows, macOS, Linux):**
   * Aplikasi desktop visual native berbasis Tauri v2 dan React 19. Menampilkan kanvas Kantor Virtual 2.5D, perancang hierarki agen visual (@xyflow/react), panel inspektur berkas, dan dialog persetujuan OS.
3. **AKSA Mobile Client (Android & iOS):**
   * Klien smartphone native terenkripsi *end-to-end* yang berfungsi sebagai pusat kendali bergerak (*mobile command center*): pemantauan status aktivitas kantor virtual *real-time*, persetujuan izin Human-in-the-Loop (HITL) satu sentuhan dengan sensor biometrik (*fingerprint* / FaceID), dan dikte instruksi kerja saat bepergian.
4. **Omni-Channel Remote Command Gateway:**
   * Gateway perpesanan terpadu berbasis lapisan adaptor modular yang dapat dihubungkan ke berbagai platform komunikasi jarak jauh yang aman (seperti Telegram, WhatsApp Business API / Baileys, Discord Webhook, Slack, Matrix, maupun webhook internal korporasi). Telegram difungsikan sebagai salah satu adaptor referensi utama yang sudah terpasang.

---

## 2. Status Pencapaian Fase Rekayasa

### Bagian I: Fondasi Sistem, Keamanan & Mesin Dokumen (SELESAI — Status: v0.0.2 Pre-Beta Alpha)

#### Fase 1 s/d Fase 5: Scaffolding, Orkestrator & Automasi 3-Tier
- [x] **Fase 1: Inisialisasi Monorepo & Shell Desktop**
  - Scaffold monorepo (Tauri v2 + React 19 + TypeScript + Tailwind CSS v4 + Python FastAPI).
  - Skema database SQLite awal (`teams`, `agents`, `workspaces`, `sessions`, `messages`).
  - Template tim default: *"Tim Produktivitas Kantor Indonesia"*.
- [x] **Fase 2: Multi-Model Router & Efisiensi Token**
  - Integrasi 10 provider cloud resmi (Gemini, Claude, OpenAI, DeepSeek, Groq, dsb) via LiteLLM.
  - Integrasi model AI lokal gratis 100% offline via Ollama (`localhost:11434`) dan LM Studio.
  - Implementasi *Sub-Agent Context Isolation* dan *Rolling Context Compaction* (hemat token hingga 80%).
- [x] **Fase 3: Sandbox Ruang Kerja & Mesin Dokumen 3-Tier**
  - Pembatasan akses berkas ketat (*path jail* `allowed_paths`) dan pencadangan otomatis ke `.aksa_backup/`.
  - Generator dan inspektur dokumen Excel (`.xlsx`), Word (`.docx`), PowerPoint (`.pptx`), dan PDF (`pymupdf`).
  - OS Bridge (`pywin32` / `osascript`), subproses Python terisolasi (`uv`), dan klien MCP.
- [x] **Fase 4: Basis Pengetahuan RAG Hibrida Lokal**
  - Pencarian hibrida vektor padat (LanceDB) + pencarian kata kunci eksak BM25 (SQLite FTS5).
  - Pemantau folder otomatis *real-time* berbasis hash `SHA-256`.
- [x] **Fase 5: Omni-Channel Gateway (Adaptor Telegram) & Mode Linux CLI**
  - Layanan bot perpesanan jarak jauh dengan kode pairing 6-digit dan whitelist akun numerik.
  - Transkripsi suara (*Voice Note*) Bahasa Indonesia dan tombol persetujuan izin HITL interaktif.
  - Dukungan mode server *headless* di Linux tanpa display server (X11/Wayland).

---

#### Fase 6 s/d Fase 37: Audit Keamanan Enterprise, Refinement UI/UX & Pipeline Build
- [x] **Fase 6 – 15: Perbaikan Desain UI/UX & Standar Zero-Emoji**
  - Transformasi seluruh antarmuka menggunakan tema *Obsidian Slate Dark* dan *Warm Paper Light*.
  - Penghapusan seluruh emoji Unicode statis di UI, digantikan 100% ikon vektor dinamis `lucide-react` + `framer-motion`.
- [x] **Fase 16 – 34: Remediasi Audit Keamanan Enterprise (14 Siklus)**
  - Otentikasi token sidecar *challenge-response* 256-bit.
  - Penyimpanan kredensial terenkripsi pada OS Keyring bawaan (Windows DPAPI / macOS Keychain).
  - Pembatasan satu kali pakai untuk token persetujuan HITL (*anti-replay cryptographic token*).
  - Verifikasi integritas biner *non-stub* format native ELF, Mach-O, dan PE.
- [x] **Fase 35 – 36: Memori Percakapan Multi-Turn & Presentasi Data Riil**
  - Pengenalan konteks rujukan lanjutan pada percakapan multi-turn (*"dari data itu tolong buatkan PPT"*).
  - Pembuatan slide presentasi PowerPoint dinamis berbasis data riil spreadsheet (bukan templat statis).
- [x] **Fase 37: Penyelarasan Versi ke 0.0.2 & Otomasi Build Installer Windows**
  - Penyesuaian versi menyeluruh ke **`v0.0.2` (Pre-Beta Alpha)** di seluruh manifest (npm, cargo, pyproject, runtime).
  - Pembersihan error encoding `cp1252` pada console Windows runner.
  - Otomasi pengemasan installer mandiri NSIS `.exe` (`AKSA_0.0.2_x64-setup.exe`, 114,5 MB) melalui pipeline CI privat tanpa publikasi release prematur.
  - Penyusunan PRD komprehensif ([`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md)) untuk Pilar Kantor Virtual, Scheduler Otonom, dan Konektor Ekosistem.

---

### Bagian II: Rencana Pengembangan Mendatang (Roadmap ke Depan)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SEKUENSI FASE MENDATANG                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ Fase 38: Autonomous Scheduler Engine & Multi-Channel HITL Gate              │
│ Fase 39: Google Workspace Ecosystem Connector (Drive, Sheets, Docs, Gmail) │
│ Fase 40: Hub Media Sosial & Komunikasi Korporat (LinkedIn, X, Meta)         │
│ Fase 41: AKSA Virtual Office Experience (Visual 2.5D Agent Floor Plan)      │
│ Fase 42: Topologi Terdistribusi & Klien Mobile AKSA (Android & iOS)         │
│ Fase 43: Inovasi Arsitektur & Kapabilitas Inti Sistem Operasi Mandiri       │
│ Fase 44: Pengujian Kelayakan Pengguna (Usability Testing) & Audit Kepatuhan │
│ Fase 45: Peluncuran Publik Resmi (v0.1.0 Public Beta ➔ v1.0.0 Production)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

#### Fase 38: Autonomous Scheduler Engine & Multi-Channel HITL Gate
*Target Rilis: AKSA v0.0.3-alpha*  
*Spesifikasi Arsitektur: [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) (Bagian 3)*
- [ ] **38.1 Backend Scheduler Core:**
  - Integrasi pustaka asinkron `APScheduler` ke dalam sidecar Python engine.
  - Migrasi skema database SQLite untuk tabel `scheduled_jobs` dan `scheduled_job_logs`.
- [ ] **38.2 Natural Language & Cron Parser:**
  - Parsing instruksi rutin bahasa alami (misal: *"Setiap Senin jam 8 pagi buatkan laporan penjualan"*) menjadi ekspresi Cron standar.
- [ ] **38.3 Multi-Channel HITL Interactive Cards:**
  - Kartu notifikasi persetujuan interaktif di Desktop UI (`tauri-plugin-notification`) dan gateway perpesanan jarak jauh dengan tombol `[Setujui & Jalankan]` / `[Tolak]`.
- [ ] **38.4 Antarmuka Jadwal & Rutinitas:**
  - Halaman manajemen jadwal di aplikasi desktop (daftar jadwal aktif, log eksekusi, tombol jeda/lanjutkan).

---

#### Fase 39: Google Workspace Ecosystem Connector
*Target Rilis: AKSA v0.0.4-alpha*  
*Spesifikasi Arsitektur: [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) (Bagian 4.2)*
- [ ] **39.1 Otentikasi Aman OAuth 2.0 PKCE:**
  - Alur otentikasi loopback desktop lokal; token akses disimpan terenkripsi di OS Keyring bawaan perangkat.
- [ ] **39.2 Alat Kerja Google Drive & Docs:**
  - Pencarian berkas di cloud, pengunduhan ke workspace lokal, dan ekspor dokumen Word/PDF lokal ke Drive.
- [ ] **39.3 Sinkronisasi Google Sheets:**
  - Pembacaan data tabel cloud dan penambahan baris rekapitulasi data secara otomatis.
- [ ] **39.4 Google Calendar & Gmail:**
  - Pemeriksaan jadwal agenda harian, pembuatan event kegiatan baru, dan penyusunan draf email Gmail yang diproteksi gerbang persetujuan HITL sebelum dikirim.

---

#### Fase 40: Hub Media Sosial & Komunikasi Korporat
*Target Rilis: AKSA v0.0.5-alpha*  
*Spesifikasi Arsitektur: [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) (Bagian 4.3)*
- [ ] **40.1 Template Agen Spesialis Komunikasi & Media Sosial:**
  - Agen baru dengan persona profesional yang bertugas merangkum hasil kerja ruang kerja menjadi materi publikasi.
- [ ] **40.2 Pratinjau Postingan Interaktif (Live Social Preview Card):**
  - Kartu visual di desktop yang menampilkan teks postingan, tautan, lampiran gambar, dan hashtag sebelum dipublikasikan.
- [ ] **40.3 Penegakan Aturan Mutlak Zero Unapproved Post:**
  - Agen dilarang keras menerbitkan postingan ke LinkedIn, X, atau Meta tanpa persetujuan eksplisit pengguna.
- [ ] **40.4 Pemantauan Sebutan & Draf Balasan Komentar:**
  - Membaca komentar audiens dan menyiapkan rekomendasi respons ramah untuk ditinjau pengguna.

---

#### Fase 41: AKSA Virtual Office Experience (Visual Agent Canvas)
*Target Rilis: AKSA v0.0.6-alpha*  
*Spesifikasi Arsitektur: [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) (Bagian 2)*
- [ ] **41.1 Denah Kantor Isometrik 2.5D (Vector SVG & Canvas):**
  - Desain ruang kerja visual yang ringan, responsif 60fps, dan selaras dengan tema Obsidian/Paper Light.
- [ ] **41.2 Animasi Status Agen Dinamis:**
  - Representasi visual nyata: Duduk santai & minum kopi saat *idle*, mengetik di monitor saat *working*, berkumpul di meja rapat saat *collaborating*, dan melambaikan tangan saat *waiting HITL approval*.
- [ ] **41.3 Sinkronisasi Real-Time via WebSocket:**
  - Perubahan status orkestrator langsung menggerakkan karakter agen di kanvas tanpa lag.
- [ ] **41.4 Interaksi Meja & Switcher Tampilan:**
  - Klik meja untuk membuka panel inspektur agen; tombol pengalih: `[ Kantor Virtual ] | [ Diagram Hirarki ] | [ Daftar Tim ]`.

---

#### Fase 42: Topologi Terdistribusi & Klien Mobile AKSA
*Target Rilis: AKSA v0.0.7-alpha*
- [ ] **42.1 Pemisahan Arsitektur Server-Client:**
  - Menjadikan `services/engine` sebagai **AKSA Core Server** mandiri yang dapat di-host di komputer kerja, homelab, atau VPS pribadi.
- [ ] **42.2 AKSA Mobile Client (Android & iOS):**
  - Aplikasi smartphone native yang terhubung secara aman (E2EE/TLS) ke AKSA Core Server pengguna.
  - Fitur: Notifikasi persetujuan HITL biometrik satu sentuhan (*fingerprint / FaceID approval*), pemantauan status kantor virtual langsung dari ponsel, dan input perintah suara/teks.
- [ ] **42.3 Omni-Channel Gateway Expansion:**
  - Perluasan adaptor perpesanan selain Telegram (WhatsApp Business API / Baileys, Discord Webhook, Slack, Matrix).

---

#### Fase 43: Inovasi Arsitektur & Kapabilitas Inti Sistem Operasi Mandiri
*Target Rilis: AKSA v0.0.8-alpha*
- [ ] **43.1 Voice-to-Action & Ambient Executive Audio Briefing:**
  - Integrasi Whisper lokal dan Piper TTS lokal (100% offline).
  - Dikte instruksi langsung melalui mikrofon dan pembacaan ringkasan eksekutif secara *hands-free*.
- [ ] **43.2 Self-Healing Document & Data Doctor:**
  - Deteksi anomali pada file spreadsheet korup, perbaikan otomatis rumus error (`#REF!`, `#DIV/0!`), dan laporan audit pemulihan.
- [ ] **43.3 Multimodal Smart OCR & Document Scanner:**
  - Ekstraksi foto kwitansi, invoice faktur, atau dokumen fisik PDF scan menjadi tabel data Excel rapi.
- [ ] **43.4 Deep Work Shield & Focus Guard:**
  - Penahanan interupsi notifikasi kecil saat pengguna sedang mengetik/coding intensif, menyajikan intisari saat pengguna senggang.
- [ ] **43.5 Distributed Multi-Node Agent Mesh & P2P Sync:**
  - Sinkronisasi status agen dan memori kerja antar-komputer lokal tanpa melalui server cloud perantara.
- [ ] **43.6 Corporate Audit & Cryptographic Compliance Ledger:**
  - Pencatatan seluruh aksi dan berkas dalam rantai hash tahan manipulasi (*tamper-proof*) untuk standar kepatuhan enterprise.
- [ ] **43.7 Dynamic Plugin & Hot-Reloading MCP Tools Engine:**
  - Integrasi Model Context Protocol (MCP) dinamis yang memungkinkan agen memuat perkakas baru tanpa mematikan runtime server.

---

#### Fase 44: Pengujian Kelayakan Pengguna (Usability Testing) & Audit Kepatuhan Final
*Target Rilis: AKSA v0.0.9-rc1*
- [ ] **44.1 Usability Testing dengan Partisipan Non-Teknis:**
  - Melakukan pengujian terstruktur dengan 5 pengguna non-teknis nyata (Section 14).
  - Mengukur kemudahan navigasi, kejelasan konfirmasi izin HITL, dan kepuasan interaksi kantor virtual.
- [ ] **44.2 Audit Keamanan & Kepatuhan Final:**
  - Verifikasi menyeluruh seluruh batas sandbox, enkripsi brankas OS, dan pemindaian kerentanan zero-day.

---

#### Fase 45: Peluncuran Publik Resmi (Public Beta ➔ Production LTS)
*Target Rilis: AKSA v0.1.0 (Public Beta) ➔ v1.0.0 (Production LTS)*
- [ ] **45.1 Rilis Public Beta (v0.1.0):**
  - Pembukaan rilis uji coba publik resmi dengan paket installer otomatis untuk Windows, macOS, dan Linux.
- [ ] **45.2 Rilis Produksi v1.0.0 Long-Term Support (LTS):**
  - Peluncuran versi stabil 1.0.0 resmi dengan dokumentasi lengkap, panduan korporat, dan garansi stabilitas jangka panjang.

---

## 3. Matriks Peluncuran & Target Rilis

| Versi | Target Fase | Status | Target Lingkungan | Fitur Utama |
| :--- | :---: | :---: | :--- | :--- |
| **v0.0.2** | Fase 37 | **SELESAI (Aktif)** | Windows GUI, macOS GUI, Linux GUI, Linux CLI | Fondasi Multi-Agen, Office Engine, RAG Hibrida, Audit Keamanan 100%, Windows .exe Installer |
| **v0.0.3-alpha** | Fase 38 | *Mendatang* | Desktop GUI & Remote Chat | Autonomous Scheduler Engine (Cron & NLP), Multi-Channel HITL Gate |
| **v0.0.4-alpha** | Fase 39 | *Mendatang* | Cloud Integration | Google Workspace Connector (Drive, Sheets, Docs, Calendar, Gmail) |
| **v0.0.5-alpha** | Fase 40 | *Mendatang* | Social Hub | Social Media Connectors (LinkedIn, X, Meta) & Zero Unapproved Post Policy |
| **v0.0.6-alpha** | Fase 41 | *Mendatang* | Visual Workspace | 2.5D Virtual Office Canvas, Live Activity Animations, Spatial Agent Floor Plan |
| **v0.0.7-alpha** | Fase 42 | *Mendatang* | Distributed & Mobile | AKSA Core Server Decoupling, Dedicated Mobile Client (Android & iOS Biometric HITL) |
| **v0.0.8-alpha** | Fase 43 | *Mendatang* | Enterprise OS | Whisper Voice Briefing, Self-Healing Data Doctor, Smart OCR, P2P Sync, Audit Ledger |
| **v0.0.9-rc1** | Fase 44 | *Mendatang* | Candidate Release | Usability Testing 5 Partisipan Non-Teknis & Final Compliance Certification |
| **v0.1.0** | Fase 45.1 | *Mendatang* | Public Beta | Rilis Publik Beta Terbuka Multi-Platform (Windows, macOS, Linux, Mobile Companion) |
| **v1.0.0** | Fase 45.2 | *Mendatang* | Production LTS | Versi Stabil Korporat & Dukungan Jangka Panjang (Long-Term Support) |

---

## 4. Standar Rekayasa & Protokol Transisi Sesi

Setiap agen pengembang AI yang melanjutkan pekerjaan pada repositori ini **WAJIB** mematuhi ketentuan berikut:

1. **Pemeriksaan Status Awal:** Selalu periksa `PROGRESS.md` dan `ROADMAP.md` sebelum memulai pekerjaan.
2. **Aturan Bahasa:** Kode, identifier, commit message, dan dokumentasi teknis dalam **Bahasa Inggris**; seluruh teks UI, pesan kesalahan, dialog, dan konfirmasi dalam **Bahasa Indonesia** formal dan alami.
3. **Standar Ikon Bebas-Emoji:** Dilarang menggunakan emoji Unicode statis dalam antarmuka grafis atau CLI. Gunakan ikon vektor `lucide-react` dan animasi `framer-motion`.
4. **Verifikasi Bertahap:** Setiap penambahan modul wajib diverifikasi dengan suite pengujian (`pytest`, `vitest`, `cargo test`, dan `tsc --noEmit`).
5. **Pembaruan Berkelanjutan:** Segera tandai `[x]` pada `PROGRESS.md` dan `ROADMAP.md` setelah menyelesaikan suatu fase atau sub-tugas.
