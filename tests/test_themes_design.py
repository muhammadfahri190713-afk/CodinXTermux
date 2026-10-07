import re
import unittest
from unittest import mock

from cx import design, envinfo, highlight, themes as T, ui


class Base(unittest.TestCase):
    def setUp(self):
        self._old = (T.depth(), T.current(), design.dump())

    def tearDown(self):
        T.set_depth(self._old[0])
        T.set_theme(self._old[1])
        design.STATE.clear()
        design.STATE.update(self._old[2])


class Palettes(Base):
    def test_many_themes_dark_and_light_with_all_roles(self):
        names = T.names()
        self.assertGreaterEqual(len(names), 45)
        self.assertTrue(any(not T.info(n)["dark"] for n in names) and any(T.info(n)["dark"] for n in names))
        for n in names:
            if n == "system":
                continue
            for r in T.ROLES:
                self.assertRegex(T.THEMES[n][r], r"^#[0-9A-Fa-f]{6}$", f"{n}.{r}")

    def test_contrast_guarantees_for_every_theme(self):
        for n in T.names():
            if n == "system":
                continue
            bg = T.META[n]["bg"]
            th = T.THEMES[n]
            self.assertGreaterEqual(T.contrast(th["text"], bg), 6.8, f"{n} text")
            self.assertGreaterEqual(T.contrast(th["muted"], bg), 3.9, f"{n} muted")
            for r in ("accent", "accent2", "ok", "warn", "err", "info"):
                self.assertGreaterEqual(T.contrast(th[r], bg), 3.4, f"{n} {r}")

    def test_catppuccin_matches_official_palette(self):
        self.assertEqual(T.META["catppuccin-mocha"]["bg"], "#1E1E2E")
        self.assertEqual(T.THEMES["catppuccin-mocha"]["accent"], "#CBA6F7")        # mauve
        self.assertEqual(T.THEMES["catppuccin-latte"]["err"], "#D20F39")           # red (latte)
        self.assertFalse(T.META["catppuccin-latte"]["dark"])

    def test_resolve_and_deprecated_names(self):
        self.assertEqual(T.resolve("auto", detect=False), T.DEFAULT_DARK)
        self.assertEqual(T.resolve("light"), T.DEFAULT_LIGHT)
        self.assertEqual(T.resolve("dark"), T.DEFAULT_DARK)
        self.assertEqual(T.resolve("catppuccin"), "catppuccin-mocha")
        self.assertEqual(T.resolve("tidak-ada"), T.DEFAULT_DARK)
        self.assertTrue(T.set_theme("tokyo-night") and T.current() == "tokyonight")


class ColorDepth(Base):
    def d(self, env, tty=True):
        return T.detect_depth(env, tty)

    def test_detection_matrix(self):
        self.assertEqual(self.d({"TERM": "xterm-256color"}), 256)
        self.assertEqual(self.d({"TERM": "xterm-256color", "COLORTERM": "truecolor"}), 24)
        self.assertEqual(self.d({"TERM": "xterm", "TERMUX_VERSION": "0.118"}), 24)
        self.assertEqual(self.d({"TERM": "xterm", "PREFIX": "/data/data/com.termux/files/usr"}), 24)
        self.assertEqual(self.d({"TERM": "xterm-kitty"}), 24)
        self.assertEqual(self.d({"TERM": "linux"}), 16)
        self.assertEqual(self.d({"TERM": "dumb"}), 0)
        self.assertEqual(self.d({"TERM": "xterm-256color"}, tty=False), 0)

    def test_overrides(self):
        self.assertEqual(self.d({"TERM": "xterm-256color", "NO_COLOR": "1"}), 0)
        self.assertEqual(self.d({"TERM": "xterm-256color", "NO_COLOR": "1", "CODINX_COLOR": "always"}), 256)
        self.assertEqual(self.d({"TERM": "dumb", "CODINX_COLOR": "truecolor"}), 24)
        self.assertEqual(self.d({"TERM": "xterm-256color", "CODINX_COLOR": "never"}), 0)
        self.assertEqual(self.d({"TERM": "xterm", "CODINX_COLOR": "16"}), 16)
        self.assertEqual(self.d({"FORCE_COLOR": "3"}, tty=False), 24)

    def test_conversions_pick_the_nearest_color(self):
        self.assertEqual(T.to_256((255, 0, 0)), 196)
        self.assertEqual(T.to_256((0, 0, 0)), 16)
        self.assertIn(T.to_256((128, 128, 128)), range(232, 256))
        self.assertIn(T.to_16((0, 0, 255)), (4, 12))
        self.assertEqual(T.to_16((255, 255, 255)), 15)

    def test_background_detection_sources(self):
        self.assertEqual(T.detect_background(env={"COLORFGBG": "0;15"}), "light")
        self.assertEqual(T.detect_background(env={"COLORFGBG": "15;0"}), "dark")
        self.assertEqual(T.detect_background(env={"COLORFGBG": "garbage"}), None)
        self.assertEqual(T.detect_background(env={"CODINX_BACKGROUND": "light"}), "light")
        rgb = T._parse_osc11(b"\x1b]11;rgb:ffff/ffff/ffff\x07")
        self.assertEqual(rgb, (1.0, 1.0, 1.0))
        self.assertAlmostEqual(T._parse_osc11(b"rgb:00/00/00")[0], 0.0)

    def test_escape_formats_per_depth(self):
        T.set_theme("codinx")
        T.set_depth(24)
        self.assertRegex(T.fg("accent"), r"^\x1b\[38;2;\d+;\d+;\d+m$")
        T.set_depth(256)
        self.assertRegex(T.fg("accent"), r"^\x1b\[38;5;\d+m$")
        T.set_depth(16)
        self.assertRegex(T.fg("accent"), r"^\x1b\[(3\d|9\d)m$")
        T.set_depth(0)
        self.assertEqual((T.fg("accent"), T.c("accent", "x"), T.pill("ok", "x")), ("", "x", "[x]"))

    def test_ui_is_not_monochrome_at_any_depth(self):
        """Regresi 'UI abu-abu': banner harus memakai banyak warna berbeda, bukan satu warna redup."""
        for depth, minimum in ((24, 8), (256, 7), (16, 5)):
            T.set_depth(depth)
            T.set_theme("codinx")
            out = []
            u = ui.UI()
            u.w = out.append
            u.banner("m-1", "build", "UJI COBA", "/root")
            codes = set(re.findall(r"\x1b\[[0-9;]*m", "".join(out)))
            self.assertGreaterEqual(len(codes), minimum, f"depth {depth}: hanya {len(codes)} kode warna")

    def test_borders_use_their_own_role_not_muted(self):
        T.set_depth(24)
        T.set_theme("codinx")
        self.assertNotEqual(T.fg("border"), T.fg("muted"))


