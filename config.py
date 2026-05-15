# -*- coding: utf-8 -*-
"""App-wide constants, paths, and config file I/O. No UI."""

import json
import os
import re


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
