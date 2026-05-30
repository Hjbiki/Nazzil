# Nazzil — Project Overview / نظرة عامة على المشروع

> A quick, code-free reference so a fresh assistant (or developer) can
> understand the whole project fast. For deep history see `CLAUDE.md`;
> for the user-facing pitch see `README.md`.
>
> مرجع سريع بلا كود ليفهم أي مساعد/مطوّر المشروع كاملًا بسرعة. للتاريخ
> التفصيلي راجع `CLAUDE.md`، وللوصف الموجّه للمستخدم راجع `README.md`.

---

## 1. Overview / نظرة عامة

**EN —** Nazzil (نزّل) is a **desktop video downloader for Windows 10/11**.
It downloads from YouTube and 1800+ other sites (X/Twitter, Instagram,
TikTok, Vimeo, Twitch, Reddit, Dailymotion, SoundCloud, …). Stack:
**Python 3.11, PySide6 (Qt 6), yt-dlp**, with **ffmpeg + ffprobe + aria2c**
bundled. UI is a Linear-inspired frameless dark/light theme with full
Arabic (RTL) support. Default language: Arabic.

**AR —** نزّل تطبيق **محمّل فيديو لسطح المكتب على ويندوز 10/11**. يحمّل من
يوتيوب وأكثر من 1800 موقع (إكس، إنستغرام، تيك توك، Vimeo، Twitch، Reddit،
Dailymotion، SoundCloud…). التقنيات: **Python 3.11، PySide6 (Qt 6)،
yt-dlp**، مع تضمين **ffmpeg + ffprobe + aria2c**. الواجهة بلا إطار بنمط
Linear داكن/فاتح ودعم كامل للعربية (RTL). اللغة الافتراضية: العربية.

- Repo: `Hjbiki/Nazzil` · Developer: Anad Askar (عناد عسكر)
- Git repo root = `nazzil/` (the outer `youtube-downloader/` folder only
  holds convenience batch scripts).

## 2. Current version / الإصدار الحالي

**1.5.0** — single source of truth is the `VERSION` file (read by
`config.APP_VERSION` at runtime, and by `nazzil.spec` / `installer.iss`
at build time). Bump with `python update_version.py 1.6.0`.

## 3. File structure / بنية الملفات

**Root modules / وحدات الجذر:**
| File | Responsibility |
|---|---|
| `main.py` | Entry point: single-instance gate, fonts, language, theme, builds `App`, runs Qt loop. |
| `config.py` | `APP_VERSION`, paths, URL regexes (`URL_RE`, `MEDIA_URL_RE`, `YT_*`), cookie modes, load/save config JSON. |
| `downloader.py` | `DownloadItem(QObject)` — one yt-dlp download per thread; passes `ffmpeg_location` + bundled aria2c; resolves real on-disk file size; persistence (`to_dict`/`from_dict`). |
| `binaries.py` | Resolves ffmpeg/ffprobe/aria2c paths; silent background fetch of any missing tool. **No user install ever.** |
| `single_instance.py` | `QLocalServer` guard — 2nd launch focuses the running window and exits. |
| `updater.py` | GitHub-releases self-update: `UpdateChecker`, `UpdateDownloader`, `launch_updater` (.bat swap). |
| `utils.py` | Pure helpers: human size, duration/ETA, error classification (i18n), filename sanitisation, open/reveal file. |
| `fonts.py` | Registers bundled Thmanyah Sans fonts at startup. |
| `fetch_binaries.py` | **Build-time** downloader → `assets/bin` (run by build.bat + CI; strips ffplay). |
| `generate_icon.py` | QPainter → PNG → ICO icon generator (headless). |
| `update_version.py` | CLI to rewrite the `VERSION` file. |

