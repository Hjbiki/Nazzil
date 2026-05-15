# -*- coding: utf-8 -*-
"""Main window (QMainWindow). Top bar, options/playlist cards, downloads
panel, search/sort/tabs, persistence, clipboard watcher, tray notifications."""

import io
import json
import os
import shutil
import threading

from PIL import Image
from PySide6.QtCore import (QEvent, QObject, QTimer, QUrl, Qt, Signal, Slot)
from PySide6.QtGui import (QAction, QDesktopServices, QGuiApplication, QIcon,
                           QKeySequence, QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                               QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSystemTrayIcon,
                               QVBoxLayout, QWidget)
import yt_dlp

from config import (DOWNLOADS_PATH, PREVIEW_H, PREVIEW_W, YT_PLAYLIST_RE,
                    YT_URL_RE, load_config, save_config)
from downloader import DownloadItem
from i18n import Translator, t
from ui.dialogs import (AccountDialog, SettingsDialog, conflict_dialog,
                        duplicate_dialog, rename_dialog)
from ui.download_row import DownloadRow
from ui.tray import Tray
from updater import (UpdateChecker, UpdateDownloader, current_exe_path,
                     github_release_url, is_frozen, launch_updater)
from utils import (classify_error, clean_error, extract_video_id,
                   fetch_image_bytes, fmt_duration, sanitize_filename,
                   truncate)


# ---------------------------------------------------------------------------
# Cross-thread "all done" signaller
# ---------------------------------------------------------------------------
class _AppBridge(QObject):
    """Used by DownloadItem to ping the App from a worker thread via a
    queued signal."""
    finished_one = Signal()


