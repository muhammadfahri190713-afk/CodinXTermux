import os
import tempfile
import unittest
from unittest import mock

from cx import lineedit, suggest

CMDS = [("/help", "daftar perintah"), ("/new", "sesi baru"), ("/sessions", "sesi lama"), ("/skills", "daftar skill"), ("/skill", "jalankan skill"),
        ("/historymode", "mode riwayat"), ("/hooks", "hooks"), ("/theme", "ganti tema"), ("/exit", "keluar"), ("/remember", "ingat")]


def make(cwd=None, skills=None):
    return suggest.Completer(lambda: CMDS, aliases=lambda: {"/q": "/exit"}, customs=lambda: [("/review", "review git")],
                             skills=lambda: skills if skills is not None else [("web-check", "cek web"), ("secret-scan", "scan rahasia")],
                             args=lambda cmd, w: [("tokyonight", "gelap"), ("dracula", "gelap"), ("auto", "")] if cmd == "/theme" else [],
                             cwd=(lambda: cwd) if cwd else None)


def vals(s):
    return [x.value for x in s]


class Ranking(unittest.TestCase):
    def test_prefix_then_word_then_substring_then_fuzzy(self):
        names = ["/help", "/historymode", "/theme", "/web-check", "/hooks"]
        order = [names[i] for i in suggest.rank("h", names)]
        self.assertEqual(order[:3], ["/help", "/historymode", "/hooks"])
        self.assertEqual([names[i] for i in suggest.rank("check", names)], ["/web-check"])      # awal kata
        self.assertEqual([names[i] for i in suggest.rank("eme", names)], ["/theme"])            # substring
        self.assertEqual([names[i] for i in suggest.rank("tm", names)], ["/historymode", "/theme"])                  # subsequence, urutan asli
        self.assertEqual(suggest.rank("", names), list(range(5)))

    def test_common_prefix(self):
        self.assertEqual(suggest.common_prefix(["/skills", "/skill", "/sessions"]), "/s")
        self.assertEqual(suggest.common_prefix(["/Skills", "/skill"]), "/Skill")
        self.assertEqual(suggest.common_prefix([]), "")


class Completer(unittest.TestCase):
    def test_slash_alone_lists_commands_in_declared_order(self):
        _, _, s = make().suggest("/", 1)
        self.assertEqual(vals(s)[:3], ["/help", "/new", "/sessions"])

    def test_h_puts_help_first(self):
        _, _, s = make().suggest("/h", 2)
        self.assertEqual(vals(s)[0], "/help")
        self.assertIn("/historymode", vals(s))

    def test_narrows_per_letter(self):
        c = make()
        counts = [len(c.suggest("/th"[:i], i)[2]) for i in (1, 2, 3)]
        self.assertGreater(counts[0], counts[2])
        self.assertEqual(vals(c.suggest("/th", 3)[2]), ["/theme"])

    def test_kinds_and_labels(self):
        s = {x.value: x for x in make().suggest("/", 1)[2]}
        self.assertEqual(s["/review"].kind, "custom")
        self.assertEqual(s["/web-check"].kind, "skill")
        self.assertEqual(s["/q"].kind, "alias")
        self.assertTrue(s["/skill"].needs_arg)
        self.assertFalse(s["/help"].needs_arg)

    def test_same_name_skill_and_custom_are_both_shown(self):
        c = suggest.Completer(lambda: [], customs=lambda: [("/deploy", "custom")], skills=lambda: [("deploy", "skill")])
        self.assertEqual(sorted(x.kind for x in c.suggest("/dep", 4)[2]), ["custom", "skill"])

    def test_argument_mode_and_replacement_span(self):
        start, end, s = make().suggest("/theme to", 9)
        self.assertEqual((start, end), (7, 9))
        self.assertEqual(vals(s)[0], "tokyonight")                                     # awalan dulu, lalu fuzzy ("auto")
        self.assertEqual(make().suggest("/theme ", 7)[2][0].value, "tokyonight")
        self.assertEqual(make().suggest("/help ", 6)[2], [])              # perintah tanpa saran argumen

    def test_dollar_skills_and_plain_text(self):
        _, _, s = make().suggest("tolong $sec", 11)
        self.assertEqual(vals(s), ["$secret-scan"])
        self.assertEqual(make().suggest("halo dunia", 10)[2], [])
        self.assertEqual(make().suggest("harga $5 dan $", 14)[2][0].value, "$web-check")

    def test_file_mentions(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "src"))
        os.makedirs(os.path.join(d, "node_modules"))
        for f in ("src/main.py", "src/util.py", "README.md", ".hidden"):
            open(os.path.join(d, f), "w").close()
        c = make(cwd=d)
        _, _, s = c.suggest("lihat @", 7)
        self.assertEqual(vals(s), ["@src/", "@README.md"])                 # folder dulu; tersembunyi & node_modules disembunyikan
        self.assertEqual(vals(c.suggest("@src/ma", 7)[2]), ["@src/main.py"])
        self.assertEqual(vals(c.suggest("@src/", 5)[2]), ["@src/main.py", "@src/util.py"])
        self.assertEqual(c.suggest("@zzz", 4)[2], [])
        self.assertIn("@.hidden", vals(c.suggest("@.h", 3)[2]))


