<div align="center">

<a href="#-aksa">
  <img src="./assets/banner.svg" alt="AKSA - Asisten Kerja &amp; Sistem Automasi" width="100%">
</a>

# ⚡ AKSA
### Asisten Kerja &amp; Sistem Automasi — AI Desktop Operating Assistant Indonesia
*(Local-First AI Desktop Operating Assistant, App Intelligence, OS Permissions &amp; Remote Command Center)*

<p align="center">
  <a href="./README.en.md"><img src="https://img.shields.io/badge/🌐_Read_in-English-6366F1?style=for-the-badge" alt="English Documentation"></a>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%2F11%20%7C%20macOS-10B981?style=for-the-badge" alt="Cross Platform">
  <img src="https://img.shields.io/badge/Desktop-Tauri%20v2%20%2B%20React%2019-0EA5E9?style=for-the-badge" alt="Tauri v2 + React 19">
  <img src="https://img.shields.io/badge/Sidecar-Python%203.12%20%2B%20uv-F59E0B?style=for-the-badge" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Database-SQLite%20FTS5%20%2B%20LanceDB-8B5CF6?style=for-the-badge" alt="Hybrid RAG">
</p>

<p align="center">
  <b>Asisten kecerdasan desktop (AI Desktop Operating Assistant) yang beroperasi langsung di PC Anda.</b><br>
  Bukan sekadar AI agent pembaca folder — AKSA mendeteksi aplikasi perangkat yang terpasang, mengelola izin native sistem operasi secara transparan, memperluas kapabilitas melalui keahlian portabel (Agent Skills), mengolah dokumen perkantoran, dan dapat dikendalikan dari jarak jauh lewat Telegram smartphone Anda.
</p>

