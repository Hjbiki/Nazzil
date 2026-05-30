# -*- coding: utf-8 -*-
"""Linear Design System theme for Nazzil — now with Dark + Light palettes.

Two layers:
    1. A QSS template (`_QSS_TEMPLATE`) rendered against a *palette* dict via
       `build_qss(palette)`. `THEME_QSS` is the dark render kept for the
       module's historical import. `apply_theme(app, mode)` swaps the live
       stylesheet AND rebinds the module-level colour constants so any widget
       built afterwards (dialogs, new rows) uses the active palette.
    2. `apply_shadow(widget, …)` — programmatic QGraphicsDropShadowEffect
       (Qt's QSS has no box-shadow).

The two palettes share the same KEYS; only the values differ. Code that
needs a colour at runtime (inline stylesheets) should read it from
`current()` so it follows the active theme.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


# ===========================================================================
# Palettes — every key exists in BOTH dicts (parity matters: apply_theme
# rebinds all of them as module globals). Dark keeps the exact pre-1.5
# values so dark mode is visually unchanged.
# ===========================================================================
DARK = {
    # Surface levels
    "L0": "#101112", "APP_BG": "#101112",
    "L1": "#0F1011", "PANEL_BG": "#0F1011",
    "L2": "#141516", "CARD_BG": "#141516",
    "L3": "#1C1C1F", "SURF_2": "#1C1C1F",
    "L4": "#232326", "SURF_3": "#232326",
    "L5": "#28282C", "SURF_4": "#28282C",
    # Borders
    "BORDER": "#23252A",
    "BORDER_HI": "#34343A",
    "BORDER_STRONG": "#3E3E44",
    # Input / overlay
    "INPUT_BG": "#161719",
    "INPUT_BG_HOVER": "#1B1C1F",
    "INPUT_BORDER": "#2A2D33",
    "TRANSLUCENT_5": "#1A1B1E",
    "SEC_HOVER": "#1B1C1F",
    # Brand
    "ACCENT": "#5E6AD2",
    "ACCENT_HOV": "#828FFF",
    "ACCENT_TINT": "#1F2240",
    "ACCENT_TINT_BORDER": "#525E9E",
    # Text
    "TEXT": "#F7F8F8",
    "TEXT_DIM": "#D0D6E0",
    "TEXT_MUTED": "#8A8F98",
    "TEXT_FAINT": "#62666D",
    # Status
    "OK": "#27A644",
    "ERR": "#EB5757",
    "WARN": "#F0BF00",
    # ---- Semantic overlay tokens (V2 chrome) ----
    "SHELL_TOP": "#151617",
    "SHELL_BOTTOM": "#101112",
    "SHELL_BORDER": "#1F2024",
    "DIVIDER": "rgba(255, 255, 255, 0.04)",
    "OVER_HOVER": "rgba(255, 255, 255, 0.04)",
    "OVER_HOVER_2": "rgba(255, 255, 255, 0.05)",
    "FILL_FIELD": "rgba(255, 255, 255, 0.04)",
    "FILL_FIELD_BORDER": "rgba(255, 255, 255, 0.08)",
    "ROW_BG": "rgba(255, 255, 255, 0.02)",
    "ROW_BG_HOVER": "rgba(255, 255, 255, 0.04)",
    "ROW_BORDER": "rgba(255, 255, 255, 0.06)",
    "ROW_BORDER_HOVER": "rgba(255, 255, 255, 0.1)",
    "ROW_DL_BG": "rgba(94, 106, 210, 0.04)",
    "ROW_DL_BORDER": "rgba(130, 143, 255, 0.2)",
    "ROW_FAIL_BORDER": "rgba(235, 87, 87, 0.25)",
    "PROG_TRACK": "rgba(255, 255, 255, 0.05)",
    "FOOTER_BG": "rgba(15, 16, 17, 0.6)",
    "PILL_ACTIVE_BG": "rgba(94, 106, 210, 0.15)",
    "PILL_ACTIVE_FG": "#828FFF",
    "PILL_ACTIVE_BORDER": "rgba(130, 143, 255, 0.4)",
    "DUR_BADGE_BG": "rgba(8, 9, 10, 0.85)",
    "META_DL": "#828FFF",
}

LIGHT = {
    # Surface levels — soft off-white base, white panels.
    "L0": "#F7F8FA", "APP_BG": "#F7F8FA",
    "L1": "#FFFFFF", "PANEL_BG": "#FFFFFF",
    "L2": "#FFFFFF", "CARD_BG": "#FFFFFF",
    "L3": "#F2F3F5", "SURF_2": "#F2F3F5",
    "L4": "#ECEDF0", "SURF_3": "#ECEDF0",
    "L5": "#FFFFFF", "SURF_4": "#FFFFFF",
    # Borders
    "BORDER": "#E3E5EA",
    "BORDER_HI": "#D5D8DE",
    "BORDER_STRONG": "#C2C6CE",
    # Input / overlay
    "INPUT_BG": "#FFFFFF",
    "INPUT_BG_HOVER": "#F2F3F5",
    "INPUT_BORDER": "#DDE0E5",
    "TRANSLUCENT_5": "#F2F3F5",
    "SEC_HOVER": "#F2F3F5",
    # Brand (darker hover since text on accent is white)
    "ACCENT": "#5E6AD2",
    "ACCENT_HOV": "#4F5BC4",
    "ACCENT_TINT": "#EEF0FB",
    "ACCENT_TINT_BORDER": "#C3C9F0",
    # Text — near-black scale
    "TEXT": "#1C1D21",
    "TEXT_DIM": "#3A3D44",
    "TEXT_MUTED": "#6B7280",
    "TEXT_FAINT": "#9CA1AB",
    # Status (slightly darkened for contrast on white)
    "OK": "#1F9E3D",
    "ERR": "#D63B3B",
    "WARN": "#B8860B",
    # ---- Semantic overlay tokens ----
    "SHELL_TOP": "#FFFFFF",
    "SHELL_BOTTOM": "#F3F4F7",
    "SHELL_BORDER": "#E3E5EA",
    "DIVIDER": "rgba(0, 0, 0, 0.06)",
    "OVER_HOVER": "rgba(0, 0, 0, 0.04)",
    "OVER_HOVER_2": "rgba(0, 0, 0, 0.05)",
    "FILL_FIELD": "#FFFFFF",
    "FILL_FIELD_BORDER": "#DDE0E5",
    "ROW_BG": "#FFFFFF",
    "ROW_BG_HOVER": "#F4F5F8",
    "ROW_BORDER": "#E6E8EC",
    "ROW_BORDER_HOVER": "#D5D8DE",
    "ROW_DL_BG": "rgba(94, 106, 210, 0.08)",
    "ROW_DL_BORDER": "rgba(94, 106, 210, 0.35)",
    "ROW_FAIL_BORDER": "rgba(214, 59, 59, 0.4)",
    "PROG_TRACK": "rgba(0, 0, 0, 0.08)",
    "FOOTER_BG": "rgba(244, 245, 248, 0.7)",
    "PILL_ACTIVE_BG": "rgba(94, 106, 210, 0.12)",
    "PILL_ACTIVE_FG": "#4F5BC4",
    "PILL_ACTIVE_BORDER": "rgba(94, 106, 210, 0.4)",
    "DUR_BADGE_BG": "rgba(0, 0, 0, 0.65)",
    "META_DL": "#4F5BC4",
}

_PALETTES = {"dark": DARK, "light": LIGHT}

# Active palette — read by inline-styled widgets via current().
_active = DARK


def current() -> dict:
    """The palette dict currently in effect."""
    return _active


def palette_for(mode: str) -> dict:
    return _PALETTES.get(mode, DARK)


# ---------------------------------------------------------------------------
# Module-level colour constants (bound to the dark palette at import; rebound
# by apply_theme). Kept so existing `from ui.theme import L1, ACCENT, …`
# imports keep working.
# ---------------------------------------------------------------------------
def _bind_globals(palette: dict):
    globals().update(palette)


_bind_globals(DARK)


# ===========================================================================
# Stylesheet template — {{ }} are literal CSS braces; {TOKEN} placeholders
# are filled from the palette via str.format(**palette).
# ===========================================================================
_QSS_TEMPLATE = """
/* ===========================================================
   Base — Thmanyah Sans first, then OS Arabic/Latin fallbacks.
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
   Surfaces
   =========================================================== */
