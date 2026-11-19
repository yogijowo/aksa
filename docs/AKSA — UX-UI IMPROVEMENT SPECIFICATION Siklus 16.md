# AKSA — UX/UI IMPROVEMENT SPECIFICATION
## Siklus 16 — Hierarki Visual, Pemilihan Model, Pengaturan Tema, dan Penyederhanaan Pengalaman

**Produk:** AKSA — Asisten Kerja Cerdas & Otonom  
**Repository:** `yogijowo/aksa`  
**Platform:** Windows, macOS, Linux  
**Jenis pekerjaan:** Audit UX/UI berbasis screenshot dan implementasi perbaikan  
**Prioritas:** Tinggi  
**Prinsip utama:** Sederhana bagi pengguna awam, tetap lengkap bagi pengguna tingkat lanjut.

---

## 1. Tujuan

Perbaiki UX/UI AKSA agar pengguna nonteknis dapat memahami cara kerja aplikasi, mengatur agen, memilih model AI, mengelola penyedia AI, memberikan izin, dan menentukan folder kerja tanpa harus memahami istilah teknis.

Implementasi harus:
- Mempertahankan identitas visual AKSA yang sudah ada.
- Mempertahankan seluruh kemampuan teknis dan fitur yang sudah tersedia.
- Mengembalikan pemilihan model AI manual.
- Menampilkan struktur multi-agent sebagai diagram hierarki visual.
- Menyediakan pilihan tema gelap, terang, dan mengikuti sistem.
- Memperjelas status penyimpanan API token tanpa membocorkan token.
- Memudahkan pemilihan folder melalui file manager native OS.
- Menyederhanakan halaman lain secara konsisten, bukan hanya dua halaman pada screenshot.

Dokumen ini merupakan spesifikasi implementasi. Jangan menganggap fitur sudah tersedia sebelum memeriksa dan mengimplementasikannya di source code.

## 2. Identitas visual yang wajib dipertahankan

Pertahankan bahasa visual AKSA:
- Latar gelap utama sekitar `#191918`.
- Panel/kartu sekitar `#21211F` dan `#262624`.
- Aksen oranye sekitar `#D97757`.
- Border tipis dan kontras lembut.
- Ikon sederhana, radius, jarak, dan gaya tombol yang konsisten dengan aplikasi sekarang.
- Nuansa desktop produktivitas yang rapi, modern, profesional, tidak ramai.

Jangan melakukan redesign total atau mengganti karakter visual AKSA.

### Sistem tema

Tambahkan tiga pilihan:
1. **Gelap** — tampilan yang sekarang; menjadi default untuk instalasi baru.
2. **Terang** — pasangan warna terang yang tetap menggunakan aksen oranye AKSA.
3. **Ikuti sistem** — mengikuti preferensi dark/light OS.

Persyaratan:
- Pilihan tema berada di Pengaturan → Tampilan.
- Terapkan tema ke seluruh aplikasi, termasuk sidebar, header, modal, dropdown, tooltip, editor, diagram, empty state, dan komponen pihak ketiga yang dapat dikendalikan.
- Simpan preferensi secara persisten.
- Perubahan tema langsung terlihat tanpa restart.
- Saat memilih “Ikuti sistem”, perubahan preferensi OS harus diikuti secara otomatis.
- Hindari warna hard-coded per komponen. Gunakan design tokens/CSS variables atau sistem tema yang sudah dipakai proyek.
- Pastikan status sukses, peringatan, bahaya, fokus, disabled, dan hover tetap terbaca pada kedua tema.
- Jangan sekadar membalik warna secara otomatis dengan filter CSS.

## 3. Struktur Tim AI — diagram hierarki visual

### Masalah yang terlihat

Halaman Struktur Tim AI saat ini menampilkan kartu Asisten Utama di area kerja dan konfigurasi agen di panel kanan. Hubungan induk-anak antaragen tidak terlihat. Ruang kosong yang besar juga belum dimanfaatkan untuk membantu pengguna memahami struktur tim.

### Hasil yang diharapkan

