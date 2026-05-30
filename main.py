#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nazzil — video downloader entry point (YouTube + 1800 other sites).

pip install -r requirements.txt

External tools (ffmpeg / ffprobe / aria2c) ship bundled with the app and are
resolved by binaries.py — no manual install needed. From a stripped source
checkout they're fetched silently on first run.
"""

import os
import sys

# Ensure the package directory is on sys.path whether you run as
# `python main.py` from inside this folder OR via `python -m nazzil.main`.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from PySide6.QtCore import Qt                  # noqa: E402
from PySide6.QtGui import QIcon                # noqa: E402
from PySide6.QtWidgets import QApplication     # noqa: E402

# Route `import yt_dlp` to a silently-cached newer copy if one exists
# (frozen-only; no-op otherwise). Must run BEFORE importing yt_dlp.
import ytdlp_updater                           # noqa: E402
ytdlp_updater.bootstrap()
try:
    import yt_dlp  # noqa: F401, E402
except Exception:
    # A bad/partial cache could shadow the bundled copy — self-heal by
    # purging it and falling back to the bundled yt-dlp.
    ytdlp_updater.purge_cache()
    try:
        import yt_dlp  # noqa: F401, E402
    except ImportError:
        # Only reachable on a source checkout with missing deps. No
        # user-facing install instruction.
        sys.stderr.write("yt-dlp module unavailable.\n")
        sys.exit(1)

from config import DEFAULT_LANG, load_config   # noqa: E402
from fonts import load_app_fonts               # noqa: E402
from i18n import Translator                    # noqa: E402
from ui.app import App                         # noqa: E402
from ui.theme import apply_theme               # noqa: E402


ASSETS_DIR = os.path.join(_HERE, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")


def _ensure_icon():
    """If running from source and the icon hasn't been generated yet, build
    it now. The frozen build always ships the icon from the spec datas."""
    if os.path.exists(ICON_PATH):
        return
    try:
        from generate_icon import draw_icon, png_to_ico
        os.makedirs(ASSETS_DIR, exist_ok=True)
        draw_icon(ICON_PATH)
        png_to_ico(ICON_PATH, os.path.join(ASSETS_DIR, "icon.ico"))
    except Exception:
        pass


def main():
    _ensure_icon()

    # ffmpeg / ffprobe / aria2c are bundled (installer) or fetched silently
    # on first run for the lean portable exe. That check lives in App so it
    # can show a non-blocking "Preparing…" status instead of a frozen window.

    app = QApplication(sys.argv)
    app.setApplicationName("Nazzil")
    app.setQuitOnLastWindowClosed(False)  # closing the window → minimize to tray

    # Single instance: if Nazzil is already running (incl. hidden in the
    # tray), ask that copy to show itself and exit — never open a 2nd window.
    from single_instance import SingleInstance
    single = SingleInstance()
    if single.is_running():
        single.ping_primary()
        return
    single.start_server()

    # Register bundled fonts BEFORE the stylesheet is applied so the QSS
    # `font-family: "Thmanyah Sans"` selector resolves against the family
    # we just registered.
    load_app_fonts(app)

    # Load language from config (default Arabic) BEFORE building UI.
    cfg = load_config()
    lang = cfg.get("lang", DEFAULT_LANG)
    Translator.load(lang)
    app.setLayoutDirection(
        Qt.RightToLeft if Translator.is_rtl() else Qt.LeftToRight)

    # Apply the saved theme (dark / light). apply_theme also rebinds the
    # ui.theme colour constants so any widget built later uses this palette.
    apply_theme(app, cfg.get("theme", "dark"))

    icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else QIcon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = App(app_icon=icon)
    # A second launch pings us → bring the existing window to the front.
    single.activated.connect(window._tray_show)
    window.show()
    window.start_update_check()
    # Silent, hands-off yt-dlp refresh in the background (frozen-only,
    # at most once a day). No UI, no prompts — takes effect next launch.
    ytdlp_updater.update_async()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
