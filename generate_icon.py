#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the Nazzil app icon.

Run once during development or in CI:
    python generate_icon.py

Writes:
    assets/icon.png    256x256 ARGB PNG, drawn with QPainter
    assets/icon.ico    Windows ICO with sizes [16, 32, 48, 64, 128, 256]

Uses Qt's offscreen platform so it works headlessly (e.g. GitHub Actions).
"""

import os
import sys

# Must be set BEFORE QGuiApplication is constructed.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image                                          # noqa: E402
from PySide6.QtCore import Qt                                  # noqa: E402
from PySide6.QtGui import (QColor, QGuiApplication, QImage,    # noqa: E402
                           QPainter, QPen)


SIZE   = 256
BG     = "#08090A"   # app background
ACCENT = "#5E6AD2"   # brand


def draw_icon(path: str) -> None:
    """Draw a minimalist N glyph in accent on the dark Linear bg."""
    QGuiApplication.instance() or QGuiApplication(sys.argv)

    img = QImage(SIZE, SIZE, QImage.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))  # transparent corners around the rounded bg

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # rounded dark background (rounded square, generous radius)
    p.setBrush(QColor(BG))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, SIZE, SIZE, 48, 48)

    # Stylised "N" — three rounded strokes in accent
    stroke = 30
    p.setPen(QPen(QColor(ACCENT), stroke,
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    margin = 70
    top    = margin
    bottom = SIZE - margin
    left   = margin + 4
    right  = SIZE - margin - 4
    p.drawLine(left,  bottom, left,  top)
    p.drawLine(left,  top,    right, bottom)
    p.drawLine(right, bottom, right, top)

    # Small down-tick under the N — gestures the "download" idea
    p.setPen(QPen(QColor(ACCENT), stroke // 2,
                  Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    cx = SIZE // 2
    p.drawLine(cx - 24, SIZE - margin + 14, cx, SIZE - margin + 38)
    p.drawLine(cx,      SIZE - margin + 38, cx + 24, SIZE - margin + 14)

    p.end()
    img.save(path, "PNG")


def png_to_ico(png_path: str, ico_path: str) -> None:
    """Multi-size ICO from the rendered PNG."""
    src = Image.open(png_path)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    src.save(ico_path, format="ICO", sizes=sizes)


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    assets = os.path.join(here, "assets")
    os.makedirs(assets, exist_ok=True)
    png = os.path.join(assets, "icon.png")
    ico = os.path.join(assets, "icon.ico")
    draw_icon(png)
    png_to_ico(png, ico)
    print(f"Wrote {png}")
    print(f"Wrote {ico}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