Jadikan area utama sebagai **kanvas visual hierarki tim**, dengan konsep diagram organisasi/workflow seperti node graph pada n8n:
- Agen utama berada di posisi paling atas atau paling kiri sebagai root.
- Agen pendukung berada pada tingkat di bawahnya.
- Sub-agent ditampilkan di bawah agen yang mendelegasikan tugas kepadanya.
- Garis penghubung menunjukkan relasi delegasi/parent-child yang sebenarnya.
- Setiap node menampilkan nama agen, peran singkat, status, dan model aktif secara ringkas.
- Node terpilih memiliki outline aksen oranye.
- Node yang sedang bekerja dapat memiliki indikator aktivitas yang halus.
- Garis dapat dianimasikan ketika tugas benar-benar sedang didelegasikan atau berjalan. Jangan membuat animasi seolah-olah ada aktivitas jika tidak ada.
- Sediakan zoom, pan, fit-to-screen, dan minimap bila library/implementasi memungkinkan.
- Diagram harus tetap nyaman dipakai pada ukuran jendela yang lebih kecil.

### Interaksi diagram

- Klik node untuk membuka konfigurasi agen pada panel samping.
- Tambah agen melalui tombol yang jelas; pengguna dapat memilih induk/agen yang akan dibantu.
- Hubungkan atau pindahkan agen dengan interaksi drag-and-drop bila aman dan sesuai arsitektur.
- Jika drag-and-drop terlalu kompleks, sediakan kontrol “Agen ini membantu” / “Pilih agen induk”.
- Tampilkan konfirmasi sebelum mengubah relasi yang berdampak pada alur kerja.
- Cegah relasi melingkar (circular dependency), node tanpa induk yang tidak valid, dan struktur yang melanggar batas sistem.
- Hapus agen harus meminta konfirmasi dan menjelaskan dampak terhadap sub-agent/tugas terkait.
- Sediakan tampilan alternatif **Daftar** untuk aksesibilitas dan pengguna yang lebih menyukai daftar.
- Diagram dan daftar harus memakai sumber data yang sama; jangan membuat representasi UI yang hanya berupa mockup.

### Informasi node

Tampilkan informasi yang membantu, bukan seluruh konfigurasi teknis:
- Nama agen.
- Peran atau tanggung jawab.
- Status: Siap, Bekerja, Menunggu persetujuan, Gagal, atau Nonaktif.
- Model yang digunakan (nama manusiawi; detail provider/model ID bisa berada di detail).
- Ringkasan jumlah kemampuan aktif bila relevan.

Hindari memenuhi node dengan token, model ID panjang, daftar tools, atau metadata internal.

### Panel konfigurasi agen

Pertahankan seluruh kemampuan konfigurasi yang ada, tetapi susun menjadi bagian yang mudah dipahami:
1. Identitas agen: nama, jenis pekerjaan/template, peran, deskripsi.
2. Tanggung jawab dan instruksi.
3. Kemampuan: tools, aplikasi, skills, akses.
4. Model AI.
5. Hubungan dengan agen lain.
6. Pengaturan lanjutan.

Mode **Sederhana** menjadi default. Mode **Lanjutan** tetap menyediakan konfigurasi teknis yang lengkap. Jangan menghapus fitur hanya untuk menyederhanakan UI.

## 4. Pemilihan model AI — kembalikan pilihan manual

### Masalah

Pada tampilan sebelumnya terdapat pilihan “Rekomendasi Otomatis” dan konfigurasi model, tetapi pengguna harus tetap dapat memilih model secara manual. Jangan memaksa semua pengguna menggunakan rekomendasi otomatis atau menyembunyikan pilihan manual.

### Perilaku yang diwajibkan

Pada konfigurasi setiap agen, sediakan pilihan:
- **Otomatis (direkomendasikan)** — sistem memilih model berdasarkan tugas, kemampuan, ketersediaan, dan kebijakan pengguna.
- **Pilih sendiri** — pengguna memilih provider dan model secara eksplisit.

