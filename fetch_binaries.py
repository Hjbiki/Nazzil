# -*- coding: utf-8 -*-
"""Build-time helper: download ffmpeg / ffprobe / aria2c into assets/bin/.

Run before PyInstaller so the official Windows builds get embedded into
Nazzil.exe (see nazzil.spec). Keeps the heavy binaries OUT of git (they're
*.exe, which .gitignore excludes) while still shipping them in releases.

    python fetch_binaries.py

Idempotent — skips anything already present. Exits 0 even on failure so a
transient network hiccup doesn't break a release build (the app downloads
the tools silently on first run as a fallback)."""

import os
import sys

import binaries


def main():
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "assets", "bin")
    os.makedirs(dest, exist_ok=True)
    print(f"[fetch_binaries] target: {dest}")

    targets = [
        ("ffmpeg", binaries._DOWNLOADS["ffmpeg"]),
        ("aria2c", binaries._DOWNLOADS["aria2c"]),
    ]
    for name, spec in targets:
        members = spec["members"]
        have_all = all(
            os.path.isfile(os.path.join(dest, m)) for m in members)
        if have_all:
            print(f"[fetch_binaries] {name}: already present, skipping")
            continue
        print(f"[fetch_binaries] {name}: downloading {spec['url']}")
        ok = binaries._download_archive(spec["url"], members, dest)
        print(f"[fetch_binaries] {name}: {'OK' if ok else 'FAILED'}")

    # We never ship ffplay.exe (not needed; keeps the bundle ~80 MB). Strip
    # it if some other tool ever drops one in.
    stray = os.path.join(dest, "ffplay.exe")
    if os.path.isfile(stray):
        try:
            os.remove(stray)
            print("[fetch_binaries] removed stray ffplay.exe")
        except Exception:
            pass

    # Always succeed — the runtime fallback covers any missing tool.
    return 0


if __name__ == "__main__":
    sys.exit(main())