# ---------------------------------------------------------------------------
class App(QMainWindow):
    def __init__(self, app_icon: QIcon = None):
        super().__init__()
        self.setObjectName("AppWindow")
        self._app_icon = app_icon or QIcon()
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)
        self.setWindowTitle(t("app_title"))
        self.resize(960, 800)
        self.setMinimumSize(820, 640)

        # ---- config ----
        self.cfg = load_config()
        self.folder = self.cfg.get("folder", "")
        self.cookie_mode = self.cfg.get("cookie_mode", "none")
        self.cookie_file = self.cfg.get("cookie_file", "")
        self.cfg.setdefault("use_aria2c", False)
        self.cfg.setdefault("clipboard_watch", True)
        self.cfg.setdefault("minimize_to_tray", True)
        self.cfg.setdefault("lang", Translator.lang())

        # ---- state ----
        self.current_info = None
        self.fetched_url = ""
        self._video_quality_labels = []
        self._preview_pix = None

        self.playlist_entries = []
        self.playlist_url = ""
        self.playlist_check_widgets = []  # list[QCheckBox]

        self.items = []                  # list[DownloadItem]
        self.rows = {}                   # id(item) → DownloadRow

        self.active_tab = "All"
        self.search_query = ""
        self.sort_by = "Last updated"

        self.active_count = 0
        self.batch_completed = 0
        self.batch_failed = 0
        self._last_clip_url = ""
        self._loading = False
        self._quitting = False

        # Bridge: worker → main thread for "one finished"
        self._bridge = _AppBridge(self)
        self._bridge.finished_one.connect(self._on_download_finished)

        # ---- UI ----
        self._build_ui()
        self._check_ffmpeg()
        self._load_downloads()

        # Tray
        self.tray = Tray(self._app_icon, self) if QSystemTrayIcon.isSystemTrayAvailable() else None
        if self.tray is not None:
            self.tray.show_requested.connect(self._tray_show)
            self.tray.exit_requested.connect(self._tray_exit)
            self.tray.show()

        # Clipboard watcher (QClipboard signal is more reliable than polling)
        self._clipboard = QGuiApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_clipboard_changed)

        # Auto-fetch debounce timer
        self._autofetch_timer = QTimer(self)
        self._autofetch_timer.setSingleShot(True)
        self._autofetch_timer.timeout.connect(self._autofetch)

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(10)

        # ----- UPDATE BANNER (hidden until updater fires) -----
        self._build_update_banner()
        root.addWidget(self.update_banner)
        self.update_banner.hide()

        # ----- TOP BAR -----
        top = QHBoxLayout()
        top.setSpacing(8)

        self.url_pill = QFrame()
        self.url_pill.setObjectName("UrlPill")
        self.url_pill.setFixedHeight(44)
        pill_layout = QHBoxLayout(self.url_pill)
        pill_layout.setContentsMargins(14, 4, 6, 4)
        pill_layout.setSpacing(6)
        magn = QLabel("🔍")
        magn.setStyleSheet("color: #8A8F98; font-size: 14px;")
        pill_layout.addWidget(magn)
        self.url_entry = QLineEdit()
        self.url_entry.setObjectName("UrlEntry")
        self.url_entry.setPlaceholderText(t("url_placeholder"))
        self.url_entry.returnPressed.connect(self._fetch)
        self.url_entry.textChanged.connect(self._on_url_change)
        self.url_entry.setContextMenuPolicy(Qt.CustomContextMenu)
        self.url_entry.customContextMenuRequested.connect(self._show_url_menu)
        pill_layout.addWidget(self.url_entry, 1)
        self.fetch_btn = QPushButton(t("fetch"))
        self.fetch_btn.setProperty("role", "primary")
        self.fetch_btn.setFixedHeight(32)
        self.fetch_btn.clicked.connect(self._fetch)
        pill_layout.addWidget(self.fetch_btn)
        top.addWidget(self.url_pill, 1)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setProperty("role", "icon")
        self.settings_btn.setToolTip(t("settings"))
        self.settings_btn.clicked.connect(self._open_settings)
        top.addWidget(self.settings_btn)

        self.account_btn = QPushButton("🔐")
        self.account_btn.setProperty("role", "icon")
        self.account_btn.setToolTip(t("account"))
        self.account_btn.clicked.connect(self._open_account)
        top.addWidget(self.account_btn)

        root.addLayout(top)

        # ----- SINGLE-VIDEO OPTIONS CARD (hidden until fetch) -----
        self.options_card = QFrame()
        self.options_card.setObjectName("PanelCard")
        oc = QVBoxLayout(self.options_card)
        oc.setContentsMargins(14, 12, 14, 12)
        oc.setSpacing(8)

        # preview row
        preview_row = QHBoxLayout()
        self.preview_thumb = QLabel()
        self.preview_thumb.setObjectName("PreviewBox")
        self.preview_thumb.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.preview_thumb.setAlignment(Qt.AlignCenter)
        preview_row.addWidget(self.preview_thumb, 0, Qt.AlignTop)
        preview_text = QVBoxLayout()
        preview_text.setSpacing(4)
        self.fetched_title_label = QLabel("")
        self.fetched_title_label.setObjectName("FetchedTitle")
        self.fetched_title_label.setWordWrap(True)
        self.fetched_meta_label = QLabel("")
        self.fetched_meta_label.setObjectName("Hint")
        preview_text.addWidget(self.fetched_title_label)
        preview_text.addWidget(self.fetched_meta_label)
        preview_text.addStretch(1)
        preview_row.addLayout(preview_text, 1)
        oc.addLayout(preview_row)

        # controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.format_group, self.format_btns = self._make_segmented(
            [("mp4", t("format_mp4")), ("mp3", t("format_mp3"))],
            self._on_format_change, current="mp4")
        for b in self.format_btns:
            ctrl.addWidget(b)
        self.quality_combo = QComboBox()
        self.quality_combo.setFixedHeight(36)
        self.quality_combo.addItem("—")
        ctrl.addWidget(self.quality_combo)
        ctrl.addStretch(1)
        self.download_btn = QPushButton(t("download"))
        self.download_btn.setProperty("role", "primary")
        self.download_btn.setFixedHeight(40)
        self.download_btn.clicked.connect(self._add_download)
        ctrl.addWidget(self.download_btn)
        oc.addLayout(ctrl)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        oc.addWidget(self.status_label)

        root.addWidget(self.options_card)
        self.options_card.hide()

        # ----- PLAYLIST CARD -----
        self.playlist_card = QFrame()
        self.playlist_card.setObjectName("PanelCard")
        pc = QVBoxLayout(self.playlist_card)
        pc.setContentsMargins(14, 12, 14, 12)
        pc.setSpacing(8)

        self.playlist_title_label = QLabel("")
        self.playlist_title_label.setObjectName("FetchedTitle")
        pc.addWidget(self.playlist_title_label)

        pl_meta = QHBoxLayout()
        self.playlist_count_label = QLabel("")
        self.playlist_count_label.setObjectName("Hint")
        pl_meta.addWidget(self.playlist_count_label, 1)
        sel_all = QPushButton(t("select_all"))
        sel_all.clicked.connect(lambda: self._playlist_toggle_all(True))
        clr_sel = QPushButton(t("clear_selection"))
        clr_sel.clicked.connect(lambda: self._playlist_toggle_all(False))
        pl_meta.addWidget(sel_all)
        pl_meta.addWidget(clr_sel)
        pc.addLayout(pl_meta)

        # checklist (QScrollArea + QVBoxLayout)
        self.playlist_scroll = QScrollArea()
        self.playlist_scroll.setWidgetResizable(True)
        self.playlist_scroll.setFixedHeight(200)
        self.playlist_scroll.setFrameShape(QFrame.NoFrame)
        self.playlist_inner = QWidget()
        self.playlist_inner_layout = QVBoxLayout(self.playlist_inner)
        self.playlist_inner_layout.setContentsMargins(8, 6, 8, 6)
        self.playlist_inner_layout.setSpacing(4)
        self.playlist_inner_layout.addStretch(1)
        self.playlist_scroll.setWidget(self.playlist_inner)
        pc.addWidget(self.playlist_scroll)

        pl_controls = QHBoxLayout()
        self.pl_format_group, self.pl_format_btns = self._make_segmented(
            [("mp4", t("format_mp4")), ("mp3", t("format_mp3"))],
            self._on_pl_format_change, current="mp4")
        for b in self.pl_format_btns:
            pl_controls.addWidget(b)
        self.pl_quality_combo = QComboBox()
        self.pl_quality_combo.setFixedHeight(36)
        self.pl_quality_combo.addItems(
            ["2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"])
        self.pl_quality_combo.setCurrentText("1080p")
        pl_controls.addWidget(self.pl_quality_combo)
        pl_controls.addStretch(1)
        self.pl_download_btn = QPushButton(t("download_selected"))
        self.pl_download_btn.setProperty("role", "primary")
        self.pl_download_btn.setFixedHeight(40)
        self.pl_download_btn.clicked.connect(self._add_playlist_downloads)
        pl_controls.addWidget(self.pl_download_btn)
        pc.addLayout(pl_controls)

        root.addWidget(self.playlist_card)
        self.playlist_card.hide()

        # ----- GLOBAL STATUS -----
        self.global_status = QLabel("")
        self.global_status.setObjectName("Hint")
        root.addWidget(self.global_status)

        # ----- TABS -----
        tabs_row = QHBoxLayout()
        self.tabs_group, self.tabs_btns = self._make_segmented(
            [("All", t("tab_all")),
             ("Video", t("tab_video")),
             ("Audio", t("tab_audio"))],
            self._on_tab_change, current="All")
        for b in self.tabs_btns:
            tabs_row.addWidget(b)
        tabs_row.addStretch(1)
        root.addLayout(tabs_row)

        # ----- DOWNLOADS PANEL -----
        panel = QFrame()
        panel.setObjectName("PanelCard")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(8)

        header = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setObjectName("SearchEntry")
        self.search_entry.setPlaceholderText(t("search_downloads"))
        self.search_entry.setFixedWidth(260)
        self.search_entry.textChanged.connect(self._on_search)
        header.addWidget(self.search_entry)

        sort_lbl = QLabel(t("sort_by"))
        sort_lbl.setObjectName("Hint")
        header.addWidget(sort_lbl)
        self.sort_combo = QComboBox()
        self.sort_combo.addItem(t("sort_last_updated"), "Last updated")
        self.sort_combo.addItem(t("sort_title"), "Title")
        self.sort_combo.addItem(t("sort_size"), "Size")
        self.sort_combo.setFixedHeight(36)
        self.sort_combo.currentIndexChanged.connect(self._on_sort)
        header.addWidget(self.sort_combo)

        header.addStretch(1)

        self.clear_btn = QPushButton(t("clear_all"))
        self.clear_btn.setProperty("role", "danger")
        self.clear_btn.clicked.connect(self.clear_all)
        header.addWidget(self.clear_btn)

        panel_layout.addLayout(header)

        # scroll list
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_inner = QWidget()
        self.list_layout = QVBoxLayout(self.list_inner)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        self.empty_label = QLabel(t("empty_hint"))
        self.empty_label.setObjectName("Hint")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch(1)
        self.list_scroll.setWidget(self.list_inner)
        panel_layout.addWidget(self.list_scroll, 1)

        footer = QHBoxLayout()
        self.count_label = QLabel(t("downloads_count", count=0))
        self.count_label.setObjectName("Hint")
        footer.addWidget(self.count_label, 1)
        panel_layout.addLayout(footer)

        root.addWidget(panel, 1)

    # ==================================================================
    # Update banner — built as part of _build_ui
    # ==================================================================
    def _build_update_banner(self):
        """Slim banner that surfaces 'update available'. Hidden by default."""
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.setStyleSheet(
            "QFrame#UpdateBanner {"
            "  background: #1F2240;"
            "  border: 1px solid #525E9E;"
            "  border-radius: 10px;"
            "}"
        )
        self.update_banner.setFixedHeight(44)

        lay = QHBoxLayout(self.update_banner)
        lay.setContentsMargins(14, 4, 8, 4)
        lay.setSpacing(8)

        self.update_label = QLabel("")
        self.update_label.setStyleSheet("color: #F7F8F8; font-size: 12px;")
        lay.addWidget(self.update_label, 1)

        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 1000)
        self.update_progress.setValue(0)
        self.update_progress.setTextVisible(False)
        self.update_progress.setFixedWidth(180)
        self.update_progress.hide()
        lay.addWidget(self.update_progress)

        self.update_action_btn = QPushButton(t("update_now"))
        self.update_action_btn.setCursor(Qt.PointingHandCursor)
        self.update_action_btn.clicked.connect(self._on_update_now)
        lay.addWidget(self.update_action_btn)

        self.update_dismiss_btn = QPushButton("✕")
        self.update_dismiss_btn.setProperty("role", "kebab")
        self.update_dismiss_btn.setCursor(Qt.PointingHandCursor)
        self.update_dismiss_btn.clicked.connect(self.update_banner.hide)
        lay.addWidget(self.update_dismiss_btn)

        # internal state
        self._update_tag = ""
        self._update_asset_url = ""
        self._update_size = 0

    # ==================================================================
    # Update flow
    # ==================================================================
    def start_update_check(self):
        """Called by main.py after the window is shown."""
        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.check_failed.connect(lambda _msg: None)
        self._update_checker.no_update.connect(lambda: None)
        self._update_checker.start()

    @Slot(str, str, int)
    def _on_update_available(self, tag, asset_url, size):
        self._update_tag = tag
        self._update_asset_url = asset_url
        self._update_size = size
        if is_frozen() and asset_url:
            self.update_label.setText(t("update_available", version=tag))
            self.update_action_btn.setText(t("update_now"))
        else:
            # source run OR release missing the portable exe → link out instead
            self.update_label.setText(t("update_source_hint", version=tag))
            self.update_action_btn.setText(t("update_open_github"))
        self.update_progress.hide()
        self.update_action_btn.setEnabled(True)
        self.update_banner.show()

    @Slot()
    def _on_update_now(self):
        if not is_frozen() or not self._update_asset_url:
            QDesktopServices.openUrl(QUrl(github_release_url()))
            return
        # start the download
        self.update_action_btn.setEnabled(False)
        self.update_progress.show()
        self.update_progress.setValue(0)
        self.update_label.setText(
            t("update_downloading", percent=0))
        self._update_downloader = UpdateDownloader(self)
        self._update_downloader.progress.connect(self._on_update_progress)
        self._update_downloader.download_done.connect(self._on_update_downloaded)
        self._update_downloader.download_failed.connect(self._on_update_failed)
        self._update_downloader.start(self._update_asset_url)

    @Slot(float)
    def _on_update_progress(self, frac):
        v = max(0, min(1000, int(frac * 1000)))
        self.update_progress.setValue(v)
        self.update_label.setText(
            t("update_downloading", percent=int(frac * 100)))

    @Slot(str)
    def _on_update_downloaded(self, local_path):
        self.update_label.setText(t("update_ready"))
        self.update_action_btn.hide()
        self.update_dismiss_btn.hide()
        exe = current_exe_path()
        if not exe:
            return
        try:
            launch_updater(local_path, exe)
        except Exception:
            return
        # let the user see "restarting…" briefly, then quit
        QTimer.singleShot(800, self._tray_exit)

    @Slot(str)
    def _on_update_failed(self, msg):
        self.update_label.setText(t("update_dl_failed", msg=msg))
        self.update_progress.hide()
        self.update_action_btn.setEnabled(True)

    def _make_segmented(self, items, on_change, current):
        """Build a QButtonGroup of tab-styled QPushButtons. `items` is a list
        of (key, label) tuples. Returns (group, [buttons])."""
        group = QButtonGroup(self)
        group.setExclusive(True)
        buttons = []
        for key, label in items:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setProperty("key", key)
            b.setProperty("role", "tab")
            b.setCursor(Qt.PointingHandCursor)
            buttons.append(b)
            group.addButton(b)

        def repolish_all():
            for btn in buttons:
                checked = btn.isChecked()
                btn.setProperty("role", "tabActive" if checked else "tab")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

        def click_handler(b=None):
            for btn in buttons:
                btn.setChecked(btn is b)
            repolish_all()
            on_change(b.property("key"))

        for btn in buttons:
            btn.clicked.connect(lambda _checked=False, b=btn: click_handler(b))
            if btn.property("key") == current:
                btn.setChecked(True)
        repolish_all()
        return group, buttons

    def _segmented_set(self, buttons, key):
        for btn in buttons:
            checked = btn.property("key") == key
            btn.setChecked(checked)
            btn.setProperty("role", "tabActive" if checked else "tab")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _check_ffmpeg(self):
        if shutil.which("ffmpeg") is None:
            QMessageBox.warning(
                self, t("ffmpeg_missing_title"), t("ffmpeg_missing_body"))

    # ==================================================================
    # Cookie opts
    # ==================================================================
    def _cookie_opts(self):
        if self.cookie_mode == "file":
            if self.cookie_file and os.path.exists(self.cookie_file):
                return {"cookiefile": self.cookie_file}
            return {}
        if self.cookie_mode in ("firefox", "brave", "chrome", "edge"):
            return {"cookiesfrombrowser": (self.cookie_mode,)}
        return {}

    # ==================================================================
    # Settings / account dialogs
    # ==================================================================
    def _open_settings(self):
        SettingsDialog(self, self).exec()

    def _open_account(self):
        AccountDialog(self, self).exec()

    # ==================================================================
    # URL handling
    # ==================================================================
    def _on_format_change(self, key):
        if key == "mp3":
            self.quality_combo.clear()
            self.quality_combo.addItems(["320 kbps", "192 kbps", "128 kbps"])
            self.quality_combo.setCurrentText("192 kbps")
        else:
            labels = self._video_quality_labels or ["—"]
            self.quality_combo.clear()
            self.quality_combo.addItems(labels)
            self.quality_combo.setCurrentIndex(0)

    def _on_url_change(self, _text):
        url = self.url_entry.text().strip()
        if url != self.fetched_url:
            self.options_card.hide()
            self.playlist_card.hide()
        self._autofetch_timer.stop()
        if YT_URL_RE.match(url) and url != self.fetched_url:
            self._autofetch_timer.start(500)

    def _autofetch(self):
        url = self.url_entry.text().strip()
        if not url or url == self.fetched_url:
            return
        if not YT_URL_RE.match(url):
            return
        if not self.fetch_btn.isEnabled():
            return
        self._fetch()

    def _show_url_menu(self, pos):
        menu = QMenu(self.url_entry)
        menu.addAction(t("menu_cut"), self.url_entry.cut)
        menu.addAction(t("menu_copy"), self.url_entry.copy)
        menu.addAction(t("menu_paste"), self.url_entry.paste)
        menu.addSeparator()
        menu.addAction(t("menu_select_all"), self.url_entry.selectAll)
        menu.exec(self.url_entry.mapToGlobal(pos))

    # ==================================================================
    # Fetch
    # ==================================================================
    def _fetch(self):
        url = self.url_entry.text().strip()
        if not url:
            self._set_global(t("paste_url_first"), "err")
            return
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText(t("fetching"))
        self._set_global(t("fetching_info"), "muted")
        cookie_opts = self._cookie_opts()
        self._fetcher = _FetchWorker(url, cookie_opts, self)
        self._fetcher.fetched_video.connect(self._fetch_done)
        self._fetcher.fetched_playlist.connect(self._playlist_fetched)
        self._fetcher.failed.connect(self._fetch_failed)
        self._fetcher.start()

    @Slot(str, dict, list)
    def _fetch_done(self, url, info, heights):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch"))
        self.current_info = info
        self.fetched_url = url
        if not heights:
            heights = [1080, 720, 480]
        labels = []
        for h in heights:
            if h >= 2160:
                labels.append(f"{h}p (4K)")
            elif h >= 1440:
                labels.append(f"{h}p (2K)")
            else:
                labels.append(f"{h}p")
        self._video_quality_labels = labels
        self.quality_combo.clear()
        self.quality_combo.addItems(labels)
        self.quality_combo.setCurrentIndex(0)
        self._segmented_set(self.format_btns, "mp4")
        self.fetched_title_label.setText(
            truncate(info.get("title", "Video"), 110))
        meta_parts = []
        uploader = info.get("uploader") or info.get("channel")
        if uploader:
            meta_parts.append(uploader)
        dur = fmt_duration(info.get("duration") or 0)
        if dur:
            meta_parts.append(dur)
        self.fetched_meta_label.setText(" · ".join(meta_parts))

        # preview thumbnail
        self._preview_pix = None
        self.preview_thumb.clear()
        if info.get("thumbnail"):
            self._preview_loader = _PreviewLoader(self)
            self._preview_loader.loaded.connect(self._on_preview_loaded)
            self._preview_loader.fetch(
                info["thumbnail"], PREVIEW_W, PREVIEW_H)

        self.status_label.setText(t("pick_format_hint"))
        self.playlist_card.hide()
        self.options_card.show()
        self._set_global("", "")

    @Slot(bytes)
    def _on_preview_loaded(self, png_bytes):
        pix = QPixmap()
        if pix.loadFromData(png_bytes, "PNG"):
            self._preview_pix = pix
            self.preview_thumb.setPixmap(pix)

    @Slot(str)
    def _fetch_failed(self, msg):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch"))
        self._set_global(t("fetch_failed", msg=msg), "err")

    # ==================================================================
    # Playlist
    # ==================================================================
    @Slot(str, dict, list)
    def _playlist_fetched(self, url, info, entries):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch"))
        self.fetched_url = url
        self.current_info = info
        self.playlist_url = url
        self.playlist_entries = entries

        # rebuild check widgets
        # remove old (everything except the trailing stretch)
        while self.playlist_inner_layout.count() > 1:
            it = self.playlist_inner_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        self.playlist_check_widgets = []
        for idx, e in enumerate(entries, 1):
            title = e.get("title") or e.get("id") or f"Video {idx}"
            chk = QCheckBox(f"{idx}. {truncate(title, 80)}")
            chk.setChecked(True)
            self.playlist_check_widgets.append(chk)
            self.playlist_inner_layout.insertWidget(
                self.playlist_inner_layout.count() - 1, chk)

        title = info.get("title") or "Playlist"
        self.playlist_title_label.setText(
            t("playlist_label", title=truncate(title, 80)))
        self.playlist_count_label.setText(
            t("playlist_count_hint", count=len(entries)))
        self.options_card.hide()
        self.playlist_card.show()
        self._set_global("", "")

    def _playlist_toggle_all(self, value):
        for c in self.playlist_check_widgets:
            c.setChecked(value)

    def _on_pl_format_change(self, key):
        if key == "mp3":
            self.pl_quality_combo.clear()
            self.pl_quality_combo.addItems(
                ["320 kbps", "192 kbps", "128 kbps"])
            self.pl_quality_combo.setCurrentText("192 kbps")
        else:
            self.pl_quality_combo.clear()
            self.pl_quality_combo.addItems(
                ["2160p (4K)", "1440p (2K)", "1080p",
                 "720p", "480p", "360p"])
            self.pl_quality_combo.setCurrentText("1080p")

    def _add_playlist_downloads(self):
        if not self.folder:
            self._set_global(t("set_folder_first"), "err")
            return
        if not self.playlist_entries:
            return
        # active format key
        fmt_key = "mp4"
        for b in self.pl_format_btns:
            if b.isChecked():
                fmt_key = b.property("key")
                break
        q = self.pl_quality_combo.currentText()
        if fmt_key == "mp3":
            fmt, height = "mp3", None
            digits = "".join(ch for ch in q if ch.isdigit())
            bitrate = int(digits) if digits else 192
        else:
            fmt = "mp4"
            digits = "".join(ch for ch in q.split("p")[0] if ch.isdigit())
            height = int(digits) if digits else 1080
            bitrate = 192

        added = 0
        for chk, entry in zip(self.playlist_check_widgets,
                              self.playlist_entries):
            if not chk.isChecked():
                continue
            video_url = entry.get("url") or entry.get("webpage_url")
            if not video_url:
                vid = entry.get("id")
                if vid:
                    video_url = f"https://www.youtube.com/watch?v={vid}"
            if not video_url:
                continue
            thumb = ""
            thumbs = entry.get("thumbnails")
            if isinstance(thumbs, list) and thumbs:
                thumb = thumbs[-1].get("url", "")
            elif entry.get("thumbnail"):
                thumb = entry.get("thumbnail")
            info = {
                "title": entry.get("title") or f"Video {added + 1}",
                "thumbnail": thumb,
                "duration": entry.get("duration") or 0,
            }
            self._create_and_start_item(video_url, fmt, height, info,
                                        bitrate=bitrate)
            added += 1

        if added == 0:
            self._set_global(t("no_videos_selected"), "warn")
            return

        self.url_entry.clear()
        self.fetched_url = ""
        self.playlist_url = ""
        self.playlist_entries = []
        self.playlist_card.hide()
        self._set_global(t("queued_from_playlist", count=added), "ok")
        self.url_entry.setFocus()
        self._refresh_list()

    # ==================================================================
    # Add single download
    # ==================================================================
    def _read_format_choice(self):
        fmt_key = "mp4"
        for b in self.format_btns:
            if b.isChecked():
                fmt_key = b.property("key")
                break
        q = self.quality_combo.currentText()
        if fmt_key == "mp3":
            digits = "".join(ch for ch in q if ch.isdigit())
            return "mp3", None, int(digits) if digits else 192
        height = 1080
        digits = "".join(ch for ch in q.split("p")[0] if ch.isdigit())
        if digits:
            height = int(digits)
        return "mp4", height, 192

    def _add_download(self):
        url = self.url_entry.text().strip()
        if not url:
            return
        if not self.folder:
            self._set_global(t("set_folder_first"), "err")
            return
        if url != self.fetched_url:
            self.status_label.setText(t("url_changed_hint"))
            return

        fmt, height, bitrate = self._read_format_choice()
        title = (self.current_info or {}).get("title") or url
        vid = extract_video_id(url)

        # duplicate?
        for it in self.items:
            if it.status == "completed" and extract_video_id(it.url) == vid:
                if duplicate_dialog(self, it.title or title):
                    self._continue_add(url, fmt, height, bitrate)
                else:
                    self._set_global(t("skipped_duplicate"), "muted")
                return

        self._continue_add(url, fmt, height, bitrate)

    def _continue_add(self, url, fmt, height, bitrate):
        title = (self.current_info or {}).get("title") or url
        safe = sanitize_filename(title)
        ext = "mp3" if fmt == "mp3" else "mp4"
        expected = os.path.join(self.folder, f"{safe}.{ext}")
        if os.path.exists(expected):
            action, payload = conflict_dialog(self, os.path.basename(expected))
            if action == "cancel":
                self._set_global(t("cancelled"), "muted")
                return
            if action == "replace":
                try:
                    os.remove(expected)
                except Exception:
                    pass
                self._create_and_start_item(
                    url, fmt, height, self.current_info, bitrate=bitrate)
            else:
                self._create_and_start_item(
                    url, fmt, height, self.current_info,
                    bitrate=bitrate, custom_filename=payload)
        else:
            self._create_and_start_item(
                url, fmt, height, self.current_info, bitrate=bitrate)
        self._after_added_single()

    def _after_added_single(self):
        self.url_entry.clear()
        self.fetched_url = ""
        self.options_card.hide()
        self._set_global(t("download_started"), "ok")
        self.url_entry.setFocus()
        self._refresh_list()

    def _create_and_start_item(self, url, fmt, height, info, *,
                               bitrate=192, custom_filename=None):
        item = DownloadItem(
            url=url, fmt=fmt, height=height, info=info or {},
            folder=self.folder, bitrate=bitrate,
            custom_filename=custom_filename, parent=self)
        item.app = self
        row = DownloadRow(item, self, parent=self.list_inner)
        # insert above the trailing stretch
        idx = self.list_layout.count() - 1
        self.list_layout.insertWidget(idx, row)
        self.items.append(item)
        self.rows[id(item)] = row
        item.start()

    # ==================================================================
    # Item lifecycle
    # ==================================================================
    def remove_item(self, item):
        if item in self.items:
            self.items.remove(item)
        self.rows.pop(id(item), None)
        self.save_downloads()
        self._refresh_list()

    def clear_all(self):
        if not self.items:
            return
        if QMessageBox.question(
                self, t("clear_all_title"), t("clear_all_body"),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                ) != QMessageBox.Yes:
            return
        for it in list(self.items):
            it.cancel()
            row = self.rows.get(id(it))
            if row:
                try:
                    row.setParent(None)
                    row.deleteLater()
                except Exception:
                    pass
        self.items.clear()
        self.rows.clear()
        self.batch_completed = 0
        self.batch_failed = 0
        try:
            if os.path.exists(DOWNLOADS_PATH):
                os.remove(DOWNLOADS_PATH)
        except Exception:
            pass
        self._refresh_list()

    # ==================================================================
    # Filter / sort
    # ==================================================================
    def _on_tab_change(self, key):
        self.active_tab = key
        self._refresh_list()

    def _on_search(self, _txt):
        self.search_query = self.search_entry.text().strip()
        self._refresh_list()

    def _on_sort(self, _idx):
        self.sort_by = self.sort_combo.currentData() or "Last updated"
        self._refresh_list()

    def _refresh_list(self):
        # collect visible items by current filter
        visible_items = []
        for it in self.items:
            row = self.rows.get(id(it))
            if not row:
                continue
            if row.matches(self.search_query, self.active_tab):
                visible_items.append(it)
            else:
                row.setVisibleRow(False)

        if self.sort_by == "Title":
            visible_items.sort(
                key=lambda i: (i.custom_filename or i.title or "").lower())
        elif self.sort_by == "Size":
            visible_items.sort(
                key=lambda i: i.size_on_disk or i.size_bytes, reverse=True)
        else:
            visible_items.sort(key=lambda i: i.last_updated, reverse=True)

        # re-order in layout: remove all rows then add in sorted order
        # (leave the trailing stretch in place)
        for it in visible_items:
            row = self.rows.get(id(it))
            if not row:
                continue
            self.list_layout.removeWidget(row)
        for it in visible_items:
            row = self.rows.get(id(it))
            if not row:
                continue
            idx = self.list_layout.count() - 1
            self.list_layout.insertWidget(idx, row)
            row.setVisibleRow(True)

        self.empty_label.setVisible(len(self.items) == 0)
        self.count_label.setText(
            t("downloads_count", count=len(visible_items)))

    # ==================================================================
    # Persistence
    # ==================================================================
    def _load_downloads(self):
        try:
            with open(DOWNLOADS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        if not isinstance(data, list):
            return
        self._loading = True
        for d in data:
            try:
                item = DownloadItem.from_dict(d)
                item.setParent(self)
                item.app = self
                row = DownloadRow(item, self, parent=self.list_inner)
                idx = self.list_layout.count() - 1
                self.list_layout.insertWidget(idx, row)
                self.items.append(item)
                self.rows[id(item)] = row
            except Exception:
                continue
        self._loading = False
        self.batch_completed = sum(1 for i in self.items
                                   if i.status == "completed")
        self.batch_failed = sum(1 for i in self.items
                                if i.status == "failed")
        self._refresh_list()

    def save_downloads(self):
        if self._loading:
            return
        try:
            data = [it.to_dict() for it in self.items]
            with open(DOWNLOADS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==================================================================
    # Active-count / batch notification
    # (DownloadItem.start() calls on_download_started; on_download_finished
    # comes back through the queued signal.)
    # ==================================================================
    def on_download_started(self):
        self.active_count += 1

    def on_download_finished_signal_emit(self):
        """Called from a worker thread — emits a queued signal."""
        self._bridge.finished_one.emit()

    @Slot()
    def _on_download_finished(self):
        if self.active_count > 0:
            self.active_count -= 1
        completed = sum(1 for i in self.items if i.status == "completed")
        failed = sum(1 for i in self.items if i.status == "failed")
        if self.active_count == 0:
            done = max(0, completed - self.batch_completed)
            fail = max(0, failed - self.batch_failed)
            if done + fail > 0:
                if fail == 0:
                    msg = t("tray_completed_only", n=done)
                elif done == 0:
                    msg = t("tray_failed_only", n=fail)
                else:
                    msg = t("tray_mixed", ok=done, fail=fail)
                if self.tray is not None:
                    self.tray.notify(t("tray_all_done_title"), msg)
            self.batch_completed = completed
            self.batch_failed = failed
        self.save_downloads()

    # ==================================================================
    # Clipboard watcher (QClipboard signal)
    # ==================================================================
    @Slot()
    def _on_clipboard_changed(self):
        if not self.cfg.get("clipboard_watch", True):
            return
        try:
            txt = self._clipboard.text()
        except Exception:
            return
        if not txt:
            return
        txt = txt.strip()
        if (YT_URL_RE.match(txt)
                and txt != self._last_clip_url
                and txt != self.url_entry.text().strip()
                and txt != self.fetched_url):
            self._last_clip_url = txt
            self.url_entry.setText(txt)
            self._fetch()

    # ==================================================================
    # Global status helper
    # ==================================================================
    def _set_global(self, text, state):
        self.global_status.setText(text)
        self.global_status.setProperty("state", state)
        self.global_status.style().unpolish(self.global_status)
        self.global_status.style().polish(self.global_status)

    # ==================================================================
    # Window close → minimize to tray (or quit if disabled)
    # ==================================================================
    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        if (self.cfg.get("minimize_to_tray", True)
                and self.tray is not None and self.tray.is_available()):
            event.ignore()
            self.hide()
        else:
            event.accept()
            QApplication.instance().quit()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if (self.windowState() & Qt.WindowMinimized
                    and self.cfg.get("minimize_to_tray", True)
                    and self.tray is not None
                    and self.tray.is_available()):
                # hide on minimize so only the tray icon remains
                QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    @Slot()
    def _tray_show(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_()
        self.activateWindow()

    @Slot()
    def _tray_exit(self):
        self._quitting = True
        for it in self.items:
            it.cancel()
        self.save_downloads()
        if self.tray is not None:
            self.tray.hide()
        QApplication.instance().quit()


# ---------------------------------------------------------------------------
# Background workers (kept here to avoid one-off worker modules)
# ---------------------------------------------------------------------------
class _FetchWorker(QObject):
    fetched_video = Signal(str, dict, list)
    fetched_playlist = Signal(str, dict, list)
    failed = Signal(str)

    def __init__(self, url, cookie_opts, parent=None):
        super().__init__(parent)
        self.url = url
        self.cookie_opts = cookie_opts

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        is_playlist = bool(YT_PLAYLIST_RE.match(self.url))
        try:
            opts = {"quiet": True, "no_warnings": True,
                    "noplaylist": not is_playlist}
            if is_playlist:
                opts["extract_flat"] = "in_playlist"
            opts.update(self.cookie_opts)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            if is_playlist and info.get("entries") is not None:
                entries = [e for e in info["entries"] if e]
                self.fetched_playlist.emit(self.url, info, entries)
                return
            heights = set()
            for f in info.get("formats", []) or []:
                if (f.get("vcodec") and f.get("vcodec") != "none"
                        and f.get("height")):
                    heights.add(f["height"])
            self.fetched_video.emit(
                self.url, info, sorted(heights, reverse=True))
        except Exception as e:
            msg = classify_error(str(e), has_cookies=bool(self.cookie_opts))
            self.failed.emit(msg)


class _PreviewLoader(QObject):
    loaded = Signal(bytes)

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
                self.loaded.emit(buf.getvalue())
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()
