"""Tema warna + deteksi kemampuan terminal (none/16/256/truecolor) + deteksi latar terang/gelap.

Masalah "UI abu-abu" biasanya bukan bug tema, melainkan: (1) terminal dianggap hanya 256-warna sehingga warna aksen
dipetakan kasar, (2) garis/footer/petunjuk semuanya memakai satu warna redup, atau (3) tema gelap dipakai di latar terang.
Modul ini menyelesaikan ketiganya:

  * kedalaman warna terdeteksi dari env (COLORTERM, TERM, TERMUX_VERSION, WT_SESSION, ...) dan bisa dipaksa
    lewat CODINX_COLOR=never|16|256|truecolor|always (NO_COLOR dihormati, FORCE_COLOR=1/2/3 didukung);
  * warna dipetakan ke 256/16 warna lewat jarak warna terdekat (bukan ambang kasar);
  * latar terang/gelap dideteksi (OSC 11, lalu COLORFGBG) bila tema "auto";
  * tiap tema dicek kontrasnya terhadap latarnya (WCAG) sehingga teks redup tetap terbaca.
"""
import os
import re
import sys

RESET = "\033[0m"
BOLD = "\033[1m"
UNBOLD = "\033[22m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
YELLOW_BRIGHT = "\033[1;93m"    # prompt izin: selalu kuning cerah

ROLES = ("accent", "accent2", "text", "muted", "ok", "warn", "err", "info", "border", "code", "link", "heading", "user", "surface")


# ------------------------------------------------------------------ util warna
def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in rgb)


def mix(a, b, t):
    """Campur dua warna hex: t=0 -> a, t=1 -> b."""
    ca, cb = _rgb(a), _rgb(b)
    return _hex([x + (y - x) * t for x, y in zip(ca, cb)])


def luminance(h):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg, bg, minimum, toward=None):
    """Geser fg menjauhi bg sampai rasio kontras >= minimum."""
    if toward is None:
        toward = "#FFFFFF" if luminance(bg) < 0.4 else "#000000"
    cur = fg
    for _ in range(14):
        if contrast(cur, bg) >= minimum:
            break
        cur = mix(cur, toward, 0.12)
    return cur


# ------------------------------------------------------------------ registri tema
THEMES = {}
META = {}


def _reg(name, family, dark, bg, text, muted, accent, accent2, ok, warn, err, info, border=None, code=None, link=None,
         heading=None, user=None, surface=None):
    fix = lambda col, ratio: ensure_contrast(col, bg, ratio)
    th = dict(
        text=fix(text, 7.0), muted=fix(muted, 4.0), accent=fix(accent, 3.5), accent2=fix(accent2, 3.5),
        ok=fix(ok, 3.5), warn=fix(warn, 3.5), err=fix(err, 3.5), info=fix(info, 3.5),
    )
    th["border"] = fix(border or mix(th["muted"], th["accent"], 0.45), 3.0)
    th["code"] = fix(code or th["info"], 4.5)
    th["link"] = fix(link or th["accent2"], 4.0)
    th["heading"] = fix(heading or th["accent"], 4.0)
    th["user"] = fix(user or th["accent"], 4.0)
    th["surface"] = surface or mix(bg, th["text"], 0.10)
    THEMES[name] = th
    META[name] = {"family": family, "dark": dark, "bg": bg}


# --- bawaan CodinX
_reg("codinx", "codinx", True, "#14141F", "#E8E8F2", "#8E8EAA", "#8B7CFF", "#22E6C4", "#5CF28E", "#F5E27A", "#FF6B7A", "#5CC8FF")
_reg("aurora", "codinx", True, "#0B1020", "#E2E8F0", "#8492A6", "#5EEAD4", "#A78BFA", "#4ADE80", "#FBBF24", "#FB7185", "#38BDF8")
_reg("neon", "codinx", True, "#0D0221", "#F5F0FF", "#9A86B8", "#FF2E97", "#00F0FF", "#39FF14", "#FFE600", "#FF3860", "#00B3FF")
_reg("terracotta", "codinx", True, "#1C1B19", "#F3F1EA", "#9A968B", "#D97757", "#E8A87C", "#8FBF6A", "#E5B567", "#E5675F", "#6FA8DC")
_reg("opencode", "opencode", True, "#0A0A0A", "#EEEEEE", "#8A8A8A", "#FAB283", "#5C9CF5", "#7FD88F", "#F5A742", "#E06C75", "#56B6C2",
     code="#9D7CD8")
