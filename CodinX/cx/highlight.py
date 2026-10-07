"""Syntax highlighting lewat Pygments (salinan vendor di cx/vendor, BSD-2). Gagal/tak tersedia -> None (UI pakai teks polos)."""
import os
import sys

from . import themes as T

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
_S = {"ready": None}
STYLE = {"codinx": "monokai", "tokyonight": "material", "catppuccin": "dracula", "gruvbox": "gruvbox-dark",
         "kanagawa": "zenburn", "nord": "nord", "one-dark": "one-dark", "everforest": "gruvbox-dark",
         "ayu": "native", "matrix": "fruity", "system": "native"}
MAX_LINES = 400


def _init():
    if _S["ready"] is None:
        try:
            if os.path.isdir(os.path.join(_VENDOR, "pygments")) and _VENDOR not in sys.path:
                sys.path.insert(0, _VENDOR)
            from pygments import highlight
            from pygments.formatters import Terminal256Formatter, TerminalTrueColorFormatter
            from pygments.lexers import get_lexer_by_name
            _S.update(ready=True, highlight=highlight, lexer=get_lexer_by_name,
                      f256=Terminal256Formatter, ftc=TerminalTrueColorFormatter)
        except Exception:
            _S["ready"] = False
    return _S["ready"]


def available():
    return bool(_init())


_STYLES = {}


def _style_for(theme):
    """Kelas Style Pygments yang dibangun dari palet tema (kode selalu senada dengan UI)."""
    if theme in _STYLES:
        return _STYLES[theme]
    cls = None
    try:
        from pygments.style import Style
        from pygments.token import (Comment, Error, Generic, Keyword, Name, Number, Operator, Punctuation, String, Token)
        h = lambda r: T.role_hex(r, theme)
        if all(h(r) for r in ("accent", "accent2", "ok", "warn", "err", "info", "text", "muted")):
            styles = {Token: h("text"), Comment: "italic " + h("muted"), Keyword: "bold " + h("accent"), Keyword.Type: h("info"),
                      Keyword.Constant: h("warn"), Name.Function: h("accent2"), Name.Class: "bold " + h("info"), Name.Decorator: h("warn"),
                      Name.Builtin: h("info"), Name.Exception: h("err"), String: h("ok"), String.Escape: h("warn"), Number: h("warn"),
                      Operator: h("text"), Operator.Word: h("accent"), Punctuation: h("muted"), Generic.Deleted: h("err"),
                      Generic.Inserted: h("ok"), Generic.Heading: "bold " + h("accent"), Generic.Subheading: h("accent2"), Error: h("err")}
            cls = type("CodinXStyle_" + theme.replace("-", "_"), (Style,), {"styles": styles, "background_color": "#00000000"})
    except Exception:
        cls = None
    _STYLES[theme] = cls
    return cls


def render(code, lang):
    """-> list baris ber-ANSI, atau None bila tidak bisa di-highlight."""
    if not (T.ENABLED and lang and _init()) or code.count("\n") > MAX_LINES:
        return None
    try:
        lexer = _S["lexer"](lang.split()[0].lower().strip("{}."), stripnl=False)
    except Exception:
        return None
    style = _style_for(T.current())
    try:
        if T.depth() == 16:
            from pygments.formatters import TerminalFormatter
            fmt = TerminalFormatter(bg="light" if not T.info(T.current()).get("dark", True) else "dark")
        else:
            fmt_cls = _S["ftc"] if T.TRUE else _S["f256"]
            fmt = fmt_cls(style=style or STYLE.get(T.current(), "monokai"))
    except Exception:
        fmt = _S["f256"](style="default")
    try:
        out = _S["highlight"](code, lexer, fmt)
    except Exception:
        return None
    return out.rstrip("\n").split("\n")
