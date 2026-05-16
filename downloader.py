# -*- coding: utf-8 -*-
"""yt-dlp wrapper. UI talks to DownloadItem via Qt Signals — never via
.after() / direct widget calls — so cross-thread updates stay safe."""

import os
import re
import shutil
import threading

from PySide6.QtCore import QObject, Signal
import yt_dlp

from i18n import t
from utils import (clean_error, classify_error, file_size,
                   sanitize_filename)


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
                 bitrate=192, status="queued", filepath="",
                 error_msg="", size_bytes=0, size_on_disk=0,
                 custom_filename=None, parent=None):
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
    # Worker
    # ------------------------------------------------------------------
    def _run(self):
        cookie_opts = self.app._cookie_opts() if self.app else {}
        has_cookies = bool(cookie_opts)
        auto_retried = False

        use_aria2c = bool(self.app.cfg.get("use_aria2c", False)) if self.app else False
        aria2c_available = shutil.which("aria2c") is not None
        if use_aria2c and not aria2c_available:
            self.progress_updated.emit(0, t("row_aria2c_fallback"))
            use_aria2c = False

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
            opts.update(cookie_opts)
            if use_aria2c:
                opts["external_downloader"] = "aria2c"
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
                        "preferredquality": str(self.bitrate or 192),
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
                    with yt_dlp.YoutubeDL(build_opts()) as ydl:
                        ydl.download([self.url])
                    self.status = "completed"
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
            fp = info.get("filepath") or info.get("_filename")
            if fp:
                self.filepath = fp

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
            bitrate=d.get("bitrate", 192),
            custom_filename=d.get("custom_filename"),
        )
