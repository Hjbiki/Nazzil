# -*- coding: utf-8 -*-
"""yt-dlp wrapper. UI talks to DownloadItem via Qt Signals — never via
.after() / direct widget calls — so cross-thread updates stay safe."""

import os
import re
import threading
from datetime import datetime
from urllib.parse import urlparse

from PySide6.QtCore import QObject, Signal
import yt_dlp

import binaries
from i18n import t
from utils import (clean_error, classify_error, file_size,
                   sanitize_filename)


def _domain_from_url(url):
    """Return the bare hostname (no `www.`) or "" if unparseable."""
    if not url:
        return ""
    try:
        netloc = urlparse(url).netloc or ""
    except Exception:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.lower()


class CancelledDownload(Exception):
    """Raised from inside the progress hook to abort yt-dlp cleanly."""


class DownloadItem(QObject):
    """State + worker thread for one download.

    Signals (all auto-marshal to the receiving thread):
        progress_updated(float frac, str text)
        state_changed()                         # status / error / filepath changed
        download_started()
        download_finished()                     # always — success or failure
    """

    progress_updated = Signal(float, str)
    state_changed = Signal()
    download_started = Signal()
    download_finished = Signal()

    def __init__(self, url, fmt, height, info, folder, *,
                 bitrate=320, status="queued", filepath="",
                 error_msg="", size_bytes=0, size_on_disk=0,
                 custom_filename=None, added_at=None,
                 extractor=None, webpage_url_domain=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.fmt = fmt                  # "mp4" or "mp3"
        self.height = height            # int height (mp4) or None
        self.bitrate = bitrate          # int kbps (mp3)
        self.info = info or {}
        self.title = self.info.get("title") or url
        self.duration = self.info.get("duration") or 0
        self.thumb_url = self.info.get("thumbnail") or ""
        self.uploader = (self.info.get("uploader")
                         or self.info.get("channel")
                         or self.info.get("uploader_id")
                         or "")
        self.folder = folder
        self.status = status            # queued/downloading/completed/failed/interrupted
        self.filepath = filepath
        self.error_msg = error_msg
        self.size_bytes = size_bytes
        self.size_on_disk = size_on_disk
        self.custom_filename = custom_filename

        # ---- Source-tag inputs ----
        # `extractor` arrives from yt-dlp's info dict (e.g. "youtube",
        # "vimeo", "twitter", "generic"). If callers pass it explicitly
        # (from_dict, playlist add path), honour that. Otherwise pull
        # from info.
        if extractor is None:
            extractor = self.info.get("extractor") or ""
        self.extractor = (extractor or "").lower()
        if webpage_url_domain is None:
            page_url = (self.info.get("webpage_url")
                        or self.info.get("original_url")
                        or url)
            webpage_url_domain = _domain_from_url(page_url)
        self.webpage_url_domain = webpage_url_domain or ""

        # ISO timestamp at row creation. Stable across restarts so
        # "Date added" sort matches the order rows entered the session.
        self.added_at = added_at or datetime.now().isoformat()

        self.last_updated = 0
        self.cancelled = False
        self.app = None  # set by App for cookie opts + persistence

        self._worker = None

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------
    def start(self):
        if self.status == "downloading":
            return
        self.cancelled = False
        self.status = "downloading"
        self.error_msg = ""
        self.state_changed.emit()
        if self.app is not None:
            self.app.save_downloads()
            self.app.on_download_started()
        self.download_started.emit()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def retry(self):
        self._cleanup_partials()
        self.start()

    def cancel(self):
        self.cancelled = True

    # ------------------------------------------------------------------
    # File-name helpers
    # ------------------------------------------------------------------
    def _outtmpl(self):
        if self.custom_filename:
            safe = sanitize_filename(self.custom_filename)
            return os.path.join(self.folder, f"{safe}.%(ext)s")
        return os.path.join(self.folder, "%(title)s.%(ext)s")

    def expected_filename(self):
        title = self.custom_filename or self.title
        safe = sanitize_filename(title)
        ext = "mp3" if self.fmt == "mp3" else "mp4"
        return os.path.join(self.folder, f"{safe}.{ext}")

    def _cleanup_partials(self):
        """Delete leftover .part / .part-Frag* / .ytdl files for this item."""
        folder = self.folder
        if not folder or not os.path.isdir(folder):
            return

        def looks_partial(name):
            return (name.endswith(".part") or name.endswith(".ytdl")
                    or ".part-Frag" in name)

        stem = None
        if self.filepath:
            base = self.filepath
            for suf in (".part", ".ytdl"):
                if base.endswith(suf):
                    base = base[:-len(suf)]
                    break
            stem = os.path.splitext(base)[0]
        title_key = re.sub(r"\W+", "",
                           self.custom_filename or self.title)[:20].lower()

        try:
            for fname in os.listdir(folder):
                if not looks_partial(fname):
                    continue
                fp = os.path.join(folder, fname)
                matched = False
                if stem and fp.startswith(stem):
                    matched = True
                elif title_key and len(title_key) >= 4:
                    name_key = re.sub(r"\W+", "", fname).lower()
                    if title_key in name_key:
                        matched = True
                if matched:
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Path resolution after download (size_on_disk source of truth)
    # ------------------------------------------------------------------
    def _resolve_final_path(self, info):
        """Find the actual merged/post-processed file on disk after
        extract_info(download=True) returns.

        Sources, in priority order:
          1. info['requested_downloads'][-1]['filepath'] — yt-dlp's
             canonical list of FINAL outputs after all PPs (Merger,
             ExtractAudio, EmbedThumbnail, FFmpegMetadata) finished.
          2. info['filepath'] / info['_filename'] — set when there's
             no PP chain (single-stream download).
          3. self.filepath — captured by our hooks during the download.
          4. self.expected_filename() — predicted from title + ext.
          5. self._find_output_file() — last-ditch folder scan.

        Returns a verified existing path, or "" if none found."""
        candidates = []
        if isinstance(info, dict):
            reqs = info.get("requested_downloads") or []
            # Walk in reverse so the LAST PP's output (the final file) wins.
            for req in reversed(reqs):
                fp = req.get("filepath") or req.get("_filename")
                if fp:
                    candidates.append(fp)
            for key in ("filepath", "_filename"):
                fp = info.get(key)
                if fp:
                    candidates.append(fp)
        if self.filepath:
            candidates.append(self.filepath)
        candidates.append(self.expected_filename())

        for fp in candidates:
            if fp and os.path.exists(fp) and os.path.isfile(fp):
                return fp

        # Final fallback — scan folder for the most-recent matching file.
        scanned = self._find_output_file()
        if scanned and os.path.exists(scanned):
            return scanned
        return ""

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------
    def _run(self):
        cookie_opts = self.app._cookie_opts() if self.app else {}
        has_cookies = bool(cookie_opts)
        auto_retried = False

        use_aria2c = bool(self.app.cfg.get("use_aria2c", False)) if self.app else False
        # aria2c ships bundled with the app (binaries.aria2c_path); fall back
        # silently to the default downloader if for some reason it isn't
        # present. No user-facing "not found" message — that's our problem,
        # not theirs.
        aria2c_exe = binaries.aria2c_path()
        if use_aria2c and not aria2c_exe:
            use_aria2c = False

        # ffmpeg / ffprobe are bundled too. Hand yt-dlp the directory so its
        # post-processors (Merger / ExtractAudio / EmbedThumbnail / Metadata)
        # use our copy instead of relying on the system PATH.
        ffmpeg_dir = binaries.ffmpeg_dir()

        def build_opts():
            opts = {
                "outtmpl": self._outtmpl(),
                "progress_hooks": [self._hook],
                "postprocessor_hooks": [self._pp_hook],
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": False,
                "continuedl": True,
                "retries": 5,
                "fragment_retries": 5,
            }
            if ffmpeg_dir:
                opts["ffmpeg_location"] = ffmpeg_dir
            opts.update(cookie_opts)
            if use_aria2c:
                # Point yt-dlp at the bundled aria2c binary explicitly.
                opts["external_downloader"] = {"default": aria2c_exe}
                opts["external_downloader_args"] = {
                    "aria2c": ["-x", "16", "-s", "16", "-k", "1M",
                               "--summary-interval=1",
                               "--console-log-level=warn"],
                }
            if self.fmt == "mp3":
                opts["format"] = "bestaudio/best"
                opts["writethumbnail"] = True
                opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(self.bitrate or 320),
                    },
                    {"key": "FFmpegMetadata", "add_metadata": True},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False},
                ]
            else:
                h = self.height or 1080
                opts["format"] = (
                    f"bv*[height<={h}]+ba/"
                    f"b[height<={h}]/"
                    f"bv*+ba/"
                    f"best"
                )
                opts["format_sort"] = [f"res:{h}", "ext:mp4:m4a", "codec:h264"]
                opts["merge_output_format"] = "mp4"
            return opts

        try:
            while True:
                try:
                    # Use extract_info(download=True) — unlike download(),
                    # this RETURNS the populated info dict containing
                    # `requested_downloads`, which lists every final
                    # on-disk file path after all post-processors ran.
                    with yt_dlp.YoutubeDL(build_opts()) as ydl:
                        info = ydl.extract_info(self.url, download=True)
                    self.status = "completed"

                    # ---- Refresh source-tag fields from the live info ----
                    # Playlist entries built via `extract_flat` arrive without
                    # `extractor`, so wait until we actually download to fill
                    # them in. The user-visible source pill renders from
                    # whatever's set here.
                    live_extractor = (info.get("extractor") or "").lower() \
                        if isinstance(info, dict) else ""
                    if live_extractor:
                        self.extractor = live_extractor
                    live_page = (info.get("webpage_url")
                                 or info.get("original_url")
                                 or self.url) if isinstance(info, dict) else self.url
                    live_domain = _domain_from_url(live_page)
                    if live_domain:
                        self.webpage_url_domain = live_domain

                    # ---- Resolve the actual on-disk output file ----
                    # The progress hook's `total_bytes` is the size of ONE
                    # stream (audio or video, never the merged result),
                    # so we MUST read the real file size from disk.
                    final_fp = self._resolve_final_path(info)
                    if final_fp:
                        self.filepath = final_fp
                    if self.filepath and os.path.exists(self.filepath):
                        self.size_on_disk = file_size(self.filepath)
                    self.state_changed.emit()
                    break
                except CancelledDownload:
                    return
                except Exception as e:
                    if self.cancelled:
                        return
                    raw = str(e)
                    low = raw.lower()
                    is_416 = ("http error 416" in low
                              or "requested range not satisfiable" in low)
                    if is_416 and not auto_retried:
                        auto_retried = True
                        self._cleanup_partials()
                        self.progress_updated.emit(0, t("row_stale_offset"))
                        continue
                    self.status = "failed"
                    self.error_msg = classify_error(raw, has_cookies)
                    self.state_changed.emit()
                    break
        finally:
            self.download_finished.emit()
            if self.app is not None:
                self.app.on_download_finished_signal_emit()

    # ------------------------------------------------------------------
    # yt-dlp hooks
    # ------------------------------------------------------------------
    def _hook(self, d):
        if self.cancelled:
            raise CancelledDownload()
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed")
            eta = d.get("eta")
            frac = (downloaded / total) if total else 0
            self.size_bytes = total or self.size_bytes
            self.last_updated += 1
            from utils import human_size, fmt_eta
            size_txt = human_size(total) if total else "?"
            done_txt = human_size(downloaded) if downloaded else "0 B"
            speed_txt = f"{human_size(speed)}/s" if speed else "…"
            eta_txt = fmt_eta(eta) if eta else ""
            parts = [f"{done_txt} / {size_txt}", speed_txt]
            if eta_txt:
                parts.append(eta_txt)
            self.progress_updated.emit(frac, " · ".join(parts))
        elif status == "finished":
            fn = d.get("filename")
            if fn:
                self.filepath = fn
            self.progress_updated.emit(1, t("row_merging"))

    def _pp_hook(self, d):
        if d.get("status") == "finished":
            info = d.get("info_dict") or {}
            # The most reliable source for the FINAL on-disk path is
            # `requested_downloads`, populated by yt-dlp after every
            # post-processor (Merge, ExtractAudio, EmbedThumbnail, …)
            # has run. Walk it last so we keep the most recent path.
            for req in info.get("requested_downloads") or []:
                req_fp = req.get("filepath") or req.get("_filename")
                if req_fp:
                    self.filepath = req_fp
            # Fall back to whatever the top-level info_dict carries.
            if not self.filepath:
                fp = info.get("filepath") or info.get("_filename")
                if fp:
                    self.filepath = fp

    def _find_output_file(self):
        """Last-ditch scan: pick the most-recently-modified file in `folder`
        whose name shares a long-enough prefix with our title (sanitised).
        Strips both `\\W` AND underscores so 'My Cool Video' matches
        'My_Cool_Video.mp4' (yt-dlp commonly substitutes spaces with `_`)."""
        folder = self.folder
        if not folder or not os.path.isdir(folder):
            return ""
        title_key = re.sub(r"[\W_]+", "",
                           self.custom_filename or self.title)[:20].lower()
        if not title_key or len(title_key) < 4:
            return ""
        target_ext = ".mp3" if self.fmt == "mp3" else ".mp4"
        candidates = []
        try:
            for fname in os.listdir(folder):
                if not fname.lower().endswith(target_ext):
                    continue
                if fname.endswith(".part") or fname.endswith(".ytdl"):
                    continue
                name_key = re.sub(r"[\W_]+", "", fname).lower()
                if title_key in name_key:
                    fp = os.path.join(folder, fname)
                    try:
                        candidates.append((os.path.getmtime(fp), fp))
                    except Exception:
                        continue
        except Exception:
            return ""
        if not candidates:
            return ""
        candidates.sort(reverse=True)
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self):
        status = self.status
        if status in ("downloading", "queued"):
            status = "interrupted"
        return {
            "url": self.url,
            "title": self.title,
            "uploader": self.uploader,
            "fmt": self.fmt,
            "height": self.height,
            "bitrate": self.bitrate,
            "thumbnail": self.thumb_url,
            "duration": self.duration,
            "status": status,
            "folder": self.folder,
            "filepath": self.filepath,
            "error_msg": self.error_msg,
            "size_bytes": self.size_bytes,
            "size_on_disk": self.size_on_disk,
            "custom_filename": self.custom_filename,
            "added_at": self.added_at,
            "extractor": self.extractor,
            "webpage_url_domain": self.webpage_url_domain,
        }

    @classmethod
    def from_dict(cls, d):
        info = {
            "title": d.get("title", ""),
            "thumbnail": d.get("thumbnail", ""),
            "duration": d.get("duration", 0),
            "uploader": d.get("uploader", ""),
        }
        status = d.get("status", "interrupted")
        if status in ("downloading", "queued"):
            status = "interrupted"
        # Back-compat: old sessions stored no extractor. Their rows are
        # almost certainly YouTube (everything pre-1.4 was YouTube-only),
        # so assume that rather than rendering a blank tag.
        extractor = d.get("extractor")
        if extractor is None:
            extractor = "youtube"
        domain = d.get("webpage_url_domain")
        if domain is None:
            domain = _domain_from_url(d.get("url", ""))
        return cls(
            url=d.get("url", ""),
            fmt=d.get("fmt", "mp4"),
            height=d.get("height"),
            info=info,
            folder=d.get("folder", ""),
            status=status,
            filepath=d.get("filepath", ""),
            error_msg=d.get("error_msg", ""),
            size_bytes=d.get("size_bytes", 0),
            size_on_disk=d.get("size_on_disk", 0),
            bitrate=d.get("bitrate", 320),
            custom_filename=d.get("custom_filename"),
            added_at=d.get("added_at"),
            extractor=extractor,
            webpage_url_domain=domain,
        )