class EditorLogic(unittest.TestCase):
    def ed(self, **kw):
        return lineedit.Editor(make(**kw))

    def type(self, e, text):
        for ch in text:
            e.handle(ch)
        return e

    def test_typing_shows_popup_with_help_first_and_enter_runs_it(self):
        e = self.type(self.ed(), "/h")
        self.assertEqual(e.sugg[0].value, "/help")
        e.handle("ENTER")
        self.assertTrue(e.done)
        self.assertEqual(e.result.strip(), "/help")

    def test_arrow_selection_then_enter(self):
        e = self.type(self.ed(), "/h")
        e.handle("DOWN")
        self.assertEqual(e.sel, 1)
        e.handle("ENTER")
        self.assertEqual(e.result.strip(), "/historymode")
        e2 = self.type(self.ed(), "/h")
        e2.handle("UP")                                                   # membungkus ke bawah
        self.assertEqual(e2.sel, len(e2.sugg) - 1)

    def test_tab_extends_to_longest_common_prefix_then_completes(self):
        e = self.type(self.ed(), "/sk")                                    # /skills & /skill -> awalan sama "/skill"
        e.handle("TAB")
        self.assertEqual(e.buf, "/skill")
        e.handle("TAB")                                                    # tak ada awalan lebih panjang -> terima pilihan
        self.assertTrue(e.buf.startswith("/skill"))
        self.assertFalse(e.done)

    def test_tab_single_match_completes_with_space(self):
        e = self.type(self.ed(), "/th")
        e.handle("TAB")
        self.assertEqual((e.buf, e.cur), ("/theme ", 7))
        self.assertEqual(e.sugg[0].value, "tokyonight")                    # saran argumen langsung muncul

    def test_enter_on_command_that_needs_args_does_not_submit(self):
        e = self.type(self.ed(), "/skil")
        e.sel = [s.value for s in e.sugg].index("/skill")
        e.handle("ENTER")
        self.assertFalse(e.done)
        self.assertEqual(e.buf, "/skill ")

    def test_enter_on_argument_submits_complete_command(self):
        e = self.type(self.ed(), "/theme dra")
        e.handle("ENTER")
        self.assertTrue(e.done)
        self.assertEqual(e.result.strip(), "/theme dracula")

    def test_dollar_skill_accept_keeps_editing(self):
        e = self.type(self.ed(), "pakai $web")
        e.handle("ENTER")
        self.assertFalse(e.done)
        self.assertEqual(e.buf, "pakai $web-check ")

    def test_escape_hides_popup_until_text_changes(self):
        e = self.type(self.ed(), "/h")
        e.handle("ESC")
        self.assertEqual(e.sugg, [])
        e.handle("e")
        self.assertTrue(e.sugg)
        e.handle("ESC")
        e.handle("ENTER")                                                  # popup tertutup -> Enter langsung kirim teks apa adanya
        self.assertEqual(e.result, "/he")

    def test_plain_text_enter_and_exact_command(self):
        e = self.type(self.ed(), "halo dunia")
        self.assertEqual(e.sugg, [])
        e.handle("ENTER")
        self.assertEqual(e.result, "halo dunia")
        e = self.type(self.ed(), "/help")
        self.assertEqual(e.sugg, [])                                       # sudah lengkap: tanpa popup
        e.handle("ENTER")
        self.assertEqual(e.result, "/help")

    def test_history_recall_does_not_open_popup(self):
        e = self.ed()
        e.history = ["/status", "tulis tes"]
        e.handle("UP")
        self.assertEqual(e.buf, "tulis tes")
        e.handle("UP")
        self.assertEqual((e.buf, e.sugg), ("/status", []))
        e.handle("DOWN")
        e.handle("DOWN")
        self.assertEqual(e.buf, "")

    def test_editing_keys(self):
        e = self.type(self.ed(), "satu dua tiga")
        e.handle("C-w")
        self.assertEqual(e.buf, "satu dua ")
        e.handle("C-a")
        e.handle("DEL")
        self.assertEqual(e.buf, "atu dua ")
        e.handle("M-f")
        self.assertEqual(e.cur, 3)
        e.handle("C-k")
        self.assertEqual(e.buf, "atu")
        e.handle("C-u")
        self.assertEqual(e.buf, "")
        with self.assertRaises(EOFError):
            e.handle("C-d")

    def test_paste_normalises_newlines_and_alt_enter_inserts_one(self):
        e = self.ed()
        e.handle("PASTE:baris1\r\nbaris2\x1b[31m")
        self.assertEqual(e.buf, "baris1\nbaris2[31m")
        e.handle("M-ENTER")
        self.assertTrue(e.buf.endswith("\n"))
        self.assertFalse(e.done)

    def test_unicode_cursor_and_widths(self):
        e = self.type(self.ed(), "日本語")
        self.assertEqual(lineedit.swidth(e.buf), 6)
        self.assertEqual(lineedit.swidth("é"), 1)
        self.assertEqual(lineedit.truncate("abcdefghij", 5), "abcd…")


