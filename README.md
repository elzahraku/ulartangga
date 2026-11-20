# Bot Ular Tangga (maks 4 pemain) + Mini App

1. `pip install -r requirements.txt`, salin `.env.example` ke `.env` dan isi.
2. `BASE_URL` WAJIB https (Telegram menolak http). Arahkan domain/reverse proxy (nginx / cloudflared)
   ke `PORT` (default 8095, bukan 8080 supaya tidak bentrok dengan bot lain di VPS).
3. `python bot.py`

Alur: `/start` atau `/ulartangga` di grup/privat -> lobby (Gabung / Keluar / Mulai / Tutup, maks 4)
-> host menekan Mulai -> tombol **Main** membuka Mini App.
Di grup, tombol Main membuka chat bot lalu tombol WebApp; isi `MINIAPP_SHORTNAME` agar langsung terbuka.

Aturan: dadu 1-6 dilempar server, harus pas di kotak 100, angka 6 = giliran lagi,
lewat 60 detik dadu dilempar otomatis.