# --- keluarga populer (palet publik; lihat docs/DESIGN.md untuk sumber)
_reg("tokyonight", "tokyonight", True, "#1A1B26", "#C0CAF5", "#6F7BB0", "#7AA2F7", "#BB9AF7", "#9ECE6A", "#E0AF68", "#F7768E", "#7DCFFF")
_reg("tokyonight-storm", "tokyonight", True, "#24283B", "#C0CAF5", "#7A86BE", "#7AA2F7", "#BB9AF7", "#9ECE6A", "#E0AF68", "#F7768E", "#7DCFFF")
_reg("tokyonight-day", "tokyonight", False, "#E1E2E7", "#3760BF", "#6172B0", "#2E7DE9", "#9854F1", "#587539", "#8C6C3E", "#F52A65", "#007197")
_reg("catppuccin-mocha", "catppuccin", True, "#1E1E2E", "#CDD6F4", "#7F849C", "#CBA6F7", "#89DCEB", "#A6E3A1", "#F9E2AF", "#F38BA8", "#89B4FA")
_reg("catppuccin-macchiato", "catppuccin", True, "#24273A", "#CAD3F5", "#8087A2", "#C6A0F6", "#91D7E3", "#A6DA95", "#EED49F", "#ED8796", "#8AADF4")
_reg("catppuccin-frappe", "catppuccin", True, "#303446", "#C6D0F5", "#838BA7", "#CA9EE6", "#99D1DB", "#A6D189", "#E5C890", "#E78284", "#8CAAEE")
_reg("catppuccin-latte", "catppuccin", False, "#EFF1F5", "#4C4F69", "#6C6F85", "#8839EF", "#04A5E5", "#40A02B", "#DF8E1D", "#D20F39", "#1E66F5")
_reg("dracula", "dracula", True, "#282A36", "#F8F8F2", "#7A88BF", "#BD93F9", "#FF79C6", "#50FA7B", "#F1FA8C", "#FF5555", "#8BE9FD")
_reg("nord", "nord", True, "#2E3440", "#D8DEE9", "#7B88A1", "#88C0D0", "#81A1C1", "#A3BE8C", "#EBCB8B", "#BF616A", "#8FBCBB")
_reg("gruvbox", "gruvbox", True, "#282828", "#EBDBB2", "#A89984", "#FE8019", "#B8BB26", "#B8BB26", "#FABD2F", "#FB4934", "#83A598")
_reg("gruvbox-light", "gruvbox", False, "#FBF1C7", "#3C3836", "#7C6F64", "#AF3A03", "#427B58", "#79740E", "#B57614", "#9D0006", "#076678")
_reg("solarized-dark", "solarized", True, "#002B36", "#93A1A1", "#657B83", "#268BD2", "#2AA198", "#859900", "#B58900", "#DC322F", "#6C71C4")
_reg("solarized-light", "solarized", False, "#FDF6E3", "#586E75", "#7F9090", "#268BD2", "#2AA198", "#859900", "#B58900", "#DC322F", "#6C71C4")
_reg("one-dark", "one", True, "#282C34", "#ABB2BF", "#7F848E", "#61AFEF", "#C678DD", "#98C379", "#E5C07B", "#E06C75", "#56B6C2")
_reg("one-light", "one", False, "#FAFAFA", "#383A42", "#696C77", "#4078F2", "#A626A4", "#50A14F", "#C18401", "#E45649", "#0184BC")
_reg("monokai", "monokai", True, "#272822", "#F8F8F2", "#90906F", "#FD971F", "#66D9EF", "#A6E22E", "#E6DB74", "#F92672", "#AE81FF")
_reg("rose-pine", "rose-pine", True, "#191724", "#E0DEF4", "#908CAA", "#C4A7E7", "#EBBCBA", "#9CCFD8", "#F6C177", "#EB6F92", "#5B9DB8")
_reg("rose-pine-moon", "rose-pine", True, "#232136", "#E0DEF4", "#908CAA", "#C4A7E7", "#EA9A97", "#9CCFD8", "#F6C177", "#EB6F92", "#6AAFCB")
_reg("rose-pine-dawn", "rose-pine", False, "#FAF4ED", "#575279", "#797593", "#907AA9", "#56949F", "#286983", "#EA9D34", "#B4637A", "#D7827E")
_reg("kanagawa", "kanagawa", True, "#1F1F28", "#DCD7BA", "#8A8980", "#7E9CD8", "#957FB8", "#98BB6C", "#E6C384", "#E46876", "#7FB4CA")
_reg("everforest", "everforest", True, "#2D353B", "#D3C6AA", "#859289", "#A7C080", "#7FBBB3", "#A7C080", "#DBBC7F", "#E67E80", "#83C092")
_reg("everforest-light", "everforest", False, "#FDF6E3", "#5C6A72", "#829181", "#8DA101", "#35A77C", "#6F8300", "#B07F00", "#E0403E", "#3A94C5")
_reg("ayu", "ayu", True, "#1F2430", "#CCCAC2", "#8A919E", "#FFCC66", "#73D0FF", "#D5FF80", "#FFAD66", "#F28779", "#5CCFE6")
_reg("ayu-light", "ayu", False, "#FAFAFA", "#5C6166", "#787B80", "#FF9940", "#399EE6", "#86B300", "#F2AE49", "#F07171", "#55B4D4")
_reg("nightfox", "nightfox", True, "#192330", "#CDCECF", "#8A97A8", "#719CD6", "#9D79D6", "#81B29A", "#DBC074", "#C94F6D", "#63CDCF")
_reg("github-dark", "github", True, "#0D1117", "#C9D1D9", "#8B949E", "#58A6FF", "#D2A8FF", "#3FB950", "#D29922", "#F85149", "#79C0FF")
_reg("github-light", "github", False, "#FFFFFF", "#1F2328", "#656D76", "#0969DA", "#8250DF", "#1A7F37", "#9A6700", "#CF222E", "#0550AE")
_reg("palenight", "material", True, "#292D3E", "#A6ACCD", "#7F86B5", "#C792EA", "#82AAFF", "#C3E88D", "#FFCB6B", "#F07178", "#89DDFF")
_reg("night-owl", "night-owl", True, "#011627", "#D6DEEB", "#7C9696", "#82AAFF", "#C792EA", "#ADDB67", "#ECC48D", "#EF5350", "#7FDBCA")
_reg("synthwave", "synthwave", True, "#262335", "#FFFFFF", "#9AA1D6", "#FF7EDB", "#36F9F6", "#72F1B8", "#FEDE5D", "#FE4450", "#B893CE")
_reg("oxocarbon", "carbon", True, "#161616", "#DDE1E6", "#8D8D8D", "#78A9FF", "#BE95FF", "#42BE65", "#F1C21B", "#EE5396", "#33B1FF")
_reg("poimandres", "poimandres", True, "#1B1E28", "#A6ACCD", "#8C93B8", "#5DE4C7", "#ADD7FF", "#5DE4C7", "#FFFAC2", "#D0679D", "#89DDFF")
_reg("vesper", "vesper", True, "#101010", "#E6E6E6", "#8B8B8B", "#FFC799", "#99FFE4", "#99FFE4", "#FFC799", "#FF8080", "#99C2FF")
_reg("zenburn", "zenburn", True, "#3F3F3F", "#DCDCCC", "#9FAF9F", "#8CD0D3", "#DC8CC3", "#9FC59F", "#F0DFAF", "#CC9393", "#93E0E3")
_reg("horizon", "horizon", True, "#1C1E26", "#D5D8DA", "#8A8DB0", "#E95678", "#25B0BC", "#29D398", "#FAB795", "#F43E5C", "#26BBD9")
# --- gaya khusus
_reg("matrix", "retro", True, "#000000", "#B6FFB6", "#3FAE5A", "#00FF41", "#00D9A0", "#00FF41", "#CCFF00", "#FF3131", "#00D9A0")
_reg("amber", "retro", True, "#1A1000", "#FFCF66", "#C49030", "#FFB000", "#FF8C00", "#C6FF66", "#FFD24A", "#FF5B3A", "#FFE29A")
_reg("paper", "paper", False, "#F4ECD8", "#433422", "#7A6A53", "#8B4513", "#2E6F5E", "#3F7D20", "#9A6A00", "#A62B1F", "#2B5D8A")
_reg("codinx-light", "codinx", False, "#F8F8FC", "#20202E", "#666680", "#5B3FD9", "#00806A", "#1A7F37", "#8A6100", "#C4162A", "#0B63C5")
# --- aksesibilitas
_reg("contrast", "accessible", True, "#000000", "#FFFFFF", "#C0C0C0", "#FFFF00", "#00FFFF", "#00FF00", "#FFA500", "#FF5F5F", "#5FAFFF")
_reg("contrast-light", "accessible", False, "#FFFFFF", "#000000", "#3D3D3D", "#0000EE", "#7A0099", "#006400", "#7A4F00", "#B00020", "#00598A")
_reg("colorblind", "accessible", True, "#121212", "#ECECEC", "#9A9A9A", "#E69F00", "#56B4E9", "#2FD2A5", "#F0E442", "#FF7A33", "#CC79A7")
# --- ikuti palet ANSI terminal (tidak memaksa warna)
THEMES["system"] = {r: "ansi:" + n for r, n in zip(ROLES, ("35", "36", "39", "90", "32", "33", "31", "34", "90", "36", "36", "35", "35", "40"))}
META["system"] = {"family": "system", "dark": True, "bg": "#000000"}

