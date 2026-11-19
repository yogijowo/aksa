# AKSA — UX IMPROVEMENT SPECIFICATION
## Siklus 15: Simplifying AKSA for Everyday Users

**Project:** AKSA Desktop AI Agent  
**Repository:** `yogijowo/aksa`  
**Target:** Windows, macOS, Linux  
**Priority:** UX, Accessibility, Usability, Interaction Consistency  
**Approach:** Preserve Existing Visual Identity, Improve User Experience

---

# 1. TUJUAN

Meningkatkan pengalaman penggunaan AKSA agar dapat dipahami dan digunakan oleh orang awam tanpa pengetahuan teknis mengenai AI, multi-agent, model AI, MCP, sandbox, API, maupun sistem operasi.

AKSA harus terasa seperti asisten pribadi yang mampu menyelesaikan pekerjaan, bukan panel kontrol teknis yang mengharuskan pengguna memahami cara kerja AI.

Prinsip utama:

> Kompleksitas berada di dalam mesin AKSA, bukan dibebankan kepada penggunanya.

Pengguna cukup menjelaskan pekerjaan yang ingin diselesaikan. AKSA bertanggung jawab menentukan agent, model, tools, skills, dan alur eksekusi yang sesuai.

# 2. ATURAN WAJIB: IDENTITAS VISUAL TIDAK BOLEH BERUBAH

Perubahan UX tidak boleh menjadi alasan untuk merombak seluruh desain.

## 2.1 Elemen yang harus dipertahankan

- Dark theme sebagai tema utama.
- Background utama `#191918`.
- Warna aksen utama `#D97757`.
- Karakter panel dan card yang sudah digunakan.
- Sidebar dan pola navigasi dasar.
- Gaya ikon Lucide yang sudah digunakan.
- Karakter visual tombol, border, radius, dan animasi.
- Tipografi dan identitas visual AKSA yang sudah ada.

## 2.2 Yang boleh diperbaiki

- Hierarki informasi.
- Ukuran teks yang terlalu kecil.
- Penamaan menu dan tombol.
- Pengelompokan menu.
- Layout dan jarak antar elemen.
- Onboarding.
- Empty state.
- Loading state.
- Error state.
- Dialog persetujuan.
- Tooltip dan petunjuk.
- Alur interaksi.
- Pengelompokan pengaturan lanjutan.

## 2.3 Larangan

JANGAN:

1. Mengganti tema dark menjadi light.
2. Mengganti warna aksen utama AKSA.
3. Membuat desain baru yang tidak konsisten dengan komponen lama.
4. Menghilangkan fitur multi-agent.
5. Menghilangkan kemampuan konfigurasi teknis.
6. Menghilangkan kontrol keamanan dan permission.
7. Mengurangi kemampuan pengguna tingkat lanjut.
8. Mengubah business logic hanya untuk mempermudah tampilan.
9. Menggunakan istilah yang terlalu teknis sebagai label utama.
10. Mengganti library atau framework UI tanpa alasan teknis yang kuat.

Jika diperlukan, gunakan progressive disclosure: informasi sederhana ditampilkan terlebih dahulu, sementara konfigurasi lanjutan tetap tersedia.

# 3. TARGET PENGGUNA

AKSA harus mendukung dua kelompok pengguna.

### A. Pengguna umum

Karakteristik:
- Tidak memahami arsitektur AI.
- Tidak memahami multi-agent.
- Tidak mengetahui perbedaan provider dan model.
- Ingin menyelesaikan pekerjaan, bukan mengonfigurasi AI.
- Membutuhkan panduan yang sederhana.
- Menginginkan kontrol yang jelas terhadap akses komputer.

### B. Pengguna lanjutan

Karakteristik:
- Memahami model AI dan provider.
- Ingin mengatur struktur multi-agent.
- Ingin mengatur tools dan skills.
- Membutuhkan informasi eksekusi secara detail.
- Ingin mengatur konfigurasi dan permission secara granular.

