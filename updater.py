# -*- coding: utf-8 -*-
"""Self-update over GitHub releases.

Components:
    UpdateChecker     — background thread, queries the latest release
                        and emits update_available(tag, asset_url, size)
                        if newer than APP_VERSION.
    UpdateDownloader  — background thread, downloads the .exe asset to a
                        temp file, emitting progress(0..1) and
                        download_done(local_path).
    launch_updater()  — writes a tiny .bat script that waits, replaces
                        the running exe, restarts it, then self-deletes.

The whole flow is best-effort and silent: network errors, rate limits, and
malformed responses just dismiss the banner without surfacing anything to
the user."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, Signal

from config import APP_VERSION, GITHUB_REPO, GITHUB_TOKEN


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------
def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def current_exe_path() -> str:
    """Path to the currently running executable when frozen, else ''."""
    return sys.executable if is_frozen() else ""


def github_release_url() -> str:
    return f"https://github.com/{GITHUB_REPO}/releases/latest"


# ---------------------------------------------------------------------------
# Version comparison — tolerant of "v1.2.3", "1.2.3-beta", "1.2", etc.
# ---------------------------------------------------------------------------
def parse_version(tag: str):
    """Return a normalised 3-tuple of ints: (major, minor, patch).

    Tolerates a leading 'v', drops pre-release / build suffixes
    ('1.2.3-beta', '1.2.3+build7' → (1, 2, 3)), and zero-pads short
    versions ('1.2' → (1, 2, 0)) so comparison is well-defined."""
    if not tag:
        return (0, 0, 0)
    s = tag.strip().lstrip("vV")
    # Drop anything after '-' / '+' / whitespace (pre-release / build meta).
    for sep in ("-", "+", " "):
        if sep in s:
            s = s.split(sep, 1)[0]
    parts = []
    for chunk in s.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote_tag: str, local_version: str) -> bool:
    """True iff remote is strictly greater than local. Same version → False."""
    return parse_version(remote_tag) > parse_version(local_version)


# ---------------------------------------------------------------------------
# GitHub REST
# ---------------------------------------------------------------------------
def _http_headers():
    h = {"User-Agent": "Nazzil-Updater",
         "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _api_get(url: str, timeout: int = 10) -> dict:
    """GET a GitHub API endpoint with a 10 s timeout + UA + optional token."""
    req = urllib.request.Request(url, headers=_http_headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def find_exe_asset(release: dict):
    """Pick the portable .exe asset (not the installer).

    Rule: name contains 'Nazzil', ends with '.exe', does NOT contain 'Setup'.
    Returns (url, size, name) or (None, 0, '')."""
    for a in release.get("assets") or []:
        name = (a.get("name") or "")
        low = name.lower()
        if not low.endswith(".exe"):
            continue
        if "setup" in low:
            continue
        if "nazzil" not in low:
            continue
        return (a.get("browser_download_url"),
                int(a.get("size") or 0),
                name)
    return None, 0, ""


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
class UpdateChecker(QObject):
    """Background check for a newer release. All signals are emitted from a
    worker thread; Qt's queued connections marshal them to the main thread."""

    update_available = Signal(str, str, int)   # tag, asset_url, size_bytes
    no_update = Signal()
    check_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            data = _api_get(url, timeout=10)
            tag = data.get("tag_name", "")
            if not tag or not is_newer(tag, APP_VERSION):
                self.no_update.emit()
                return
            asset_url, size, _name = find_exe_asset(data)
            self.update_available.emit(tag, asset_url or "", size)
        except urllib.error.HTTPError as e:
            # 403 = rate-limit, 404 = bad repo/no releases yet
            print(f"[updater] HTTP {e.code} from {url}: {e.reason}",
                  file=sys.stderr)
            self.check_failed.emit(f"HTTP {e.code}")
        except urllib.error.URLError as e:
            # DNS / connection refused / timeout
            print(f"[updater] network error: {e.reason}", file=sys.stderr)
            self.check_failed.emit(str(e.reason)[:120])
        except Exception as e:
            print(f"[updater] check failed: {e!r}", file=sys.stderr)
            self.check_failed.emit(str(e)[:120])


class UpdateDownloader(QObject):
    """Stream the .exe asset into a temp file."""

    progress = Signal(float)         # 0.0 .. 1.0
    download_done = Signal(str)      # local path
    download_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def start(self, asset_url: str):
        threading.Thread(target=self._run, args=(asset_url,),
                         daemon=True).start()

    def _run(self, asset_url: str):
        try:
            tmp_path = os.path.join(tempfile.gettempdir(),
                                    "Nazzil_update.exe")
            req = urllib.request.Request(asset_url, headers=_http_headers())
            with urllib.request.urlopen(req, timeout=30) as r:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        if self._cancelled:
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass
                            return
                        chunk = r.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total:
                            self.progress.emit(got / total)
            self.progress.emit(1.0)
            self.download_done.emit(tmp_path)
        except Exception as e:
            self.download_failed.emit(str(e)[:120])


# ---------------------------------------------------------------------------
# Self-replace
# ---------------------------------------------------------------------------
def write_updater_script(downloaded_path: str, exe_path: str) -> str:
    """Emit a .bat that waits, swaps the exe, relaunches, self-deletes.
    Returns the path to the .bat file."""
    bat = os.path.join(tempfile.gettempdir(), "nazzil_update.bat")
    content = (
        "@echo off\r\n"
        "timeout /t 3 /nobreak >nul\r\n"
        f'move /y "{downloaded_path}" "{exe_path}"\r\n'
        f'start "" "{exe_path}"\r\n'
        'del "%~f0"\r\n'
    )
    with open(bat, "w", encoding="utf-8") as f:
        f.write(content)
    return bat


def launch_updater(downloaded_path: str, exe_path: str) -> None:
    """Write + spawn the updater.bat detached so it survives our exit."""
    bat = write_updater_script(downloaded_path, exe_path)
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP on Windows
    creationflags = 0x00000008 | 0x00000200 if sys.platform.startswith("win") else 0
    subprocess.Popen(
        ["cmd.exe", "/c", bat] if sys.platform.startswith("win")
        else ["/bin/sh", bat],
        creationflags=creationflags,
        close_fds=True,
    )
