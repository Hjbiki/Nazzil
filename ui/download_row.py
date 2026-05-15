# -*- coding: utf-8 -*-
"""One download row widget. Wraps a DownloadItem and subscribes to its
Signals."""

import io
import os
import threading

from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu,
                               QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from config import THUMB_H, THUMB_W
from i18n import t
from ui.theme import (BORDER, ERR, OK, WARN, TEXT_MUTED)
from utils import (fetch_image_bytes, fmt_duration, human_size,
                   open_file_with_default_app, open_in_explorer,
                   reveal_in_explorer, truncate)


class _ThumbLoader(QObject):
    """Tiny QObject so we can emit a Signal from a worker thread to deliver
    the decoded thumbnail bytes back to the main thread."""
    loaded = Signal(bytes, int, int)

    def fetch(self, url, w, h):
        def run():
            data = fetch_image_bytes(url)
            if not data:
                return
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB")
                src_w, src_h = img.size
                scale = max(w / src_w, h / src_h)
                ns = (int(src_w * scale), int(src_h * scale))
                img = img.resize(ns, Image.LANCZOS)
                left = (ns[0] - w) // 2
                top  = (ns[1] - h) // 2
                img = img.crop((left, top, left + w, top + h))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                self.loaded.emit(buf.getvalue(), w, h)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()


