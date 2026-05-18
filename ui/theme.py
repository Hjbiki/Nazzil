# -*- coding: utf-8 -*-
"""Linear Design System theme for Nazzil.

Two layers:
    1. `THEME_QSS` — the global stylesheet applied via `app.setStyleSheet`.
    2. `apply_shadow(widget, …)` — programmatic QGraphicsDropShadowEffect
       (Qt's QSS has no box-shadow), called from ui/app.py and
       ui/download_row.py to add Linear's "glass edge" depth.

Token reference (see Linear DESIGN.md):

    Surface levels (darker → lighter, ~elevation)
        L0 #08090A  — window background
        L1 #0F1011  — main content panel (downloads list)
        L2 #141516  — cards (download row, format picker, playlist)
        L3 #1C1C1F  — URL bar area, search bar, settings panels
        L4 #232326  — hover state on cards, active tab background
        L5 #28282C  — context menus, dropdowns, tooltips

    Borders (3 strengths, never just one)
        Primary    #23252A  — standard card / panel boundaries
        Secondary  #34343A  — strong section dividers
        Tertiary   #3E3E44  — focused / active panels
        Input      rgba(255,255,255,0.08)  → flat #2A2D33
        Focus      #5E6AD2

    Text  #F7F8F8 / #D0D6E0 / #8A8F98 / #62666D
    Brand #5E6AD2 (hover #828FFF), accent tint rgba(94,106,210,0.18)
    Status green #27A644, red #EB5757, yellow #F0BF00

Spacing scale (anything not in this list is forbidden):
    4 · 6 · 8 · 10 · 12 · 16 · 20 · 24 · 40 · 48
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


# ===========================================================================
# Raw colour tokens (re-exported so Python can reach them when QSS isn't
# enough — e.g. QPainter colours or programmatic effect tints).
# ===========================================================================

# Surface levels
L0 = APP_BG       = "#101112"
L1 = PANEL_BG     = "#0F1011"
L2 = CARD_BG      = "#141516"
L3 = SURF_2       = "#1C1C1F"
L4 = SURF_3       = "#232326"
L5 = SURF_4       = "#28282C"

# Borders
BORDER            = "#23252A"   # primary
BORDER_HI         = "#34343A"   # secondary
BORDER_STRONG     = "#3E3E44"   # tertiary

# Input / overlay (flattened from rgba over near-black, kept as solid
# hex so QSS renders identically to the rgba intent)
INPUT_BG          = "#161719"   # ~ rgba(255,255,255,0.03)
INPUT_BG_HOVER    = "#1B1C1F"   # ~ rgba(255,255,255,0.07)
INPUT_BORDER      = "#2A2D33"   # ~ rgba(255,255,255,0.08)
TRANSLUCENT_5     = "#1A1B1E"   # ~ rgba(255,255,255,0.05)
SEC_HOVER         = INPUT_BG_HOVER

# Brand
ACCENT            = "#5E6AD2"
ACCENT_HOV        = "#828FFF"
ACCENT_TINT       = "#1F2240"   # ~ rgba(94,106,210,0.18) over L0
ACCENT_TINT_BORDER = "#525E9E"  # ~ rgba(130,143,255,0.4)

# Text
TEXT              = "#F7F8F8"
TEXT_DIM          = "#D0D6E0"
TEXT_MUTED        = "#8A8F98"
TEXT_FAINT        = "#62666D"

# Status
OK                = "#27A644"
ERR               = "#EB5757"
WARN              = "#F0BF00"


# ===========================================================================
# Object names + role properties (canonical so QSS selectors don't drift)
# ===========================================================================
#   #PanelMain      — main downloads panel (L1)
#   #PanelCard      — options/playlist cards (L2)
#   #DownloadRow    — single download row (L2)
#   #UrlPill        — top URL bar wrapper (L3)
#   #UrlEntry       — line edit inside UrlPill
#   #SearchEntry    — downloads list search (L3)
#   #UpdateBanner   — top-of-window update banner
#   #BottomStatusBar— footer bar with version + dot
#   #ThumbBox / #PreviewBox  — image holders
#   #DurationBadge  — overlay chip on thumbnails
#   #SectionHeader / #Hint / #StatusLabel / #MetaLabel / #TitleLabel
#                   / #FetchedTitle — typed labels
#   QPushButton[role=
#       "primary" | "secondary" | "danger" | "icon" |
#       "tab" | "tabActive" | "kebab" | "kebabDanger"]
#   QLabel[role="badge" | "badgeActive"]
#   QCheckBox[role="switch"]


# ===========================================================================
# Stylesheet
# ===========================================================================

THEME_QSS = f"""
/* ===========================================================
   Base — Thmanyah Sans first (loaded from assets/fonts at
   startup), then OS Arabic/Latin fallbacks.
   =========================================================== */
