"""Impor pustaka pihak ketiga: pakai versi sistem bila ada, jika tidak pakai salinan di cx/vendor (ditambahkan di AKHIR sys.path)."""
import importlib
import os
import sys

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")


def load(name):
    try:
        return importlib.import_module(name)
    except Exception:
        pass
    if os.path.isdir(os.path.join(VENDOR, name)) and VENDOR not in sys.path:
        sys.path.append(VENDOR)
    try:
        return importlib.import_module(name)
    except Exception:
        return None