DEFAULT_DARK = "codinx"
DEFAULT_LIGHT = "codinx-light"
DEPRECATED = {"catppuccin": "catppuccin-mocha", "tokyo-night": "tokyonight", "one": "one-dark"}   # nama lama -> baru

# ------------------------------------------------------------------ deteksi kemampuan terminal
_cur = DEFAULT_DARK
_depth = 0                   # 0 = tanpa warna, 16, 256, 24 (truecolor)
ENABLED = False
TRUE = False
_cache = {}


def _termux():
    return bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get("PREFIX", "")


def detect_depth(env=None, isatty=None):
    """-> 0 | 16 | 256 | 24.  Urutan: CODINX_COLOR, NO_COLOR, FORCE_COLOR, bukan-TTY, COLORTERM, Termux, TERM_PROGRAM, TERM."""
    e = os.environ if env is None else env
    tty = sys.stdout.isatty() if isatty is None else isatty
    pref = (e.get("CODINX_COLOR") or "auto").strip().lower()
    forced = {"16": 16, "256": 256, "truecolor": 24, "24bit": 24, "24": 24}
    if pref in ("never", "no", "0", "off", "none"):
        return 0
    if pref in forced:
        return forced[pref]
    always = pref in ("always", "yes", "1", "on", "force")
    if e.get("NO_COLOR") and not always:
        return 0
    fc = (e.get("FORCE_COLOR") or "").strip()
    if fc in ("1", "2", "3") and not tty:
        return {"1": 16, "2": 256, "3": 24}[fc]
    if not tty and not always:
        return 0
    term = (e.get("TERM") or "").lower()
    if term == "dumb":
        return 0 if not always else 16
    colorterm = (e.get("COLORTERM") or "").lower()
    prog = e.get("TERM_PROGRAM") or ""
    if colorterm in ("truecolor", "24bit") or "truecolor" in term or "24bit" in term or "direct" in term:
        return 24
    if e.get("TERMUX_VERSION") or "com.termux" in e.get("PREFIX", ""):
        return 24                                # Termux mendukung 24-bit meski COLORTERM tidak di-set
    if prog in ("iTerm.app", "vscode", "WezTerm", "Hyper", "ghostty") or e.get("WT_SESSION") or e.get("KITTY_WINDOW_ID") \
            or e.get("ALACRITTY_LOG") or any(k in term for k in ("kitty", "alacritty", "foot", "wezterm", "ghostty")):
        return 24
    if "256color" in term or prog == "Apple_Terminal":
        return 256
    if e.get("COLORTERM") or term.startswith(("xterm", "screen", "tmux", "rxvt", "linux", "vt100", "ansi", "putty", "cygwin")):
        return 16 if "256" not in term else 256
    return 16