**`ui/` (all widgets):**
| File | Responsibility |
|---|---|
| `app.py` | `App(FramelessMainWindow)` — main window, fetch flow, downloads list, search/sort/filter, pagination, persistence, clipboard watch, tray, update flow, `set_language`/`set_theme`. |
| `theme.py` | `DARK`/`LIGHT` palettes + `build_qss` + `apply_theme(app, mode)` + `current()`; shadow recipes. |
| `dialogs.py` | `SettingsDialog`, `AccountDialog` (cookies), `AboutDialog`, `ShortcutsDialog`, `themed_message`, rename/conflict/duplicate/delete dialogs. |
| `download_row.py` | `DownloadRow` — one row (thumb, title, channel, source·format·duration·size, progress, error, action buttons); `KNOWN_SOURCES` brand tags. |
| `window_chrome.py` | Frameless window + WM_NCHITTEST (resize/snap), traffic-light controls, title bar, `FramelessDialog` shell. |
| `image_viewer.py` | `FramelessImageViewer` — zoom/rotate/pan/save thumbnail viewer. |
| `tray.py` | `Tray` wrapping `QSystemTrayIcon` (show/exit, batch-done notify). |
| `icons.py` | qtawesome (MDI6) icon wrapper (`NAMES` map). |

**Data / resources:**
| Path | Responsibility |
|---|---|
| `i18n/` | `Translator` + `en.json` / `ar.json` (202 keys each, must stay in parity). |
| `assets/` | `icon.png/ico`, `fonts/` (Thmanyah Sans), `bin/` (ffmpeg/ffprobe/aria2c — **git-ignored** `*.exe`). |
| `nazzil.spec` | PyInstaller one-file spec (does **not** embed the heavy binaries). |
| `installer.iss` | Inno Setup — ships the 3 tools to `{app}\assets\bin` → offline installer. |
| `build.bat` | Local build: fetch binaries → PyInstaller. |
| `.github/workflows/build.yml` | CI: on release → icon, fetch binaries, build exe, build installer, upload assets. |
| `requirements.txt` | PySide6, yt-dlp, Pillow, qtawesome. |

User files (outside repo): `~/.yt_downloader_config.json` (settings) and
`~/.yt_downloader_downloads.json` (session list).

## 4. Tool resolution / حل مسارات الأدوات

**EN —** `binaries.py` resolves each tool in this order, returning the
first that exists:
1. `<_MEIPASS>/assets/bin` — if embedded in the one-file exe (not the default).
2. `<exe_dir>/assets/bin` — where **NazzilSetup.exe** installs them (primary for installed users).
3. `<package>/assets/bin` — running from source / dev.
4. `%LOCALAPPDATA%/Nazzil/bin` — user cache (silent runtime download target).
5. system **PATH** — last-resort courtesy only.

If anything is missing, `ensure_binaries_async()` downloads it silently in
the background (ffmpeg = gyan.dev **essentials** build; aria2c 1.37.0).
**Principle: the user is NEVER asked to install anything — no ffmpeg, no
aria2c, no winget, no PATH setup.** ffmpeg dir is handed to yt-dlp via
`ffmpeg_location`.

**AR —** `binaries.py` يحل كل أداة بالترتيب أعلاه ويعيد أول مسار موجود:
مُضمّن في الـexe ← بجانب الـexe المُثبَّت (`{app}\assets\bin`، الأساسي
للمُثبَّت) ← مجلد المشروع (للمصدر) ← كاش المستخدم ← PATH (ملاذ أخير). أي
أداة ناقصة تُجلب بصمت في الخلفية. **المبدأ: لا يُطلب من المستخدم تثبيت أي
شيء إطلاقًا — لا ffmpeg، لا aria2c، لا winget، لا PATH.**

## 5. Distribution / طرق التوزيع

| Channel | Notes |
|---|---|
| **`NazzilSetup.exe`** (Inno Setup) | **Recommended.** Bundles ffmpeg + ffprobe + aria2c inside the installer → works **100% offline right after install**. |
| `Nazzil.exe` (portable, one-file) | Lean — binaries NOT embedded. Fetches them silently on first run (one-time internet) as a fallback. |
| `start.bat` → `python nazzil\main.py` | **Developer only** — run from source. Uses the same binary resolution (finds `assets/bin`). |

