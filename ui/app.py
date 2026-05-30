# -*- coding: utf-8 -*-
"""Main window (QMainWindow). Top bar, options/playlist cards, downloads
panel, search/sort/tabs, persistence, clipboard watcher, tray notifications."""

import io
import json
import os
import shutil
import threading

from PIL import Image
from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPropertyAnimation,
                            QTimer, QUrl, Qt, Signal, Slot)
from PySide6.QtGui import (QAction, QDesktopServices, QGuiApplication, QIcon,
                           QKeySequence, QPixmap, QShortcut)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                               QComboBox, QDialog, QFileDialog, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QMenu, QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QSystemTrayIcon,
                               QVBoxLayout, QWidget)
import yt_dlp

from config import (APP_VERSION, DOWNLOADS_PATH, MEDIA_URL_RE, PREVIEW_H,
                    PREVIEW_W, URL_RE, YT_PLAYLIST_RE,
                    load_config, save_config)
from downloader import DownloadItem
from i18n import Translator, t
from ui.dialogs import (AccountDialog, AboutDialog, SettingsDialog,
                        conflict_dialog, duplicate_dialog, rename_dialog,
                        themed_message)
from ui.download_row import DownloadRow
from ui.icons import icon as _icon, isize as _isize
from ui.tray import Tray
from ui.window_chrome import FramelessMainWindow, TitleBar
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


class _ToolsBridge(QObject):
    """Marshals binaries.ensure_binaries_async's on_done callback (fired on a
    worker thread) back to the main thread via a queued signal."""
    done = Signal(bool, bool)   # ffmpeg_ok, aria2c_ok


# ---------------------------------------------------------------------------
# Sort options — stable keys + i18n labels. The dropdown order here IS the
# order users see, so the most useful options sit at the top.
# ---------------------------------------------------------------------------
SORT_OPTIONS = [
    ("sort_date_added",         "sort_date_added"),
    ("sort_date_added_oldest",  "sort_date_added_oldest"),
    ("sort_name_az",            "sort_name_az"),
    ("sort_name_za",            "sort_name_za"),
    ("sort_size_largest",       "sort_size_largest"),
    ("sort_size_smallest",      "sort_size_smallest"),
    ("sort_duration_longest",   "sort_duration_longest"),
    ("sort_duration_shortest",  "sort_duration_shortest"),
]
_SORT_KEYS = {key for key, _ in SORT_OPTIONS}

# Legacy v1.3 sort_by values → new keys. Pre-v1.4 the dropdown stored
# the localized English display strings; we also handle a few likely
# lowercase variants in case anyone hand-edited their config.
_LEGACY_SORT_MAP = {
    "Last updated": "sort_date_added",
    "last_updated": "sort_date_added",
    "Title":        "sort_name_az",
    "name":         "sort_name_az",
    "Size":         "sort_size_largest",
    "size":         "sort_size_largest",
}


