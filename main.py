#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nazzil — YouTube downloader entry point.

pip install -r requirements.txt
External tools: ffmpeg (required for 4K merge / MP3),
                aria2c (optional faster downloads)
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

try:
    import yt_dlp  # noqa: F401, E402
except ImportError:
    print("yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

from config import DEFAULT_LANG, load_config   # noqa: E402
from i18n import Translator                    # noqa: E402
from ui.app import App                         # noqa: E402
from ui.theme import THEME_QSS                 # noqa: E402


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

    app = QApplication(sys.argv)
    app.setApplicationName("Nazzil")
    app.setQuitOnLastWindowClosed(False)  # closing the window → minimize to tray

    # Load language from config (default Arabic) BEFORE building UI.
    cfg = load_config()
    lang = cfg.get("lang", DEFAULT_LANG)
    Translator.load(lang)
    app.setLayoutDirection(
        Qt.RightToLeft if Translator.is_rtl() else Qt.LeftToRight)

    app.setStyleSheet(THEME_QSS)

    icon = QIcon(ICON_PATH) if os.path.exists(ICON_PATH) else QIcon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    window = App(app_icon=icon)
    window.show()
    window.start_update_check()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
