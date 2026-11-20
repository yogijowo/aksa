<div align="center">

<a href="#aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# AKSA
### Asisten Kerja &amp; Sistem Automasi — AI Desktop Operating System &amp; Digital Headquarters
*(Hierarchical Multi-Agent Team, Distributed Server-Client Topology, Office Engine, Autonomous Scheduler &amp; Enterprise Security Baseline)*

<p align="center">
  <a href="./README.en.md"><img src="https://img.shields.io/badge/Read_in-English-D97757?style=for-the-badge" alt="English Documentation"></a>
  <img src="https://img.shields.io/badge/Versi_Saat_Ini-v0.0.2_(Pre--Beta_Alpha)-3B82F6?style=for-the-badge" alt="Versi Saat Ini v0.0.2">
  <img src="https://img.shields.io/badge/Status-Fase_37_Aktif-F59E0B?style=for-the-badge" alt="Fase 37 Aktif">
  <img src="https://img.shields.io/badge/Audit_Keamanan-Siklus_14_Lolos_100%25-10B981?style=for-the-badge" alt="Security Audit Cycle 14">
  <img src="https://img.shields.io/badge/GUI-Windows_%7C_macOS_%7C_Linux-21211F?style=for-the-badge" alt="Desktop GUI">
  <img src="https://img.shields.io/badge/CLI_&_Server-Linux_Headless_Daemon-21211F?style=for-the-badge" alt="Linux CLI Headless">
  <img src="https://img.shields.io/badge/Klien_Mobile-Roadmap_Android_&_iOS-21211F?style=for-the-badge" alt="Mobile Client Roadmap">
  <img src="https://img.shields.io/badge/Pengujian-325_Passed-10B981?style=for-the-badge" alt="325 Tests Passed">
</p>

<p align="center">
  <b>Sistem operasi kerja AI lokal yang beroperasi langsung di komputer Anda — mendukung arsitektur Server-Client terdistribusi (Desktop GUI Windows/macOS/Linux, Server Headless CLI Linux 24/7, dan Klien Mobile Android/iOS mendatang) — dengan tim agen otonom bertingkat, otomatisasi dokumen Office nyata, gateway kendali jarak jauh multi-kanal, dan isolasi privasi lokal 100%.</b><br>
  AKSA menghubungkan model AI tercanggih (cloud maupun 100% offline lokal) dengan file kerja, spreadsheet, jadwal rutin, dan aplikasi harian Anda tanpa pernah membocorkan data pribadi atau melakukan tindakan berisiko tanpa izin eksplisit Anda.
</p>

