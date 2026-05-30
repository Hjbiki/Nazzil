# -*- coding: utf-8 -*-
"""Qt dialogs: Settings, Account/cookies, Rename, File-conflict,
Duplicate-video confirm, Shortcuts, About."""

import os
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                               QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)

from config import APP_VERSION, COOKIE_MODES, save_config
from i18n import Translator, t
from ui.icons import icon as _icon
from ui.window_chrome import FramelessDialog
from utils import classify_error, clean_error


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingsDialog(FramelessDialog):
    def __init__(self, app, parent=None):
        super().__init__(title=t("settings_title"), parent=parent)
        self.app = app
        self.setMinimumSize(620, 640)

        root = QVBoxLayout(self.body)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(12)

        # --- folder ---
        self.folder_header = self._header(t("download_folder"))
        root.addWidget(self.folder_header)
        folder_row = QHBoxLayout()
        self.folder_lbl = QLabel(app.folder or t("not_set"))
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
        # No restart hint — language switches live (no app restart needed).

        # --- theme (dark / light) ---
        root.addSpacing(8)
        self.theme_header = self._header(t("theme"))
        root.addWidget(self.theme_header)
        theme_row = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(t("theme_dark"), "dark")
        self.theme_combo.addItem(t("theme_light"), "light")
        cur_theme = app.cfg.get("theme", "dark")
        tidx = self.theme_combo.findData(cur_theme)
        self.theme_combo.setCurrentIndex(tidx if tidx >= 0 else 0)
        self.theme_combo.currentIndexChanged.connect(self._on_theme_change)
        theme_row.addWidget(self.theme_combo, 0)
        theme_row.addStretch(1)
        root.addLayout(theme_row)

        # --- aria2c ---
        root.addSpacing(8)
        self.aria_chk = QCheckBox(t("use_aria2c"))
        self.aria_chk.setProperty("role", "switch")
        self.aria_chk.setChecked(bool(app.cfg.get("use_aria2c", False)))
        self.aria_chk.setStyleSheet("QCheckBox { spacing: 12px; }")
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
        self.clip_chk.setStyleSheet("QCheckBox { spacing: 12px; }")
        self.clip_chk.toggled.connect(self._on_clip_toggle)
        root.addWidget(self.clip_chk)

        # --- minimize to tray ---
        self.tray_chk = QCheckBox(t("minimize_to_tray"))
        self.tray_chk.setProperty("role", "switch")
        self.tray_chk.setChecked(bool(app.cfg.get("minimize_to_tray", True)))
        self.tray_chk.setStyleSheet("QCheckBox { spacing: 12px; }")
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

        # NOTE: the old "Update yt-dlp" button was removed in v1.5.x. yt-dlp
        # is bundled with the app and updates itself silently in the
        # background (see ytdlp_updater.py) — the user never has to think
        # about it, so there's no UI for it anymore.

        root.addStretch(1)

        # --- footer: About + config-saved hint ---
        footer = QHBoxLayout()
        self.about_btn = QPushButton(t("about"))
        self.about_btn.clicked.connect(self._open_about)
        footer.addWidget(self.about_btn)
        self.shortcuts_btn = QPushButton(t("shortcuts_title"))
        self.shortcuts_btn.clicked.connect(self._open_shortcuts)
        footer.addWidget(self.shortcuts_btn)
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

    def _on_theme_change(self, _idx):
        mode = self.theme_combo.currentData()
        if hasattr(self.app, "set_theme"):
            self.app.set_theme(mode)

    def _on_aria_toggle(self, val):
        self.app.cfg["use_aria2c"] = bool(val)
        save_config(self.app.cfg)
        self._refresh_aria_hint()

    def _refresh_aria_hint(self):
        # aria2c is bundled with the app, so detect it via binaries.aria2c_path
        # (NOT shutil.which, which only sees PATH). aria2c is purely optional —
        # we never tell the user to install anything.
        import binaries
        present = bool(binaries.aria2c_path())
        if not self.aria_chk.isChecked():
            self.aria_hint.setText(t("aria2c_hint_off"))
        elif present:
            self.aria_hint.setText(t("aria2c_hint_on"))
        else:
            # Toggle on but aria2c unavailable (rare — it ships bundled).
            # Silent functional fallback to the default downloader; the hint
            # is just an indicator, never an install instruction.
            self.aria_hint.setText(t("aria2c_hint_missing"))

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

    def _open_shortcuts(self):
        ShortcutsDialog(self).exec()

    # ------------------------------------------------------------------
    # Live language switch
    # ------------------------------------------------------------------
    def retranslate(self):
        try:
            self.setWindowTitle(t("settings_title"))
            self.set_title(t("settings_title"))
            self.folder_header.setText(t("download_folder"))
            self.change_btn.setText(t("change"))
            if not self.app.folder:
                self.folder_lbl.setText(t("not_set"))
            self.lang_header.setText(t("language"))
            self.theme_header.setText(t("theme"))
            self.theme_combo.setItemText(0, t("theme_dark"))
            self.theme_combo.setItemText(1, t("theme_light"))
            self.aria_chk.setText(t("use_aria2c"))
            self._refresh_aria_hint()
            self.clip_chk.setText(t("clipboard_watch"))
            self.tray_chk.setText(t("minimize_to_tray"))
            self.app_update_header.setText(t("app_short"))
            self.check_updates_btn.setText(t("check_for_updates"))
            self.about_btn.setText(t("about"))
            self.shortcuts_btn.setText(t("shortcuts_title"))
            self.cfg_hint.setText(t("config_saved_at"))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Account / cookies