# ---------------------------------------------------------------------------
class App(FramelessMainWindow):
    def __init__(self, app_icon: QIcon = None):
        super().__init__()
        self.setObjectName("AppWindow")
        self._app_icon = app_icon or QIcon()
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)
        self.setWindowTitle(t("app_title"))
        self.resize(780, 820)
        self.setMinimumSize(640, 640)

        # ---- config ----
        self.cfg = load_config()
        self.folder = self.cfg.get("folder", "")
        self.cookie_mode = self.cfg.get("cookie_mode", "none")
        self.cookie_file = self.cfg.get("cookie_file", "")
        self.cfg.setdefault("use_aria2c", False)
        self.cfg.setdefault("clipboard_watch", True)
        self.cfg.setdefault("minimize_to_tray", True)
        self.cfg.setdefault("lang", Translator.lang())
        self.cfg.setdefault("per_page", 15)   # 15 | 30 | 50 | 0 (= all)
        self.cfg.setdefault("compact_mode", False)
        self.cfg.setdefault("theme", "dark")  # "dark" | "light"

        # Pagination
        self.page_size = int(self.cfg.get("per_page", 15) or 0)
        self.current_page = 1

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
        # Sort options are stored under stable string keys so they survive
        # both restarts and i18n switches. Old v1.3 stored a localized
        # display string ("Last updated", "Title", "Size") — migrate
        # those to the new key set before reading.
        self.sort_by = self._migrate_sort_key(
            self.cfg.get("sort_by"), default="sort_date_added")
        self.cfg["sort_by"] = self.sort_by

        self.active_count = 0
        self.batch_completed = 0
        self.batch_failed = 0
        self._last_clip_url = ""
        self._loading = False
        self._quitting = False

        # Bridge: worker → main thread for "one finished"
        self._bridge = _AppBridge(self)
        self._bridge.finished_one.connect(self._on_download_finished)

        # Bridge: binaries fetch worker → main thread
        self._tools_bridge = _ToolsBridge(self)
        self._tools_bridge.done.connect(self._on_tools_ready)

        # ---- UI ----
        self._build_ui()
        self._apply_window_direction()  # mirror children in RTL languages
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

        # First-run: ask where to save videos (once). Deferred so it shows
        # after the window is up, not during construction.
        if not self.folder:
            QTimer.singleShot(350, self._first_run_choose_folder)

    # ==================================================================
    # First-run download-folder setup (happens once)
    # ==================================================================
    def _default_download_dir(self):
        """A sensible default if the user skips the picker: ~/Downloads,
        else ~/Videos, else the home folder."""
        home = os.path.expanduser("~")
        for name in ("Downloads", "Videos"):
            cand = os.path.join(home, name)
            if os.path.isdir(cand):
                return cand
        return home

    def _set_folder(self, path):
        self.folder = path
        self.cfg["folder"] = path
        save_config(self.cfg)

    def _first_run_choose_folder(self):
        """Shown once on first launch (no folder saved yet). Friendly prompt
        then a folder picker. If the user cancels, fall back to a sensible
        default — never block them. They can change it later in Settings."""
        if self.folder:
            return  # already set (race guard)
        # Friendly heads-up first.
        themed_message(self, t("first_run_title"), t("first_run_message"),
                       primary=t("first_run_choose"))
        chosen = QFileDialog.getExistingDirectory(
            self, t("first_run_dialog_title"),
            self._default_download_dir())
        if chosen:
            self._set_folder(chosen)
            self._set_global(t("first_run_saved", folder=chosen), "ok")
        else:
            # Cancelled — use a default silently, don't force them.
            self._set_folder(self._default_download_dir())

    @staticmethod
    def _migrate_sort_key(value, default="sort_date_added"):
        """Coerce a stored sort_by value to one of the current SORT_OPTIONS
        keys. Handles legacy v1.3 values and unrecognised garbage."""
        if value in _SORT_KEYS:
            return value
        return _LEGACY_SORT_MAP.get(value, default)

    # ==================================================================
    # UI construction — frameless rounded shell with custom chrome
    # ==================================================================
    def _build_ui(self):
        # The QMainWindow's central widget is a single rounded solid frame
        # (#WindowShell). The actual rounded clip is done by the
        # FramelessMainWindow base class via setMask in resizeEvent.
        shell_container = QWidget()
        shell_container.setStyleSheet("background: transparent;")
        self.setCentralWidget(shell_container)
        outer_lay = QVBoxLayout(shell_container)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        self.window_shell = QFrame()
        self.window_shell.setObjectName("WindowShell")
        outer_lay.addWidget(self.window_shell)

        root = QVBoxLayout(self.window_shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- Custom title bar ----
        self.title_bar = TitleBar(self.window_shell)
        self.title_bar.cookies_clicked.connect(self._open_account)
        self.title_bar.settings_clicked.connect(self._open_settings)
        self.title_bar.compact_toggled.connect(self._toggle_compact)
        root.addWidget(self.title_bar)

        # ---- Optional download-progress banner (used during update DL) ----
        self._build_update_banner()
        root.addWidget(self.update_banner)
        self.update_banner.hide()

        # ---- URL row (link icon + entry + Fetch) ----
        url_row = QFrame()
        url_row.setObjectName("UrlRow")
        url_row.setFixedHeight(60)
        url_lay = QHBoxLayout(url_row)
        url_lay.setContentsMargins(12, 10, 12, 10)
        url_lay.setSpacing(8)

        # Build a sub-frame so we can place the leading icon inside the input.
        self.url_pill = QFrame(url_row)
        self.url_pill.setObjectName("UrlPillV2")
        self.url_pill.setFixedHeight(36)
        pill_lay = QHBoxLayout(self.url_pill)
        pill_lay.setContentsMargins(0, 0, 0, 0)
        pill_lay.setSpacing(0)
        self.url_entry = QLineEdit()
        self.url_entry.setObjectName("UrlEntryV2")
        self.url_entry.setPlaceholderText(t("url_placeholder"))
        self.url_entry.setClearButtonEnabled(True)
        self.url_entry.returnPressed.connect(self._fetch)
        self.url_entry.textChanged.connect(self._on_url_change)
        self.url_entry.setContextMenuPolicy(Qt.CustomContextMenu)
        self.url_entry.customContextMenuRequested.connect(self._show_url_menu)
        # Leading link icon inside the entry (qtawesome vector).
        from PySide6.QtGui import QAction as _QAction
        link_act = _QAction(self.url_entry)
        link_ic = _icon("link", color="#62666D")
        if not link_ic.isNull():
            link_act.setIcon(link_ic)
        else:
            link_act.setText("🔗")  # fallback if qtawesome missing
        link_act.setEnabled(False)
        self.url_entry.addAction(link_act, QLineEdit.LeadingPosition)
        pill_lay.addWidget(self.url_entry, 1)
        url_lay.addWidget(self.url_pill, 1)

        self.fetch_btn = QPushButton(t("fetch_button"))
        self.fetch_btn.setObjectName("FetchBtnV2")
        self.fetch_btn.clicked.connect(self._fetch)
        url_lay.addWidget(self.fetch_btn, 0)
        root.addWidget(url_row)

        # ----- Indeterminate fetch loading indicator (2 px sliver) -----
        # Shown only while _FetchWorker is in flight so the user knows the
        # app is doing something during the 2–5 s yt-dlp lookup.
        self.fetch_loading_bar = QProgressBar()
        self.fetch_loading_bar.setObjectName("FetchLoadingBar")
        self.fetch_loading_bar.setRange(0, 0)  # 0..0 → indeterminate marquee
        self.fetch_loading_bar.setTextVisible(False)
        self.fetch_loading_bar.setFixedHeight(2)
        self.fetch_loading_bar.setStyleSheet(
            "QProgressBar#FetchLoadingBar {"
            "  background: transparent;"
            "  border: 0;"
            "}"
            "QProgressBar#FetchLoadingBar::chunk {"
            "  background: #5E6AD2;"
            "}"
        )
        self.fetch_loading_bar.hide()
        root.addWidget(self.fetch_loading_bar)

        # ----- SINGLE-VIDEO OPTIONS CARD (hidden until fetch) -----
        self.options_card = QFrame()
        self.options_card.setObjectName("PanelCard")
        oc = QVBoxLayout(self.options_card)
        oc.setContentsMargins(16, 12, 16, 12)
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
        self.quality_combo.addItem("—")
        ctrl.addWidget(self.quality_combo)
        ctrl.addStretch(1)
        self.download_btn = QPushButton(t("download"))
        self.download_btn.setProperty("role", "primary")
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
        pc.setContentsMargins(16, 12, 16, 12)
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
        self.pl_quality_combo.addItems(
            ["2160p (4K)", "1440p (2K)", "1080p", "720p", "480p", "360p"])
        self.pl_quality_combo.setCurrentText("1080p")
        pl_controls.addWidget(self.pl_quality_combo)
        pl_controls.addStretch(1)
        self.pl_download_btn = QPushButton(t("download_selected"))
        self.pl_download_btn.setProperty("role", "primary")
        self.pl_download_btn.clicked.connect(self._add_playlist_downloads)
        pl_controls.addWidget(self.pl_download_btn)
        pc.addLayout(pl_controls)

        root.addWidget(self.playlist_card)
        self.playlist_card.hide()

        # ---- Global status (transient hint line shown under URL row) ----
        self.global_status = QLabel("")
        self.global_status.setObjectName("Hint")
        self.global_status.setContentsMargins(12, 0, 12, 0)
        root.addWidget(self.global_status)

        # ---- Filter row: pills (left) + search/sort (right) ----
        filter_row = QFrame()
        filter_row.setObjectName("FilterRow")
        filter_row.setFixedHeight(52)
        flay = QHBoxLayout(filter_row)
        flay.setContentsMargins(12, 12, 12, 12)
        flay.setSpacing(6)

        self.tabs_btns = []
        self._tab_labels = {"All": t("tab_all"),
                            "Video": t("tab_video"),
                            "Audio": t("tab_audio")}
        for key in ("All", "Video", "Audio"):
            btn = QPushButton(self._tab_labels[key], filter_row)
            btn.setProperty("key", key)
            btn.setProperty("role", "pill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda _=False, k=key: self._on_tab_change(k))
            self.tabs_btns.append(btn)
            flay.addWidget(btn)

        # ---- Search input — always visible, flexible width, slot
        # between pills and sort. Replaces the earlier icon-only button. ----
        self.search_entry = QLineEdit(filter_row)
        self.search_entry.setObjectName("SearchEntryCompact")
        self.search_entry.setPlaceholderText(t("search_placeholder"))
        self.search_entry.setClearButtonEnabled(True)
        self.search_entry.setMinimumWidth(140)
        self.search_entry.setMaximumWidth(280)
        self.search_entry.setSizePolicy(QSizePolicy.Expanding,
                                        QSizePolicy.Fixed)
        # Leading magnifier inside the field.
        from PySide6.QtGui import QAction as _QAction
        search_act = _QAction(self.search_entry)
        s_ic = _icon("search", color="#62666D")
        if not s_ic.isNull():
            search_act.setIcon(s_ic)
        else:
            search_act.setText("🔍")
        search_act.setEnabled(False)
        self.search_entry.addAction(search_act, QLineEdit.LeadingPosition)
        self.search_entry.textChanged.connect(self._on_search)
        # search_btn is no longer in the layout; keep an alias for legacy
        # references / shortcuts.
        self.search_btn = self.search_entry
        flay.addWidget(self.search_entry, 1)

        self.sort_combo = QComboBox(filter_row)
        self.sort_combo.setObjectName("SortCompact")
        for key, label_key in SORT_OPTIONS:
            self.sort_combo.addItem(t(label_key), key)
        idx = self.sort_combo.findData(self.sort_by)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        # The new labels are longer than v1.3's three options (e.g.
        # "Date added (newest)"), so the dropdown needs more room. The
        # popup widens automatically once items render.
        self.sort_combo.setFixedWidth(180)
        self.sort_combo.currentIndexChanged.connect(self._on_sort)
        flay.addWidget(self.sort_combo)

        self.clear_btn = QPushButton("", filter_row)
        self.clear_btn.setProperty("role", "clearDanger")
        self.clear_btn.setToolTip(t("clear_all"))
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        clr_ic = _icon("close", color="#EB5757")
        if not clr_ic.isNull():
            self.clear_btn.setIcon(clr_ic)
            self.clear_btn.setIconSize(_isize(14))
        else:
            self.clear_btn.setText("✕")
        self.clear_btn.clicked.connect(self.clear_all)
        flay.addWidget(self.clear_btn)

        root.addWidget(filter_row)

        # ---- Main downloads panel (no border — sits flush in shell) ----
        panel = QWidget()
        panel.setObjectName("PanelInline")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 8, 12, 0)
        panel_layout.setSpacing(6)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_inner = QWidget()
        self.list_layout = QVBoxLayout(self.list_inner)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(6)
        self.empty_label = QLabel(t("empty_hint"))
        self.empty_label.setObjectName("Hint")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.list_layout.addWidget(self.empty_label)
        self.list_layout.addStretch(1)
        self.list_scroll.setWidget(self.list_inner)
        panel_layout.addWidget(self.list_scroll, 1)

        # ---- Pagination row ----
        pag_row = QFrame()
        pag_row.setObjectName("PaginationRow")
        pag_row.setFixedHeight(36)
        pag_lay = QHBoxLayout(pag_row)
        pag_lay.setContentsMargins(10, 8, 10, 8)
        pag_lay.setSpacing(8)

        self.pagination_summary = QLabel("", pag_row)
        self.pagination_summary.setObjectName("PaginationLabel")
        pag_lay.addWidget(self.pagination_summary, 0)

        pag_lay.addStretch(1)

        self.pagination_wrap = QWidget(pag_row)
        self.pagination_layout = QHBoxLayout(self.pagination_wrap)
        self.pagination_layout.setContentsMargins(0, 0, 0, 0)
        self.pagination_layout.setSpacing(4)
        pag_lay.addWidget(self.pagination_wrap, 0)

        self.per_page_combo = QComboBox(pag_row)
        self.per_page_combo.setObjectName("SortCompact")
        self.per_page_combo.addItem(t("per_page", n=15), 15)
        self.per_page_combo.addItem(t("per_page", n=30), 30)
        self.per_page_combo.addItem(t("per_page", n=50), 50)
        self.per_page_combo.addItem(t("per_page_all"), 0)
        saved = int(self.cfg.get("per_page", 15) or 0)
        idx = self.per_page_combo.findData(saved)
        if idx >= 0:
            self.per_page_combo.setCurrentIndex(idx)
        self.per_page_combo.currentIndexChanged.connect(
            self._on_per_page_change)
        pag_lay.addWidget(self.per_page_combo, 0)

        panel_layout.addWidget(pag_row)

        # count_label is no longer in panel — it lives in footer. Keep an
        # invisible placeholder so legacy retranslate code still works.
        self.count_label = QLabel("", self)
        self.count_label.hide()

        root.addWidget(panel, 1)
        self._main_panel = panel  # kept so external code can reach it

        # ---- Footer strip ----
        self._build_footer(root)

        # ---- Highlight the initial active tab ----
        self._update_pill_state()

        # ---- Drop shadows ----
        self._apply_linear_shadows()

        # ---- Keyboard shortcuts ----
        self._add_shortcuts()

    def _build_footer(self, root):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        from ui.theme import L1, BORDER
        self.footer_strip = QFrame()
        self.footer_strip.setObjectName("FooterStrip")
        self.footer_strip.setFixedHeight(32)
        flay = QHBoxLayout(self.footer_strip)
        flay.setContentsMargins(14, 6, 14, 6)
        flay.setSpacing(8)
        self.footer_left = QLabel("", self.footer_strip)
        self.footer_left.setObjectName("FooterText")
        flay.addWidget(self.footer_left, 1, Qt.AlignVCenter)

        # ---- Right cluster: [● dot] [Update vX.Y.Z pill?] [v1.3.0] ----
        # Locked LTR so the dot is always visually left of the version,
        # regardless of the surrounding RTL content direction.
        self.footer_right_wrap = QWidget(self.footer_strip)
        self.footer_right_wrap.setLayoutDirection(Qt.LeftToRight)
        right_lay = QHBoxLayout(self.footer_right_wrap)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        # 7 px status dot — green/yellow/gray with a soft glow.
        self.footer_status_dot = QLabel("●", self.footer_right_wrap)
        self.footer_status_dot.setStyleSheet(
            "color: #62666D; font-size: 9px; background: transparent;")
        self._footer_dot_glow = QGraphicsDropShadowEffect(
            self.footer_status_dot)
        self._footer_dot_glow.setBlurRadius(8)
        self._footer_dot_glow.setOffset(0, 0)
        self._footer_dot_glow.setColor(QColor(98, 102, 109, 102))
        self.footer_status_dot.setGraphicsEffect(self._footer_dot_glow)
        right_lay.addWidget(self.footer_status_dot, 0, Qt.AlignVCenter)

        # Inline "Update vX.Y.Z" pill — only visible when an update is
        # available. Same brand-tinted styling as before; click triggers
        # _on_update_now (the same handler the title-bar pill used to call).
        self.footer_update_pill = QPushButton("", self.footer_right_wrap)
        self.footer_update_pill.setObjectName("UpdatePill")
        self.footer_update_pill.setCursor(Qt.PointingHandCursor)
        self.footer_update_pill.setStyleSheet(
            "QPushButton#UpdatePill {"
            "  background: rgba(94,106,210,0.15);"
            "  border: 1px solid rgba(130,143,255,0.4);"
            "  border-radius: 9px;"
            "  color: #828FFF;"
            "  padding: 0 8px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "  min-height: 18px;"
            "}"
            "QPushButton#UpdatePill:hover {"
            "  background: rgba(94,106,210,0.25);"
            "}"
        )
        self.footer_update_pill.clicked.connect(self._on_update_now)
        self.footer_update_pill.hide()
        right_lay.addWidget(self.footer_update_pill, 0, Qt.AlignVCenter)

        self.footer_right = QLabel("", self.footer_right_wrap)
        self.footer_right.setObjectName("FooterText")
        right_lay.addWidget(self.footer_right, 0, Qt.AlignVCenter)

        flay.addWidget(self.footer_right_wrap, 0, Qt.AlignVCenter)
        root.addWidget(self.footer_strip)
        self._update_footer_stats()

    def _apply_linear_shadows(self):
        """Drop shadows for elevated cards. The shell itself gets a small
        outer shadow so it reads as a floating window."""
        from ui.theme import (apply_shadow, SHADOW_CARD, SHADOW_PANEL)
        apply_shadow(self.window_shell, **SHADOW_PANEL)
        apply_shadow(self.options_card,  **SHADOW_CARD)
        apply_shadow(self.playlist_card, **SHADOW_CARD)

    # ==================================================================
    # Update banner — slim progress strip shown only DURING download.
    # The "available" announcement lives in the title bar pill now.
    # ==================================================================
    def _build_update_banner(self):
        from ui.theme import (ACCENT_TINT, ACCENT_TINT_BORDER, TEXT)
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        self.update_banner.setStyleSheet(
            "QFrame#UpdateBanner {"
            f"  background: {ACCENT_TINT};"
            f"  border-top: 1px solid {ACCENT_TINT_BORDER};"
            f"  border-bottom: 1px solid {ACCENT_TINT_BORDER};"
            "}"
        )
        self.update_banner.setFixedHeight(36)

        lay = QHBoxLayout(self.update_banner)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)

        self.update_label = QLabel("")
        self.update_label.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-weight: 500;"
            " letter-spacing: -0.15px;")
        lay.addWidget(self.update_label, 1)

        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 1000)
        self.update_progress.setValue(0)
        self.update_progress.setTextVisible(False)
        self.update_progress.setFixedWidth(140)
        self.update_progress.hide()
        lay.addWidget(self.update_progress)

        # Internal state (also used by the title-bar pill click handler)
        self._update_tag = ""
        self._update_asset_url = ""
        self._update_size = 0
        self._update_state = "unknown"

    # ==================================================================
    # Update flow
    # ==================================================================
    def start_update_check(self, show_status: bool = False):
        """Run the GitHub release check. `show_status=True` means the user
        manually clicked Check-for-updates — we surface progress AND any
        failure in the status bar. `show_status=False` is the silent
        startup auto-check: success updates the dot, failure leaves it
        gray (only the stderr log records what went wrong)."""
        self._update_check_manual = bool(show_status)
        if show_status:
            self._set_update_status("checking")
        self._update_checker = UpdateChecker(self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.check_failed.connect(self._on_update_check_failed)
        self._update_checker.no_update.connect(self._on_no_update)
        self._update_checker.start()

    @Slot(str, str, int)
    def _on_update_available(self, tag, asset_url, size):
        self._update_tag = tag
        self._update_asset_url = asset_url
        self._update_size = size
        # The user-facing announcement is the yellow dot + "Update vX.Y.Z"
        # pill in the title bar — no inline banner unless we actually
        # start downloading.
        self.update_banner.hide()
        self._set_update_status("available", tag)
        # If the user manually clicked "Check for updates", surface a clear
        # result dialog (not just the silent footer dot) with an action.
        if getattr(self, "_update_check_manual", False):
            self._update_check_manual = False
            clean = (tag or "").lstrip("vV")
            if themed_message(
                    self, t("update_check_title"),
                    t("update_available_msg",
                      version=f"v{clean}", current=APP_VERSION),
                    primary=t("update_now"), secondary=t("update_later")):
                self._on_update_now()

    @Slot()
    def _on_no_update(self):
        self._set_update_status("up_to_date")
        if getattr(self, "_update_check_manual", False):
            self._update_check_manual = False
            themed_message(
                self, t("update_check_title"),
                t("update_uptodate_msg", version=APP_VERSION),
                primary=t("close"))

    @Slot(str)
    def _on_update_check_failed(self, _msg):
        # Only display the failure if the user explicitly asked. Auto-checks
        # fail silently — we leave the dot gray ("unknown") so transient
        # network hiccups don't spook the user. The real error already
        # went to stderr from UpdateChecker.
        if getattr(self, "_update_check_manual", False):
            self._update_check_manual = False
            self._set_update_status("failed")
            themed_message(
                self, t("update_check_title"), t("update_failed_msg"),
                primary=t("close"))
        else:
            self._set_update_status("unknown")

    @Slot()
    def _on_update_now(self):
        if not is_frozen() or not self._update_asset_url:
            QDesktopServices.openUrl(QUrl(github_release_url()))
            return
        # start the download — show the slim progress banner just below
        # the title bar for the duration of the swap.
        self.update_progress.show()
        self.update_progress.setValue(0)
        self.update_label.setText(t("update_downloading", percent=0))
        self.update_banner.show()
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

    # ==================================================================
    # Update status — rendered as the footer's dot + inline "Update" pill.
    # Moved from the title bar in v1.4 so the title bar is identical in
    # every language and stays minimal.
    # ==================================================================
    def _set_update_status(self, state: str, version: str = ""):
        """state ∈ {unknown, checking, up_to_date, available, failed}"""
        self._update_state = state
        self._update_tag = version or self._update_tag
        try:
            from PySide6.QtGui import QColor
            colors = {
                "unknown":     ("#62666D", (98, 102, 109)),
                "checking":    ("#62666D", (98, 102, 109)),
                "up_to_date":  ("#27A644", (39, 166, 68)),
                "available":   ("#F0BF00", (240, 191, 0)),
                "failed":      ("#62666D", (98, 102, 109)),
            }
            hex_, rgb = colors.get(state, colors["unknown"])
            self.footer_status_dot.setStyleSheet(
                f"color: {hex_}; font-size: 9px; background: transparent;")
            r, g, b = rgb
            self._footer_dot_glow.setColor(QColor(r, g, b, 102))

            if state == "available" and version:
                clean = version.lstrip("vV")
                self.footer_update_pill.setText(
                    t("status_update_available", version=f"v{clean}"))
                self.footer_update_pill.show()
            else:
                self.footer_update_pill.hide()
        except Exception:
            pass

    # ==================================================================
    # Pagination
    # ==================================================================
    def _on_per_page_change(self, _idx):
        data = self.per_page_combo.currentData()
        self.page_size = int(data or 0)
        self.cfg["per_page"] = self.page_size
        save_config(self.cfg)
        self.current_page = 1
        self._refresh_list()

    def _render_pagination(self, total_pages: int):
        # clear existing children
        while self.pagination_layout.count():
            it = self.pagination_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        if total_pages <= 1:
            self.pagination_wrap.setVisible(False)
            return
        self.pagination_wrap.setVisible(True)

        def make_btn(text, page=None, active=False, enabled=True,
                     icon_name=None):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("role",
                          "pageBtnActive" if active else "pageBtn")
            b.setEnabled(enabled)
            if icon_name:
                col = "#62666D" if enabled else "#3E3E44"
                ic = _icon(icon_name, color=col)
                if not ic.isNull():
                    b.setText("")
                    b.setIcon(ic)
                    b.setIconSize(_isize(11))
            if page is not None and enabled and not active:
                b.clicked.connect(lambda _=False, p=page: self._goto_page(p))
            return b

        cur = self.current_page
        # In RTL, the "previous" arrow points right and "next" points left
        # so the icons match the reading direction.
        is_rtl = Translator.is_rtl()
        prev_icon = "chevron_r" if is_rtl else "chevron_l"
        next_icon = "chevron_l" if is_rtl else "chevron_r"
        # prev arrow
        self.pagination_layout.addWidget(
            make_btn("‹", page=max(1, cur - 1),
                     enabled=cur > 1, icon_name=prev_icon))

        # window of page numbers with ellipsis
        def add_page(p):
            self.pagination_layout.addWidget(
                make_btn(str(p), page=p, active=(p == cur)))

        def add_dots():
            lbl = QLabel("…")
            lbl.setStyleSheet("color: #8A8F98; padding: 0 4px;")
            self.pagination_layout.addWidget(lbl)

        pages_to_show = set([1, total_pages, cur, cur - 1, cur + 1])
        pages = sorted(p for p in pages_to_show if 1 <= p <= total_pages)
        prev = 0
        for p in pages:
            if prev and p > prev + 1:
                add_dots()
            add_page(p)
            prev = p

        # next arrow
        self.pagination_layout.addWidget(
            make_btn("›", page=min(total_pages, cur + 1),
                     enabled=cur < total_pages, icon_name=next_icon))

    def _goto_page(self, page: int):
        self.current_page = max(1, page)
        self._refresh_list()

    # ==================================================================
    # Live language switch
    # ==================================================================
    def set_language(self, code: str):
        if code not in Translator.AVAILABLE:
            return
        if code == Translator.lang():
            return
        Translator.load(code)
        self.cfg["lang"] = code
        save_config(self.cfg)
        # flip layout direction live (window + every child + open dialogs)
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(
                Qt.RightToLeft if Translator.is_rtl() else Qt.LeftToRight)
        self._apply_window_direction()
        self.retranslate()

    # ==================================================================
    # Live theme switch (dark / light) — mirrors the language flow.
    # ==================================================================
    def set_theme(self, mode: str):
        mode = mode if mode in ("dark", "light") else "dark"
        if mode == self.cfg.get("theme", "dark"):
            return
        self.cfg["theme"] = mode
        save_config(self.cfg)
        from ui.theme import apply_theme
        app = QApplication.instance()
        apply_theme(app, mode)
        self._after_theme_change()

    def _after_theme_change(self):
        """Re-apply the bits that carry inline (non-QSS) colours so the swap
        looks complete without a restart. The global stylesheet cascade
        already restyles everything that uses object-name / role selectors."""
        try:
            # Footer status dot colour is status-driven inline — re-assert it.
            self._set_update_status(self._update_state, self._update_tag)
        except Exception:
            pass
        # Repolish the shell + open dialogs so QSS-driven widgets refresh.
        for w in [self.window_shell] + list(self.findChildren(QDialog)):
            try:
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()
            except Exception:
                pass

    def _apply_window_direction(self):
        """Push the active text direction onto the window + chrome.
        The title bar reorders its brand / right-icons clusters; all
        other widgets inherit and mirror naturally."""
        rtl = Translator.is_rtl()
        direction = Qt.RightToLeft if rtl else Qt.LeftToRight
        self.setLayoutDirection(direction)
        try:
            self.title_bar.apply_layout_direction(direction)
        except Exception:
            pass
        # Pagination chevrons swap meaning in RTL — re-render so they
        # use chevron-right for "previous" etc.
        try:
            self._refresh_list()
        except Exception:
            pass
        # Any open dialog also flips.
        for dlg in self.findChildren(QDialog):
            try:
                dlg.setLayoutDirection(direction)
            except Exception:
                pass

    def retranslate(self):
        """Re-apply every translated string. Called after the active language
        is swapped (also walks open dialogs + per-row widgets + tray).

        Individual sections are protected so one widget-level failure doesn't
        block the rest of the tree from updating."""
        self.setWindowTitle(t("app_title"))

        # URL row
        self.url_entry.setPlaceholderText(t("url_placeholder"))
        self.fetch_btn.setText(t("fetch_button"))
        # Title bar button tooltips
        try:
            self.title_bar.compact_btn.setToolTip(t("compact_mode"))
            self.title_bar.cookies_btn.setToolTip(t("account"))
            self.title_bar.settings_btn.setToolTip(t("settings"))
        except Exception:
            pass

        # Options card
        self._retranslate_segmented(
            self.format_btns,
            {"mp4": t("format_mp4"), "mp3": t("format_mp3")})
        self.download_btn.setText(t("download"))
        if self.options_card.isVisible():
            self.status_label.setText(t("pick_format_hint"))

        # Playlist card
        self._retranslate_segmented(
            self.pl_format_btns,
            {"mp4": t("format_mp4"), "mp3": t("format_mp3")})
        self.pl_download_btn.setText(t("download_selected"))

        # Filter pills — re-cache labels and refresh counts
        self._tab_labels = {"All": t("tab_all"),
                            "Video": t("tab_video"),
                            "Audio": t("tab_audio")}
        self._update_pill_counts()

        # Search / sort / clear
        self.search_entry.setPlaceholderText(t("search_placeholder"))
        self._rebuild_sort_combo()
        self.clear_btn.setToolTip(t("clear_all"))

        # Empty hint + per-page combo
        self.empty_label.setText(t("empty_hint"))
        self._rebuild_per_page_combo()

        # Status dot via title bar
        self._set_update_status(self._update_state, self._update_tag)
        self._update_footer_stats()

        # Per-row UI
        for row in self.rows.values():
            try:
                row.retranslate()
            except Exception:
                pass

        # Tray
        if self.tray is not None:
            try:
                self.tray.retranslate()
            except Exception:
                pass

        # Open dialogs (children + parented popups)
        for dlg in self.findChildren(QDialog):
            if hasattr(dlg, "retranslate"):
                try:
                    dlg.retranslate()
                except Exception:
                    pass

        # Re-render list (pagination labels include translated text)
        self._refresh_list()

    def _retranslate_segmented(self, buttons, key_to_label):
        for b in buttons:
            key = b.property("key")
            if key in key_to_label:
                b.setText(key_to_label[key])

    def _rebuild_sort_combo(self):
        current_key = self.sort_combo.currentData() or self.sort_by
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        for key, label_key in SORT_OPTIONS:
            self.sort_combo.addItem(t(label_key), key)
        idx = self.sort_combo.findData(current_key)
        if idx >= 0:
            self.sort_combo.setCurrentIndex(idx)
        self.sort_combo.blockSignals(False)

    def _rebuild_per_page_combo(self):
        current = self.per_page_combo.currentData()
        self.per_page_combo.blockSignals(True)
        self.per_page_combo.clear()
        self.per_page_combo.addItem(t("per_page", n=15), 15)
        self.per_page_combo.addItem(t("per_page", n=30), 30)
        self.per_page_combo.addItem(t("per_page", n=50), 50)
        self.per_page_combo.addItem(t("per_page_all"), 0)
        idx = self.per_page_combo.findData(current)
        if idx >= 0:
            self.per_page_combo.setCurrentIndex(idx)
        self.per_page_combo.blockSignals(False)

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
        # ffmpeg / aria2c ship bundled (installer) or are fetched silently on
        # first run (lean portable exe). We NEVER ask the user to install
        # anything. If anything's missing, show a small non-blocking
        # "Preparing…" hint (never a frozen window) and fetch in background.
        import binaries
        if binaries.have_ffmpeg() and binaries.aria2c_path():
            return
        self._set_global(t("preparing_tools"), "muted")
        binaries.ensure_binaries_async(on_done=self._tools_bridge.done.emit)

    @Slot(bool, bool)
    def _on_tools_ready(self, ffmpeg_ok, _aria_ok):
        # Clear the "Preparing…" hint on success; on failure show ONE
        # friendly bilingual message — never a stack trace, never a
        # "go install ffmpeg" instruction.
        if ffmpeg_ok:
            if self.global_status.text() == t("preparing_tools"):
                self._set_global("", "")
        else:
            self._set_global(t("tools_failed"), "err")

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

    def _open_shortcuts(self):
        from ui.dialogs import ShortcutsDialog
        ShortcutsDialog(self).exec()

    # ==================================================================
    # URL handling
    # ==================================================================
    def _on_format_change(self, key):
        if key == "mp3":
            self.quality_combo.clear()
            self.quality_combo.addItems(["320 kbps", "192 kbps", "128 kbps"])
            self.quality_combo.setCurrentText("320 kbps")
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
        if URL_RE.match(url) and url != self.fetched_url:
            self._autofetch_timer.start(500)

    def _autofetch(self):
        url = self.url_entry.text().strip()
        if not url or url == self.fetched_url:
            return
        if not URL_RE.match(url):
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
        # Marquee bar — indeterminate animation runs natively while the
        # worker thread queries yt-dlp.
        self.fetch_loading_bar.show()
        cookie_opts = self._cookie_opts()
        self._fetcher = _FetchWorker(url, cookie_opts, self)
        self._fetcher.fetched_video.connect(self._fetch_done)
        self._fetcher.fetched_playlist.connect(self._playlist_fetched)
        self._fetcher.failed.connect(self._fetch_failed)
        self._fetcher.start()

    @Slot(str, dict, list)
    def _fetch_done(self, url, info, heights):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch_button"))
        self.fetch_loading_bar.hide()
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
        self.fetch_btn.setText(t("fetch_button"))
        self.fetch_loading_bar.hide()
        self._set_global(t("fetch_failed", msg=msg), "err")

    # ==================================================================
    # Playlist
    # ==================================================================
    @Slot(str, dict, list)
    def _playlist_fetched(self, url, info, entries):
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch_button"))
        self.fetch_loading_bar.hide()
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
            self.pl_quality_combo.setCurrentText("320 kbps")
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
            bitrate = int(digits) if digits else 320
        else:
            fmt = "mp4"
            digits = "".join(ch for ch in q.split("p")[0] if ch.isdigit())
            height = int(digits) if digits else 1080
            bitrate = 320

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
            return "mp3", None, int(digits) if digits else 320
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
                               bitrate=320, custom_filename=None):
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
        self._update_pill_state()
        self._refresh_list()

    def _update_pill_state(self):
        for b in self.tabs_btns:
            key = b.property("key")
            active = (key == self.active_tab)
            b.setProperty("role", "pillActive" if active else "pill")
            try:
                b.style().unpolish(b); b.style().polish(b)
            except Exception:
                pass

    def _update_pill_counts(self, filtered_total=None):
        """Pill labels include the count for that filter category."""
        n_all   = len(self.items)
        n_video = sum(1 for it in self.items if it.fmt == "mp4")
        n_audio = sum(1 for it in self.items if it.fmt == "mp3")
        counts = {"All": n_all, "Video": n_video, "Audio": n_audio}
        for b in self.tabs_btns:
            key = b.property("key")
            label = self._tab_labels.get(key, key)
            b.setText(f"{label} · {counts.get(key, 0)}")

    # ------------------------------------------------------------------
    # Footer stats (left: active/completed, right: speed · version)
    # ------------------------------------------------------------------
    def _update_footer_stats(self):
        try:
            completed = sum(1 for i in self.items if i.status == "completed")
            self.footer_left.setText(
                t("footer_active_completed",
                  active=self.active_count, completed=completed))
            # Aggregate live download speed by hooking into items — for now
            # we just show the version on the right.
            self.footer_right.setText(
                t("footer_speed_idle", version=APP_VERSION))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Compact mode (NEW): shrink rows in place
    # ------------------------------------------------------------------
    def _toggle_compact(self):
        new_val = not bool(self.cfg.get("compact_mode", False))
        self.cfg["compact_mode"] = new_val
        save_config(self.cfg)
        for row in self.rows.values():
            try:
                row.set_compact(new_val)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------
    def _add_shortcuts(self):
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)
            return s

        sc("Ctrl+W", self.close)
        sc("Ctrl+M", self.showMinimized)
        sc("F11",    self._toggle_max_restore)
        sc("Ctrl+,", self._open_settings)
        sc("Ctrl+L", lambda: (self.url_entry.setFocus(),
                              self.url_entry.selectAll()))
        sc("Ctrl+F", lambda: (self.search_entry.setFocus(),
                              self.search_entry.selectAll()))
        sc("Ctrl+V", self._shortcut_paste_url)
        sc("F1",     self._open_shortcuts)

    def _toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # (Search expand-on-click + animation removed — see the comment in
    # the filter row build. The hidden self.search_entry is kept so the
    # filter pipeline + i18n call sites still work; click currently no-ops.)

    def _shortcut_paste_url(self):
        # Only intercept when the URL field has focus or no other input does.
        try:
            focused = QApplication.focusWidget()
        except Exception:
            focused = None
        if focused is not None and focused is not self.url_entry:
            # Let the focused widget handle paste itself.
            if isinstance(focused, QLineEdit):
                focused.paste()
                return
        self.url_entry.setFocus()
        self.url_entry.paste()
        # if it looks like any URL, kick auto-fetch (yt-dlp handles 1800+ sites)
        if URL_RE.match(self.url_entry.text().strip()):
            self._fetch()

    def _on_search(self, _txt):
        self.search_query = self.search_entry.text().strip()
        self._refresh_list()

    def _on_sort(self, _idx):
        key = self.sort_combo.currentData() or "sort_date_added"
        self.sort_by = self._migrate_sort_key(key)
        self.cfg["sort_by"] = self.sort_by
        save_config(self.cfg)
        self._refresh_list()

    def _refresh_list(self):
        # collect visible items by current filter
        filtered = []
        for it in self.items:
            row = self.rows.get(id(it))
            if not row:
                continue
            if row.matches(self.search_query, self.active_tab):
                filtered.append(it)
            else:
                row.setVisibleRow(False)

        # Helpers — each returns None for "missing field". Rows with a
        # missing field always sink to the end regardless of direction.
        def _name_key(it):
            v = (it.custom_filename or it.title or "").strip()
            return v.lower() or None

        def _size_key(it):
            v = it.size_on_disk or it.size_bytes
            return v if v else None

        def _dur_key(it):
            return it.duration if it.duration else None

        def _added_key(it):
            return it.added_at or None

        def _sort_with_missing_last(key_fn, reverse=False):
            have, miss = [], []
            for it in filtered:
                if key_fn(it) is None:
                    miss.append(it)
                else:
                    have.append(it)
            have.sort(key=key_fn, reverse=reverse)
            return have + miss

        if self.sort_by == "sort_name_az":
            filtered = _sort_with_missing_last(_name_key)
        elif self.sort_by == "sort_name_za":
            filtered = _sort_with_missing_last(_name_key, reverse=True)
        elif self.sort_by == "sort_size_largest":
            filtered = _sort_with_missing_last(_size_key, reverse=True)
        elif self.sort_by == "sort_size_smallest":
            filtered = _sort_with_missing_last(_size_key)
        elif self.sort_by == "sort_duration_longest":
            filtered = _sort_with_missing_last(_dur_key, reverse=True)
        elif self.sort_by == "sort_duration_shortest":
            filtered = _sort_with_missing_last(_dur_key)
        elif self.sort_by == "sort_date_added_oldest":
            filtered = _sort_with_missing_last(_added_key)
        else:
            # Default: sort_date_added (newest first). This IS the
            # download history order — added_at is set when the row
            # first enters the session.
            filtered = _sort_with_missing_last(_added_key, reverse=True)

        # Pagination: slice to current page.
        total = len(filtered)
        if self.page_size > 0:
            total_pages = max(1, (total + self.page_size - 1) // self.page_size)
            if self.current_page > total_pages:
                self.current_page = total_pages
            start = (self.current_page - 1) * self.page_size
            end = start + self.page_size
            page_items = filtered[start:end]
        else:
            total_pages = 1
            self.current_page = 1
            page_items = filtered

        # Hide rows that are filtered-in but on a different page
        on_page_ids = {id(it) for it in page_items}
        for it in filtered:
            if id(it) not in on_page_ids:
                row = self.rows.get(id(it))
                if row:
                    row.setVisibleRow(False)

        # Reorder visible rows in the layout
        for it in page_items:
            row = self.rows.get(id(it))
            if not row:
                continue
            self.list_layout.removeWidget(row)
        for it in page_items:
            row = self.rows.get(id(it))
            if not row:
                continue
            idx = self.list_layout.count() - 1
            self.list_layout.insertWidget(idx, row)
            row.setVisibleRow(True)

        self.empty_label.setVisible(len(self.items) == 0)
        self.count_label.setText(t("downloads_count", count=total))
        self._render_pagination(total_pages)

        # Pagination summary ("Showing 4 of 17")
        shown_n = len(page_items) if self.page_size > 0 else total
        self.pagination_summary.setText(
            t("pagination_showing", current=shown_n, total=total))

        # Pill counts ("All · 17")
        self._update_pill_counts(filtered_total=total)
        # Footer line
        self._update_footer_stats()

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
        self._update_footer_stats()

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
        self._update_footer_stats()

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
        if (MEDIA_URL_RE.match(txt)
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
