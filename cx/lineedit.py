"""Editor baris mode-raw dengan saran LIVE (popup) ala opencode — Linux & Termux, tanpa dependensi.

Mengetik "/" menampilkan daftar perintah; tiap huruf mempersempit daftar ("/h" -> "/help" teratas).
  ↑/↓ (atau Ctrl-P/N) pilih · Tab lengkapi (awalan terpanjang / penuh) · Enter terima & jalankan · Esc tutup popup
  Shift-Tab pilih sebelumnya · PgUp/PgDn lompat · juga bekerja untuk argumen (/theme tok), @file, dan $skill.
Penyuntingan: ←/→ Home/End, Ctrl-A/E/B/F, Alt-B/F & Ctrl-←/→ (kata), Ctrl-W/U/K, Delete, Ctrl-D (EOF bila kosong),
Ctrl-L (bersihkan layar), Alt-Enter (baris baru), tempel (bracketed paste), riwayat ↑/↓ (disimpan ke file).
Baris diedit dalam jendela horizontal satu baris sehingga tidak pernah merusak tata letak di layar sempit.
Bukan TTY / tanpa termios / CODINX_SIMPLE_INPUT=1  ->  jatuh ke input() biasa.
"""
import codecs
import os
import re
import select
import shutil
import sys
import unicodedata

from . import envinfo
from . import themes as T
from .themes import c

try:
    import termios
    import tty
except ImportError:                                     # pragma: no cover (Windows)
    termios = tty = None

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def strip_ansi(s):
    return _ANSI.sub("", s)


def cw(ch):
    """Lebar kolom satu karakter (0 untuk kontrol/penggabung, 2 untuk CJK/emoji lebar)."""
    o = ord(ch)
    if o < 32 or o == 127:
        return 0
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def swidth(s):
    return sum(cw(ch) for ch in s)


def truncate(s, width):
    """Potong ke `width` kolom (tambah … bila terpotong)."""
    if width <= 0:
        return ""
    if swidth(s) <= width:
        return s
    ell = "…" if envinfo.utf8_ok() else "~"
    out, used = "", 0
    for ch in s:
        if used + cw(ch) > width - 1:
            break
        out += ch
        used += cw(ch)
    return out + ell


# ------------------------------------------------------------------ pembaca tombol
class KeyReader:
    """Mengubah byte terminal menjadi token tombol: 'a', 'UP', 'C-a', 'M-b', 'ENTER', 'TAB', 'ESC', 'PASTE:teks', ..."""

    def __init__(self, fd):
        self.fd = fd
        self.dec = codecs.getincrementaldecoder("utf-8")("ignore")
        self.pending = ""
        self.paste = None

    def _more(self, timeout):
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return False
        data = os.read(self.fd, 4096)
        if not data:
            raise EOFError("stdin ditutup")
        self.pending += self.dec.decode(data)
        return True

    def read(self):
        tokens = []
        if not self.pending and not self._more(None):
            return tokens
        while True:
            while self.pending:
                t = self.parse_one()
                if t is None:
                    break
                if t != "":
                    tokens.append(t)
            if self.paste is not None:
                if not self._more(1.0):                  # tempel terputus: pakai apa yang sudah ada
                    tokens.append("PASTE:" + self.paste)
                    self.paste = None
                    break
                continue
            break
        return tokens

    def feed(self, text):
        """Untuk pengujian: umpankan teks, kembalikan token."""
        self.pending += text
        out = []
        while self.pending:
            t = self.parse_one(nowait=True)
            if t is None:
                break
            if t != "":
                out.append(t)
        return out

    def parse_one(self, nowait=False):
        s = self.pending
        if self.paste is not None:
            i = s.find("\x1b[201~")
            if i < 0:
                self.paste += s
                self.pending = ""
                return None
            tok = "PASTE:" + self.paste + s[:i]
            self.pending = s[i + 6:]
            self.paste = None
            return tok
        ch = s[0]
        if ch == "\x1b":
            if len(s) == 1:
                if not nowait and self._more(0.03):
                    return self.parse_one()
                self.pending = ""
                return "ESC"
            n = s[1]
            if n == "[":
                m = re.match(r"\x1b\[([0-9;?]*)([ -/]*[@-~])", s)
                if not m:
                    if not nowait and self._more(0.05):
                        return self.parse_one()
                    self.pending = s[2:]
                    return "ESC"
                self.pending = s[m.end():]
                return self._csi(m.group(1), m.group(2))
            if n == "O":
                if len(s) < 3:
                    if not nowait and self._more(0.05):
                        return self.parse_one()
                    self.pending = ""
                    return "ESC"
                self.pending = s[3:]
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT", "H": "HOME", "F": "END"}.get(s[2], "")
            self.pending = s[2:]
            if n in "\r\n":
                return "M-ENTER"
            if n == "\x7f":
                return "M-BACKSPACE"
            return "M-" + n
        self.pending = s[1:]
        if ch in "\r\n":
            return "ENTER"
        if ch == "\t":
            return "TAB"
        if ch in "\x7f\x08":
            return "BACKSPACE"
        o = ord(ch)
        if o < 32:
            return "C-" + chr(o + 96)
        return ch

    def _csi(self, params, final):
        if final == "~":
            if params == "200":
                self.paste = ""
                return ""
            p = params.split(";")[0]
            return {"1": "HOME", "7": "HOME", "4": "END", "8": "END", "3": "DEL", "5": "PGUP", "6": "PGDN"}.get(p, "")
        base = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT", "H": "HOME", "F": "END", "Z": "BTAB"}.get(final)
        if base is None:
            return ""
        mod = params.split(";")[1] if ";" in params else ""
        if mod in ("3", "4"):
            return "M-" + base
        if mod in ("5", "6"):
            return "C-" + base
        return base


