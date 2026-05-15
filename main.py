#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nazzil — YouTube downloader entry point.

pip install PySide6 yt-dlp Pillow
External tools (optional/required): ffmpeg (required for 4K merge / MP3),
                                    aria2c (optional faster downloads)
"""

import os
import sys

# Ensure the package's own directory is on sys.path when running as
# `python main.py` from inside the nazzil/ folder OR via `python -m nazzil.main`.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from PIL import Image, ImageDraw            # noqa: E402
from PySide6.QtCore import Qt               # noqa: E402
from PySide6.QtGui import QIcon             # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

try:
    import yt_dlp  # noqa: F401, E402
except ImportError:
    print("yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

from config import DEFAULT_LANG, load_config  # noqa: E402
from i18n import Translator                   # noqa: E402
from ui.app import App                        # noqa: E402
from ui.theme import THEME_QSS                # noqa: E402


ASSETS_DIR = os.path.join(_HERE, "assets")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")


def _generate_icon_if_missing():
    """Generate a small brand-coloured icon on first run."""
    if os.path.exists(ICON_PATH):
        return
    try:
        os.makedirs(ASSETS_DIR, exist_ok=True)
        size = 256
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # rounded square in Linear accent
        d.rounded_rectangle((16, 16, size - 16, size - 16),
                            radius=56, fill=(94, 106, 210, 255))
        # play-arrow glyph
        d.polygon([(90, 72), (190, 128), (90, 184)],
                  fill=(255, 255, 255, 255))
        img.save(ICON_PATH, "PNG")
    except Exception:
        pass


def main():
    _generate_icon_if_missing()

    app = QApplication(sys.argv)
    app.setApplicationName("Nazzil")
    app.setQuitOnLastWindowClosed(False)  # closing the window → tray

    # Load language from config (default Arabic) BEFORE building UI so all
    # widget strings are translated up-front.
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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
