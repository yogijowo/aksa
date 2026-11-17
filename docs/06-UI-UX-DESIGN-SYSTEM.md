# 06 — UI/UX Design System & Bahasa Indonesia Localization Guide

## 1. Design Philosophy: "Super Clean, Calm, and Powerful"

Even though AKSA combines many advanced features (Hierarchical Multi-Agent Builder, Local + API LLM Router, Office Automation, Local RAG, and Telegram Gateway), the UI **must never feel cluttered or intimidating**.

Our visual benchmark is a fusion of:
- **Claude Desktop & ChatGPT macOS App:** Warm, clean chat workspace with collapsible reasoning and artifact panels.
- **Linear & Raycast:** Crisp `1px` borders, subtle glassmorphism, keyboard-first navigation (`Ctrl+K` / `Cmd+K`), and zero visual noise.
- **n8n & Langflow (Refined):** Clean, rounded, custom React Flow cards for hierarchical agent design without overwhelming technical wires.

---

## 2. Frontend UI Library Stack (Mandatory)

| Layer | Package | Usage Standard |
| :--- | :--- | :--- |
| **Core Framework** | `react@19`, `typescript`, `vite` | Strict typing, fast HMR. |
| **Styling Engine** | `tailwindcss@4` | Utility-first CSS with semantic CSS variables for Dark & Light themes. |
| **UI Primitives** | `shadcn/ui` (`@radix-ui/*`) | Accessible Dialogs, Dropdowns, Sheets, Tabs, Switches, Tooltips, Accordions. |
| **Agent Hierarchy Canvas** | `@xyflow/react` (React Flow v12) | Visual node editor for Supervisor $\rightarrow$ Sub-Agent hierarchy & live status animations. |
| **Animations** | `framer-motion` (`motion`) | Smooth panel transitions, collapsible step accordions, active agent pulse effects, and interactive icon micro-animations. |
| **Icons (NO STATIC/EMOJI ICONS)** | `lucide-react` (+ `framer-motion` wrappers) | **NEVER use static Unicode emojis (`🏠`, `☁️`, `🎙️`, `📊`, etc.) or static glyph strings.** Always use dynamic vector icon components with `1.75px` stroke width, semantic color tokens, and hover/state animations. |
| **Typography** | `Geist Sans` / `Inter` + `Geist Mono` | Bundled locally (`@fontsource`) so offline rendering is identical on Windows & Mac. |
| **Command Palette & Toast** | `cmdk` + `sonner` | Instant global quick actions (`Ctrl+K`) and sleek non-intrusive notifications. |
| **Markdown & Code** | `react-markdown`, `remark-gfm`, `shiki` | Crisp tables, formatted Indonesian reports, and syntax-highlighted code blocks. |

---

## 3. Color Palette & Visual Tokens

Support both **Dark Mode (Default — Modern Obsidian Slate)** and **Light Mode (Clean Warm Paper)**:

```css
/* Dark Mode (Obsidian Slate) */
--background: #090A0F;          /* Deep calm background */
--surface-1: #11131A;           /* Sidebar & cards */
--surface-2: #181B24;           /* Hover states & elevated modals */
--border-subtle: rgba(255, 255, 255, 0.07);
--text-primary: #F3F4F6;
--text-secondary: #9CA3AF;
--accent-primary: #6366F1;      /* Indigo Nusantara - Primary actions & active agent */
--accent-emerald: #10B981;      /* Active local Ollama / completed tasks / Excel badge */
--accent-amber: #F59E0B;        /* HITL Approval waiting / warning */
--accent-rose: #F43F5E;         /* High-risk action / stop button */
```

---

## 4. Application Layout Architecture (3-Pane Progressive Disclosure)

```text
+-----------------------------------------------------------------------------------+
| [● ● ●]  AKSA — Asisten Kerja Cerdas        [📁 D:\Kerjaan\Laporan ▾]  [🟢 Telegram]|
+------------------+-------------------------------------------+--------------------+
|                  |                                           |                    |
|  🧭 NAVIGASI      |   💬 RUANG KERJA & EKSEKUSI               |  📄 PANEL ARTEFAK  |
|                  |                                           |  (Auto-Slide Open) |
|  [💬 Ruang Kerja]|   👤 User:                                |                    |
|  [🕸️ Tim Agen]   |   "Tolong baca data penjualan di folder   |  📊 Laporan.xlsx   |
|  [📚 Pengetahuan]|    ini lalu buatkan laporan Excel & Word" |  [Buka di Excel]   |
|  [📱 Telegram]   |                                           |  [Kirim Telegram]  |
|  [🛡️ Izin & PC]  |   🤖 Tim Eksekutif AKSA:                  |                    |
|  [⚙️ Pengaturan] |   ┌─────────────────────────────────────┐ |  📝 Surat.docx     |
|                  |   │ ▾ 🧠 Manajer Utama (Claude Sonnet)  │ |  [Buka di Word]    |
|  ──────────────  |   │   ├─ ✅ Agen RAG (Ollama Qwen2.5)   │ |                    |
|  ⚡ Efisiensi     |   │   │    Membaca 3 file di folder     │ |  ────────────────  |
|  Token Hemat:    |   │   └─ 🔄 Spesialis Office (DeepSeek) │ |  📊 Rincian Token: |
|  78% (Rp 120)    |   │        Membuat Laporan.xlsx...      │ |  Input: 1.240      |
|                  |   └─────────────────────────────────────┘ |  Hemat: 8.400 (RAG)|
|  🏠 Ollama: Aktif|                                           |                    |
|                  |   [ Ketik perintah atau lampirkan file...               [➤] ]  |
+------------------+-------------------------------------------+--------------------+
```

