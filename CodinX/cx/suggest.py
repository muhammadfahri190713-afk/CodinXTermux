"""Mesin saran otomatis ala opencode: /perintah, argumen perintah, @file, $skill.  Logika murni — mudah diuji.

Perilaku (mengikuti praktik menu slash pada TUI sejenis):
  * mengetik "/" lalu huruf -> daftar menyempit tiap huruf; kecocokan awalan diurutkan menurut urutan daftar perintah
    (jadi "/h" -> "/help" paling atas);
  * Tab melengkapi awalan terpanjang yang sama; bila hanya satu kecocokan, melengkapi penuh;
  * perintah yang butuh argumen diberi spasi otomatis, lalu saran argumen muncul;
  * skill muncul di menu slash berlabel "skill"; nama perintah/skill yang sama tidak saling menyembunyikan.
"""
import os
import re
from collections import namedtuple

Suggestion = namedtuple("Suggestion", "value label desc kind needs_arg")

NEEDS_ARG = {"/skill", "/remember", "/view"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", ".mypy_cache", ".cache"}
MAX_RESULTS = 60


def rank(query, names):
    """-> indeks `names` terurut: awalan > awal kata > substring > subsequence (urutan asli dipertahankan)."""
    q = query.lower()
    if not q:
        return list(range(len(names)))
    tiers = ([], [], [], [])
    for i, n in enumerate(names):
        low = n.lower().lstrip("/@$")
        if low.startswith(q):
            tiers[0].append(i)
        elif any(w.startswith(q) for w in re.split(r"[-_./ ]+", low) if w):
            tiers[1].append(i)
        elif q in low:
            tiers[2].append(i)
        else:
            it = iter(low)
            if all(ch in it for ch in q):
                tiers[3].append(i)
    return [i for t in tiers for i in t]


def common_prefix(values):
    if not values:
        return ""
    lo, hi = min(values, key=str.lower), max(values, key=str.lower)
    n = 0
    while n < len(lo) and n < len(hi) and lo[n].lower() == hi[n].lower():
        n += 1
    return values[0][:n]


class Completer:
    """Sumber data disuntik dari aplikasi (fungsi), sehingga modul ini tidak bergantung pada App."""

    def __init__(self, commands, aliases=None, customs=None, skills=None, args=None, cwd=None):
        self.commands = commands            # fungsi -> [(nama, deskripsi)]   nama diawali "/"
        self.aliases = aliases or (lambda: {})
        self.customs = customs or (lambda: [])      # [(nama, deskripsi)]
        self.skills = skills or (lambda: [])        # [(nama, deskripsi)]  tanpa "/"
        self.args = args or (lambda cmd, word: [])  # [(nilai, deskripsi)]
        self.cwd = cwd or os.getcwd

    # ------------------------------------------------------------ titik masuk
    def suggest(self, buf, cur):
        """-> (start, end, [Suggestion]); teks buf[start:end] akan diganti nilai saran terpilih."""
        head = buf[:cur]
        if buf.startswith("/"):
            if not re.search(r"\s", head):
                end = cur
                while end < len(buf) and not buf[end].isspace():
                    end += 1
                return 0, end, self._commands(head[1:])
            cmd = head.split(None, 1)[0]
            m = re.search(r"(\S*)$", head)
            start = m.start(1)
            end = cur
            while end < len(buf) and not buf[end].isspace():
                end += 1
            return start, end, self._args(cmd, m.group(1))
        m = re.search(r"(?:^|\s)([@$][^\s]*)$", head)
        if m:
            start = m.start(1)
            end = cur
            while end < len(buf) and not buf[end].isspace():
                end += 1
            word = m.group(1)
            return start, end, (self._files(word[1:]) if word[0] == "@" else self._vars(word[1:]))
        return cur, cur, []

    # ------------------------------------------------------------ sumber saran
    def _commands(self, query):
        entries = [(n, d, "cmd") for n, d in self.commands()]
        have = {n for n, _, _ in entries}
        entries += [(n if n.startswith("/") else "/" + n, d, "custom") for n, d in self.customs()]
        entries += [("/" + n, d, "skill") for n, d in self.skills()]
        entries += [(a, "= " + t, "alias") for a, t in self.aliases().items() if a not in have]
        order = rank(query, [e[0] for e in entries])
        out = []
        for i in order[:MAX_RESULTS]:
            n, d, kind = entries[i]
            out.append(Suggestion(n, n, d, kind, n in NEEDS_ARG))
        return out

    def _args(self, cmd, word):
        pairs = list(self.args(cmd, word) or [])
        order = rank(word, [p[0] for p in pairs])
        return [Suggestion(pairs[i][0], pairs[i][0], pairs[i][1], "arg", False) for i in order[:MAX_RESULTS]]

    def _vars(self, query):
        sk = list(self.skills())
        order = rank(query, [n for n, _ in sk])
        return [Suggestion("$" + sk[i][0], "$" + sk[i][0], sk[i][1], "skill", False) for i in order[:MAX_RESULTS]]

    def _files(self, prefix):
        raw = os.path.expanduser(prefix)
        base = self.cwd()
        d, name = os.path.split(raw)
        folder = d if os.path.isabs(d) else os.path.join(base, d)
        try:
            entries = sorted(os.listdir(folder or base))
        except OSError:
            return []
        hidden_ok = name.startswith(".")
        out = []
        for e in entries:
            if (e.startswith(".") and not hidden_ok) or e in SKIP_DIRS:
                continue
            if name and not e.lower().startswith(name.lower()):
                continue
            full = os.path.join(folder or base, e)
            isdir = os.path.isdir(full)
            shown = (d + "/" if d and not d.endswith("/") else d) + e + ("/" if isdir else "")
            if prefix.startswith("~"):
                shown = prefix[: len(prefix) - len(name)] + e + ("/" if isdir else "")
            out.append(Suggestion("@" + shown, shown, "folder" if isdir else "file", "file", False))
            if len(out) >= MAX_RESULTS:
                break
        out.sort(key=lambda s: (not s.label.endswith("/"), s.label.lower()))
        return out
