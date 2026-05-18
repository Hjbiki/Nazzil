# -*- coding: utf-8 -*-
"""Compact download row — Linear-style desktop mockup layout.

Structure (single row, 64-72 px tall):

    ┌──────────────────────────────────────────────────────────────────┐
    │ [thumb 72×46]  Title …                                  [act][⋯] │
    │     ⏱ 4:32     [YouTube] Channel · [MP4·1080p] 12 MB · 2 MB/s    │
    │  ────────────  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  progress 2 px                 │
    └──────────────────────────────────────────────────────────────────┘

State-driven action buttons (right side, 24×24):
    completed     → [📁 Show in folder] [⋯ more]
    downloading   → [⋯ more]            [✕ cancel]
    failed / int. → [↻ retry]           [✕ remove]
"""

import io
import os
import threading

from PIL import Image
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QFontMetrics, QGuiApplication, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu,
                               QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from i18n import t
from ui.icons import icon as _icon, isize as _isize
from utils import (fetch_image_bytes, fmt_duration, human_size,
                   open_file_with_default_app, open_in_explorer,
                   reveal_in_explorer, truncate)


# ---------------------------------------------------------------------------
# Source tag rendering — keyed by yt-dlp's `extractor` field. Each entry is
# (display label, text color, background, border) so we can style brand-
# accurate pills (red YouTube, blue X, purple Twitch, etc.) without scattering
# colour literals across the row code. Falls back to neutral gray for any
# extractor not in the map.
# ---------------------------------------------------------------------------
KNOWN_SOURCES = {
    "youtube":    ("YouTube",    "#FF6B6B", "rgba(235,87,87,0.12)",  "rgba(235,87,87,0.3)"),
    "twitter":    ("X",          "#1DA1F2", "rgba(29,161,242,0.12)", "rgba(29,161,242,0.3)"),
    "vimeo":      ("Vimeo",      "#1AB7EA", "rgba(26,183,234,0.12)", "rgba(26,183,234,0.3)"),
    "twitch":     ("Twitch",     "#9146FF", "rgba(145,70,255,0.12)", "rgba(145,70,255,0.3)"),
    "tiktok":     ("TikTok",     "#FE2C55", "rgba(254,44,85,0.12)",  "rgba(254,44,85,0.3)"),
    "instagram":  ("Instagram",  "#E1306C", "rgba(225,48,108,0.12)", "rgba(225,48,108,0.3)"),
    "facebook":   ("Facebook",   "#1877F2", "rgba(24,119,242,0.12)", "rgba(24,119,242,0.3)"),
    "reddit":     ("Reddit",     "#FF4500", "rgba(255,69,0,0.12)",   "rgba(255,69,0,0.3)"),
    "soundcloud": ("SoundCloud", "#FF7700", "rgba(255,119,0,0.12)",  "rgba(255,119,0,0.3)"),
}

_NEUTRAL_TAG = ("#8A8F98", "rgba(255,255,255,0.04)", "rgba(255,255,255,0.08)")


