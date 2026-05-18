# -*- coding: utf-8 -*-
"""Vector icon helper backed by qtawesome (Material Design Icons).

Everywhere we used to render Unicode glyphs / emoji on QPushButtons or
QLabels, call `icon(name, color, size)` and feed it into `setIcon` /
`setIconSize`. Falls back gracefully to a null QIcon when qtawesome
isn't installed — callers can then check `icon_available()` and use a
plain text glyph as a backup.
"""

from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

try:
    import qtawesome as _qta
    _HAS_QTA = True
except Exception:
    _qta = None
    _HAS_QTA = False


# Canonical name → MDI6 mapping. Every icon in the app should be looked
# up via this dict so we have a single place to swap families.
NAMES = {
    "compact":     "mdi6.view-agenda-outline",
    "cookies":     "mdi6.cookie-outline",
    "settings":    "mdi6.cog-outline",
    "link":        "mdi6.link",
    "search":      "mdi6.magnify",
    "folder":      "mdi6.folder-outline",
    "dots":        "mdi6.dots-horizontal",
    "close":       "mdi6.close",
    "play":        "mdi6.play",
    "pause":       "mdi6.pause",
    "refresh":     "mdi6.refresh",
    "music":       "mdi6.music-note",
    "chevron_l":   "mdi6.chevron-left",
    "chevron_r":   "mdi6.chevron-right",
    "alert":       "mdi6.alert-outline",
    "download":    "mdi6.download",
    "video":       "mdi6.play-box-outline",
    "audio":       "mdi6.music-note",
    "all":         "mdi6.view-list-outline",
    "filter":      "mdi6.tune",
    "sort":        "mdi6.sort",
}


def icon_available() -> bool:
    return _HAS_QTA


def icon(name: str, color: str = "#8A8F98") -> QIcon:
    """Return a QIcon for `name`. `name` may be either a key in NAMES
    or an MDI identifier directly (anything containing a dot)."""
    if not _HAS_QTA:
        return QIcon()
    mdi = name if "." in name else NAMES.get(name)
    if mdi is None:
        return QIcon()
    try:
        return _qta.icon(mdi, color=color)
    except Exception:
        return QIcon()


def isize(px: int) -> QSize:
    return QSize(px, px)
