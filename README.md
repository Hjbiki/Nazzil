<div align="center">

# Nazzil — نزّل

**A clean, modern desktop video downloader for Windows.**
**محمّل فيديو حديث وأنيق لسطح المكتب على ويندوز.**

Version 1.5.0 · Built with Python + PySide6 + yt-dlp

</div>

---

## English

**Nazzil** is a desktop downloader for YouTube and 1800+ other sites
(X/Twitter, Instagram, TikTok, Facebook, Vimeo, Twitch, Reddit, and more),
with a Linear-inspired dark/light UI and full Arabic (RTL) support.

### Download

**Recommended: `NazzilSetup.exe`** — the installer bundles ffmpeg, ffprobe
and aria2c inside it, so Nazzil works **100% offline right after install**.
No internet needed after install, and nothing extra to install yourself.
A small portable `Nazzil.exe` is also available; it fetches those tools
silently on first run (one-time, requires internet that once).

### Highlights

- **Zero install — nothing extra to set up.** The installer ships ffmpeg,
  ffprobe and aria2c bundled, so everything works offline immediately. The
  portable build fetches them silently on first launch as a fallback. You
  never install any external tool yourself and never see an
  "install ffmpeg" message.
- **Any site, not just YouTube.** Paste a link from X, Instagram, TikTok,
  Vimeo, Twitch, Reddit, Dailymotion, SoundCloud and more. The source is
  detected automatically and shown with a brand-coloured tag.
- **Formats made clear.** Choose **Video + Audio (MP4)** up to 4K, or
  **Audio only (MP3)**. Default audio quality is **320 kbps** (128 / 192 /
  320 selectable).
- **Per-row controls.** Completed rows get a **▶ Play** button, **Show in
  folder**, and a **⋯ More** menu (Retry, Copy link, Rename, Remove,
  Delete file). Duration is shown on the info line — never over the
  thumbnail.
- **Light & Dark themes.** Switch instantly from Settings — no restart,
  just like the language switch.
- **Update check that actually tells you.** "Check for updates" shows a
  clear result: a new version is available (with an Update button), you're
  on the latest version, or the check failed.
- **Single instance.** Launching Nazzil again just brings the running
  window to the front instead of opening a second copy.
- **Keyboard shortcuts help.** Press **F1** (or open it from Settings) for
  a full reference card.
