; Inno Setup script for the Safe Eyes Windows installer.
;
; Build (after producing dist/SafeEyes with PyInstaller):
;     ISCC.exe packaging\windows\installer.iss
; Produces packaging/windows/installer/SafeEyes-<version>-setup.exe
;
; Per-user install (no administrator rights required), matching Safe Eyes'
; per-user config (%APPDATA%\SafeEyes) and per-user autostart.

#define MyAppName "Safe Eyes"
#define MyAppVersion "3.5.1"
#define MyAppPublisher "Gobinath Loganathan"
#define MyAppURL "https://github.com/slgobinath/safeeyes"
#define MyAppExeName "SafeEyes.exe"

[Setup]
; A stable, unique AppId so upgrades replace the previous install in place.
AppId={{B8F3A2D6-5C4E-4E1B-9F2A-7E6C1D0A9B34}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\SafeEyes
DefaultGroupName=Safe Eyes
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=installer
OutputBaseFilename=SafeEyes-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install: no admin prompt, installs under %LOCALAPPDATA%\Programs.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Start Safe Eyes automatically when I log in"; GroupDescription: "Startup:"

[Files]
; The entire PyInstaller onedir output.
Source: "..\..\dist\SafeEyes\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Safe Eyes"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Safe Eyes"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Safe Eyes"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\Safe Eyes"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Safe Eyes}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Make sure a running instance is closed before files are removed.
Filename: "{app}\{#MyAppExeName}"; Parameters: "-q"; Flags: skipifdoesntexist runhidden; RunOnceId: "QuitSafeEyes"