## 6. i18n / التعدّد اللغوي

- Two bundles: `i18n/en.json` and `i18n/ar.json` — **202 keys each, must be
  identical key sets (zero diff)**. English is the fallback.
- Add a key: add it to **both** files; access via `t("key", **kwargs)`
  (does `str.format`). Verify parity:
  `set(json.load(open('i18n/en.json'))) == set(json.load(open('i18n/ar.json')))`.
- Live switch via `App.set_language(code)` → reloads bundle, flips layout
  direction (RTL for Arabic), calls every widget's `retranslate()`.
- Arabic alignment uses `Qt.AlignLeading`; eliding is unicode-aware.

## 7. Themes / الثيمات

- `ui/theme.py`: `DARK` and `LIGHT` palette dicts (same keys), one QSS
  template rendered by `build_qss(palette)`.
- `apply_theme(app, mode)` swaps the live stylesheet **and** rebinds the
  module colour constants so widgets built afterwards use the active
  palette. `current()` returns the active palette for inline styles.
- Live switch via `App.set_theme(mode)` (no restart, like the language
  switch). Saved in config key `theme` (`"dark"`/`"light"`, default dark).

## 8. Features / الميزات (quick list)

Paste/auto-fetch any URL · format & quality (MP4 ≤4K, MP3 128/192/**320**)
· unlimited parallel downloads · playlists with checklist · cookies (file /
Firefox / Brave / Chrome / Edge) + test login · MP3 cover-art + metadata ·
clipboard watch · session persistence (interrupted on restart) · conflict &
duplicate handling · per-row actions (▶ Play, Show in folder, Copy link,
Rename, Remove, Delete file) · brand source tags · search / sort / filter
tabs · pagination · system tray + batch-done notify · live language +
theme switch · self-update (GitHub) with clear result dialog ·
single-instance · keyboard-shortcuts help (F1) · image viewer for thumbs.

## 9. Key design decisions (do NOT reopen) / قرارات مهمة لا تُعاد

- **ffmpeg = gyan.dev *essentials* build (~97 MB/exe), NOT the 388 MB
  static GPL.** Ship only `ffmpeg.exe` + `ffprobe.exe` (no ffplay).
- **Installer bundles the binaries; the portable exe does NOT embed them**
  (keeps it lean) and relies on the silent first-run download.
- **The user is never told to install anything** (no ffmpeg/aria2c/winget
  messages anywhere). aria2c is **optional**: if absent, fall back silently
  to yt-dlp's default downloader; Settings shows only a passive indicator.
- **Default MP3 bitrate = 320 kbps.**
- **Single-instance**: a 2nd launch focuses the existing window.
- **Frameless window + `setMask` for rounded corners** (no acrylic /
  translucency — was tried and removed; do not reintroduce `transparency`).
- **Real completed file size comes from disk** (`size_on_disk`), never the
  progress hook's single-stream `size_bytes`.
- **Vector icons (qtawesome MDI6) only — never emoji as UI icons.**
- Title bar is permanently LTR (traffic lights stay left even in RTL).

## 10. Build & release / البناء والإصدار

- **Local:** `build.bat` → fetches binaries → `pyinstaller nazzil.spec` →
  `dist/Nazzil.exe`.
- **Release:** `release.bat` bumps the VERSION minor, commits, tags, and
  `gh release create`. The tag triggers `.github/workflows/build.yml`,
  which on Windows: installs deps, generates the icon, runs
  `fetch_binaries.py`, builds `dist/Nazzil.exe`, installs Inno Setup, builds
  `output/NazzilSetup.exe`, and uploads **both** to the GitHub release.
- **In-app auto-update:** `App.start_update_check()` queries the latest
  GitHub release; if newer and frozen, downloads the exe and swaps it via a
  small `.bat`; from source it opens the release page.

---

*Keep this file in sync when structure or decisions change. Detailed
session-by-session history lives in `CLAUDE.md`.*
