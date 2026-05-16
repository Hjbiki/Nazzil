#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bump the project version in ONE place.

Usage:
    python update_version.py 1.2.0

What it does:
    1. Rewrites the VERSION file with the given version.
    2. config.py reads VERSION at import time → APP_VERSION is live.
    3. nazzil.spec reads VERSION at build time.
    4. installer.iss reads VERSION at compile time (via Inno preprocessor).

So a single command keeps every artifact in sync — no other files need to
change.
"""

import os
import re
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_PATH = os.path.join(_HERE, "VERSION")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?$")


def main(argv):
    if len(argv) != 2:
        print(f"usage: {os.path.basename(argv[0])} <version>", file=sys.stderr)
        print(f"  example: {os.path.basename(argv[0])} 1.2.0", file=sys.stderr)
        return 2

    version = argv[1].strip().lstrip("vV")
    if not SEMVER_RE.match(version):
        print(f"error: '{version}' is not a valid semver (e.g. 1.2.0)",
              file=sys.stderr)
        return 2

    try:
        with open(VERSION_PATH, "w", encoding="utf-8", newline="\n") as f:
            f.write(version + "\n")
    except Exception as e:
        print(f"error: failed to write {VERSION_PATH}: {e}", file=sys.stderr)
        return 1

    print(f"VERSION updated → {version}")
    print("  → config.APP_VERSION will reflect this on the next import.")
    print("  → installer.iss and nazzil.spec read VERSION at build time.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
