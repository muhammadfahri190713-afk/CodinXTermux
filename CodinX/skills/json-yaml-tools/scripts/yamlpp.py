#!/usr/bin/env python3
"""Konversi/rapikan JSON <-> YAML tanpa PyYAML terpasang (memakai salinan di cx/vendor).
Pakai: yamlpp.py FILE [--to json|yaml]   (FILE '-' = stdin).  Default: JSON->YAML, YAML->JSON."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(os.path.join(ROOT, "cx", "vendor"))
try:
    import yaml
except ImportError:
    sys.exit("PyYAML tidak tersedia (cx/vendor/yaml hilang).")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    text = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
    to = sys.argv[sys.argv.index("--to") + 1] if "--to" in sys.argv else None
    try:
        data = json.loads(text)
        src = "json"
    except ValueError:
        data, src = yaml.safe_load(text), "yaml"
    to = to or ("yaml" if src == "json" else "json")
    if to == "yaml":
        sys.stdout.write(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
