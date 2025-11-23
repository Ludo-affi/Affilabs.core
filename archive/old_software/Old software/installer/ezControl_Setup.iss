; ezControl Installer Script for Inno Setup 6
; This creates a professional Windows installer with driver support

#define MyAppName "ezControl"
#define MyAppVersion "4.0"
#define MyAppPublisher "Your Company Name"
#define MyAppExeName "ezControl.exe"
#define MyAppAssocName MyAppName + " File"
#define MyAppAssocExt ".ezc"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
AppId={{B8F5A2C9-3D4E-4F1A-9B2C-7E8F6D5A4C3B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE.txt
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=.\output
OutputBaseFilename=ezControl_Setup_{#MyAppVersion}
SetupIconFile=..\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "installDrivers"; Description: "Install USB drivers (only if not already installed)"; GroupDescription: "Hardware Support:"; Flags: unchecked

[Files]
; Main application
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Configuration files
Source: "..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs

; USB Drivers (you'll need to add these)
Source: "drivers\*"; DestDir: "{tmp}\drivers"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: installDrivers

; Visual C++ Redistributable (if needed)
Source: "redist\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: ignoreversion deleteafterinstall; Check: VCRedistNeedsInstall

; README and documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\QUICK_START_MODERN_THEME.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Install Visual C++ Redistributable if needed
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/quiet /norestart"; StatusMsg: "Installing Visual C++ Redistributable..."; Flags: waituntilterminated; Check: VCRedistNeedsInstall

; Install USB drivers (FTDI)
Filename: "{tmp}\drivers\FTDI_CDM_Driver.exe"; Parameters: "/S"; StatusMsg: "Installing FTDI USB drivers..."; Flags: waituntilterminated skipifdoesntexist; Tasks: installDrivers

; Install libusb drivers (if you have them)
Filename: "{tmp}\drivers\libusb_driver_installer.exe"; Parameters: "/S"; StatusMsg: "Installing LibUSB drivers..."; Flags: waituntilterminated skipifdoesntexist; Tasks: installDrivers

; Launch application after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if Visual C++ Redistributable is installed
function VCRedistNeedsInstall: Boolean;
var
  Version: String;
begin
  // Check for VC++ 2015-2022 Redistributable (x64)
  if RegQueryStringValue(HKEY_LOCAL_MACHINE,
     'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Version', Version) then
  begin
    Result := False; // Already installed
  end
  else
  begin
    Result := True; // Needs installation
  end;
end;

// Check if FTDI drivers are installed
function FTDIDriversInstalled: Boolean;
var
  ResultCode: Integer;
begin
  // Simple check - you can enhance this
  Result := RegKeyExists(HKEY_LOCAL_MACHINE, 'SYSTEM\CurrentControlSet\Enum\FTDIBUS');
end;

// Show driver installation status
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if FTDIDriversInstalled then
      MsgBox('FTDI drivers are installed and ready.', mbInformation, MB_OK)
    else if WizardIsTaskSelected('installDrivers') then
      MsgBox('Driver installation completed. You may need to restart your computer for changes to take effect.', mbInformation, MB_OK);
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\config"
Type: filesandordirs; Name: "{app}\logs"