Kedua kelompok harus dapat menggunakan aplikasi yang sama tanpa membuat dua aplikasi atau dua tema terpisah.

# 4. GLOBAL UX STANDARDS

Terapkan standar berikut ke seluruh aplikasi.

## 4.1 Bahasa

Gunakan bahasa Indonesia yang natural dan mudah dipahami.

Contoh:

| Hindari | Gunakan |
|---|---|
| Workspace | Ruang Kerja |
| Agent Hierarchy | Struktur Tim AI |
| Sub-Agent | Agen Pendukung |
| Provider | Penyedia AI |
| Model ID | Model AI |
| Tool Categories | Kemampuan |
| Sandbox | Area Kerja Terlindungi |
| Capability | Hak Akses |
| Human-in-the-Loop | Persetujuan Pengguna |
| Execution Trace | Riwayat Pekerjaan |
| Revoke Permission | Cabut Izin |
| Needs User Action | Memerlukan Tindakan Anda |
| RAG | Pencarian dalam Dokumen |
| MCP Server | Koneksi Layanan |

Catatan: istilah teknis boleh tetap digunakan pada mode lanjutan atau bagian detail teknis.

Jangan menerjemahkan nama produk, provider, model, library, maupun protokol secara keliru.

## 4.2 Ukuran teks

Target minimum:

- Judul halaman: 20–24 px.
- Judul bagian: 16–18 px.
- Teks utama: 14–16 px.
- Deskripsi: 13–14 px.
- Label dan metadata: minimum 12 px.
- Informasi teknis sekunder: minimum 11 px jika memang diperlukan.

Pastikan kontras teks mencukupi, khususnya teks abu-abu pada background gelap.

## 4.3 Interaksi

Setiap kontrol harus memiliki:
- Nama yang jelas.
- Tujuan yang dapat dipahami.
- Status aktif/nonaktif yang terlihat.
- Feedback ketika digunakan.
- Loading state jika proses membutuhkan waktu.
- Error state jika tindakan gagal.

Jangan membuat tombol yang hanya berfungsi sebagai dekorasi.

## 4.4 Konsistensi

Buat atau rapikan shared UI components untuk:
- Page header.
- Section header.
- Primary button.
- Secondary button.
- Destructive button.
- Status badge.
- Empty state.
- Loading state.
- Error state.
- Confirmation dialog.
- Tooltip.
- Form field.
- Permission card.

Gunakan komponen yang sudah tersedia apabila sesuai. Hindari membuat duplikasi komponen.

# 5. SPESIFIKASI PER HALAMAN

## 5.1 BERANDA / RUANG KERJA

Priority: P1

Tujuan:
Pengguna dapat langsung memulai pekerjaan tanpa harus memahami struktur internal AKSA.

### Tampilan awal

Judul:

"Halo, apa yang ingin Anda kerjakan?"

Deskripsi:

"Ceritakan pekerjaan yang ingin diselesaikan. AKSA akan membantu menentukan langkah yang diperlukan."

Tampilkan beberapa pilihan aktivitas:

1. Mengolah dokumen.
   - Membaca PDF, Word, dan Excel.
   - Membuat laporan.
   - Mengolah data.

2. Mencari informasi.
   - Mencari informasi.
   - Merangkum dokumen.
   - Membandingkan data.

3. Mengerjakan tugas komputer.
   - Mengoperasikan aplikasi.
   - Mengelola file.
   - Membantu pekerjaan berulang.

4. Bertanya kepada AKSA.
   - Tanya jawab.
   - Brainstorming.
   - Analisis dan rekomendasi.

Pilihan tersebut merupakan shortcut yang mengisi atau memulai instruksi, bukan membatasi kemampuan AKSA.

### Input instruksi

Placeholder:

"Ceritakan pekerjaan yang ingin Anda selesaikan..."