Ketika memilih manual:
1. Pilih penyedia AI yang telah dikonfigurasi.
2. Pilih model yang benar-benar tersedia dari provider tersebut.
3. Tampilkan nama model yang mudah dibaca.
4. Sediakan informasi ringkas: kemampuan, konteks, biaya/kuota bila datanya tersedia, serta dukungan tool/function calling jika relevan.
5. Tampilkan model ID teknis di detail lanjutan, bukan sebagai label utama.
6. Berikan status bila model tidak tersedia, provider belum memiliki token, atau koneksi gagal.
7. Sediakan tombol uji koneksi/model jika didukung.
8. Simpan pilihan per agen dan tampilkan model aktif pada diagram.

### Ketentuan penting

- Pemilihan manual tidak boleh hilang saat berpindah mode Sederhana/Lanjutan.
- Rekomendasi otomatis tidak boleh menimpa pilihan manual tanpa persetujuan.
- Jika model yang dipilih tidak tersedia, jangan diam-diam mengganti model. Beri tahu pengguna dan tawarkan pilihan pengganti.
- Jangan mengarang daftar model. Gunakan data provider/model dari konfigurasi dan API yang benar-benar tersedia.
- Pastikan backend benar-benar menggunakan model yang ditampilkan UI.
- Uji persistensi pilihan model setelah aplikasi ditutup dan dibuka kembali.
- Jika model mempunyai parameter khusus, tampilkan parameter umum terlebih dahulu; sisanya di bagian lanjutan.

## 5. Pengaturan penyedia AI dan API token

### Masalah pada screenshot

Kartu provider menunjukkan status “Siap digunakan” atau “Belum diatur”, namun kolom token tampak kosong/placeholder walaupun provider dapat saja sudah tersambung. Pengguna awam tidak yakin apakah token sudah tersimpan dan apakah perlu memasukkan ulang.

### Tampilan status token

Setiap kartu provider harus membedakan:
- **Belum dihubungkan** — belum ada kredensial tersimpan.
- **Token tersimpan** — kredensial tersedia secara lokal/secure storage.
- **Terhubung** — tes koneksi berhasil pada pemeriksaan terakhir.
- **Perlu diperiksa** — token ada, tetapi belum pernah diuji atau hasil tes sudah kedaluwarsa.
- **Koneksi gagal** — pemeriksaan terakhir gagal; tampilkan pesan yang aman dan mudah dimengerti.

Jangan menyamakan “token tersimpan” dengan “koneksi berhasil”.

### Perilaku input token

Jika token sudah tersimpan:
- Jangan mengirim token asli ke frontend hanya untuk mengisi ulang input.
- Tampilkan indikator seperti **“Token sudah tersimpan”**.
- Tampilkan input password masked dengan placeholder misalnya `••••••••••••••••`.
- Jika diperlukan, tampilkan petunjuk empat karakter terakhir hanya jika kebijakan keamanan proyek mengizinkan dan tidak menimbulkan risiko.
- Tombol ikon mata hanya untuk nilai baru yang sedang diketik, bukan untuk mengambil atau menampilkan kembali secret yang tersimpan.
- Sediakan tombol **Ganti token** atau izinkan pengguna mengetik token baru untuk menggantikan token lama.
- Sediakan aksi **Hapus token** dengan konfirmasi.
- Jangan pernah menampilkan token asli dalam log, telemetry, error, notifikasi, atau state yang dapat diinspeksi secara tidak perlu.

Jika token belum tersimpan:
- Tampilkan input kosong dengan placeholder contoh format yang tidak menyerupai token valid.
- Berikan tautan resmi “Dapatkan API key” jika URL resmi telah dikonfirmasi dari konfigurasi aplikasi.
- Berikan penjelasan singkat bahwa token disimpan dengan aman di perangkat.

### Tombol dan feedback

- Tombol utama: **Simpan token** atau **Perbarui token** sesuai status.
- Tombol sekunder: **Uji koneksi**.
- Tampilkan loading ketika menyimpan/menguji.
- Tampilkan hasil yang jelas: berhasil, token tidak valid, kuota/provider bermasalah, jaringan gagal, atau error lain yang aman.
- Jangan menghapus token lama jika token pengganti gagal disimpan/diuji, kecuali pengguna secara eksplisit memilih menghapus.
- Jangan menampilkan error teknis mentah kepada pengguna awam; detail teknis dapat dibuka melalui “Detail”.

