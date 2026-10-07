import json
import os
import subprocess
import sys
import tempfile
import unittest
import zoneinfo
from datetime import datetime
from unittest import mock

from cx import config, geo, mdview, perms, themes as T, tools, ui, vault, vendored
from cx.session import Session
from . import ROOT
from .helpers import read


class MdView(unittest.TestCase):
    DOC = "# Judul\nParagraf **tebal** dan `kode` serta [tautan](https://a.b/c) yang cukup panjang supaya terbungkus.\n\n- satu\n  - bersarang\n1. a\n2. b\n\n> kutipan\n\n```python\nx = 1\n```\n\n| A | B |\n|---|---|\n| 1 | dua |\n\n---\n"

    def setUp(self):
        self.old = T.depth()
        T.set_depth(0)

    def tearDown(self):
        T.set_depth(self.old)

    def test_structure(self):
        lines = mdview.render(self.DOC, width=40)
        text = "\n".join(lines)
        for needle in ("JUDUL", "━", "• satu", "  • bersarang", "1. a", "2. b", "┃ kutipan", "x = 1", "│ A", "dua", "https://a.b/c"):
            self.assertIn(needle, text)

    def test_wraps_to_requested_width(self):
        for ln in mdview.render(self.DOC, width=30):
            self.assertLessEqual(ui.strip_ansi(ln).__len__(), 34, ln)

    def test_falls_back_when_markdown_it_is_missing(self):
        with mock.patch.object(vendored, "load", return_value=None):
            self.assertIsNone(mdview.render(self.DOC))
            u = ui.UI()
            buf = []
            u.w = buf.append
            mdview.show(u, "# Judul\n- a\n")
            self.assertIn("JUDUL", "".join(buf))

    def test_all_bundled_docs_render(self):
        d = os.path.join(ROOT, "docs")
        for f in sorted(os.listdir(d)):
            if f.endswith(".md"):
                lines = mdview.render(read(os.path.join(d, f)), width=70)
                self.assertTrue(lines and any(l.strip() for l in lines), f)


class VendoredLibs(unittest.TestCase):
    def test_libraries_load(self):
        for name in ("yaml", "tabulate", "markdown_it", "mdurl"):
            self.assertIsNotNone(vendored.load(name), name)
        self.assertEqual(vendored.load("yaml").safe_load("a: [1, 2]"), {"a": [1, 2]})
        self.assertIn("a", vendored.load("tabulate").tabulate([[1]], headers=["a"]))

    def test_licenses_ship_with_vendor(self):
        lic = os.path.join(ROOT, "cx", "vendor", "licenses")
        for n in ("markdown_it", "mdurl", "tabulate", "yaml"):
            self.assertTrue(os.path.getsize(os.path.join(lic, n + "-LICENSE")) > 100, n)
        meta = json.loads(read(os.path.join(ROOT, "cx", "vendor", "VENDOR.json")))
        self.assertGreater(meta["zoneinfo"]["files"], 400)

    def test_yamlpp_script_converts_both_ways(self):
        script = os.path.join(ROOT, "skills", "json-yaml-tools", "scripts", "yamlpp.py")
        f = os.path.join(tempfile.mkdtemp(), "d.json")
        with open(f, "w") as fh:
            fh.write('{"nama": "budi", "tag": ["a", "b"]}')
        y = subprocess.run([sys.executable, script, f], capture_output=True, text=True)
        self.assertEqual(y.returncode, 0)
        self.assertIn("nama: budi", y.stdout)
        g = os.path.join(os.path.dirname(f), "d.yaml")
        with open(g, "w") as fh:
            fh.write(y.stdout)
        j = subprocess.run([sys.executable, script, g], capture_output=True, text=True)
        self.assertEqual(json.loads(j.stdout), {"nama": "budi", "tag": ["a", "b"]})


class TableExport(unittest.TestCase):
    def setUp(self):
        self.cwd = os.path.realpath(tempfile.mkdtemp())
        cfg = {"tool_policy": {}, "permission": {}}
        u = ui.UI()
        u.quiet = True
        self.ctx = tools.Ctx(self.cwd, perms.Perms(cfg), u, Session(self.cwd), cfg)

    def test_extra_formats(self):
        for fn, needle in (("t.html", "<table>"), ("t.rst", "==="), ("t.txt", "│"), ("t.tex", "tabular"), ("t.yaml", "- a: 1")):
            out = tools.run(self.ctx, "table", {"columns": ["a", "b"], "rows": [[1, "x"]], "save_as": fn})
            self.assertIn("Disimpan", out, fn)
            self.assertIn(needle, read(os.path.join(self.cwd, fn)), fn)


class OfflineTimeZones(unittest.TestCase):
    def test_vendored_zone_used_when_system_tzdata_is_missing(self):
        real = zoneinfo.ZoneInfo

        class NoSystem(real):
            def __new__(cls, key):
                raise zoneinfo.ZoneInfoNotFoundError(key)
        with mock.patch.object(zoneinfo, "ZoneInfo", NoSystem):
            for name, offset in (("Asia/Jakarta", 7), ("Asia/Jayapura", 9), ("Asia/Makassar", 8)):
                z = geo.zone(name)
                self.assertEqual(datetime.now(z).utcoffset().total_seconds(), offset * 3600, name)
            for bad in ("../../etc/passwd", "Mars/Olympus", "", "a/../b"):
                with self.assertRaises(Exception):
                    geo.zone(bad)

    def test_now_and_next_reset_work_through_vendored_zones(self):
        real = zoneinfo.ZoneInfo

        class NoSystem(real):
            def __new__(cls, key):
                raise zoneinfo.ZoneInfoNotFoundError(key)
        with mock.patch.object(zoneinfo, "ZoneInfo", NoSystem):
            nxt = geo.next_reset({"timezone": "Asia/Jayapura"})
            self.assertEqual((nxt.hour, nxt.minute, nxt.utcoffset().total_seconds()), (0, 0, 9 * 3600))


class VaultOnAndroid(unittest.TestCase):
    def test_install_id_is_created_once_with_private_permissions(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(vault, "_home_dir", return_value=d):
            a = vault._install_id()
            b = vault._install_id()
            self.assertEqual(a, b)
            self.assertEqual(len(a), 32)
            self.assertEqual(os.stat(os.path.join(d, ".machine-id")).st_mode & 0o777, 0o600)

    def test_encrypt_uses_install_id_without_machine_id_and_keeps_legacy_keys_readable(self):
        d = tempfile.mkdtemp()
        real_open = open

        def fake_open(path, *a, **k):
            if str(path) in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                raise FileNotFoundError(path)
            return real_open(path, *a, **k)
        with mock.patch.object(vault, "_home_dir", return_value=d), mock.patch("builtins.open", fake_open):
            self.assertEqual(len(vault._machine_secrets()), 2)                  # install-id + warisan nodename
            blob = vault.encrypt("sk-rahasia")
            self.assertEqual(vault.decrypt(blob), "sk-rahasia")
            legacy = vault._keys(os.uname().nodename.encode())                   # kunci lama (nodename) tetap bisa dibuka
            import base64, hashlib, hmac
            raw = b"sk-lama"
            nonce = os.urandom(16)
            ct = bytes(x ^ y for x, y in zip(raw, vault._stream(legacy[0], nonce, len(raw))))
            tag = hmac.new(legacy[1], vault.MAGIC + nonce + ct, hashlib.sha256).digest()
            self.assertEqual(vault.decrypt(base64.b64encode(vault.MAGIC + nonce + ct + tag)), "sk-lama")


if __name__ == "__main__":
    unittest.main()
