import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import cx
from cx import design, envinfo, themes as T
from . import ROOT

TERMUX = {"TERMUX_VERSION": "0.118.1", "PREFIX": "/data/data/com.termux/files/usr", "TERM": "xterm-256color"}


class Detection(unittest.TestCase):
    def test_termux_and_android(self):
        self.assertTrue(envinfo.is_termux(TERMUX))
        self.assertTrue(envinfo.is_android(TERMUX))
        self.assertFalse(envinfo.is_termux({"TERM": "xterm"}))
        self.assertEqual(T.detect_depth(TERMUX, True), 24)
        with mock.patch.dict(os.environ, TERMUX, clear=False):
            self.assertEqual(envinfo.platform_label(), "Termux (Android)")

    def test_temp_dir_honours_tmpdir(self):
        d = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"TMPDIR": d}):
            import tempfile as tf
            tf.tempdir = None
            self.assertEqual(envinfo.tmpdir(), d)
            tf.tempdir = None

    def test_no_hardcoded_tmp_in_shipped_scripts(self):
        import glob
        for p in glob.glob(os.path.join(ROOT, "skills", "*", "scripts", "*")) + glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")):
            with open(p, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if "/tmp/" in line and "TMPDIR" not in line:
                        self.fail(f"{p}:{n} memakai /tmp langsung (tidak ada di Termux): {line.strip()[:80]}")

    def test_compact_preset_for_phones(self):
        p = design.PRESETS["termux"]
        self.assertEqual((p["density"], p["prompt"], p["status"]), ("compact", "chevron", "minimal"))


class Installer(unittest.TestCase):
    def run_install(self, extra_env):
        d = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if not k.startswith("CODINX_")}
        env.update(HOME=os.path.join(d, "home"), CODINX_INSTALL_DIR=os.path.join(d, "app"), CODINX_BIN_DIR=os.path.join(d, "bin"))
        env.update(extra_env)
        os.makedirs(env["HOME"])
        r = subprocess.run(["bash", os.path.join(ROOT, "install.sh")], capture_output=True, text=True, env=env, timeout=120)
        return d, env, r

    def test_installs_wrapper_that_runs_without_usr_bin_env(self):
        d, env, r = self.run_install({})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        wrapper = os.path.join(d, "bin", "codinx")
        self.assertTrue(os.stat(wrapper).st_mode & stat.S_IXUSR)
        with open(wrapper) as f:
            first, second = f.read().splitlines()[:2]
        self.assertTrue(first.startswith("#!/") and os.path.exists(first[2:]), first)       # shebang ke sh nyata, bukan /usr/bin/env
        self.assertFalse(os.path.islink(wrapper))
        self.assertIn("exec python3", second)
        out = subprocess.run([wrapper, "--version"], capture_output=True, text=True, env=env)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(f"CodinX {cx.__version__}", out.stdout)

    def test_installed_copy_has_vendor_and_data(self):
        d, env, r = self.run_install({})
        app = os.path.join(d, "app")
        for rel in ("cx/vendor/pygments/__init__.py", "cx/vendor/zoneinfo/Asia/Jakarta", "data/models.json", "skills/web-check/SKILL.md", "api.example.py"):
            self.assertTrue(os.path.exists(os.path.join(app, rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(app, "api.py")))                       # kunci milik pengguna tidak pernah dibuat/dibawa


class Guard(unittest.TestCase):
    def test_root_is_optional_by_default_and_enforceable(self):
        from cx import guard
        guard.check()                                                   # tidak boleh keluar (tanpa CODINX_REQUIRE_ROOT)
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            with mock.patch.dict(os.environ, {"CODINX_REQUIRE_ROOT": "1"}):
                with self.assertRaises(SystemExit):
                    guard.check()


if __name__ == "__main__":
    unittest.main()
