; installer.iss
; Inno Setup script for Bambu Dashboard
;
; Requirements:
;   - Inno Setup 6.x from https://jrsoftware.org/isdl.php
;   - Run build.ps1 first to produce dist\BambuDashboard.exe
;
; Open this file with Inno Setup Compiler and press F9 (Compile)
; Output: dist\BambuDashboard_Setup.exe

#define AppName      "Bambu Dashboard"
#define AppVersion   "1.3.1"
#define AppPublisher "Bambu Dashboard"
#define AppExeName   "BambuDashboard.exe"
#define AppGUID      "{{B56C71D2-8A2D-4B9F-8408-A9369C9588C0}"

[Setup]
AppId={#AppGUID}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com
AppSupportURL=https://github.com
AppUpdatesURL=https://github.com

; Install per-user (no admin required) into LocalAppData
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

; Build output
OutputDir=dist
OutputBaseFilename=BambuDashboard_Setup_{#AppVersion}

; Appearance
SetupIconFile=logo2.ico
WizardStyle=modern
WizardSizePercent=110
WizardResizable=no

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Behaviour
CloseApplications=force
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.WelcomeLabel1=Welcome to the {#AppName} Setup Wizard
english.WelcomeLabel2=This will install {#AppName} {#AppVersion} on your computer.%n%nBambu Dashboard is a personal monitoring tool for Bambu Lab printers. It connects directly to your Bambu Lab account — no third-party servers involved.%n%nClick Next to continue.
english.FinishedLabel=Setup has finished installing {#AppName} on your computer.%n%nThe application will ask for your Bambu Lab account credentials on first launch. Your login token is stored privately in:%n  %%APPDATA%%\BambuDashboard\%n%nClick Finish to exit.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Main executable (single-file build from PyInstaller)
Source: "dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Application icon (used by shortcuts)
Source: "logo2.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo2.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional)
Name: "{autodesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo2.ico"; Tasks: desktopicon

[Run]
; Launch after install
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the installation folder entirely (exe + icon)
Type: filesandordirs; Name: "{app}"
; Remove user config from Roaming AppData
; NOTE: we ask the user before deleting their config (see [Code] below)

[Registry]
; Remove any "Start with Windows" autorun entry on uninstall
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#AppName}"; Flags: deletevalue uninsdeletevalue

[Code]

// ── Helpers ─────────────────────────────────────────────────────────────────

function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := ExpandConstant('Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppGUID}_is1');
  sUnInstallString := '';
  if not RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

// ── Setup init: handle existing installation ─────────────────────────────────

function InitializeSetup(): Boolean;
var
  UninstallStr: String;
  ResultCode:   Integer;
  Answer:       Integer;
begin
  Result := True;

  if IsUpgrade() then
  begin
    Answer := MsgBox(
      '{#AppName} is already installed on this computer.' + #13#10 + #13#10 +
      'Click Yes to upgrade to version {#AppVersion}.' + #13#10 +
      'Click No  to uninstall the current version and exit.' + #13#10 +
      'Click Cancel to abort.',
      mbConfirmation, MB_YESNOCANCEL
    );

    if Answer = IDCANCEL then
    begin
      Result := False;
      Exit;
    end;

    UninstallStr := RemoveQuotes(GetUninstallString());

    if Answer = IDNO then
    begin
      // Silent uninstall then exit
      Exec(UninstallStr, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
      Result := False;
      Exit;
    end;

    // IDYES → silent uninstall then continue with fresh install
    Exec(UninstallStr, '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
  end;
end;

// ── Uninstall: optionally remove user config ──────────────────────────────────

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigDir: String;
  Answer:    Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    ConfigDir := ExpandConstant('{userappdata}\{#AppName}');
    if DirExists(ConfigDir) then
    begin
      Answer := MsgBox(
        'Do you also want to remove your personal settings?' + #13#10 +
        '(login token, printer list, print history)' + #13#10 + #13#10 +
        ConfigDir + #13#10 + #13#10 +
        'Click Yes to delete everything, No to keep your settings.',
        mbConfirmation, MB_YESNO
      );
      if Answer = IDYES then
        DelTree(ConfigDir, True, True, True);
    end;
  end;
end;