QWidget {{
    background: {L0};
    color: {TEXT};
    font-family: "Thmanyah Sans", "Segoe UI", "Tahoma",
                 "Noto Sans Arabic", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.15px;
}}

QMainWindow {{ background: {L0}; }}

/* ===========================================================
   Surfaces — six distinct elevation levels
   =========================================================== */

/* L1 — the main downloads panel */
QFrame#PanelMain {{
    background: {L1};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

/* L2 — options + playlist cards (sit on top of L0/L1) */
QFrame#PanelCard {{
    background: {L2};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

/* L2 — individual download row */
QFrame#DownloadRow {{
    background: {L2};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#DownloadRow:hover {{
    background: {L4};
    border-color: {BORDER_HI};
}}

/* Translucent inner panels — header strips inside a card */
QFrame#FrostedHeader {{
    background: {TRANSLUCENT_5};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
}}

/* Thumbnail / preview holders */
QFrame#ThumbBox,
QFrame#PreviewBox {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
}}

QLabel#DurationBadge {{
    background: black;
    color: white;
    font-size: 10px;
    font-weight: 600;
    padding: 0 4px;
    min-height: 16px;
    border-radius: 4px;
}}

/* ===========================================================
   Labels
   =========================================================== */
QLabel {{ background: transparent; color: {TEXT}; }}
QLabel#StatusLabel,
QLabel#MetaLabel {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: -0.15px;
}}
QLabel#TitleLabel,
QLabel#FetchedTitle {{
    color: {TEXT};
    font-weight: 600;
    font-size: 13px;
    letter-spacing: -0.3px;
}}
QLabel#SectionHeader {{
    color: {TEXT};
    font-weight: 600;
    font-size: 12px;
    letter-spacing: -0.3px;
}}
QLabel#Hint {{
    color: {TEXT_MUTED};
    font-size: 11px;
    font-weight: 500;
}}
QLabel[state="ok"]   {{ color: {OK}; }}
QLabel[state="err"]  {{ color: {ERR}; }}
QLabel[state="warn"] {{ color: {WARN}; }}

/* ===========================================================
   URL pill (L3) + line edits
   =========================================================== */
QFrame#UrlPill {{
    background: {L3};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
}}
QFrame#UrlPill[focused="true"] {{ border-color: {ACCENT}; }}

QLineEdit {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
    padding: 0 12px;
    min-height: 40px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QLineEdit#UrlEntry {{
    background: transparent;
    border: none;
    padding: 0 4px;
    min-height: 40px;
    font-size: 13px;
    letter-spacing: -0.15px;
}}
QLineEdit#UrlEntry:focus {{ border: none; }}

QLineEdit#SearchEntry {{
    background: {L3};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
    padding: 0 12px;
    min-height: 40px;
}}
QLineEdit#SearchEntry:focus {{ border-color: {ACCENT}; }}

/* ===========================================================
   Buttons — pill-shaped, no fixed height in Python.
   Secondary is the default; role=primary/danger/icon/tab override.
   =========================================================== */
QPushButton {{
    background: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {INPUT_BORDER};
    border-radius: 9999px;
    padding: 0 16px;
    min-height: 40px;
    font-weight: 600;
    letter-spacing: -0.3px;
}}
QPushButton:hover    {{ background: {INPUT_BG_HOVER}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; }}