def _refresh():
    global ENABLED, TRUE
    ENABLED = _depth > 0
    TRUE = _depth == 24
    _cache.clear()


def init(env=None, isatty=None):
    """Deteksi ulang kedalaman warna dari lingkungan."""
    global _depth
    _depth = detect_depth(env, isatty)
    _refresh()
    return _depth


def depth():
    return _depth


def set_depth(n):
    global _depth
    _depth = int(n)
    _refresh()


def set_enabled(v):
    """Kompatibilitas: True -> paksa warna (256 bila belum ada), False -> matikan."""
    global _depth
    _depth = (_depth or 256) if v else 0
    _refresh()


def depth_label():
    return {0: "tanpa warna", 16: "16 warna", 256: "256 warna", 24: "truecolor (24-bit)"}[_depth]


# ------------------------------------------------------------------ tema aktif
def names():
    return list(THEMES)


def current():
    return _cur


def info(name):
    return dict(META.get(name, {}), name=name)


def set_theme(name):
    global _cur
    name = DEPRECATED.get(name, name)
    if name in THEMES:
        _cur = name
        _cache.clear()
        return True
    return False


def role_hex(role, theme=None):
    v = THEMES[theme or _cur].get(role)
    return None if v is None or v.startswith("ansi:") else v


# ------------------------------------------------------------------ konversi warna -> escape
_ANSI16 = [(0, 0, 0), (205, 0, 0), (0, 205, 0), (205, 205, 0), (0, 0, 238), (205, 0, 205), (0, 205, 205), (229, 229, 229),
           (127, 127, 127), (255, 0, 0), (0, 255, 0), (255, 255, 0), (92, 92, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
_CUBE = (0, 95, 135, 175, 215, 255)


def _dist(a, b):
    rm = (a[0] + b[0]) / 2.0                          # "redmean": jarak warna yang lebih sesuai persepsi
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 + rm / 256) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256) * db * db


