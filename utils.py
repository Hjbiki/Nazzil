# -*- coding: utf-8 -*-
"""Pure helpers — no UI, no Qt. Error classification uses the translator
so the user sees messages in their selected language."""

import os
import re
import subprocess
import sys
import urllib.request

from i18n import t

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

AUTH_KEYWORDS = (
    "members-only", "join this channel", "private video", "sign in",
    "login required", "this video is private", "members only",
    "confirm your age", "age-restricted",
)


# ---------------------------------------------------------------------------
# Numbers / strings
# ---------------------------------------------------------------------------
def human_size(num):
    if not num:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def fmt_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_eta(seconds):
    """Render an ETA in plain language. Uses i18n strings."""
    if seconds is None or seconds < 0:
        return ""
    s = int(seconds)
    if s < 60:
        return t("eta_seconds", n=s)
    m, sec = divmod(s, 60)
    if m < 60:
        return (t("eta_minutes", m=m, s=sec) if sec
                else t("eta_minutes_only", m=m))
    h, m = divmod(m, 60)
    return t("eta_hours", h=h, m=m) if m else t("eta_hours_only", h=h)


def truncate(text, n):
    if not text:
        return ""
    return text if len(text) <= n else text[:n - 1] + "…"


# ---------------------------------------------------------------------------
# File / system
# ---------------------------------------------------------------------------
def open_in_explorer(path):
    """Open a folder in the OS file manager."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def reveal_in_explorer(filepath):
    """Reveal a specific file in the OS file manager."""
    try:
        if not filepath or not os.path.exists(filepath):
            folder = os.path.dirname(filepath) if filepath else ""
            if folder and os.path.isdir(folder):
                open_in_explorer(folder)
            return
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(filepath)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", filepath])
        else:
            open_in_explorer(os.path.dirname(filepath))
    except Exception:
        pass


def open_file_with_default_app(path):
    try:
        if not path or not os.path.exists(path):
            return False
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def file_size(path):
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
def clean_error(text):
    if not text:
        return ""
    text = ANSI_RE.sub("", text)
    text = text.replace("ERROR:", "").strip()
    text = text.split("\n")[0]
    return text[:90] + ("…" if len(text) > 90 else "")


def classify_error(raw, has_cookies):
    raw = ANSI_RE.sub("", raw or "")
    low = raw.lower()
    if "could not copy" in low and "cookie" in low:
        return t("err_cookie_db_unreadable")
    if "database is locked" in low:
        return t("err_cookie_db_locked")
    if any(k in low for k in AUTH_KEYWORDS):
        return t("err_auth_with_cookies") if has_cookies else t("err_auth_no_cookies")
    if "http error 416" in low or "requested range not satisfiable" in low:
        return t("err_416")
    return clean_error(raw)


# ---------------------------------------------------------------------------
# Network — thumbnail fetch
# ---------------------------------------------------------------------------
def fetch_image_bytes(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# YouTube URL parsing + filename sanitisation
# ---------------------------------------------------------------------------
_VIDEO_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/shorts/|/live/|/embed/)([\w\-]{6,})", re.IGNORECASE)


def extract_video_id(url):
    if not url:
        return ""
    m = _VIDEO_ID_RE.search(url)
    return m.group(1) if m else url


_INVALID_FN_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name):
    if not name:
        return ""
    name = _INVALID_FN_CHARS.sub("#", name)
    name = name.strip().strip(".")
    return name[:200]
