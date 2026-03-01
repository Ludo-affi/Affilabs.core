; Affilabs-Core NSIS Installer Script
; Includes automatic USB4000 driver installation via Zadig

!include "MUI2.nsh"
!include "LogicLib.nsh"

; Installer Information
!define PRODUCT_NAME "Affilabs-Core"
!define PRODUCT_VERSION "2.0.5"
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

  ; Copy Zadig for USB driver installation (required for Ocean Optics spectrometer)
  ${If} ${FileExists} "installer_files\zadig.exe"
    File "installer_files\zadig.exe"
    DetailPrint "Zadig USB driver tool included."
  ${Else}
    DetailPrint "WARNING: zadig.exe not found in installer_files\ — USB driver setup skipped."
  ${EndIf}

  ; Create shortcuts
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\Affilabs-Core.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall.lnk" "$INSTDIR\uninst.exe"
  CreateShortCut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\Affilabs-Core.exe"

  ; Add a "Install USB Driver" shortcut to Start Menu (so users can re-run Zadig any time)
  ${If} ${FileExists} "$INSTDIR\zadig.exe"
    CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Install USB Driver (Zadig).lnk" "$INSTDIR\zadig.exe"
  ${EndIf}

  ; Write uninstaller
  WriteUninstaller "$INSTDIR\uninst.exe"

  ; Write registry keys
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\Affilabs-Core.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"

  ; -----------------------------------------------------------------------
  ; USB Driver Setup — required for Ocean Optics spectrometer (Flame-T / USB4000)
  ; Zadig replaces the default Ocean Optics driver with WinUSB so AffiLabs.core
  ; can communicate with the spectrometer via libusb.
  ; -----------------------------------------------------------------------
  ${If} ${FileExists} "$INSTDIR\zadig.exe"
    MessageBox MB_YESNO \
      "USB Driver Setup (required for spectrometer)$\n$\n\
AffiLabs.core uses the WinUSB driver to communicate with your Ocean Optics spectrometer (Flame-T / USB4000).$\n$\n\
The Zadig tool installs this driver in 3 clicks. Without it, the software cannot detect the spectrometer.$\n$\n\
Would you like to run Zadig now to install the USB driver?" \
      IDYES LaunchZadig IDNO SkipZadig

    LaunchZadig:
      MessageBox MB_OK \
        "Zadig will now open.$\n$\n\
Steps (takes ~30 seconds):$\n\
  1. Connect your spectrometer to USB if not already done$\n\
  2. In Zadig: open the Device menu → tick 'List All Devices'$\n\
  3. Select your spectrometer (USB4000, Flame-T, OceanOptics...)(4. Make sure 'WinUSB' is selected in the driver dropdown$\n\
  5. Click 'Install Driver' and wait for the green confirmation$\n\
  6. Close Zadig when done, then launch AffiLabs.core$\n$\n\
Tip: You can re-run Zadig anytime from Start → ${PRODUCT_NAME} → Install USB Driver (Zadig)."
      ExecWait '"$INSTDIR\zadig.exe"'

    SkipZadig:
      DetailPrint "USB driver setup: skipped or completed."
  ${Else}
    ; zadig.exe missing from the installer package — fall back to web link guidance
    MessageBox MB_OK \
      "USB Driver Setup (required for spectrometer)$\n$\n\
AffiLabs.core needs the WinUSB driver to detect the spectrometer.$\n$\n\
Please download Zadig from https://zadig.akeo.ie and run it:$\n\
  1. Open Zadig → Device menu → List All Devices$\n\
  2. Select your spectrometer$\n\
  3. Choose WinUSB → Install Driver$\n$\n\
This step is required before the spectrometer will appear in software."
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
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Install USB Driver (Zadig).lnk"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

  ; Remove installation directory
  ; Clean up PyInstaller extract folder (system/) - safe to always delete
  RMDir /r "$INSTDIR\system"
  ; Clean up app-generated runtime files (logs, config cache)
  RMDir /r "$INSTDIR\generated-files"
  RMDir /r "$INSTDIR\config"
  ; Leave user data files (cycle_templates.json, user_profiles.json,
  ; queue_presets.json, license.json) — they hold the customer's work.
  RMDir "$INSTDIR"

  ; Remove registry keys
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"

  MessageBox MB_OK "${PRODUCT_NAME} has been uninstalled.$\n$\nNote: the WinUSB spectrometer driver installed by Zadig remains active.$\nTo revert to the original Ocean Optics driver, re-run Zadig and select 'libusb-win32' or the OEM driver."

SectionEnd

; Section Descriptions
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Install the main Affilabs-Core application"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDriver} "Automatically install WinUSB driver for Ocean Optics spectrometer (Flame-T, USB4000) if detected"
!insertmacro MUI_FUNCTION_DESCRIPTION_END