### Keamanan

- Gunakan secure storage/keychain/credential vault yang sudah disediakan arsitektur AKSA.
- Jangan menyimpan API key dalam localStorage, file konfigurasi plaintext, database plaintext, atau log.
- Jangan mengirim secret ke telemetry.
- Pastikan operasi read/write/delete token memiliki batas izin dan audit yang sesuai.
- Jangan pernah mengembalikan secret lengkap dari backend hanya untuk mengisi indikator UI.
- Tambahkan pengujian bahwa secret tidak muncul pada response, log, error, crash report, atau snapshot UI.

## 6. Pemilihan folder kerja melalui file manager native OS

### Masalah

Path folder root/penyimpanan saat ini terlihat seperti teks path teknis. Pengguna awam seharusnya tidak perlu mengetik atau memahami path filesystem.

### UX yang diharapkan

Pada pengaturan Workspace/Ruang Kerja:
- Tampilkan nama folder yang dipilih, bukan path panjang sebagai informasi utama.
- Tampilkan path lengkap dalam teks sekunder/detail yang dapat disalin.
- Sediakan tombol **Pilih folder…**.
- Tombol membuka native folder picker OS (Windows Explorer, macOS Finder, Linux file chooser) menggunakan mekanisme resmi Tauri/plugin yang sesuai versi proyek.
- Pengguna dapat memilih folder root/ruang kerja.
- Setelah memilih, tampilkan ringkasan lokasi dan minta konfirmasi bila perubahan berdampak pada workspace aktif.
- Sediakan **Buka folder** untuk membuka lokasi di file manager OS.
- Sediakan **Ganti folder** dan **Kembalikan ke lokasi default** jika memang didukung.
- Tampilkan status folder: dapat diakses, tidak ditemukan, izin ditolak, read-only, atau tidak tersedia.
- Jika folder tidak dapat diakses, berikan langkah pemulihan yang mudah dimengerti.

### Validasi dan keamanan

- Jangan membuat custom file browser berbasis web jika native folder picker dapat digunakan.
- Jangan meminta izin filesystem terlalu luas hanya untuk memilih folder.
- Validasi path di backend/Rust, bukan hanya di frontend.
- Pertahankan sandbox/path allowlist yang sudah ada.
- Pemilihan folder tidak otomatis memberikan izin read/write/execute ke seluruh folder. Izin akses harus tetap dijelaskan dan diminta secara terpisah sesuai kebijakan keamanan AKSA.
- Jangan mengubah folder workspace secara diam-diam.
- Tangani cancel tanpa mengubah pengaturan.
- Uji path dengan spasi, karakter non-ASCII, folder jaringan bila didukung, folder tidak ada, dan folder tanpa izin.

## 7. Pengaturan Tampilan

Buat bagian khusus **Pengaturan → Tampilan** yang mudah ditemukan.

Kontrol:
- Tema: Gelap / Terang / Ikuti sistem.
- Ukuran tampilan atau kepadatan UI bila sudah didukung tanpa merusak layout.
- Animasi: Normal / Kurangi animasi (opsional, mengikuti `prefers-reduced-motion`).
- Bahasa aplikasi jika sistem lokalisasi tersedia; jangan tampilkan kontrol yang belum berfungsi.

Gunakan preview kecil tema bila bermanfaat, tetapi jangan membuat halaman pengaturan terlalu ramai.

## 8. Penyederhanaan halaman lain secara menyeluruh

Audit dan rapikan halaman lain agar konsisten dengan pengalaman pengguna awam. Pertahankan fitur dan istilah teknis pada detail/Mode Lanjutan.

### A. Ruang Kerja

