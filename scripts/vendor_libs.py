#!/usr/bin/env python3
"""Salin pustaka pihak ketiga murni-Python (MIT/BSD) + data zona waktu ke cx/vendor beserta lisensinya.

Dipakai oleh: markdown_it+mdurl (penampil Markdown /docs /view), tabulate (ekspor tabel), yaml (ekspor YAML & skill json-yaml-tools),
zoneinfo (zona waktu di perangkat tanpa tzdata, mis. Android/Termux). Pygments ditangani scripts/vendor_pygments.py.

  python3 scripts/vendor_libs.py
"""
import glob
import importlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "cx", "vendor")
LIBS = ["markdown_it", "mdurl", "tabulate", "yaml"]
SKIP_SUFFIX = (".so", ".pyd", ".pyc", ".pyx", ".pxd", ".c", ".h")


def copy_pkg(name):
    mod = importlib.import_module(name)
    src = os.path.dirname(mod.__file__)
    dst = os.path.join(DEST, name)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=lambda d, files: [f for f in files if f == "__pycache__" or f.endswith(SKIP_SUFFIX) or f == "py.typed"])
    return getattr(mod, "__version__", "?"), os.path.dirname(src)


def license_for(name, site):
    dist = {"markdown_it": "markdown_it_py", "mdurl": "mdurl", "tabulate": "tabulate", "yaml": "pyyaml"}[name]
    for pat in (f"{dist}-*.dist-info", f"{dist.replace('_', '-')}-*.dist-info"):
        for d in glob.glob(os.path.join(site, pat)):
            for root, _, files in os.walk(d):
                for f in files:
                    if f.upper().startswith(("LICENSE", "LICENCE", "COPYING")):
                        return os.path.join(root, f)
    return None


def main():
    os.makedirs(os.path.join(DEST, "licenses"), exist_ok=True)
    info = {}
    for name in LIBS:
        ver, site = copy_pkg(name)
        lic = license_for(name, site)
        if lic:
            shutil.copy2(lic, os.path.join(DEST, "licenses", f"{name}-LICENSE"))
        info[name] = {"version": ver, "license_file": bool(lic)}
        print(f"  {name:12} {ver:8} lisensi={'ya' if lic else 'TIDAK ADA'}")
    # data zona waktu (domain publik) — untuk perangkat tanpa tzdata
    zsrc = "/usr/share/zoneinfo"
    zdst = os.path.join(DEST, "zoneinfo")
    shutil.rmtree(zdst, ignore_errors=True)
    n = 0
    for root, dirs, files in os.walk(zsrc):
        dirs[:] = [d for d in dirs if d not in ("posix", "right", "SystemV", "Etc") or d == "Etc"]
        for f in files:
            p = os.path.join(root, f)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            with open(p, "rb") as fh:
                head = fh.read(4)
                if head != b"TZif":
                    continue
                fh.seek(0)
                data = fh.read()
            rel = os.path.relpath(p, zsrc)
            os.makedirs(os.path.dirname(os.path.join(zdst, rel)) or zdst, exist_ok=True)
            with open(os.path.join(zdst, rel), "wb") as out:
                out.write(data)
            n += 1
    info["zoneinfo"] = {"files": n, "license": "domain publik (IANA tz database)"}
    print(f"  zoneinfo     {n} zona")
    with open(os.path.join(DEST, "VENDOR.json"), "w") as f:
        json.dump(info, f, indent=1)


if __name__ == "__main__":
    sys.exit(main())
