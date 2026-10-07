# CodinX Termux

> **Agent coding berbasis terminal untuk Linux dan Termux** — tulis kode, jalankan perintah, gunakan tools, dan verifikasi hasil langsung dari terminal.

CodinX adalah coding agent berbasis Python yang dirancang untuk berjalan ringan di **Termux tanpa root**, Linux, container, dan lingkungan pengembangan lainnya. Proyek ini menggunakan Python standard library dengan Pygments yang sudah tersedia di dalam vendor proyek.

[![Platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-00a884?style=flat-square)](docs/TERMUX.md)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

## Fitur utama

- **Coding agent interaktif** untuk membaca, menulis, mengedit, dan memeriksa kode.
- **Dukungan Termux tanpa root** dengan deteksi lingkungan dan warna terminal otomatis.
- **Live autocomplete**: ketik `/` untuk mencari command, serta dukungan `@file` dan skill.
- **17 tools bawaan**, termasuk `read`, `write`, `edit`, `grep`, `glob`, `bash`, `webfetch`, `websearch`, `todo`, `task`, `skill`, `memory`, dan MCP.
- **42 skills** siap pakai untuk debugging, testing, dokumentasi, GitHub, keamanan, deployment, dan kebutuhan lainnya.
- **Sub-agent** untuk membagi pekerjaan seperti eksplorasi, testing, review, dokumentasi, dan audit keamanan.
- **Memori sesi** agar percakapan dan pekerjaan dapat dilanjutkan.
- **Permission guard** untuk meminta izin sebelum operasi sensitif dan memblokir perintah destruktif.
- **UI terminal yang dapat dikustomisasi** dengan tema, banner, spinner, prompt, Markdown berwarna, dan syntax highlighting.
- **Kompatibilitas proxy** dengan mode otomatis untuk function calling, tool berbasis teks, dan chat fallback.
- **MCP server** untuk memperluas kemampuan agent dengan server eksternal.

## Instalasi cepat di Termux

Pastikan Python tersedia:

```bash
pkg update
pkg install python git unzip
```

Clone repositori dan jalankan installer:

```bash
git clone https://github.com/muhammadfahri190713-afk/CodinXTermux.git
cd CodinXTermux
bash install.sh
```

Setelah instalasi, jalankan:

```bash
codinx
```

Jika tidak ingin memasang secara permanen, jalankan langsung dari folder proyek:

```bash
python3 bin/codinx
```

> Installer mendeteksi `$PREFIX` secara otomatis di Termux. Python **3.9 atau lebih baru** diperlukan.

## Konfigurasi API

Buat konfigurasi lokal dari template:

```bash
cp api.example.py api.py
```

Kemudian isi API key dan endpoint sesuai kebutuhan di `api.py`. File `api.py` dan `.env` tidak boleh dibagikan karena dapat berisi kredensial. Keduanya sudah dilindungi oleh `.gitignore`.

Konfigurasi lengkap tersedia di [docs/CONFIG.md](docs/CONFIG.md). Endpoint bawaan proyek adalah:

```text
https://inttelix.vercel.app/api/v1
```

## Contoh penggunaan

Mulai sesi interaktif:

```bash
codinx
```

Berikan tugas langsung secara non-interaktif:

```bash
codinx run "buat web todo sederhana" --auto
codinx run -c "lanjutkan pekerjaan sebelumnya"
codinx run "/skill debug-fix error pada aplikasi saya"
codinx run "jelaskan file @src/main.py" --format json
```

Perintah berguna di dalam sesi:

| Perintah | Kegunaan |
|---|---|
| `/help` | Melihat daftar perintah |
| `/plan` | Membuat rencana read-only |
| `/diff` | Melihat perubahan |
| `/undo` / `/redo` | Membatalkan atau mengulangi perubahan |
| `/skills` | Melihat semua skill |
| `/skill <nama>` | Menjalankan skill tertentu |
| `/theme` | Mengganti tema terminal |
| `/remember` | Menyimpan memori jangka panjang |
| `@file` | Menyertakan isi file ke prompt |
| `!perintah` | Menjalankan perintah shell |

## Struktur proyek

```text
.
├── agents/          # Sub-agent bawaan
├── bin/             # Entry point perintah codinx
├── commands/        # Command/prompt siap pakai
├── completions/     # Autocomplete Bash dan shell
├── cx/              # Source code utama CodinX
├── data/            # Data dan konfigurasi model
├── docs/            # Dokumentasi teknis lengkap
├── examples/        # Contoh konfigurasi, hooks, dan MCP
├── scripts/         # Tool build, dokumentasi, vendor, dan security scan
├── skills/          # Skill bawaan CodinX
├── tests/           # Test suite
├── api.example.py   # Template konfigurasi API
├── install.sh       # Installer Linux/Termux
└── uninstall.sh     # Uninstaller
```

## Dokumentasi

| Topik | Dokumentasi |
|---|---|
| Arsitektur | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Daftar command | [docs/COMMANDS.md](docs/COMMANDS.md) |
| Konfigurasi dan environment | [docs/CONFIG.md](docs/CONFIG.md) |
| Termux dan Linux | [docs/TERMUX.md](docs/TERMUX.md) |
| Desain terminal | [docs/DESIGN.md](docs/DESIGN.md) |
| Skills | [docs/SKILLS.md](docs/SKILLS.md) |
| Sub-agent | [docs/SUBAGENTS.md](docs/SUBAGENTS.md) |
| Hooks | [docs/HOOKS.md](docs/HOOKS.md) |
| MCP | [docs/MCP.md](docs/MCP.md) |
| Permission dan keamanan | [docs/PERMISSIONS.md](docs/PERMISSIONS.md) |
| Kompatibilitas proxy | [docs/PROXY_COMPAT.md](docs/PROXY_COMPAT.md) |
| Troubleshooting | [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) |
| Kontribusi | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Keamanan | [SECURITY.md](SECURITY.md) |

## Testing dan pengembangan

Jalankan test suite:

```bash
make test
```

Pemeriksaan keamanan dan pembuatan dokumentasi:

```bash
make scan
make docs
```

Sebelum melakukan push, jalankan secret scan:

```bash
python3 scripts/secret_scan.py .
```

## Model dan mode trial

Dalam mode trial (`trial_mode`, aktif secara bawaan), model yang tersedia dapat digunakan tanpa kunci paket tambahan. Untuk menonaktifkannya:

```bash
export CODINX_TRIAL=0
```

Aturan paket dan pembatasan penggunaan dijelaskan di dokumentasi konfigurasi. Penegakan penggunaan yang sebenarnya tetap bergantung pada proxy/API yang digunakan.

## Keamanan

- Jangan commit `api.py`, `.env`, atau kredensial apa pun.
- Tinjau perubahan dengan `/diff` sebelum menyetujui operasi agent.
- Jalankan `python3 scripts/secret_scan.py .` sebelum membagikan kode.
- Baca [SECURITY.md](SECURITY.md) untuk pelaporan kerentanan dan panduan keamanan.

## Lisensi

CodinX dirilis di bawah [MIT License](LICENSE). Komponen pihak ketiga tercantum di [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

**Repository:** https://github.com/muhammadfahri190713-afk/CodinXTermux