# ------------------------------------------------------------------ editor
class Editor:
    def __init__(self, completer=None, history_file=None, max_popup=7):
        self.completer = completer
        self.max_popup = max_popup
        self.hist_file = history_file
        self.history = []
        self.used = False
        self._load_history()
        self.reset("")

    # ---- riwayat
    def _load_history(self):
        if not self.hist_file:
            return
        try:
            with open(self.hist_file, encoding="utf-8", errors="replace") as f:
                self.history = [ln.rstrip("\n").replace("\\n", "\n") for ln in f if ln.strip()][-1000:]
        except OSError:
            pass

    def _remember(self, line):
        line = line.strip()
        if not line or (self.history and self.history[-1] == line):
            return
        self.history.append(line)
        if self.hist_file:
            try:
                os.makedirs(os.path.dirname(self.hist_file), exist_ok=True)
                with open(self.hist_file, "a", encoding="utf-8") as f:
                    f.write(line.replace("\n", "\\n") + "\n")
                os.chmod(self.hist_file, 0o600)
                if len(self.history) > 1500:
                    self.history = self.history[-1000:]
                    with open(self.hist_file, "w", encoding="utf-8") as f:
                        f.write("".join(h.replace("\n", "\\n") + "\n" for h in self.history))
            except OSError:
                pass

    # ---- state
    def reset(self, initial=""):
        self.buf, self.cur = initial, len(initial)
        self.sugg, self.sel, self.top, self.span = [], 0, 0, (0, 0)
        self._hidden, self._key = None, None
        self.hist_i, self.hist_stash = None, ""
        self.done, self.result = False, ""
        self._drawn, self._view = 0, 0

    def refresh(self):
        self.sugg = []
        if not self.completer or self._hidden == self.buf:
            return
        start, end, sugg = self.completer.suggest(self.buf, self.cur)
        if len(sugg) == 1 and sugg[0].kind in ("cmd", "custom", "alias") and sugg[0].value == self.buf[start:end]:
            sugg = []                                   # sudah lengkap, tak perlu popup
        key = tuple(s.value for s in sugg)
        if key != self._key:
            self.sel, self.top, self._key = 0, 0, key
        self.span, self.sugg = (start, end), sugg

    def visible(self):
        return bool(self.sugg)

    # ---- aksi
    def insert(self, text):
        self.buf = self.buf[:self.cur] + text + self.buf[self.cur:]
        self.cur += len(text)
        self._hidden = None

    def _delete(self, a, b):
        self.buf = self.buf[:a] + self.buf[b:]
        self.cur = a
        self._hidden = None

    def _word_left(self, i):
        while i > 0 and self.buf[i - 1].isspace():
            i -= 1
        while i > 0 and not self.buf[i - 1].isspace():
            i -= 1
        return i

    def _word_right(self, i):
        n = len(self.buf)
        while i < n and self.buf[i].isspace():
            i += 1
        while i < n and not self.buf[i].isspace():
            i += 1
        return i

    def accept(self, s):
        start, end = self.span
        new = self.buf[:start] + s.value
        tail = self.buf[end:]
        want_space = s.kind in ("cmd", "custom", "skill", "alias", "arg") or (s.kind == "file" and not s.value.endswith("/"))
        if want_space:
            if tail.startswith(" "):
                self.buf, self.cur = new + tail, len(new) + 1
            else:
                self.buf, self.cur = new + " " + tail, len(new) + 1
        else:
            self.buf, self.cur = new + tail, len(new)
        self._hidden = None

    def _tab(self):
        if not self.sugg:
            return
        start, end = self.span
        token = self.buf[start:end]
        values = [s.value for s in self.sugg]
        if len(values) > 1:
            lcp = suggest_common(values)
            if len(lcp) > len(token) and lcp.lower().startswith(token.lower()):
                self.buf = self.buf[:start] + lcp + self.buf[end:]
                self.cur = start + len(lcp)
                return
        self.accept(self.sugg[self.sel])

    def _enter(self):
        if self.sugg:
            s = self.sugg[self.sel]
            token = self.buf[self.span[0]:self.span[1]]
            if token != s.value:
                self.accept(s)
                self.refresh()
                if s.kind == "file" or s.needs_arg or s.value.startswith("$"):
                    return                              # lanjut mengetik (perlu argumen / path)
        self.result, self.done = self.buf, True

    def _hist(self, d):
        if not self.history:
            return
        if self.hist_i is None:
            if d > 0:
                return
            self.hist_stash, self.hist_i = self.buf, len(self.history)
        self.hist_i = max(0, min(len(self.history), self.hist_i + d))
        if self.hist_i == len(self.history):
            self.buf, self.hist_i = self.hist_stash, None
        else:
            self.buf = self.history[self.hist_i]
        self.cur = len(self.buf)
        self._hidden = self.buf                          # hasil recall tidak memunculkan popup

    def move_sel(self, d):
        if self.sugg:
            self.sel = (self.sel + d) % len(self.sugg)

    def handle(self, k):
        """Proses satu token tombol. Mengembalikan 'clear' bila layar perlu dibersihkan (Ctrl-L)."""
        if k.startswith("PASTE:"):
            self.insert(k[6:].replace("\r\n", "\n").replace("\r", "\n").replace("\x1b", ""))
        elif len(k) == 1 and (ord(k) >= 32 and ord(k) != 127):
            self.insert(k)
        elif k == "BACKSPACE":
            if self.cur > 0:
                self._delete(self.cur - 1, self.cur)
        elif k == "DEL":
            if self.cur < len(self.buf):
                self._delete(self.cur, self.cur + 1)
        elif k == "C-d":
            if not self.buf:
                raise EOFError("Ctrl-D")
            if self.cur < len(self.buf):
                self._delete(self.cur, self.cur + 1)
        elif k in ("LEFT", "C-b"):
            self.cur = max(0, self.cur - 1)
        elif k in ("RIGHT", "C-f"):
            self.cur = min(len(self.buf), self.cur + 1)
        elif k in ("HOME", "C-a"):
            self.cur = 0
        elif k in ("END", "C-e"):
            self.cur = len(self.buf)
        elif k in ("M-b", "C-LEFT", "M-LEFT"):
            self.cur = self._word_left(self.cur)
        elif k in ("M-f", "C-RIGHT", "M-RIGHT"):
            self.cur = self._word_right(self.cur)
        elif k in ("C-w", "M-BACKSPACE"):
            self._delete(self._word_left(self.cur), self.cur)
        elif k == "C-u":
            self._delete(0, self.cur)
        elif k == "C-k":
            self._delete(self.cur, len(self.buf))
        elif k in ("UP", "C-p"):
            self.move_sel(-1) if self.sugg else self._hist(-1)
        elif k in ("DOWN", "C-n"):
            self.move_sel(1) if self.sugg else self._hist(1)
        elif k == "BTAB":
            self.move_sel(-1)
        elif k == "PGUP":
            self.move_sel(-self.max_popup) if self.sugg else None
        elif k == "PGDN":
            self.move_sel(self.max_popup) if self.sugg else None
        elif k == "TAB":
            self._tab()
        elif k == "ESC":
            if self.sugg:
                self._hidden = self.buf
        elif k == "ENTER":
            self._enter()
        elif k == "M-ENTER":
            self.insert("\n")
        elif k == "C-l":
            return "clear"
        if not self.done:
            self.refresh()
        return None

    # ---- tampilan
    def _popup_lines(self, cols, rows):
        if not self.sugg:
            return []
        n = len(self.sugg)
        maxr = max(2, min(self.max_popup, rows - 4))
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + maxr:
            self.top = self.sel - maxr + 1
        shown = self.sugg[self.top:self.top + maxr]
        lw = min(max(swidth(s.label) for s in self.sugg), 24, max(8, cols // 2 - 4))
        mark = "❯" if envinfo.utf8_ok() else ">"
        tags = {"custom": "custom", "skill": "skill", "alias": "alias", "file": ""}
        lines = []
        for i, s in enumerate(shown):
            selected = (self.top + i) == self.sel
            label = truncate(s.label, lw)
            pad = " " * (lw - swidth(label))
            tag = tags.get(s.kind, "")
            room = cols - 5 - lw - (len(tag) + 2 if tag else 0)
            desc = truncate(s.desc, max(0, room))
            visible_w = 2 + lw + 2 + swidth(desc) + (len(tag) + 2 if tag else 0)
            tail = " " * max(0, cols - 1 - visible_w - 1)
            if not T.ENABLED:
                lines.append(("> " if selected else "  ") + label + pad + "  " + desc + ((" " + tag) if tag else ""))
            elif selected:
                lines.append(T.bg("surface") + T.fg("accent") + T.BOLD + mark + " " + T.fg("heading") + label + T.UNBOLD + pad + "  " +
                             T.fg("text") + desc + (T.fg("border") + "  " + tag if tag else "") + tail + T.RESET)
            else:
                lines.append("  " + c("accent2", label) + pad + "  " + c("muted", desc) + (c("border", "  " + tag) if tag else ""))
        above, below = self.top, n - self.top - len(shown)
        if cols >= 50:
            hint = "↑↓ pilih · Tab lengkapi · Enter jalankan · Esc tutup" if envinfo.utf8_ok() else "up/down Tab Enter Esc"
        else:
            hint = "↑↓ Tab Enter Esc"
        extra = (f"  ↑{above}" if above else "") + (f"  ↓{below}" if below else "")
        lines.append("  " + c("border", truncate(hint + extra, cols - 4)))
        return lines

    def render(self, prompt, cols=None, rows=None):
        size = shutil.get_terminal_size((80, 24))
        cols, rows = cols or size.columns, rows or size.lines
        pw = swidth(strip_ansi(prompt))
        avail = max(10, cols - pw - 1)
        disp = self.buf.replace("\n", "↵" if envinfo.utf8_ok() else "|")
        w = [cw(ch) for ch in disp]
        v = min(self._view, self.cur)
        while v < self.cur and sum(w[v:self.cur]) > avail - (1 if v > 0 else 0) - 2:
            v += 1
        self._view = v
        left = v > 0
        room = avail - (1 if left else 0)
        end, used = v, 0
        while end < len(disp) and used + w[end] <= room:
            used += w[end]
            end += 1
        right = end < len(disp)
        if right:
            while end > v and used > room - 1:
                end -= 1
                used -= w[end]
        ell = "…" if envinfo.utf8_ok() else "~"
        text = (ell if left else "") + disp[v:end] + (ell if right else "")
        col = pw + (1 if left else 0) + sum(w[v:self.cur])
        shown = self._colorize(text, v == 0)
        out = ["\r", prompt, shown, "\x1b[K"]
        lines = self._popup_lines(cols, rows)
        total = max(len(lines), self._drawn)
        for i in range(total):
            out.append("\n\r\x1b[K")
            if i < len(lines):
                out.append(lines[i])
        if total:
            out.append(f"\x1b[{total}A")
        out.append(f"\x1b[{col + 1}G")
        self._drawn = len(lines)
        return "".join(out)

    def _colorize(self, text, at_start):
        if not T.ENABLED:
            return text

        def sub(m):
            tok = m.group(0)
            if tok.startswith("/") and at_start and m.start() == 0:
                return c("heading", tok, bold=True)
            if tok.startswith("@"):
                return c("info", tok)
            if tok.startswith("$"):
                return c("accent2", tok)
            return tok
        return re.sub(r"(?<!\S)(?:/[\w-]*|@\S*|\$[\w-]+)", sub, text)

    # ---- loop utama
    def available(self):
        return bool(termios and sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("CODINX_SIMPLE_INPUT"))

    def read(self, prompt, initial=""):
        if not self.available():
            return input(prompt)
        self.used = True
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        reader = KeyReader(fd)
        self.reset(initial)
        out = sys.stdout
        try:
            tty.setcbreak(fd)
            out.write("\x1b[?2004h")
            self.refresh()
            out.write(self.render(prompt))
            out.flush()
            while not self.done:
                for k in reader.read():
                    if self.handle(k) == "clear":
                        out.write("\x1b[H\x1b[2J")
                        self._drawn = 0
                    if self.done:
                        break
                if self.done:
                    self.sugg = []
                out.write(self.render(prompt))
                out.flush()
            out.write("\n")
        except (KeyboardInterrupt, EOFError):
            self.sugg = []
            out.write(self.render(prompt) + "\n")
            out.flush()
            raise
        finally:
            out.write("\x1b[?2004l")
            out.flush()
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        self._remember(self.result)
        return self.result


def suggest_common(values):
    from .suggest import common_prefix
    return common_prefix(values)
