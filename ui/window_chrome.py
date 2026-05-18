# -*- coding: utf-8 -*-
"""Custom window chrome — frameless + macOS-style traffic-lights + drag /
resize / Aero-snap on Windows.

Pieces in this file:

    FramelessMainWindow  — QMainWindow subclass that strips the native
                           title bar and handles WM_NCHITTEST so Windows
                           snap-to-edge + edge-resize still work natively.
    WindowControls       — three round buttons (close / minimize / max).
    TitleBar             — 40 px high; controls + brand + status dot +
                           optional "Update" pill + drag area + right-side
                           icon buttons (compact-mode / cookies / settings).
    DragArea             — fallback mouse-drag handler for non-Windows
                           platforms (Windows gets it via HTCAPTION).
"""

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import (QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QCursor, QGuiApplication, QMouseEvent,
                           QPainterPath, QRegion)
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ui.icons import icon as _icon, isize as _isize


# Shared corner radius for the rounded-mask
WINDOW_RADIUS_PX = 12


def _apply_round_mask(widget):
    """Clip `widget` to a 12 px rounded rectangle. Call from resizeEvent.
    No compositor-side translucency needed — the mask alone is enough."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()),
                        WINDOW_RADIUS_PX, WINDOW_RADIUS_PX)
    region = QRegion(path.toFillPolygon().toPolygon())
    widget.setMask(region)


_IS_WIN = sys.platform.startswith("win")


# ===========================================================================
# Three round window controls (mac-style)
# ===========================================================================
class _ControlButton(QPushButton):
    """Rectangular 32×24 window-control button with a coloured background
    and a centred qta icon. Replaces the old 12 px round bullets which
    were too small to click reliably. All four size dimensions are
    locked (setFixedSize + QSizePolicy.Fixed + QSS min/max) so layouts
    can't stretch them."""

    SIZE = (32, 24)

    def __init__(self, color, hover_color, icon_name, parent=None):
        super().__init__("", parent)
        self._color = color
        self._hover = hover_color
        self._icon_name = icon_name
        self.setFixedSize(*self.SIZE)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        # Solid black-on-coloured icon, never recoloured on hover —
        # only the bg changes.
        ic = _icon(icon_name, color="rgba(0,0,0,0.6)")
        if not ic.isNull():
            self.setIcon(ic)
            self.setIconSize(_isize(14))
        self.setStyleSheet(self._qss(color))

    def _qss(self, fill):
        return (
            "QPushButton {"
            f"  background: {fill};"
            "  min-width: 32px; max-width: 32px;"
            "  min-height: 24px; max-height: 24px;"
            "  border: 0;"
            "  border-radius: 6px;"
            "  padding: 0;"
            "}"
            "QPushButton:hover {"
            f"  background: {self._hover};"
            "}"
        )

    def set_icon(self, icon_name):
        """Swap the icon (used by the max button to toggle restore icon)."""
        self._icon_name = icon_name
        ic = _icon(icon_name, color="rgba(0,0,0,0.6)")
        if not ic.isNull():
            self.setIcon(ic)


# Back-compat alias — older code paths (Settings/Account close button)
# import _Bullet by name.
_Bullet = _ControlButton


