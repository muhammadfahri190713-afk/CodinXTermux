"""Interactive REPL, slash commands, connect wizard, model picker, permission centre."""
import getpass
import glob as _glob
import json
import os
import re
import shlex
import subprocess
import sys
import time

from . import __version__, agents, api, caps, config, design, doctor, envinfo, fsutil, geo, highlight, hooks, lineedit, log, mcp, memory, menu, skills, suggest, tiers, tools
from . import themes as T
from .agent import Agent
from .perms import DEFAULT_POLICY, POLICY_CYCLE, Perms
from .session import Session
from .themes import c
from .ui import UI

try:
    import readline
except ImportError:
    readline = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, ".seed")
PKG_COMMANDS = os.path.join(ROOT, "commands")

COMMANDS = [
    ("/help", "daftar perintah"), ("/new", "sesi baru"), ("/sessions", "lanjutkan sesi lama"),
    ("/skills", "daftar skill + jalankan (pilih nomor)"), ("/skill", "jalankan skill: /skill <nama> [tugas]  ·  atau /<nama>  ·  atau $nama"),
    ("/agents", "daftar sub-agent khusus"), ("/mcp", "server MCP: status / reload"), ("/hooks", "daftar hooks aktif"),
    ("/diff", "git diff berwarna  (/diff --stat)"), ("/debug", "on | off | tail — log debug"),
    ("/models", "pilih model  (/models pro · /models claude)"), ("/connect", "atur endpoint + API key"),
    ("/doctor", "diagnosa proxy: riwayat percakapan + tool (otomatis)"), ("/toolmode", "auto|native|text|none"),
    ("/historymode", "auto|native|flat"), ("/remember", "simpan sesuatu ke memori"), ("/forget", "hapus memori (id | all)"),
    ("/memory", "lihat/cari/tambah/hapus memori"), ("/permissions", "pengaturan izin tool (web, kamera, terminal…)"),
    ("/tier", "lihat/ubah paket FREE·PRO·MAX"), ("/status", "paket, Dinar, mode, konteks"), ("/plan", "mode plan (read-only)"),
    ("/build", "mode build (bisa edit)"), ("/auto", "auto-izinkan semua (hard-deny tetap)"), ("/compact", "ringkas konteks"),
    ("/undo", "batalkan giliran terakhir"), ("/redo", "ulangi yang di-undo"), ("/init", "buat AGENTS.md"),
    ("/theme", "pilih tema (pratinjau langsung) · auto|dark|light|test"), ("/design", "preset desain: opencode · claude · codex · retro · neon…"),
    ("/banner", "gaya banner"), ("/border", "gaya garis/tabel"), ("/spinner", "gaya animasi tunggu"), ("/icons", "set ikon: unicode · ascii · nerd · emoji"),
    ("/prompt", "gaya prompt"), ("/gutter", "penanda kiri jawaban"), ("/density", "kerapatan tampilan (ringkas untuk ponsel)"),
    ("/footer", "gaya baris status"), ("/colors", "uji warna & kemampuan terminal"), ("/docs", "baca dokumentasi di terminal"),
    ("/view", "tampilkan file Markdown/kode"), ("/details", "tampil/sembunyi detail tool"), ("/thinking", "tampil/sembunyi proses berpikir"),
    ("/export", "simpan percakapan ke .md"), ("/share", "ekspor lokal untuk dibagikan"),
    ("/location", "provinsi + zona waktu (reset Dinar)"), ("/clear", "bersihkan layar"), ("/exit", "keluar"),
]
ALIASES = {"/quit": "/exit", "/q": "/exit", "/izin": "/permissions", "/perm": "/permissions", "/resume": "/sessions",
           "/continue": "/sessions", "/clear-session": "/new", "/usage": "/status", "/model": "/models", "/summarize": "/compact",
           "/themes": "/theme", "/session": "/sessions", "/diagnosa": "/doctor", "/cek": "/doctor", "/ingat": "/remember",
           "/lupa": "/forget", "/tools": "/toolmode", "/tema": "/theme", "/desain": "/design", "/warna": "/colors",
           "/doc": "/docs", "/lihat": "/view", "/status-style": "/footer"}

PERM_ROWS = [
    ("bash", "Jalankan perintah terminal"), ("edit", "Tulis / ubah file"), ("read", "Baca file"),
    ("webfetch", "Akses web / internet"), ("localhost", "Akses localhost:3000 dkk"), ("camera", "Kamera (foto)"),
    ("task", "Sub-agent"), ("memory", "Memori jangka panjang"), ("skill", "Skills"), ("mcp", "Server MCP eksternal (semua tool MCP)"),
    ("external_directory", "File di luar folder proyek"),
]
POLICY_LABEL = {"default": "○ bawaan", "ask": "? selalu tanya", "allow": "✓ selalu izinkan", "deny": "✗ tolak", "off": "⊘ mati"}