def to_256(rgb):
    best, bi = 1e18, 16
    for i in range(216):
        c = (_CUBE[i // 36], _CUBE[(i // 6) % 6], _CUBE[i % 6])
        d = _dist(rgb, c)
        if d < best:
            best, bi = d, 16 + i
    for g in range(24):
        v = 8 + g * 10
        d = _dist(rgb, (v, v, v))
        if d < best:
            best, bi = d, 232 + g
    return bi


def to_16(rgb):
    return min(range(16), key=lambda i: _dist(rgb, _ANSI16[i]))


def _esc(spec, is_bg=False):
    if spec.startswith("ansi:"):
        n = spec[5:]
        return "\033[%sm" % n if not is_bg else "\033[%sm" % (str(int(n) + 10) if n.isdigit() and int(n) < 100 else n)
    rgb = _rgb(spec)
    if _depth == 24:
        return "\033[%d;2;%d;%d;%dm" % (48 if is_bg else 38, *rgb)
    if _depth == 256:
        return "\033[%d;5;%dm" % (48 if is_bg else 38, to_256(rgb))
    i = to_16(rgb)
    base = (40 if is_bg else 30) if i < 8 else (100 if is_bg else 90)
    return "\033[%dm" % (base + (i % 8))


def hexfg(h):
    return _esc(h) if ENABLED else ""


def hexbg(h):
    return _esc(h, True) if ENABLED else ""


def fg(role):
    if not ENABLED:
        return ""
    key = (_cur, role, _depth, "fg")
    if key not in _cache:
        _cache[key] = _esc(THEMES[_cur][role])
    return _cache[key]


def bg(role):
    if not ENABLED:
        return ""
    key = (_cur, role, _depth, "bg")
    if key not in _cache:
        _cache[key] = _esc(THEMES[_cur][role], True)
    return _cache[key]


def c(role, text, bold=False, dim=False, italic=False, underline=False):
    if not ENABLED:
        return text
    pre = (BOLD if bold else "") + (DIM if dim else "") + (ITALIC if italic else "") + (UNDERLINE if underline else "")
    return f"{pre}{fg(role)}{text}{RESET}"


def paint(hexcolor, text, bold=False):
    return f"{BOLD if bold else ''}{hexfg(hexcolor)}{text}{RESET}" if ENABLED else text


def pill(role, text, bold=True):
    """Lencana berlatar warna (teks gelap/terang otomatis)."""
    if not ENABLED:
        return f"[{text}]"
    h = role_hex(role)
    on = "#000000" if h and luminance(h) > 0.35 else "#FFFFFF"
    if _depth == 16 or h is None:
        return f"\033[7m{fg(role)} {text} {RESET}"
    return f"{BOLD if bold else ''}{hexbg(h)}{hexfg(on)} {text} {RESET}"


def lerp_hex(a, b, t):
    return mix(a, b, t)


def gradient(text, t0=0.0, t1=1.0):
    """Warnai tiap karakter dari accent ke accent2 (16 warna / tema ansi: pakai accent saja)."""
    th = THEMES[_cur]
    if not ENABLED or _depth == 16 or th["accent"].startswith("ansi:"):
        return c("accent", text, bold=True)
    out, n = [], max(len(text) - 1, 1)
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
            continue
        out.append(_esc(mix(th["accent"], th["accent2"], t0 + (t1 - t0) * i / n)) + ch)
    return BOLD + "".join(out) + RESET


# ------------------------------------------------------------------ deteksi latar terang/gelap
def _parse_osc11(buf):
    m = re.search(rb"rgb:([0-9a-fA-F]+)/([0-9a-fA-F]+)/([0-9a-fA-F]+)", buf)
    if not m:
        return None
    vals = []
    for g in m.groups():
        vals.append(int(g, 16) / (16 ** len(g) - 1))
    return tuple(vals)


def _bg_from_colorfgbg(v):
    if not v:
        return None
    last = v.split(";")[-1]
    if not last.isdigit() or not 0 <= int(last) <= 15:
        return None
    n = int(last)
    return "dark" if n <= 6 or n == 8 else "light"      # konvensi rxvt


def detect_background(timeout=0.12, env=None):
    """-> 'dark' | 'light' | None.  CODINX_BACKGROUND > OSC 11 (bila TTY) > COLORFGBG."""
    e = os.environ if env is None else env
    forced = (e.get("CODINX_BACKGROUND") or "").strip().lower()
    if forced in ("dark", "light"):
        return forced
    if env is None and not e.get("CODINX_NO_BGQUERY") and sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import select
            import termios
            import time
            import tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                sys.stdout.write("\033]11;?\007")
                sys.stdout.flush()
                buf, end = b"", time.time() + timeout
                while time.time() < end:
                    r, _, _ = select.select([fd], [], [], max(0.0, end - time.time()))
                    if not r:
                        break
                    buf += os.read(fd, 256)
                    if b"\007" in buf or b"\033\\" in buf:
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            rgb = _parse_osc11(buf)
            if rgb:
                lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                return "light" if lum > 0.5 else "dark"
        except Exception:
            pass
    return _bg_from_colorfgbg(e.get("COLORFGBG"))


def resolve(name, detect=True):
    """Nama tema dari konfigurasi -> tema nyata. 'auto' mendeteksi latar; 'dark'/'light' memilih bawaan."""
    name = (name or "auto").strip().lower()
    name = DEPRECATED.get(name, name)
    if name in THEMES:
        return name
    if name == "light":
        return DEFAULT_LIGHT
    if name == "dark":
        return DEFAULT_DARK
    if name == "auto":
        bgm = detect_background() if detect and ENABLED else None
        return DEFAULT_LIGHT if bgm == "light" else DEFAULT_DARK
    return DEFAULT_DARK


init()