class WindowControls(QWidget):
    """Window controls: Close → Maximize → Minimize, all on the LEFT.

    The container's layout direction is locked to LTR so the trio
    stays on the visual left even when the app runs in RTL — they're
    system-style controls, not content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setLayoutDirection(Qt.LeftToRight)  # never mirror
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self.close_btn = _ControlButton(
            "#EB5757", "#FF6B6B", "close", self)
        self.max_btn   = _ControlButton(
            "#27A644", "#34C759", "mdi6.fullscreen", self)
        self.min_btn   = _ControlButton(
            "#F0BF00", "#FFD028", "mdi6.window-minimize", self)

        self.close_btn.clicked.connect(self._on_close)
        self.max_btn.clicked.connect(self._on_toggle_max)
        self.min_btn.clicked.connect(self._on_minimize)

        for b in (self.close_btn, self.max_btn, self.min_btn):
            lay.addWidget(b, 0, Qt.AlignVCenter)

    def _win(self):
        return self.window()

    def _on_close(self):
        self._win().close()

    def _on_minimize(self):
        self._win().showMinimized()

    def _on_toggle_max(self):
        w = self._win()
        if w.isMaximized():
            w.showNormal()
            self.max_btn.set_icon("mdi6.fullscreen")
        else:
            w.showMaximized()
            self.max_btn.set_icon("mdi6.window-restore")


# ===========================================================================
# Drag area (cross-platform fallback; on Windows HTCAPTION does the work)
# ===========================================================================
class DragArea(QWidget):
    """Empty middle strip that drags the window. Double-click toggles
    maximize/restore. On Windows the parent's WM_NCHITTEST returns
    HTCAPTION over this region so native Aero-snap kicks in for free.

    Sized as Expanding/Preferred with stretch=1 in the parent layout so
    the strip always fills the gap between the brand cluster and the
    right-side icon buttons — earlier versions could shrink to 0 if the
    title bar got tight, making the drag region effectively dead."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.ArrowCursor)
        # Expanding so the parent layout always gives us all the leftover
        # horizontal space, even when the window is small.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumWidth(40)
        self._drag_pos = None

        # Subtle drag hint in the centre — three dots, low opacity.
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("⋯⋯⋯", self)
        hint.setStyleSheet("color: rgba(98,102,109,0.4); font-size: 13px;"
                           " letter-spacing: -0.5px;")
        hint.setAlignment(Qt.AlignCenter)
        # Critical: stop the QLabel from consuming the mouse events meant
        # for the drag region underneath it.
        hint.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lay.addStretch(1)
        lay.addWidget(hint, 0, Qt.AlignCenter)
        lay.addStretch(1)

    # Non-Windows fallback path. On Windows the OS handles the drag
    # natively because WM_NCHITTEST returns HTCAPTION over this widget.
    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            self._drag_pos = (e.globalPosition().toPoint()
                              - self.window().frameGeometry().topLeft())
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() & Qt.LeftButton and self._drag_pos is not None:
            self.window().move(
                e.globalPosition().toPoint() - self._drag_pos)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            w = self.window()
            if w.isMaximized():
                w.showNormal()
            else:
                w.showMaximized()
            e.accept()
        else:
            super().mouseDoubleClickEvent(e)


