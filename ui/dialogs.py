# -*- coding: utf-8 -*-
"""Qt dialogs: Settings, Account/cookies, Rename, File-conflict,
Duplicate-video confirm, yt-dlp updater, About."""

import os
import shutil
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout)

from config import APP_VERSION, COOKIE_MODES, save_config
from i18n import Translator, t
from utils import classify_error, clean_error


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle(t("settings_title"))
        self.setMinimumSize(620, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # --- folder ---
        self.folder_header = self._header(t("download_folder"))
        root.addWidget(self.folder_header)
        folder_row = QHBoxLayout()
        self.folder_lbl = QLabel(app.folder or t("not_set"))
        self.folder_lbl.setStyleSheet("color: #D0D6E0;")
        self.change_btn = QPushButton(t("change"))
        self.change_btn.setProperty("role", "primary")
        self.change_btn.clicked.connect(self._pick_folder)
        folder_row.addWidget(self.folder_lbl, 1)
        folder_row.addWidget(self.change_btn, 0)
        root.addLayout(folder_row)

        # --- language ---
        root.addSpacing(8)
        self.lang_header = self._header(t("language"))
        root.addWidget(self.lang_header)
        lang_row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("العربية", "ar")
        self.lang_combo.addItem("English", "en")
        current = app.cfg.get("lang", "ar")
        idx = self.lang_combo.findData(current)
        self.lang_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_change)
        lang_row.addWidget(self.lang_combo, 0)
        lang_row.addStretch(1)
        root.addLayout(lang_row)
        self.lang_hint = QLabel(t("language_hint"))
        self.lang_hint.setObjectName("Hint")
        self.lang_hint.setWordWrap(True)
        root.addWidget(self.lang_hint)

        # --- aria2c ---
        root.addSpacing(8)
        self.aria_chk = QCheckBox(t("use_aria2c"))
        self.aria_chk.setProperty("role", "switch")
        self.aria_chk.setChecked(bool(app.cfg.get("use_aria2c", False)))
        self.aria_chk.toggled.connect(self._on_aria_toggle)
        root.addWidget(self.aria_chk)
        self.aria_hint = QLabel()
        self.aria_hint.setObjectName("Hint")
        self.aria_hint.setWordWrap(True)
        root.addWidget(self.aria_hint)
        self._refresh_aria_hint()

        # --- clipboard watch ---
        root.addSpacing(8)
        self.clip_chk = QCheckBox(t("clipboard_watch"))
        self.clip_chk.setProperty("role", "switch")
        self.clip_chk.setChecked(bool(app.cfg.get("clipboard_watch", True)))
        self.clip_chk.toggled.connect(self._on_clip_toggle)
        root.addWidget(self.clip_chk)

        # --- minimize to tray ---
        self.tray_chk = QCheckBox(t("minimize_to_tray"))
        self.tray_chk.setProperty("role", "switch")
        self.tray_chk.setChecked(bool(app.cfg.get("minimize_to_tray", True)))
        self.tray_chk.toggled.connect(self._on_tray_toggle)
        root.addWidget(self.tray_chk)

        # --- check for updates (Nazzil itself) ---
        root.addSpacing(12)
        chk_row = QHBoxLayout()
        self.app_update_header = self._header(t("app_short"))
        chk_row.addWidget(self.app_update_header)
        chk_row.addStretch(1)
        self.check_updates_btn = QPushButton(t("check_for_updates"))
        self.check_updates_btn.clicked.connect(self._check_app_updates)
        chk_row.addWidget(self.check_updates_btn)
        root.addLayout(chk_row)

        # --- yt-dlp updater ---
        root.addSpacing(8)
        upd_row = QHBoxLayout()
        self.ytdlp_header = self._header("yt-dlp")
        upd_row.addWidget(self.ytdlp_header)
        upd_row.addStretch(1)
        self.update_btn = QPushButton(t("update_ytdlp"))
        self.update_btn.clicked.connect(self._do_update)
        upd_row.addWidget(self.update_btn)
        root.addLayout(upd_row)
        self.update_status = QLabel()
        self.update_status.setObjectName("Hint")
        self.update_status.setWordWrap(True)
        root.addWidget(self.update_status)

        root.addStretch(1)

        # --- footer: About + config-saved hint ---
        footer = QHBoxLayout()
        self.about_btn = QPushButton(t("about"))
        self.about_btn.clicked.connect(self._open_about)
        footer.addWidget(self.about_btn)
        footer.addStretch(1)
        self.cfg_hint = QLabel(t("config_saved_at"))
        self.cfg_hint.setObjectName("Hint")
        footer.addWidget(self.cfg_hint)
        root.addLayout(footer)

    def _header(self, text):
        l = QLabel(text)
        l.setObjectName("SectionHeader")
        return l

    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, t("download_folder"))
        if d:
            self.app.folder = d
            self.app.cfg["folder"] = d
            save_config(self.app.cfg)
            self.folder_lbl.setText(d)

    def _on_lang_change(self, _idx):
        code = self.lang_combo.currentData()
        # Persist + delegate the live flip to App, which retranslates the
        # whole UI tree (including this dialog).
        if hasattr(self.app, "set_language"):
            self.app.set_language(code)

    def _on_aria_toggle(self, val):
        self.app.cfg["use_aria2c"] = bool(val)
        save_config(self.app.cfg)
        self._refresh_aria_hint()

    def _refresh_aria_hint(self):
        present = shutil.which("aria2c") is not None
        if self.aria_chk.isChecked() and not present:
            self.aria_hint.setText(t("aria2c_hint_missing"))
        elif present:
            self.aria_hint.setText(t("aria2c_hint_on"))
        else:
            self.aria_hint.setText(t("aria2c_hint_off"))

    def _on_clip_toggle(self, val):
        self.app.cfg["clipboard_watch"] = bool(val)
        save_config(self.app.cfg)

    def _on_tray_toggle(self, val):
        self.app.cfg["minimize_to_tray"] = bool(val)
        save_config(self.app.cfg)

    def _check_app_updates(self):
        if hasattr(self.app, "start_update_check"):
            self.app.start_update_check(show_status=True)

    def _open_about(self):
        AboutDialog(self).exec()

    # --- yt-dlp update (runs in a thread, reports via Signal) ---
    def _do_update(self):
        self.update_btn.setEnabled(False)
        self.update_btn.setText(t("updating_ytdlp"))
        self.update_status.setText(t("update_running"))
        self._updater = _UpdaterWorker(self)
        self._updater.done.connect(self._on_update_done)
        self._updater.start()

    @Slot(str, str)
    def _on_update_done(self, msg, level):
        self.update_btn.setEnabled(True)
        self.update_btn.setText(t("update_ytdlp"))
        self.update_status.setText(msg)

    # ------------------------------------------------------------------
    # Live language switch
    # ------------------------------------------------------------------
    def retranslate(self):
        try:
            self.setWindowTitle(t("settings_title"))
            self.folder_header.setText(t("download_folder"))
            self.change_btn.setText(t("change"))
            if not self.app.folder:
                self.folder_lbl.setText(t("not_set"))
            self.lang_header.setText(t("language"))
            self.lang_hint.setText(t("language_hint"))
            self.aria_chk.setText(t("use_aria2c"))
            self._refresh_aria_hint()
            self.clip_chk.setText(t("clipboard_watch"))
            self.tray_chk.setText(t("minimize_to_tray"))
            self.app_update_header.setText(t("app_short"))
            self.check_updates_btn.setText(t("check_for_updates"))
            self.update_btn.setText(t("update_ytdlp"))
            self.about_btn.setText(t("about"))
            self.cfg_hint.setText(t("config_saved_at"))
        except Exception:
            pass


