"""Penampil Markdown di terminal (CommonMark via markdown-it): judul, daftar bersarang, kutipan, kode ber-warna, tabel, tautan.

Dipakai oleh /docs dan /view (dan `codinx docs`). Bila markdown-it tidak bisa dimuat, kembali ke renderer baris bawaan (ui.Markdown).
"""
import re

from . import design, envinfo, highlight, themes as T, ui, vendored
from .lineedit import cw, swidth
from .themes import c


def _runs(children):
    """Token inline -> [(teks, gaya)]; gaya = frozenset({'b','i','code','link','s'})."""
    out, st, href = [], set(), None
    for t in children or []:
        k = t.type
        if k == "text":
            out.append((t.content, frozenset(st)))
        elif k == "code_inline":
            out.append((t.content, frozenset(st | {"code"})))
        elif k in ("softbreak",):
            out.append((" ", frozenset(st)))
        elif k == "hardbreak":
            out.append(("\n", frozenset()))
        elif k == "strong_open":
            st.add("b")
        elif k == "strong_close":
            st.discard("b")
        elif k == "em_open":
            st.add("i")
        elif k == "em_close":
            st.discard("i")
        elif k == "s_open":
            st.add("s")
        elif k == "s_close":
            st.discard("s")
        elif k == "link_open":
            st.add("link")
            href = dict(t.attrs or {}).get("href")
        elif k == "link_close":
            st.discard("link")
            if href and not href.startswith("#"):
                out.append((f" ({href})", frozenset({"url"})))
            href = None
        elif k == "image":
            out.append(("[" + (t.content or "gambar") + "]", frozenset({"i"})))
        elif k == "html_inline":
            out.append((t.content, frozenset({"url"})))
    return out


def _paint(word, style):
    if "code" in style:
        return c("code", word)
    if "link" in style:
        return c("link", word, underline=True)
    if "url" in style:
        return c("muted", word)
    if "s" in style:
        return c("muted", word)
    if "b" in style:
        return c("heading", word, bold=True)
    if "i" in style:
        return c("text", word, italic=True)
    return c("text", word)


def _wrap(runs, width, first, rest):
    """Bungkus kata per kata (gaya dipertahankan per kata). first/rest = awalan (sudah ber-warna) baris pertama/berikutnya."""
    words = []
    for text, style in runs:
        for i, part in enumerate(re.split(r"(\s+)", text)):
            if not part:
                continue
            if part == "\n":
                words.append(("\n", style))
            elif part.isspace():
                words.append((" ", style))
            else:
                words.append((part, style))
    lines, cur, curw = [], first, ui.swidth_plain(first) if hasattr(ui, "swidth_plain") else swidth(_strip(first))
    pre_w = swidth(_strip(first))
    pending_space = False
    for w, style in words:
        if w == "\n":
            lines.append(cur)
            cur, curw, pending_space = rest, swidth(_strip(rest)), False
            continue
        if w == " ":
            pending_space = curw > swidth(_strip(rest if lines else first))
            continue
        ww = swidth(w)
        need = ww + (1 if pending_space else 0)
        if curw + need > width and curw > swidth(_strip(rest if lines else first)):
            lines.append(cur)
            cur, curw, pending_space = rest, swidth(_strip(rest)), False
            need = ww
        cur += (" " if pending_space else "") + _paint(w, style)
        curw += need
        pending_space = False
    lines.append(cur)
    return lines


def _strip(s):
    return ui.strip_ansi(s)


def render(text, width=None):
    """-> list baris ber-ANSI, atau None bila markdown-it tidak tersedia."""
    mdi = vendored.load("markdown_it")
    if mdi is None:
        return None
    parser = mdi.MarkdownIt("commonmark").enable("table").enable("strikethrough")
    toks = parser.parse(text)
    width = width or max(30, min(envinfo.term_size().columns - 2, 100))
    out = []
    bd = design.border()
    lists = []                    # tumpukan: {"ordered": bool, "n": int}
    quote = 0
    item_first = []               # awalan baris pertama item (sekali pakai)

    def prefix_rest():
        return "  " * len(lists) + (c("border", "┃ ") * quote if quote else "")

    i = 0
    while i < len(toks):
        t = toks[i]
        k = t.type
        if k == "heading_open":
            level = int(t.tag[1])
            runs = _runs(toks[i + 1].children)
            plain = "".join(r[0] for r in runs)
            if level == 1:
                out += ["", c("heading", plain.upper(), bold=True), c("border", "━" * min(swidth(plain), width))]
            elif level == 2:
                out += ["", c("heading", "▌ " + plain, bold=True)]
            else:
                out.append(c("accent2", design.icon("skill") + " " + plain, bold=True))
            i += 3
            continue
        if k == "paragraph_open":
            runs = _runs(toks[i + 1].children)
            base = prefix_rest()
            first = item_first.pop() if item_first else base
            out += _wrap(runs, width, first, base)
            if not t.hidden:
                out.append("")
            i += 3
            continue
        if k in ("bullet_list_open", "ordered_list_open"):
            lists.append({"ordered": k == "ordered_list_open", "n": int(dict(t.attrs or {}).get("start", 1))})
        elif k in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
            if not lists:
                out.append("")
        elif k == "list_item_open":
            ls = lists[-1]
            mark = f"{ls['n']}." if ls["ordered"] else design.icon("bullet")
            ls["n"] += 1
            depth = len(lists) - 1
            item_first.append("  " * depth + (c("border", "┃ ") * quote if quote else "") + c("accent", mark) + " ")
        elif k == "blockquote_open":
            quote += 1
        elif k == "blockquote_close":
            quote -= 1
        elif k in ("fence", "code_block"):
            lang = (t.info or "").strip().split()[0] if k == "fence" and (t.info or "").strip() else ""
            code = t.content.rstrip("\n")
            lines = highlight.render(code, lang) or [c("code", ln) for ln in code.split("\n")]
            base = prefix_rest()
            out.append(base + c("border", "  " + bd["tl"] + bd["h"] + " ") + c("accent2", lang or "code", italic=True))
            out += [base + c("border", "  " + bd["v"] + " ") + ln + (T.RESET if T.ENABLED else "") for ln in lines]
            out.append(base + c("border", "  " + bd["bl"] + bd["h"]))
            out.append("")
        elif k == "hr":
            out += [c("border", bd["h"] * min(width, 60)), ""]
        elif k == "table_open":
            header, body, row, in_head = [], [], [], False
            j = i + 1
            while j < len(toks) and toks[j].type != "table_close":
                tj = toks[j]
                if tj.type == "thead_open":
                    in_head = True
                elif tj.type == "thead_close":
                    in_head = False
                elif tj.type == "tr_open":
                    row = []
                elif tj.type in ("th_open", "td_open"):
                    row.append("".join(r[0] for r in _runs(toks[j + 1].children)))
                elif tj.type == "tr_close":
                    (header if in_head else body).append(row)
                j += 1
            out += ui.table_lines(header[0] if header else [""] * len(body[0]), body) + [""]
            i = j
        elif k == "html_block":
            out += [c("muted", ln) for ln in t.content.rstrip("\n").split("\n")] + [""]
        i += 1
    while out and out[-1] == "":
        out.pop()
    return out


def show(ui_, text):
    lines = render(text)
    if lines is None:
        ui_.markdown(text)
        return
    for ln in lines:
        ui_.p(ln)
