"""Deteksi lingkungan: Termux/Android, Unicode, direktori sementara, ukuran terminal."""
import os
import shutil
import sys
import tempfile


def is_termux(env=None):
    e = os.environ if env is None else env
    return bool(e.get("TERMUX_VERSION")) or "com.termux" in e.get("PREFIX", "")


def is_android(env=None):
    e = os.environ if env is None else env
    return is_termux(e) or bool(e.get("ANDROID_ROOT")) or os.path.exists("/system/build.prop")


def utf8_ok():
    enc = (getattr(sys.stdout, "encoding", None) or "").lower().replace("-", "")
    if enc and "utf8" not in enc:
        return False
    return True


def tmpdir():
    return tempfile.gettempdir()          # menghormati $TMPDIR (Termux: $PREFIX/tmp)


def term_size(default=(80, 24)):
    return shutil.get_terminal_size(default)


def platform_label():
    if is_termux():
        return "Termux (Android)"
    if is_android():
        return "Android"
    return sys.platform


def compact_hint():
    """Layar sempit (mis. ponsel portrait) -> tata letak ringkas."""
    return term_size().columns < 60