class _UpdaterWorker(QObject):
    done = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                capture_output=True, text=True, timeout=180)
            out = (proc.stdout or "") + (proc.stderr or "")
            low = out.lower()
            if proc.returncode != 0:
                self.done.emit(
                    t("update_failed", msg=clean_error(out)), "err")
            elif "already satisfied" in low and "upgrad" not in low:
                self.done.emit(t("update_already"), "muted")
            else:
                self.done.emit(t("update_success"), "ok")
        except Exception as e:
            self.done.emit(
                t("update_failed", msg=clean_error(str(e))), "err")


# ---------------------------------------------------------------------------
# Account / cookies
# ---------------------------------------------------------------------------
class AccountDialog(QDialog):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle(t("account_title"))
        self.setMinimumSize(580, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        self.header = QLabel(t("account_source"))
        self.header.setObjectName("SectionHeader")
        self.header.setWordWrap(True)
        root.addWidget(self.header)

        src_row = QHBoxLayout()
        self.combo = QComboBox()
        for key, label_key in COOKIE_MODES:
            self.combo.addItem(t(label_key), key)
        idx = self.combo.findData(app.cookie_mode)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self.combo.currentIndexChanged.connect(self._refresh)

        self.test_btn = QPushButton(t("test_login"))
        self.test_btn.clicked.connect(self._test)

        src_row.addWidget(self.combo, 0)
        src_row.addWidget(self.test_btn, 0)
        src_row.addStretch(1)
        root.addLayout(src_row)

        self.test_result = QLabel("")
        self.test_result.setObjectName("Hint")
        self.test_result.setWordWrap(True)
        root.addWidget(self.test_result)

        self.hint = QLabel("")
        self.hint.setObjectName("Hint")
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)

        # cookies.txt file row (visible only in file mode)
        self.file_row_widget = QHBoxLayout()
        self.file_lbl = QLabel(
            os.path.basename(app.cookie_file) if app.cookie_file
            else t("no_file_selected"))
        self.file_lbl.setStyleSheet("color: #D0D6E0;")
        self.pick_btn = QPushButton(t("pick_file"))
        self.pick_btn.clicked.connect(self._pick_file)
        self.file_row_widget.addWidget(self.file_lbl, 1)
        self.file_row_widget.addWidget(self.pick_btn, 0)
        self.file_row_container = QHBoxLayout()
        self.file_row_container.addLayout(self.file_row_widget)
        root.addLayout(self.file_row_container)

        root.addStretch(1)

        self._refresh()

    def _refresh(self, *_):
        code = self.combo.currentData() or "none"
        self.app.cookie_mode = code
        self.app.cfg["cookie_mode"] = code
        save_config(self.app.cfg)
        is_file = (code == "file")
        self.file_lbl.setVisible(is_file)
        self.pick_btn.setVisible(is_file)
        if code == "file":
            self.hint.setText(t("cookie_hint_file"))
        elif code == "none":
            self.hint.setText(t("cookie_hint_none"))
        elif code == "firefox":
            self.hint.setText(t("cookie_hint_firefox"))
        else:
            self.hint.setText(t("cookie_hint_chromium"))

    def _pick_file(self):
        p, _ = QFileDialog.getOpenFileName(
            self, t("pick_file"), "", "Cookies / Text (*.txt);;All files (*)")
        if p:
            self.app.cookie_file = p
            self.app.cfg["cookie_file"] = p
            save_config(self.app.cfg)
            self.file_lbl.setText(os.path.basename(p))

    def _test(self):
        cookie_opts = self.app._cookie_opts()
        if not cookie_opts:
            self.test_result.setText(t("test_no_source"))
            return
        self.test_btn.setEnabled(False)
        self.test_btn.setText(t("testing"))
        self.test_result.setText(t("test_checking"))
        self._tester = _LoginTester(cookie_opts, self)
        self._tester.done.connect(self._on_test_done)
        self._tester.start()

    @Slot(bool, str)
    def _on_test_done(self, ok, msg):
        self.test_btn.setEnabled(True)
        self.test_btn.setText(t("test_login"))
        self.test_result.setText(msg)

    # ------------------------------------------------------------------
    # Live language switch
    # ------------------------------------------------------------------
    def retranslate(self):
        try:
            self.setWindowTitle(t("account_title"))
            self.header.setText(t("account_source"))
            self.test_btn.setText(t("test_login"))
            self.pick_btn.setText(t("pick_file"))
            if not self.app.cookie_file:
                self.file_lbl.setText(t("no_file_selected"))
            # rebuild combo items (preserve current data key)
            current_key = self.combo.currentData()
            self.combo.blockSignals(True)
            self.combo.clear()
            for key, label_key in COOKIE_MODES:
                self.combo.addItem(t(label_key), key)
            idx = self.combo.findData(current_key)
            if idx >= 0:
                self.combo.setCurrentIndex(idx)
            self.combo.blockSignals(False)
            self._refresh()
        except Exception:
            pass


