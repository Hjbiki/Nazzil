# -*- coding: utf-8 -*-
"""Bundled external tools — ffmpeg / ffprobe / aria2c.

Goal: ZERO install for the end user. The app never asks the user to install
or download any external tool. Tools are resolved (READ-ONLY) in this order,
returning the first that exists:

    1. <_MEIPASS>/assets/bin/<tool>.exe     — if embedded in the one-file exe
                                              (not the default; see the spec).
    2. <exe_dir>/assets/bin/<tool>.exe      — where NazzilSetup.exe installs
                                              them, beside the installed exe.
    3. <package>/assets/bin/<tool>.exe      — running from source / dev.
    4. %LOCALAPPDATA%/Nazzil/bin/<tool>.exe — user cache (silent-download tgt).
    5. system PATH (shutil.which)           — last-resort courtesy lookup.

SAFETY: resolution only READS. This module NEVER modifies PATH and NEVER
writes, moves, or deletes any file on PATH or any ffmpeg the user installed
themselves. The only files it ever writes are a temp zip in %TEMP% and the
extracted exes inside its own cache (%LOCALAPPDATA%/Nazzil/bin).

On startup `ensure_binaries_async()` checks (1)-(4) and, if anything is
missing, silently downloads the official Windows builds into the user cache
only. Best-effort and non-blocking — on failure the resolvers fall through
to PATH (read-only) as a courtesy.
"""

import os
import shutil
import sys
import threading
import zipfile
import tempfile
import urllib.request


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
def resource_root() -> str:
    """Directory that holds bundled resources.

    Frozen (PyInstaller one-file): sys._MEIPASS — the temp extract dir that
    also contains any assets/ tree declared in nazzil.spec.
    From source: the directory this module lives in (the package root)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    return os.path.dirname(os.path.abspath(__file__))


def _bundled_dirs():
    """Every place the app's bundled tools might live, most-specific first.

      1. <_MEIPASS>/assets/bin    — if nazzil.spec embedded them (not the
         default: the portable exe is kept lean, see the spec).
      2. <exe_dir>/assets/bin     — where NazzilSetup.exe drops them next to
         the installed Nazzil.exe. THIS is the primary path for installed
         users → fully offline after one install.
      3. <package>/assets/bin     — running from source / dev.
    """
    dirs = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.append(os.path.join(meipass, "assets", "bin"))
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)),
                                 "assets", "bin"))
    dirs.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "bin"))
    return dirs


# Primary bundled dir — used by fetch_binaries.py (dev/build target) and as
# the canonical "where we ship them" reference.
BUNDLED_BIN_DIR = os.path.join(resource_root(), "assets", "bin")


def user_bin_dir() -> str:
    """Writable per-user cache for runtime-downloaded tools."""
    base = (os.environ.get("LOCALAPPDATA")
            or os.path.join(os.path.expanduser("~"), "AppData", "Local"))
    path = os.path.join(base, "Nazzil", "bin")
    return path


# Tool name (no extension) -> windows exe filename
_EXE = ".exe" if sys.platform.startswith("win") else ""


def _exe_name(tool: str) -> str:
    return f"{tool}{_EXE}"


def _find(tool: str) -> str:
    """Resolve a tool path: bundled (incl. installed beside the exe) → user
    cache → PATH (last resort only). Returns "" if none found.

    PATH is never the primary strategy (and we never ask the user to install
    anything); it's just a final courtesy fallback for a dev box that happens
    to have the tool already."""
    fname = _exe_name(tool)
    for d in _bundled_dirs() + [user_bin_dir()]:
        cand = os.path.join(d, fname)
        if os.path.isfile(cand):
            return cand
    found = shutil.which(tool)
    return found or ""


# ---------------------------------------------------------------------------
# Public resolvers (cached after first lookup that succeeds)
# ---------------------------------------------------------------------------
_cache = {}


def _resolve(tool: str) -> str:
    path = _find(tool)
    if path:
        _cache[tool] = path
    return path


def ffmpeg_path() -> str:
    return _cache.get("ffmpeg") or _resolve("ffmpeg")


def ffprobe_path() -> str:
    return _cache.get("ffprobe") or _resolve("ffprobe")


def aria2c_path() -> str:
    return _cache.get("aria2c") or _resolve("aria2c")


def ffmpeg_dir() -> str:
    """Directory containing ffmpeg (and ideally ffprobe) — this is what we
    hand to yt-dlp's `ffmpeg_location`. yt-dlp accepts a directory and finds
    both ffmpeg and ffprobe inside it. Returns "" if ffmpeg isn't found."""
    p = ffmpeg_path()
    return os.path.dirname(p) if p else ""


