# Desain terminal

CodinX punya sistem desain yang bisa diatur per pengguna: **tema warna**, **preset**, dan pilihan terpisah untuk banner, garis, spinner, ikon, prompt, gutter, baris status, dan kerapatan.

## Tema (`/theme`)
`/theme` membuka pemilih dengan **pratinjau langsung** (↑↓ pilih, ketik untuk mencari, Enter terapkan, Esc batal).
- `auto` (bawaan): mendeteksi latar terminal (OSC 11, lalu `COLORFGBG`) → `codinx` untuk latar gelap, `codinx-light` untuk latar terang.
- 49 tema, gelap & terang: codinx, aurora, neon, terracotta, opencode, tokyonight (+storm/day), catppuccin (mocha/macchiato/frappe/latte),
  dracula, nord, gruvbox (+light), solarized (dark/light), one (dark/light), monokai, rose-pine (+moon/dawn), kanagawa, everforest (+light),
  ayu (+light), nightfox, github (dark/light), palenight, night-owl, synthwave, oxocarbon, poimandres, vesper, zenburn, horizon,
  matrix, amber, paper, contrast (+light), colorblind (palet Okabe-Ito), system (palet ANSI terminal).
- Setiap tema dicek kontrasnya (WCAG) terhadap latarnya: teks ≥ 7:1, redup ≥ 4:1, aksen ≥ 3,5:1.
- Warna kode (syntax highlighting) dibangun dari palet tema aktif sehingga selalu senada.
- `/theme test` (atau `/colors`) menampilkan kedalaman warna terminal dan swatch untuk diagnosa.

## Kedalaman warna (mengapa UI bisa tampak abu-abu)
Terdeteksi otomatis: truecolor (24-bit) → 256 → 16 → tanpa warna. Termux selalu dianggap truecolor. Paksa dengan `CODINX_COLOR=truecolor|256|16|never|always`;
`NO_COLOR` dihormati. Pemetaan ke 256/16 warna memakai jarak warna terdekat (bukan ambang kasar), jadi aksen tetap berwarna di terminal terbatas.
Latar terang dengan tema gelap membuat teks terang tak terbaca → pakai `/theme auto` atau `/theme light`.

## Preset (`/design`)
`codinx` (bawaan) · `opencode` · `claude` · `codex` · `minimal` · `retro` · `neon` · `paper` · `contrast` · `termux`.
`/design` membuka pemilih preset (pratinjau langsung). `/design save <nama>` menyimpan preset sendiri; `/design reset`, `/design show`, `/design set <kunci> <nilai>`.

## Pilihan satuan
| Perintah | Pilihan |
|---|---|
| `/banner` | pro · block · slant · small · wide · boxed · mini · none |
| `/border` | rounded · square · heavy · double · ascii · minimal |
| `/spinner` | 30 gaya (dots, dots2, line, pulse, star, moon, bounce, arc, …) |
| `/icons` | auto · unicode · ascii · nerd · emoji |
| `/prompt` | bar ┃ · arrow ❯ · chevron › · dollar $ · triangle ▶ · lambda λ · plain > |
| `/gutter` | none · bar · dot · line (penanda di kiri jawaban) |
| `/footer` | dots · pills · bar · minimal (baris status) |
| `/density` | comfortable · compact (hemat baris, cocok layar ponsel) |

Terminal tanpa UTF-8 otomatis memakai ASCII (border, ikon, spinner, prompt).

## Saran otomatis saat mengetik
Ketik `/` → daftar perintah muncul dan menyempit tiap huruf (`/h` → `/help` teratas). ↑↓ pilih · **Tab** lengkapi (awalan terpanjang) · **Enter** jalankan · **Esc** tutup.
Berlaku juga untuk argumen (`/theme tok`), `@file`, dan `$skill`. `CODINX_SIMPLE_INPUT=1` mematikan popup.

## Sumber palet
Palet disesuaikan dari spesifikasi warna publik masing-masing tema (Catppuccin, Tokyo Night, Rosé Pine, Dracula, Nord, Gruvbox, Solarized, One, Monokai,
Kanagawa, Everforest, Ayu, Nightfox, GitHub, Material Palenight, Night Owl, Synthwave '84, Carbon/Oxocarbon, Poimandres, Vesper, Zenburn, Horizon).
Daftar spinner mengikuti koleksi cli-spinners. Nilai Catppuccin diverifikasi terhadap palet resminya.