[Visi & Arah Masa Depan](#-visi-aksa-akan-menjadi-apa-ke-depan) • [Posisi & Skor Kematangan Saat Ini](#-posisi-status--skor-kematangan-saat-ini-v002) • [Topologi Server & Klien](#-topologi-arsitektur-aksa-server--dedicated-clients) • [Pusat Akses Jarak Jauh Multi-Kanal](#-pusat-akses-jarak-jauh-multi-kanal-omni-channel-gateway) • [Inovasi Arsitektur & Kapabilitas Inti](#-inovasi-arsitektur--kapabilitas-inti-aksa) • [Fitur Utama Saat Ini](#-fitur-utama-saat-ini) • [Peta Jalan Pengembangan (Roadmap)](#-peta-jalan-pengembangan-roadmap) • [Panduan Memulai Cepat](#-panduan-memulai-cepat-quickstart) • [Dokumentasi Lengkap](#-dokumentasi-lengkap--spesifikasi-domain)

<br>

<img src="./docs/assets/desktop.webp" alt="Tampilan Antarmuka AKSA Desktop — Perancang Hirarki Tim Agen Bertingkat" width="100%">

</div>

---

## 🏛️ Visi: AKSA Akan Menjadi Apa ke Depan?

Mayoritas asisten AI saat ini hanya berbentuk jendela *chat* pasif di browser web yang terpisah dari struktur berkas di komputer Anda dan melupakan konteks pekerjaan segera setelah jendela ditutup. Sebaliknya, agen otomasi yang diberi kebebasan tanpa pagar pembatas berisiko merusak sistem operasi atau membocorkan dokumen rahasia.

**AKSA dirancang untuk menjadi Digital Headquarters & Autonomous Co-Worker Anda:**

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AKSA DIGITAL HEADQUARTERS                             │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│    KANTOR VIRTUAL       │   PENJADWALAN OTONOM    │   KONEKTOR EKOSISTEM    │
│  (Visual Office Canvas) │   (Autonomous Scheduler)│ (Cloud & Social Media)  │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Denah kantor 2.5D visual│ Menjalankan tugas rutin │ Terhubung langsung ke   │
│ interaktif; agen tampak │ berkala (Cron & bahasa  │ Google Workspace (Drive,│
│ bekerja di meja, rapat, │ alami) dengan konfirmasi│ Sheets, Docs, Calendar, │
│ santai, atau butuh izin │ multi-channel (Desktop, │ Gmail) & publikasi medsos│
│ pengguna secara nyata.  │ Mobile, & Chat Gateway).│ (LinkedIn, X, Meta).    │
├─────────────────────────┴─────────────────────────┴─────────────────────────┤
│                          MESIN EKSEKUSI LOKAL                               │
│  • Automasi Office Nyata (Excel rumus & grafik, Word naskah dinas, PPT, PDF)│
│  • Topologi Server-Client: GUI Desktop, Server Headless CLI, & Klien Mobile │
│  • Perlindungan Sandbox Path Jail & Pencadangan Otomatis (.aksa_backup/)    │
│  • Multi-Model Router (Gemini, Claude, GPT, DeepSeek, Ollama, LM Studio)    │
│  • Kerahasiaan 100% Lokal (Zero Silent Cloud Fallback & Enkripsi DPAPI/Keyring)│
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Rekan Kerja Visual, Bukan Sekadar Chatbot:** Pengguna dapat melihat representasi visual interaktif tempat agen-agen AI bekerja, mengetahui secara instan siapa yang sedang menganalisis data, siapa yang menyusun laporan, dan siapa yang membutuhkan persetujuan Anda.
2. **Bekerja Proaktif Secara Mandiri:** Berikan tugas rutin satu kali (*"Setiap hari Senin jam 08:00, rekap data penjualan mingguan dari folder laporan, buatkan presentasi PPT, dan siapkan draf emailnya"*), dan AKSA akan mengeksekusinya tepat waktu dengan gerbang persetujuan aman.
3. **Topologi Fleksibel: Server Mandiri & Klien Dedicated:** AKSA Core Server dapat beroperasi lokal di PC kerja maupun 24/7 di Linux Server / VPS, dan dapat diakses melalui Desktop GUI native, aplikasi Mobile native (Android/iOS), maupun gateway perpesanan aman.
4. **Kedaulatan Privasi 100%:** Beroperasi lokal (*local-first*). Data Anda tidak pernah dikirim diam-diam ke cloud, dan penggunaan model AI lokal (Ollama / LM Studio) menjamin pemrosesan 100% tanpa internet.

---

## 📊 Posisi, Status & Skor Kematangan Saat Ini (v0.0.2)

### Laporan Status Jujur & Transparan (Honest Status Disclosure)
* **Fase Saat Ini:** **Fase 37 — Pre-Beta Alpha (Versi 0.0.2)**.
* **Status Kematangan:** Fondasi sistem inti, pengujian otomatis, dan audit keamanan telah selesai 100%. Namun, aplikasi ini **belum dirilis sebagai versi produksi umum (belum v1.0.0)** karena masih dalam tahap pengujian privat internal sebelum memasuki *Public Beta (v0.1.0)*.
* **Keterbatasan Saat Ini yang Perlu Diketahui:**
  1. *Pengujian Kegunaan Eksternal:* Pengujian langsung dengan 5 partisipan non-teknis (Usability Testing Section 14) masih berstatus *"belum diuji secara langsung dengan manusia"*.
  2. *Status Fitur Baru:* Fitur Kantor Virtual (Pilar 1), Scheduler (Pilar 2), Konektor Ekosistem (Pilar 3), dan Klien Mobile saat ini telah selesai pada tahap spesifikasi arsitektur teknis lengkap ([`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) dan [`ROADMAP.md`](./ROADMAP.md)) dan sedang dijadwalkan untuk implementasi bertahap di Fase 38+.

### Tabel Skor & Metrik Verifikasi Nyata

| Dimensi Evaluasi | Skor / Metrik Riil | Status | Bukti Verifikasi |
| :--- | :---: | :---: | :--- |
| **Audit Keamanan & Integritas OS** | **100% Lulus** | Terverifikasi | Lolos 14 siklus re-audit independen ([`docs/AKSA — Independent Re-Audit Siklus 14.md`](./docs/AKSA%20—%20Independent%20Re-Audit%20Siklus%2014.md)). Zero-trust sidecar handshake, DPAPI/Keychain vault, path traversal jail, dan anti-replay HITL tokens. |
| **Suite Pengujian Backend (Python Pytest)** | **291 Passed** / 4 Skipped | Terverifikasi | 291 skenario lulus sempurna di mesin Python engine (4 skenario khusus kernel sandbox Windows/Linux dilewati pada macOS runner). |
| **Suite Pengujian Frontend (React Vitest)** | **16 Passed** (100%) | Terverifikasi | Pengujian unit Zustand store, hidrasi database awal, dan validasi identitas engine sidecar lulus dalam 1.1 detik. |
| **Integritas Shell Desktop (Tauri v2 Rust)** | **18 Passed** (100%) | Terverifikasi | `cargo check` dan `cargo test` selesai tanpa galat (*zero errors*) pada target native. |
| **Kompilasi TypeScript & Bundle Vite** | **0 Errors** (Bersih) | Terverifikasi | `tsc --noEmit && vite build` selesai dalam 2.5 detik; pemisahan chunk produksi optimal. |
| **Audit Pasokan Dependensi (Supply Chain)** | **0 Vulnerabilities** | Terverifikasi | `npm audit --omit=dev --audit-level=high` bersih tanpa celah keamanan kritis. |
| **Efisiensi Penggunaan Token** | **Hemat 28% – 80%** | Terverifikasi | Penghematan biaya API nyata melalui isolasi konteks sub-agen, pemanggilan alat dinamis (*lazy tools*), dan pemadatan konteks bergulir (*rolling compaction*). |

---

## 🌐 Topologi Arsitektur: AKSA Server & Dedicated Clients

AKSA mengadopsi pemisahan arsitektur modern antara **Mesin Host (AKSA Core Server)** dan **Aplikasi Klien Dedicated**:

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
   * Mesin komputasi utama berbasis Python FastAPI, SQLite, dan sandbox terisolasi yang mengelola eksekusi orkestrasi agen, pembuatan dokumen Office, RAG semantik, scheduler, dan audit ledger.
   * Dapat dijalankan langsung di workstation pengguna (Windows, macOS, Linux) atau beroperasi 24/7 sebagai *headless daemon / service* di Linux Server, homelab, VPS, atau container Docker tanpa display grafis.
2. **AKSA Desktop Client (Windows, macOS, Linux):**
   * Antarmuka visual native berbasis Tauri v2 dan React 19 yang terhubung secara aman ke AKSA Core Server (baik lokal pada mesin yang sama maupun server terdistribusi).
   * Menyajikan kanvas Kantor Virtual 2.5D, diagram hierarki agen (@xyflow/react), panel inspektur berkas, dan dialog izin desktop.
3. **AKSA Mobile Client (Tahap Pengembangan Mendatang: Android & iOS):**
   * Aplikasi mobile native terenkripsi *end-to-end* yang berfungsi sebagai pusat kendali bergerak (*mobile command center*):
     * Memantau aktivitas kerja tim agen di kantor virtual secara *real-time*.
     * Memberikan konfirmasi persetujuan izin Human-in-the-Loop (HITL) satu sentuhan via sensor biometrik perangkat (*fingerprint* / FaceID).
     * Menerima notifikasi tugas berkala dan mendiktekan instruksi kerja via teks/suara saat bepergian.

---

## 📡 Pusat Akses Jarak Jauh Multi-Kanal (Omni-Channel Gateway)

AKSA tidak membatasi pengguna pada satu aplikasi atau satu platform tertentu. Sistem dilengkapi dengan arsitektur **Omni-Channel Remote Command Gateway** yang modular dan agnostik terhadap platform perpesanan:

1. **Arsitektur Gateway Modular:**
   * Gateway dirancang dengan lapisan abstraksi adaptor (*adapter layer*). Sistem dapat dihubungkan ke berbagai platform perpesanan modern yang aman, seperti Telegram, WhatsApp (Business API / protocol bridging), Discord Webhooks, Slack, Matrix, maupun sistem Webhook internal perusahaan.
2. **Telegram sebagai Adaptor Referensi Siap Pakai:**
   * Saat ini, Telegram difungsikan sebagai salah satu adaptor referensi utama yang sudah terpasang dan siap digunakan (*out-of-the-box*) dengan mekanisme keamanan kode pairing 6-digit dan whitelist akun numerik terverifikasi.
3. **Kendali Penuh dari Jarak Jauh:**
   * Pengguna dapat mengirim instruksi kerja, mengunggah dokumen dari smartphone ke folder PC, menerima dokumen hasil kerja (.xlsx, .docx, .pptx, .pdf), serta menyetujui tindakan berisiko (HITL) langsung melalui tombol interaktif di aplikasi chat pilihan pengguna.

---

## ⚡ Inovasi Arsitektur & Kapabilitas Inti AKSA

Untuk menghadirkan sistem operasi kerja cerdas yang berdaulat, aman, dan efisien, AKSA mengintegrasikan pilar kapabilitas tingkat lanjut:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                 KAPABILITAS INTI & INOVASI ARSITEKTUR MASA DEPAN            │
├─────────────────────────┬─────────────────────────┬─────────────────────────┤
│   1. VOICE-TO-ACTION    │   2. DATA & DOC DOCTOR  │   3. SMART SCANNER OCR  │
│  Ambient Audio Briefing │  Self-Healing Documents │ Scan Kwitansi -> Excel  │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Dikte suara lokal via   │ Mendeteksi & memperbaiki│ Membaca foto struk/nota/│
│ Whisper; AKSA membacakan│ otomatis formula Excel  │ PDF scan fisik, otomatis│
│ ringkasan kerja harian  │ error (#REF!, #DIV/0!)  │ diubah menjadi tabel data│
│ secara hands-free.      │ dan data tabel korup.   │ dan draf pembukuan rapi.│
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│   4. DEEP WORK SHIELD   │   5. P2P MESH SYNC      │  6. AUDIT COMPLIANCE    │
│ Focus Guard Throttling  │ Sinkronisasi Tanpa Cloud│ Tamper-Proof Hash Chain │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Menahan interupsi saat  │ Sinkronisasi memori tim │ Mencatat seluruh mutasi │
│ pengguna sedang fokus,  │ antar-node PC & server  │ berkas & persetujuan izin│
│ menyajikan ringkasan    │ via P2P lokal terenkripsi│ ke ledger kriptografis  │
│ berkala saat senggang.  │ tanpa perantara cloud.  │ untuk audit kepatuhan.  │
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│    7. KANTOR VIRTUAL    │  8. SCHEDULER OTONOM    │  9. DYNAMIC MCP PLUGINS │
│ 2.5D Visual Agent Floor │ Cron & Rutinitas Proaktif│ Hot-Reloading MCP Tools│
├─────────────────────────┼─────────────────────────┼─────────────────────────┤
│ Agen tampak beraktivitas│ Menjalankan tugas rutin │ Memperluas alat kerja   │
│ di meja, ruang rapat, & │ berkala berpagar izin   │ agen secara dinamis     │
│ gestur interaksi nyata. │ multi-channel aman.     │ tanpa restart server.   │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

1. **Voice-to-Action & Ambient Executive Audio Briefing (Whisper & Piper TTS Lokal):**
   * Perintahkan agen cukup dengan berbicara langsung melalui mikrofon komputer menggunakan model Whisper lokal (100% offline tanpa cloud).
   * Agen dapat membacakan ringkasan eksekutif pagi hari (*audio executive briefing*) secara *hands-free* saat Anda sedang mempersiapkan pekerjaan.
2. **Self-Healing Document & Data Doctor (Pemulihan Berkas Otomatis):**
   * Saat membaca file Excel atau data tabel yang berantakan, formula rusak (`#REF!`, `#DIV/0!`), atau sel kosong yang tidak konsisten, AKSA tidak berhenti bekerja. Agen *Data Doctor* secara cerdas mendeteksi anomali, membersihkan data kotor, menyambung kembali rumus yang putus, dan menyajikan audit perbaikan untuk disetujui.
3. **Multimodal Smart Scanner & OCR (Kwitansi & Faktur Pajak):**
   * Cukup letakkan berkas foto struk belanja, invoice faktur pajak, atau pindaian dokumen fisik PDF di folder kerja. AKSA otomatis mengekstraksi data angka, tanggal, dan nama entitas menjadi rekap tabel Excel terstruktur dan siap dilaporkan.
4. **Deep Work & Focus Guard (Perlindungan Konsentrasi Kerja):**
   * Ketika mendeteksi pengguna sedang fokus mengetik atau memprogram, AKSA menahan notifikasi interupsi non-kritis di latar belakang dan merangkumnya menjadi laporan ringkas saat pengguna selesai.
5. **Distributed Multi-Node Agent Mesh & P2P Local Sync:**
   * Sinkronisasi memori kerja agen dan profil tim antar-komputer pengguna (misal: laptop Windows di kantor, MacBook di rumah, dan homelab Linux server) secara terenkripsi *peer-to-peer* (E2EE) tanpa server perantara pihak ketiga.
6. **Corporate Audit & Cryptographic Compliance Ledger:**
   * Setiap mutasi berkas, pembacaan data, dan persetujuan izin dicatat dalam rantai hash kriptografis yang tahan manipulasi (*tamper-proof*), siap diekspor sewaktu-waktu untuk kepatuhan audit perusahaan (ISO 27001, UU PDP Indonesia, SOX).
7. **Kantor Virtual 2.5D (Visual Agent Canvas & Spatial Workspace):**
   * Representasi visual interaktif di mana agen digambarkan bekerja di meja masing-masing, berkumpul di ruang rapat saat berkolaborasi, santai saat *idle*, dan melambaikan tangan saat memerlukan izin persetujuan pengguna.
8. **Mesin Penjadwalan Otonom & Rutinitas Proaktif:**
   * Eksekusi jadwal rutin otonom menggunakan instruksi bahasa alami atau ekspresi Cron standar yang diproteksi kartu persetujuan multi-kanal (Desktop, Mobile, Chat).
9. **Arsitektur Dynamic Plugin & Hot-Reloading MCP Tools Engine:**
   * Memungkinkan sistem memperluas keahlian dan alat kerja agen secara modular melalui ekosistem standar Model Context Protocol (MCP) dan plugin lokal tanpa perlu mematikan atau me-restart server.

---

## 🛠️ Fitur Utama Saat Ini

### 1. Orkestrasi Tim Multi-Agen Bertingkat & Efisiensi Token
* **Hirarki Supervisor & Sub-Agen:** Manajer Eksekutif mengurai instruksi rumit, mendelegasikan tugas ke sub-agen spesialis (Analis Data, Penyusun Dokumen, Peneliti Berkas), dan mengonsolidasikan hasil akhir.
* **Isolasi Konteks Sub-Agen:** Sub-agen menjalankan perputaran alat (*tool-loop*) di ruang kerja terisolasi. Hanya ringkasan terstruktur dan berkas hasil yang diserahkan kembali ke Supervisor, menjaga jendela konteks tetap bersih dan hemat token hingga 80%.
* **Deteksi Konteks Percakapan Multi-Turn:** Mampu memahami instruksi rujukan lanjutan (misal: *"dari data Excel tadi, tolong ubah jadi presentasi PPT"* tanpa kehilangan konteks file sumber).

### 2. Mesin Otomasi Dokumen Nyata (Office & PC Engine)
* **Microsoft Excel (`.xlsx`):** Menganalisis isi sheet, header, dan ribuan baris data, menyusun tabel bergaya korporat, memformat angka Rupiah (`Rp`), menulis formula aktif (`=SUM`, `=AVERAGE`, `=VLOOKUP`), dan menyematkan grafik Bar/Line/Pie.
* **Microsoft Word (`.docx`):** Menghasilkan surat resmi, naskah dinas, draf kontrak perjanjian kerjasama (MoU), laporan berkala dengan penataan gaya teks formal dan tabel rapi.
* **Microsoft PowerPoint (`.pptx`):** Menyusun presentasi eksekutif berbasis data riil dari berkas spreadsheet, mencakup slide judul, ringkasan tinjauan data, tabel sampel terformat, dan kesimpulan strategis.
* **Format PDF & Ekstraksi Teks:** Mengekstraksi teks dokumen PDF tebal ke format Markdown, menghasilkan laporan PDF berstandar cetak, serta menggabungkan atau memecah berkas.

### 3. Keamanan Sandboxing & Persetujuan Berjenjang (HITL Gate)
* **Path Jail & Pencadangan Otomatis:** Agen hanya diizinkan membaca dan menulis di dalam folder kerja yang telah dipilih pengguna (`allowed_paths`). Sebelum berkas kerja yang sudah ada diubah, sistem otomatis membuat salinan cadangan di `.aksa_backup/`.
* **Human-in-the-Loop (HITL) Approval:** Tindakan berisiko tinggi otomatis memunculkan dialog persetujuan (*approval card*) di desktop atau saluran remote. Tanpa persetujuan eksplisit, tindakan akan dibatalkan (*fail-closed*).
* **Penyaring Privasi Otomatis:** Menyensor informasi sensitif (kunci API, Bearer token, NIK 16 digit, NPWP, nomor rekening, nomor telepon) sebelum data disimpan ke memori lokal atau dikirim ke LLM.

### 4. Router Multi-Model Fleksibel (Cloud & 100% Offline Lokal)
* **Penyedia Cloud Resmi:** Mendukung Google Gemini, Anthropic Claude, OpenAI, DeepSeek, Groq Cloud, OpenRouter, Mistral, dan xAI Grok.
* **Model AI Lokal Gratis (Ollama & LM Studio):** Jalankan model canggih seperti `qwen2.5:7b`, `deepseek-r1:8b`, atau `llama3.1:8b` langsung di komputer Anda tanpa biaya langganan API dan 100% beroperasi tanpa internet.
* **Zero Silent Cloud Fallback:** Saat memilih model lokal atau mengaktifkan mode `local_only`, sistem menjamin data Anda tidak akan dialihkan ke cloud dalam kondisi apa pun.

### 5. Basis Pengetahuan RAG Hibrida Lokal
* **Pencarian Semantik Hibrida (LanceDB + SQLite FTS5):** Menemukan informasi di ribuan berkas kerja lokal dengan memadukan pencarian vektor semantik dan pencarian kata kunci eksak (BM25) dengan pemantau perubahan folder *real-time*.

---

## 🗺️ Peta Jalan Pengembangan (Roadmap)

Rencana pengembangan menyeluruh AKSA terbagi dalam tahapan rekayasa terstruktur dari awal hingga rilis produksi jangka panjang. Cetak biru lengkap dapat dilihat pada [**`ROADMAP.md`**](./ROADMAP.md) dan [`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md):

* **Fase 0 – 37 (Fondasi Inti Rampung — Status: v0.0.2 Pre-Beta Alpha):**
  * Multi-agent hierarchy, sandbox path jail, pemulihan cadangan otomatis (`.aksa_backup/`), Office engine nyata (Excel rumus & grafik, Word naskah dinas, PPT data-driven, PDF), RAG hibrida, remote command gateway, dan 14 siklus audit keamanan enterprise.
* **Fase 38: Autonomous Scheduler Engine & Multi-Channel HITL Gate:**
  * Penjadwalan berkala otomatis berbasis Cron dan bahasa alami dengan kartu persetujuan interaktif (Desktop & Remote Chat).
* **Fase 39: Google Workspace Ecosystem Connector:**
  * Integrasi Google Drive, Docs, Sheets sinkronisasi dua arah, Google Calendar, dan draf Gmail berpagar HITL.
* **Fase 40: Hub Media Sosial & Spesialis Komunikasi:**
  * Konektor LinkedIn, X, Meta Graph dengan kartu pratinjau konten dan aturan *Zero Unapproved Post*.
* **Fase 41: AKSA Virtual Office Experience:**
  * Denah kantor isometrik visual 2.5D dengan animasi status aktivitas agen *real-time* (mengetik, santai, rapat, minta izin).
* **Fase 42: Topologi Terdistribusi & Klien Mobile AKSA:**
  * Pemisahan arsitektur AKSA Core Server dan pengembangan Klien Mobile native (Android & iOS) dengan persetujuan biometrik satu sentuhan.
* **Fase 43: Inovasi Kapabilitas Tingkat Lanjut:**
  * Voice-to-Action lokal (Whisper), Self-Healing Data Doctor, Smart OCR Scanner kwitansi, dan P2P Mesh sync.
* **Fase 44: Usability Testing Partisipan Nyata & Sertifikasi Kepatuhan Final:**
  * Pengujian kegunaan terstruktur dengan 5 pengguna non-teknis nyata.
* **Fase 45: Peluncuran Publik Resmi:**
  * Peluncuran **v0.1.0 Public Beta** $\rightarrow$ rilis stabil **v1.0.0 Production LTS**.

---

## 🚀 Panduan Memulai Cepat (Quickstart)

### Prasyarat Sistem:
* **Node.js:** Versi 20.x atau 22.x LTS ([nodejs.org](https://nodejs.org/))
* **Python:** Versi 3.12+ ([python.org](https://python.org/))
* **Rust (Opsional):** Diperlukan jika ingin mengompilasi jendela desktop native via Tauri ([rustup.rs](https://rustup.rs/))
* **Ollama (Opsional):** Untuk menjalankan model AI lokal 100% gratis & offline ([ollama.com](https://ollama.com/))

---

### Langkah Instalasi:

```bash
# 1. Klon repositori
git clone https://github.com/yogijowo/aksa.git
cd aksa

# 2. Pasang dependensi frontend desktop
npm --prefix apps/desktop install

# 3. Siapkan environment Python untuk backend sidecar
cd services/engine
python -m venv .venv

# Aktifkan virtual environment:
# Windows (cmd/PowerShell):
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Pasang dependensi engine:
pip install -e ".[dev]"
cd ../..
```

---

### Menjalankan AKSA Sesuai Kebutuhan Lingkungan:

#### 1. Mode Cepat Web Browser (Windows, macOS, Linux — Tanpa Butuh Rust)
Menjalankan antarmuka React di browser web dan backend Python FastAPI secara lokal:
```bash
npm run dev
# Buka di browser: http://localhost:1420
```

#### 2. Mode Desktop GUI Native (Windows, macOS, Linux — Membutuhkan Rust)
Menjalankan aplikasi sebagai jendela desktop native dengan integrasi System Tray dan dialog izin OS:
```bash
npm run dev:tauri
```

#### 3. Mode Headless Server / CLI di Linux (Server, VPS, Docker — Tanpa Display/GUI)
Menjalankan mesin engine AKSA sebagai layanan latar belakang di Linux server tanpa antarmuka grafis. Seluruh tugas dapat dikendalikan dari jarak jauh melalui remote gateway atau REST/WebSocket API:
```bash
cd services/engine
source .venv/bin/activate
python -m app.main --host 0.0.0.0 --port 43120 --production
```

---

### Menjalankan Suite Pengujian & Verifikasi:
```bash
# Uji unit antarmuka frontend (Vitest):
npm --prefix apps/desktop run test

# Verifikasi kompilasi TypeScript ketat & bundle produksi Vite:
npm --prefix apps/desktop run build

# Uji biner Rust native Tauri:
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml

# Uji backend Python engine (295 skenario pengujian):
cd services/engine && pytest
```

---

## 📚 Dokumentasi Lengkap & Spesifikasi Domain

Seluruh rincian teknis, standar kode, dan arsitektur terdokumentasi rapi di dalam direktori [`docs/`](./docs/):

* [**`ROADMAP.md`**](./ROADMAP.md) — **Master Peta Jalan Pengembangan Lengkap (Fase 1 s/d Fase 45).**
* [**`docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md`**](./docs/09-PRD-VIRTUAL-OFFICE-SCHEDULER-CONNECTORS.md) — **PRD Lengkap:** Virtual Office Canvas, Autonomous Scheduler & Konektor Google/Medsos.
* [**`AGENTS.md`**](./AGENTS.md) — Pedoman utama arsitektur, konvensi kode (Code in English, UI in Bahasa Indonesia), dan aturan kerja AI.
* [**`PROGRESS.md`**](./PROGRESS.md) — Pelacak progres pengembangan live, riwayat sesi, dan status tugas terkini.
* [**`docs/01-ARCHITECTURE.md`**](./docs/01-ARCHITECTURE.md) — Arsitektur terpadu Tauri v2 (Rust) + Python FastAPI Sidecar.
* [**`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`**](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md) — Orkestrasi agen bertingkat & optimasi token.
* [**`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`**](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md) — Mesin dokumen Office (Word, Excel, PPT, PDF) & Sandbox.
* [**`docs/04-RAG-AND-MEMORY-SYSTEM.md`**](./docs/04-RAG-AND-MEMORY-SYSTEM.md) — Mesin pencarian hibrida lokal (LanceDB + SQLite FTS5).
* [**`docs/05-TELEGRAM-GATEWAY.md`**](./docs/05-TELEGRAM-GATEWAY.md) — Arsitektur pusat kendali jarak jauh melalui remote gateway.
* [**`docs/06-UI-UX-DESIGN-SYSTEM.md`**](./docs/06-UI-UX-DESIGN-SYSTEM.md) — Sistem desain Warm Obsidian / Paper Light & glosarium UI Indonesia.
* [**`docs/07-DATABASE-AND-API-SCHEMA.md`**](./docs/07-DATABASE-AND-API-SCHEMA.md) — Skema database SQLite & kontrak REST/WebSocket API.
* [**`docs/08-ROADMAP-AND-PHASES.md`**](./docs/08-ROADMAP-AND-PHASES.md) — Peta implementasi rekayasa bertahap.
* [**`SECURITY.md`**](./SECURITY.md) • [**`PRIVACY.md`**](./PRIVACY.md) • [**`SUPPORT.md`**](./SUPPORT.md)

---

## Lisensi

Didistribusikan di bawah lisensi resmi **[MIT License](./LICENSE)**. Seluruh kode sumber terbuka untuk dipelajari, dikembangkan, dan dimanfaatkan secara bebas.
