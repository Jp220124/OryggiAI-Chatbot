; OryggiAI Gateway Agent - Enhanced Inno Setup Installer v2.3
;
; Features:
;   - Auto database discovery with GUI dropdown
;   - CHOICE: Windows Authentication OR SQL Server Authentication
;   - SQL Auth = No service account headaches (runs as LocalSystem)
;   - SQL Connection verification BEFORE installing
;   - Token pre-fill from command line parameter
;   - NSSM-based service management for reliability
;   - Clean, professional UI
;
; Usage:
;   Normal:  OryggiAI-Gateway-Setup.exe
;   Silent (Windows Auth):  OryggiAI-Gateway-Setup.exe /VERYSILENT /token=gw_xxx /database=MyDB /authtype=windows /serviceuser=.\User /servicepass=Pass
;   Silent (SQL Auth):  OryggiAI-Gateway-Setup.exe /VERYSILENT /token=gw_xxx /database=MyDB /authtype=sql /sqluser=sa /sqlpass=Password123
;
; Build:
;   1. Run build_service.py to create OryggiGatewayService.exe
;   2. Ensure nssm.exe is in the project folder
;   3. Open this file in Inno Setup Compiler 6.x
;   4. Click Build > Compile
;
; Output: Output/OryggiAI-Gateway-Setup.exe

#define MyAppName "OryggiAI Gateway Agent"
#define MyAppVersion "2.3.0"
#define MyAppPublisher "OryggiAI"
#define MyAppURL "https://oryggi.ai"
#define MyAppServiceExe "OryggiGatewayService.exe"
#define MyServiceName "OryggiGatewayAgent"
#define MyServiceDisplayName "OryggiAI Gateway Agent"

