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
Compression=lzma2/ultra
SolidCompression=yes
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

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
