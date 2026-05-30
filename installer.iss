; Inno Setup script for Nazzil
; Build with:   iscc installer.iss
; Output:       output\NazzilSetup.exe
;
; Version is read DYNAMICALLY from the VERSION file (single source of truth).

#define AppName       "Nazzil"
#define AppPublisher  "Anad Askar"
#define AppExeName    "Nazzil.exe"

; --- Read version from VERSION file -----------------------------------------
#define VersionHandle FileOpen(AddBackslash(SourcePath) + "VERSION")
#define AppVersion    Trim(FileRead(VersionHandle))
#expr   FileClose(VersionHandle)
#undef  VersionHandle

[Setup]
; A stable AppId is what lets the installer detect existing installs and
; upgrade them in place. Never change this GUID.
AppId={{F7B8D2E5-3C0A-4E91-9A6E-2F1D7B3C5A88}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/Hjbiki/Nazzil
AppSupportURL=https://github.com/Hjbiki/Nazzil/issues
AppUpdatesURL=https://github.com/Hjbiki/Nazzil/releases

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=NazzilSetup
SetupIconFile=assets\icon.ico
; Strongest compression Inno Setup offers — shrinks the NazzilSetup.exe
; download as much as possible. This only affects the installer file size;
; the installed app is identical and just as fast after extraction.
Compression=lzma2/ultra64
SolidCompression=yes
; Run the LZMA compressor in a separate process so the large bundled
; binaries (ffmpeg/ffprobe ~190 MB combined) don't exhaust memory at the
; ultra64 dictionary size during the build.
LZMAUseSeparateProcess=yes
WizardStyle=modern

PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64

; --- Upgrade-in-place behaviour ---------------------------------------------
; If a previous install of the same AppId is present, install over it
; without making the user uninstall first. Close any running instance
; gracefully (CloseApplications) and relaunch it after install.
CloseApplications=yes
RestartApplications=yes
CloseApplicationsFilter=*.exe
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousLanguage=yes
UsePreviousSetupType=yes
UsePreviousTasks=yes

UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}.0
VersionInfoProductVersion={#AppVersion}.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "arabic";  MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Nazzil.exe";  DestDir: "{app}"; Flags: ignoreversion
Source: "assets\icon.ico";  DestDir: "{app}"; Flags: ignoreversion
; Bundled external tools — ffmpeg / ffprobe / aria2c. Shipped INSIDE the
; installer so the app works 100% offline right after install (no first-run
; download needed). `fetch_binaries.py` (run by build.bat / CI) populates
; assets\bin before ISCC runs. binaries._bundled_dirs() resolves them from
; {app}\assets\bin next to the installed Nazzil.exe.
Source: "assets\bin\ffmpeg.exe";  DestDir: "{app}\assets\bin"; Flags: ignoreversion
Source: "assets\bin\ffprobe.exe"; DestDir: "{app}\assets\bin"; Flags: ignoreversion
Source: "assets\bin\aria2c.exe";  DestDir: "{app}\assets\bin"; Flags: ignoreversion

[Icons]
; Primary Start-menu shortcut — its name carries BOTH the Arabic wordmark
; (with the shadda: نزّل) AND the English "Nazzil", so Windows Search finds
; the app whether the user types "نزّل" or "Nazzil".
Name: "{group}\نزّل Nazzil";          Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
; Extra shortcut WITHOUT the shadda ("نزل"). Windows Search compares
; diacritics literally, so a search for the plain "نزل" won't match "نزّل".
; This second shortcut (same exe, same icon) guarantees the app is found
; when typed without diacritics — how most people type.
Name: "{group}\نزل";                  Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
; Uninstall entry — name intentionally unchanged.
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; On uninstall, also remove Nazzil's OWN runtime-download cache (where the
; lean portable build may have silently fetched ffmpeg / aria2c). This is the
; ONLY thing cleaned outside {app}, and it is 100% app-owned — it never
; contains, points to, or affects any ffmpeg the user installed elsewhere.
; The default uninstall already removes everything under {app}. Nothing on
; the user's PATH, in System32, or in shared Program Files is ever touched.
Type: filesandordirs; Name: "{localappdata}\Nazzil"