# ---------------------------------------------------------------------------
class AccountDialog(FramelessDialog):
    def __init__(self, app, parent=None):
        super().__init__(title=t("account_title"), parent=parent)
        self.app = app
        self.setMinimumSize(560, 440)

        root = QVBoxLayout(self.body)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(10)

        self.header = QLabel(t("account_source"))
        self.header.setObjectName("SectionHeader")
        self.header.setWordWrap(True)
        root.addWidget(self.header)

        # ---- Vertical radio list with optional pill + help on Firefox row.
        # Converted from QComboBox so we can inline a "Recommended" tag
        # next to the Firefox option without a custom item delegate. ----
        self.source_group = QButtonGroup(self)
        self.source_group.setExclusive(True)
        self.source_radios = {}
        self._firefox_pill = None
        self._firefox_help = None

        sources_container = QWidget(self.body)
        sources_lay = QVBoxLayout(sources_container)
        sources_lay.setContentsMargins(0, 0, 0, 0)
        sources_lay.setSpacing(4)

        for key, label_key in COOKIE_MODES:
            row_wrap = QWidget(sources_container)
            row_lay = QHBoxLayout(row_wrap)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(8)

            radio = QRadioButton(t(label_key), row_wrap)
            radio.setProperty("key", key)
            radio.toggled.connect(
                lambda checked, k=key: self._on_source_select(k, checked))
            self.source_group.addButton(radio)
            self.source_radios[key] = radio
            row_lay.addWidget(radio, 0, Qt.AlignVCenter)

            if key == "firefox":
                self._firefox_pill = QLabel(t("cookies_recommended"), row_wrap)
                self._firefox_pill.setStyleSheet(
                    "background: rgba(94,106,210,0.15);"
                    " color: #828FFF;"
                    " border: 1px solid rgba(130,143,255,0.25);"
                    " border-radius: 4px;"
                    " padding: 1px 6px;"
                    " font-size: 11px;"
                    " font-weight: 500;")
                row_lay.addWidget(self._firefox_pill, 0, Qt.AlignVCenter)

                self._firefox_help = QLabel(row_wrap)
                ic = _icon("mdi6.help-circle-outline", color="#62666D")
                if not ic.isNull():
                    self._firefox_help.setPixmap(ic.pixmap(12, 12))
                else:
                    self._firefox_help.setText("?")
                    self._firefox_help.setStyleSheet(
                        "color: #62666D; font-size: 11px;")
                self._firefox_help.setToolTip(t("cookies_recommended_tooltip"))
                self._firefox_help.setCursor(Qt.WhatsThisCursor)
                row_lay.addWidget(self._firefox_help, 0, Qt.AlignVCenter)

            row_lay.addStretch(1)
            sources_lay.addWidget(row_wrap)

        initial = self.source_radios.get(app.cookie_mode) \
            or self.source_radios.get("none")
        if initial is not None:
            initial.blockSignals(True)
            initial.setChecked(True)
            initial.blockSignals(False)

        root.addWidget(sources_container)

        # ---- Test login button row ----
        action_row = QHBoxLayout()
        self.test_btn = QPushButton(t("test_login"))
        self.test_btn.clicked.connect(self._test)
        action_row.addWidget(self.test_btn, 0)
        action_row.addStretch(1)
        root.addLayout(action_row)

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
        self.pick_btn = QPushButton(t("pick_file"))
        self.pick_btn.clicked.connect(self._pick_file)
        self.file_row_widget.addWidget(self.file_lbl, 1)
        self.file_row_widget.addWidget(self.pick_btn, 0)
        self.file_row_container = QHBoxLayout()
        self.file_row_container.addLayout(self.file_row_widget)
        root.addLayout(self.file_row_container)

        root.addStretch(1)

        # Self-documenting hint at the bottom so the dialog doesn't feel empty.
        self.account_help = QLabel(t("account_help"))
        self.account_help.setWordWrap(True)
        self.account_help.setStyleSheet(
            "color: #62666D; font-size: 11px;"
            " letter-spacing: -0.15px;")
        root.addWidget(self.account_help)

        self._refresh()

    def _on_source_select(self, key, checked):
        if not checked:
            return
        self._refresh(key)

    def _selected_source(self):
        for key, radio in self.source_radios.items():
            if radio.isChecked():
                return key
        return "none"

    def _refresh(self, code=None):
        if code is None:
            code = self._selected_source()
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
            self.set_title(t("account_title"))
            self.header.setText(t("account_source"))
            self.test_btn.setText(t("test_login"))
            self.pick_btn.setText(t("pick_file"))
            self.account_help.setText(t("account_help"))
            if not self.app.cookie_file:
                self.file_lbl.setText(t("no_file_selected"))
            # Refresh source labels — the radio set itself stays put.
            for key, label_key in COOKIE_MODES:
                radio = self.source_radios.get(key)
                if radio is not None:
                    radio.setText(t(label_key))
            if self._firefox_pill is not None:
                self._firefox_pill.setText(t("cookies_recommended"))
            if self._firefox_help is not None:
                self._firefox_help.setToolTip(
                    t("cookies_recommended_tooltip"))
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
    root.setContentsMargins(20, 20, 20, 20)
    root.setSpacing(8)

    h = QLabel(t("rename_prompt"))
    h.setObjectName("SectionHeader")
    root.addWidget(h)

    entry = QLineEdit(current or "")
    entry.setMinimumHeight(40)
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
    root.setContentsMargins(20, 20, 20, 20)
    root.setSpacing(8)

    h = QLabel(t("conflict_body"))
    h.setObjectName("SectionHeader")
    root.addWidget(h)

    name_lbl = QLabel(filename)
    name_lbl.setWordWrap(True)
    root.addWidget(name_lbl)

    prompt = QLabel(t("conflict_rename_prompt"))
    prompt.setObjectName("Hint")
    root.addWidget(prompt)

    entry = QLineEdit("")
    entry.setMinimumHeight(40)
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
# Delete-file confirm — returns bool. Used by DownloadRow.delete_with_file
# to warn before permanently nuking a file from disk.
# ---------------------------------------------------------------------------
def delete_file_confirm_dialog(parent, filename):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(t("delete_file_confirm_title"))
    box.setText(t("delete_file_confirm_message", filename=filename))
    del_btn = box.addButton(t("delete"), QMessageBox.DestructiveRole)
    cancel_btn = box.addButton(t("cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(cancel_btn)
    box.exec()
    return box.clickedButton() is del_btn


# ---------------------------------------------------------------------------
# Themed message dialog — same rounded shell as the rest of the app.
# Returns True if the primary button was clicked, else False.
# ---------------------------------------------------------------------------
class _MessageDialog(FramelessDialog):
    def __init__(self, parent, title, message, *,
                 primary=None, secondary=None, accent="brand"):
        super().__init__(title=title, parent=parent)
        self.setMinimumWidth(420)
        self._primary_clicked = False

        root = QVBoxLayout(self.body)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        from ui.theme import current as _theme
        msg = QLabel(message)
        msg.setWordWrap(True)
        msg.setStyleSheet(
            f"color: {_theme()['TEXT_DIM']}; font-size: 14px;"
            " background: transparent;")
        root.addWidget(msg)
        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        if secondary:
            sec = QPushButton(secondary)
            sec.setProperty("role", "secondary")
            sec.setCursor(Qt.PointingHandCursor)
            sec.clicked.connect(self.reject)
            btn_row.addWidget(sec)
        if primary:
            pri = QPushButton(primary)
            pri.setProperty("role", "primary")
            pri.setCursor(Qt.PointingHandCursor)
            pri.clicked.connect(self._on_primary)
            btn_row.addWidget(pri)
        root.addLayout(btn_row)

    def _on_primary(self):
        self._primary_clicked = True
        self.accept()


def themed_message(parent, title, message, *, primary=None, secondary=None):
    """Show a themed modal message. Returns True if `primary` was clicked."""
    dlg = _MessageDialog(parent, title, message,
                         primary=primary, secondary=secondary)
    dlg.exec()
    return dlg._primary_clicked


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
# Keyboard shortcuts — reference card matching the app shell.
# ---------------------------------------------------------------------------
# (keys, i18n description key). Keys are shown in a monospace-ish chip.
_SHORTCUTS = [
    ("Ctrl + V",  "sc_paste"),
    ("Ctrl + L",  "sc_focus_url"),
    ("Ctrl + F",  "sc_focus_search"),
    ("Ctrl + ,",  "sc_settings"),
    ("Ctrl + M",  "sc_minimize"),
    ("F11",       "sc_maximize"),
    ("Ctrl + W",  "sc_close"),
    ("F1",        "sc_help"),
]


class ShortcutsDialog(FramelessDialog):
    """Read-only list of every keyboard shortcut, styled like the app."""

    def __init__(self, parent=None):
        super().__init__(title=t("shortcuts_title"), parent=parent)
        self.setMinimumSize(440, 420)

        root = QVBoxLayout(self.body)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(6)

        self._rows = []   # (keys_label, desc_label, desc_key)
        for keys, desc_key in _SHORTCUTS:
            row = QFrame(self.body)
            row.setObjectName("ShortcutRow")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(12)

            desc = QLabel(t(desc_key), row)
            desc.setStyleSheet("background: transparent; font-size: 13px;")
            rl.addWidget(desc, 1, Qt.AlignVCenter)

            keycap = QLabel(keys, row)
            keycap.setObjectName("Keycap")
            keycap.setAlignment(Qt.AlignCenter)
            rl.addWidget(keycap, 0, Qt.AlignVCenter)

            row.setStyleSheet(
                "QFrame#ShortcutRow { background: transparent;"
                " border: 0; border-bottom: 1px solid rgba(128,128,128,0.15); }"
                "QLabel#Keycap { background: rgba(128,128,128,0.12);"
                " border: 1px solid rgba(128,128,128,0.25); border-radius: 5px;"
                " padding: 2px 8px; font-size: 12px; font-weight: 600; }")
            root.addWidget(row)
            self._rows.append((keycap, desc, desc_key))

        root.addStretch(1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.close_btn = QPushButton(t("close"))
        self.close_btn.setProperty("role", "primary")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.close_btn)
        root.addLayout(btn_row)

    def retranslate(self):
        try:
            self.setWindowTitle(t("shortcuts_title"))
            self.set_title(t("shortcuts_title"))
            for _keycap, desc, desc_key in self._rows:
                desc.setText(t(desc_key))
            self.close_btn.setText(t("close"))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# About — app name, credits, links, donation button
# ---------------------------------------------------------------------------
WEBSITE_URL  = "https://creators.sa/hibiki"
DONATION_URL = "https://tip.dokan.sa/hibiki"


class AboutDialog(FramelessDialog):
    """About card — same rounded gradient shell, fonts, and button styles
    as the rest of Nazzil (it used to be a plain QDialog that looked out of
    place)."""

    def __init__(self, parent=None):
        super().__init__(title=t("about_title"), parent=parent)
        self.setMinimumSize(440, 420)

        root = QVBoxLayout(self.body)
        root.setContentsMargins(28, 20, 28, 24)
        root.setSpacing(8)

        root.addStretch(1)

        # App icon (round-ish) above the wordmark for a polished header.
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        try:
            import os
            here = os.path.dirname(os.path.abspath(__file__))
            icon_png = os.path.normpath(
                os.path.join(here, "..", "assets", "icon.png"))
            if os.path.exists(icon_png):
                from PySide6.QtGui import QPixmap
                pix = QPixmap(icon_png).scaled(
                    64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.icon_label.setPixmap(pix)
                root.addWidget(self.icon_label)
                root.addSpacing(4)
        except Exception:
            pass

        # App name (bilingual line) — large, palette-aware text colour.
        from ui.theme import current as _theme
        self.name_label = QLabel("Nazzil — نزّل")
        self.name_label.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {_theme()['TEXT']};"
            " letter-spacing: -0.3px; background: transparent;")
        self.name_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.name_label)

        self.version_label = QLabel(
            t("about_version_label", version=APP_VERSION))
        self.version_label.setObjectName("Hint")
        self.version_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.version_label)

        # developer
        self.dev_label = QLabel(t("about_developed_by"))
        self.dev_label.setStyleSheet(
            f"color: {_theme()['TEXT_DIM']}; font-size: 13px;"
            " background: transparent;")
        self.dev_label.setAlignment(Qt.AlignCenter)
        root.addSpacing(6)
        root.addWidget(self.dev_label)

        # divider line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #23252A; background: #23252A;")
        line.setFixedHeight(1)
        root.addSpacing(10)
        root.addWidget(line)
        root.addSpacing(12)

        # ---- action buttons, all sharing the app button styles ----
        self.site_btn = QPushButton(t("about_visit_site"))
        self.site_btn.setProperty("role", "secondary")
        self.site_btn.setCursor(Qt.PointingHandCursor)
        self.site_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(WEBSITE_URL)))
        root.addWidget(self.site_btn)

        self.donate_btn = QPushButton(t("about_donate"))
        self.donate_btn.setProperty("role", "primary")
        self.donate_btn.setCursor(Qt.PointingHandCursor)
        self.donate_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(DONATION_URL)))
        root.addWidget(self.donate_btn)

        self.close_btn = QPushButton(t("close"))
        self.close_btn.setProperty("role", "secondary")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        root.addWidget(self.close_btn)

        root.addStretch(1)

    def retranslate(self):
        try:
            self.setWindowTitle(t("about_title"))
            self.set_title(t("about_title"))
            self.version_label.setText(
                t("about_version_label", version=APP_VERSION))
            self.dev_label.setText(t("about_developed_by"))
            self.site_btn.setText(t("about_visit_site"))
            self.donate_btn.setText(t("about_donate"))
            self.close_btn.setText(t("close"))
        except Exception:
            pass
