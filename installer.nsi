; Affilabs-Core NSIS Installer Script
; Includes automatic USB4000 driver installation via Zadig

!include "MUI2.nsh"
!include "LogicLib.nsh"

; Installer Information
!define PRODUCT_NAME "Affilabs-Core"
!define PRODUCT_VERSION "1.0.2"
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
  File "dist\Affilabs-Core.exe"

  ; Copy Zadig for driver installation
  File "installer_files\zadig.exe"

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

Section "USB4000 Spectrometer Driver" SecDriver
  DetailPrint "Checking for USB4000 spectrometer..."

  ; Check if USB4000 is connected using Zadig's list command
  nsExec::ExecToStack '"$INSTDIR\zadig.exe" --list-devices'
  Pop $0 ; Return code
  Pop $1 ; Output

  ; Check if USB4000 is in the device list
  ${If} $1 != ""
    StrCpy $2 $1 7 ; Get first 7 chars
    ${If} $2 == "USB4000"
      DetailPrint "USB4000 detected! Installing WinUSB driver..."

      ; Install WinUSB driver automatically for USB4000
      ; Parameters: --device <name> --driver <winusb|libusbk|libusb0> --install
      nsExec::ExecToLog '"$INSTDIR\zadig.exe" --device "USB4000" --driver winusb --install --timeout 60'
      Pop $0

      ${If} $0 == 0
        DetailPrint "USB4000 driver installed successfully!"
        MessageBox MB_OK "USB4000 WinUSB driver installed successfully!$\n$\nYour spectrometer is ready to use."
      ${Else}
        DetailPrint "Automatic driver installation failed (code: $0)"
        MessageBox MB_YESNO "Automatic USB4000 driver installation encountered an issue.$\n$\nWould you like to install the driver manually using Zadig?" IDYES RunZadigManual
        Goto SkipManual

        RunZadigManual:
          DetailPrint "Launching Zadig for manual driver installation..."
          MessageBox MB_OK "Zadig will now open.$\n$\nSteps:$\n1. Select 'USB4000' from the device list$\n2. Ensure 'WinUSB' is selected as driver$\n3. Click 'Install Driver'$\n4. Wait for completion"
          ExecWait '"$INSTDIR\zadig.exe"'

        SkipManual:
      ${EndIf}
    ${Else}
      DetailPrint "USB4000 not currently connected"
      MessageBox MB_YESNO "USB4000 spectrometer not detected.$\n$\nIf you plan to use a USB4000 spectrometer, you'll need to install the WinUSB driver.$\n$\nWould you like to run Zadig now to install the driver when you connect it?" IDYES RunZadigLater IDNO SkipZadig

      RunZadigLater:
        DetailPrint "User will run Zadig later"
        MessageBox MB_OK "Zadig has been installed to:$\n$INSTDIR\zadig.exe$\n$\nRun it after connecting your USB4000 to install the driver."
        Goto SkipZadig

      SkipZadig:
        DetailPrint "Skipping driver installation for now"
    ${EndIf}
  ${Else}
    DetailPrint "Could not query devices, Zadig may require user interaction"
    MessageBox MB_YESNO "Unable to automatically detect USB devices.$\n$\nWould you like to open Zadig to check for the USB4000 driver?" IDYES OpenZadig IDNO SkipDriverInstall

    OpenZadig:
      ExecWait '"$INSTDIR\zadig.exe"'

    SkipDriverInstall:
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

  MessageBox MB_OK "${PRODUCT_NAME} has been uninstalled.$\n$\nNote: USB4000 driver will remain installed.$\nTo remove it, use Zadig to replace with the original driver."

SectionEnd

; Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install the main Affilabs-Core application"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDriver} "Automatically install WinUSB driver for USB4000 spectrometer (if detected)"
!insertmacro MUI_FUNCTION_DESCRIPTION_END