Tambahkan:
- Tombol kirim.
- Indikator lampiran jika fitur tersedia.
- Petunjuk singkat tentang jenis file yang dapat digunakan.
- Penanganan instruksi kosong.
- Penanganan kegagalan pengiriman.

Jangan memaksa pengguna memilih agent sebelum mengirim instruksi.

### First-time onboarding

Ketika pertama kali membuka AKSA, tampilkan onboarding singkat dan dapat dilewati.

Urutan:

1. Sambutan dan penjelasan singkat AKSA.
2. Penjelasan bahwa AKSA dapat membantu pekerjaan di komputer.
3. Penjelasan bahwa izin akses hanya diminta saat dibutuhkan.
4. Ajakan mencoba tugas pertama.

Jangan langsung meminta seluruh permission sistem operasi pada saat onboarding.

### Status eksekusi

Ketika AI sedang bekerja, tampilkan:

- Pekerjaan yang sedang dilakukan.
- Status proses.
- Langkah yang telah selesai.
- Langkah yang sedang berjalan.
- Langkah berikutnya.
- Tindakan yang memerlukan persetujuan pengguna.

Contoh:

"Sedang membuat laporan dari file Excel."

1. Membaca file — Selesai.
2. Menganalisis data — Selesai.
3. Membuat laporan — Sedang dikerjakan.
4. Menyimpan hasil — Menunggu.

Informasi agent, model, provider, token, dan detail teknis tetap dapat dibuka melalui bagian "Detail aktivitas".

PENTING:
Jangan menampilkan chain-of-thought internal model. Yang ditampilkan hanya status, aktivitas, dan ringkasan tindakan yang aman untuk pengguna.

### Hasil pekerjaan

Hasil akhir harus memiliki:
- Ringkasan pekerjaan.
- Status berhasil atau gagal.
- Daftar file hasil jika ada.
- Tombol membuka hasil.
- Tombol membuka lokasi file jika tersedia.
- Informasi langkah lanjutan yang relevan.

Jangan hanya menampilkan output teknis tanpa menjelaskan hasilnya.

---

## 5.2 PUSAT AKSES AKSA

Priority: P1

File awal yang perlu diperiksa:
`apps/desktop/src/components/settings/PermissionsAndPCView.tsx`

Ubah konsep halaman dari:

"Pusat Izin Sistem Operasi & Sandbox AKSA"

Menjadi:

"Pusat Akses AKSA"

Deskripsi:

"Atur apa saja yang boleh dilakukan AKSA di komputer Anda."

### Kategori akses

1. Folder dan file.
2. Aplikasi komputer.
3. Kontrol layar dan keyboard.
4. Koneksi eksternal.
5. Perintah dan program.
6. Informasi sensitif dan kredensial.

Setiap kategori menampilkan:
- Penjelasan sederhana.
- Status izin.
- Cakupan akses.
- Agent yang menggunakan akses tersebut jika tersedia.
- Tombol mengatur izin.
- Tombol mencabut izin.

### Status yang digunakan

| Status teknis | Status UI |
|---|---|
| GRANTED | Izin diberikan |
| DENIED | Akses ditolak |
| NEEDS_USER_ACTION | Memerlukan tindakan Anda |
| automatic_sandbox | Dilindungi otomatis |
| Not available | Tidak tersedia pada perangkat ini |

Jangan menampilkan enum internal secara langsung.

### Pengaturan folder

Pisahkan permission menjadi:

- Melihat daftar file.
- Membaca isi file.
- Membuat file.
- Mengubah file.
- Memindahkan file.
- Menghapus file.
- Menjalankan program atau skrip.

Jangan menggabungkan seluruh permission menjadi satu pilihan tanpa penjelasan.

Penghapusan permanen dan eksekusi program harus memiliki kontrol tersendiri.

### Pengelolaan akses