# ===========================================================================
# Title bar widget — assembled inside the window's central layout
# ===========================================================================
class TitleBar(QWidget):
    """44 px tall row.

    Layout is IDENTICAL in every language:
        [controls] [brand] [drag] [compact/cookies/settings]

    The title bar is system-level chrome, not content — it never flips.
    Only the content area below the title bar (URL row, filter row,
    download rows, pagination, footer) mirrors for RTL.

    The status dot used to live next to the brand; in v1.4 it moved to
    the footer (App._build_footer / set_status), so the brand cluster
    here is just the "Nazzil" wordmark."""

    compact_toggled = Signal()
    cookies_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(44)
        # Lock the entire title bar (and every child it owns) to LTR so
        # the traffic lights stay on the left and the chrome buttons stay
        # on the right regardless of the app's language direction. Each
        # child widget inherits this until it explicitly overrides.
        self.setLayoutDirection(Qt.LeftToRight)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- traffic lights (always far-left) ----
        self.controls = WindowControls(self)
        outer.addWidget(self.controls, 0, Qt.AlignVCenter)

        # ---- brand cluster: just "Nazzil" wordmark ----
        self.brand_wrap = QWidget(self)
        brand_lay = QHBoxLayout(self.brand_wrap)
        brand_lay.setContentsMargins(12, 0, 0, 0)
        brand_lay.setSpacing(6)
        self.brand_label = QLabel("Nazzil", self.brand_wrap)
        self.brand_label.setObjectName("BrandLabel")
        self.brand_label.setStyleSheet(
            "color: #828FFF; font-size: 14px; font-weight: 500;"
            " letter-spacing: -0.15px;")
        brand_lay.addWidget(self.brand_label, 0, Qt.AlignVCenter)

        # ---- drag area ----
        self.drag_area = DragArea(self)

        # ---- right-side icon cluster ----
        self.right_wrap = QWidget(self)
        self.right_wrap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        right_lay = QHBoxLayout(self.right_wrap)
        right_lay.setContentsMargins(0, 0, 12, 0)
        right_lay.setSpacing(4)
        self.compact_btn  = self._chrome_button("compact",  "Compact mode")
        self.cookies_btn  = self._chrome_button("cookies",  "Account / cookies")
        self.settings_btn = self._chrome_button("settings", "Settings")
        self.compact_btn.clicked.connect(self.compact_toggled.emit)
        self.cookies_btn.clicked.connect(self.cookies_clicked.emit)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        for b in (self.compact_btn, self.cookies_btn, self.settings_btn):
            right_lay.addWidget(b, 0, Qt.AlignVCenter)

        # Final assembly — fixed order, no reordering on language switch.
        outer.addWidget(self.brand_wrap, 0, Qt.AlignVCenter)
        outer.addWidget(self.drag_area, 1)
        outer.addWidget(self.right_wrap, 0, Qt.AlignVCenter)
        self._outer_layout = outer

    def apply_layout_direction(self, direction):
        """No-op — the title bar is permanently LTR. Kept as a signature
        for backward compat with `App._apply_window_direction` which still
        calls it (and used to swap brand/right-icons in RTL)."""
        # Re-assert LTR in case some external code mutated it.
        self.setLayoutDirection(Qt.LeftToRight)

    def _chrome_button(self, icon_name, tooltip):
        b = QPushButton("", self)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tooltip)
        b.setFixedSize(32, 32)
        b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        ic = _icon(icon_name, color="#8A8F98")
        if not ic.isNull():
            b.setIcon(ic)
            b.setIconSize(_isize(17))
        b.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  border: 0.5px solid rgba(255,255,255,0.08);"
            "  border-radius: 6px;"
            "  min-width: 32px; max-width: 32px;"
            "  min-height: 32px; max-height: 32px;"
            "  color: #8A8F98;"
            "  font-size: 14px;"
            "  padding: 0;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255,255,255,0.05);"
            "  border-color: #34343A;"
            "  color: #F7F8F8;"
            "}"
        )
        return b

    # Status dot + update pill moved to the footer in v1.4 — see
    # App._build_footer and App._set_update_status.


# ===========================================================================
# Frameless QMainWindow base — handles WM_NCHITTEST so the OS keeps
# resize + snap-to-edge behaviour even with the native chrome stripped.
# ===========================================================================

_HTCLIENT       = 1
_HTCAPTION      = 2
_HTLEFT         = 10
_HTRIGHT        = 11
_HTTOP          = 12
_HTTOPLEFT      = 13
_HTTOPRIGHT     = 14
_HTBOTTOM       = 15
_HTBOTTOMLEFT   = 16
_HTBOTTOMRIGHT  = 17

_WM_NCHITTEST   = 0x0084
_WM_NCCALCSIZE  = 0x0083


