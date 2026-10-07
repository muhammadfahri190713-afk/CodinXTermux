# Pemberitahuan pihak ketiga

## Pygments (disertakan di `cx/vendor/pygments`)
Dipakai untuk syntax highlighting blok kode di terminal. Subset lexer disalin apa adanya (tanpa modifikasi isi lexer);
hanya `lexers/_mapping.py` dibuat ulang agar sesuai modul yang disertakan (lihat `scripts/vendor_pygments.py`).

- Proyek: https://pygments.org
- Lisensi: BSD-2-Clause — teks lengkap di `cx/vendor/PYGMENTS_LICENSE`, daftar penulis di `cx/vendor/PYGMENTS_AUTHORS`.
- Versi: lihat `cx/vendor/PYGMENTS_VERSION`.

Bila Pygments tidak bisa dimuat, CodinX otomatis jatuh ke teks polos tanpa warna sintaks.

## Pustaka lain di `cx/vendor` (tanpa modifikasi)
| Pustaka | Lisensi | Dipakai untuk |
|---|---|---|
| markdown-it-py + mdurl | MIT | penampil Markdown `/docs` `/view` |
| tabulate | MIT | ekspor tabel (.txt .rst .html .tex .org) |
| PyYAML (bagian murni-Python) | MIT | ekspor YAML, skrip `yamlpp.py` |
| tzdata IANA (berkas zoneinfo) | domain publik | zona waktu pada perangkat tanpa tzdata (Android/Termux) |

Teks lisensi ada di `cx/vendor/licenses/`. Dibangun ulang dengan `scripts/vendor_libs.py`.