class Rendering(unittest.TestCase):
    def test_popup_rows_and_cursor_restore(self):
        e = lineedit.Editor(make())
        for ch in "/h":
            e.handle(ch)
        out = e.render("› ", cols=60, rows=24)
        plain = lineedit.strip_ansi(out)
        self.assertIn("/help", plain)
        self.assertIn("Tab", plain)                                        # baris petunjuk
        rows = len(e.sugg) + 1
        self.assertIn(f"\x1b[{rows}A", out)                                # kursor kembali ke baris input
        self.assertTrue(out.rstrip().endswith("G"))                       # kolom kursor di-set

    def test_popup_is_cleared_when_it_shrinks(self):
        e = lineedit.Editor(make())
        e.handle("/")
        first = e.render("› ", cols=60, rows=24)
        for ch in "th":
            e.handle(ch)
        second = e.render("› ", cols=60, rows=24)
        self.assertGreaterEqual(second.count("\n"), first.count("\n") - 1)

    def test_long_input_scrolls_horizontally_within_width(self):
        e = lineedit.Editor(make())
        e.handle("PASTE:" + "kata " * 60)
        out = e.render("› ", cols=30, rows=24)
        line = lineedit.strip_ansi(out.split("\x1b[K")[0]).replace("\r", "")
        self.assertLessEqual(lineedit.swidth(line), 29)
        self.assertIn("…", line)

    def test_narrow_and_short_terminals_do_not_crash(self):
        e = lineedit.Editor(make())
        e.handle("/")
        for cols, rows in ((20, 6), (12, 4), (80, 5)):
            out = e.render("› ", cols=cols, rows=rows)
            self.assertIn("\x1b[", out)

    def test_plain_when_color_disabled(self):
        from cx import themes as T
        old = T.depth()
        T.set_depth(0)
        try:
            e = lineedit.Editor(make())
            e.handle("/")
            e.handle("h")
            self.assertIn("> /help", e.render("> ", cols=60, rows=24))
        finally:
            T.set_depth(old)


class KeyParsing(unittest.TestCase):
    def feed(self, text):
        return lineedit.KeyReader(0).feed(text)

    def test_sequences(self):
        self.assertEqual(self.feed("a\x1b[A\x1b[B\x1b[C\x1b[D"), ["a", "UP", "DOWN", "RIGHT", "LEFT"])
        self.assertEqual(self.feed("\x1bOA\x1bOH\x1b[F\x1b[3~\x1b[5~\x1b[6~\x1b[Z"), ["UP", "HOME", "END", "DEL", "PGUP", "PGDN", "BTAB"])
        self.assertEqual(self.feed("\x1b[1;5C\x1b[1;3D"), ["C-RIGHT", "M-LEFT"])
        self.assertEqual(self.feed("\r\n\t\x7f\x01\x04"), ["ENTER", "ENTER", "TAB", "BACKSPACE", "C-a", "C-d"])
        self.assertEqual(self.feed("\x1bb\x1b\r\x1b\x7f"), ["M-b", "M-ENTER", "M-BACKSPACE"])
        self.assertEqual(self.feed("\x1b"), ["ESC"])

    def test_bracketed_paste_and_split_chunks(self):
        r = lineedit.KeyReader(0)
        self.assertEqual(r.feed("x\x1b[200~satu\ndua\x1b[201~y"), ["x", "PASTE:satu\ndua", "y"])
        r2 = lineedit.KeyReader(0)
        self.assertEqual(r2.feed("\x1b[200~bagian1"), [])
        self.assertEqual(r2.feed("bagian2\x1b[201~"), ["PASTE:bagian1bagian2"])

    def test_unicode_passthrough(self):
        self.assertEqual(self.feed("é日😀"), ["é", "日", "😀"])


if __name__ == "__main__":
    unittest.main()