QFrame#PanelMain {{
    background: {L1};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#PanelCard {{
    background: {L2};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#DownloadRow {{
    background: {L2};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#DownloadRow:hover {{
    background: {L4};
    border-color: {BORDER_HI};
}}
QFrame#FrostedHeader {{
    background: {TRANSLUCENT_5};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
}}
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
   Buttons
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

QPushButton[role="secondary"] {{
    background: {INPUT_BG};
    color: {TEXT};
    border: 1px solid {INPUT_BORDER};
}}

QPushButton[role="danger"] {{
    color: {ERR};
}}

QPushButton[role="icon"] {{
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    border-radius: 9999px;
    font-size: 16px;
    padding: 0;
}}

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
   ComboBox
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
   Radio button
   =========================================================== */
QRadioButton {{
    background: transparent;
    color: {TEXT_DIM};
    spacing: 8px;
    font-weight: 500;
}}
QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {INPUT_BORDER};
    background: {INPUT_BG};
    border-radius: 8px;
}}
QRadioButton::indicator:checked {{
    background: {ACCENT};
    border: 4px solid {INPUT_BG};
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
   Menus
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
   Dialogs
   =========================================================== */
QDialog {{ background: {L3}; }}
QDialog QLabel {{ background: transparent; }}

/* ===========================================================
   Tooltips
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
QFrame#WindowShell {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 {SHELL_TOP},
        stop:1 {SHELL_BOTTOM}
    );
    border: 1px solid {SHELL_BORDER};
    border-radius: 12px;
}}

QWidget#TitleBar {{
    background: transparent;
}}

/* Dialog title-bar text (FramelessDialog) — palette-driven so it follows
   a live theme switch. */
QLabel#DialogTitleText {{
    color: {TEXT_DIM};
    font-size: 13px;
    font-weight: 500;
    letter-spacing: -0.15px;
    background: transparent;
}}