class _LoginTester(QObject):
    done = Signal(bool, str)

    def __init__(self, cookie_opts, parent=None):
        super().__init__(parent)
        self.cookie_opts = cookie_opts

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True,
                "extract_flat": True, "playlistend": 1,
                "skip_download": True}
        opts.update(self.cookie_opts)
        ok, msg = False, ""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    "https://www.youtube.com/feed/subscriptions",
                    download=False)
            ok = bool(info and (info.get("entries") or info.get("title")))
            msg = t("test_ok") if ok else t("test_no_entries")
        except Exception as e:
            msg = classify_error(str(e), has_cookies=True) or clean_error(str(e))
        self.done.emit(ok, msg)


# ---------------------------------------------------------------------------
# Rename — returns the entered name or None on cancel.
# ---------------------------------------------------------------------------
def rename_dialog(parent, current):
    dlg = QDialog(parent)
    dlg.setWindowTitle(t("rename_title"))
    dlg.setMinimumSize(480, 200)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(18, 18, 18, 18)
    root.setSpacing(8)

    h = QLabel(t("rename_prompt"))
    h.setObjectName("SectionHeader")
    root.addWidget(h)

    entry = QLineEdit(current or "")
    entry.setMinimumHeight(34)
    root.addWidget(entry)

    hint = QLabel(t("rename_hint"))
    hint.setObjectName("Hint")
    root.addWidget(hint)
    root.addStretch(1)

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = QPushButton(t("cancel"))
    save_btn = QPushButton(t("save"))
    save_btn.setProperty("role", "primary")
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(save_btn)
    root.addLayout(btn_row)

    cancel_btn.clicked.connect(dlg.reject)
    save_btn.clicked.connect(dlg.accept)
    entry.returnPressed.connect(dlg.accept)
    entry.selectAll()
    entry.setFocus()

    if dlg.exec() == QDialog.Accepted:
        return entry.text()
    return None


