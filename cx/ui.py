"""Terminal UI: banner, markdown renderer, spinner, permission prompt, tool cards."""
import difflib
import os
import re
import shutil
import sys
import textwrap
import threading
import time

from . import __version__, design, envinfo
from . import highlight
from . import themes as T
from .themes import c

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

def strip_ansi(s):
    return ANSI_RE.sub("", s)


def term_width():
    return shutil.get_terminal_size((80, 24)).columns


def banner_lines():
    return design.block_rows()


# ----------------------------------------------------------------- tabel (dipakai Markdown & penampil)
def table_lines(header, body):
    n = len(header)
    has_header = any(h.strip() for h in header)
    body = [(r + [""] * n)[:n] for r in body]
    widths = [max(len(strip_ansi(x)) for x in col) for col in zip(header, *body)]
    avail = term_width() - (3 * n + 2)
    while sum(widths) > avail and max(widths) > 8:
        widths[widths.index(max(widths))] -= 1

    def wrap(x, w):
        return textwrap.wrap(x, max(w, 1), break_long_words=True, replace_whitespace=False) or [""]

    bd = design.border()

    def line(l, m, r):
        return c("border", l + m.join(bd["h"] * (w + 2) for w in widths) + r)
    bar = c("border", bd["v"])

    def row_lines(r, role, bold=False):
        cells = [wrap(x, w) for x, w in zip(r, widths)]
        h = max(len(cc) for cc in cells)
        return [bar + bar.join(" " + c(role, (cc[i] if i < len(cc) else "").ljust(w), bold=bold) + " "
                               for cc, w in zip(cells, widths)) + bar for i in range(h)]
    out = [line(bd["tl"], bd["tj"], bd["tr"])]
    if has_header:
        out += row_lines(header, "heading", bold=True)
        out.append(line(bd["lj"], bd["x"], bd["rj"]))
    for r in body:
        out += row_lines(r, "text")
    out.append(line(bd["bl"], bd["bj"], bd["br"]))
    return out


# ----------------------------------------------------------------- markdown
class Markdown:
    """Line-buffered streaming markdown renderer (headings, lists, code, tables, inline)."""

    def __init__(self, write):
        self.write = write
        self.buf = ""
        self.in_code = False
        self.lang = ""
        self.code = []
        self.table = []

    def feed(self, text):
        self.buf += text
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            self._line(line)

    def flush(self):
        if self.buf:
            self._line(self.buf)
            self.buf = ""
        self._end_table()
        if self.in_code:
            self._emit_code()
            self.in_code = False

    def _emit_code(self):
        lines = highlight.render("\n".join(self.code), self.lang)
        bar = c("border", "  " + design.border()["v"] + " ")
        if lines is None:
            lines = [c("info", ln) for ln in self.code]
        self.write("".join(bar + ln + T.RESET + "\n" if T.ENABLED else bar + ln + "\n" for ln in lines))
        self.code = []

    # -- inline
    def inline(self, s):
        if not T.ENABLED:
            return s
        txt = T.fg("text")
        s = re.sub(r"`([^`]+)`", lambda m: T.fg("code") + m.group(1) + txt, s)
        s = re.sub(r"\*\*(.+?)\*\*", lambda m: T.BOLD + T.fg("heading") + m.group(1) + T.UNBOLD + txt, s)
        s = re.sub(r"(?<!\*)\*(?!\s)([^*]+?)\*(?!\*)", lambda m: T.ITALIC + m.group(1) + "\033[23m", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)",
                   lambda m: T.fg("link") + T.UNDERLINE + m.group(1) + "\033[24m" + T.fg("muted") + " (" + m.group(2) + ")" + txt, s)
        return txt + s + T.RESET

    # -- tables
    def _end_table(self):
        if not self.table:
            return
        rows = [[x.strip() for x in r.strip().strip("|").split("|")] for r in self.table]
        self.table = []
        header, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", x) for x in r)]
        self.write("\n".join(table_lines(header, body)) + "\n")

    def _line(self, ln):
        s = ln.rstrip("\r")
        if s.strip().startswith("```"):
            self._end_table()
            if not self.in_code:
                self.in_code = True
                self.lang = s.strip()[3:].strip()
                self.code = []
                bd = design.border()
                self.write(c("border", "  " + bd["tl"] + bd["h"] + " ") + c("accent2", self.lang or "code", italic=True) + "\n")
            else:
                self._emit_code()
                self.in_code = False
                bd = design.border()
                self.write(c("border", "  " + bd["bl"] + bd["h"]) + "\n")
            return
        if self.in_code:
            self.code.append(s)          # ditampung sampai blok tertutup, lalu di-highlight sekaligus
            return
        if s.lstrip().startswith("|") and s.count("|") >= 2:
            self.table.append(s)
            return
        self._end_table()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            lvl, t = len(m.group(1)), re.sub(r"[*`]", "", m.group(2))
            if lvl == 1:
                self.write("\n" + c("heading", t.upper(), bold=True) + "\n" + c("border", "━" * min(len(t), 60)) + "\n")
            elif lvl == 2:
                self.write("\n" + c("heading", "▌ " + t, bold=True) + "\n")
            else:
                self.write(c("accent2", design.icon("skill") + " " + t, bold=True) + "\n")
            return
        if re.match(r"^\s*([-*_])\1{2,}\s*$", s):
            self.write(c("border", design.border()["h"] * min(term_width() - 2, 60)) + "\n")
            return
        m = re.match(r"^(\s*)[-*+]\s+(.*)$", s)
        if m:
            self.write(m.group(1) + c("accent", design.icon("bullet") + " ") + self.inline(m.group(2)) + "\n")
            return
        m = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", s)
        if m:
            self.write(m.group(1) + c("accent", m.group(2) + ". ") + self.inline(m.group(3)) + "\n")
            return
        if s.startswith(">"):
            self.write(c("border", "┃ " if envinfo.utf8_ok() else "| ") + c("muted", s.lstrip("> "), italic=True) + "\n")
            return
        self.write(self.inline(s) + "\n")