/* ----- URL bar row ----- */
QFrame#UrlRow {{
    background: transparent;
    border: 0;
    border-bottom: 1px solid {DIVIDER};
}}
QLineEdit#UrlEntryV2 {{
    background: {FILL_FIELD};
    border: 1px solid {FILL_FIELD_BORDER};
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
    border-bottom: 1px solid {DIVIDER};
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
    background: {OVER_HOVER};
    color: {TEXT_DIM};
}}
QPushButton[role="pillActive"] {{
    background: {PILL_ACTIVE_BG};
    color: {PILL_ACTIVE_FG};
    border: 1px solid {PILL_ACTIVE_BORDER};
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
    background: {OVER_HOVER};
    color: {TEXT_DIM};
}}

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
    background: {FILL_FIELD};
    border: 1px solid {FILL_FIELD_BORDER};
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
QComboBox#SortCompact:hover {{ background: {OVER_HOVER}; }}
QComboBox#SortCompact::drop-down {{ border: 0; width: 12px; }}
QComboBox#SortCompact::down-arrow {{ image: none; }}

/* ----- Download row v2 ----- */
QFrame#RowV2 {{
    background: {ROW_BG};
    border: 1px solid {ROW_BORDER};
    border-radius: 8px;
}}
QFrame#RowV2:hover {{
    background: {ROW_BG_HOVER};
    border-color: {ROW_BORDER_HOVER};
}}
QFrame#RowV2[state="downloading"] {{
    background: {ROW_DL_BG};
    border-color: {ROW_DL_BORDER};
}}
QFrame#RowV2[state="failed"] {{
    border-color: {ROW_FAIL_BORDER};
}}

QFrame#RowV2 QFrame#ThumbBoxV2 {{
    background: {L3};
    border-radius: 5px;
    border: 0;
}}
QLabel#DurationBadgeV2 {{
    background: {DUR_BADGE_BG};
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
QLabel#MetaV2[state="downloading"] {{ color: {META_DL}; }}
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
    color: {PILL_ACTIVE_FG};
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
    background: {OVER_HOVER_2};
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

QProgressBar#RowProgressV2 {{
    background: {PROG_TRACK};
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
    background: {OVER_HOVER_2};
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
    background: {FOOTER_BG};
    border: 0;
    border-top: 1px solid {DIVIDER};
}}
QLabel#FooterText {{
    color: {TEXT_FAINT};
    font-size: 12px;
    font-weight: 500;
}}
"""


def build_qss(palette: dict) -> str:
    """Render the QSS template against a palette dict."""
    return _QSS_TEMPLATE.format(**palette)


def qss_for(mode: str) -> str:
    return build_qss(palette_for(mode))


# Dark render kept under the historical name (main.py imports THEME_QSS).
THEME_QSS = build_qss(DARK)


def apply_theme(app, mode: str) -> str:
    """Swap the live application theme. Rebinds the module colour constants
    so widgets built afterwards pick up the new palette, then sets the
    stylesheet. Returns the mode actually applied."""
    global _active
    mode = mode if mode in _PALETTES else "dark"
    _active = _PALETTES[mode]
    _bind_globals(_active)
    if app is not None:
        app.setStyleSheet(build_qss(_active))
    return mode


# ===========================================================================
# Shadows
# ===========================================================================
def apply_shadow(widget, blur=12, color=(0, 0, 0, 40), x=0, y=3):
    """Attach a QGraphicsDropShadowEffect to `widget`."""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    r, g, b, a = color
    eff.setColor(QColor(r, g, b, a))
    eff.setOffset(x, y)
    widget.setGraphicsEffect(eff)
    return eff


SHADOW_PANEL  = dict(blur=12, color=(0, 0, 0, 40), x=0, y=3)
SHADOW_CARD   = dict(blur=10, color=(0, 0, 0, 35), x=0, y=2)
SHADOW_INPUT  = dict(blur=8,  color=(0, 0, 0, 30), x=0, y=2)
SHADOW_ROW    = dict(blur=4,  color=(0, 0, 0, 20), x=0, y=1)
SHADOW_POPUP  = dict(blur=32, color=(0, 0, 0, 90), x=0, y=7)
