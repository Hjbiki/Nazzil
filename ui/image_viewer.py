# -*- coding: utf-8 -*-
"""Frameless image viewer for download thumbnails.

Built because Windows Photos can't open the webp thumbnails YouTube
serves by default, and the chrome should match the rest of the app.

    [title bar]
    [QGraphicsView with QGraphicsPixmapItem  — pan/zoom]
    [40 px toolbar: zoom out · % · zoom in | fit · 1:1 |
                    rot-L · rot-R | fullscreen | save-as]

Keyboard:  +/= zoom in · - zoom out · 0 fit · 1 actual ·
           R rotate right · Shift+R rotate left ·
           F / F11 fullscreen · Esc close (or exit fullscreen first) ·
           Ctrl+S save · wheel zoom centered on cursor · drag pan.
"""

import os
import threading
from io import BytesIO

from PIL import Image
from PySide6.QtCore import (QObject, QRectF, QTimer, Qt, Signal, Slot)
from PySide6.QtGui import (QImage, QKeySequence, QPainter, QPixmap, QShortcut,
                           QTransform)
from PySide6.QtWidgets import (QFileDialog, QFrame, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsView, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout)

from i18n import t
from ui.icons import icon as _icon, isize as _isize
from ui.window_chrome import FramelessDialog
from utils import fetch_image_bytes


# ---------------------------------------------------------------------------
# Background loader for the original (full-resolution) thumbnail URL.
# YouTube serves either jpg or webp — both are readable by QPixmap on the
# PySide6 wheels (which bundle the webp plugin). Pillow is used as a
# fallback for any image format Qt can't decode directly.
# ---------------------------------------------------------------------------
class _ImageLoader(QObject):
    loaded = Signal(bytes)
    failed = Signal()

    def fetch(self, url):
        def run():
            data = fetch_image_bytes(url)
            if data:
                self.loaded.emit(data)
            else:
                self.failed.emit()
        threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# QGraphicsView subclass that forwards wheel events to the parent viewer
