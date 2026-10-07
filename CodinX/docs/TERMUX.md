# Termux & Linux

CodinX berjalan di **Linux (root atau user biasa)** dan **Termux (Android)** tanpa root.

## Termux — pasang & jalankan
```bash
pkg update && pkg install python git          # nodejs opsional (untuk `npm run`)
unzip CodinX.zip && cd CodinX
cp api.example.py api.py && nano api.py        # isi API_KEY (atau pakai .env / environment)
python3 bin/codinx                             # atau: bash install.sh  →  ketik: codinx
```
`install.sh` memasang ke `$PREFIX/share/codinx` dan membuat pembungkus `$PREFIX/bin/codinx` (bukan symlink, jadi tidak butuh `/usr/bin/env`).

## Penyesuaian otomatis untuk Termux
- Warna **truecolor** otomatis (`TERMUX_VERSION`); latar terang/gelap dideteksi untuk tema `auto`. Tombol ekstra Termux (↑ ↓ Tab Esc) bekerja di popup saran.
- Layar sempit: `/design termux` (banner ringkas, prompt `›`, kerapatan compact); tabel membungkus teks, popup memotong deskripsi.
- Zona waktu memakai salinan tzdata bawaan bila Android tidak punya (reset Dinar tengah malam lokal tetap benar).
- Brankas kunci memakai ID acak per-instalasi (Android tak punya `/etc/machine-id`).
- Kamera: bila **Termux:API** terpasang, tool `camera` memakai `termux-camera-photo` (aktifkan izinnya di `/permissions`).
- File sementara memakai `$TMPDIR`, bukan `/tmp`. Shell tool memakai bash/sh yang tersedia.

## Linux
Root maupun user biasa. `CODINX_REQUIRE_ROOT=1` mewajibkan root. Data di `~/.codinx` (ubah dengan `CODINX_HOME`).

## Masalah umum
| Gejala | Solusi |
|---|---|
| Semua tampak abu-abu / tanpa warna | `/colors`; `CODINX_COLOR=truecolor`; ganti tema `/theme`; latar terang: `/theme light` |
| Garis/ikon jadi kotak "?" | font tidak mendukung: `/icons ascii` dan `/border ascii` |
| Popup saran mengganggu | `CODINX_SIMPLE_INPUT=1` |
| `python3: not found` | `pkg install python` |