- Jadikan input utama berorientasi tugas: “Apa yang ingin Anda kerjakan?”
- Berikan contoh tugas sehari-hari yang konkret, bukan istilah internal seperti RAG, orchestration, atau pipeline.
- Pengguna tidak perlu membuat atau memahami agen sebelum meminta pekerjaan.
- Tampilkan proses dalam bahasa sederhana: memahami tugas, menyiapkan langkah, mengerjakan, menunggu persetujuan bila perlu, selesai.
- Informasi provider, model ID, token, dan trace teknis masuk ke **Detail aktivitas**.
- Hasil pekerjaan harus mudah ditemukan, dibuka, disimpan, dan diunduh.
- Bedakan hasil final, file sementara, dan log aktivitas.
- Sediakan state kosong yang menjelaskan langkah pertama.

### B. Persetujuan akses (HITL)

- Gunakan judul bahasa sederhana: “AKSA meminta izin”.
- Jelaskan siapa agen yang meminta, tindakan yang akan dilakukan, lokasi/objek yang terdampak, dan alasan izin dibutuhkan.
- Jelaskan apakah data akan dikirim ke layanan cloud jika relevan dan diketahui.
- Jadikan **Izinkan sekali** pilihan utama untuk tindakan berisiko.
- Pisahkan izin permanen dari izin sekali pakai.
- Jangan gunakan tombol yang sekaligus memberi read, write, dan execute bila permintaan sebenarnya hanya membutuhkan satu jenis izin.
- Jelaskan ruang lingkup dan durasi izin permanen.
- Tolak secara aman dan sediakan pilihan “Jangan izinkan”.
- Jangan mengklaim backup aktif jika backup tidak benar-benar dilakukan dan diverifikasi.

### C. Pusat Akses

- Kelompokkan izin berdasarkan objek yang dimengerti: File & folder, Aplikasi, Layar & input, Jaringan, Perintah sistem, dan Kredensial (hanya jika memang didukung).
- Terjemahkan status OS seperti `GRANTED` dan `NEEDS_USER_ACTION` menjadi label manusiawi; status teknis tetap dapat dilihat di detail.
- Bedakan izin sistem operasi dari persetujuan internal AKSA.
- Tampilkan izin aktif, alasan, cakupan, dan cara mencabutnya.
- Hak baca, tulis, ubah, hapus, dan eksekusi harus granular sesuai kemampuan backend.
- Jangan menampilkan kontrol yang tidak benar-benar terhubung dengan mekanisme permission.

### D. Aplikasi

- Jelaskan fungsi aplikasi yang terdeteksi dan status integrasinya.
- Pisahkan aplikasi terpasang, aplikasi yang sudah dihubungkan, dan aplikasi yang dapat diakses AKSA.
- Tampilkan izin yang dibutuhkan sebelum menghubungkan.
- Sediakan pencarian, kategori, dan state ketika tidak ada aplikasi yang ditemukan.
- Jangan menyimpulkan aplikasi bisa dikendalikan hanya karena terdeteksi terpasang.

### E. Keahlian / Skills

- Gunakan deskripsi manfaat dalam bahasa sederhana.
- Tampilkan sumber, penerbit, versi, kompatibilitas, izin yang diminta, dan status verifikasi.
- Bedakan skill resmi/terverifikasi dari skill pihak ketiga.
- Sebelum instalasi skill eksternal, jelaskan akses yang diminta dan risiko secara proporsional.
- Sediakan alur tinjau, instal, perbarui, nonaktifkan, dan hapus.
- Jangan menyamarkan kemampuan skill atau izin yang diminta.

### F. Pengetahuan

- Jelaskan sumber pengetahuan yang terhubung dan bagaimana AKSA menggunakannya.
- Gunakan istilah seperti “Tambahkan dokumen” atau “Hubungkan folder”.
- Tampilkan progres indeksasi, jumlah dokumen, status, dan error yang bisa ditindaklanjuti.
- Jelaskan cara memperbarui/menghapus sumber dan dampaknya pada indeks.
- Pastikan penghapusan sumber dan penghapusan data indeks dijelaskan secara akurat.

### G. Integrasi

- Tampilkan integrasi dalam bentuk kartu dengan fungsi, status, dan izin.
- Gunakan label “Hubungkan”, “Terhubung”, “Perlu tindakan”, dan “Putuskan”.
- Jelaskan data apa yang dapat diakses integrasi.
- Hindari status hijau “Terhubung” jika koneksi sudah kedaluwarsa atau gagal.