- **System tray.** Close to tray, get notified when a batch finishes.
- **Live language switch** (العربية / English) with full RTL mirroring,
  unlimited parallel downloads, playlists, clipboard auto-fill, search /
  sort / filter, pagination, and session persistence.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl + V` | Paste URL & fetch |
| `Ctrl + L` | Focus the URL field |
| `Ctrl + F` | Focus the search field |
| `Ctrl + ,` | Open settings |
| `Ctrl + M` | Minimize to tray |
| `F11` | Maximize / restore |
| `Ctrl + W` | Close to tray |
| `F1` | Show keyboard shortcuts |

### Run from source

```cmd
pip install -r requirements.txt
python main.py
```

### Build

```cmd
build.bat        REM fetches bundled tools, then PyInstaller → dist\Nazzil.exe
```

---

## العربية

**نزّل** هو محمّل فيديو لسطح المكتب يدعم يوتيوب وأكثر من 1800 موقع آخر
(إكس/تويتر، إنستغرام، تيك توك، فيسبوك، Vimeo، Twitch، Reddit، وغيرها)،
بواجهة داكنة/فاتحة مستوحاة من Linear ودعم كامل للعربية (من اليمين لليسار).

### التحميل

**المُوصى به: `NazzilSetup.exe`** — المثبّت يضمّن ffmpeg و ffprobe و aria2c
بداخله، فيعمل نزّل **بدون إنترنت تمامًا فور التثبيت**. لا حاجة لإنترنت بعد
التثبيت، ولا أدوات إضافية تثبّتها بنفسك. تتوفّر أيضًا نسخة محمولة صغيرة
`Nazzil.exe` تجلب هذه الأدوات بصمت عند أول تشغيل (مرة واحدة، تحتاج إنترنت
تلك المرة فقط).

### أبرز المزايا

- **صفر تثبيت — لا حاجة لإعداد أي شيء.** المثبّت يضمّن ffmpeg و ffprobe و
  aria2c، فيعمل كل شيء بدون إنترنت فورًا. والنسخة المحمولة تجلبها بصمت عند
  أول تشغيل كحل احتياطي. لن تثبّت أي أداة خارجية بنفسك، ولن ترى رسالة
  "ثبّت ffmpeg".
- **أي موقع وليس يوتيوب فقط.** الصق رابطًا من إكس أو إنستغرام أو تيك توك أو
  Vimeo أو Twitch أو Reddit أو Dailymotion أو SoundCloud وغيرها. يُكتشف
  المصدر تلقائيًا ويظهر بعلامة ملوّنة بهوية الموقع.
- **صيغ واضحة.** اختر **فيديو + صوت (MP4)** حتى دقة 4K، أو **صوت فقط (بدون
  فيديو) (MP3)**. جودة الصوت الافتراضية **320 kbps** (مع خيارات 128 / 192 /
  320).
- **تحكّم لكل عنصر.** الصفوف المكتملة فيها زر **▶ تشغيل** و**إظهار في
  المجلد** وقائمة **⋯ المزيد** (إعادة المحاولة، نسخ الرابط، إعادة تسمية،
  إزالة، حذف الملف). تظهر المدة في سطر المعلومات — وليست فوق الصورة المصغّرة.
- **مظهر فاتح وداكن.** بدّل فورًا من الإعدادات — بدون إعادة تشغيل، تمامًا
  مثل تبديل اللغة.
- **فحص تحديث يخبرك بالنتيجة فعلًا.** "تحقّق من التحديثات" يعرض نتيجة واضحة:
  يتوفّر إصدار جديد (مع زر تحديث)، أو أنت على آخر إصدار، أو فشل التحقق.
- **نسخة واحدة فقط.** فتح نزّل مرة أخرى يُظهر النافذة الشغّالة بدل فتح نسخة
  ثانية.
- **مساعدة اختصارات لوحة المفاتيح.** اضغط **F1** (أو افتحها من الإعدادات)
  لعرض بطاقة الاختصارات كاملة.
- **شريط المهام (Tray).** الإغلاق إلى شريط المهام، وتنبيه عند انتهاء
  مجموعة التحميلات.
- **تبديل لغة مباشر** (العربية / English) مع انعكاس كامل للاتجاه، وتحميلات
  متوازية بلا حد، وقوائم تشغيل، وتعبئة تلقائية من الحافظة، وبحث/ترتيب/تصفية،
  وترقيم صفحات، وحفظ الجلسة.

### اختصارات لوحة المفاتيح

| الاختصار | الإجراء |
|---|---|
| `Ctrl + V` | لصق الرابط والجلب |
| `Ctrl + L` | التركيز على حقل الرابط |
| `Ctrl + F` | التركيز على حقل البحث |
| `Ctrl + ,` | فتح الإعدادات |
| `Ctrl + M` | التصغير إلى شريط المهام |
| `F11` | تكبير / استعادة |
| `Ctrl + W` | الإغلاق إلى شريط المهام |
| `F1` | عرض اختصارات لوحة المفاتيح |

### التشغيل من المصدر

```cmd
pip install -r requirements.txt
python main.py
```

### البناء

```cmd
build.bat        REM يجلب الأدوات المُضمّنة ثم PyInstaller → dist\Nazzil.exe
```

---

<div align="center">

تطوير **عناد عسكر** — Developed by **Anad Askar**
[الموقع / Website](https://creators.sa/hibiki) ·
[ادعمني / Support](https://tip.dokan.sa/hibiki)

</div>