# so we can implement cursor-centered zoom and skip the default scroll.
# ---------------------------------------------------------------------------
class _ZoomGraphicsView(QGraphicsView):
    wheel_zoom = Signal(int)  # +1 = zoom in, -1 = zoom out

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta != 0:
            self.wheel_zoom.emit(1 if delta > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


# ---------------------------------------------------------------------------
# The viewer dialog.
# ---------------------------------------------------------------------------
class FramelessImageViewer(FramelessDialog):
    MIN_ZOOM = 0.10
    MAX_ZOOM = 8.0
    ZOOM_STEP = 1.15

    def __init__(self, title="", thumb_url="", thumb_path="", parent=None):
        # Truncate the title so the title bar doesn't get clobbered.
        shown = (title or t("viewer_title"))
        if len(shown) > 80:
            shown = shown[:79] + "…"
        super().__init__(title=shown, parent=parent)
        self.resize(900, 600)
        self.setMinimumSize(600, 400)

        # ---- state ----
        self._zoom = 1.0
        self._rotation = 0
        self._fit_mode = True
        self._is_fullscreen = False
        self._image_bytes = None
        # Used as the default "Save as…" extension; webp is YouTube's
        # default now, but jpg shows up on older thumbs.
        self._image_ext = ".jpg"

        # ---- body layout ----
        body_lay = QVBoxLayout(self.body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # ---- graphics scene + view ----
        self._scene = QGraphicsScene(self)
        self._view = _ZoomGraphicsView(self._scene, self.body)
        self._view.setRenderHints(QPainter.SmoothPixmapTransform
                                  | QPainter.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setFrameShape(QFrame.NoFrame)
        self._view.setDragMode(QGraphicsView.NoDrag)
        self._view.setStyleSheet(
            "QGraphicsView { background: transparent; border: 0; }")
        self._view.wheel_zoom.connect(self._on_wheel_zoom)
        self._pix_item = QGraphicsPixmapItem()
        self._pix_item.setTransformationMode(Qt.SmoothTransformation)
        self._scene.addItem(self._pix_item)
        body_lay.addWidget(self._view, 1)

        # ---- toolbar ----
        body_lay.addWidget(self._build_toolbar())

        # ---- loader ----
        self._loader = _ImageLoader(self)
        self._loader.loaded.connect(self._on_loaded)

        if thumb_path and os.path.exists(thumb_path):
            try:
                with open(thumb_path, "rb") as f:
                    self._on_loaded(f.read())
            except Exception:
                pass
            ext = os.path.splitext(thumb_path)[1].lower()
            if ext in (".jpg", ".jpeg", ".webp", ".png"):
                self._image_ext = ext
        elif thumb_url:
            # Pull the extension from the URL (sans query string) so the
            # default save filename matches what's actually on the wire.
            url_path = thumb_url.split("?", 1)[0]
            ext = os.path.splitext(url_path)[1].lower()
            if ext in (".jpg", ".jpeg", ".webp", ".png"):
                self._image_ext = ext
            self._loader.fetch(thumb_url)

        self._setup_shortcuts()

    # ----------------------------------------------------------------------
    # Toolbar
    # ----------------------------------------------------------------------
    def _build_toolbar(self):
        tb = QFrame(self.body)
        tb.setObjectName("ViewerToolbar")
        tb.setFixedHeight(40)
        tb.setStyleSheet(
            "QFrame#ViewerToolbar {"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "    stop:0 rgba(20,21,22,0.85), stop:1 rgba(15,16,17,0.85));"
            "  border-top: 1px solid rgba(255,255,255,0.06);"
            "}"
        )
        lay = QHBoxLayout(tb)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(4)
        # Inner cluster locked LTR — viewer controls are visual, not
        # textual content, so they shouldn't mirror in RTL.
        tb.setLayoutDirection(Qt.LeftToRight)

        lay.addStretch(1)

        zo = self._mk_btn("mdi6.minus", t("viewer_zoom_out"))
        zo.clicked.connect(self._zoom_out)
        lay.addWidget(zo)

        self._zoom_label = QLabel("100%", tb)
        self._zoom_label.setFixedWidth(60)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_label.setStyleSheet(
            "color: #D0D6E0; font-size: 12px; background: transparent;")
        lay.addWidget(self._zoom_label)

        zi = self._mk_btn("mdi6.plus", t("viewer_zoom_in"))
        zi.clicked.connect(self._zoom_in)
        lay.addWidget(zi)

        lay.addWidget(self._sep())

        fit = self._mk_btn("mdi6.fit-to-page-outline", t("viewer_fit_window"))
        fit.clicked.connect(self._fit_to_window)
        lay.addWidget(fit)

        actual = self._mk_btn(
            "mdi6.numeric-1-box-outline", t("viewer_actual_size"))
        actual.clicked.connect(self._actual_size)
        lay.addWidget(actual)

        lay.addWidget(self._sep())

        rl = self._mk_btn("mdi6.rotate-left", t("viewer_rotate_left"))
        rl.clicked.connect(lambda: self._rotate(-90))
        lay.addWidget(rl)

        rr = self._mk_btn("mdi6.rotate-right", t("viewer_rotate_right"))
        rr.clicked.connect(lambda: self._rotate(90))
        lay.addWidget(rr)

        lay.addWidget(self._sep())

        self._fs_btn = self._mk_btn("mdi6.fullscreen", t("viewer_fullscreen"))
        self._fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(self._fs_btn)

        lay.addWidget(self._sep())

        save = self._mk_btn(
            "mdi6.content-save-outline", t("viewer_save_as"))
        save.clicked.connect(self._save_as)
        lay.addWidget(save)

        lay.addStretch(1)
        return tb

    def _mk_btn(self, icon_name, tooltip):
        b = QPushButton("", self.body)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tooltip)
        b.setFixedSize(32, 32)
        ic = _icon(icon_name, color="#D0D6E0")
        if not ic.isNull():
            b.setIcon(ic)
            b.setIconSize(_isize(16))
        b.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  border: 1px solid rgba(255,255,255,0.06);"
            "  border-radius: 6px;"
            "  min-width: 30px; max-width: 30px;"
            "  min-height: 30px; max-height: 30px;"
            "  padding: 0;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255,255,255,0.06);"
            "  border-color: rgba(255,255,255,0.18);"
            "}"
        )
        return b

    def _sep(self):
        sep = QFrame(self.body)
        sep.setFixedSize(1, 20)
        sep.setStyleSheet("background: rgba(255,255,255,0.08);")
        return sep

    # ----------------------------------------------------------------------
    # Shortcuts
    # ----------------------------------------------------------------------
    def _setup_shortcuts(self):
        def sc(seq, fn):
            s = QShortcut(QKeySequence(seq), self)
            s.activated.connect(fn)
            return s
        sc("+", self._zoom_in)
        sc("=", self._zoom_in)
        sc("-", self._zoom_out)
        sc("0", self._fit_to_window)
        sc("1", self._actual_size)
        sc("R", lambda: self._rotate(90))
        sc("Shift+R", lambda: self._rotate(-90))
        sc("F", self._toggle_fullscreen)
        sc("F11", self._toggle_fullscreen)
        sc("Ctrl+S", self._save_as)

    # ----------------------------------------------------------------------
    # Image loading
    # ----------------------------------------------------------------------
    @Slot(bytes)
    def _on_loaded(self, data):
        self._image_bytes = data
        pix = self._decode_pixmap(data)
        if pix is None or pix.isNull():
            return
        self._pix_item.setPixmap(pix)
        # Reset rotation around the new image's center.
        self._pix_item.setTransformOriginPoint(
            pix.rect().center())
        self._pix_item.setRotation(0)
        self._rotation = 0
        self._scene.setSceneRect(QRectF(pix.rect()))
        # Defer fit until after layout settles (the dialog may not yet
        # know its final size if this fires before the first paint).
        QTimer.singleShot(0, self._fit_to_window)

    def _decode_pixmap(self, data):
        """QPixmap.loadFromData → Pillow fallback. Returns None on failure."""
        pix = QPixmap()
        if pix.loadFromData(data):
            return pix
        # Pillow can usually rescue weird webp variants Qt struggles with.
        try:
            img = Image.open(BytesIO(data)).convert("RGB")
            buf = BytesIO()
            img.save(buf, format="PNG")
            pix2 = QPixmap()
            if pix2.loadFromData(buf.getvalue(), "PNG"):
                return pix2
        except Exception:
            pass
        return None

    # ----------------------------------------------------------------------
    # Zoom / rotate / fit / actual size
    # ----------------------------------------------------------------------
    def _apply_zoom_transform(self):
        # Rotation is applied on the pixmap item (so its bounding rect
        # rotates with it); the view only scales.
        tx = QTransform()
        tx.scale(self._zoom, self._zoom)
        self._view.setTransform(tx)

    def _update_zoom_label(self):
        self._zoom_label.setText(f"{int(round(self._zoom * 100))}%")

    def _zoom_in(self):
        self._set_zoom(min(self.MAX_ZOOM, self._zoom * self.ZOOM_STEP))

    def _zoom_out(self):
        self._set_zoom(max(self.MIN_ZOOM, self._zoom / self.ZOOM_STEP))

    def _set_zoom(self, z, anchor_under_mouse=False):
        z = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        if abs(z - self._zoom) < 1e-4:
            return
        self._view.setTransformationAnchor(
            QGraphicsView.AnchorUnderMouse if anchor_under_mouse
            else QGraphicsView.AnchorViewCenter)
        self._zoom = z
        self._fit_mode = False
        self._apply_zoom_transform()
        self._update_zoom_label()
        self._update_drag_mode()

    @Slot(int)
    def _on_wheel_zoom(self, direction):
        factor = self.ZOOM_STEP if direction > 0 else 1.0 / self.ZOOM_STEP
        self._set_zoom(self._zoom * factor, anchor_under_mouse=True)

    def _fit_to_window(self):
        if self._pix_item.pixmap().isNull():
            return
        self._fit_mode = True
        # Use the item's sceneBoundingRect so rotation is accounted for.
        rect = self._pix_item.sceneBoundingRect()
        view_size = self._view.viewport().size()
        # Honour 24 px padding on each side.
        pad = 24
        w_avail = max(1, view_size.width() - pad * 2)
        h_avail = max(1, view_size.height() - pad * 2)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        sx = w_avail / rect.width()
        sy = h_avail / rect.height()
        z = min(sx, sy)
        z = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        self._view.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self._zoom = z
        self._apply_zoom_transform()
        self._view.centerOn(self._pix_item)
        self._update_zoom_label()
        self._update_drag_mode()

    def _actual_size(self):
        self._set_zoom(1.0)
        # center on the image's middle
        self._view.centerOn(self._pix_item)

    def _rotate(self, delta_deg):
        self._rotation = (self._rotation + delta_deg) % 360
        center = self._pix_item.pixmap().rect().center()
        self._pix_item.setTransformOriginPoint(center)
        self._pix_item.setRotation(self._rotation)
        # Re-fit so the rotated image stays fully visible if we were
        # in fit mode; otherwise just re-anchor in the view center.
        if self._fit_mode:
            QTimer.singleShot(0, self._fit_to_window)
        else:
            self._view.centerOn(self._pix_item)

    # ----------------------------------------------------------------------
    # Fullscreen
    # ----------------------------------------------------------------------
    def _toggle_fullscreen(self):
        if self._is_fullscreen:
            self.showNormal()
            self._is_fullscreen = False
            new_icon = "mdi6.fullscreen"
        else:
            self.showFullScreen()
            self._is_fullscreen = True
            new_icon = "mdi6.fullscreen-exit"
        ic = _icon(new_icon, color="#D0D6E0")
        if not ic.isNull():
            self._fs_btn.setIcon(ic)
        if self._fit_mode:
            QTimer.singleShot(0, self._fit_to_window)

    # ----------------------------------------------------------------------
    # Save as
    # ----------------------------------------------------------------------
    def _save_as(self):
        if not self._image_bytes:
            return
        default_name = f"thumbnail{self._image_ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, t("viewer_save_dialog_title"), default_name,
            "Images (*.jpg *.jpeg *.png *.webp);;All files (*.*)")
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._image_bytes)
        except Exception:
            pass

    # ----------------------------------------------------------------------
    # Drag-to-pan only makes sense when the image overflows the viewport.
    # ----------------------------------------------------------------------
    def _update_drag_mode(self):
        rect = self._pix_item.sceneBoundingRect()
        scaled_w = rect.width() * self._zoom
        scaled_h = rect.height() * self._zoom
        view_size = self._view.viewport().size()
        overflowing = (scaled_w > view_size.width()
                       or scaled_h > view_size.height())
        self._view.setDragMode(
            QGraphicsView.ScrollHandDrag if overflowing
            else QGraphicsView.NoDrag)
        # Show scrollbars only when overflowing so the chrome isn't busy.
        policy = (Qt.ScrollBarAsNeeded if overflowing
                  else Qt.ScrollBarAlwaysOff)
        self._view.setHorizontalScrollBarPolicy(policy)
        self._view.setVerticalScrollBarPolicy(policy)

    # ----------------------------------------------------------------------
    # Key handling — Esc closes (or exits fullscreen first)
    # ----------------------------------------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._is_fullscreen:
                self._toggle_fullscreen()
            else:
                self.reject()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode and not self._pix_item.pixmap().isNull():
            QTimer.singleShot(0, self._fit_to_window)
