# -*- coding: utf-8 -*-
"""App-wide constants, paths, and config file I/O. No UI."""

import json
import os
import re


# ---------------------------------------------------------------------------
# App identity / release metadata
# ---------------------------------------------------------------------------
def _read_version():
    """Single source of truth — read the project's VERSION file.

    Works both from source (file next to config.py) and from a PyInstaller
    one-file bundle (file extracted to sys._MEIPASS, which is also the dir
    config.py is loaded from)."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "VERSION")
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except Exception:
        pass
    return "0.0.0"


APP_VERSION = _read_version()
GITHUB_REPO = "Hjbiki/Nazzil"
# Set to a personal-access-token string for private-repo testing.
# Leave empty for public releases (no auth header sent).
GITHUB_TOKEN = ""


# ---------------------------------------------------------------------------
# Paths — keep existing filenames so old user configs migrate cleanly.
# ---------------------------------------------------------------------------
CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".yt_downloader_config.json")
DOWNLOADS_PATH = os.path.join(
    os.path.expanduser("~"), ".yt_downloader_downloads.json")

# Default language: Arabic (per spec).
DEFAULT_LANG = "ar"


# ---------------------------------------------------------------------------
# URL recognisers
# ---------------------------------------------------------------------------
YT_URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?"
    r"(?:youtube\.com/(?:watch\?v=|shorts/|live/|playlist\?list=)|youtu\.be/)"
    r"[\w\-]+",
    re.IGNORECASE)
YT_PLAYLIST_RE = re.compile(
    r"https?://(?:www\.|m\.)?youtube\.com/playlist\?list=[\w\-]+",
    re.IGNORECASE)


# ---------------------------------------------------------------------------
# Cookie modes — internal key + i18n label key
# ---------------------------------------------------------------------------
COOKIE_MODES = [
    ("none",    "cookie_none"),
    ("file",    "cookie_file"),
    ("firefox", "cookie_firefox"),
    ("brave",   "cookie_brave"),
    ("chrome",  "cookie_chrome"),
    ("edge",    "cookie_edge"),
]


# ---------------------------------------------------------------------------
# Image sizes (the colour tokens live in ui/theme.py now).
# ---------------------------------------------------------------------------
THUMB_W, THUMB_H = 140, 80
PREVIEW_W, PREVIEW_H = 200, 113


# ---------------------------------------------------------------------------
# Config file I/O
# ---------------------------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
