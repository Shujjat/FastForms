[Setup]
AppId={{A5D0B599-9E34-4D6B-A4C9-2E5371F2B4A0}
AppName=FastForms
AppVersion=1.0.0
AppPublisher=FastForms
DefaultDirName={autopf}\FastForms
DefaultGroupName=FastForms
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=FastForms-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicons"; Description: "Create desktop shortcuts"; GroupDescription: "Additional icons:"; Flags: unchecked

[Code]
var
  PgConfigPage: TInputQueryWizardPage;
  PgPassword: string;

function PythonAlreadyInstalled(): Boolean;
begin
  Result := FileExists('C:\Program Files\Python312\python.exe') or FileExists('C:\Program Files (x86)\Python312\python.exe');
end;

function NodeAlreadyInstalled(): Boolean;
begin
  Result := FileExists('C:\Program Files\nodejs\npm.cmd') or FileExists('C:\Program Files (x86)\nodejs\npm.cmd');
end;

function PostgreSQLAlreadyInstalled(): Boolean;
begin
  Result :=
    FileExists('C:\Program Files\PostgreSQL\16\bin\psql.exe') or
    FileExists('C:\Program Files\PostgreSQL\17\bin\psql.exe') or
    FileExists('C:\Program Files\PostgreSQL\15\bin\psql.exe') or
    FileExists('C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe') or
    FileExists('C:\Program Files (x86)\PostgreSQL\17\bin\psql.exe') or
    FileExists('C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe');
end;

function InstallRuntimeNeeded(): Boolean;
begin
  Result := (not PythonAlreadyInstalled()) or (not NodeAlreadyInstalled()) or (not PostgreSQLAlreadyInstalled());
end;

procedure EnsurePythonInstalled();
var
  PythonUrl: string;
  BaseName: string;
  DownloadBytes: Int64;
  PythonExePath: string;
  ResultCode: Integer;
begin
  if PythonAlreadyInstalled() then
    Exit;

  PythonUrl := 'https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe';
  BaseName := 'python-3.12.5-amd64.exe';
  PythonExePath := ExpandConstant('{tmp}') + '\' + BaseName;

  try
    WizardForm.StatusLabel.Caption := 'Downloading Python 3.12...';
    DownloadBytes := DownloadTemporaryFile(PythonUrl, BaseName, '', nil);
    if DownloadBytes < 0 then
      ; // just keep compiler happy; negative is not expected
    WizardForm.StatusLabel.Caption := 'Installing Python 3.12...';
    if not Exec(PythonExePath,
      '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0',
      '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException(Format('Python installer failed (code %d).', [ResultCode]));
  except
    RaiseException('Failed to download/install Python 3.12. Check internet/proxy settings.');
  end;
end;

procedure EnsureNodeInstalled();
var
  NodeUrl: string;
  BaseName: string;
  DownloadBytes: Int64;
  NodeMsiPath: string;
  ResultCode: Integer;
begin
  if NodeAlreadyInstalled() then
    Exit;

  NodeUrl := 'https://nodejs.org/dist/v20.20.0/node-v20.20.0-x64.msi';
  BaseName := 'node-v20.20.0-x64.msi';
  NodeMsiPath := ExpandConstant('{tmp}') + '\' + BaseName;

  try
    WizardForm.StatusLabel.Caption := 'Downloading Node.js 20...';
    DownloadBytes := DownloadTemporaryFile(NodeUrl, BaseName, '', nil);
    if DownloadBytes < 0 then
      ; // just keep compiler happy; negative is not expected
    WizardForm.StatusLabel.Caption := 'Installing Node.js 20...';
    if not Exec('msiexec',
      '/qn /norestart /i "' + NodeMsiPath + '"',
      '',
      SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException(Format('Node installer failed (code %d).', [ResultCode]));
  except
    RaiseException('Failed to download/install Node.js 20. Check internet/proxy settings.');
  end;
end;

procedure EnsurePostgreSQLInstalled();
var
  PostgresUrl: string;
  BaseName: string;
  PostgresExePath: string;
  ResultCode: Integer;
begin
  if PostgreSQLAlreadyInstalled() then
    Exit;

  PostgresUrl := 'https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64.exe';
  BaseName := 'postgresql-16.4-1-windows-x64.exe';
  PostgresExePath := ExpandConstant('{tmp}') + '\' + BaseName;

  try
    WizardForm.StatusLabel.Caption := 'Downloading PostgreSQL 16...';
    DownloadTemporaryFile(PostgresUrl, BaseName, '', nil);
    WizardForm.StatusLabel.Caption := 'Installing PostgreSQL 16...';
    if not Exec(
      PostgresExePath,
      '--mode unattended --unattendedmodeui minimal --superpassword "' + PgPassword + '" --servicepassword "' + PgPassword + '" --prefix "C:\Program Files\PostgreSQL\16" --datadir "C:\Program Files\PostgreSQL\16\data"',
      '',
      SW_HIDE,
      ewWaitUntilTerminated,
      ResultCode
    ) then
      RaiseException(Format('PostgreSQL installer failed (code %d).', [ResultCode]));
  except
    RaiseException('Failed to download/install PostgreSQL 16. Check internet/proxy settings or password rules.');
  end;
end;

function DetectPsqlPath(): string;
begin
  Result := '';
  if FileExists('C:\Program Files\PostgreSQL\16\bin\psql.exe') then
    Result := 'C:\Program Files\PostgreSQL\16\bin\psql.exe'
  else if FileExists('C:\Program Files\PostgreSQL\17\bin\psql.exe') then
    Result := 'C:\Program Files\PostgreSQL\17\bin\psql.exe'
  else if FileExists('C:\Program Files\PostgreSQL\15\bin\psql.exe') then
    Result := 'C:\Program Files\PostgreSQL\15\bin\psql.exe'
  else if FileExists('C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe') then
    Result := 'C:\Program Files (x86)\PostgreSQL\16\bin\psql.exe'
  else if FileExists('C:\Program Files (x86)\PostgreSQL\17\bin\psql.exe') then
    Result := 'C:\Program Files (x86)\PostgreSQL\17\bin\psql.exe'
  else if FileExists('C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe') then
    Result := 'C:\Program Files (x86)\PostgreSQL\15\bin\psql.exe';
end;

procedure ConfigureBackendEnv();
var
  EnvPath: string;
  EnvBody: string;
begin
  EnvPath := ExpandConstant('{app}\backend\.env');
  EnvBody :=
    'DJANGO_SECRET_KEY=change-me' + #13#10 +
    'DEBUG=True' + #13#10 +
    'ALLOWED_HOSTS=*' + #13#10 +
    'DB_ENGINE=postgres' + #13#10 +
    'DB_NAME=fastforms' + #13#10 +
    'DB_USER=postgres' + #13#10 +
    'DB_PASSWORD=' + PgPassword + #13#10 +
    'DB_HOST=127.0.0.1' + #13#10 +
    'DB_PORT=5432' + #13#10 +
    'CELERY_BROKER_URL=redis://localhost:6379/0' + #13#10 +
    'CELERY_RESULT_BACKEND=redis://localhost:6379/0' + #13#10 +
    'CELERY_TASK_ALWAYS_EAGER=False' + #13#10 +
    'EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend' + #13#10 +
    'DEFAULT_FROM_EMAIL=noreply@fastforms.local' + #13#10;
  SaveStringToFile(EnvPath, EnvBody, False);
end;

procedure EnsureFastFormsDatabase();
var
  PsqlPath: string;
  ResultCode: Integer;
  CmdParams: string;
begin
  PsqlPath := DetectPsqlPath();
  if PsqlPath = '' then
    Exit;

  CmdParams :=
    '/C set "PGPASSWORD=' + PgPassword + '" && "' + PsqlPath + '" -h 127.0.0.1 -p 5432 -U postgres -d postgres -c "CREATE DATABASE fastforms;"';

  Exec('cmd.exe', CmdParams, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure InitializeWizard();
begin
  PgConfigPage := CreateInputQueryPage(
    wpSelectTasks,
    'PostgreSQL Setup',
    'Configure PostgreSQL for FastForms',
    'Enter the PostgreSQL superuser password to be used by installer-created database and backend .env.'
  );
  PgConfigPage.Add('PostgreSQL password:', True);
  PgConfigPage.Values[0] := 'FastForms@123';
  PgPassword := PgConfigPage.Values[0];
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PgConfigPage.ID then
  begin
    PgPassword := Trim(PgConfigPage.Values[0]);
    if PgPassword = '' then
    begin
      MsgBox('PostgreSQL password cannot be empty.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    if PgPassword = '' then
      PgPassword := 'FastForms@123';
    if InstallRuntimeNeeded() then
    begin
      EnsurePythonInstalled();
      EnsureNodeInstalled();
      EnsurePostgreSQLInstalled();
    end;
  end;
  if CurStep = ssPostInstall then
  begin
    ConfigureBackendEnv();
    EnsureFastFormsDatabase();
  end;
end;

[Files]
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docker-compose.yml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\backend\*"; DestDir: "{app}\backend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*;*.pyc;.venv\*;.pytest_cache\*;db.sqlite3"
Source: "..\frontend\*"; DestDir: "{app}\frontend"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "node_modules\*;dist\*;.vite\*"
Source: "..\Docs\*"; DestDir: "{app}\Docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\start-backend.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\start-frontend.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\scripts\start-fastforms.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Dirs]
Name: "{app}\frontend\node_modules"; Flags: uninsneveruninstall

[Icons]
Name: "{group}\Run FastForms"; Filename: "{app}\scripts\start-fastforms.bat"; WorkingDir: "{app}\scripts"
Name: "{group}\Start Backend"; Filename: "{app}\scripts\start-backend.bat"; WorkingDir: "{app}\backend"
Name: "{group}\Start Frontend"; Filename: "{app}\scripts\start-frontend.bat"; WorkingDir: "{app}\frontend"
Name: "{commondesktop}\Run FastForms"; Filename: "{app}\scripts\start-fastforms.bat"; WorkingDir: "{app}\scripts"; Tasks: desktopicons
Name: "{commondesktop}\FastForms Backend"; Filename: "{app}\scripts\start-backend.bat"; WorkingDir: "{app}\backend"; Tasks: desktopicons
Name: "{commondesktop}\FastForms Frontend"; Filename: "{app}\scripts\start-frontend.bat"; WorkingDir: "{app}\frontend"; Tasks: desktopicons

[Run]
Filename: "{app}\scripts\start-fastforms.bat"; Description: "Run FastForms (opens browser)"; Flags: postinstall shellexec skipifsilent unchecked