/* Primary — brand-coloured */
QPushButton[role="primary"] {{
    background: {ACCENT};
    color: white;
    border: 1px solid transparent;
    border-radius: 9999px;
    padding: 0 20px;
    min-height: 40px;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover   {{ background: {ACCENT_HOV}; }}
QPushButton[role="primary"]:pressed {{ background: {ACCENT}; }}

/* Secondary — explicit class for the few call sites that set role */
QPushButton[role="secondary"] {{
    background: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {INPUT_BORDER};
}}

/* Danger tint (text colour only) */
QPushButton[role="danger"] {{
    color: {ERR};
}}

/* Round icon-only button (settings/account in top bar) */
QPushButton[role="icon"] {{
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    border-radius: 9999px;
    font-size: 16px;
    padding: 0;
}}

/* Kebab + ✕ on each row */
QPushButton[role="kebab"] {{
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    border-radius: 9999px;
    font-size: 14px;
    padding: 0;
    font-weight: 600;
}}
QPushButton[role="kebabDanger"] {{
    min-width: 24px;
    max-width: 24px;
    min-height: 24px;
    max-height: 24px;
    border-radius: 9999px;
    font-size: 12px;
    padding: 0;
    font-weight: 600;
    background: transparent;
    color: {ERR};
    border: 1px solid {INPUT_BORDER};
}}
QPushButton[role="kebabDanger"]:hover {{ background: {INPUT_BG_HOVER}; }}

/* Tab-style pushbutton (segmented group) */
QPushButton[role="tab"] {{
    background: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {INPUT_BORDER};
    border-radius: 9999px;
    padding: 0 20px;
    min-height: 40px;
    font-weight: 500;
}}
QPushButton[role="tab"]:hover {{ background: {INPUT_BG_HOVER}; }}
QPushButton[role="tabActive"] {{
    background: {L4};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    border-radius: 9999px;
    padding: 0 20px;
    min-height: 40px;
    font-weight: 600;
}}

/* ===========================================================
   Badges
   =========================================================== */
QLabel[role="badge"] {{
    background: {TRANSLUCENT_5};
    color: {TEXT_DIM};
    border: 1px solid {INPUT_BORDER};
    border-radius: 9999px;
    padding: 0 10px;
    min-height: 24px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: -0.15px;
}}
QLabel[role="badgeActive"] {{
    background: {ACCENT_TINT};
    color: white;
    border: 1px solid {ACCENT_TINT_BORDER};
    border-radius: 9999px;
    padding: 0 10px;
    min-height: 24px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: -0.15px;
}}

/* ===========================================================
   ComboBox — inputs
   =========================================================== */
QComboBox {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
    padding: 0 12px;
    min-height: 40px;
    color: {TEXT};
    font-weight: 500;
}}
QComboBox:hover {{ background: {INPUT_BG_HOVER}; }}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QComboBox::down-arrow {{ image: none; }}

/* Popup list (L5 — popover surface) */
QComboBox QAbstractItemView {{
    background: {L5};
    border: 1px solid {BORDER_HI};
    color: {TEXT};
    selection-background-color: {INPUT_BG_HOVER};
    selection-color: {TEXT};
    outline: 0;
    padding: 4px;
    border-radius: 12px;
}}

/* ===========================================================
   Progress bar
   =========================================================== */
QProgressBar {{
    background: {INPUT_BG};
    border: none;
    border-radius: 4px;
    min-height: 4px;
    max-height: 4px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}

/* ===========================================================
   Checkbox
   =========================================================== */
QCheckBox {{
    background: transparent;
    color: {TEXT_DIM};
    spacing: 8px;
    font-weight: 500;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {INPUT_BORDER};
    background: {INPUT_BG};
    border-radius: 4px;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT_HOV}; }}

/* Switch — implemented as QCheckBox[role="switch"] */
QCheckBox[role="switch"]::indicator {{
    width: 32px;
    height: 20px;
    border-radius: 10px;
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
}}
QCheckBox[role="switch"]::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ===========================================================
   Scroll area / scroll bars
   =========================================================== */
QScrollArea {{ background: transparent; border: 0; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 4px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_HI};
    min-height: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {BORDER_STRONG}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0 4px 4px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_HI};
    min-width: 24px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {BORDER_STRONG}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ===========================================================
   Menus — L5 popover surface
   =========================================================== */
QMenu {{
    background: {L5};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 500;
}}
QMenu::item:selected {{
    background: {INPUT_BG_HOVER};
    color: {TEXT};
}}
QMenu::item:disabled {{ color: {TEXT_FAINT}; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER_HI};
    margin: 4px 6px;
}}

/* ===========================================================
   Dialogs — settings panel surface (L3)
   =========================================================== */
QDialog {{ background: {L3}; }}
QDialog QLabel {{ background: transparent; }}

/* ===========================================================
   Tooltips — L5 popover
   =========================================================== */
QToolTip {{
    background: {L5};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    padding: 8px 10px;
    border-radius: 8px;
}}

/* ===========================================================
   Frameless window chrome
   =========================================================== */

/* Rounded window shell — subtle diagonal gradient for depth.
   The window is clipped to a 12 px rounded rectangle by the
   FramelessMainWindow / FramelessDialog mask. The border + radius here
   give the visible edge polish. Same shell QSS applies to dialogs
   (SettingsDialog, AccountDialog) so they match the main window. */
