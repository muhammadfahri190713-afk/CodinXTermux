"""Sistem desain terminal: banner, border, spinner, ikon, prompt, gutter, gaya status, kerapatan + preset.

Semua pilihan disimpan di config["design"] dan bisa diubah lewat /design, /banner, /border, /spinner, /icons, /prompt, ...
Bila terminal tidak mendukung UTF-8, semuanya otomatis jatuh ke ASCII.
"""
from . import envinfo

DEFAULT = {"banner": "pro", "border": "rounded", "spinner": "dots", "icons": "auto", "prompt": "bar",
           "status": "dots", "gutter": "none", "density": "comfortable"}

BORDERS = {
    "rounded": dict(tl="╭", tr="╮", bl="╰", br="╯", h="─", v="│", tj="┬", bj="┴", lj="├", rj="┤", x="┼"),
    "square": dict(tl="┌", tr="┐", bl="└", br="┘", h="─", v="│", tj="┬", bj="┴", lj="├", rj="┤", x="┼"),
    "heavy": dict(tl="┏", tr="┓", bl="┗", br="┛", h="━", v="┃", tj="┳", bj="┻", lj="┣", rj="┫", x="╋"),
    "double": dict(tl="╔", tr="╗", bl="╚", br="╝", h="═", v="║", tj="╦", bj="╩", lj="╠", rj="╣", x="╬"),
    "ascii": dict(tl="+", tr="+", bl="+", br="+", h="-", v="|", tj="+", bj="+", lj="+", rj="+", x="+"),
    "minimal": dict(tl="─", tr="─", bl="─", br="─", h="─", v=" ", tj="─", bj="─", lj="─", rj="─", x="─"),
}

ICONS = {
    "unicode": dict(ok="✓", err="✗", warn="⚠", info="ℹ", tool="⚙", mem="◆", skill="▸", think="▍", bullet="•", sub="↳", todo="☰",
                    done="✓", prog="◐", pend="○", arrow="›", file="▪"),
    "ascii": dict(ok="+", err="x", warn="!", info="i", tool="*", mem="#", skill=">", think="|", bullet="-", sub="->", todo="=",
                  done="x", prog="~", pend="o", arrow=">", file="-"),
    "nerd": dict(ok=chr(0xF00C), err=chr(0xF00D), warn=chr(0xF071), info=chr(0xF05A), tool=chr(0xF013), mem=chr(0xF02E),
                 skill=chr(0xF0EB), think=chr(0xF0E5), bullet="•", sub="↳", todo=chr(0xF0CA), done=chr(0xF00C), prog=chr(0xF110),
                 pend=chr(0xF10C), arrow=chr(0xF054), file=chr(0xF15B)),
    "emoji": dict(ok="✅", err="❌", warn="⚠️", info="ℹ️", tool="🔧", mem="💾", skill="🧩", think="💭", bullet="•", sub="↳", todo="📋",
                  done="✅", prog="⏳", pend="⬜", arrow="›", file="📄"),
}

