# -*- coding: utf-8 -*-
"""Silent, hands-off yt-dlp updater.

The user never sees or touches this. yt-dlp ships BUNDLED inside the app
(PyInstaller embeds the `yt_dlp` package — see nazzil.spec hiddenimports), so
downloads work from the very first launch with no internet and no update.

As a *silent enhancement*, this module keeps yt-dlp fresh on its own:

  • bootstrap()    — called BEFORE `import yt_dlp`. If a newer yt-dlp was
                     cached on a previous run, a tiny meta-path finder makes
                     that cached copy load instead of the bundled one.
  • update_async() — a background daemon thread that, at most once a day,
                     checks PyPI for a newer yt-dlp, downloads its wheel, and
                     unpacks the pure-python `yt_dlp/` package into the cache.
                     Takes effect on the NEXT launch.

Everything is best-effort and dead silent: no UI, no buttons, no messages.
Any failure (offline, etc.) just leaves the current yt-dlp in place.

Frozen-only: the cache shadow + auto-download run only in the built app
(`sys.frozen`). From a source checkout we leave the developer's own
pip-managed yt-dlp untouched.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

_PKG = "yt_dlp"
_CHECK_INTERVAL = 24 * 60 * 60  # at most one PyPI check per day


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------
def _nazzil_local() -> str:
    base = (os.environ.get("LOCALAPPDATA")
            or os.path.join(os.path.expanduser("~"), "AppData", "Local"))
    return os.path.join(base, "Nazzil")


def _cache_dir() -> str:
    """Dir that holds the updated `yt_dlp/` package (added to import path)."""
    return os.path.join(_nazzil_local(), "ytdlp")


def _stamp_path() -> str:
    return os.path.join(_nazzil_local(), "ytdlp_last_check")


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _version_in(pkg_parent: str) -> str:
    """Read __version__ from <pkg_parent>/yt_dlp/version.py without importing."""
    vf = os.path.join(pkg_parent, _PKG, "version.py")
    try:
        with open(vf, "r", encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", txt)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _valid_cache() -> bool:
    d = _cache_dir()
    return (os.path.isfile(os.path.join(d, _PKG, "__init__.py"))
            and bool(_version_in(d)))


# ---------------------------------------------------------------------------
# Version compare (tolerant of yt-dlp's YYYY.MM.DD scheme)
# ---------------------------------------------------------------------------
def _parse(v: str):
    parts = []
    for chunk in str(v or "").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def _is_newer(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


# ---------------------------------------------------------------------------
# bootstrap — make a cached newer yt-dlp win over the bundled one
# ---------------------------------------------------------------------------
class _CacheFinder:
    """Meta-path finder that resolves ONLY the top-level `yt_dlp` package from
    the cache dir. Submodules then load via yt_dlp.__path__ automatically.
    Scoped to a single name so it can never disturb any other import."""

    def __init__(self, cache_dir):
        self._cache = cache_dir

    def find_spec(self, name, path=None, target=None):
        if name != _PKG:
            return None
        try:
            import importlib.machinery as _m
            return _m.PathFinder.find_spec(name, [self._cache])
        except Exception:
            return None


_installed_finder = None


def bootstrap():
    """Call BEFORE importing yt_dlp. Frozen-only: if a valid newer copy is
    cached, route `import yt_dlp` to it. No-op from source or if no cache."""
    global _installed_finder
    if not _is_frozen():
        return
    try:
        if not _valid_cache():
            return
        _installed_finder = _CacheFinder(_cache_dir())
        sys.meta_path.insert(0, _installed_finder)
    except Exception:
        _installed_finder = None


def purge_cache():
    """Self-heal: drop the cache from the import path and delete it. Call if
    `import yt_dlp` ever fails after bootstrap() — the bundled copy then loads."""
    global _installed_finder
    try:
        if _installed_finder in sys.meta_path:
            sys.meta_path.remove(_installed_finder)
    except Exception:
        pass
    _installed_finder = None
    try:
        shutil.rmtree(_cache_dir(), ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Background update
# ---------------------------------------------------------------------------
def _due_for_check() -> bool:
    try:
        last = os.path.getmtime(_stamp_path())
        return (time.time() - last) >= _CHECK_INTERVAL
    except Exception:
        return True  # no stamp yet → check


def _touch_stamp():
    try:
        os.makedirs(_nazzil_local(), exist_ok=True)
        with open(_stamp_path(), "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
    except Exception:
        pass


def _current_version() -> str:
    try:
        import yt_dlp
        return getattr(getattr(yt_dlp, "version", None), "__version__", "") or ""
    except Exception:
        return _version_in(_cache_dir())


def _pypi_latest_wheel():
    """Return (latest_version, wheel_url) from PyPI, or (None, None)."""
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/yt-dlp/json",
            headers={"User-Agent": "Nazzil-ytdlp-updater"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        latest = data["info"]["version"]
        for f in data["releases"].get(latest, []):
            if f.get("filename", "").endswith(".whl"):
                return latest, f.get("url")
    except Exception:
        pass
    return None, None


def _install_wheel(url: str) -> bool:
    """Download the wheel and atomically place its yt_dlp/ package into the
    cache. Returns True on success."""
    parent = _nazzil_local()
    os.makedirs(parent, exist_ok=True)
    tmp_whl = os.path.join(tempfile.gettempdir(), "nazzil_ytdlp.whl")
    staging = tempfile.mkdtemp(prefix="ytdlp_stage_", dir=parent)
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Nazzil-ytdlp-updater"})
        with urllib.request.urlopen(req, timeout=60) as r, \
                open(tmp_whl, "wb") as f:
            shutil.copyfileobj(r, f)

        with zipfile.ZipFile(tmp_whl) as zf:
            for n in zf.namelist():
                # Only the runtime package; skip dist-info / tests.
                if n.startswith(_PKG + "/") and not n.endswith("/"):
                    zf.extract(n, staging)

        # Validate the staged copy before swapping it in.
        if not _version_in(staging):
            return False

        target = os.path.join(_cache_dir(), _PKG)
        os.makedirs(_cache_dir(), exist_ok=True)
        backup = target + ".old"
        shutil.rmtree(backup, ignore_errors=True)
        if os.path.isdir(target):
            os.replace(target, backup)
        try:
            os.replace(os.path.join(staging, _PKG), target)
        except Exception:
            # Restore the previous copy if the swap failed half-way.
            if os.path.isdir(backup) and not os.path.isdir(target):
                os.replace(backup, target)
            return False
        shutil.rmtree(backup, ignore_errors=True)
        return True
    except Exception:
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        try:
            os.remove(tmp_whl)
        except Exception:
            pass


def _run():
    try:
        if not _due_for_check():
            return
        latest, url = _pypi_latest_wheel()
        # Record the check time regardless so we don't re-hit PyPI all day.
        _touch_stamp()
        if not latest or not url:
            return
        if not _is_newer(latest, _current_version()):
            return
        _install_wheel(url)  # silent; takes effect next launch
    except Exception:
        pass  # never surface anything to the user


def update_async():
    """Kick off the silent background check/update. Frozen-only and
    non-blocking — returns immediately."""
    if not _is_frozen():
        return
    threading.Thread(target=_run, daemon=True).start()