def _rl(s):
    return re.sub(r"(\033\[[0-9;]*m)", "\001\\1\002", s)


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ui = UI()
        self.ui.show_thinking = cfg.get("show_thinking", False)
        self.ui.show_details = cfg.get("show_details", True)
        design.load(cfg)
        self._theme_pref = cfg.get("theme", "auto")
        self._auto = None
        T.set_theme(self._resolve_theme(self._theme_pref))
        self.cwd = os.getcwd()
        self.key = config.get_key()
        self.perms = Perms(cfg)
        self.session = Session(self.cwd)
        self.ctx = tools.Ctx(self.cwd, self.perms, self.ui, self.session, cfg)
        self.ctx.mode = cfg.get("agent", "build") if cfg.get("agent") in ("build", "plan") else "build"
        self.agent = Agent(self)
        self.ctx.subagent_fn = self.agent.subagent
        self._probed = set()
        self.editor = lineedit.Editor(self._completer(), history_file=config.HISTORY)
        mcp.manager.load(self.cwd, cfg)

    # ------------------------------------------------------------ input aman (tidak pernah menggantung di non-TTY)
    @staticmethod
    def _ask(prompt):
        if not sys.stdin.isatty():
            raise EOFError("stdin bukan terminal")
        return input(prompt)

    @staticmethod
    def _ask_secret(prompt):
        if not sys.stdin.isatty():
            raise EOFError("stdin bukan terminal")
        return getpass.getpass(prompt)

    # ------------------------------------------------------------ connection
    def _import_seed(self):
        try:
            with open(SEED) as f:
                d = json.load(f)
            if d.get("api_key"):
                config.set_key(d["api_key"])
                self.key = d["api_key"]
            if d.get("base_url"):
                self.cfg["base_url"] = config.normalize_url(d["base_url"])
            config.save(self.cfg)
            size = os.path.getsize(SEED)
            with open(SEED, "r+b") as f:       # timpa lalu hapus: tidak ada kunci plaintext tersisa
                f.write(os.urandom(size))
            os.remove(SEED)
            self.ui.ok("Kunci API diimpor ke brankas terenkripsi (~/.codinx/.key.enc) dan file seed dihapus.")
            return True
        except (OSError, ValueError):
            return False

    def ensure_connected(self):
        if self.key and self.cfg.get("base_url"):
            return True
        if os.path.isfile(SEED) and self._import_seed():
            return True
        self.ui.warn("Belum terhubung ke endpoint.")
        if not sys.stdin.isatty():
            self.ui.err("API key belum ada: jalankan `cp api.example.py api.py`, isi API_KEY, atau set CODINX_API_KEY, lalu ulangi.")
            return False
        return self.connect_wizard()

    def connect_wizard(self):
        if config.env("CODINX_API_KEY") or config.env("CODINX_BASE_URL"):
            self.ui.warn("api.py / environment aktif dan menimpa pengaturan koneksi. Edit api.py untuk mengganti key.")
        if not sys.stdin.isatty():
            self.ui.err("`connect` butuh terminal interaktif. Alternatif: isi API_KEY di api.py.")
            return False
        cur = self.cfg.get("base_url") or config.DEFAULT_BASE_URL
        try:
            url = self._ask(c("accent2", "  Endpoint ") + c("muted", f"[{cur}] › ")).strip() or cur
            key = self._ask_secret(c("accent2", "  API key ") + c("muted", "(tersembunyi, kosong = tetap) › ")).strip()
        except (EOFError, KeyboardInterrupt):
            self.ui.p()
            return False
        self.cfg["base_url"] = config.normalize_url(url)
        if key:
            config.set_key(key)
            self.key = key
        config.save(self.cfg)
        if not self.key:
            self.ui.err("API key kosong.")
            return False
        try:
            ids = api.list_models(self.cfg, self.key)
            self.ui.ok(f"Terhubung ke {self.cfg['base_url']} · {len(ids)} model tersedia di proxy")
        except api.ApiError as e:
            self.ui.warn(f"Tersimpan, tapi daftar model gagal diambil: {str(e)[:160]}")
        return True

    # ------------------------------------------------------------ helpers
    def set_session(self, s):
        self.session = s
        self.ctx.session = s
        self.ctx.backups = {}

    def save_cfg(self):
        config.save(self.cfg)

    def _resolve_theme(self, pref):
        """Nama tema nyata dari preferensi (auto/dark/light/nama). Deteksi latar hanya sekali."""
        if pref == "auto":
            if self._auto is None:
                self._auto = T.resolve("auto")
            return self._auto
        return T.resolve(pref, detect=False)

    def footer(self):
        st = tiers.status(self.cfg)
        lim = max(int(self.cfg.get("context_limit", 128000)), 1)
        pct = min(100, int(self.session.last_prompt_tokens * 100 / lim))
        build = self.ctx.mode == "build"
        cost = "uji coba · gratis" if st["trial"] else (f"Dinar {st['dinar']}/{st['limit']}" if st["tier"] == "FREE" else f"paket {st['tier']}")
        tags = []
        tm, hm = self.agent.modes()
        if hm == "flat":
            tags.append("riwayat:flat")
        if tm != "native":
            tags.append({"text": "tool:teks", "none": "tanpa-tool"}.get(tm, tm))
        if self.perms.auto:
            tags.append("AUTO")
        ctx_role = "ok" if pct < 60 else ("warn" if pct < 85 else "err")
        style = design.get("status")
        mode_c = c("accent" if build else "warn", self.ctx.mode, bold=True)
        model_c = c("accent2", self.cfg["model"])
        ctx_c = c(ctx_role, f"ctx {pct}%")
        if style == "minimal":
            return "  " + model_c + c("border", " · ") + ctx_c
        if style == "pills":
            parts = [T.pill("accent" if build else "warn", self.ctx.mode), T.pill("accent2", self.cfg["model"]), c("muted", cost), ctx_c]
            return "  " + " ".join(parts + [c("warn", t) for t in tags])
        sep = c("border", " │ " if style == "bar" else " · ")
        parts = [mode_c, model_c, c("ok" if st["trial"] else "info", cost), ctx_c] + [c("warn", t) for t in tags]
        return "  " + sep.join(parts)

    def prompt(self, plain=False):
        glyph = c("user" if self.ctx.mode == "build" else "warn", design.prompt_glyph(), bold=True)
        return glyph if plain else _rl(glyph)

    def custom_commands(self):
        found = {}
        for d in (PKG_COMMANDS, os.path.join(config.HOME, "commands"), os.path.join(self.cwd, ".codinx", "commands")):
            if not os.path.isdir(d):
                continue
            for f in sorted(os.listdir(d)):
                if f.endswith(".md"):
                    try:
                        meta, body = skills.parse(fsutil.read_text(os.path.join(d, f)))
                    except OSError:
                        continue
                    found["/" + f[:-3]] = (meta.get("description", ""), body.strip())
        return found

    def all_command_names(self):
        return sorted({x[0] for x in COMMANDS} | set(self.custom_commands()))

    def setup_readline(self):
        if not readline:
            return
        try:
            readline.read_history_file(config.HISTORY)
        except OSError:
            pass
        readline.set_history_length(1000)
        readline.set_completer_delims(" \t\n")

        def completer(text, state):
            buf = readline.get_line_buffer()
            if buf.startswith("/") and " " not in buf:
                opts = [x for x in self.all_command_names() if x.startswith(buf)]
            elif text.startswith("@"):
                opts = ["@" + p + ("/" if os.path.isdir(p) else "") for p in _glob.glob(os.path.expanduser(text[1:]) + "*")]
            else:
                opts = []
            return opts[state] if state < len(opts) else None
        readline.set_completer(completer)
        readline.parse_and_bind("tab: complete")

    def save_history(self):
        if self.editor.used:                 # riwayat dikelola Editor (file yang sama); jangan ditimpa readline
            return
        if readline:
            try:
                readline.write_history_file(config.HISTORY)
                os.chmod(config.HISTORY, 0o600)
            except OSError:
                pass

    # ------------------------------------------------------------ input expansion
    def attach_mentions(self, text):
        extra = []
        for m in re.finditer(r"(?<!\S)@([\w./~\-]+)", text):
            p = self.ctx.path(m.group(1))
            if os.path.isfile(p):
                try:
                    body = fsutil.read_text(p)[:20000]
                    extra.append(f'<file path="{p}">\n{body}\n</file>')
                except OSError:
                    pass
            elif os.path.isdir(p):
                extra.append(f'<dir path="{p}">\n' + "\n".join(sorted(os.listdir(p))[:200]) + "\n</dir>")
        return text + ("\n\n" + "\n".join(extra) if extra else "")

    def expand_template(self, tpl, args):
        try:
            parts = shlex.split(args)
        except ValueError:
            parts = args.split()
        tpl = tpl.replace("$ARGUMENTS", args)
        for i in range(9, 0, -1):
            tpl = tpl.replace(f"${i}", parts[i - 1] if len(parts) >= i else "")
        tpl = re.sub(r"!`([^`]+)`", lambda m: "\n" + tools.t_bash(self.ctx, m.group(1)) + "\n", tpl)
        return self.attach_mentions(tpl)

    def shell(self, cmd):
        try:
            r = subprocess.run(["bash", "-c", cmd], cwd=self.cwd, capture_output=True, text=True, timeout=120)
            out = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            out = "(timeout 120s)"
        self.ui.p(c("muted", out[:6000] or "(tanpa output)"))
        self.session.messages.append({"role": "user", "content": f"Saya menjalankan `{cmd}` di terminal. Outputnya:\n```\n{out[:8000]}\n```"})
        self.session.messages.append({"role": "assistant", "content": "Dicatat."})
        self.session.save()

    def expand_skill_mentions(self, text):
        """$nama-skill di dalam pesan -> isi SKILL.md ikut dikirim (tanpa bergantung pada kemampuan tool model)."""
        if "[SKILL AKTIF:" in text:
            return text
        found = []
        for m in re.finditer(r"(?<![\w$])\$([A-Za-z][\w-]*)", text):
            sk = skills.resolve(m.group(1), self.cwd, exact=True)
            if sk and sk["name"] not in found:
                found.append(sk["name"])
        if not found:
            return text
        self.ui.p(c("muted", "  ▸ skill dimuat: " + ", ".join(found)))
        return text + "\n\n" + "\n\n".join(f"[SKILL AKTIF: {n}]\n{skills.load(n, self.cwd)}" for n in found)

    def maybe_probe(self):
        """Diagnosa kemampuan proxy/model sekali per model (riwayat + tool) agar skills & memori pasti jalan."""
        model = self.cfg["model"]
        if model in self._probed or not self.cfg.get("auto_probe", True):
            return
        self._probed.add(model)
        if self.cfg.get("tool_mode", "auto") != "auto" and self.cfg.get("history_mode", "auto") != "auto":
            return
        if caps.get(model) or not tiers.can_use_model(self.cfg, model)[0]:
            return
        self.ui.info("Memeriksa kemampuan model (sekali saja per model)…")
        self.ui.spin_start("diagnosa")
        try:
            res = doctor.run(self)
        except api.ApiError as e:
            self.ui.spin_stop()
            self.ui.warn(f"Diagnosa dilewati: {str(e)[:120]}")
            return
        finally:
            self.ui.spin_stop()
        self.ui.p(c("muted", "  " + doctor.summary(res)))

    def submit(self, text, attach=True):
        h = hooks.run("UserPromptSubmit", self.cwd, self.cfg, {"prompt": text})
        if h["blocked"]:
            self.ui.warn("Prompt diblokir oleh hook: " + h["message"][:200])
            return ""
        text = self.expand_skill_mentions(text)
        for fact in memory.auto_capture(text, self.cwd):
            self.ui.p(c("muted", "  💾 diingat: ") + c("text", fact))
        if h["output"]:
            text += "\n\n[konteks dari hook]\n" + h["output"]
        final = self.agent.turn(self.attach_mentions(text) if attach else text)
        s = hooks.run("Stop", self.cwd, self.cfg, {"final": (final or "")[:2000], "session": self.session.id})
        if s["message"]:
            self.ui.info("hook Stop: " + s["message"][:160])
        return final

    def run_turn(self, text, attach=True):
        if not self.ensure_connected():
            return
        self.maybe_probe()
        self.submit(text, attach)
        if design.get("density") != "compact":
            self.ui.p()

    def run_skill(self, name, args=""):
        sk = skills.resolve(name, self.cwd)
        if not sk:
            import difflib
            near = difflib.get_close_matches(name, list(skills.discover(self.cwd)), 3)
            return self.ui.err(f"Skill '{name}' tidak ada." + (" Maksud kamu: " + ", ".join(near) + "?" if near else " Lihat /skills"))
        body = skills.load(sk["name"], self.cwd)
        task = self.attach_mentions(args.strip()) if args.strip() else "Terapkan skill ini pada konteks/percakapan saat ini dan kerjakan hingga selesai."
        self.ui.p(c("accent2", "  ▸ skill: ") + c("text", sk["name"], bold=True) + c("muted", " — " + sk["description"][:60]))
        self.run_turn(f"[SKILL AKTIF: {sk['name']}]\n{body}\n\n[TUGAS USER]\n{task}", attach=False)

    # ------------------------------------------------------------ REPL
    def read_line(self):
        self.ui.p(self.footer())
        fancy = self.editor.available()
        line = self.editor.read(self.prompt(plain=True)) if fancy else input(self.prompt())
        while line.endswith("\\"):
            cont = c("muted", "… ")
            line = line[:-1] + "\n" + (self.editor.read(cont) if fancy else input(_rl(cont)))
        return line

    def repl(self):
        self.setup_readline()
        ok = self.ensure_connected()
        prev = Session.latest_for(self.cwd)
        extra = ""
        if prev and ok:
            self.set_session(prev)
            extra = f"sesi dilanjutkan: {prev.title[:40] or prev.id} ({len(prev.messages)} pesan) · /new untuk baru"
        self.ui.banner(self.cfg["model"], self.ctx.mode, tiers.plan_label(self.cfg), self.cwd, extra)
        leak = config.env_leak_warning()
        if leak:
            self.ui.warn(leak)
        if ok:
            m = tiers.can_use_model(self.cfg, self.cfg["model"])
            if not m[0]:
                self.ui.warn(m[2])
        while True:
            try:
                line = self.read_line()
            except EOFError:
                break
            except KeyboardInterrupt:
                self.ui.p("\n" + c("muted", "  (Ctrl-C) ketik /exit atau Ctrl-D untuk keluar"))
                continue
            line = line.strip()
            if not line:
                continue
            try:
                if line.startswith("/"):
                    if self.slash(line) == "exit":
                        break
                elif line.startswith("!"):
                    self.shell(line[1:].strip())
                else:
                    self.run_turn(line)
            except KeyboardInterrupt:
                self.ui.p("\n" + c("warn", "  dihentikan"))
        self.session.save()
        self.save_history()
        self.ui.p(c("muted", "  sampai jumpa 👋"))

    # ------------------------------------------------------------ slash commands
    def slash(self, line):
        name, _, arg = line.partition(" ")
        name = ALIASES.get(name.lower(), name.lower())
        arg = arg.strip()
        fn = getattr(self, "cmd_" + name[1:].replace("-", "_"), None)
        if fn:
            return fn(arg)
        custom = self.custom_commands().get(name)
        if custom:
            return self.run_turn(self.expand_template(custom[1], arg), attach=False)
        sk = skills.resolve(name[1:], self.cwd)
        if sk:
            return self.run_skill(sk["name"], arg)
        self.ui.err(f"Perintah {name} tidak dikenal. Ketik /help")

    def cmd_help(self, arg):
        rows = [[n, d] for n, d in COMMANDS]
        self.ui.table(["perintah", "fungsi"], rows, "CodinX — perintah")
        cc = self.custom_commands()
        if cc:
            self.ui.table(["custom", "fungsi"], [[n, d] for n, (d, _) in cc.items()], "Perintah custom")
        self.ui.p(c("muted", "  @file lampirkan file · !perintah jalankan shell · akhiri baris dengan \\ untuk multi-baris · Ctrl-C hentikan"))

    def cmd_exit(self, arg):
        return "exit"

    def cmd_clear(self, arg):
        sys.stdout.write("\033[2J\033[H")
        self.ui.banner(self.cfg["model"], self.ctx.mode, tiers.plan_label(self.cfg), self.cwd)

    def cmd_new(self, arg):
        self.session.save()
        self.set_session(Session(self.cwd))
        self.ui.ok("Sesi baru dimulai.")

    def cmd_connect(self, arg):
        self.connect_wizard()

    def cmd_status(self, arg):
        st = tiers.status(self.cfg)
        g = geo.lookup()
        rows = [["model", self.cfg["model"]], ["paket", tiers.plan_label(self.cfg)], ["mode", self.ctx.mode],
                ["endpoint", self.cfg["base_url"]], ["sumber API key", config.key_source()], ["folder", self.cwd], ["sesi", f"{self.session.id} ({len(self.session.messages)} pesan)"],
                ["token konteks", f"{self.session.last_prompt_tokens}/{self.cfg.get('context_limit')}"],
                ["request hari ini", st["requests"]]]
        tm, hm = self.agent.modes()
        rows.append(["mode tool", tm + (" (auto)" if self.cfg.get("tool_mode") == "auto" else "")])
        rows.append(["mode riwayat", hm + (" (auto)" if self.cfg.get("history_mode") == "auto" else "")])
        rows.append(["id percakapan", self.session.id])
        rows.append(["id respons server", self.session.remote_id or "-"])
        if self.session.remote_conv:
            rows.append(["id percakapan server", self.session.remote_conv])
        if st["trial"]:
            rows.append(["biaya", "GRATIS — mode uji coba (Dinar tidak dipotong). Matikan: CODINX_TRIAL=0"])
        elif st["tier"] == "FREE":
            rows.append(["Dinar", f"{st['dinar']}/{st['limit']}  (reset 00:00 dalam {st['reset_in']})"])
        rows.append(["zona waktu", f"{geo.tz_name(self.cfg)}" + (f" · {g.get('province')}" if g.get("province") else "")])
        if st["trials"]:
            rows.append(["trial terpakai", ", ".join(f"{k}:{v}" for k, v in st["trials"].items())])
        self.ui.table(["", ""], rows, "Status")

    def cmd_location(self, arg):
        g = geo.lookup(force=(arg == "refresh"))
        rows = [["provinsi", g.get("province") or "-"], ["kota", g.get("city") or "-"], ["negara", g.get("country") or "-"],
                ["zona waktu", geo.tz_name(self.cfg)], ["sumber", g.get("source")],
                ["reset berikutnya", geo.next_reset(self.cfg).strftime("%Y-%m-%d %H:%M %Z")], ["sisa", geo.remaining_str(self.cfg)]]
        self.ui.table(["", ""], rows, "Lokasi (untuk reset Dinar jam 00:00)")
        self.ui.p(c("muted", "  Lokasi dari IP publik via ipwho.is (di-cache 24 jam). Paksa zona waktu: edit \"timezone\" di config.json. /location refresh = ambil ulang."))

    def cmd_tier(self, arg):
        if not arg:
            st = tiers.status(self.cfg)
            self.ui.info(f"Paket saat ini: {st['tier']}. Ganti: /tier free | pro | max")
            return
        if arg.lower() not in ("free", "pro", "max"):
            self.ui.err("Pilih: free | pro | max")
            return
        self.cfg["tier"] = arg.lower()
        self.save_cfg()
        self.ui.ok(f"Paket diubah ke {arg.upper()}.")
        if tiers.trial_mode(self.cfg):
            return self.ui.info("Mode uji coba aktif: semua model gratis, paket belum berpengaruh. Matikan dengan CODINX_TRIAL=0.")
        ok, _, msg = tiers.can_use_model(self.cfg, self.cfg["model"])
        if not ok:
            self.ui.warn(msg + " Pilih model lain dengan /models.")

    def cmd_plan(self, arg):
        self.ctx.mode = "plan"
        self.cfg["agent"] = "plan"
        self.save_cfg()
        self.ui.ok("Mode PLAN: read-only, tidak bisa mengubah file.")

    def cmd_build(self, arg):
        self.ctx.mode = "build"
        self.cfg["agent"] = "build"
        self.save_cfg()
        self.ui.ok("Mode BUILD: bisa membuat, mengedit, dan menjalankan.")

    def cmd_agent(self, arg):
        (self.cmd_plan if (arg == "plan" or (not arg and self.ctx.mode == "build")) else self.cmd_build)(arg)

    def cmd_auto(self, arg):
        self.perms.auto = not self.perms.auto
        (self.ui.warn if self.perms.auto else self.ui.ok)("AUTO " + ("AKTIF: semua izin 'tanya' dilewati (perintah destruktif tetap diblokir)." if self.perms.auto else "mati."))

    def cmd_details(self, arg):
        self.ui.show_details = not self.ui.show_details
        self.cfg["show_details"] = self.ui.show_details
        self.save_cfg()
        self.ui.ok("Detail tool: " + ("tampil" if self.ui.show_details else "disembunyikan"))

    def cmd_thinking(self, arg):
        self.ui.show_thinking = not self.ui.show_thinking
        self.cfg["show_thinking"] = self.ui.show_thinking
        self.save_cfg()
        self.ui.ok("Proses berpikir: " + ("tampil" if self.ui.show_thinking else "disembunyikan"))

    def cmd_compact(self, arg):
        if not self.ensure_connected():
            return
        self.ui.spin_start("meringkas")
        ok = self.agent.compact()
        self.ui.spin_stop()
        self.ui.ok("Konteks diringkas.") if ok else self.ui.warn("Tidak ada yang diringkas (terlalu pendek atau gagal).")

    def cmd_undo(self, arg):
        t = self.session.undo()
        if not t:
            return self.ui.warn("Tidak ada yang bisa di-undo.")
        self.ui.ok(f"Undo: {len(t['backups'])} file dikembalikan, pesan dihapus: \"{t['user'][:50]}\"")

    def cmd_redo(self, arg):
        t = self.session.redo()
        self.ui.ok("Redo berhasil.") if t else self.ui.warn("Tidak ada yang bisa di-redo.")

    def cmd_init(self, arg):
        self.run_turn("Analisis proyek ini (struktur, bahasa, cara build/test/run, konvensi) lalu buat atau perbarui file AGENTS.md "
                      "di root folder berisi panduan ringkas untuk agent coding. Jangan menulis rahasia.")

    def cmd_export(self, arg):
        name = arg or f"codinx-{self.session.id}.md"
        p = self.ctx.path(name)
        fsutil.write_text(p, self.session.export_md())
        self.ui.ok("Diekspor: " + p)

    def cmd_share(self, arg):
        d = os.path.join(config.HOME, "shares")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, self.session.id + ".md")
        fsutil.write_text(p, self.session.export_md())
        self.ui.ok("Ekspor lokal (tanpa upload): " + p)

    def cmd_skills(self, arg):
        sk = skills.discover(self.cwd)
        if arg:
            name, _, rest = arg.partition(" ")
            return self.run_skill(name, rest)
        if not sk:
            return self.ui.info("Belum ada skill. Letakkan di ~/.codinx/skills/<nama>/SKILL.md")
        names = list(sk)
        self.ui.table(["#", "skill", "deskripsi"], [[i + 1, n, sk[n]["description"][:62]] for i, n in enumerate(names)],
                      "Skills — jalankan: /skill <nama> <tugas>  ·  /<nama>  ·  $nama di pesan")
        try:
            a = self._ask(c("muted", "  nomor / nama skill untuk dijalankan (enter batal) › ")).strip()
            if not a:
                return
            name = names[int(a) - 1] if a.isdigit() and 1 <= int(a) <= len(names) else a
            task = self._ask(c("muted", "  tugas untuk skill ini (enter = pakai konteks saat ini) › ")).strip()
        except (EOFError, KeyboardInterrupt):
            return self.ui.p()
        self.run_skill(name, task)

    cmd_skill = cmd_skills

    def cmd_remember(self, arg):
        if not arg:
            return self.ui.info("Pakai: /remember <teks yang harus diingat>")
        self.ui.ok(f"Tersimpan di memori (id {memory.add(arg, 'global', self.cwd)}).")

    def cmd_forget(self, arg):
        if arg == "all":
            memory.clear()
            return self.ui.ok("Memori dikosongkan.")
        if arg.isdigit():
            return self.ui.ok(f"{memory.remove(arg)} ingatan dihapus.")
        self.ui.info("Pakai: /forget <id>  atau  /forget all")

    def cmd_memory(self, arg):
        sub, _, rest = arg.partition(" ")
        if sub == "add" and rest:
            return self.cmd_remember(rest)
        if sub in ("rm", "del", "hapus") and rest.strip().isdigit():
            return self.cmd_forget(rest.strip())
        if sub == "clear":
            return self.cmd_forget("all")
        items = memory.relevant(self.cwd, rest if sub in ("search", "cari") else "")
        if not items:
            return self.ui.info("Memori kosong. /remember <teks>, atau tulis \"ingat bahwa …\" / \"nama saya …\" di chat.")
        self.ui.table(["id", "lingkup", "isi"], [[i["id"], i["scope"], i["text"][:80]] for i in items], "Memori")

    def cmd_doctor(self, arg):
        if not self.ensure_connected():
            return
        if arg == "reset":
            caps.clear(self.cfg["model"])
            self.ui.ok("Hasil diagnosa model ini dihapus.")
        ok, _, msg = tiers.can_use_model(self.cfg, self.cfg["model"])
        if not ok:
            return self.ui.warn(msg)
        self.ui.spin_start("diagnosa proxy (±5-30 dtk)")
        try:
            res = doctor.run(self)
        except api.ApiError as e:
            self.ui.spin_stop()
            return self.ui.err(f"Diagnosa gagal: {str(e)[:200]}")
        finally:
            self.ui.spin_stop()
        h = {"native": "✓ normal — proxy meneruskan riwayat",
             "flat": "⚠ proxy TIDAK meneruskan riwayat → otomatis memakai mode flat (riwayat digabung jadi 1 pesan)",
             None: "✗ tidak bisa dipastikan (tetap native). Coba /historymode flat"}[res["history"]]
        t = {"native": "✓ native (function-calling OpenAI)",
             "text": "⚠ teks: proxy/model tanpa function-calling → tool lewat blok <tool_call> (tetap berfungsi penuh)",
             "none": "✗ model ini tidak bisa memakai tool → chat saja; skill lewat /skill, tindakan lewat !perintah. Coba /models lain"}[res["tools"]]
        self.ui.table(["", ""], [["model", res["model"]], ["riwayat percakapan", h], ["pemanggilan tool", t]] +
                      [["catatan", n] for n in res["notes"]], "Diagnosa CodinX")
        self.ui.p(c("muted", "  Disimpan untuk model ini dan dipakai otomatis. Ulang: /doctor · hapus: /doctor reset"))

    def _set_mode(self, key, allowed, arg, label):
        if arg in allowed:
            self.cfg[key] = arg
            self.save_cfg()
            self.ui.ok(f"{label}: {arg}")
        else:
            tm, hm = self.agent.modes()
            self.ui.info(f"{label} sekarang: {self.cfg.get(key)} (efektif: {tm if key == 'tool_mode' else hm}). Pilih: {' | '.join(allowed)}")

    def cmd_toolmode(self, arg):
        self._set_mode("tool_mode", ("auto", "native", "text", "none"), arg.lower(), "Mode tool")

    def cmd_historymode(self, arg):
        self._set_mode("history_mode", ("auto", "native", "flat"), arg.lower(), "Mode riwayat")

    def cmd_agents(self, arg):
        ag = agents.discover(self.cwd)
        if not ag:
            return self.ui.info("Belum ada sub-agent. Letakkan file .md di ~/.codinx/agents/")
        self.ui.table(["agent", "tool", "deskripsi"], [[n, ", ".join(a["tools"] or tools.SUBAGENT_TOOLS)[:34], a["description"][:50]] for n, a in ag.items()],
                      "Sub-agent (dipanggil model lewat tool task)")

    def cmd_mcp(self, arg):
        if arg == "reload":
            mcp.manager.reload(self.cwd, self.cfg)
        if not mcp.manager.specs:
            return self.ui.info("Belum ada server MCP. Isi ~/.codinx/mcp.json (contoh: examples/mcp.json).")
        mcp.manager.ensure_started(self.ui)
        self.ui.table(["server", "status", "tool"], mcp.manager.status(), "Server MCP")

    def cmd_hooks(self, arg):
        rows = [[ev, it.get("matcher", "*"), it["command"][:50]] for ev, items in hooks.load(self.cwd, self.cfg).items() for it in items]
        if not rows:
            return self.ui.info("Belum ada hooks. Isi ~/.codinx/hooks.json (contoh: examples/hooks.json).")
        self.ui.table(["event", "matcher", "perintah"], rows, "Hooks aktif")

    def cmd_diff(self, arg):
        try:
            r = subprocess.run(["git", "-C", self.cwd, "diff", "--no-color"] + shlex.split(arg), capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            return self.ui.err(f"git diff gagal: {e}")
        if r.returncode != 0:
            return self.ui.err((r.stderr or "bukan repo git").strip()[:200])
        if not r.stdout.strip():
            return self.ui.info("Tidak ada perubahan (git diff kosong).")
        self.ui.diff(r.stdout, limit=500, force=True)

    def cmd_debug(self, arg):
        if arg in ("on", "off"):
            log.set_enabled(arg == "on")
            return self.ui.ok(f"Log debug {arg}. File: {log.LOG_DIR}")
        if arg == "tail":
            for ln in log.tail(30):
                self.ui.p(c("muted", "  " + ln[:200]))
            return
        self.ui.info(f"Log debug: {'ON' if log.enabled() else 'off'}  ({log.LOG_DIR}). Pakai: /debug on | off | tail")

    # ------------------------------------------------------------ saran otomatis (completer)
    def _completer(self):
        return suggest.Completer(
            commands=lambda: COMMANDS,
            aliases=lambda: dict(ALIASES),
            customs=lambda: [(n, d) for n, (d, _) in self.custom_commands().items()],
            skills=lambda: [(n, s["description"]) for n, s in skills.discover(self.cwd).items()],
            args=self._arg_suggestions,
            cwd=lambda: self.cwd)

    def _arg_suggestions(self, cmd, word):
        """Saran argumen per perintah: [(nilai, deskripsi)]."""
        cmd = ALIASES.get(cmd, cmd)
        if cmd == "/theme":
            rows = [("auto", "deteksi latar terang/gelap"), ("dark", "tema gelap bawaan"), ("light", "tema terang bawaan"), ("test", "uji warna terminal"),
                    ("list", "daftar semua tema")]
            return rows + [(n, f"{T.info(n)['family']} · {'gelap' if T.info(n)['dark'] else 'terang'}") for n in T.names()]
        if cmd == "/design":
            return [(n, design.PRESET_NOTE.get(n, "preset kustom")) for n in list(design.PRESETS) + list(self.cfg.get("presets", {}))] + \
                   [("list", "daftar preset"), ("reset", "kembali ke bawaan"), ("show", "tampilkan pilihan saat ini"), ("save", "simpan preset: save <nama>")]
        for key, name in (("banner", "/banner"), ("border", "/border"), ("spinner", "/spinner"), ("icons", "/icons"), ("prompt", "/prompt"),
                          ("gutter", "/gutter"), ("density", "/density"), ("status", "/footer")):
            if cmd == name:
                return [(v, "") for v in design.CHOICES[key]]
        if cmd in ("/skill", "/skills"):
            return [(n, s["description"]) for n, s in skills.discover(self.cwd).items()]
        if cmd == "/models":
            return [("free", "model FREE"), ("pro", "model PRO"), ("max", "model MAX")] + [(m["id"], m["role"]) for m in tiers.catalog()]
        simple = {"/agent": ["build", "plan"], "/tier": ["free", "pro", "max"], "/toolmode": ["auto", "native", "text", "none"],
                  "/historymode": ["auto", "native", "flat"], "/debug": ["on", "off", "tail"], "/mcp": ["reload"], "/doctor": ["reset"],
                  "/memory": ["add", "rm", "clear", "search"]}
        if cmd in simple:
            return [(v, "") for v in simple[cmd]]
        if cmd in ("/docs", "/doc"):
            return [(n, "dokumentasi") for n in self._doc_names()]
        return []

    # ------------------------------------------------------------ tema & desain
    def _persist_design(self):
        self.cfg["design"] = design.dump()
        self.cfg["theme"] = self._theme_pref
        self.save_cfg()

    def _apply_theme_pref(self, pref):
        self._theme_pref = pref
        T.set_theme(self._resolve_theme(pref))

    def _theme_preview(self, _value=None):
        bd = design.border()
        lines = ["  " + c("heading", "▌ Judul", bold=True) + "  " + c("accent", "aksen") + " " + c("accent2", "aksen2") + "  " +
                 c("link", "tautan", underline=True) + "  " + c("code", "`kode`"),
                 "  " + c("ok", design.icon("ok") + " ok") + "  " + c("warn", design.icon("warn") + " peringatan") + "  " +
                 c("err", design.icon("err") + " galat") + "  " + c("info", design.icon("info") + " info") + "  " + c("muted", "redup"),
                 "  " + c("border", bd["tl"] + bd["h"] * 12 + bd["tr"]) + " " + c("text", "teks utama")]
        code = highlight.render("def halo(x):\n    return x * 2  # kali dua", "python")
        if code:
            lines += ["  " + c("border", bd["v"] + " ") + ln + T.RESET for ln in code]
        return lines

    def _theme_items(self):
        items = [("auto", "auto", "deteksi latar terang/gelap terminal")]
        for n in T.names():
            i = T.info(n)
            items.append((n, n, f"{i['family']} · {'gelap' if i['dark'] else 'terang'}"))
        return items

    def cmd_theme(self, arg):
        a = arg.strip().lower()
        if a in ("test", "colors", "warna"):
            return self.cmd_colors("")
        if a in ("list", "ls"):
            rows = [[n, T.info(n)["family"], "gelap" if T.info(n)["dark"] else "terang"] for n in T.names()]
            return self.ui.table(["tema", "keluarga", "latar"], rows, f"{len(rows)} tema · aktif: {T.current()}")
        if a:
            if a in ("auto", "dark", "light") or T.DEPRECATED.get(a, a) in T.THEMES:
                pref = a if a == "auto" else (T.resolve(a, detect=False) if a in ("dark", "light") else T.DEPRECATED.get(a, a))
                self._apply_theme_pref(pref)
                self._persist_design()
                self.ui.ok(f"Tema: {pref}" + (f" (terdeteksi: {T.current()})" if pref == "auto" else ""))
                return self.ui.p("\n".join(self._theme_preview()))
            import difflib
            near = difflib.get_close_matches(a, T.names(), 3)
            return self.ui.err(f"Tema '{a}' tidak ada." + (" Maksud kamu: " + ", ".join(near) + "?" if near else " Ketik /theme untuk memilih."))
        if not menu.available():
            self.ui.p("  " + "  ".join(c("accent" if n == T.current() else "muted", n) for n in T.names()))
            return self.ui.p(c("muted", "  pakai: /theme <nama> · auto · dark · light · test"))
        self._resolve_theme("auto")                      # deteksi latar SEBELUM masuk mode raw
        before = (self._theme_pref, T.current())
        pick = menu.pick("Tema", self._theme_items(), current=self._theme_pref,
                         on_move=lambda v: T.set_theme(self._resolve_theme(v)), preview=self._theme_preview)
        if pick is None:
            self._theme_pref = before[0]
            T.set_theme(before[1])
            return
        self._apply_theme_pref(pick)
        self._persist_design()
        self.ui.ok(f"Tema: {pick}")

    def cmd_colors(self, arg):
        env = os.environ
        rows = [["kedalaman warna", T.depth_label()], ["TERM", env.get("TERM", "-")], ["COLORTERM", env.get("COLORTERM", "-")],
                ["platform", envinfo.platform_label()], ["UTF-8", "ya" if envinfo.utf8_ok() else "TIDAK (mode ASCII)"],
                ["latar terminal", T.detect_background() or "tidak terdeteksi"], ["tema aktif", f"{T.current()}  (preferensi: {self._theme_pref})"],
                ["lebar terminal", envinfo.term_size().columns]]
        self.ui.table(["", ""], rows, "Uji warna CodinX")
        sw = "  ".join(c(r, f"{r}") for r in ("accent", "accent2", "ok", "warn", "err", "info", "muted", "border", "code", "link"))
        self.ui.p("  " + sw)
        ramp = "".join(T.hexfg(T.mix("#FF4D4D", "#4DA6FF", i / 23)) + "█" for i in range(24)) + T.RESET if T.ENABLED else "(tanpa warna)"
        self.ui.p("  " + ramp)
        if T.depth() == 0:
            self.ui.warn("Warna MATI. Penyebab umum: stdout bukan terminal, NO_COLOR di-set, atau TERM=dumb. Paksa: CODINX_COLOR=256 (atau truecolor).")
        elif T.depth() == 16:
            self.ui.info("Hanya 16 warna. Bila terminalmu mendukung lebih: CODINX_COLOR=256 atau CODINX_COLOR=truecolor (Termux: sudah otomatis).")
        self.ui.p(c("muted", "  Semua terlihat abu-abu? coba: /theme (pilih tema), CODINX_COLOR=truecolor, atau CODINX_BACKGROUND=light bila latar terang."))

    def _sample(self, key):
        bd = design.border()
        if key == "banner":
            rows = design.banner_rows(design.get("banner"))
            return [("  " + T.gradient(r)) for r in rows] if rows else ["  " + T.gradient("CodinX") + c("muted", "  v" + __version__)]
        if key == "border":
            return ["  " + c("border", bd["tl"] + bd["h"] * 8 + bd["tj"] + bd["h"] * 8 + bd["tr"]),
                    "  " + c("border", bd["v"]) + c("heading", " kolom A ", bold=True) + c("border", bd["v"]) + c("text", " kolom B ") + c("border", bd["v"]),
                    "  " + c("border", bd["bl"] + bd["h"] * 8 + bd["bj"] + bd["h"] * 8 + bd["br"])]
        if key == "spinner":
            frames, _ = design.spinner()
            return ["  " + "  ".join(c("accent", f) for f in frames[:12])]
        if key == "icons":
            return ["  " + "  ".join(c(r, design.icon(n)) + " " + n for r, n in (("ok", "ok"), ("err", "err"), ("warn", "warn"), ("info", "info"), ("accent2", "tool"), ("accent", "skill")))]
        if key == "prompt":
            return ["  " + c("user", design.prompt_glyph(), bold=True) + c("text", "contoh pesan kamu")]
        if key == "gutter":
            g = design.gutter_glyph()
            return ["  " + c("accent", g) + c("text", "baris jawaban pertama"), "  " + c("accent", g) + c("text", "baris jawaban kedua")]
        if key == "status":
            return [self.footer()]
        return ["  " + c("text", "kerapatan: " + design.get("density"))]

    _DESC = {"banner": {"pro": "satu baris profesional", "block": "blok gradien besar", "slant": "miring", "small": "kecil 2 baris", "wide": "huruf renggang",
                        "boxed": "dalam kotak", "mini": "ringkas", "none": "tanpa banner"},
             "border": {"rounded": "╭╮ sudut bulat", "square": "┌┐ sudut siku", "heavy": "┏┓ tebal", "double": "╔╗ ganda", "ascii": "+-| aman semua font", "minimal": "hanya garis datar"},
             "icons": {"auto": "ikuti dukungan UTF-8", "unicode": "✓ ✗ ⚠", "ascii": "+ x !", "nerd": "butuh Nerd Font", "emoji": "✅ ❌ 🔧"},
             "prompt": {"bar": "┃", "arrow": "❯", "chevron": "›", "dollar": "$", "triangle": "▶", "lambda": "λ", "plain": ">"},
             "gutter": {"none": "tanpa", "bar": "▎ garis", "dot": "● titik", "line": "│ garis tipis"},
             "status": {"dots": "a · b · c", "pills": "lencana berwarna", "bar": "a │ b │ c", "minimal": "model · ctx"},
             "density": {"comfortable": "lega", "compact": "ringkas (ponsel)"}}

    def _design_cmd(self, key, arg, label):
        arg = arg.strip().lower()
        choices = design.CHOICES[key]
        before = design.get(key)
        if arg:
            if arg not in choices:
                return self.ui.err(f"{label} '{arg}' tidak dikenal. Pilihan: {', '.join(choices)}")
        elif menu.available():
            items = [(v, v, self._DESC.get(key, {}).get(v, "")) for v in choices]
            arg = menu.pick(label, items, current=before, on_move=lambda v: design.set(key, v), preview=lambda v: self._sample(key))
            if arg is None:
                design.set(key, before)
                return
        else:
            return self.ui.info(f"{label} sekarang: {before}. Pilihan: {', '.join(choices)}")
        design.set(key, arg)
        self._persist_design()
        self.ui.ok(f"{label}: {arg}")
        if key == "banner":
            self.ui.banner(self.cfg["model"], self.ctx.mode, tiers.plan_label(self.cfg), self.cwd)
        elif key == "spinner":
            self.ui.spin_start("contoh animasi")
            time.sleep(0.9)
            self.ui.spin_stop()
        else:
            self.ui.p("\n".join(self._sample(key)))

    def cmd_banner(self, arg):
        self._design_cmd("banner", arg, "Banner")

    def cmd_border(self, arg):
        self._design_cmd("border", arg, "Border")

    def cmd_spinner(self, arg):
        self._design_cmd("spinner", arg, "Spinner")

    def cmd_icons(self, arg):
        self._design_cmd("icons", arg, "Ikon")

    def cmd_prompt(self, arg):
        self._design_cmd("prompt", arg, "Prompt")

    def cmd_gutter(self, arg):
        self._design_cmd("gutter", arg, "Gutter")

    def cmd_density(self, arg):
        self._design_cmd("density", arg, "Kerapatan")

    def cmd_footer(self, arg):
        self._design_cmd("status", arg, "Baris status")

    def _all_presets(self):
        allp = dict(design.PRESETS)
        allp.update(self.cfg.get("presets", {}))
        return allp

    def _apply_preset(self, name):
        p = self._all_presets().get(name)
        if not p:
            return False
        for k in design.DEFAULT:
            if k in p and (k not in design.CHOICES or p[k] in design.CHOICES[k]):
                design.STATE[k] = p[k]
        self._theme_pref = p.get("theme", "auto")
        T.set_theme(self._resolve_theme(self._theme_pref))
        return True

    def cmd_design(self, arg):
        a = arg.strip()
        low = a.lower()
        if low == "show":
            rows = [[k, v] for k, v in design.dump().items()] + [["tema", f"{self._theme_pref} → {T.current()}"]]
            return self.ui.table(["", ""], rows, "Desain saat ini")
        if low in ("list", "ls"):
            rows = [[n, p.get("theme", "auto"), p.get("banner", ""), p.get("border", ""), design.PRESET_NOTE.get(n, "kustom")] for n, p in self._all_presets().items()]
            return self.ui.table(["preset", "tema", "banner", "border", "catatan"], rows, "Preset desain")
        if low == "reset":
            self._apply_preset("codinx")
            self._persist_design()
            return self.ui.ok("Desain dikembalikan ke bawaan (codinx).")
        if low.startswith("save"):
            name = a[4:].strip().lower()
            if not name or not re.fullmatch(r"[a-z0-9_-]{1,24}", name):
                return self.ui.err("Pakai: /design save <nama> (huruf kecil/angka/-/_).")
            self.cfg.setdefault("presets", {})[name] = dict(design.dump(), theme=self._theme_pref)
            self.save_cfg()
            return self.ui.ok(f"Preset '{name}' disimpan. Pakai: /design {name}")
        if low.startswith("set "):
            parts = low.split()
            if len(parts) != 3 or parts[1] not in design.CHOICES:
                return self.ui.err("Pakai: /design set <banner|border|spinner|icons|prompt|status|gutter|density> <nilai>")
            if not design.set(parts[1], parts[2]):
                return self.ui.err(f"Nilai tidak valid. Pilihan: {', '.join(design.CHOICES[parts[1]])}")
            self._persist_design()
            return self.ui.ok(f"{parts[1]}: {parts[2]}")
        if low:
            if not self._apply_preset(low):
                return self.ui.err(f"Preset '{low}' tidak ada. Lihat: /design list")
            self._persist_design()
            self.ui.ok(f"Desain: {low}")
            return self.ui.banner(self.cfg["model"], self.ctx.mode, tiers.plan_label(self.cfg), self.cwd)
        if not menu.available():
            return self.cmd_design("list")
        self._resolve_theme("auto")
        snap = (design.dump(), self._theme_pref)
        items = [(n, n, design.PRESET_NOTE.get(n, "preset kustom")) for n in self._all_presets()]
        pick = menu.pick("Preset desain", items, on_move=self._apply_preset, preview=lambda v: self._theme_preview() + self._sample("status"))
        if pick is None:
            design.STATE.update(snap[0])
            self._theme_pref = snap[1]
            T.set_theme(self._resolve_theme(snap[1]))
            return
        self._apply_preset(pick)
        self._persist_design()
        self.ui.ok(f"Desain: {pick}")
        self.ui.banner(self.cfg["model"], self.ctx.mode, tiers.plan_label(self.cfg), self.cwd)

    # ------------------------------------------------------------ penampil dokumen
    def _doc_dir(self):
        return os.path.join(config.ROOT, "docs")

    def _doc_names(self):
        try:
            return sorted(f[:-3] for f in os.listdir(self._doc_dir()) if f.endswith(".md")) + ["README"]
        except OSError:
            return ["README"]

    def cmd_docs(self, arg):
        from . import mdview
        names = self._doc_names()
        a = arg.strip().lower()
        if not a:
            if menu.available():
                a = menu.pick("Dokumentasi", [(n, n, "") for n in names]) or ""
            if not a:
                return self.ui.table(["dokumen"], [[n] for n in names], "Dokumentasi — /docs <nama>")
        hit = next((n for n in names if n.lower() == a), None) or next((n for n in names if n.lower().startswith(a)), None)
        if not hit:
            return self.ui.err(f"Dokumen '{a}' tidak ada. Pilihan: {', '.join(names)}")
        path = os.path.join(config.ROOT, "README.md") if hit == "README" else os.path.join(self._doc_dir(), hit + ".md")
        mdview.show(self.ui, fsutil.read_text(path))

    def cmd_view(self, arg):
        from . import mdview
        path = self.ctx.path(arg.strip())
        if not arg.strip() or not os.path.isfile(path):
            return self.ui.err("Pakai: /view <file>  (file tidak ditemukan)" if arg.strip() else "Pakai: /view <file.md|kode>")
        text = fsutil.read_text(path)
        if path.lower().endswith((".md", ".markdown")):
            return mdview.show(self.ui, text)
        ext = os.path.splitext(path)[1].lstrip(".").lower() or os.path.basename(path).lower()
        lines = highlight.render("\n".join(text.splitlines()[:300]), ext) or text.splitlines()[:300]
        for i, ln in enumerate(lines, 1):
            self.ui.p(c("muted", f"{i:>4} ") + ln + (T.RESET if T.ENABLED else ""))

    def cmd_sessions(self, arg):
        items = Session.list_all()[:15]
        if not items:
            return self.ui.info("Belum ada sesi tersimpan.")
        self.ui.table(["#", "judul", "folder", "pesan"], [[i + 1, it["title"][:34] or it["id"], it["cwd"][-24:], it["n"]] for i, it in enumerate(items)], "Sesi")
        try:
            a = self._ask(c("muted", "  nomor untuk dilanjutkan (enter batal) › ")).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if a.isdigit() and 1 <= int(a) <= len(items):
            self.session.save()
            self.set_session(Session.load(items[int(a) - 1]["id"]))
            self.ui.ok(f"Sesi dilanjutkan: {self.session.title[:50]}")

    # ------------------------------------------------------------ models
    def cmd_models(self, arg):
        q = arg.strip().lower()
        cat = list(tiers.catalog())
        known = {m["id"] for m in cat}
        if self.key:
            try:
                live = api.list_model_specs(self.cfg, self.key)
                cat += [m for m in live if m["id"] not in known]
            except api.ApiError:
                pass
        items = [m for m in cat if not q or q in m["id"].lower() or q in m["name"].lower() or q == m["role"].lower()]
        if not items:
            return self.ui.warn("Tidak ada model cocok.")
        cnt = {r: sum(1 for m in cat if m["role"] == r) for r in ("FREE", "PRO", "MAX")}
        if tiers.trial_mode(self.cfg):
            self.ui.p(c("muted", f"  {len(cat)} model · ") + c("ok", "SEMUA GRATIS", bold=True) + c("muted", " (mode uji coba)"))
        else:
            self.ui.p(c("muted", f"  {len(cat)} model · FREE {cnt['FREE']} · PRO {cnt['PRO']} · MAX {cnt['MAX']} · paket kamu: ") + c("accent2", tiers.tier_of(self.cfg), bold=True))
        shown = items[:40]
        for i, m in enumerate(shown, 1):
            ok, via, _ = tiers.can_use_model(self.cfg, m["id"])
            mark = c("ok", "✓") if ok and not via else c("warn", "◐") if ok else c("muted", "🔒")
            cur = c("accent", " ◀ aktif", bold=True) if m["id"] == self.cfg["model"] else ""
            tag = f"[{m['role']}" + (f" · trial {m['trial']}x" if m.get("trial") else "") + "]"
            self.ui.p(f"  {i:>3} {mark} " + c("text" if ok else "muted", m["id"]) + " " + c("muted", tag) + cur)
        if len(items) > len(shown):
            self.ui.p(c("muted", f"  … {len(items) - len(shown)} lagi — persempit: /models claude · /models free · /models pro"))
        try:
            a = self._ask(c("muted", "  pilih nomor / id (enter batal) › ")).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not a:
            return
        pick = shown[int(a) - 1] if a.isdigit() and 1 <= int(a) <= len(shown) else next((m for m in cat if m["id"] == a), None)
        if not pick:
            return self.ui.err("Model tidak ditemukan.")
        ok, _, msg = tiers.can_use_model(self.cfg, pick["id"])
        if not ok:
            return self.ui.warn(msg)
        self.cfg["model"] = pick["id"]
        self.save_cfg()
        self.ui.ok(f"Model: {pick['id']}" + (f"  ({msg})" if msg else ""))

    # ------------------------------------------------------------ permission centre
    def cmd_permissions(self, arg):
        while True:
            rows = [[i + 1, t, POLICY_LABEL[self.perms.policy(t)] + (" (bawaan)" if t not in self.cfg.get("tool_policy", {}) and t in DEFAULT_POLICY else ""), d]
                    for i, (t, d) in enumerate(PERM_ROWS)]
            self.ui.table(["#", "izin", "status", "keterangan"], rows, "Pengaturan izin CodinX")
            self.ui.p(c("muted", "  ketik nomor = ganti status (bawaan → tanya → izinkan → tolak → mati) · r = reset semua · enter = selesai"))
            try:
                a = self._ask(c("accent", "  izin › ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                self.ui.p()
                return
            if not a:
                return
            if a == "r":
                self.cfg["tool_policy"] = {}
                self.save_cfg()
                continue
            if a.isdigit() and 1 <= int(a) <= len(PERM_ROWS):
                t = PERM_ROWS[int(a) - 1][0]
                order = [x for x in POLICY_CYCLE if not (x == "default" and t in DEFAULT_POLICY)]
                cur = self.perms.policy(t)
                nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else order[0]
                self.perms.set_policy(t, nxt)