def have_ffmpeg() -> bool:
    return bool(ffmpeg_path())


def have_aria2c() -> bool:
    return bool(aria2c_path())


# ---------------------------------------------------------------------------
# Silent runtime download
# ---------------------------------------------------------------------------
# Official Windows x64 builds. Each entry lists the archive URL plus the
# basenames we want to extract (matched anywhere inside the zip).
_DOWNLOADS = {
    "ffmpeg": {
        # gyan.dev ESSENTIALS build — ~80 MB total (not the 388 MB static
        # GPL build). Stable URL on gyan's own server. Essentials fully
        # supports MP4 merge + MP3 extraction, which is all Nazzil needs.
        # We pull ONLY ffmpeg.exe + ffprobe.exe (ffplay.exe is never
        # extracted) since `members` lists just those two.
        "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "members": ("ffmpeg.exe", "ffprobe.exe"),
    },
    "aria2c": {
        "url": ("https://github.com/aria2/aria2/releases/download/"
                "release-1.37.0/aria2-1.37.0-win-64bit-build1.zip"),
        "members": ("aria2c.exe",),
    },
}


def _download_archive(url: str, members, dest_dir: str) -> bool:
    """Download `url`, extract the listed basenames into `dest_dir`.
    Returns True if at least one member was extracted."""
    os.makedirs(dest_dir, exist_ok=True)
    wanted = {m.lower() for m in members}
    got = False
    tmp_zip = os.path.join(tempfile.gettempdir(),
                           "nazzil_" + os.path.basename(url))
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Nazzil-Setup"})
        with urllib.request.urlopen(req, timeout=60) as r, \
                open(tmp_zip, "wb") as f:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(tmp_zip) as zf:
            for info in zf.infolist():
                base = os.path.basename(info.filename).lower()
                if base in wanted:
                    target = os.path.join(dest_dir,
                                          os.path.basename(info.filename))
                    with zf.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    got = True
    except Exception:
        return False
    finally:
        try:
            os.remove(tmp_zip)
        except Exception:
            pass
    return got


def _ensure_worker(on_done=None):
    dest = user_bin_dir()
    # ffmpeg + ffprobe travel together in one archive.
    if not (have_ffmpeg() and ffprobe_path()):
        if _download_archive(_DOWNLOADS["ffmpeg"]["url"],
                              _DOWNLOADS["ffmpeg"]["members"], dest):
            _cache.pop("ffmpeg", None)
            _cache.pop("ffprobe", None)
    if not have_aria2c():
        if _download_archive(_DOWNLOADS["aria2c"]["url"],
                             _DOWNLOADS["aria2c"]["members"], dest):
            _cache.pop("aria2c", None)
    if on_done is not None:
        try:
            on_done(have_ffmpeg(), have_aria2c())
        except Exception:
            pass


def ensure_binaries_async(on_done=None):
    """Kick off a silent background check/download of the external tools.

    Returns immediately. If everything is already present, the worker exits
    almost instantly. Only ever downloads into the user cache dir, which is
    always writable (unlike a Program Files install)."""
    # Fast path — nothing to do, don't even spawn a thread.
    if have_ffmpeg() and ffprobe_path() and have_aria2c():
        if on_done is not None:
            try:
                on_done(True, True)
            except Exception:
                pass
        return
    threading.Thread(target=_ensure_worker, args=(on_done,),
                     daemon=True).start()