### H. Pengaturan umum

- Kelompokkan berdasarkan Akun, Tampilan, AI & Model, Ruang Kerja, Privasi & Data, Notifikasi, dan Lanjutan bila relevan.
- Jangan menumpuk semua pengaturan dalam satu halaman panjang tanpa navigasi.
- Berikan penjelasan singkat di bawah setiap pengaturan.
- Aksi berisiko seperti reset, hapus data, dan keluar akun harus memiliki konfirmasi yang jelas.

## 9. Navigasi dan konsistensi

Pertahankan pengelompokan navigasi yang mudah dipahami:
- **Pekerjaan:** Ruang Kerja, Tim AI.
- **Kemampuan:** Aplikasi, Keahlian, Pengetahuan, Integrasi.
- **Kontrol:** Pusat Akses, Pengaturan.

Ketentuan:
- Label menu gunakan bahasa Indonesia yang konsisten.
- Ikon harus mudah dibedakan dan memiliki tooltip bila perlu.
- Item aktif terlihat jelas tetapi tidak terlalu mencolok.
- Sidebar dapat diciutkan tanpa menghilangkan konteks.
- Hindari label campuran Indonesia/Inggris kecuali nama produk atau istilah yang memang umum.

## 10. Tipografi, layout, dan aksesibilitas

Standar minimum yang disarankan:
- Judul halaman: 20–24 px.
- Judul bagian: 16–18 px.
- Teks utama: 14–16 px.
- Deskripsi: 13–14 px.
- Metadata: idealnya minimal 12 px.
- Hindari teks 9–11 px untuk informasi penting atau instruksi.

Persyaratan:
- Kontras teks dan kontrol memadai pada tema gelap maupun terang.
- Semua aksi penting dapat diakses dengan keyboard.
- Fokus keyboard terlihat jelas.
- Label form tidak hanya berupa placeholder.
- Ikon tanpa teks memiliki accessible name/tooltip.
- Status tidak hanya dibedakan dengan warna.
- Hormati pengaturan reduce motion.
- Area klik tombol dan kontrol cukup besar.
- Modal memiliki urutan fokus dan dapat ditutup dengan cara yang aman.
- Uji pada ukuran jendela desktop kecil dan skala display 125–150%.

## 11. Empty, loading, error, dan success state

Setiap halaman dan alur utama harus memiliki state yang jelas:
- **Kosong:** jelaskan manfaat dan satu langkah berikutnya.
- **Memuat:** indikator proses dan hindari layar kosong.
- **Berhasil:** konfirmasi tindakan dan apa yang berubah.
- **Gagal:** jelaskan penyebab yang dapat dipahami serta tindakan pemulihan.
- **Tidak tersedia:** jelaskan apakah karena OS, koneksi, konfigurasi, atau batas fitur.
- **Membutuhkan izin:** jelaskan izin apa yang dibutuhkan dan mengapa.

Jangan gunakan pesan error teknis mentah sebagai satu-satunya informasi untuk pengguna awam.

## 12. Aturan implementasi teknis

Sebelum mengubah kode:
1. Periksa struktur repo dan implementasi aktual semua halaman.
2. Identifikasi design system, komponen bersama, state management, routing, dan mekanisme penyimpanan.
3. Periksa versi Tauri dan plugin yang tersedia sebelum memilih API native.
4. Periksa backend/model configuration agar UI sesuai perilaku aktual.
5. Identifikasi test yang sudah ada dan tambahkan test sesuai perubahan.
6. Periksa perubahan lokal/uncommitted; jangan menimpa pekerjaan pengguna.

