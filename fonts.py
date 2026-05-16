# -*- coding: utf-8 -*-
"""Load the bundled ThmanyahSans family at startup.

Scans `assets/fonts/*.ttf` and `*.otf`, registers each with
QFontDatabase, and applies the first loaded family as the QApplication's
default font. The QSS in ui/theme.py already lists "Thmanyah Sans" as
the primary family, so once the font is registered every styled widget
picks it up automatically.

Safe to call when the folder is empty — degrades silently to the QSS
fallback chain (Segoe UI / Tahoma / Noto Sans Arabic).
"""

import os
import sys

from PySide6.QtGui import QFont, QFontDatabase


_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_HERE, "assets", "fonts")

# Family name expected from the ThmanyahSans .ttf metadata.
PREFERRED_FAMILY = "Thmanyah Sans"


def load_app_fonts(app):
    """Register every font file in assets/fonts/ and set the default app
    font. Returns the family name actually applied, or '' if no fonts
    were loaded."""
    if not os.path.isdir(FONTS_DIR):
        return ""

    loaded_families = []
    for fname in sorted(os.listdir(FONTS_DIR)):
        low = fname.lower()
        if not (low.endswith(".ttf") or low.endswith(".otf")):
            continue
        path = os.path.join(FONTS_DIR, fname)
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id == -1:
            print(f"[fonts] failed to load {path}", file=sys.stderr)
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        loaded_families.extend(families)

    if not loaded_families:
        return ""

    # Pick the preferred family if the bundled fonts include it, else
    # fall back to whatever loaded first.
    family = next((f for f in loaded_families if f == PREFERRED_FAMILY),
                  loaded_families[0])

    base_font = QFont(family)
    base_font.setPointSize(10)  # Qt picks a sensible default size for the family
    app.setFont(base_font)
    return family
