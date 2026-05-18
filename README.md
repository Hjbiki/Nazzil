<div align="center">

# ███╗   ██╗ █████╗ ███████╗███████╗██╗██╗
# ████╗  ██║██╔══██╗╚══███╔╝╚══███╔╝██║██║
# ██╔██╗ ██║███████║  ███╔╝   ███╔╝ ██║██║
# ██║╚██╗██║██╔══██║ ███╔╝   ███╔╝  ██║██║
# ██║ ╚████║██║  ██║███████╗███████╗██║███████╗
# ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝╚══════╝

**محمّل فيديوهات لسطح المكتب — Desktop Video Downloader**

[Download Latest Release](https://github.com/Hjbiki/Nazzil/releases/latest)

---

</div>

<div dir="rtl" align="right">

## نزّل

محمّل فيديوهات مجاني ومفتوح المصدر لسطح المكتب. الصق الرابط، اختر الجودة، وحمّل. يدعم يوتيوب وأكثر من 1800 موقع آخر.

---

### وش يسوي؟

نزّل تطبيق ويندوز مبني بـ Python و Qt، يستخدم yt-dlp للتحميل و ffmpeg للدمج والتحويل. صُمّم بأسلوب Linear الداكن مع واجهة نظيفة ومرتبة.

### المميزات

**التحميل**

- تحميل فيديو بجودة تصل إلى 4K (MP4)
- تحميل صوت بجودات 128 / 192 / 320 kbps (MP3) مع غلاف الألبوم والبيانات الوصفية
- تحميلات متعددة بالتوازي، كل واحد بشريط تقدم مستقل
- دعم الكوكيز لفيديوهات الأعضاء والمحتوى المقيّد بالعمر (Firefox موصى به)
- دعم قوائم التشغيل مع إمكانية اختيار فيديوهات محددة
- إعادة المحاولة تلقائياً عند الفشل (حتى 5 مرات)
- تسريع التحميل عبر aria2c (اختياري)
- كشف التكرار وحل تعارض أسماء الملفات

**الواجهة**

- نافذة بدون إطار مع شريط عنوان مخصص وزوايا مدوّرة
- بحث وفرز وتصفية التحميلات (الكل / فيديو / صوت)
- ثمانية خيارات فرز: تاريخ الإضافة، الاسم، الحجم، المدة (تصاعدي وتنازلي)
- صفحات (15 / 30 / 50 لكل صفحة)
- وضع مضغوط للصفوف يعرض عدد أكبر من التحميلات
- مراقبة الحافظة: ينسخ الرابط تلقائياً ويبدأ الجلب
- اختصارات لوحة مفاتيح شاملة
- عارض صور مدمج للصور المصغرة مع تكبير وتدوير
- تصغير إلى منطقة الإشعارات مع تنبيه عند اكتمال جميع التحميلات

**اللغات**

- عربي وإنجليزي مع تبديل فوري بدون إعادة تشغيل
- دعم كامل للاتجاه من اليمين لليسار

**كشف المصدر**

- يكتشف الموقع تلقائياً ويعرضه بلون العلامة التجارية (يوتيوب، X، إنستغرام، فيميو، تويتش، تيك توك، ساوندكلاود، وغيرها)
- أي موقع غير معروف يُعرض باسم النطاق

**التحديث**

- يفحص التحديثات من GitHub Releases تلقائياً
- يعرض إشعار "تحديث متاح" في الشريط السفلي
- يحدّث نفسه بنقرة واحدة

### التثبيت

حمّل أحدث نسخة من صفحة [Releases](https://github.com/Hjbiki/Nazzil/releases/latest):

- **NazzilSetup.exe** — مثبّت كامل (موصى به)
- **Nazzil.exe** — نسخة محمولة بدون تثبيت

### المتطلبات

لا يوجد. التطبيق يتضمن كل شيء مطلوب بما فيها ffmpeg.

لتفعيل التحميل المتسارع، ثبّت [aria2](https://aria2.github.io/) وتأكد من وجوده في PATH.

### البناء من المصدر

</div>

```bash
git clone https://github.com/Hjbiki/Nazzil.git
cd Nazzil
pip install -r requirements.txt
python main.py
```

<div dir="rtl" align="right">

للبناء كملف تنفيذي:

</div>

```bash
build.bat
```

<div dir="rtl" align="right">

### اختصارات لوحة المفاتيح

| الاختصار | الوظيفة |
|---|---|
| Ctrl+V | لصق الرابط وبدء الجلب |
| Ctrl+W | إغلاق النافذة |
| Ctrl+M | تصغير |
| F11 | ملء الشاشة |
| Ctrl+, | الإعدادات |
| Ctrl+L | التركيز على حقل الرابط |
| Ctrl+F | التركيز على البحث |
| Delete | حذف الصف المحدد |
| Space | إيقاف / استئناف التحميل |

### المطوّر

عناد عسكر

- [creators.sa/hibiki](https://creators.sa/hibiki)
- [tip.dokan.sa/hibiki](https://tip.dokan.sa/hibiki)

### الرخصة

مفتوح المصدر. راجع ملف LICENSE للتفاصيل.

---

</div>

## Nazzil

A free, open-source desktop video downloader. Paste a URL, pick your quality, download. Supports YouTube and 1800+ other sites.

---

### What is it?

Nazzil is a Windows desktop app built with Python and Qt. It uses yt-dlp for downloading and ffmpeg for merging and conversion. The interface follows a Linear-inspired dark design with a clean, structured layout.

### Features

**Downloading**

- Video downloads up to 4K (MP4)
- Audio extraction at 128 / 192 / 320 kbps (MP3) with embedded cover art and metadata
- Unlimited parallel downloads, each with its own progress bar
- Cookie support for members-only and age-restricted content (Firefox recommended)
- Playlist support with per-video selection
- Auto-retry on failure (up to 5 attempts)
- Optional aria2c acceleration for faster multi-connection downloads
- Duplicate detection and file-name conflict resolution (replace / rename / cancel)

**Interface**

- Frameless window with custom title bar and rounded corners
- Search, sort, and filter downloads (All / Video / Audio tabs)
- Eight sort options: date added, name, size, duration (ascending and descending)
- Pagination (15 / 30 / 50 per page)
- Compact mode toggle for denser row display
- Clipboard watcher: auto-fills and fetches when a video URL is copied
- Full keyboard shortcut support
- Built-in image viewer for thumbnails with zoom, rotate, and fullscreen
- Minimize to system tray with notification when all downloads complete

**Languages**

- Arabic and English with instant live switching (no restart needed)
- Full right-to-left layout support

**Source detection**

- Automatically identifies the source site and displays it with brand colors (YouTube, X, Instagram, Vimeo, Twitch, TikTok, SoundCloud, and more)
- Unknown sites fall back to displaying the domain name

**Updates**

- Checks GitHub Releases automatically on launch
- Shows an "Update available" indicator in the footer
- One-click self-update

### Installation

Download the latest version from [Releases](https://github.com/Hjbiki/Nazzil/releases/latest):

- **NazzilSetup.exe** — Full installer (recommended)
- **Nazzil.exe** — Portable, no installation needed

### Requirements

None. The app bundles everything it needs, including ffmpeg.

For faster downloads, install [aria2](https://aria2.github.io/) and make sure it's on your PATH.

### Build from source

```bash
git clone https://github.com/Hjbiki/Nazzil.git
cd Nazzil
pip install -r requirements.txt
python main.py
```

To build as a standalone executable:

```bash
build.bat
```

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+V | Paste URL and auto-fetch |
| Ctrl+W | Close window |
| Ctrl+M | Minimize |
| F11 | Toggle fullscreen |
| Ctrl+, | Open settings |
| Ctrl+L | Focus URL input |
| Ctrl+F | Focus search |
| Delete | Remove selected row |
| Space | Pause / resume download |

### Author

Anad Askar

- [creators.sa/hibiki](https://creators.sa/hibiki)
- [tip.dokan.sa/hibiki](https://tip.dokan.sa/hibiki)

### License

Open source. See the LICENSE file for details.