Selama implementasi:
- Gunakan komponen bersama untuk tombol, input, card, badge, dialog, tabs, dan status.
- Gunakan design tokens untuk tema.
- Jangan mengganti backend/API dengan mock.
- Jangan menghapus kemampuan yang sudah ada.
- Jangan membuat data dummy seolah-olah nyata.
- Jangan menampilkan status koneksi, token, model, izin, atau aktivitas yang tidak didukung data aktual.
- Jangan menyimpan secret di frontend.
- Pertahankan sandbox, permission boundary, dan human-in-the-loop.
- Pastikan perubahan diagram tidak melemahkan validasi struktur agen.
- Tambahkan migrasi hanya jika benar-benar diperlukan dan kompatibel dengan data lama.

## 13. Pengujian wajib

### A. Struktur Tim AI
- Root agent tampil benar.
- Banyak agen dan sub-agent tampil sesuai relasi backend.
- Garis koneksi mengikuti relasi aktual.
- Klik node membuka konfigurasi yang benar.
- Tambah, ubah, pindah, dan hapus agen berfungsi.
- Relasi melingkar ditolak.
- Diagram dan daftar selalu konsisten.
- Status animasi hanya aktif ketika status runtime memang aktif.
- Zoom/pan/fit-to-screen tidak menghalangi interaksi dasar.

### B. Model AI
- Mode otomatis dan manual dapat dipilih.
- Provider/model yang dipilih tersimpan per agen.
- Pilihan manual bertahan setelah restart.
- Model yang tidak tersedia menghasilkan pesan yang jelas.
- UI tidak mengganti model diam-diam.
- Model aktual yang dipakai backend sesuai pilihan UI.
- Uji pergantian provider, model, dan kredensial.

### C. API token
- Provider tanpa token ditampilkan dengan benar.
- Provider dengan token menampilkan “Token tersimpan” tanpa mengekspos secret.
- Token baru dapat disimpan dan diperbarui.
- Token dapat dihapus dengan konfirmasi.
- Tes koneksi menunjukkan status yang benar.
- Token tidak muncul dalam response, log, telemetry, crash report, atau screenshot test.

### D. Folder kerja
- Tombol membuka native folder picker pada setiap OS yang didukung.
- Cancel tidak mengubah folder.
- Folder terpilih tersimpan dan ditampilkan benar.
- Buka folder bekerja.
- Folder tidak valid/akses ditolak ditangani.
- Pemilihan folder tidak otomatis memperluas permission.
- Sandbox/path restrictions tetap berlaku.

### E. Tema
- Gelap, terang, dan ikuti sistem berfungsi.
- Preferensi tersimpan setelah restart.
- Perubahan OS diikuti saat mode sistem dipilih.
- Tidak ada komponen yang tertinggal dengan warna tema lama.
- Kontras, fokus, modal, diagram, dan form diuji di kedua tema.

### F. Regression
Jalankan test yang relevan untuk:
- Multi-agent orchestration.
- Agent memory dan adaptive learning.
- Skills dan instalasi skill eksternal.
- MCP/integrasi.
- Computer Use.
- OS permission dan HITL.
- Sandbox dan file operations.
- Credential storage.
- Workspace dan hasil pekerjaan.

Jalankan lint, typecheck, unit/integration tests, build frontend, serta pemeriksaan Rust/Tauri yang sesuai dengan konfigurasi repo.

## 14. Uji kegunaan dengan pengguna nonteknis

Jangan menyatakan UI mudah digunakan hanya berdasarkan penilaian developer.

Lakukan usability test minimal 5 orang yang tidak terbiasa dengan konsep AI agent, dengan tugas:
1. Meminta AKSA membuat dokumen sederhana.
2. Menemukan hasil pekerjaan.
3. Membuat satu agen pendukung dari template.
4. Memilih model AI secara manual.
5. Memastikan token provider sudah tersimpan tanpa melihat token asli.
6. Mengganti folder kerja melalui file manager.
7. Mengubah tema ke terang dan kembali ke gelap.
8. Menolak permintaan akses dan memahami dampaknya.

Target:
- Minimal 4 dari 5 peserta menyelesaikan tugas utama tanpa bantuan.
- Tidak ada kebingungan kritis pada persetujuan izin, token, atau folder.
- Catat tugas yang gagal, waktu penyelesaian, dan bagian UI yang membingungkan.
- Jika usability test belum dilakukan, tulis “belum diuji”, jangan mengklaim lulus.