### Key Screen Specifications:

1. **💬 Ruang Kerja (Main Chat & Workspace View):**
   - **Top Bar:** Displays the **Active Workspace Folder** pill (`📁 D:\Kerjaan\Laporan` with a quick button to switch/add folders) and the active **Agent Team** selector.
   - **Live Multi-Agent Execution Accordion:** Instead of flooding the chat with raw logs, sub-agent delegations appear inside a clean, collapsible timeline card showing *which agent* is working, *which model* it uses, and *which tool* is running.
   - **Right Artifact Inspector Drawer:** Automatically slides open when files (`.xlsx`, `.docx`, `.pptx`, `.pdf`) are created, offering 1-click buttons: **"Buka File"**, **"Buka Lokasi Folder"**, and **"Kirim ke Telegram"**.

2. **🕸️ Tim Agen (Visual Hierarchical Agent Builder):**
   - Offers a toggle between **Mode Visual (Kanvas Hirarki)** using `@xyflow/react` and **Mode Ringkas (Daftar Struktur)** for beginners.
   - **Custom Agent Node Card:** Each card cleanly displays:
     - Agent Avatar & Name (e.g., *Manajer Utama*, *Spesialis Office & Laporan*)
     - Model Badge with Provider Icon (e.g., `🟢 Ollama • qwen2.5:7b` or `🟣 Anthropic • Claude 3.7 Sonnet`)
     - Enabled Skill Pills (`📊 Excel`, `📝 Word`, `🔍 RAG`, `💻 Terminal`)
     - `+ Tambah Sub-Agen Bawahan` button right on the bottom handle of any card!
   - Clicking an agent card opens a sleek right-side configuration sheet to edit its Bahasa Indonesia persona prompt, temperature, model, and allowed tools.

3. **📚 Basis Pengetahuan (Local RAG Manager):**
   - Drag-and-drop folders or files, toggle **Auto-Sync Folder**, view indexing status (`Terindeks • 42 Dokumen • 1.280 Bagian`), and run a live **"Uji Pencarian Dokumen"** preview.

4. **📱 Koneksi Telegram & Kontrol Jarak Jauh:**
   - Clean 3-step wizard in Bahasa Indonesia to connect `@BotFather` token, pair via 6-digit code, toggle voice note transcription, and view live Telegram activity logs.

5. **⚙️ Pengaturan Model & Analitik Token:**
   - Manage API Keys (OpenAI, Claude, Gemini, DeepSeek, OpenRouter, Groq) with a **"Tes Koneksi"** button.
   - Manage Local AI (auto-detects **Ollama** & **LM Studio**, displays installed local models and RAM usage).
   - **Dashboard Efisiensi Token:** Shows total tokens used, estimated cost saved by Sub-Agent Context Isolation & Local Models, and token budget limits.

---

## 5. Bahasa Indonesia UX & Localization Guidelines

All user-facing text must feel natural, modern, and empowering—never stiff or robotic.

### Official Term Glossary (English Technical $\rightarrow$ Bahasa Indonesia UI)

| Technical Concept | Official AKSA Bahasa Indonesia Term | Avoid Using |
| :--- | :--- | :--- |
| Workspace Folder | **Folder Kerja** | Direktori Kerja / Ruang Nama |
| Root Supervisor Agent | **Manajer Utama (Supervisor)** | Agen Akar / Agen Induk |
| Specialist Sub-Agent | **Sub-Agen Spesialis** | Agen Anak / Budak (Worker) |
| System Prompt | **Instruksi & Karakter Agen** | Prompt Sistem |
| Knowledge Base (RAG) | **Basis Pengetahuan (RAG)** | Pangkalan Data Vektor |
| Tool / Skill | **Keahlian & Akses Alat** | Perkakas |
| Token Efficiency / Compaction | **Penghematan Token Otomatis** | Pemadatan Konteks |
| Human-in-the-Loop Approval | **Konfirmasi Izin Akses** | Persetujuan Manusia-dalam-Putaran |
| Visual Computer Use | **Kontrol Layar & Aplikasi (Visual)** | Penggunaan Komputer |

---

## 6. Default Pre-Built Indonesian Agent Templates (Out-of-the-Box)

When the user installs AKSA for the first time, it comes pre-seeded with a ready-to-use hierarchical team (**"Tim Produktivitas Kantor Indonesia"**):

1. **🧠 Manajer Eksekutif (Root Supervisor):**
   - *Persona:* Merencanakan langkah kerja secara sistematis, membagi tugas ke sub-agen yang tepat, dan menyusun laporan akhir dalam Bahasa Indonesia yang rapi dan profesional.
2. **📊 Spesialis Administrasi & Office (Sub-Agent):**
   - *Persona:* Ahli membuat pembukuan Excel (dengan rumus dan grafik), surat resmi/laporan Word sesuai standar bisnis Indonesia, dan materi presentasi PowerPoint.
3. **📚 Peneliti Dokumen & Arsip RAG (Sub-Agent):**
   - *Persona:* Membaca cepat ratusan halaman PDF/Word/Excel di dalam Folder Kerja dan mengekstrak fakta akurat beserta kutipan halamannya (sangat cocok dipasang model lokal Ollama agar gratis).
4. **💻 Operator PC & Automasi Sistem (Sub-Agent):**
   - *Persona:* Mengoperasikan aplikasi desktop, menjalankan skrip Python otomatisasi data, dan mengontrol layar PC jika diperlukan.