class DownloadRow(QFrame):
    """Per-download row widget. Signals from DownloadItem auto-marshal to
    the main thread, so slot methods touch widgets safely."""

    # bubble-up signals so the app can update counts / refresh sort order
    removed = Signal(object)             # emits the DownloadItem

    def __init__(self, item, app, parent=None):
        super().__init__(parent)
        self.setObjectName("DownloadRow")
        self.item = item
        self.app = app
        self.visible = True
        self._thumb_pix = None

        self._build()
        self._connect_signals()
        self._apply_status_visuals()

        if item.thumb_url:
            self._thumb_loader = _ThumbLoader(self)
            self._thumb_loader.loaded.connect(self._on_thumb_loaded)
            self._thumb_loader.fetch(item.thumb_url, THUMB_W, THUMB_H)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 8, 10)
        outer.setSpacing(12)

        # ---- thumbnail box with duration badge ----
        self.thumb_box = QFrame()
        self.thumb_box.setObjectName("ThumbBox")
        self.thumb_box.setFixedSize(THUMB_W, THUMB_H)
        self.thumb_label = QLabel(self.thumb_box)
        self.thumb_label.setFixedSize(THUMB_W, THUMB_H)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        if self.item.duration:
            badge = QLabel(fmt_duration(self.item.duration), self.thumb_box)
            badge.setObjectName("DurationBadge")
            badge.adjustSize()
            badge.move(THUMB_W - badge.width() - 4,
                       THUMB_H - badge.height() - 4)
        outer.addWidget(self.thumb_box, 0, Qt.AlignTop)

        # ---- middle column: title / badges / meta / progress ----
        mid = QVBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(4)

        self.title_label = QLabel(self._display_title())
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setWordWrap(True)
        self.title_label.setCursor(Qt.PointingHandCursor)
        self.title_label.setMaximumHeight(40)
        self.title_label.mousePressEvent = lambda e: self.open_rename()
        mid.addWidget(self.title_label)

        # badges row
        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(6)
        badges.addWidget(self._make_badge(
            "MP3" if self.item.fmt == "mp3" else "MP4"))
        if self.item.fmt == "mp4" and self.item.height:
            badges.addWidget(self._make_badge(f"{self.item.height}p"))
        elif self.item.fmt == "mp3":
            badges.addWidget(self._make_badge(f"{self.item.bitrate}k"))
        badges.addStretch(1)
        mid.addLayout(badges)

        self.meta_label = QLabel(t("row_waiting"))
        self.meta_label.setObjectName("MetaLabel")
        self.meta_label.setWordWrap(False)
        mid.addWidget(self.meta_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        mid.addWidget(self.bar)

        outer.addLayout(mid, 1)

        # ---- right column: kebab + delete ----
        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        actions.setAlignment(Qt.AlignTop)

        row_btns = QHBoxLayout()
        row_btns.setContentsMargins(0, 0, 0, 0)
        row_btns.setSpacing(6)

        self.kebab_btn = QPushButton("⋯")
        self.kebab_btn.setProperty("role", "kebab")
        self.kebab_btn.setCursor(Qt.PointingHandCursor)
        self.kebab_btn.clicked.connect(self._show_kebab_menu)
        row_btns.addWidget(self.kebab_btn)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setProperty("role", "kebabDanger")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.clicked.connect(self.delete)
        row_btns.addWidget(self.delete_btn)

        actions.addLayout(row_btns)
        actions.addStretch(1)

        outer.addLayout(actions, 0)

        # Tooltip for full error text — Qt's native QToolTip
        self.meta_label.setToolTip("")

    def _make_badge(self, text):
        lbl = QLabel(text)
        lbl.setProperty("role", "badge")
        return lbl

    def _display_title(self):
        return truncate(self.item.custom_filename or self.item.title, 120)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self):
        # AutoConnection — when the worker thread emits, slots run on the
        # main thread (this row was created on the main thread).
        self.item.progress_updated.connect(self._on_progress)
        self.item.state_changed.connect(self._apply_status_visuals)

    @Slot(float, str)
    def _on_progress(self, frac, text):
        try:
            self.bar.setValue(int(frac * 1000))
            self.meta_label.setText(text)
            self.meta_label.setProperty("state", "")
            self.meta_label.style().unpolish(self.meta_label)
            self.meta_label.style().polish(self.meta_label)
        except Exception:
            pass

    @Slot()
    def _apply_status_visuals(self):
        try:
            self.title_label.setText(self._display_title())
        except Exception:
            return
        status = self.item.status
        if status == "completed":
            self.bar.setValue(1000)
            size_to_show = self.item.size_on_disk or self.item.size_bytes
            text = (t("row_completed", size=human_size(size_to_show))
                    if size_to_show else t("row_completed_no_size"))
            self._set_meta(text, "ok")
            self.meta_label.setToolTip("")
        elif status == "failed":
            msg = self.item.error_msg or ""
            text = (t("row_failed", msg=msg) if msg
                    else t("row_failed_unknown"))
            self._set_meta(text, "err")
            self.meta_label.setToolTip(msg)
        elif status == "interrupted":
            self._set_meta(t("row_interrupted"), "warn")
            self.meta_label.setToolTip("")
        elif status == "downloading":
            # progress hook drives the meta line
            pass
        else:
            self._set_meta(t("row_waiting"), "")

    def _set_meta(self, text, state):
        self.meta_label.setText(text)
        self.meta_label.setProperty("state", state)
        self.meta_label.style().unpolish(self.meta_label)
        self.meta_label.style().polish(self.meta_label)

    # ------------------------------------------------------------------
    # Thumbnail
    # ------------------------------------------------------------------
    @Slot(bytes, int, int)
    def _on_thumb_loaded(self, png_bytes, w, h):
        pix = QPixmap()
        if pix.loadFromData(png_bytes, "PNG"):
            self._thumb_pix = pix
            self.thumb_label.setPixmap(pix)

    # ------------------------------------------------------------------
    # Filter / matching
    # ------------------------------------------------------------------
    def matches(self, query, tab):
        item = self.item
        if tab == "Video" and item.fmt != "mp4":
            return False
        if tab == "Audio" and item.fmt != "mp3":
            return False
        name = item.custom_filename or item.title or ""
        if query and query.lower() not in name.lower():
            return False
        return True

    def setVisibleRow(self, val):
        self.setVisible(val)
        self.visible = val

    # ------------------------------------------------------------------
    # Kebab menu actions
    # ------------------------------------------------------------------
    def _show_kebab_menu(self):
        menu = QMenu(self)
        item = self.item
        playable = bool(item.filepath and os.path.exists(item.filepath))
        retryable = item.status in ("failed", "interrupted")

        if retryable:
            act = QAction(t("menu_retry"), menu)
            act.triggered.connect(item.retry)
            menu.addAction(act)
            menu.addSeparator()

        a_play = QAction(t("menu_play"), menu)
        a_play.setEnabled(playable)
        a_play.triggered.connect(self._play_file)
        menu.addAction(a_play)

        a_show = QAction(t("menu_show_in_folder"), menu)
        a_show.triggered.connect(self._show_in_folder)
        menu.addAction(a_show)

        a_link = QAction(t("menu_copy_link"), menu)
        a_link.triggered.connect(self._copy_link)
        menu.addAction(a_link)

        a_rename = QAction(t("menu_rename"), menu)
        a_rename.triggered.connect(self.open_rename)
        menu.addAction(a_rename)

        menu.addSeparator()
        a_remove = QAction(t("menu_remove"), menu)
        a_remove.triggered.connect(self.delete)
        menu.addAction(a_remove)

        menu.exec(self.kebab_btn.mapToGlobal(
            self.kebab_btn.rect().bottomLeft()))

    def _play_file(self):
        open_file_with_default_app(self.item.filepath)

    def _show_in_folder(self):
        if self.item.filepath:
            reveal_in_explorer(self.item.filepath)
        else:
            open_in_explorer(self.item.folder)

    def _copy_link(self):
        from PySide6.QtGui import QGuiApplication
        try:
            QGuiApplication.clipboard().setText(self.item.url)
        except Exception:
            pass

    def open_rename(self):
        from ui.dialogs import rename_dialog
        current = self.item.custom_filename or self.item.title
        new_name = rename_dialog(self.window(), current=current)
        if new_name is None:
            return
        new_name = (new_name or "").strip()
        self.item.custom_filename = new_name or None
        self._apply_status_visuals()
        if self.app:
            self.app.save_downloads()

    def delete(self):
        self.item.cancel()
        try:
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass
        self.removed.emit(self.item)
        if self.app:
            self.app.remove_item(self.item)