## 15. Prioritas implementasi

### P0 — Wajib
1. Diagram hierarki multi-agent dengan relasi nyata.
2. Pemilihan model manual dan otomatis.
3. Status token tersimpan/masked, update, delete, dan test connection yang aman.
4. Native folder picker untuk folder workspace.
5. Tema gelap/terang/ikuti sistem.

### P1 — Pengalaman inti
1. Penyederhanaan Ruang Kerja.
2. Penyederhanaan panel konfigurasi agen.
3. Penyempurnaan HITL dan Pusat Akses.
4. Penyederhanaan status dan error provider.
5. Empty/loading/success state.

### P2 — Konsistensi produk
1. Penyempurnaan Aplikasi, Keahlian, Pengetahuan, Integrasi.
2. Navigasi, tipografi, aksesibilitas, dan responsive layout.
3. Reduce motion dan detail visual diagram.
4. Usability test dan perbaikan berdasarkan temuan.

## 16. Deliverables

Setelah implementasi, laporkan:
- Ringkasan perubahan UX/UI.
- Daftar file yang diubah.
- Screenshot sebelum/sesudah untuk halaman utama yang berubah.
- Bukti diagram menggunakan relasi data aktual.
- Bukti pilihan model manual dan otomatis.
- Bukti status token tanpa mengekspos secret.
- Bukti native folder picker di platform yang dapat diuji.
- Bukti tema gelap/terang/ikuti sistem.
- Hasil lint, typecheck, test, dan build beserta status aktual.
- Hasil regression test keamanan.
- Hasil usability test atau pernyataan jujur bahwa belum dilakukan.
- Daftar kekurangan yang masih tersisa.

Jangan mengklaim test berhasil jika tidak benar-benar dijalankan. Bedakan test lokal, CI, dan inspeksi source code.

## 17. Instruksi untuk AI coding agent

Bertindak sebagai **Senior Product Designer, Senior UX Engineer, Frontend Engineer, Tauri/Rust Engineer, Accessibility Specialist, dan QA Engineer**.

Lakukan implementasi langsung pada repository yang sedang terbuka:
1. Audit source code aktual dan pahami arsitektur sebelum mengubah.
2. Gunakan screenshot yang diberikan sebagai referensi kondisi saat ini, bukan sebagai instruksi untuk menyalin layout secara mentah.
3. Pertahankan identitas visual AKSA.
4. Implementasikan semua P0 dan P1; lanjutkan P2 jika tidak mengganggu stabilitas.
5. Jangan hanya membuat rekomendasi atau mockup. Perubahan harus terhubung ke data dan fungsi nyata.
6. Jangan menghapus fitur lanjutan. Sederhanakan tampilan dengan mode Sederhana/Lanjutan.
7. Jaga keamanan token, sandbox, permission, dan persetujuan manusia.
8. Jangan menimpa perubahan pengguna yang belum di-commit.
9. Jalankan test dan laporkan hasil sebenarnya.
10. Jika suatu fitur tidak dapat diimplementasikan karena keterbatasan arsitektur, jelaskan hambatan, bukti, dan alternatif yang aman. Jangan membuat tombol palsu.

## 18. Definisi keberhasilan

AKSA berhasil diperbaiki ketika:
- Pengguna memahami struktur tim AI hanya dengan melihat diagram.
- Pengguna dapat memilih model sendiri tanpa kehilangan opsi otomatis.
- Pengguna tahu token provider sudah tersimpan tanpa dapat melihat secret aslinya.
- Pengguna dapat memilih folder melalui file manager yang familiar.
- Pengguna dapat memilih tema sesuai kenyamanan.
- Pengguna awam dapat menyelesaikan pekerjaan dasar tanpa memahami istilah multi-agent.
- Pengguna tingkat lanjut tetap memiliki akses ke konfigurasi teknis.
- Seluruh perubahan tidak melemahkan keamanan dan tidak merusak fitur yang sudah ada.

**Prinsip produk: AKSA harus sederhana di permukaan, transparan dalam meminta izin, dan tetap canggih di dalam.**