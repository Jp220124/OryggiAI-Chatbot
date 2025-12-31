; OryggiAI Gateway Agent - Inno Setup Installer Script
; This creates a professional Windows installer
;
; Requirements:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - Built executable from PyInstaller (dist/OryggiAI-Gateway.exe)
;
; Build:
;   1. Run build_exe.py to create the executable
;   2. Open this file in Inno Setup Compiler
;   3. Click Build > Compile
;
; Output: Output/OryggiAI-Gateway-Setup.exe

#define MyAppName "OryggiAI Gateway Agent"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "OryggiAI"
#define MyAppURL "https://oryggi.ai"
#define MyAppExeName "OryggiAI-Gateway.exe"

[Setup]
; Basic info
AppId={{B7D8A9E1-4F2C-4A5B-9C3D-6E8F0A1B2C3D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/support
AppUpdatesURL={#MyAppURL}/downloads

; Install directories
DefaultDirName={autopf}\OryggiAI\Gateway
DefaultGroupName=OryggiAI
DisableProgramGroupPage=yes

; Output
OutputDir=Output
OutputBaseFilename=OryggiAI-Gateway-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Permissions
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Visual
WizardStyle=modern
WizardSizePercent=120
WindowVisible=no

; Signing (uncomment and configure for production)
; SignTool=signtool sign /f "certificate.pfx" /p "password" /t http://timestamp.digicert.com $f

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start automatically with Windows"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
; Main executable
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Icon (if exists)
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Startup folder (auto-start with Windows)
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--minimized"; Tasks: startupicon

[Run]
; Launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop any running instance before uninstall
Filename: "taskkill"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden

[UninstallDelete]
; Clean up config and logs
Type: filesandordirs; Name: "{commonappdata}\OryggiAI"
Type: dirifempty; Name: "{app}"

[Code]
// Pascal Script for custom installer behavior

var
  TokenPage: TInputQueryWizardPage;
  DatabasePage: TInputOptionWizardPage;
  TokenValue: String;
  DatabaseValue: String;

// Check if a previous version is running
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('tasklist', '/FI "IMAGENAME eq OryggiAI-Gateway.exe" /NH', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

// Stop running instance
procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec('taskkill', '/F /IM OryggiAI-Gateway.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
end;

procedure InitializeWizard();
begin
  // Create Token input page
  TokenPage := CreateInputQueryPage(wpWelcome,
    'Gateway Token',
    'Enter your OryggiAI Gateway Token',
    'Paste the token from your OryggiAI dashboard. If you don''t have one, you can get it from the Databases page in your tenant portal.');
  TokenPage.Add('Gateway Token:', False);

  // Pre-fill token from command line if provided
  TokenValue := ExpandConstant('{param:token|}');
  if TokenValue <> '' then
    TokenPage.Values[0] := TokenValue;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  // Validate token on token page
  if CurPageID = TokenPage.ID then
  begin
    TokenValue := TokenPage.Values[0];
    if TokenValue = '' then
    begin
      MsgBox('Please enter your Gateway Token.', mbError, MB_OK);
      Result := False;
    end
    else if Pos('gw_', TokenValue) <> 1 then
    begin
      MsgBox('Invalid token format. Token should start with "gw_"', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: String;
  ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Save token to config file for the app to read
    ConfigFile := ExpandConstant('{commonappdata}\OryggiAI\gateway-token.txt');
    ForceDirectories(ExtractFilePath(ConfigFile));

    TokenValue := TokenPage.Values[0];
    if TokenValue <> '' then
    begin
      SaveStringToFile(ConfigFile, TokenValue, False);
    end;
  end;
end;

// Prevent installation if app is running
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsAppRunning() then
  begin
    if MsgBox('OryggiAI Gateway Agent is currently running. It will be stopped to continue installation. Continue?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      StopRunningApp();
    end
    else
    begin
      Result := 'Please close OryggiAI Gateway Agent before installing.';
    end;
  end;
end;