[Setup]
; Unique App ID
AppId={{B7D8A9E1-4F2C-4A5B-9C3D-6E8F0A1B2C3D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/support
AppUpdatesURL={#MyAppURL}/downloads

; Installation directory
DefaultDirName={autopf}\OryggiAI\Gateway
DefaultGroupName=OryggiAI
DisableProgramGroupPage=yes

; Output settings
OutputDir=Output
OutputBaseFilename=OryggiAI-Gateway-Setup
UninstallDisplayIcon={app}\{#MyAppServiceExe}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Permissions - always require admin for service installation
PrivilegesRequired=admin

; Visual style - LARGER WIZARD
WizardStyle=modern
WizardSizePercent=140,140

; Allow silent install
AllowNoIcons=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation (recommended)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "main"; Description: "Gateway Agent Service"; Types: full custom; Flags: fixed
Name: "desktop"; Description: "Desktop shortcut"; Types: full

[Tasks]
Name: "autostart"; Description: "Start automatically with Windows"; GroupDescription: "Service Options:"; Flags: checkedonce

[Files]
; Main service executable
Source: "dist\{#MyAppServiceExe}"; DestDir: "{app}"; Flags: ignoreversion
; NSSM for reliable service management
Source: "nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
; Icon (optional)
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Start Menu
Name: "{group}\{#MyAppName} Status"; Filename: "services.msc"
Name: "{group}\View Logs"; Filename: "{commonappdata}\OryggiAI\logs"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "services.msc"; Components: desktop

[Dirs]
Name: "{commonappdata}\OryggiAI"; Permissions: users-full
Name: "{commonappdata}\OryggiAI\logs"; Permissions: users-full

[UninstallRun]
; Stop and remove the service before uninstall using NSSM
Filename: "{app}\nssm.exe"; Parameters: "stop {#MyServiceName}"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\nssm.exe"; Parameters: "remove {#MyServiceName} confirm"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\OryggiAI"
Type: dirifempty; Name: "{app}"

[Code]
// ============================================================================
// Pascal Script for Enhanced Installer Behavior
// ============================================================================

var
  // Wizard pages
  TokenPage: TInputQueryWizardPage;
  DatabasePage: TWizardPage;
  AuthMethodPage: TWizardPage;
  ServiceAccountPage: TWizardPage;
  VerificationPage: TWizardPage;

  // Database page controls
  DatabaseComboBox: TNewComboBox;
  DatabaseStatusLabel: TNewStaticText;
  RefreshButton: TNewButton;

  // Auth method page controls
  AuthMethodSQLRadio: TNewRadioButton;
  AuthMethodWindowsRadio: TNewRadioButton;
  SQLUsernameEdit: TNewEdit;
  SQLPasswordEdit: TPasswordEdit;
  SQLCredentialsPanel: TPanel;

  // Service account controls (only for Windows Auth)
  ServiceUsernameEdit: TNewEdit;
  ServicePasswordEdit: TPasswordEdit;

  // Verification page controls
  VerifyButton: TNewButton;
  VerifyStatusLabel: TNewStaticText;
  VerifyResultMemo: TNewMemo;
  ConnectionVerified: Boolean;

  // Values
  TokenValue: String;
  SelectedDatabase: String;
  GatewayURL: String;
  DatabaseHost: String;
  DatabasePort: String;
  Databases: TStringList;
  ServiceUsername: String;
  ServicePassword: String;

  // Auth method
  UseSQLAuth: Boolean;
  SQLUsername: String;
  SQLPassword: String;

// ============================================================================
// Utility Functions
// ============================================================================

function GetCurrentUsername(): String;
begin
  Result := GetUserNameString();
end;

function GetCurrentDomain(): String;
var
  Domain: String;
begin
  Domain := GetEnv('USERDOMAIN');
  if Domain = '' then
    Domain := GetEnv('COMPUTERNAME');
  if Domain = '' then
    Domain := '.';
  Result := Domain;
end;

// Execute a command and capture output
function ExecAndCapture(const Cmd, Params: String; var Output: String): Boolean;
var
  TempFile: String;
  ResultCode: Integer;
  Lines: TStringList;
begin
  Result := False;
  Output := '';
  TempFile := ExpandConstant('{tmp}\cmdoutput.txt');

  if Exec('cmd.exe', '/C ' + Cmd + ' ' + Params + ' > "' + TempFile + '" 2>&1', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if FileExists(TempFile) then
    begin
      Lines := TStringList.Create;
      try
        Lines.LoadFromFile(TempFile);
        Output := Lines.Text;
        Result := True;
      finally
        Lines.Free;
      end;
      DeleteFile(TempFile);
    end;
  end;
end;

// ============================================================================
// Database Discovery Functions
// ============================================================================

procedure DiscoverDatabases();
var
  PowerShellScript: String;
  TempPS1: String;
  Output: String;
  ResultCode: Integer;
  I: Integer;
  Line: String;
  Lines: TStringList;
begin
  // Update status
  if DatabaseStatusLabel <> nil then
    DatabaseStatusLabel.Caption := 'Discovering databases on ' + DatabaseHost + '...';

  // Clear existing
  if DatabaseComboBox <> nil then
    DatabaseComboBox.Items.Clear;
  Databases.Clear;

  // Create PowerShell script for database discovery (only shows databases user has access to)
  PowerShellScript :=
    '$ErrorActionPreference = "SilentlyContinue"' + #13#10 +
    '$connStr = "Server=' + DatabaseHost + ',' + DatabasePort + ';Database=master;Integrated Security=True;TrustServerCertificate=True;"' + #13#10 +
    'try {' + #13#10 +
    '  $conn = New-Object System.Data.SqlClient.SqlConnection($connStr)' + #13#10 +
    '  $conn.Open()' + #13#10 +
    '  $cmd = $conn.CreateCommand()' + #13#10 +
    '  $cmd.CommandText = "SELECT name FROM sys.databases WHERE name NOT IN (''master'',''tempdb'',''model'',''msdb'') AND state_desc = ''ONLINE'' AND HAS_DBACCESS(name) = 1 ORDER BY name"' + #13#10 +
    '  $reader = $cmd.ExecuteReader()' + #13#10 +
    '  while ($reader.Read()) { Write-Output $reader["name"] }' + #13#10 +
    '  $conn.Close()' + #13#10 +
    '} catch {' + #13#10 +
    '  Write-Output "ERROR: $($_.Exception.Message)"' + #13#10 +
    '}';

  // Save to temp file
  TempPS1 := ExpandConstant('{tmp}\discover_db.ps1');
  SaveStringToFile(TempPS1, PowerShellScript, False);

  // Execute PowerShell and capture output
  if ExecAndCapture('powershell.exe', '-ExecutionPolicy Bypass -NoProfile -File "' + TempPS1 + '"', Output) then
  begin
    Lines := TStringList.Create;
    try
      Lines.Text := Output;
      for I := 0 to Lines.Count - 1 do
      begin
        Line := Trim(Lines[I]);
        if (Line <> '') and (Pos('ERROR:', Line) = 0) then
        begin
          Databases.Add(Line);
          if DatabaseComboBox <> nil then
            DatabaseComboBox.Items.Add(Line);
        end;
      end;
    finally
      Lines.Free;
    end;
  end;

  DeleteFile(TempPS1);

  // Update UI
  if DatabaseComboBox <> nil then
  begin
    if DatabaseComboBox.Items.Count > 0 then
    begin
      DatabaseComboBox.ItemIndex := 0;
      DatabaseStatusLabel.Caption := 'Found ' + IntToStr(DatabaseComboBox.Items.Count) + ' database(s) on ' + DatabaseHost;
      DatabaseStatusLabel.Font.Color := clGreen;
    end
    else
    begin
      DatabaseComboBox.Items.Add('(Enter database name manually)');
      DatabaseComboBox.ItemIndex := 0;
      DatabaseStatusLabel.Caption := 'No databases found. You can enter a name manually.';
      DatabaseStatusLabel.Font.Color := $000080FF; // Orange
    end;
  end;

  // Pre-select database from command line if provided
  SelectedDatabase := ExpandConstant('{param:database|}');
  if (SelectedDatabase <> '') and (DatabaseComboBox <> nil) then
  begin
    for I := 0 to DatabaseComboBox.Items.Count - 1 do
    begin
      if DatabaseComboBox.Items[I] = SelectedDatabase then
      begin
        DatabaseComboBox.ItemIndex := I;
        Break;
      end;
    end;
  end;
end;

procedure RefreshButtonClick(Sender: TObject);
begin
  DiscoverDatabases();
end;

// Handle auth method radio button clicks
procedure AuthMethodRadioClick(Sender: TObject);
begin
  UseSQLAuth := AuthMethodSQLRadio.Checked;

  // Enable/disable SQL credential fields based on selection
  if SQLUsernameEdit <> nil then
    SQLUsernameEdit.Enabled := UseSQLAuth;
  if SQLPasswordEdit <> nil then
    SQLPasswordEdit.Enabled := UseSQLAuth;
end;

// ============================================================================
// Connection Verification
// ============================================================================

procedure VerifyConnectionClick(Sender: TObject);
var
  PowerShellScript: String;
  TempPS1: String;
  Output: String;
  Database: String;
  ConnString: String;
  AuthInfo: String;
begin
  ConnectionVerified := False;
  Database := DatabaseComboBox.Text;

  if (Database = '') or (Database = '(Enter database name manually)') then
  begin
    VerifyResultMemo.Text := 'Please select a database first.';
    VerifyStatusLabel.Caption := 'No database selected';
    VerifyStatusLabel.Font.Color := clRed;
    Exit;
  end;

  // Validate credentials based on auth method
  if UseSQLAuth then
  begin
    SQLUsername := SQLUsernameEdit.Text;
    SQLPassword := SQLPasswordEdit.Text;

    if (SQLUsername = '') or (SQLPassword = '') then
    begin
      VerifyResultMemo.Text := 'Please enter SQL Server username and password.';
      VerifyStatusLabel.Caption := 'Missing SQL credentials';
      VerifyStatusLabel.Font.Color := clRed;
      Exit;
    end;

    ConnString := 'Server=' + DatabaseHost + ',' + DatabasePort + ';Database=' + Database + ';User Id=' + SQLUsername + ';Password=' + SQLPassword + ';TrustServerCertificate=True;';
    AuthInfo := 'SQL Auth user: ' + SQLUsername;
  end
  else
  begin
    ServiceUsername := ServiceUsernameEdit.Text;
    ServicePassword := ServicePasswordEdit.Text;

    if (ServiceUsername = '') or (ServicePassword = '') then
    begin
      VerifyResultMemo.Text := 'Please enter Windows username and password.';
      VerifyStatusLabel.Caption := 'Missing Windows credentials';
      VerifyStatusLabel.Font.Color := clRed;
      Exit;
    end;

    ConnString := 'Server=' + DatabaseHost + ',' + DatabasePort + ';Database=' + Database + ';Integrated Security=True;TrustServerCertificate=True;';
    AuthInfo := 'Windows Auth user: ' + ServiceUsername;
  end;

  VerifyStatusLabel.Caption := 'Testing connection...';
  VerifyStatusLabel.Font.Color := clBlue;
  VerifyResultMemo.Text := 'Connecting to SQL Server...' + #13#10 + AuthInfo + #13#10;

  // Create PowerShell script to test connection
  PowerShellScript :=
    '$ErrorActionPreference = "Stop"' + #13#10 +
    'try {' + #13#10 +
    '  $connStr = "' + ConnString + '"' + #13#10 +
    '  $conn = New-Object System.Data.SqlClient.SqlConnection($connStr)' + #13#10 +
    '  $conn.Open()' + #13#10 +
    '  $cmd = $conn.CreateCommand()' + #13#10 +
    '  $cmd.CommandText = "SELECT DB_NAME() as CurrentDB, SUSER_SNAME() as CurrentUser, @@VERSION as SQLVersion"' + #13#10 +
    '  $reader = $cmd.ExecuteReader()' + #13#10 +
    '  if ($reader.Read()) {' + #13#10 +
    '    Write-Output "SUCCESS"' + #13#10 +
    '    Write-Output "Database: $($reader[''CurrentDB''])"' + #13#10 +
    '    Write-Output "User: $($reader[''CurrentUser''])"' + #13#10 +
    '    Write-Output "Server: $($reader[''SQLVersion''].Substring(0, 50))..."' + #13#10 +
    '  }' + #13#10 +
    '  $conn.Close()' + #13#10 +
    '} catch {' + #13#10 +
    '  Write-Output "FAILED"' + #13#10 +
    '  Write-Output $_.Exception.Message' + #13#10 +
    '}';

  TempPS1 := ExpandConstant('{tmp}\verify_conn.ps1');
  SaveStringToFile(TempPS1, PowerShellScript, False);

  if ExecAndCapture('powershell.exe', '-ExecutionPolicy Bypass -NoProfile -File "' + TempPS1 + '"', Output) then
  begin
    VerifyResultMemo.Text := Output;

    if Pos('SUCCESS', Output) > 0 then
    begin
      ConnectionVerified := True;
      VerifyStatusLabel.Caption := 'Connection successful! You can proceed.';
      VerifyStatusLabel.Font.Color := clGreen;
    end
    else
    begin
      VerifyStatusLabel.Caption := 'Connection failed. Check credentials and try again.';
      VerifyStatusLabel.Font.Color := clRed;
    end;
  end
  else
  begin
    VerifyResultMemo.Text := 'Failed to execute verification script.';
    VerifyStatusLabel.Caption := 'Verification error';
    VerifyStatusLabel.Font.Color := clRed;
  end;

  DeleteFile(TempPS1);
end;

// ============================================================================
// Wizard Page Creation
// ============================================================================

procedure InitializeWizard();
var
  TopPos: Integer;
  LabelText: TNewStaticText;
begin
  // Initialize database list
  Databases := TStringList.Create;
  ConnectionVerified := False;
  UseSQLAuth := True;  // Default to SQL Auth (recommended)

  // Get defaults from params
  GatewayURL := ExpandConstant('{param:gateway_url|ws://103.197.77.163:3000/api/gateway/ws}');
  DatabaseHost := ExpandConstant('{param:dbhost|localhost}');
  DatabasePort := ExpandConstant('{param:dbport|1433}');

  // =========================================================================
  // PAGE 1: Token
  // =========================================================================
  TokenPage := CreateInputQueryPage(wpWelcome,
    'Gateway Token',
    'Enter your OryggiAI Gateway Token',
    'Paste the token from your OryggiAI dashboard. This token securely connects your database to the OryggiAI cloud platform.');
  TokenPage.Add('Gateway Token:', False);

  // Pre-fill token from command line if provided
  TokenValue := ExpandConstant('{param:token|}');
  if TokenValue <> '' then
    TokenPage.Values[0] := TokenValue;

  // =========================================================================
  // PAGE 2: Database Selection
  // =========================================================================
  DatabasePage := CreateCustomPage(TokenPage.ID,
    'Select Database',
    'Choose the database you want to connect to OryggiAI');

  TopPos := 0;

  // Description
  LabelText := TNewStaticText.Create(DatabasePage);
  LabelText.Parent := DatabasePage.Surface;
  LabelText.Caption := 'The installer will automatically discover SQL Server databases on your system.' + #13#10 +
                       'Select a database from the dropdown or enter a name manually:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := DatabasePage.SurfaceWidth;
  LabelText.Height := 40;
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;
  TopPos := TopPos + 50;

  // Database dropdown
  DatabaseComboBox := TNewComboBox.Create(DatabasePage);
  DatabaseComboBox.Parent := DatabasePage.Surface;
  DatabaseComboBox.Left := 0;
  DatabaseComboBox.Top := TopPos;
  DatabaseComboBox.Width := DatabasePage.SurfaceWidth - 100;
  DatabaseComboBox.Style := csDropDown;
  TopPos := TopPos + 35;

  // Refresh button
  RefreshButton := TNewButton.Create(DatabasePage);
  RefreshButton.Parent := DatabasePage.Surface;
  RefreshButton.Caption := 'Refresh';
  RefreshButton.Left := DatabaseComboBox.Width + 10;
  RefreshButton.Top := DatabaseComboBox.Top - 2;
  RefreshButton.Width := 80;
  RefreshButton.Height := 25;
  RefreshButton.OnClick := @RefreshButtonClick;

  // Status label
  DatabaseStatusLabel := TNewStaticText.Create(DatabasePage);
  DatabaseStatusLabel.Parent := DatabasePage.Surface;
  DatabaseStatusLabel.Caption := 'Click Refresh to discover databases...';
  DatabaseStatusLabel.Left := 0;
  DatabaseStatusLabel.Top := TopPos;
  DatabaseStatusLabel.Width := DatabasePage.SurfaceWidth;
  DatabaseStatusLabel.Font.Color := clGray;

  // =========================================================================
  // PAGE 3: Authentication Method
  // =========================================================================
  AuthMethodPage := CreateCustomPage(DatabasePage.ID,
    'Authentication Method',
    'How should the Gateway connect to SQL Server?');

  TopPos := 0;

  // Description
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := 'Choose how the Gateway Agent authenticates with SQL Server:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := AuthMethodPage.SurfaceWidth;
  TopPos := TopPos + 30;

  // SQL Auth Radio (Recommended - first option)
  AuthMethodSQLRadio := TNewRadioButton.Create(AuthMethodPage);
  AuthMethodSQLRadio.Parent := AuthMethodPage.Surface;
  AuthMethodSQLRadio.Caption := 'SQL Server Authentication (Recommended)';
  AuthMethodSQLRadio.Left := 0;
  AuthMethodSQLRadio.Top := TopPos;
  AuthMethodSQLRadio.Width := AuthMethodPage.SurfaceWidth;
  AuthMethodSQLRadio.Checked := True;
  AuthMethodSQLRadio.OnClick := @AuthMethodRadioClick;
  AuthMethodSQLRadio.Font.Style := [fsBold];
  TopPos := TopPos + 22;

  // SQL Auth description
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := '     Use SQL Server login credentials (username/password). ' +
                       'Easiest setup - no Windows service account needed.';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := AuthMethodPage.SurfaceWidth;
  LabelText.Height := 30;
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;
  LabelText.Font.Color := clGray;
  TopPos := TopPos + 40;

  // Windows Auth Radio
  AuthMethodWindowsRadio := TNewRadioButton.Create(AuthMethodPage);
  AuthMethodWindowsRadio.Parent := AuthMethodPage.Surface;
  AuthMethodWindowsRadio.Caption := 'Windows Authentication';
  AuthMethodWindowsRadio.Left := 0;
  AuthMethodWindowsRadio.Top := TopPos;
  AuthMethodWindowsRadio.Width := AuthMethodPage.SurfaceWidth;
  AuthMethodWindowsRadio.Checked := False;
  AuthMethodWindowsRadio.OnClick := @AuthMethodRadioClick;
  TopPos := TopPos + 22;

  // Windows Auth description
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := '     Use your Windows login. Requires entering Windows password ' +
                       'and "Log on as service" permission.';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := AuthMethodPage.SurfaceWidth;
  LabelText.Height := 30;
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;
  LabelText.Font.Color := clGray;
  TopPos := TopPos + 50;

  // SQL Credentials section
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := 'SQL Server Credentials:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Font.Style := [fsBold];
  TopPos := TopPos + 25;

  // SQL Username label
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := 'SQL Username:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  TopPos := TopPos + 20;

  // SQL Username edit
  SQLUsernameEdit := TNewEdit.Create(AuthMethodPage);
  SQLUsernameEdit.Parent := AuthMethodPage.Surface;
  SQLUsernameEdit.Left := 0;
  SQLUsernameEdit.Top := TopPos;
  SQLUsernameEdit.Width := AuthMethodPage.SurfaceWidth;
  SQLUsernameEdit.Text := 'sa';
  TopPos := TopPos + 30;

  // SQL Password label
  LabelText := TNewStaticText.Create(AuthMethodPage);
  LabelText.Parent := AuthMethodPage.Surface;
  LabelText.Caption := 'SQL Password:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  TopPos := TopPos + 20;

  // SQL Password edit
  SQLPasswordEdit := TPasswordEdit.Create(AuthMethodPage);
  SQLPasswordEdit.Parent := AuthMethodPage.Surface;
  SQLPasswordEdit.Left := 0;
  SQLPasswordEdit.Top := TopPos;
  SQLPasswordEdit.Width := AuthMethodPage.SurfaceWidth;

  // =========================================================================
  // PAGE 4: Service Account (only for Windows Auth)
  // =========================================================================
  ServiceAccountPage := CreateCustomPage(AuthMethodPage.ID,
    'Service Account',
    'Configure the Windows account for the Gateway Service');

  TopPos := 0;

  // Explanation
  LabelText := TNewStaticText.Create(ServiceAccountPage);
  LabelText.Parent := ServiceAccountPage.Surface;
  LabelText.Caption := 'The Gateway Service needs to run as a Windows account that has access to SQL Server.' + #13#10 +
                       'Enter the credentials of your Windows account (the one you use to log into SQL Server):';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := ServiceAccountPage.SurfaceWidth;
  LabelText.Height := 50;
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;
  TopPos := TopPos + 60;

  // Username label
  LabelText := TNewStaticText.Create(ServiceAccountPage);
  LabelText.Parent := ServiceAccountPage.Surface;
  LabelText.Caption := 'Windows Username (DOMAIN\User or .\User for local account):';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  TopPos := TopPos + 20;

  // Username edit
  ServiceUsernameEdit := TNewEdit.Create(ServiceAccountPage);
  ServiceUsernameEdit.Parent := ServiceAccountPage.Surface;
  ServiceUsernameEdit.Left := 0;
  ServiceUsernameEdit.Top := TopPos;
  ServiceUsernameEdit.Width := ServiceAccountPage.SurfaceWidth;
  ServiceUsernameEdit.Text := '.\' + GetCurrentUsername();
  TopPos := TopPos + 35;

  // Password label
  LabelText := TNewStaticText.Create(ServiceAccountPage);
  LabelText.Parent := ServiceAccountPage.Surface;
  LabelText.Caption := 'Windows Password:';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  TopPos := TopPos + 20;

  // Password edit
  ServicePasswordEdit := TPasswordEdit.Create(ServiceAccountPage);
  ServicePasswordEdit.Parent := ServiceAccountPage.Surface;
  ServicePasswordEdit.Left := 0;
  ServicePasswordEdit.Top := TopPos;
  ServicePasswordEdit.Width := ServiceAccountPage.SurfaceWidth;
  TopPos := TopPos + 45;

  // Info note
  LabelText := TNewStaticText.Create(ServiceAccountPage);
  LabelText.Parent := ServiceAccountPage.Surface;
  LabelText.Caption := 'Your password is used only to configure the Windows Service and is NOT stored by OryggiAI.';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := ServiceAccountPage.SurfaceWidth;
  LabelText.Font.Color := clGray;
  LabelText.Font.Style := [fsItalic];
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;

  // =========================================================================
  // PAGE 5: Connection Verification
  // =========================================================================
  VerificationPage := CreateCustomPage(ServiceAccountPage.ID,
    'Verify Connection',
    'Test your SQL Server connection before installing');

  TopPos := 0;

  // Description
  LabelText := TNewStaticText.Create(VerificationPage);
  LabelText.Parent := VerificationPage.Surface;
  LabelText.Caption := 'Click the button below to verify that your credentials can connect to the selected database.' + #13#10 +
                       'This ensures the Gateway Service will work correctly after installation.';
  LabelText.Left := 0;
  LabelText.Top := TopPos;
  LabelText.Width := VerificationPage.SurfaceWidth;
  LabelText.Height := 45;
  LabelText.AutoSize := False;
  LabelText.WordWrap := True;
  TopPos := TopPos + 55;

  // Verify button
  VerifyButton := TNewButton.Create(VerificationPage);
  VerifyButton.Parent := VerificationPage.Surface;
  VerifyButton.Caption := 'Test Connection';
  VerifyButton.Left := 0;
  VerifyButton.Top := TopPos;
  VerifyButton.Width := 150;
  VerifyButton.Height := 30;
  VerifyButton.OnClick := @VerifyConnectionClick;
  TopPos := TopPos + 40;

  // Status label
  VerifyStatusLabel := TNewStaticText.Create(VerificationPage);
  VerifyStatusLabel.Parent := VerificationPage.Surface;
  VerifyStatusLabel.Caption := 'Click "Test Connection" to verify your settings';
  VerifyStatusLabel.Left := 0;
  VerifyStatusLabel.Top := TopPos;
  VerifyStatusLabel.Width := VerificationPage.SurfaceWidth;
  VerifyStatusLabel.Font.Style := [fsBold];
  TopPos := TopPos + 25;

  // Result memo
  VerifyResultMemo := TNewMemo.Create(VerificationPage);
  VerifyResultMemo.Parent := VerificationPage.Surface;
  VerifyResultMemo.Left := 0;
  VerifyResultMemo.Top := TopPos;
  VerifyResultMemo.Width := VerificationPage.SurfaceWidth;
  VerifyResultMemo.Height := 120;
  VerifyResultMemo.ReadOnly := True;
  VerifyResultMemo.ScrollBars := ssVertical;
  VerifyResultMemo.Text := 'Connection test results will appear here...';
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // Auto-discover databases when entering the database page
  if CurPageID = DatabasePage.ID then
  begin
    if DatabaseComboBox.Items.Count = 0 then
      DiscoverDatabases();
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  // Validate token
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

  // Validate database selection
  if CurPageID = DatabasePage.ID then
  begin
    SelectedDatabase := DatabaseComboBox.Text;
    if (SelectedDatabase = '') or (SelectedDatabase = '(Enter database name manually)') then
    begin
      MsgBox('Please select or enter a database name.', mbError, MB_OK);
      Result := False;
    end;
  end;

  // Validate auth method page
  if CurPageID = AuthMethodPage.ID then
  begin
    UseSQLAuth := AuthMethodSQLRadio.Checked;

    if UseSQLAuth then
    begin
      SQLUsername := SQLUsernameEdit.Text;
      SQLPassword := SQLPasswordEdit.Text;
      if SQLUsername = '' then
      begin
        MsgBox('Please enter SQL Server username.', mbError, MB_OK);
        Result := False;
      end
      else if SQLPassword = '' then
      begin
        MsgBox('Please enter SQL Server password.', mbError, MB_OK);
        Result := False;
      end;
    end;
  end;

  // Validate service account (only for Windows Auth)
  if CurPageID = ServiceAccountPage.ID then
  begin
    ServiceUsername := ServiceUsernameEdit.Text;
    ServicePassword := ServicePasswordEdit.Text;
    if ServiceUsername = '' then
    begin
      MsgBox('Please enter a username for the service account.', mbError, MB_OK);
      Result := False;
    end
    else if ServicePassword = '' then
    begin
      MsgBox('Please enter the password for the service account.', mbError, MB_OK);
      Result := False;
    end;
  end;

  // Validate connection verification
  if CurPageID = VerificationPage.ID then
  begin
    if not ConnectionVerified then
    begin
      if MsgBox('Connection has not been verified. Are you sure you want to continue?' + #13#10 + #13#10 +
                'The service may fail to start if the credentials are incorrect.',
                mbConfirmation, MB_YESNO) = IDNO then
      begin
        Result := False;
      end;
    end;
  end;
end;

// ============================================================================
// Configuration File Creation
// ============================================================================

procedure SaveConfiguration();
var
  ConfigPath: String;
  ConfigContent: String;
  UseWindowsAuthStr: String;
begin
  ConfigPath := ExpandConstant('{commonappdata}\OryggiAI\gateway-config.json');

  // Get final values
  TokenValue := TokenPage.Values[0];
  if DatabaseComboBox <> nil then
    SelectedDatabase := DatabaseComboBox.Text;

  // Create JSON config based on auth method
  if UseSQLAuth then
  begin
    // SQL Auth - store SQL credentials in config
    UseWindowsAuthStr := 'false';
    ConfigContent := '{' + #13#10 +
      '  "gateway_token": "' + TokenValue + '",' + #13#10 +
      '  "saas_url": "' + GatewayURL + '",' + #13#10 +
      '  "db_host": "' + DatabaseHost + '",' + #13#10 +
      '  "db_port": ' + DatabasePort + ',' + #13#10 +
      '  "db_database": "' + SelectedDatabase + '",' + #13#10 +
      '  "use_windows_auth": false,' + #13#10 +
      '  "db_username": "' + SQLUsername + '",' + #13#10 +
      '  "db_password": "' + SQLPassword + '",' + #13#10 +
      '  "db_driver": "ODBC Driver 17 for SQL Server"' + #13#10 +
      '}';
  end
  else
  begin
    // Windows Auth - no SQL credentials needed
    UseWindowsAuthStr := 'true';
    ConfigContent := '{' + #13#10 +
      '  "gateway_token": "' + TokenValue + '",' + #13#10 +
      '  "saas_url": "' + GatewayURL + '",' + #13#10 +
      '  "db_host": "' + DatabaseHost + '",' + #13#10 +
      '  "db_port": ' + DatabasePort + ',' + #13#10 +
      '  "db_database": "' + SelectedDatabase + '",' + #13#10 +
      '  "use_windows_auth": true,' + #13#10 +
      '  "db_driver": "ODBC Driver 17 for SQL Server"' + #13#10 +
      '}';
  end;

  // Save configuration
  ForceDirectories(ExtractFilePath(ConfigPath));
  SaveStringToFile(ConfigPath, ConfigContent, False);
end;

// ============================================================================
// Service Installation with NSSM
// ============================================================================

procedure InstallServiceWithNSSM();
var
  ResultCode: Integer;
  NSSMPath, ServiceExePath: String;
begin
  NSSMPath := ExpandConstant('{app}\nssm.exe');
  ServiceExePath := ExpandConstant('{app}\{#MyAppServiceExe}');

  // Remove existing service if present
  Exec(NSSMPath, 'stop {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
  Exec(NSSMPath, 'remove {#MyServiceName} confirm', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(500);

  // Install new service with NSSM
  Exec(NSSMPath, 'install {#MyServiceName} "' + ServiceExePath + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Configure display name
  Exec(NSSMPath, 'set {#MyServiceName} DisplayName "{#MyServiceDisplayName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Configure description
  Exec(NSSMPath, 'set {#MyServiceName} Description "OryggiAI Gateway Agent - Connects your SQL Server database to OryggiAI cloud"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Configure service account based on auth method
  if UseSQLAuth then
  begin
    // SQL Auth - run as LocalSystem (no user credentials needed)
    // LocalSystem is the default, so we don't need to set ObjectName
    Exec(NSSMPath, 'set {#MyServiceName} ObjectName LocalSystem', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end
  else
  begin
    // Windows Auth - run as specified Windows user
    ServiceUsername := ServiceUsernameEdit.Text;
    ServicePassword := ServicePasswordEdit.Text;
    Exec(NSSMPath, 'set {#MyServiceName} ObjectName "' + ServiceUsername + '" "' + ServicePassword + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;

  // Configure auto-start
  Exec(NSSMPath, 'set {#MyServiceName} Start SERVICE_AUTO_START', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Configure stdout/stderr logging
  Exec(NSSMPath, 'set {#MyServiceName} AppStdout ' + ExpandConstant('{commonappdata}\OryggiAI\logs\service-stdout.log'), '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(NSSMPath, 'set {#MyServiceName} AppStderr ' + ExpandConstant('{commonappdata}\OryggiAI\logs\service-stderr.log'), '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // Start the service
  Sleep(500);
  Exec(NSSMPath, 'start {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SaveConfiguration();
    InstallServiceWithNSSM();
  end;
end;

// ============================================================================
// Service Management
// ============================================================================

function IsServiceInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('sc.exe', 'query {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  NSSMPath: String;
begin
  Result := '';
  NSSMPath := ExpandConstant('{tmp}\nssm.exe');

  // Extract NSSM to temp for pre-install cleanup
  ExtractTemporaryFile('nssm.exe');

  // Stop and remove existing service if present
  if IsServiceInstalled() then
  begin
    Exec(NSSMPath, 'stop {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
    Exec(NSSMPath, 'remove {#MyServiceName} confirm', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);

    // Fallback with sc.exe
    Exec('sc.exe', 'stop {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
    Exec('sc.exe', 'delete {#MyServiceName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);

    // Kill process if still running
    Exec('taskkill', '/F /IM {#MyAppServiceExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(500);
  end;
end;

// ============================================================================
// Cleanup
// ============================================================================

procedure DeinitializeSetup();
begin
  if Databases <> nil then
    Databases.Free;
end;

// ============================================================================
// Silent Install Support
// ============================================================================

function ShouldSkipPage(PageID: Integer): Boolean;
var
  ParamToken, ParamDatabase, ParamUser, ParamPass, ParamAuthType, ParamSQLUser, ParamSQLPass: String;
begin
  Result := False;

  ParamToken := ExpandConstant('{param:token|}');
  ParamDatabase := ExpandConstant('{param:database|}');
  ParamUser := ExpandConstant('{param:serviceuser|}');
  ParamPass := ExpandConstant('{param:servicepass|}');
  ParamAuthType := ExpandConstant('{param:authtype|}');
  ParamSQLUser := ExpandConstant('{param:sqluser|}');
  ParamSQLPass := ExpandConstant('{param:sqlpass|}');

  // Skip token page if token provided
  if (PageID = TokenPage.ID) and (ParamToken <> '') then
  begin
    TokenValue := ParamToken;
    TokenPage.Values[0] := ParamToken;
    Result := True;
  end;

  // Skip database page if database provided
  if (PageID = DatabasePage.ID) and (ParamDatabase <> '') then
  begin
    SelectedDatabase := ParamDatabase;
    if DatabaseComboBox <> nil then
      DatabaseComboBox.Text := ParamDatabase;
    Result := True;
  end;

  // Skip auth method page if auth type provided
  if (PageID = AuthMethodPage.ID) and (ParamAuthType <> '') then
  begin
    if ParamAuthType = 'sql' then
    begin
      UseSQLAuth := True;
      SQLUsername := ParamSQLUser;
      SQLPassword := ParamSQLPass;
      if AuthMethodSQLRadio <> nil then
        AuthMethodSQLRadio.Checked := True;
      if SQLUsernameEdit <> nil then
        SQLUsernameEdit.Text := ParamSQLUser;
      if SQLPasswordEdit <> nil then
        SQLPasswordEdit.Text := ParamSQLPass;
    end
    else
    begin
      UseSQLAuth := False;
      if AuthMethodWindowsRadio <> nil then
        AuthMethodWindowsRadio.Checked := True;
    end;
    Result := True;
  end;

  // Skip service account page if using SQL Auth OR if Windows credentials provided
  if PageID = ServiceAccountPage.ID then
  begin
    if UseSQLAuth then
    begin
      // SQL Auth - skip service account page entirely (run as LocalSystem)
      Result := True;
    end
    else if (ParamUser <> '') and (ParamPass <> '') then
    begin
      // Windows Auth with credentials provided
      ServiceUsername := ParamUser;
      ServicePassword := ParamPass;
      if ServiceUsernameEdit <> nil then
        ServiceUsernameEdit.Text := ParamUser;
      if ServicePasswordEdit <> nil then
        ServicePasswordEdit.Text := ParamPass;
      Result := True;
    end;
  end;

  // Skip verification page in silent mode
  if PageID = VerificationPage.ID then
  begin
    if UseSQLAuth and (ParamToken <> '') and (ParamDatabase <> '') and (ParamSQLUser <> '') and (ParamSQLPass <> '') then
    begin
      // SQL Auth silent install
      ConnectionVerified := True;
      Result := True;
    end
    else if (not UseSQLAuth) and (ParamToken <> '') and (ParamDatabase <> '') and (ParamUser <> '') and (ParamPass <> '') then
    begin
      // Windows Auth silent install
      ConnectionVerified := True;
      Result := True;
    end;
  end;
end;