class Design(Base):
    def test_registries_are_consistent(self):
        keys = set(design.BORDERS["rounded"])
        for n, b in design.BORDERS.items():
            self.assertEqual(set(b), keys, n)
        ik = set(design.ICONS["unicode"])
        for n, i in design.ICONS.items():
            self.assertEqual(set(i), ik, n)
        for n, (frames, interval, _) in design.SPINNERS.items():
            self.assertTrue(len(frames) >= 2 and interval > 0, n)
        self.assertGreaterEqual(len(design.SPINNERS), 28)
        for style in design.CHOICES["banner"]:
            if style not in ("pro", "mini", "boxed", "none"):
                self.assertTrue(design.banner_rows(style), style)

    def test_presets_are_valid(self):
        self.assertGreaterEqual(len(design.PRESETS), 10)
        for n, p in design.PRESETS.items():
            self.assertTrue(p["theme"] == "auto" or p["theme"] in T.THEMES, n)
            for k, v in p.items():
                if k != "theme":
                    self.assertIn(v, design.CHOICES[k], f"{n}.{k}")
            self.assertIn(n, design.PRESET_NOTE)

    def test_apply_load_dump_roundtrip(self):
        self.assertEqual(design.apply_preset("retro"), "amber")
        saved = design.dump()
        design.load({})
        self.assertEqual(design.get("border"), "rounded")
        design.load({"design": saved, "x": 1})
        self.assertEqual(design.dump(), saved)
        design.load({"design": {"border": "tidak-ada", "spinner": "star"}})
        self.assertEqual((design.get("border"), design.get("spinner")), ("rounded", "star"))
        self.assertIsNone(design.apply_preset("tidak-ada"))
        self.assertFalse(design.set("border", "x"))

    def test_ascii_fallback_without_utf8(self):
        with mock.patch.object(envinfo, "utf8_ok", return_value=False):
            self.assertEqual(design.border()["tl"], "+")
            self.assertEqual(design.icon_set(), "ascii")
            self.assertEqual(design.spinner()[0][0], "-")
            self.assertEqual(design.prompt_glyph(), "> ")

    def test_ui_follows_design_choices(self):
        T.set_depth(0)
        design.set("border", "double")
        out = []
        u = ui.UI()
        u.w = out.append
        u.table(["a"], [["1"]], None)
        self.assertIn("╔", "".join(out))
        design.set("icons", "ascii")
        out.clear()
        u.ok("selesai")
        self.assertEqual("".join(out), "+ selesai\n")


class SyntaxColorsFollowTheme(Base):
    def test_code_colors_change_with_theme(self):
        T.set_depth(24)
        T.set_theme("dracula")
        a = highlight.render("def f(x):\n    return 'a'", "python")
        T.set_theme("nord")
        b = highlight.render("def f(x):\n    return 'a'", "python")
        self.assertNotEqual(a, b)
        self.assertEqual([ui.strip_ansi(x) for x in a], ["def f(x):", "    return 'a'"])
        T.set_depth(16)
        self.assertTrue(highlight.render("x = 1", "python"))


if __name__ == "__main__":
    unittest.main()