# subset cli-spinners (nama & bingkai mengikuti koleksi populer); True = aman ASCII
SPINNERS = {
    "dots": ("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 0.08, False), "dots2": ("⣾⣽⣻⢿⡿⣟⣯⣷", 0.08, False), "dots3": ("⠋⠙⠚⠞⠖⠦⠴⠲⠳⠓", 0.08, False),
    "dots4": ("⠄⠆⠇⠋⠙⠸⠰⠠⠰⠸⠙⠋⠇⠆", 0.08, False), "dots5": ("⠁⠉⠙⠚⠒⠂⠂⠒⠲⠴⠤⠄⠄⠤⠴⠲⠒⠂⠂⠒⠚⠙⠉⠁", 0.08, False),
    "bounce": ("⠁⠂⠄⡀⢀⠠⠐⠈", 0.1, False), "line": ("-\\|/", 0.12, True), "pipe": ("┤┘┴└├┌┬┐", 0.1, False),
    "star": ("✶✸✹✺✹✷", 0.12, False), "star2": ("+x*", 0.08, True), "flip": ("_-`'´-_", 0.07, True), "hamburger": ("☱☲☴", 0.1, False),
    "growV": ("▁▃▄▅▆▇▆▅▄▃", 0.12, False), "growH": ("▏▎▍▌▋▊▉▊▋▌▍▎", 0.12, False), "noise": ("▓▒░", 0.1, False),
    "triangle": ("◢◣◤◥", 0.05, False), "arc": ("◜◠◝◞◡◟", 0.1, False), "circle": ("◡⊙◠", 0.12, False),
    "squareCorners": ("◰◳◲◱", 0.18, False), "circleQuarters": ("◴◷◶◵", 0.12, False), "circleHalves": ("◐◓◑◒", 0.05, False),
    "toggle": ("⊶⊷", 0.25, False), "arrow": ("←↖↑↗→↘↓↙", 0.1, False), "simpleDots": (".  ,.. ,...,   ".split(","), 0.4, True),
    "pulse": ("∙∙∙,●∙∙,∙●∙,∙∙●,∙∙∙".split(","), 0.12, False), "bar": ("[=   ],[==  ],[=== ],[ ===],[  ==],[   =],[  ==],[ ===],[=== ],[==  ]".split(","), 0.1, True),
    "dqpb": ("dqpb", 0.1, True), "moon": ("🌑🌒🌓🌔🌕🌖🌗🌘", 0.08, False), "earth": ("🌍🌎🌏", 0.18, False),
    "layer": ("-=≡", 0.15, False), "balloon": (" .oO@* ", 0.14, True), "sand": ("⠁⠂⠄⡀⡈⡐⡠⣀⣁⣂⣄⣌⣔⣤⣥⣦⣮⣶⣷⣿⡿⠿⢟⠟⡛⠛⠫⢋⠋⠍⡉⠉⠑⠡⢁", 0.08, False),
}

PROMPTS = {"bar": "┃ ", "arrow": "❯ ", "chevron": "› ", "dollar": "$ ", "triangle": "▶ ", "lambda": "λ ", "plain": "> "}
GUTTERS = {"none": "", "bar": "▎ ", "dot": "● ", "line": "│ "}
STATUS = ("dots", "pills", "bar", "minimal")
DENSITY = ("comfortable", "compact")
CHOICES = {"banner": ("pro", "block", "slant", "small", "wide", "boxed", "mini", "none"), "border": tuple(BORDERS),
           "spinner": tuple(SPINNERS), "icons": ("auto",) + tuple(ICONS), "prompt": tuple(PROMPTS), "status": STATUS,
           "gutter": tuple(GUTTERS), "density": DENSITY}

PRESETS = {
    "codinx":   dict(theme="auto", banner="pro", border="rounded", spinner="dots", prompt="bar", status="dots", gutter="none", density="comfortable"),
    "opencode": dict(theme="opencode", banner="mini", border="square", spinner="dots", prompt="bar", status="bar", gutter="bar", density="comfortable"),
    "claude":   dict(theme="terracotta", banner="pro", border="rounded", spinner="star", prompt="arrow", status="minimal", gutter="dot", density="comfortable"),
    "codex":    dict(theme="oxocarbon", banner="small", border="square", spinner="dots2", prompt="chevron", status="dots", gutter="none", density="comfortable"),
    "minimal":  dict(theme="auto", banner="none", border="minimal", spinner="line", prompt="dollar", status="minimal", gutter="none", density="compact"),
    "retro":    dict(theme="amber", banner="block", border="double", spinner="bounce", prompt="dollar", status="bar", gutter="line", density="comfortable"),
    "neon":     dict(theme="neon", banner="slant", border="heavy", spinner="star", prompt="triangle", status="pills", gutter="bar", density="comfortable"),
    "paper":    dict(theme="paper", banner="small", border="rounded", spinner="arc", prompt="arrow", status="dots", gutter="none", density="comfortable"),
    "contrast": dict(theme="contrast", banner="pro", border="heavy", spinner="line", prompt="arrow", status="bar", gutter="bar", density="comfortable"),
    "termux":   dict(theme="auto", banner="pro", border="rounded", spinner="dots", prompt="chevron", status="minimal", gutter="none", density="compact"),
}
PRESET_NOTE = {"codinx": "bawaan, seimbang", "opencode": "mirip TUI opencode (jingga/biru, gutter)", "claude": "terakota + titik ala Claude Code",
               "codex": "netral, prompt ›", "minimal": "tanpa banner, ringkas", "retro": "terminal CRT amber, border ganda",
               "neon": "synthwave, lencana status", "paper": "tema terang kertas", "contrast": "kontras tinggi (aksesibilitas)",
               "termux": "ringkas untuk layar ponsel"}

STATE = dict(DEFAULT)

GLYPHS = {
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "D": ["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "X": ["██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝"],
}
SMALL = {"C": ("█▀▀", "█▄▄"), "O": ("█▀█", "█▄█"), "D": ("█▀▄", "█▄▀"), "I": ("█", "█"), "N": ("█▄ █", "█ ▀█"), "X": ("▀▄▀", "█ █")}


def block_rows():
    return ["".join(GLYPHS[ch][r] for ch in "CODINX") for r in range(6)]


def banner_rows(style):
    """Baris mentah banner; None = pakai gaya teks (pro/mini/boxed/none)."""
    if style == "block":
        return block_rows()
    if style == "slant":
        return [" " * ((5 - i) // 2) + row for i, row in enumerate(block_rows())]
    if style == "small":
        return [" ".join(SMALL[ch][r] for ch in "CODINX") for r in range(2)]
    if style == "wide":
        return ["  ".join("CODINX"), "━" * 16]
    return None


def load(cfg):
    STATE.clear()
    STATE.update(DEFAULT)
    for k, v in (cfg.get("design") or {}).items():
        if k in DEFAULT and (k not in CHOICES or v in CHOICES[k]):
            STATE[k] = v


def dump():
    return dict(STATE)


def get(key):
    return STATE.get(key, DEFAULT.get(key))


def set(key, value):
    if key not in CHOICES or value not in CHOICES[key]:
        return False
    STATE[key] = value
    return True


def icon_set():
    n = STATE["icons"]
    if n == "auto":
        return "unicode" if envinfo.utf8_ok() else "ascii"
    return n if envinfo.utf8_ok() or n == "ascii" else "ascii"


def icon(name):
    return ICONS[icon_set()].get(name, "?")


def border(kind=None):
    k = kind or STATE["border"]
    return BORDERS[k] if envinfo.utf8_ok() or k == "ascii" else BORDERS["ascii"]


def spinner():
    frames, interval, ascii_ok = SPINNERS.get(STATE["spinner"], SPINNERS["dots"])
    if not envinfo.utf8_ok() and not ascii_ok:
        frames, interval, _ = SPINNERS["line"]
    return list(frames), interval


def prompt_glyph():
    return PROMPTS.get(STATE["prompt"], PROMPTS["bar"]) if envinfo.utf8_ok() else PROMPTS["plain"]


def gutter_glyph():
    g = GUTTERS.get(STATE["gutter"], "")
    return g if envinfo.utf8_ok() or not g else "| "


def apply_preset(name):
    """-> nama tema preset (atau None bila preset tidak ada). Mengisi STATE."""
    p = PRESETS.get(name)
    if not p:
        return None
    for k in DEFAULT:
        if k in p:
            STATE[k] = p[k]
    return p["theme"]
