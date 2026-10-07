"""Pemilih interaktif (↑↓, ketik untuk mencari, Enter, Esc) dengan pratinjau langsung — untuk /theme, /design, dll.

Hanya untuk TTY; pemanggil harus menyediakan jalur non-interaktif sendiri (cukup cek `available()`).
"""
import os
import sys

from . import envinfo
from . import themes as T
from .lineedit import KeyReader, swidth, termios, truncate, tty
from .suggest import rank
from .themes import c


def available():
    return bool(termios and sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("CODINX_SIMPLE_INPUT"))


def pick(title, items, current=None, on_move=None, preview=None, rows=10):
    """items: [(value, label, desc)] -> value terpilih, atau None bila dibatalkan.
    on_move(value) dipanggil tiap sorotan berubah (mis. menerapkan tema); preview(value) -> [baris] ditampilkan di bawah daftar."""
    if not items:
        return None
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    reader = KeyReader(fd)
    query, sel, top, drawn = "", 0, 0, 0
    labels = [it[1] for it in items]
    cur_idx = next((i for i, it in enumerate(items) if it[0] == current), 0)
    sel = cur_idx
    out = sys.stdout

    def visible():
        idx = rank(query, labels) if query else list(range(len(items)))
        return idx or []

    def draw(final=False):
        nonlocal drawn, top
        cols, lines_avail = envinfo.term_size().columns, envinfo.term_size().lines
        idx = visible()
        nonlocal sel
        sel = max(0, min(sel, len(idx) - 1)) if idx else 0
        maxr = max(3, min(rows, lines_avail - 9))
        if sel < top:
            top = sel
        if sel >= top + maxr:
            top = sel - maxr + 1
        lines = [c("heading", title, bold=True) + c("muted", "  " + (f"cari: {query}" if query else "ketik untuk mencari"))]
        mark = "❯" if envinfo.utf8_ok() else ">"
        lw = min(max([swidth(items[i][1]) for i in idx] or [8]), 26)
        for pos in range(top, min(len(idx), top + maxr)):
            value, label, desc = items[idx[pos]]
            on = pos == sel
            flag = c("ok", "●") if value == current else " "
            body = truncate(label, lw).ljust(lw + (len(label) - swidth(label) if swidth(label) < len(label) else 0))
            d = truncate(desc, max(0, cols - lw - 10))
            if not T.ENABLED:
                lines.append(("> " if on else "  ") + body + "  " + d)
            elif on:
                lines.append(T.bg("surface") + T.fg("accent") + T.BOLD + mark + " " + T.fg("heading") + body + T.UNBOLD + "  " + T.fg("text") + d + T.RESET)
            else:
                lines.append("  " + c("accent2", body) + "  " + c("muted", d))
            lines[-1] = lines[-1] + ("" if value != current else " " + flag)
        if len(idx) > maxr:
            lines.append(c("border", f"  {len(idx)} pilihan · ↑↓ PgUp PgDn"))
        if not idx:
            lines.append(c("muted", "  (tidak ada yang cocok)"))
        if preview and idx and not final:
            lines.append("")
            lines += [truncate_ansi(x, cols - 1) for x in (preview(items[idx[sel]][0]) or [])]
        lines.append(c("border", "  " + ("↑↓ pilih · Enter terapkan · Esc batal" if envinfo.utf8_ok() else "up/down Enter Esc")))
        buf = []
        if drawn:
            buf.append(f"\x1b[{drawn - 1}A" if drawn > 1 else "")
        buf.append("\r")
        for i, ln in enumerate(lines):
            buf.append("\x1b[K" + ln + ("\n" if i < len(lines) - 1 else ""))
        extra = drawn - len(lines)
        if extra > 0:
            for _ in range(extra):
                buf.append("\n\x1b[K")
            buf.append(f"\x1b[{extra}A")
        drawn = len(lines)
        out.write("".join(buf))
        out.flush()
        return idx

    def clear():
        if drawn:
            out.write((f"\x1b[{drawn - 1}A" if drawn > 1 else "") + "\r\x1b[J")
            out.flush()

    result = None
    try:
        tty.setcbreak(fd)
        out.write("\x1b[?25l")
        idx = draw()
        last = items[idx[sel]][0] if idx else None
        if on_move and last is not None:
            on_move(last)
        while True:
            toks = reader.read()
            changed = False
            for k in toks:
                idx = visible()
                if k == "ENTER":
                    result = items[idx[sel]][0] if idx else None
                    raise StopIteration
                if k in ("ESC", "C-c"):
                    result = None
                    raise StopIteration
                if k in ("UP", "C-p"):
                    sel = (sel - 1) % max(1, len(idx))
                elif k in ("DOWN", "C-n"):
                    sel = (sel + 1) % max(1, len(idx))
                elif k == "PGUP":
                    sel = max(0, sel - rows)
                elif k == "PGDN":
                    sel = min(max(0, len(idx) - 1), sel + rows)
                elif k == "HOME":
                    sel = 0
                elif k == "END":
                    sel = max(0, len(idx) - 1)
                elif k == "BACKSPACE":
                    query, sel = query[:-1], 0
                elif len(k) == 1 and k >= " ":
                    query, sel = query + k, 0
                changed = True
            if changed:
                idx = draw()
                now = items[idx[sel]][0] if idx else None
                if on_move and now is not None and now != last:
                    on_move(now)
                    idx = draw()
                last = now
    except StopIteration:
        pass
    except KeyboardInterrupt:
        result = None
    finally:
        clear()
        out.write("\x1b[?25h")
        out.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return result


def truncate_ansi(s, width):
    """Potong string ber-ANSI ke `width` kolom tampilan tanpa memutus escape."""
    from .lineedit import cw
    out, used, i = [], 0, 0
    while i < len(s):
        if s[i] == "\x1b":
            j = i + 1
            if j < len(s) and s[j] == "[":
                j += 1
                while j < len(s) and not ("@" <= s[j] <= "~"):
                    j += 1
            out.append(s[i:j + 1])
            i = j + 1
            continue
        w = cw(s[i])
        if used + w > width:
            break
        out.append(s[i])
        used += w
        i += 1
    return "".join(out) + (T.RESET if T.ENABLED else "")
