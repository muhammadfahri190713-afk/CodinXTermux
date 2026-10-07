"""Encrypted API-key storage (stdlib only).

The key lives in a hidden file (~/.codinx/.key.enc, mode 600) encrypted with
an HMAC-SHA256 keystream (encrypt-then-MAC), keyed from this machine's id via
PBKDF2. It stops casual reads and copies to other machines; root on the same
box can still decrypt it.
"""
import base64
import hashlib
import hmac
import os

MAGIC = b"CX1"


def _home_dir():
    return os.path.abspath(os.path.expanduser(os.environ.get("CODINX_HOME") or "~/.codinx"))


def _install_id():
    """ID acak per-instalasi (dibuat sekali) untuk perangkat tanpa /etc/machine-id, mis. Android/Termux."""
    p = os.path.join(_home_dir(), ".machine-id")
    try:
        with open(p) as f:
            v = f.read().strip()
        if v:
            return v.encode()
    except OSError:
        pass
    v = os.urandom(16).hex()
    try:
        os.makedirs(os.path.dirname(p), mode=0o700, exist_ok=True)
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(v)
        return v.encode()
    except OSError:
        return None


def _machine_secrets():
    out = []
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(p) as f:
                v = f.read().strip()
            if v:
                out.append(v.encode())
                break
        except OSError:
            pass
    if not out:
        iid = _install_id()
        if iid:
            out.append(iid)
    out.append(os.uname().nodename.encode())          # kompatibilitas kunci lama
    return out


def _keys(secret):
    k = hashlib.pbkdf2_hmac("sha256", secret, b"codinx-vault-v1", 200_000, 64)
    return k[:32], k[32:]


def _stream(key, nonce, n):
    out = bytearray()
    ctr = 0
    while len(out) < n:
        out += hmac.new(key, nonce + ctr.to_bytes(8, "big"), hashlib.sha256).digest()
        ctr += 1
    return bytes(out[:n])


def encrypt(text):
    ek, mk = _keys(_machine_secrets()[0])
    raw = text.encode()
    nonce = os.urandom(16)
    ct = bytes(a ^ b for a, b in zip(raw, _stream(ek, nonce, len(raw))))
    tag = hmac.new(mk, MAGIC + nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(MAGIC + nonce + ct + tag)


def decrypt(blob):
    data = base64.b64decode(blob)
    if data[:3] != MAGIC or len(data) < 3 + 16 + 32:
        raise ValueError("bad key file")
    nonce, ct, tag = data[3:19], data[19:-32], data[-32:]
    for secret in _machine_secrets():                  # coba rahasia utama, lalu yang lama
        ek, mk = _keys(secret)
        if hmac.compare_digest(tag, hmac.new(mk, MAGIC + nonce + ct, hashlib.sha256).digest()):
            return bytes(a ^ b for a, b in zip(ct, _stream(ek, nonce, len(ct)))).decode()
    raise ValueError("key file corrupted or from another machine")