Pengguna harus dapat:
- Melihat seluruh izin yang aktif.
- Melihat izin yang pernah diberikan.
- Mengetahui cakupan setiap izin.
- Mengetahui agent yang menggunakan izin.
- Mencabut izin.
- Melihat panduan mengaktifkan permission OS jika diperlukan.

Jangan mengklaim izin sudah dicabut jika OS atau backend belum mengonfirmasi keberhasilan.

---

## 5.3 DIALOG PERSETUJUAN AKSES

Priority: P1

File:
`apps/desktop/src/components/workspace/HITLApprovalModal.tsx`

Tujuan:
Pengguna memahami dengan jelas apa yang akan dilakukan AKSA sebelum memberikan izin.

### Struktur dialog

Judul:

"AKSA membutuhkan izin Anda"

Isi:

"[Nama agen] ingin [tindakan] pada [target]."

Contoh:

"AKSA ingin membaca file laporan.xlsx di folder Dokumen untuk membuat ringkasan."

Tampilkan informasi:
- Agen yang meminta izin.
- Tindakan yang akan dilakukan.
- File atau folder target.
- Apakah data akan dikirim ke layanan eksternal, jika relevan dan diketahui.
- Apakah tindakan dapat dibatalkan.
- Informasi backup jika benar-benar tersedia.

### Tombol

Pilihan utama:
"Izinkan tindakan ini"

Pilihan sekunder:
"Tolak"

Pilihan tambahan:
"Atur izin untuk folder ini"

### Aturan keamanan wajib

1. Izin sekali menjadi pilihan default yang paling jelas.
2. Jangan mengaktifkan read, write, dan execute sekaligus melalui satu persetujuan yang ambigu.
3. Izin permanen harus menjelaskan cakupannya.
4. Izin untuk satu agent tidak otomatis berlaku bagi agent lainnya.
5. Jangan memperluas izin melebihi permintaan yang disetujui.
6. Tindakan berisiko tinggi tetap memerlukan persetujuan eksplisit.
7. Jangan menampilkan status backup aktif jika backup tidak benar-benar tersedia.
8. Jangan menganggap izin AKSA sama dengan izin native OS.

Jika terdapat pilihan izin permanen, tampilkan ringkasan izin sebelum pengguna menyetujuinya.

---

## 5.4 TIM AI / PENGELOLAAN AGENT

Priority: P2

File awal:
`apps/desktop/src/components/agents/AgentHierarchyView.tsx`

Tujuan:
Memungkinkan pengguna umum membuat dan mengelola agent tanpa memahami konfigurasi teknis.

### Mode sederhana

Jadikan mode sederhana sebagai pengalaman default.

Pengguna dapat:

1. Membuat agent.
2. Memberi nama.
3. Memilih jenis pekerjaan.
4. Menentukan deskripsi tugas.
5. Memilih kemampuan yang dibutuhkan.
6. Menggunakan rekomendasi model otomatis.
7. Menyimpan agent.

Contoh jenis pekerjaan:
- Asisten dokumen.
- Analis data.
- Riset informasi.
- Asisten administrasi.
- Asisten pemrograman.
- Agent khusus.

Jenis tersebut boleh berupa template, tetapi tidak boleh membatasi pembuatan agent kustom.

### Mode lanjutan

Tetap sediakan semua kemampuan yang sudah ada:

- Struktur hierarki agent.
- Kanvas visual.
- Daftar struktur.
- Penambahan sub-agent.
- Provider AI.
- Model AI.
- Model kustom.
- Konfigurasi tools.
- Penugasan aplikasi.
- Penugasan skills.
- Konfigurasi lanjutan.

Pindahkan detail konfigurasi ke bagian lanjutan, bukan menghapusnya.

### Perubahan istilah

| Istilah lama | Istilah utama UI |
|---|---|
| Agent Hierarchy | Struktur Tim AI |
| Add Sub-Agent | Tambah Agen Pendukung |
| Model ID | Model AI |
| Provider | Penyedia AI |
| Tool Categories | Kemampuan Agen |
| Custom Model | Model Kustom |
| Tier Level | Tingkat Agen |

