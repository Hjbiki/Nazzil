Drop ThmanyahSans .ttf / .otf files here.

Recommended set:
  ThmanyahSans-Medium.ttf     — regular text
  ThmanyahSans-Bold.ttf       — headings & buttons

At startup, every .ttf / .otf file in this folder is auto-loaded via
QFontDatabase.addApplicationFont(). The first family name reported by
the loaded fonts becomes the app's default font. The QSS in
ui/theme.py uses "Thmanyah Sans" with safe fallbacks
(Segoe UI / Tahoma / Noto Sans Arabic), so if no font is dropped here
the app still looks right — just without the custom face.