QFrame#WindowShell {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #151617,
        stop:1 #101112
    );
    border: 1px solid #1F2024;
    border-radius: 12px;
}}

QWidget#TitleBar {{
    background: transparent;
}}

/* ----- URL bar row (under the title bar) ----- */
QFrame#UrlRow {{
    background: transparent;
    border: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}}
QLineEdit#UrlEntryV2 {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 0 12px;
    min-height: 40px;
    color: {TEXT};
    font-size: 13px;
}}
QLineEdit#UrlEntryV2:focus {{ border-color: {ACCENT}; }}

QPushButton#FetchBtnV2 {{
    background: {ACCENT};
    color: white;
    border: 0;
    border-radius: 8px;
    min-height: 40px;
    padding: 0 20px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#FetchBtnV2:hover    {{ background: {ACCENT_HOV}; }}
QPushButton#FetchBtnV2:disabled {{ color: rgba(255,255,255,0.5); }}

/* ----- Filter pills row ----- */
QFrame#FilterRow {{
    background: transparent;
    border: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}}
QPushButton[role="pill"] {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    padding: 0 12px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 500;
}}
QPushButton[role="pill"]:hover {{
    background: rgba(255, 255, 255, 0.04);
    color: {TEXT_DIM};
}}
QPushButton[role="pillActive"] {{
    background: rgba(94, 106, 210, 0.15);
    color: #828FFF;
    border: 1px solid rgba(130, 143, 255, 0.4);
    border-radius: 6px;
    padding: 0 12px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton[role="pillIcon"] {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    padding: 0;
}}
QPushButton[role="pillIcon"]:hover {{
    background: rgba(255, 255, 255, 0.04);
    color: {TEXT_DIM};
}}

/* Danger-tinted icon button (Clear all in filter row) */
QPushButton[role="clearDanger"] {{
    background: rgba(235, 87, 87, 0.08);
    color: {ERR};
    border: 1px solid rgba(235, 87, 87, 0.25);
    border-radius: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    padding: 0;
}}
QPushButton[role="clearDanger"]:hover {{
    background: rgba(235, 87, 87, 0.18);
    border-color: rgba(235, 87, 87, 0.4);
}}

QLineEdit#SearchEntryCompact {{
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 0 12px 0 32px;
    min-height: 32px;
    color: {TEXT};
    font-size: 13px;
}}
QLineEdit#SearchEntryCompact:focus {{ border-color: {ACCENT}; }}

QComboBox#SortCompact {{
    background: transparent;
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    padding: 0 10px;
    min-height: 24px;
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 500;
}}
QComboBox#SortCompact:hover {{ background: rgba(255,255,255,0.04); }}
QComboBox#SortCompact::drop-down {{ border: 0; width: 12px; }}
QComboBox#SortCompact::down-arrow {{ image: none; }}

/* ----- Download row v2 ----- */
QFrame#RowV2 {{
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
}}
QFrame#RowV2:hover {{
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.1);
}}
QFrame#RowV2[state="downloading"] {{
    background: rgba(94, 106, 210, 0.04);
    border-color: rgba(130, 143, 255, 0.2);
}}
QFrame#RowV2[state="failed"] {{
    border-color: rgba(235, 87, 87, 0.25);
}}

QFrame#RowV2 QFrame#ThumbBoxV2 {{
    background: {L3};
    border-radius: 5px;
    border: 0;
}}
QLabel#DurationBadgeV2 {{
    background: rgba(8, 9, 10, 0.85);
    color: {TEXT_DIM};
    border-radius: 3px;
    padding: 0 4px;
    min-height: 12px;
    font-size: 9px;
    font-weight: 500;
}}

QLabel#TitleV2 {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.15px;
}}
QLabel#ChannelV2 {{
    color: {TEXT_DIM};
    font-size: 12px;
    font-weight: 400;
}}
QLabel#MetaV2 {{
    color: {TEXT_FAINT};
    font-size: 12px;
    font-weight: 500;
}}
QLabel#MetaV2[state="downloading"] {{ color: #828FFF; }}
QLabel#MetaV2[state="err"]         {{ color: {ERR}; }}