### Keamanan

- Tampilkan permission masing-masing agent.
- Jangan mewariskan permission secara otomatis tanpa kebijakan eksplisit.
- Tampilkan peringatan sebelum menghapus agent.
- Pastikan penghapusan agent tidak menghapus data atau memori lain secara tidak sengaja.
- Jelaskan dampak penghapusan sebelum dikonfirmasi.

---

## 5.5 APLIKASI

Priority: P2

Tujuan:
Pengguna dapat memahami aplikasi yang dapat digunakan AKSA.

Tampilkan setiap aplikasi dengan:
- Nama aplikasi.
- Ikon.
- Fungsi singkat.
- Status terdeteksi atau tidak.
- Status izin.
- Tombol hubungkan atau atur akses.

Gunakan bahasa:

"AKSA dapat menggunakan aplikasi ini setelah Anda memberikan izin yang diperlukan."

Jangan menampilkan nama package, executable path, atau identifier internal sebagai informasi utama.

Detail teknis tetap tersedia di mode lanjutan.

Jangan memberikan kesan bahwa AKSA dapat mengontrol seluruh aplikasi hanya karena aplikasi tersebut terdeteksi.

---

## 5.6 KEAHLIAN / SKILLS

Priority: P2

Tujuan:
Pengguna dapat menambahkan kemampuan tanpa memahami struktur file skill.

Tampilkan:
- Nama keahlian.
- Deskripsi.
- Fungsi.
- Sumber.
- Status instalasi.
- Agent yang menggunakan skill.
- Status keamanan atau verifikasi.

Bedakan secara jelas:
- Skill bawaan AKSA.
- Skill dari sumber eksternal.
- Skill buatan pengguna.

Sebelum memasang skill eksternal, tampilkan:
- Asal sumber.
- Izin yang diminta.
- Kemampuan yang akan diberikan.
- Status verifikasi.
- Peringatan jika sumber belum dipercaya.

Jangan menjadikan label "Verified" sebagai jaminan keamanan absolut.

---

## 5.7 BASIS PENGETAHUAN

Priority: P3

Gunakan istilah yang mudah dipahami:

"Pengetahuan AKSA"

Pengguna harus memahami bahwa halaman ini berfungsi untuk mengelola dokumen atau informasi yang dapat digunakan AKSA sebagai referensi.

Tampilkan:
- Tambah dokumen.
- Daftar dokumen.
- Status pemrosesan.
- Status indeks.
- Agent yang dapat mengakses.
- Tombol hapus.
- Informasi kegagalan pemrosesan.

Jelaskan bahwa menambahkan dokumen tidak otomatis berarti seluruh agent memperoleh akses tanpa batas.

---

## 5.8 INTEGRASI

Priority: P3

Gabungkan pengelolaan koneksi layanan eksternal ke dalam halaman yang mudah dipahami.

Tampilkan:
- Nama layanan.
- Deskripsi fungsi.
- Status koneksi.
- Hak akses yang digunakan.
- Tombol hubungkan.
- Tombol putuskan koneksi.

Jangan menampilkan konfigurasi API dan credential sebagai elemen utama.

Credential harus tetap dikelola menggunakan mekanisme penyimpanan yang aman.

---

## 5.9 PENGATURAN

Priority: P3

Kelompokkan menjadi:

1. Umum.
2. Tampilan.
3. Model AI.
4. Privasi dan data.
5. Penyimpanan.
6. Jaringan.
7. Lanjutan.
8. Informasi aplikasi.

Jangan mencampur pengaturan keamanan kritis dengan pengaturan tampilan sederhana.

# 6. NAVIGASI SIDEBAR

Pertahankan bentuk sidebar yang sudah ada.

