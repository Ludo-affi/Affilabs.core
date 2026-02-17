; Affilabs-Core NSIS Installer Script
; Includes automatic USB4000 driver installation via Zadig

!include "MUI2.nsh"
!include "LogicLib.nsh"

; Installer Information
!define PRODUCT_NAME "Affilabs-Core"
!define PRODUCT_VERSION "2.0.5 beta"
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
    DetailPrint "Zadig driver tool available"
    MessageBox MB_YESNO "Would you like to install the WinUSB driver for Ocean Optics spectrometer now?$\n$\n(Connect your spectrometer first if possible)" IDYES LaunchZadig IDNO SkipDriver
    
    LaunchZadig:
      DetailPrint "Launching Zadig..."
      MessageBox MB_OK "Zadig will now open.$\n$\nSteps to install WinUSB driver:$\n1. Connect your Ocean Optics spectrometer$\n2. Click the refresh icon if device doesn't appear$\n3. Select your device (USB4000, Flame-T, etc.)$\n4. Select 'WinUSB' from the driver dropdown$\n5. Click 'Install Driver'$\n$\nClose Zadig when done."
      ExecWait '"$INSTDIR\zadig.exe"'
      
    SkipDriver:
      DetailPrint "Zadig available at: $INSTDIR\zadig.exe"
  ${Else}
    DetailPrint "WARNING: zadig.exe not found"
    MessageBox MB_OK "WARNING: Zadig driver tool is missing!$\n$\nYou can download it from: https://zadig.akeo.ie/$\n$\nTo install WinUSB driver for your spectrometer, run Zadig manually."
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