[Fitur Utama](#-fitur-utama) • [Arsitektur Desktop Intelligence](#-arsitektur-kecerdasan-desktop-aksa) • [Arsitektur Sistem](#️-arsitektur-sistem) • [Panduan Cepat](#-panduan-memulai-cepat-quickstart) • [Keamanan & Privasi](#-keamanan-privasi-lokal--transparansi-model) • [Dokumentasi Lengkap](#-dokumentasi-teknis--spesifikasi-arsitektur)

</div>

---

## 🌟 Mengapa AKSA Berbeda?

Mayoritas AI saat ini hanya berupa kotak obrolan di peramban web (*web chatbot*) yang terisolasi dari aplikasi dan berkas kerja Anda di komputer. Setiap kali ingin membuat laporan atau mengoperasikan program, Anda harus menyalin-menempel teks secara manual dan merapikan semuanya sendiri.

**AKSA (Asisten Kerja & Sistem Automasi)** dirancang sejak hari pertama sebagai **platform agen AI desktop lokal pertama di Indonesia** yang memiliki kendali dan akses kerja nyata ke dalam aplikasi serta folder yang Anda izinkan di komputer:

1. **Automasi Aplikasi & Dokumen Kerja Nyata:** Tidak hanya memberi saran teks, AKSA mampu mengontrol aplikasi di perangkat Anda serta langsung menghasilkan file nyata seperti spreadsheet analitis (**Excel / `.xlsx`** lengkap dengan formula & grafik), dokumen formal (**Word / `.docx`** standar administrasi), presentasi visual (**PowerPoint / `.pptx`**), hingga berkas **PDF**.
2. **Pencarian Dokumen Hibrida (RAG Lokal):** Membaca ribuan halaman dokumen PDF, arsip regulasi, dan data kantor Anda dalam hitungan detik secara 100% lokal tanpa biaya server eksternal.
3. **Kendali Jarak Jauh via Telegram:** Sedang di perjalanan atau rapat di luar kantor? Cukup kirim pesan teks atau **pesan suara (Voice Note)** ke Bot Telegram pribadi Anda, AKSA di PC rumah/kantor akan langsung mengerjakannya dan mengirimkan file hasilnya kembali ke HP Anda.
4. **Efisiensi Token Ekstrem:** Menghemat kuota dan biaya API hingga **80%** menggunakan arsitektur isolasi konteks sub-agen dan pemuatan keahlian malas (*lazy tool loading*).

---

## ✨ Fitur Utama

### 🕸️ 1. Kanvas Hierarki Agen Bertingkat (Visual Multi-Agent Builder)
* **Struktur Tim Eksekutif:** Bangun tim kerja digital yang terdiri dari **Manajer Eksekutif (Supervisor)** dan **Sub-Agen Spesialis** (Administrasi Office, Riset Dokumen RAG, Operator PC & Layar) menggunakan kanvas interaktif *drag-and-drop* (`@xyflow/react`) atau tampilan bagan organisasi yang rapi.
* **Kombinasi Bebas Model API Cloud & AI Lokal Gratis:**
  * Pasang model unggulan **Cloud API** (Claude 3.7 Sonnet, Gemini 2.5 Pro, GPT-4o, DeepSeek V3) untuk Manajer Utama yang membutuhkan penalaran kompleks.
  * Pasang model **100% Gratis & Lokal** via **Ollama** atau **LM Studio** (Qwen 2.5, Llama 3.3, DeepSeek R1) untuk sub-agen pembaca data rahasia agar data sensitif tidak pernah meninggalkan komputer Anda.

### 💻 2. Mesin Automasi PC 3-Tier Berizin Terkontrol (Workspace Sandbox)
* **Kotak Pasir Folder Aman (*Sandbox Path Jail*):** Agen hanya diizinkan membaca dan menulis di dalam folder PC yang Anda pilih (misalnya `D:\Kantor\Laporan_2026`). Akses di luar folder akan langsung diblokir secara otomatis di tingkat kernel engine.
* **Gerbang Izin Persetujuan Manusia (*Human-in-the-Loop Gateway*):** Aksi sistem berisiko tinggi (menjalankan skrip, menghapus berkas, automasi layar) wajib disetujui pengguna melalui dialog konfirmasi desktop atau tombol Telegram `[✅ Izinkan]` / `[❌ Tolak]`.
* **3 Lapisan Eksekusi PC:**
  * **Tier 1 (Direct Office Engine):** Pembuatan dan penyuntingan file Office secara instan dan rapi di latar belakang menggunakan library native (`openpyxl`, `python-docx`, `python-pptx`, `pymupdf`).
  * **Tier 2 (Native OS Bridge & uv Runner):** Interaksi langsung dengan jendela Office yang sedang terbuka (Windows COM / macOS AppleScript), eksekusi skrip Python mandiri berbasis `uv`, serta integrasi Model Context Protocol (MCP).
  * **Tier 3 (Visual Computer Use):** Membaca tampilan layar, navigasi kursor mouse, dan ketikan keyboard untuk aplikasi lama yang tidak memiliki API, dilengkapi fitur darurat *Failsafe Corner Abort* dan hotkey `Ctrl+Shift+Q`.

### ⚡ 3. Penghemat Token Cerdas (Efisiensi Biaya hingga 80%)
* **Isolasi Konteks Sub-Agen (*Context Isolation*):** Sub-agen memproses dokumen tebal dan draf mentah di ruang kerja terisolasi. Hanya ringkasan terstruktur dan berkas hasil akhir yang diserahkan ke Manajer Eksekutif.
* **Lazy Tool Loading:** Agen hanya disuntikkan skema *tools* yang relevan dengan spesialisasinya, mencegah jendela konteks penuh oleh instruksi fungsi yang tidak terpakai.
* **Pemadatan Riwayat Otomatis (*Rolling Compaction*):** Percakapan panjang dipadatkan secara berkala tanpa kehilangan poin-poin keputusan penting.

### 📚 4. Basis Pengetahuan Hibrida RAG Lokal (Zero Server Setup)
* **Pencarian Makna + Kata Kunci Eksak:** Menggabungkan **LanceDB** (*Vector Semantic Search*) dan **SQLite FTS5** (*BM25 Exact Search*) untuk menemukan nomor surat, NIK, kode nota dinas, atau kata kunci regulasi secara presisi.
* **Pemantau Berkas Otomatis (*Watchdog Folder Monitor*):** Setiap file PDF, Word, Excel, atau teks baru yang Anda masukkan ke folder kerja langsung diindeks secara inkremental menggunakan sidik jari SHA-256 tanpa perlu menekan tombol sinkronisasi manual.

### 📱 5. Pusat Kendali Jarak Jauh Telegram (Remote Command Center)
* **Kendalikan PC dari Smartphone:** Kirim pesan teks perintah kerja, unggah berkas acuan, atau kirim **Pesan Suara (Voice Note)** dalam Bahasa Indonesia dari mana saja.
* **Hasil Langsung Dikirim ke HP:** Manajer Eksekutif akan membalas dengan kemajuan kerja bertahap (*live progress*) dan melampirkan berkas hasil kerja (dokumen `.docx`, rekap `.xlsx`, laporan `.pdf`, atau foto layar PC) langsung ke ruang obrolan Telegram Anda.
* **Keamanan Akses Ketat:** Hanya akun Telegram dengan ID numerik yang terdaftar di *whitelist* dan telah diverifikasi menggunakan kode pairing 6-digit dari aplikasi desktop yang diizinkan memberi perintah.

### 🖥️ 6. Penemuan Aplikasi Desktop, Izin OS & Keahlian Agen (Agent Skills)
* **Deteksi Aplikasi Otomatis:** Memindai registri sistem operasi secara aman tanpa membutuhkan hak administrator untuk mengenali aplikasi yang terpasang (Office, Browser, Editor Teks) beserta adapter otomasi yang tersedia.
* **Pusat Izin Sistem Operasi:** Melacak status izin native platform (Accessibility, Screen Recording, File ACLs) dan persetujuan pengguna (*consent*) secara independen dengan log audit.
* **Format Standar Agent Skills (`SKILL.md`):** Mendukung pemasangan paket keahlian eksternal dengan karantina file, analisis keamanan kode statis, dan status *nonaktif secara default*.

---

## 🚀 Arsitektur Kecerdasan Desktop AKSA

AKSA menerapkan arsitektur bertingkat (*layered architecture*) yang memisahkan antara pemahaman perintah, penemuan aplikasi, perizinan OS, ekstensi keahlian, dan lapisan eksekusi lokal:

```text
                  +-------------------------------------------------------------+
                  |                     PENGGUNA / USER                         |
                  |           (Desktop UI / Telegram Smartphone)                |
                  +------------------------------+------------------------------+
                                                 |
                                                 v
                  +-------------------------------------------------------------+
                  |                   AKSA AI ORCHESTRATOR                      |
                  |        (Memahami Perintah, Memilih Aplikasi & Tools)        |
                  +------------------------------+------------------------------+
                                                 |
                                                 v
         +-----------------------+---------------+---------------+-----------------------+
         |                       |                               |                       |
         v                       v                               v                       v
+-----------------+     +-----------------+             +-----------------+     +-----------------+
| APP INTELLIGENCE|     | OS PERMISSION   |             | EXTERNAL SKILL  |     | INTEGRATION     |
| (Deteksi App    |     | BROKER          |             | MANAGER         |     | MANAGER         |
| Terpasang &     |     | (Izin Native    |             | (Agent Skills   |     | (MCP Client &   |
| Sedang Berjalan)|     | Windows/macOS)  |             | SKILL.md Aman)  |     | Adapter Native) |
+--------+--------+     +--------+--------+             +--------+--------+     +--------+--------+
         |                       |                               |                       |
         +-----------------------+---------------+---------------+-----------------------+
                                                 |
                                                 v
                  +-------------------------------------------------------------+
                  |                  NATIVE OS EXECUTION LAYER                  |
                  |    Windows / macOS · Akses Sesuai Izin · Audit · Emergency  |
                  +------------------------------+------------------------------+
                                                 |
                                                 v
                  +-------------------------------------------------------------+
                  |                    WORKSPACE SANDBOX PC                     |
                  |      Folder Kerja Diizinkan Pengguna (Path Jail & Backup)   |
                  +-------------------------------------------------------------+
```

### Pemisahan Peran & Tanggung Jawab Keamanan:
1. **AKSA AI Orchestrator:** Menerima instruksi pengguna, menyusun rencana eksekusi, memilih agen spesialis, dan menentukan alat yang relevan.
2. **App Intelligence:** Memindai registri Windows dan bundle macOS untuk mendeteksi program terpasang beserta adapter yang tersedia tanpa hak administrator.
3. **OS Permission Broker:** Meminta dan memverifikasi izin native platform (Accessibility, Screen Recording, File ACLs) secara terpisah dari konsen internal AKSA.
4. **External Skill Manager:** Memasang paket instruksi `SKILL.md` terkurasi dengan isolasi karantina arsip dan status nonaktif secara default.
5. **Integration Manager:** Menghubungkan server Model Context Protocol (MCP) dan antarmuka aplikasi native (Office COM, AppleScript).
6. **Native OS Execution Layer:** Menjalankan eksekusi terverifikasi di bawah pembatasan folder `allowed_paths`, audit logging, dan tombol *Emergency Stop*.

---

## 🏗️ Arsitektur Sistem

AKSA dibangun menggunakan pola **Hybrid Native Shell (Tauri v2) + Python FastAPI Sidecar**:

* **Frontend Desktop Shell (`apps/desktop`):** Dibangun dengan **Tauri v2 (Rust)**, **React 19**, **TypeScript**, dan **Tailwind CSS v4**. Memberikan waktu peluncuran instan, penggunaan memori RAM sangat rendah (~40–80 MB), tampilan tray sistem, dan estetika premium yang terinspirasi dari *Linear* dan *Claude Desktop*.
* **Core Sidecar Engine (`services/engine`):** Berjalan secara lokal di port `127.0.0.1:43120` menggunakan Python 3.12+ yang dikelola oleh `uv`. Mengendalikan siklus hidup multi-agen, router LiteLLM, hybrid search LanceDB + SQLite FTS5, dan bot Telegram asynchronous (`aiogram` v3).

---

## 💻 Panduan Memulai Cepat (Quickstart)

### 1. Prasyarat Sistem
Pastikan perangkat Anda telah terpasang:
* **Node.js:** Versi 20.x atau 22.x LTS ([Unduh](https://nodejs.org/))
* **Python:** Versi 3.12+ beserta [uv](https://docs.astral.sh/uv/)
* **Rust:** Versi stabil terbaru ([rustup.rs](https://rustup.rs/)) — *wajib jika ingin mengompilasi binary native Tauri*
* **Ollama (Opsional):** Jika ingin menjalankan AI lokal gratis ([ollama.ai](https://ollama.ai/))

### 2. Klon Repositori & Instalasi
```bash
# Klon repositori
git clone https://github.com/yogijowo/aksa.git
cd aksa

# Pasang dependensi frontend
npm --prefix apps/desktop install

# Siapkan virtual environment Python dengan uv
uv venv services/engine/.venv
uv pip install -r services/engine/pyproject.toml --project services/engine
```

### 3. Menjalankan di Mode Pengembang (Satu Perintah)
Gunakan skrip pengembang otomatis lintas platform:

```bash
# Jalankan Desktop Web & Backend Sidecar secara bersamaan
python scripts/dev.py

# Atau jalankan langsung sebagai Jendela Native Desktop Tauri v2
python scripts/dev.py --tauri
```
Aplikasi akan otomatis membuka antarmuka kerja di browser pada `http://localhost:5173` atau membuka jendela desktop native.

### 4. Menjalankan Pengujian Otomatis
```bash
# Pengujian Unit & Integrasi Backend (23 skenario pengujian)
uv run --project services/engine pytest services/engine/tests -v

# Pemeriksaan Tipe TypeScript & Build Frontend
npm --prefix apps/desktop run build
```

---

## 🔒 Keamanan, Privasi Lokal & Transparansi Model

AKSA memegang teguh prinsip **Kedaulatan Data Lokal (*Local-First Privacy*)**:
* **Bebas Telemetri Pihak Ketiga:** AKSA tidak memiliki pelacak (*tracking*) atau pengiriman telemetri tersembunyi ke server pengembang.
* **Transparansi Pemrosesan AI:**
  * **Model Lokal (Ollama / LM Studio):** 100% pemrosesan prompt, dokumen, dan basis data RAG berjalan sepenuhnya di komputer Anda secara luring (*offline*).
  * **Model Cloud (Gemini, OpenAI, Anthropic, DeepSeek):** Jika Anda memilih model cloud dan memasukkan API key sendiri, data percakapan dan berkas terkait hanya dikirimkan secara langsung melalui HTTPS ke penyedia API resmi yang Anda pilih.
* **Penyimpanan Kredensial Terlindungi:** Kunci API disimpan di dalam database SQLite lokal pengguna dan disamarkan di antarmuka serta respons HTTP (`••••••••••••9iYY`).
* **Proteksi WebSocket Per-Sesi:** Aliran event eksekusi agen terisolasi secara ketat berdasarkan ID sesi kerja sehingga tidak terjadi kebocoran data antar tab atau client.
* **Pusat Izin OS & Sandbox Folders:** Operasi file dibatasi pada folder kerja yang dipilih secara eksplisit (`allowed_paths`). Akses sensitif (eksekusi perintah, otomasi layar GUI) mewajibkan konfirmasi persetujuan pengguna (*Human-in-the-Loop*).

---

## 📚 Dokumentasi Teknis & Spesifikasi Arsitektur

Bagi pengembang, kontributor, dan agen AI coding, seluruh spesifikasi arsitektur mendalam tersedia di direktori [`docs/`](./docs/):

* 🤖 [**`AGENTS.md`**](./AGENTS.md) — Aturan wajib pengkodean, standar dwibahasa, dan layout repositori.
* 🏛️ [**`docs/01-ARCHITECTURE.md`**](./docs/01-ARCHITECTURE.md) — Spesifikasi interaksi IPC Tauri v2, siklus hidup sidecar, dan protokol WebSocket.
* 🧠 [**`docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md`**](./docs/02-MULTI-AGENT-AND-TOKEN-EFFICIENCY.md) — Algoritma perutean multi-agen dan 5 teknik penghematan token.
* 💻 [**`docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md`**](./docs/03-PC-AUTOMATION-AND-OFFICE-ENGINE.md) — Arsitektur 3-Tier PC Action Engine dan Human-in-the-Loop Gateway.
* 📚 [**`docs/04-RAG-AND-MEMORY-SYSTEM.md`**](./docs/04-RAG-AND-MEMORY-SYSTEM.md) — Desain mesin pencarian hibrida LanceDB + SQLite FTS5 RRF.
* 📱 [**`docs/05-TELEGRAM-GATEWAY.md`**](./docs/05-TELEGRAM-GATEWAY.md) — Protokol gateway Telegram, whitelist, dan penanganan suara.
* 🎨 [**`docs/06-UI-UX-DESIGN-SYSTEM.md`**](./docs/06-UI-UX-DESIGN-SYSTEM.md) — Standar estetika Claude Desktop / Linear dan glosarium UI Bahasa Indonesia.
* 🗄️ [**`docs/07-DATABASE-AND-API-SCHEMA.md`**](./docs/07-DATABASE-AND-API-SCHEMA.md) — Skema tabel SQLite dan kontrak REST/WebSocket endpoint.
* 🗺️ [**`docs/08-ROADMAP-AND-PHASES.md`**](./docs/08-ROADMAP-AND-PHASES.md) — Peta jalan fitur dan rekam jejak implementasi.

---

## 📄 Lisensi

AKSA didistribusikan di bawah lisensi resmi **[MIT License](./LICENSE)**. Anda bebas menggunakan, memodifikasi, dan mengembangkan perangkat lunak ini secara terbuka.