Rekomendasi pengelompokan:

**PEKERJAAN**
- Ruang Kerja
- Tim AI

**KEMAMPUAN**
- Aplikasi
- Keahlian
- Pengetahuan
- Integrasi

**KONTROL**
- Pusat Akses
- Pengaturan

Gunakan label yang konsisten dan singkat.

Pastikan:
- Menu aktif mudah diketahui.
- Ikon tetap konsisten.
- Tooltip tersedia bila sidebar dalam keadaan collapsed.
- Navigasi tidak terputus ketika pengguna membuka dialog.
- Perpindahan halaman tidak menghilangkan pekerjaan yang sedang berlangsung.

# 7. EMPTY, LOADING, ERROR, DAN SUCCESS STATES

Seluruh halaman harus memiliki empat kondisi ini.

## Empty state

Jangan hanya menampilkan halaman kosong.

Contoh:

"Belum ada agent."

"Anda belum membuat agent. Buat agent pertama untuk membantu pekerjaan tertentu."

Sediakan tombol tindakan yang jelas.

## Loading state

Tampilkan:
- Indikator proses.
- Penjelasan aktivitas.
- Feedback ketika proses terlalu lama.

Jangan menggunakan loading yang tidak jelas atau berhenti tanpa informasi.

## Error state

Gunakan bahasa yang menjelaskan:
- Apa yang gagal.
- Penyebab jika diketahui.
- Apakah data tetap aman.
- Langkah yang dapat dilakukan.

Jangan menampilkan stack trace kepada pengguna umum.

Detail teknis dapat dibuka melalui bagian "Detail kesalahan".

## Success state

Jelaskan tindakan yang berhasil dilakukan.

Contoh:

"File laporan berhasil dibuat."

Sediakan tindakan lanjutan yang relevan.

# 8. ACCESSIBILITY DAN RESPONSIVENESS

Target:

- Seluruh tombol dapat digunakan melalui keyboard.
- Focus indicator terlihat.
- Dialog mendukung navigasi keyboard.
- Modal tidak menjebak fokus secara keliru.
- Kontras warna memadai.
- Label input dapat diakses screen reader.
- Status tidak hanya dibedakan berdasarkan warna.
- Tooltip tidak menjadi satu-satunya sumber informasi penting.
- Tampilan tetap dapat digunakan pada resolusi desktop yang lebih kecil.
- Panel tidak terpotong.
- Dialog tidak keluar dari area layar.

Hormati pengaturan reduced motion jika tersedia.

Jangan memperkecil teks demi mempertahankan lebih banyak informasi dalam satu layar.

# 9. TECHNICAL IMPLEMENTATION RULES

Sebelum mengubah kode:

1. Audit struktur frontend yang sebenarnya.
2. Identifikasi shared components.
3. Identifikasi state management.
4. Identifikasi routing.
5. Identifikasi seluruh halaman yang terdampak.
6. Identifikasi alur backend yang terhubung.
7. Identifikasi permission dan security boundaries.
8. Buat rencana perubahan sebelum implementasi.

Ketika melakukan implementasi:

- Gunakan stack dan pola arsitektur yang sudah ada.
- Hindari duplikasi state.
- Jangan membuat mock data untuk menggantikan data produksi.
- Jangan menghapus fitur lama.
- Jangan mengubah API contract tanpa alasan kuat.
- Pertahankan kompatibilitas dengan backend.
- Pertahankan keamanan permission.
- Pastikan loading dan error state berasal dari kondisi nyata.
- Gunakan shared component untuk elemen berulang.
- Hindari hardcoded text yang tidak konsisten.
- Pertimbangkan penggunaan central UI copy/constants jika sesuai dengan struktur proyek.

Jika melakukan refactoring besar, pecah menjadi perubahan kecil yang mudah ditinjau.

# 10. ACCEPTANCE CRITERIA

Implementasi belum dianggap selesai sebelum seluruh k