# ---------------------------------------------------------------------------
# Conflict — Replace / Rename / Cancel
# returns ("replace", None) | ("rename", new_name) | ("cancel", None)
# ---------------------------------------------------------------------------
def conflict_dialog(parent, filename):
    dlg = QDialog(parent)
    dlg.setWindowTitle(t("conflict_title"))
    dlg.setMinimumSize(520, 240)

    root = QVBoxLayout(dlg)
    root.setContentsMargins(18, 18, 18, 18)
    root.setSpacing(8)

    h = QLabel(t("conflict_body"))
    h.setObjectName("SectionHeader")
    root.addWidget(h)

    name_lbl = QLabel(filename)
    name_lbl.setStyleSheet("color: #D0D6E0;")
    name_lbl.setWordWrap(True)
    root.addWidget(name_lbl)

    prompt = QLabel(t("conflict_rename_prompt"))
    prompt.setObjectName("Hint")
    root.addWidget(prompt)

    entry = QLineEdit("")
    entry.setMinimumHeight(34)
    root.addWidget(entry)

    root.addStretch(1)

    result = {"value": ("cancel", None)}

    btn_row = QHBoxLayout()
    btn_row.addStretch(1)
    cancel_btn = QPushButton(t("cancel"))
    rename_btn = QPushButton(t("rename"))
    replace_btn = QPushButton(t("replace"))
    replace_btn.setProperty("role", "primary")
    btn_row.addWidget(cancel_btn)
    btn_row.addWidget(rename_btn)
    btn_row.addWidget(replace_btn)
    root.addLayout(btn_row)

    def do_cancel():
        result["value"] = ("cancel", None)
        dlg.accept()

    def do_rename():
        val = entry.text().strip()
        if not val:
            return  # require a name
        result["value"] = ("rename", val)
        dlg.accept()

    def do_replace():
        result["value"] = ("replace", None)
        dlg.accept()

    cancel_btn.clicked.connect(do_cancel)
    rename_btn.clicked.connect(do_rename)
    replace_btn.clicked.connect(do_replace)

    dlg.exec()
    return result["value"]


