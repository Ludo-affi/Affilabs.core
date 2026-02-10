; Affilabs-Core NSIS Installer Script
; Includes automatic USB4000 driver installation via Zadig

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "StrFunc.nsh"

${StrContains}  ; Declare StrContains function

; Installer Information
!define PRODUCT_NAME "Affilabs-Core"
!define PRODUCT_VERSION "2.0.2"
!define PRODUCT_PUBLISHER "Affilabs"
!define PRODUCT_WEB_SITE "https://affinitelabs.com"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "Affilabs-Core-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES64\Affilabs\Affilabs-Core"
InstallDirRegKey HKLM "${PRODUCT_UNINST_KEY}" "InstallLocation"
RequestExecutionLevel admin

; Modern UI Configuration
!define MUI_ABORTWARNING
!define MUI_ICON "ui\img\affinite2.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Installer Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\Affilabs-Core.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch ${PRODUCT_NAME}"
!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Language
!insertmacro MUI_LANGUAGE "English"

; Installer Section
Section "Main Application" SecMain
  SectionIn RO

  SetOutPath "$INSTDIR"

  ; Copy main executable
  File "/oname=Affilabs-Core.exe" "dist\Affilabs-Core-v${PRODUCT_VERSION}.exe"

  ; Copy Zadig for driver installation (optional - check if exists)
  ${If} ${FileExists} "installer_files\zadig.exe"
    File "installer_files\zadig.exe"
  ${Else}
    DetailPrint "WARNING: zadig.exe not included - manual driver installation required"
  ${EndIf}

  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\Affilabs-Core.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\uninst.exe"
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\Affilabs-Core.exe"

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninst.exe"

  ; Write registry keys
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\Affilabs-Core.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"

SectionEnd

Section "Ocean Optics Spectrometer Driver" SecDriver
  DetailPrint "Checking for Ocean Optics spectrometer..."

  ; Check if Zadig exists (required for driver installation)
  ${If} ${FileExists} "$INSTDIR\zadig.exe"
    ; Check if Ocean Optics device is connected using Zadig's list command
    nsExec::ExecToStack '"$INSTDIR\zadig.exe" --list-devices'
    Pop $0 ; Return code
    Pop $1 ; Output

    ; Check if Ocean Optics device (Flame-T, USB4000, etc.) is in the device list
    ${If} $1 != ""
      StrCpy $3 0  ; Flag for device found
      
      ; Check for Flame-T
      ${StrContains} $2 "Flame" $1
      ${If} $2 != ""
        StrCpy $3 1
        StrCpy $4 "Flame-T"
      ${EndIf}
      
      ; Check for USB4000
      ${StrContains} $2 "USB4000" $1
      ${If} $2 != ""
        StrCpy $3 1
        StrCpy $4 "USB4000"
      ${EndIf}
      
      ${If} $3 == 1
        DetailPrint "$4 detected! Installing WinUSB driver..."
        MessageBox MB_YESNO "Ocean Optics $4 detected!$\n$\nInstall WinUSB driver automatically?" IDYES InstallAuto IDNO InstallManual
        
        InstallAuto:
          nsExec::ExecToLog '"$INSTDIR\zadig.exe" --device "$4" --driver winusb --install --timeout 60'
          Pop $0
          ${If} $0 == 0
            DetailPrint "$4 driver installed successfully!"
            MessageBox MB_OK "$4 WinUSB driver installed!$\n$\nYour spectrometer is ready to use."
          ${Else}
            DetailPrint "Automatic driver installation failed (code: $0)"
            MessageBox MB_OK "Automatic installation failed.$\n$\nZadig will open for manual installation."
            Goto InstallManual
          ${EndIf}
          Goto DriverDone
          
        InstallManual:
          DetailPrint "Launching Zadig for manual driver installation..."
          MessageBox MB_OK "Zadig will now open.$\n$\nSteps:$\n1. Select '$4' from the device list$\n2. Ensure 'WinUSB' is selected as driver$\n3. Click 'Install Driver'$\n4. Wait for completion"
          ExecWait '"$INSTDIR\zadig.exe"'
          
        DriverDone:
      ${Else}
        DetailPrint "Ocean Optics device not currently connected"
        MessageBox MB_YESNO "Ocean Optics spectrometer not detected.$\n$\nZadig has been installed for future use.$\n$\nLaunch Zadig now to prepare?" IDYES RunZadig IDNO SkipZadig
        
        RunZadig:
          MessageBox MB_OK "Zadig will open.$\n$\nConnect your spectrometer, then:$\n1. Select it from the device list$\n2. Choose 'WinUSB' driver$\n3. Click 'Install Driver'"
          ExecWait '"$INSTDIR\zadig.exe"'
          
        SkipZadig:
          DetailPrint "Zadig available at: $INSTDIR\zadig.exe"
      ${EndIf}
    ${Else}
      DetailPrint "Could not query devices"
      MessageBox MB_YESNO "Cannot auto-detect devices.$\n$\nOpen Zadig to manually install driver?" IDYES OpenZadig IDNO SkipDriverInstall
      
      OpenZadig:
        ExecWait '"$INSTDIR\zadig.exe"'
        
      SkipDriverInstall:
    ${EndIf}
  ${Else}
    DetailPrint "WARNING: zadig.exe not found in installer!"
    MessageBox MB_OK "WARNING: Zadig driver installer is missing!$\n$\nYou will need to manually install WinUSB driver for your spectrometer.$\n$\nDownload Zadig from: https://zadig.akeo.ie/"
  ${EndIf}

SectionEnd

; Uninstaller Section
Section "Uninstall"
  Delete "$INSTDIR\Affilabs-Core.exe"
  Delete "$INSTDIR\zadig.exe"
  Delete "$INSTDIR\uninst.exe"

  ; Remove shortcuts
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

  ; Remove installation directory
  RMDir "$INSTDIR"

  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

  MessageBox MB_OK "${PRODUCT_NAME} has been uninstalled.$\n$\nNote: Ocean Optics WinUSB driver will remain installed.$\nTo remove it, use Zadig to replace with the original driver."

SectionEnd

; Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install the main Affilabs-Core application"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDriver} "Automatically install WinUSB driver for Ocean Optics spectrometer (Flame-T, USB4000) if detected"
!insertmacro MUI_FUNCTION_DESCRIPTION_END
