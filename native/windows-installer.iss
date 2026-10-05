#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef MyAppRevision
  #define MyAppRevision "0"
#endif

#define MyAppName "MTA Audio Editor"
#define MyAppPublisher "Alessandro De Salvo"
#define MyAppExeName "MTA Audio Editor.exe"
#ifndef SourceDir
  #define SourceDir "..\\dist\\MTA Audio Editor"
#endif
#ifndef OutputDir
  #define OutputDir "..\\dist-installer"
#endif

[Setup]
AppId={{8415208D-8D3A-4DFC-A143-C567994A3D67}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\MTA Audio Editor
DefaultGroupName=MTA Audio Editor
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=MTA-Audio-Editor-{#MyAppVersion}-r{#MyAppRevision}-Windows-x64-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icons\mta-audio-editor.ico
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=yes

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\MTA Audio Editor"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\MTA Audio Editor"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crea un collegamento sul desktop"; GroupDescription: "Collegamenti aggiuntivi:"

[Registry]
Root: HKCU; Subkey: "Software\Classes\.maeproj"; ValueType: string; ValueName: ""; ValueData: "MTA.AudioEditor.Project"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\MTA.AudioEditor.Project"; ValueType: string; ValueName: ""; ValueData: "MTA Audio Editor Project"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\MTA.AudioEditor.Project\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\MTA.AudioEditor.Project\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\MTA.AudioEditor.Project"; ValueType: string; ValueName: "Content Type"; ValueData: "application/vnd.mta-audio-editor.project"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia MTA Audio Editor"; Flags: nowait postinstall skipifsilent