# ---------------------------------------------------------------------------
# Duplicate-video confirm — returns bool
# ---------------------------------------------------------------------------
def duplicate_dialog(parent, video_title):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(t("duplicate_title"))
    box.setText(t("duplicate_body"))
    box.setInformativeText(f"{video_title}\n\n{t('duplicate_ask')}")
    yes_btn = box.addButton(t("yes"), QMessageBox.YesRole)
    no_btn = box.addButton(t("no"), QMessageBox.NoRole)
    box.setDefaultButton(no_btn)
    box.exec()
    return box.clickedButton() is yes_btn


# ---------------------------------------------------------------------------
# About — app name, credits, links, donation button
# ---------------------------------------------------------------------------
WEBSITE_URL  = "https://creators.sa/hibiki"
DONATION_URL = "https://tip.dokan.sa/hibiki"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about_title"))
        self.setMinimumSize(460, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 18)
        root.setSpacing(10)

        # App name (bilingual line) — large
        self.name_label = QLabel("Nazzil — نزّل")
        self.name_label.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #F7F8F8;")
        self.name_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.name_label)

        self.version_label = QLabel(t("about_version_label", version=APP_VERSION))
        self.version_label.setObjectName("Hint")
        self.version_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.version_label)

        # divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #23252A; background: #23252A;")
        line.setFixedHeight(1)
        root.addSpacing(4)
        root.addWidget(line)
        root.addSpacing(4)

        # developer
        self.dev_label = QLabel(t("about_developed_by"))
        self.dev_label.setStyleSheet("color: #D0D6E0; font-size: 13px;")
        self.dev_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.dev_label)

        # website link
        self.site_btn = QPushButton(t("about_visit_site"))
        self.site_btn.setCursor(Qt.PointingHandCursor)
        self.site_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(WEBSITE_URL)))
        root.addWidget(self.site_btn, alignment=Qt.AlignCenter)

        # donation button (primary, accent)
        self.donate_btn = QPushButton(t("about_donate"))
        self.donate_btn.setProperty("role", "primary")
        self.donate_btn.setCursor(Qt.PointingHandCursor)
        self.donate_btn.setMinimumHeight(40)
        self.donate_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DONATION_URL)))
        root.addSpacing(6)
        root.addWidget(self.donate_btn, alignment=Qt.AlignCenter)

        root.addStretch(1)

        self.powered_label = QLabel(t("about_powered_by"))
        self.powered_label.setObjectName("Hint")
        self.powered_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.powered_label)

        # close
        self.close_btn = QPushButton(t("close"))
        self.close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

    def retranslate(self):
        try:
            self.setWindowTitle(t("about_title"))
            self.version_label.setText(
                t("about_version_label", version=APP_VERSION))
            self.dev_label.setText(t("about_developed_by"))
            self.site_btn.setText(t("about_visit_site"))
            self.donate_btn.setText(t("about_donate"))
            self.powered_label.setText(t("about_powered_by"))
            self.close_btn.setText(t("close"))
        except Exception:
            pass