def _source_tag_info(extractor, domain):
    """Resolve (label, color, bg, border) for a download's source tag.

    `extractor` is yt-dlp's normalised name (e.g. "youtube", "vimeo",
    "instagram:reels", "twitter:broadcast"). We match KNOWN_SOURCES keys
    as PREFIXES, so any sub-extractor that starts with a known key
    inherits that key's branding ("instagram:story" → Instagram pink,
    "youtube:tab" → YouTube red).

    `domain` is the bare hostname (`youtube.com`, `x.com`, …) used as
    fallback for `generic` extractors or for any source not in the map."""
    ext = (extractor or "").lower()
    if ext and not ext.startswith("generic"):
        # Prefix match — "instagram:reels" → "instagram", etc.
        for prefix, info in KNOWN_SOURCES.items():
            if ext == prefix or ext.startswith(prefix + ":"):
                return info
    # Generic / unknown — derive a display from the page domain.
    host = (domain or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        label = "Source"
    else:
        base = host.split(".")[0]
        label = base[:1].upper() + base[1:] if base else host
    return (label,) + _NEUTRAL_TAG


# Comfortable vs compact sizing — scaled +15% for the 780 px default window.
THUMB_COMF = (104, 64)
THUMB_COMP = (68, 40)
ROW_PAD = 14          # outer row padding
ROW_SPACING = 12      # gap between thumb and middle column
ACTION_BTN_SIZE = 30  # row-action button (final visible size)
ACTION_ICON_SIZE = 16
# Comfortable rows host 5 stackable lines (title / channel / source ·
# format · size / progress / error), compact rows hide channel + error.
ROW_MIN_COMF = 104
ROW_MIN_COMP = 68
# Action-cluster widget width — two 30 px buttons + 6 px gap, plus a
# couple of pixels of breathing room. Locked at Fixed + min/max so the
# cluster never shrinks; the title elides instead.
ACTIONS_WIDTH = 72


class _ElidingLabel(QLabel):
    """QLabel that truncates with a unicode-aware ellipsis on resize.
    Used for the row title so it shrinks gracefully instead of pushing
    the action buttons off-screen."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setWordWrap(False)
        # Don't expand vertically — the row layout controls height.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(120)
        # Leading alignment so Arabic right-aligns naturally.
        self.setAlignment(Qt.AlignLeading | Qt.AlignVCenter)

    def setText(self, text):
        self._full_text = text or ""
        super().setText(self._full_text)
        self._update_elide()

    def text_full(self):
        return self._full_text

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._update_elide()

    def _update_elide(self):
        if not self._full_text:
            return
        fm = QFontMetrics(self.font())
        elided = fm.elidedText(self._full_text, Qt.ElideRight,
                               max(0, self.width() - 4))
        # Skip super().setText if it'd recurse; QLabel.setText doesn't.
        QLabel.setText(self, elided)


class _ThumbLoader(QObject):
    """Fetch + decode a thumbnail in a background thread, emit PNG bytes
    back to the row on the main thread."""
    loaded = Signal(bytes, int, int)

    def fetch(self, url, w, h):
        def run():
            data = fetch_image_bytes(url)
            if not data:
                return
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB")
                sw, sh = img.size
                scale = max(w / sw, h / sh)
                ns = (int(sw * scale), int(sh * scale))
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
    """Per-download row; subscribes to its DownloadItem's signals."""

    removed = Signal(object)

    def __init__(self, item, app, parent=None):
        super().__init__(parent)
        self.setObjectName("RowV2")
        self.item = item
        self.app = app
        self.visible = True
        self._thumb_pix = None

        # Per-app preference (set by the title bar's compact toggle).
        self._compact = bool(app.cfg.get("compact_mode", False)) if app else False

        self._build()
        self._connect_signals()
        self._apply_status_visuals()

        # subtle drop shadow per Linear spec
        from ui.theme import apply_shadow, SHADOW_ROW
        apply_shadow(self, **SHADOW_ROW)

        if item.thumb_url:
            self._thumb_loader = _ThumbLoader(self)
            self._thumb_loader.loaded.connect(self._on_thumb_loaded)
            tw, th = THUMB_COMP if self._compact else THUMB_COMF
            self._thumb_loader.fetch(item.thumb_url, tw, th)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        # Lock a minimum row height so the action buttons have breathing
        # room and the layout doesn't collapse mid-download.
        self.setMinimumHeight(ROW_MIN_COMP if self._compact else ROW_MIN_COMF)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(ROW_PAD, ROW_PAD, ROW_PAD, ROW_PAD)
        outer.setSpacing(ROW_SPACING)
        # Three slots: [thumb fixed] [info expanding] [actions fixed].
        # Stretches are explicit so the title is the only thing that
        # ever shrinks under width pressure.

        # ---- thumbnail ----
        tw, th = THUMB_COMP if self._compact else THUMB_COMF
        self.thumb_box = QFrame(self)
        self.thumb_box.setObjectName("ThumbBoxV2")
        self.thumb_box.setFixedSize(tw, th)
        self.thumb_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.thumb_box.setCursor(Qt.PointingHandCursor)
        # Left-click anywhere in the thumb box opens the image viewer.
        self.thumb_box.mousePressEvent = self._thumb_clicked
        self.thumb_label = QLabel(self.thumb_box)
        self.thumb_label.setFixedSize(tw, th)
        self.thumb_label.setAlignment(Qt.AlignCenter)
        # Forward clicks on the inner label to the box's handler so the
        # whole thumb area is hot, not just the unpainted border pixels.
        self.thumb_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        ph_ic = _icon("audio" if self.item.fmt == "mp3" else "play",
                      color="#62666D")
        if not ph_ic.isNull():
            self.thumb_label.setPixmap(ph_ic.pixmap(16, 16))
        else:
            self.thumb_label.setText("▶")
            self.thumb_label.setStyleSheet(
                "color: #62666D; font-size: 14px; background: transparent;")

        if self.item.duration:
            self._badge = QLabel(fmt_duration(self.item.duration),
                                 self.thumb_box)
            self._badge.setObjectName("DurationBadgeV2")
            self._badge.adjustSize()
            self._badge.move(tw - self._badge.width() - 4,
                             th - self._badge.height() - 4)
        outer.addWidget(self.thumb_box, 0, Qt.AlignTop)

        # ---- middle column: structured info block ----
        # Layout (comfortable):
        #   Line 1: Title
        #   Line 2: Channel name
        #   Line 3: [Source pill] · MP4 · 1080p · 12.4 / 69.9 MB · 2.4 MB/s
        #   Line 4: Progress bar (2 px)
        #   Line 5: Error text (red, only if failed)
        self.info_block = QWidget(self)
        self.info_block.setSizePolicy(QSizePolicy.Expanding,
                                      QSizePolicy.Preferred)
        mid = QVBoxLayout(self.info_block)
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(2)

        # Line 1 — title.
        self.title_label = _ElidingLabel(self._display_title(),
                                         self.info_block)
        self.title_label.setObjectName("TitleV2")
        self.title_label.setMinimumWidth(80)  # shrinkable down to 80 px
        self.title_label.setCursor(Qt.PointingHandCursor)
        self.title_label.mousePressEvent = lambda e: self.open_rename()
        self.title_label.setToolTip(self.title_label.text_full())
        mid.addWidget(self.title_label)

        # Line 2 — channel name (auto-collapses when uploader unknown).
        self.channel_label = _ElidingLabel(self._channel_text(),
                                           self.info_block)
        self.channel_label.setObjectName("ChannelV2")
        self.channel_label.setMinimumWidth(60)
        self.channel_label.setVisible(bool(self.item.uploader)
                                      and not self._compact)
        mid.addWidget(self.channel_label)

        # Line 3 — source pill · format · size/speed
        self.line_meta = QWidget(self.info_block)
        meta_lay = QHBoxLayout(self.line_meta)
        meta_lay.setContentsMargins(0, 0, 0, 0)
        meta_lay.setSpacing(6)

        self.tag_source = QLabel("", self.line_meta)
        meta_lay.addWidget(self.tag_source, 0, Qt.AlignVCenter)
        self._apply_source_tag()

        self._sep1 = self._meta_dot()
        meta_lay.addWidget(self._sep1, 0, Qt.AlignVCenter)

        self.tag_format = QLabel(self._format_tag_text(), self.line_meta)
        is_audio = self.item.fmt == "mp3"
        self.tag_format.setProperty("role",
                                    "tagAudio" if is_audio else "tagFormat")
        meta_lay.addWidget(self.tag_format, 0, Qt.AlignVCenter)

        self._sep2 = self._meta_dot()
        meta_lay.addWidget(self._sep2, 0, Qt.AlignVCenter)

        self.meta_label = QLabel(t("row_waiting"), self.line_meta)
        self.meta_label.setObjectName("MetaV2")
        self.meta_label.setToolTip("")
        meta_lay.addWidget(self.meta_label, 1, Qt.AlignVCenter)

        if self._compact:
            self.line_meta.hide()
        mid.addWidget(self.line_meta)

        # Line 4 — slim progress bar.
        self.bar = QProgressBar(self.info_block)
        self.bar.setObjectName("RowProgressV2")
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        mid.addWidget(self.bar)

        # Line 5 — error message (conditional, hidden until needed).
        self.error_label = _ElidingLabel("", self.info_block)
        self.error_label.setObjectName("ErrorLineV2")
        self.error_label.setStyleSheet(
            "color: #EB5757; font-size: 12px; font-weight: 500;"
            " background: transparent;")
        self.error_label.setVisible(False)
        mid.addWidget(self.error_label)

        outer.addWidget(self.info_block, 1, Qt.AlignVCenter)

        # ---- right column: action buttons ----
        # NEVER shrinks. Fixed width + Fixed/Preferred + matching
        # min/max width via setFixedWidth — three locks because Qt
        # layouts can still stretch a "Fixed" widget if the parent
        # gives it extra space.
        self.actions = QWidget(self)
        self.actions.setObjectName("RowActionsV2")
        self.actions.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        self.actions.setFixedWidth(ACTIONS_WIDTH)
        self.actions.setMinimumWidth(ACTIONS_WIDTH)
        actions_lay = QHBoxLayout(self.actions)
        actions_lay.setContentsMargins(0, 0, 0, 0)
        actions_lay.setSpacing(6)
        actions_lay.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        self._action_btns = []
        outer.addWidget(self.actions, 0, Qt.AlignVCenter)

        # Stretches: thumb=0, info=1, actions=0. Title elides under
        # pressure; the action cluster stays put.
        outer.setStretch(0, 0)
        outer.setStretch(1, 1)
        outer.setStretch(2, 0)

    def _meta_dot(self):
        d = QLabel("·", self.line_meta if hasattr(self, "line_meta") else self)
        d.setStyleSheet(
            "color: #62666D; font-size: 11px; background: transparent;")
        return d

    def _apply_source_tag(self):
        """Re-style the source tag from the item's extractor + domain."""
        label, color, bg, border = _source_tag_info(
            self.item.extractor, self.item.webpage_url_domain)
        self.tag_source.setText(label)
        self.tag_source.setStyleSheet(
            f"background: {bg};"
            f" color: {color};"
            f" border: 1px solid {border};"
            " border-radius: 3px;"
            " padding: 0 6px;"
            " min-height: 18px;"
            " font-size: 12px;"
            " font-weight: 500;")

    def _display_title(self):
        return truncate(self.item.custom_filename or self.item.title, 90)

    def _channel_text(self):
        return truncate(self.item.uploader or "", 28)

    def _format_tag_text(self):
        if self.item.fmt == "mp3":
            return f"MP3 · {self.item.bitrate}kbps"
        if self.item.height:
            return f"MP4 · {self.item.height}p"
        return "MP4"

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.item.progress_updated.connect(self._on_progress)
        self.item.state_changed.connect(self._apply_status_visuals)

    @Slot(float, str)
    def _on_progress(self, frac, text):
        try:
            self.bar.setValue(int(frac * 1000))
            self.meta_label.setText(text)
            self.meta_label.setProperty("state", "downloading")
            self._repolish(self.meta_label)
        except Exception:
            pass

    @Slot()
    def _apply_status_visuals(self):
        try:
            self.title_label.setText(self._display_title())
            self.title_label.setToolTip(self.title_label.text_full())
            self.channel_label.setText(self._channel_text())
            # Channel line auto-collapses when there's no uploader text,
            # and stays hidden in compact mode.
            self.channel_label.setVisible(
                bool(self.item.uploader) and not self._compact)
            self.tag_format.setText(self._format_tag_text())
            # extractor may have been refreshed during the live download
            self._apply_source_tag()
        except Exception:
            return

        status = self.item.status

        # Row-level state property → drives QSS for bg + border
        row_state = {
            "completed":  "completed",
            "downloading": "downloading",
            "failed":     "failed",
            "interrupted": "failed",
        }.get(status, "")
        self.setProperty("state", row_state)
        self._repolish(self)

        # Progress bar tint
        bar_state = {
            "completed":  "completed",
            "downloading": "",
            "failed":     "err",
            "interrupted": "paused",
        }.get(status, "")
        self.bar.setProperty("state", bar_state)
        # Subtle dim on completed bars — kept visible per spec
        # ("provides nice visual confirmation") but at 60 % opacity so it
        # doesn't compete with the size text.
        if status == "completed":
            self.bar.setStyleSheet(
                "QProgressBar { opacity: 0.6; }")
        else:
            self.bar.setStyleSheet("")
        self._repolish(self.bar)

        # ---- Line 5: error / interrupted-reason text (conditional) ----
        if status == "failed":
            err = self.item.error_msg or t("row_failed_unknown")
            self.error_label.setText(err)
            self.error_label.setToolTip(err)
            self.error_label.setVisible(not self._compact)
        elif status == "interrupted":
            err = t("row_interrupted")
            self.error_label.setText(err)
            self.error_label.setToolTip(err)
            self.error_label.setVisible(not self._compact)
        else:
            self.error_label.setVisible(False)

        # ---- Line 3: meta (size/speed/state, after source · format ·) ----
        if status == "completed":
            self.bar.setValue(1000)
            if self.item.size_on_disk:
                size_txt = human_size(self.item.size_on_disk)
            else:
                size_txt = t("row_completed_no_size")
            self._set_meta(size_txt, "")
            self.meta_label.setToolTip("")
        elif status == "failed":
            # Keep line 3 short — the full message lives on line 5.
            partial = (human_size(self.item.size_bytes)
                       if self.item.size_bytes else "—")
            self._set_meta(partial, "err")
            self.meta_label.setToolTip(self.item.error_msg or "")
        elif status == "interrupted":
            partial = (human_size(self.item.size_bytes)
                       if self.item.size_bytes else "—")
            self._set_meta(partial, "err")
            self.meta_label.setToolTip("")
        elif status == "downloading":
            # progress hook drives meta text
            pass
        else:
            self._set_meta(t("row_waiting"), "")

        self._apply_action_buttons(status)

    def _set_meta(self, text, state):
        self.meta_label.setText(text)
        self.meta_label.setProperty("state", state)
        self._repolish(self.meta_label)

    def _repolish(self, w):
        try:
            w.style().unpolish(w)
            w.style().polish(w)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action buttons (rebuilt every status change)
    # ------------------------------------------------------------------
    def _apply_action_buttons(self, status):
        # tear down existing
        for b in self._action_btns:
            try:
                b.setParent(None)
                b.deleteLater()
            except Exception:
                pass
        self._action_btns = []

        if status == "completed":
            # [folder] [⋯ more menu]
            self._add_action("folder", t("menu_show_in_folder"),
                             self._show_in_folder)
            self._add_action("dots", t("menu_play"), self._show_kebab_menu)
        elif status == "downloading":
            # [✕ cancel]
            self._add_action("close", t("menu_remove"), self.delete,
                             danger=True)
        elif status in ("failed", "interrupted"):
            # [↻ retry] [✕ remove]
            self._add_action("refresh", t("menu_retry"), self.item.retry)
            self._add_action("close", t("menu_remove"), self.delete,
                             danger=True)
        else:  # queued
            self._add_action("close", t("menu_remove"), self.delete,
                             danger=True)

    def _add_action(self, icon_name, tooltip, slot, danger=False):
        b = QPushButton("", self.actions)
        b.setProperty("role", "rowActionDanger" if danger else "rowAction")
        b.setToolTip(tooltip)
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedSize(ACTION_BTN_SIZE, ACTION_BTN_SIZE)
        color = "#EB5757" if danger else "#8A8F98"
        ic = _icon(icon_name, color=color)
        if not ic.isNull():
            b.setIcon(ic)
            b.setIconSize(_isize(ACTION_ICON_SIZE))
        else:
            fallback = {"folder": "📁", "dots": "⋯", "close": "✕",
                        "refresh": "↻"}.get(icon_name, "•")
            b.setText(fallback)
        b.clicked.connect(slot)
        self.actions.layout().addWidget(b)
        self._action_btns.append(b)

    # ------------------------------------------------------------------
    # Thumbnail
    # ------------------------------------------------------------------
    @Slot(bytes, int, int)
    def _on_thumb_loaded(self, png_bytes, w, h):
        pix = QPixmap()
        if pix.loadFromData(png_bytes, "PNG"):
            self._thumb_pix = pix
            self.thumb_label.setText("")
            self.thumb_label.setPixmap(pix)

    # ------------------------------------------------------------------
    # Filter
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
    # Kebab menu
    # ------------------------------------------------------------------
    def _show_kebab_menu(self):
        menu = QMenu(self)
        item = self.item
        playable = bool(item.filepath and os.path.exists(item.filepath))
        retryable = item.status in ("failed", "interrupted")
        on_disk = playable  # same condition — file present + path known

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

        # Delete-file is only meaningful when an actual file exists on
        # disk — disable otherwise so the user understands it's a no-op.
        a_delete_file = QAction(t("action_delete_file"), menu)
        a_delete_file.setEnabled(on_disk)
        a_delete_file.triggered.connect(self.delete_with_file)
        menu.addAction(a_delete_file)

        # Pop up under the kebab button itself (the LAST action in
        # completed state). Earlier slice was wrong (`[-2]`).
        anchor = self._action_btns[-1] if self._action_btns else self
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _open_file(self):
        """Open the completed file with the OS default app.

        No-op on non-completed rows (partial files may be corrupt /
        unplayable). Cross-platform via open_file_with_default_app."""
        if self.item.status != "completed":
            return
        path = self.item.filepath
        if not path or not os.path.exists(path):
            return
        open_file_with_default_app(path)

    # The kebab menu's "Play" item routes here too so both entry points
    # share one code path.
    _play_file = _open_file

    def mouseDoubleClickEvent(self, event):
        """Double-click anywhere on a completed row → open the file."""
        if (event.button() == Qt.LeftButton
                and self.item.status == "completed"):
            self._open_file()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _thumb_clicked(self, event):
        """Left-click on the thumbnail → open the image viewer with the
        full-resolution YouTube thumbnail (or the source's equivalent)."""
        if event.button() != Qt.LeftButton:
            return
        if not self.item.thumb_url:
            return
        try:
            from ui.image_viewer import FramelessImageViewer
            viewer = FramelessImageViewer(
                title=self.item.custom_filename or self.item.title or "",
                thumb_url=self.item.thumb_url,
                parent=self.window())
            viewer.exec()
        except Exception:
            pass

    def _show_in_folder(self):
        if self.item.filepath:
            reveal_in_explorer(self.item.filepath)
        else:
            open_in_explorer(self.item.folder)

    def _copy_link(self):
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
        """Remove the row from the list. Keeps the file on disk."""
        self.item.cancel()
        try:
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass
        self.removed.emit(self.item)
        if self.app:
            self.app.remove_item(self.item)

    def delete_with_file(self):
        """Confirm with the user, then delete the file from disk AND the
        row from the list. Used by the kebab menu's "Delete file" entry."""
        path = self.item.filepath
        if not path:
            # Nothing on disk to delete — fall back to plain row removal.
            self.delete()
            return
        # Import lazily so dialogs.py isn't pulled in until needed.
        from ui.dialogs import delete_file_confirm_dialog
        if not delete_file_confirm_dialog(self.window(),
                                          os.path.basename(path)):
            return
        # Cancel any active worker before touching the file.
        self.item.cancel()
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        self.delete()

    # ------------------------------------------------------------------
    # Live language switch
    # ------------------------------------------------------------------
    def retranslate(self):
        try:
            # Source label comes from the extractor map, not i18n —
            # _apply_status_visuals refreshes it along with the rest.
            self._apply_status_visuals()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Compact mode toggle
    # ------------------------------------------------------------------
    def set_compact(self, compact: bool):
        if compact == self._compact:
            return
        self._compact = compact
        tw, th = THUMB_COMP if compact else THUMB_COMF
        self.thumb_box.setFixedSize(tw, th)
        self.thumb_label.setFixedSize(tw, th)
        if self._thumb_pix is not None:
            self.thumb_label.setPixmap(
                self._thumb_pix.scaled(tw, th,
                                       Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation))
        # Compact hides channel (line 2), meta+source pill row (line 3),
        # and the error line (line 5). Title + progress bar stay visible.
        self.setMinimumHeight(ROW_MIN_COMP if compact else ROW_MIN_COMF)
        self.channel_label.setVisible(bool(self.item.uploader) and not compact)
        self.line_meta.setVisible(not compact)
        # Re-evaluate the error line for the new mode.
        self._apply_status_visuals()
