# -*- coding: utf-8 -*-
"""Linear-inspired dark theme as a QSS stylesheet.

Token references:
    APP_BG       #08090A   window
    PANEL_BG     #0F1011   downloads panel, options/playlist cards
    CARD_BG      #141516   download rows
    BORDER       #23252A
    BORDER_HI    #34343A
    INPUT_BG     rgba(255,255,255,0.03)  → flattened to #161719
    INPUT_BORDER rgba(255,255,255,0.08)  → flattened to #2A2D33
    ACCENT       #5E6AD2   hover #828FFF
    ACCENT_TINT  rgba(94,106,210,0.18)   active tabs / badges
    TEXT         #F7F8F8 / #D0D6E0 / #8A8F98 / #62666D
    OK / ERR / WARN  #27A644 / #EB5757 / #F0BF00
"""

# --- raw colour constants (re-exported so Python code can reference them
#     when QSS isn't enough — e.g. setting QPainter colours or row tints)
APP_BG       = "#08090A"
PANEL_BG     = "#0F1011"
CARD_BG      = "#141516"
SURF_2       = "#1C1C1F"
SURF_3       = "#232326"
BORDER       = "#23252A"
BORDER_HI    = "#34343A"
INPUT_BG     = "#161719"
INPUT_BORDER = "#2A2D33"
SEC_HOVER    = "#2A2D33"
ACCENT       = "#5E6AD2"
ACCENT_HOV   = "#828FFF"
ACCENT_TINT  = "#1F2240"
ACCENT_TINT_BORDER = "#525E9E"
TEXT         = "#F7F8F8"
TEXT_DIM     = "#D0D6E0"
TEXT_MUTED   = "#8A8F98"
TEXT_FAINT   = "#62666D"
OK           = "#27A644"
ERR          = "#EB5757"
WARN         = "#F0BF00"


# Names used as Qt object names / property selectors throughout the UI.
# Keep this list canonical so QSS selectors don't drift from Python.
#   #UrlPill, #UrlEntry, #SearchEntry
#   QPushButton[role="primary"|"secondary"|"icon"|"danger"|"tab"|"tabActive"|"badge"|"kebab"]
#   #PanelCard, #DownloadRow, #ThumbBox, #DurationBadge
#   #StatusLabel, #MetaLabel, #TitleLabel, #FetchedTitle
#   QProgressBar
#   QComboBox, QLineEdit
#   QMenu, QScrollBar
#   QDialog