# ------------------------------------------------------------------- the UI
class UI:
    def __init__(self):
        self.quiet = False
        self.show_thinking = False
        self.show_details = True
        self._stop = None
        self._t = None
        self._md = None
        self._mode = None

    # basic output
    def w(self, s=""):
        if not self.quiet:
            sys.stdout.write(s)
            sys.stdout.flush()

    def p(self, s=""):
        self.w(s + "\n")

    def info(self, s):
        self.p(c("info", design.icon("info") + " ") + c("text", s))

    def ok(self, s):
        self.p(c("ok", design.icon("ok") + " ") + c("text", s))

    def warn(self, s):
        self.p(c("warn", design.icon("warn") + " ") + c("text", s))

    def err(self, s):
        self.p(c("err", design.icon("err") + " ") + c("text", s))

    # banner / home
    def banner(self, model, agent, tier, cwd, extra=""):
        style = design.get("banner")
        w = term_width()
        rows = design.banner_rows(style)
        compact = design.get("density") == "compact"
        if not compact:
            self.p()
        tag = f"v{__version__} · terminal coding agent"
        if style == "none":
            pass
        elif rows and w >= max(len(r) for r in rows) + 4:
            n = len(rows)
            for i, r in enumerate(rows):
                self.p("  " + T.gradient(r, i / (n * 2), 0.5 + i / (n * 2)))
            self.p("  " + c("muted", tag))
        elif style == "mini":
            self.p("  " + c("accent", "▌", bold=True) + c("heading", "CodinX", bold=True) + c("accent2", "▐ ") + c("muted", tag))
        elif style == "boxed":
            bd = design.border()
            inner = f" CodinX  {tag} "
            inner = inner if len(inner) < w - 6 else " CodinX "
            self.p("  " + c("border", bd["tl"] + bd["h"] * len(inner) + bd["tr"]))
            self.p("  " + c("border", bd["v"]) + c("heading", " CodinX ", bold=True) + c("muted", inner[8:]) + c("border", bd["v"]))
            self.p("  " + c("border", bd["bl"] + bd["h"] * len(inner) + bd["br"]))
        else:
            self.p("  " + T.gradient("CodinX", 0.0, 1.0) + c("muted", f"  {tag}"))
        if not compact:
            self.p()
        bd = design.border()
        box = [("model", model or "(belum dipilih)"), ("agent", agent), ("paket", tier), ("folder", cwd)]
        if extra:
            box.append(("info", extra))
        wd = max(20, min(w - 6, 64))
        self.p("  " + c("border", bd["tl"] + bd["h"] * wd + bd["tr"]))
        for k, v in box:
            body = f" {k:<7}{v}"
            body = body if len(body) <= wd else body[: wd - 1] + "…"
            self.p("  " + c("border", bd["v"]) + c("accent2", body[:8], bold=True) + c("text", body[8:]) + " " * (wd - len(body)) + c("border", bd["v"]))
        self.p("  " + c("border", bd["bl"] + bd["h"] * wd + bd["br"]))
        if not compact:
            self.p()
        hint = [("/", "perintah"), ("@file", "lampir"), ("!cmd", "shell"), ("/skills", ""), ("/theme", ""), ("/design", ""), ("/doctor", "")]
        self.p("  " + c("muted", "ketik ") + c("accent", "/", bold=True) + c("muted", " untuk saran · ") +
               " ".join(c("accent2", k) for k, _ in hint[1:]))
        if not compact:
            self.p()

    # spinner
    def spin_start(self, label="berpikir"):
        if self.quiet or not sys.stdout.isatty() or self._t:
            return
        self._stop = threading.Event()

        frames, interval = design.spinner()

        def run():
            i, t0 = 0, time.time()
            while not self._stop.is_set():
                sys.stdout.write("\r" + c("accent", frames[i % len(frames)]) + " " + c("muted", f"{label} {int(time.time() - t0)}s") + "\033[K")
                sys.stdout.flush()
                i += 1
                time.sleep(interval)
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
        self._t = threading.Thread(target=run, daemon=True)
        self._t.start()

    def spin_stop(self):
        if self._t:
            self._stop.set()
            self._t.join()
            self._t = None

    # streaming model output
    def _gutter_write(self, s):
        g = design.gutter_glyph()
        if not g:
            return self.w(s)
        pre = c("accent", g)
        parts = s.split("\n")
        self.w("\n".join((pre + x if x.strip() or i < len(parts) - 1 else x) for i, x in enumerate(parts)))

    def stream_begin(self):
        self._md = Markdown(self._gutter_write)
        self._mode = None
        self.spin_start()

    def stream_text(self, s):
        if self.quiet:
            return
        if self._mode != "text":
            self.spin_stop()
            if self._mode == "reason":
                self.w("\n")
            self._mode = "text"
        self._md.feed(s)

    def stream_reasoning(self, s):
        if self.quiet or not self.show_thinking:
            return
        if self._mode != "reason":
            self.spin_stop()
            self._mode = "reason"
            self.w(c("muted", "  ▍ berpikir: ", italic=True))
        self.w(c("muted", s.replace("\n", "\n  ▍ "), italic=True))

    def stream_end(self):
        self.spin_stop()
        if self._md:
            self._md.flush()
        self._md = None

    def markdown(self, text):
        md = Markdown(self.w)
        md.feed(text + "\n")
        md.flush()

    # tools
    def tool_start(self, name, summary):
        self.spin_stop()
        self.p(c("accent2", "  " + design.icon("tool") + " ") + c("text", name, bold=True) + " " + c("muted", summary))

    def tool_result(self, text, ok=True):
        if not self.show_details:
            return
        lines = (text or "").splitlines() or [""]
        shown = lines[:6]
        for ln in shown:
            self.p(c("border", "    " + design.border()["v"] + " ") + c("muted" if ok else "err", ln[: term_width() - 8]))
        if len(lines) > 6:
            self.p(c("border", "    " + design.border()["v"] + " ") + c("muted", f"… {len(lines) - 6} baris lagi"))

    def diff(self, text, limit=60, force=False):
        if (not self.show_details and not force) or not text:
            return
        for ln in text.splitlines()[:limit]:
            col = "ok" if ln.startswith("+") and not ln.startswith("+++") else "err" if ln.startswith("-") and not ln.startswith("---") else "muted"
            self.p("    " + c(col, ln[: term_width() - 6]))

    def todos(self, todos):
        self.p(c("accent", "  " + design.icon("todo") + " rencana"))
        for t in todos:
            st = t.get("status", "pending")
            mark = {"completed": c("ok", design.icon("done")), "in_progress": c("warn", design.icon("prog")),
                    "pending": c("muted", design.icon("pend"))}.get(st, design.icon("pend"))
            self.p(f"    {mark} " + c("muted" if st == "completed" else "text", str(t.get("content", ""))))

    def table(self, columns, rows, title=None):
        if title:
            self.p(c("heading", "▌ " + title, bold=True))
        md = Markdown(self.w)
        md.table = ["| " + " | ".join(map(str, columns)) + " |", "|" + "---|" * len(columns)] + \
                   ["| " + " | ".join(str(x) for x in r) + " |" for r in rows]
        md._end_table()

    # permission prompt (yellow, Indonesian): Iya / Tidak / Selalu izinkan
    @staticmethod
    def _keys(data):
        i = 0
        while i < len(data):
            if data[i] == 0x1b and i + 2 < len(data) and data[i + 1:i + 2] == b"[":
                yield data[i:i + 3]
                i += 3
            else:
                yield data[i:i + 1]
                i += 1

    def choose(self, options):
        """Arrow/Tab/number/letter selection. Returns index, or None if not interactive."""
        if self.quiet or not (sys.stdin.isatty() and sys.stdout.isatty()):
            return None
        try:
            import termios
            import tty
        except ImportError:
            return None
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        idx, n = 0, len(options)
        initials = [o[0].lower() for o in options]

        def render():
            parts = []
            for i, o in enumerate(options):
                parts.append(c("accent", f"❯ {o}", bold=True) if i == idx else c("muted", f"  {o}"))
            sys.stdout.write("\r\033[K   " + "      ".join(parts))
            sys.stdout.flush()
        try:
            tty.setcbreak(fd)
            render()
            done = False
            while not done:
                data = os.read(fd, 64)
                if not data:                      # EOF -> tolak
                    idx = 1
                    break
                for k in self._keys(data):
                    if k in (b"\r", b"\n"):
                        done = True
                        break
                    if k in (b"\x1b[C", b"\x1b[B", b"\t", b"l", b"j"):
                        idx = (idx + 1) % n
                    elif k in (b"\x1b[D", b"\x1b[A", b"h", b"k", b"\x1b[Z"):
                        idx = (idx - 1) % n
                    elif k.isdigit() and 1 <= int(k) <= n:
                        idx, done = int(k) - 1, True
                        break
                    elif len(k) == 1 and k.decode("latin1").lower() in initials:
                        idx, done = initials.index(k.decode("latin1").lower()), True
                        break
                render()
        except KeyboardInterrupt:
            idx = 1
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            sys.stdout.write("\n")
        return idx

    def confirm(self, tool, subject, preview=None):
        """Returns 'once' | 'always' | 'no'."""
        self.spin_stop()
        w = term_width() - 6
        self.p()
        self.p(c("warn", "  ┃ ") + c("text", "⚙ " + tool, bold=True))
        for ln in str(subject).splitlines()[:8] or [""]:
            self.p(c("warn", "  ┃ ") + c("info", ln[:w]))
        if preview:
            for ln in preview.splitlines()[:14]:
                col = "ok" if ln.startswith("+") and not ln.startswith("+++") else "err" if ln.startswith("-") and not ln.startswith("---") else "muted"
                self.p(c("warn", "  ┃ ") + c(col, ln[:w]))
        yellow = T.YELLOW_BRIGHT if T.ENABLED else ""
        self.p(f"{yellow}  Apakah anda ingin izinkan ini?{T.RESET if T.ENABLED else ''}")
        idx = self.choose(["Iya", "Tidak", "Selalu izinkan"])
        if idx is None:
            if self.quiet or not sys.stdin.isatty():
                return "no"
            try:
                a = input("   [i]ya / [t]idak / [s]elalu izinkan › ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return "no"
            idx = 0 if a.startswith("i") else 2 if a.startswith("s") else 1
        return ("once", "no", "always")[idx]