/* Tags on the channel line */
QLabel[role="tagYouTube"] {{
    background: rgba(235, 87, 87, 0.12);
    color: #FF6B6B;
    border: 1px solid rgba(235, 87, 87, 0.3);
    border-radius: 3px;
    padding: 0 6px;
    min-height: 18px;
    font-size: 12px;
    font-weight: 500;
}}
QLabel[role="tagFormat"] {{
    background: rgba(94, 106, 210, 0.12);
    color: #828FFF;
    border: 1px solid rgba(130, 143, 255, 0.25);
    border-radius: 3px;
    padding: 0 6px;
    min-height: 18px;
    font-size: 12px;
    font-weight: 500;
}}
QLabel[role="tagAudio"] {{
    background: rgba(240, 191, 0, 0.12);
    color: {WARN};
    border: 1px solid rgba(240, 191, 0, 0.25);
    border-radius: 3px;
    padding: 0 6px;
    min-height: 18px;
    font-size: 12px;
    font-weight: 500;
}}

/* Row action buttons — final 30×30 with 1 px border.
   QSS adds borders on top of min-width/min-height in Qt, so we set
   content to 28 px → total 30 px. */
QPushButton[role="rowAction"] {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    padding: 0;
}}
QPushButton[role="rowAction"]:hover {{
    background: rgba(255, 255, 255, 0.05);
    color: {TEXT};
}}
QPushButton[role="rowActionDanger"] {{
    background: rgba(235, 87, 87, 0.08);
    color: {ERR};
    border: 1px solid rgba(235, 87, 87, 0.2);
    border-radius: 6px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    padding: 0;
}}
QPushButton[role="rowActionDanger"]:hover {{
    background: rgba(235, 87, 87, 0.15);
}}

/* Row progress bar — slimmer than the global default */
QProgressBar#RowProgressV2 {{
    background: rgba(255, 255, 255, 0.05);
    border: 0;
    border-radius: 1px;
    min-height: 2px;
    max-height: 2px;
    color: transparent;
}}
QProgressBar#RowProgressV2::chunk {{
    background: {ACCENT};
    border-radius: 1px;
}}
QProgressBar#RowProgressV2[state="completed"]::chunk {{ background: {OK}; }}
QProgressBar#RowProgressV2[state="err"]::chunk       {{ background: {ERR}; }}
QProgressBar#RowProgressV2[state="paused"]::chunk    {{ background: {TEXT_FAINT}; }}

/* ----- Pagination row ----- */
QFrame#PaginationRow {{
    background: transparent;
    border: 0;
}}
QLabel#PaginationLabel {{
    color: {TEXT_FAINT};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton[role="pageBtn"] {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 5px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    font-size: 10px;
    padding: 0;
}}
QPushButton[role="pageBtn"]:hover {{
    background: rgba(255, 255, 255, 0.05);
    color: {TEXT};
}}
QPushButton[role="pageBtnActive"] {{
    background: {ACCENT};
    color: white;
    border: 0;
    border-radius: 5px;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
    font-size: 10px;
    padding: 0;
    font-weight: 500;
}}

/* ----- Bottom footer strip ----- */
QFrame#FooterStrip {{
    background: rgba(15, 16, 17, 0.6);
    border: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
}}
QLabel#FooterText {{
    color: {TEXT_FAINT};
    font-size: 12px;
    font-weight: 500;
}}
"""


# ===========================================================================
# Shadows — programmatic, since QSS has no box-shadow.
# ===========================================================================
def apply_shadow(widget, blur=12, color=(0, 0, 0, 40), x=0, y=3):
    """Attach a QGraphicsDropShadowEffect to `widget`.

    Linear's "glass edge" depth comes from soft shadows under elevated
    surfaces combined with the fine 1 px borders. Numbers chosen to match
    the spec recipes:

        Main panel        blur=12 alpha=40 offset=(0,3)
        Format card       blur=10 alpha=35 offset=(0,2)
        URL bar           blur= 8 alpha=30 offset=(0,2)
        Download row      blur= 4 alpha=20 offset=(0,1)
        Popovers          blur=32 alpha=90 offset=(0,7)
    """
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    r, g, b, a = color
    eff.setColor(QColor(r, g, b, a))
    eff.setOffset(x, y)
    widget.setGraphicsEffect(eff)
    return eff


# Convenient named recipes
SHADOW_PANEL  = dict(blur=12, color=(0, 0, 0, 40), x=0, y=3)
SHADOW_CARD   = dict(blur=10, color=(0, 0, 0, 35), x=0, y=2)
SHADOW_INPUT  = dict(blur=8,  color=(0, 0, 0, 30), x=0, y=2)
SHADOW_ROW    = dict(blur=4,  color=(0, 0, 0, 20), x=0, y=1)
SHADOW_POPUP  = dict(blur=32, color=(0, 0, 0, 90), x=0, y=7)


# (The blur-fallback override was removed — the shell is always solid.)