class FramelessMainWindow(QMainWindow):
    """QMainWindow with no native frame. On Windows, WM_NCHITTEST is
    handled manually so the user still gets edge-resize, double-click-to-
    maximize, and Aero-snap. On non-Windows we fall back to size grips
    plus DragArea-based dragging.

    Subclasses should expose `self.title_bar` (a TitleBar instance) so
    the hit-test can route those pixels to HTCAPTION."""

    RESIZE_BORDER = 6  # pixels of edge that count as a resize zone

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # Solid shell; the rectangular window is clipped to a rounded
        # mask on every resize. No compositor translucency required.
        self.setMouseTracking(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_round_mask(self)

    # ------------------------------------------------------------------
    # Windows: native hit-test
    # ------------------------------------------------------------------
    def nativeEvent(self, event_type, message):
        if not _IS_WIN:
            return super().nativeEvent(event_type, message)
        try:
            msg = wintypes.MSG.from_address(int(message))
        except Exception:
            return super().nativeEvent(event_type, message)

        if msg.message == _WM_NCHITTEST:
            # lParam packs the cursor's screen-space (x, y) into a DWORD
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            # Account for HiDPI: msg.lParam is in physical pixels but
            # Qt usually maps consistently for top-level widgets.
            pos_global = QPoint(x, y)
            try:
                pos = self.mapFromGlobal(pos_global)
            except Exception:
                pos = pos_global

            w, h = self.width(), self.height()
            b = self.RESIZE_BORDER
            on_left   = pos.x() < b
            on_right  = pos.x() > w - b
            on_top    = pos.y() < b
            on_bot    = pos.y() > h - b

            if on_top and on_left:    return True, _HTTOPLEFT
            if on_top and on_right:   return True, _HTTOPRIGHT
            if on_bot and on_left:    return True, _HTBOTTOMLEFT
            if on_bot and on_right:   return True, _HTBOTTOMRIGHT
            if on_left:               return True, _HTLEFT
            if on_right:              return True, _HTRIGHT
            if on_top:                return True, _HTTOP
            if on_bot:                return True, _HTBOTTOM

            # Inside the title bar (excluding interactive buttons)
            # → tell Windows to treat as caption (drag + snap).
            tb = getattr(self, "title_bar", None)
            if tb is not None:
                try:
                    tb_geo = QRect(tb.mapTo(self, QPoint(0, 0)), tb.size())
                except Exception:
                    tb_geo = QRect()
                if tb_geo.contains(pos):
                    # If the actual widget under the cursor is interactive
                    # (a button or its parent button), let Qt handle it.
                    child = self.childAt(pos)
                    interactive = False
                    cur = child
                    while cur is not None and cur is not tb:
                        if isinstance(cur, QPushButton):
                            interactive = True
                            break
                        cur = cur.parentWidget()
                    if not interactive:
                        return True, _HTCAPTION

            return True, _HTCLIENT

        return super().nativeEvent(event_type, message)


# ===========================================================================
# Dialog chrome — same rounded shell + minimal title bar (close button only)
# ===========================================================================
class DialogTitleBar(QWidget):
    """36 px title bar for dialogs. Layout: [title text] [drag area] [×]."""

    close_clicked = Signal()

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 12, 0)
        lay.setSpacing(8)

        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(
            "color: #D0D6E0; font-size: 13px; font-weight: 500;"
            " letter-spacing: -0.15px;")
        lay.addWidget(self.title_label, 0, Qt.AlignVCenter | Qt.AlignLeft)

        self.drag_area = DragArea(self)
        lay.addWidget(self.drag_area, 1)

        self.close_btn = _Bullet("#EB5757", "#FF6B6B", "×", self)
        self.close_btn.clicked.connect(self.close_clicked.emit)
        lay.addWidget(self.close_btn, 0, Qt.AlignVCenter)

    def set_title(self, text):
        self.title_label.setText(text)


class FramelessDialog(QDialog):
    """QDialog with the same rounded solid shell as the main window.

    Subclasses build their UI into `self.body` (a plain QWidget) — the
    title bar is provided for you. Call `set_title(text)` to update the
    title later (e.g. on a language switch)."""

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        # Inherit the app's text direction so Arabic users see a mirrored
        # dialog (close button moves to the leading edge etc.).
        try:
            from PySide6.QtWidgets import QApplication as _QApp
            inst = _QApp.instance()
            if inst is not None:
                self.setLayoutDirection(inst.layoutDirection())
        except Exception:
            pass
        # Outer layout holds the rounded shell so the QDialog's own
        # background (which we don't see) never paints over our chrome.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.dialog_shell = QFrame(self)
        self.dialog_shell.setObjectName("WindowShell")
        outer.addWidget(self.dialog_shell)

        shell_lay = QVBoxLayout(self.dialog_shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)

        self.dialog_title_bar = DialogTitleBar(title, self.dialog_shell)
        self.dialog_title_bar.close_clicked.connect(self.reject)
        shell_lay.addWidget(self.dialog_title_bar)

        # Subclasses install their layout on self.body.
        self.body = QWidget(self.dialog_shell)
        shell_lay.addWidget(self.body, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _apply_round_mask(self)

    def set_title(self, text):
        self.dialog_title_bar.set_title(text)
