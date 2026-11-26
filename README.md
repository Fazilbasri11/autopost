# Auto-Post Utas Threads (Google Sheets + Gemini AI + GitHub Actions)

Sistem otomatis yang berjalan setiap **3 jam sekali** di cloud gratis (GitHub Actions):
1. Membaca produk aktif dari **Google Sheets** (otomatis memilih produk yang paling jarang diposting).
2. Meminta **Gemini AI** membuat utas **7–8 bagian** bergaya santai (`gue/lo`), edukatif dulu (hook + fase masalah + tips), pengenalan produk beserta alasan & kekurangannya secara jujur, link produk di postingan ke-2 terakhir, dan ditutup ajakan diskusi di komentar.
3. Memposting utas berantai ke **Threads** melalui Meta Threads API resmi.
4. Mengupdate kolom `Total_Post`, `Terakhir_Post`, dan `Catatan_Angle` di Google Sheets.

---

## Langkah 1: Siapkan Google Sheets
1. Buat Google Sheet baru di akun Google kamu.
2. Pastikan nama tab sheet di bawah adalah **`Produk`**.
3. Isi **Baris 1 (Header)** kolom A sampai H persis seperti ini:
   `Produk` | `Keunggulan` | `Link_Produk` | `Image_URL` | `Aktif` | `Total_Post` | `Terakhir_Post` | `Catatan_Angle`
   *(Opsional: kamu juga bisa menambahkan kolom `Niche`, `Kekurangan`, dan `Topic` jika ingin AI lebih spesifik — kalau `Topic` dikosongkan, AI otomatis memilihkan tag topik biru Threads yang relevan).*
4. Isi baris ke-2 dan seterusnya dengan produkmu:
   - `Link_Produk`: boleh 1 link atau beberapa link sekaligus (pisahkan dengan baris baru / spasi) kalau 1 baris berisi paket beberapa produk.
   - `Aktif`: isi `YA` kalau mau ikut dirotasi, `TIDAK` kalau mau dijeda.
   - `Image_URL`: boleh dikosongkan (teks saja), atau isi URL gambar publik langsung (`.jpg`/`.png`).
   - `Total_Post`, `Terakhir_Post`, `Catatan_Angle`: biarkan kosong (akan diisi otomatis).
5. Buka menu **Extensions → Apps Script**, hapus kode bawaan, lalu copy-paste seluruh isi file [`google_apps_script.js`](google_apps_script.js).
6. Ubah `SECRET_KEY` di baris atas kode menjadi kata sandi acak buatanmu (catat ini untuk `SHEET_SECRET`).
7. Klik **Deploy → New deployment → Web app**:
   - **Execute as:** `Me`
   - **Who has access:** `Anyone`
   - Klik **Deploy**, izinkan akses (*Advanced → Go to ...*), lalu salin **Web App URL**-nya (simpan sebagai `SHEET_WEBHOOK_URL`).

---

## Langkah 2: Ambil Gemini API Key (Gratis)
1. Buka [Google AI Studio](https://aistudio.google.com/).
2. Login akun Google → klik **Get API key → Create API key**.
3. Simpan API key tersebut (sebagai `GEMINI_API_KEY`).

---

## Langkah 3: Ambil Threads User ID & Access Token
1. Buka [Meta for Developers](https://developers.facebook.com/) → buat App baru → pilih use case **Access the Threads API**.
2. Di menu **Threads API / Permissions**, aktifkan permission:
   - `threads_basic`
   - `threads_content_publish`
3. Tambahkan akun Threads kamu sebagai **Threads Tester** di menu *App Roles → Roles*, lalu buka aplikasi Threads di HP/web (`Settings → Account → Website permissions → Tester invites`) dan klik **Accept**.
4. Gunakan **Graph API Explorer** / generator token di dashboard app Meta untuk mendapatkan Access Token, lalu tukar menjadi **Long-Lived Token** (berlaku 60 hari) dan cek User ID kamu (`GET https://graph.threads.net/v1.0/me?fields=id,username&access_token=TOKEN`).
5. Catat **`THREADS_USER_ID`** (angka ID akun) dan **`THREADS_ACCESS_TOKEN`**.

> **Catatan Token 60 Hari:** Setiap ~45-50 hari sekali, jalankan `python refresh_token.py` (atau buka endpoint `refresh_access_token`) untuk memperpanjang masa aktif token selama 60 hari lagi, lalu update secret `THREADS_ACCESS_TOKEN` di GitHub.

---

## Langkah 4: Upload ke GitHub & Aktifkan Jadwal 3 Jam
1. Buat repository baru di [GitHub](https://github.com/new) (pilih **Private** agar aman).
2. Upload seluruh isi folder project ini (termasuk folder `.github/workflows/autopost.yml`).
3. Di repository GitHub, buka **Settings → Secrets and variables → Actions → New repository secret**, lalu tambahkan 5 secret berikut:
   - `SHEET_WEBHOOK_URL`
   - `SHEET_SECRET`
   - `GEMINI_API_KEY`
   - `THREADS_USER_ID`
   - `THREADS_ACCESS_TOKEN`
4. Buka tab **Actions** di GitHub → pilih workflow **Auto-Post Utas Threads** → klik **Run workflow**:
   - Coba jalankan dulu dengan `dry_run = true` untuk mengecek apakah koneksi Sheet & hasil utas Gemini AI sudah bagus.
   - Kalau sudah oke, jalankan dengan `dry_run = false`, dan selanjutnya jadwal `0 */3 * * *` akan otomatis memposting setiap 3 jam (`07:00`, `10:00`, `13:00`, `16:00`, `19:00`, `22:00`, `01:00`, `04:00` WIB).