THEME_QSS = f"""
/* ===========================================================
   Base
   ===========================================================
   Primary family: Thmanyah Sans (registered at startup from
   assets/fonts/). Fallbacks cover both Latin and Arabic if the bundled
   font is missing — Tahoma & Noto Sans Arabic have good descender
   metrics so ج ح ت ي don't get clipped. */
QWidget {{
    background: {APP_BG};
    color: {TEXT};
    font-family: "Thmanyah Sans", "Segoe UI", "Tahoma", "Noto Sans Arabic", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QMainWindow {{ background: {APP_BG}; }}

/* ===========================================================
   Surfaces
   =========================================================== */
QFrame#PanelCard {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#DownloadRow {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#ThumbBox {{
    background: {INPUT_BG};
    border-radius: 8px;
}}
QFrame#PreviewBox {{
    background: {INPUT_BG};
    border-radius: 8px;
}}
QLabel#DurationBadge {{
    background: black;
    color: white;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 4px;
}}

/* ===========================================================
   Labels
   =========================================================== */
QLabel {{ background: transparent; color: {TEXT}; }}
QLabel#StatusLabel,
QLabel#MetaLabel {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel#TitleLabel {{
    color: {TEXT};
    font-weight: 700;
    font-size: 13px;
}}
QLabel#FetchedTitle {{
    color: {TEXT};
    font-weight: 700;
    font-size: 13px;
}}
QLabel#SectionHeader {{
    color: {TEXT};
    font-weight: 700;
    font-size: 12px;
}}
QLabel#Hint {{ color: {TEXT_MUTED}; font-size: 11px; }}
QLabel[state="ok"] {{ color: {OK}; }}
QLabel[state="err"] {{ color: {ERR}; }}
QLabel[state="warn"] {{ color: {WARN}; }}

/* ===========================================================
   URL pill + line edits
   =========================================================== */
QFrame#UrlPill {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 12px;
}}
QFrame#UrlPill[focused="true"] {{ border-color: {ACCENT}; }}

QLineEdit {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 7px 10px 9px 10px;
    min-height: 22px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}

QLineEdit#UrlEntry {{
    background: transparent;
    border: none;
    padding: 8px 4px 10px 4px;
    min-height: 22px;
    font-size: 13px;
}}
QLineEdit#UrlEntry:focus {{ border: none; }}

QLineEdit#SearchEntry {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 7px 12px 9px 12px;
    min-height: 22px;
}}

/* ===========================================================
   Buttons
   ===========================================================
   Sizing rule: don't pin a fixed height in Python. Use QSS min-height
   + generous horizontal padding so Arabic glyphs (which run ~10-15%
   wider than Latin) get the room they need without clipping. Bold
   weight comes from the Thmanyah Sans family. */
QPushButton {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 18px;
    padding: 6px 18px 8px 18px;
    min-height: 24px;
    color: {TEXT};
    font-weight: 600;
}}
QPushButton:hover  {{ background: {SEC_HOVER}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; }}

/* Primary */
QPushButton[role="primary"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    padding: 7px 22px 9px 22px;
    min-height: 24px;
    border-radius: 20px;
    font-weight: 700;
}}
QPushButton[role="primary"]:hover {{ background: {ACCENT_HOV}; border-color: {ACCENT_HOV}; }}
QPushButton[role="primary"]:pressed {{ background: {ACCENT}; }}

/* Secondary (default) — already styled above */
QPushButton[role="secondary"] {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    color: {TEXT};
}}

/* Danger label colour */
QPushButton[role="danger"] {{
    color: {ERR};
}}

/* Icon-only round button (settings/account in top bar) */
QPushButton[role="icon"] {{
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    border-radius: 22px;
    font-size: 16px;
    padding: 0;
}}

/* Kebab + ✕ in row action area */
QPushButton[role="kebab"] {{
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    font-size: 15px;
    padding: 0;
    font-weight: 700;
}}
QPushButton[role="kebabDanger"] {{
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    font-size: 13px;
    padding: 0;
    font-weight: 700;
    background: transparent;
    color: {ERR};
    border: 1px solid {INPUT_BORDER};
}}
QPushButton[role="kebabDanger"]:hover {{ background: {SEC_HOVER}; }}

/* Tab-style pushbutton (segmented group) */
QPushButton[role="tab"] {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    color: {TEXT};
    border-radius: 10px;
    padding: 6px 20px 8px 20px;
    min-height: 22px;
}}
QPushButton[role="tab"]:hover {{ background: {SEC_HOVER}; }}
QPushButton[role="tabActive"] {{
    background: {ACCENT_TINT};
    border: 1px solid {ACCENT_TINT_BORDER};
    color: {TEXT};
    border-radius: 10px;
    padding: 6px 20px 8px 20px;
    min-height: 22px;
    font-weight: 700;
}}

/* Inline badge labels */
QLabel[role="badge"] {{
    background: {ACCENT_TINT};
    border: 1px solid {ACCENT_TINT_BORDER};
    color: {TEXT};
    border-radius: 6px;
    padding: 2px 8px 3px 8px;
    font-size: 10px;
    font-weight: 700;
}}

/* ===========================================================
   ComboBox
   =========================================================== */
QComboBox {{
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 7px 12px 9px 12px;
    min-height: 22px;
    color: {TEXT};
}}
QComboBox:hover {{ background: {SEC_HOVER}; }}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    color: {TEXT};
    selection-background-color: {SEC_HOVER};
    selection-color: {TEXT};
    outline: 0;
    padding: 4px;
}}

/* ===========================================================
   Progress bar
   =========================================================== */
QProgressBar {{
    background: {INPUT_BG};
    border: none;
    border-radius: 2px;
    min-height: 4px;
    max-height: 4px;
    text-align: center;
    color: transparent;  /* hide the percent text */
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ===========================================================
   Checkbox
   =========================================================== */
QCheckBox {{
    background: transparent;
    color: {TEXT_DIM};
    spacing: 8px;
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

/* ===========================================================
   Switch — implemented as QCheckBox[role="switch"]
   =========================================================== */
QCheckBox[role="switch"]::indicator {{
    width: 34px;
    height: 18px;
    border-radius: 9px;
    background: {INPUT_BG};
    border: 1px solid {INPUT_BORDER};
}}
QCheckBox[role="switch"]::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}

/* ===========================================================
   Scroll area
   =========================================================== */
QScrollArea {{ background: transparent; border: 0; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_HI};
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_HI};
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ===========================================================
   Menus
   =========================================================== */
QMenu {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    color: {TEXT};
    padding: 4px;
    border-radius: 8px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {SEC_HOVER};
    color: {TEXT};
}}
QMenu::item:disabled {{ color: {TEXT_FAINT}; }}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 6px;
}}

/* ===========================================================
   Dialogs
   =========================================================== */
QDialog {{ background: {APP_BG}; }}
QDialog QLabel {{ background: transparent; }}

/* ===========================================================
   Tooltips
   =========================================================== */
QToolTip {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px 8px;
    border-radius: 6px;
}}
"""
