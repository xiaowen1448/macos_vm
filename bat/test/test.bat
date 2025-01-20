@setlocal enabledelayedexpansion
@echo off
set  BASE_DIR=%cd%
set TEMPLATE_PATH=%BASE_DIR%\..\..\TemplateVM\macos10.15
REM Set the storage path of the target VM
set VM_BASE_PATH=%BASE_DIR%\..\..\NewVM
set ISO_BASE_HOME=%BASE_DIR%\..\..\iso
REM Set the number of virtual machines that need to be created
for /r "%VM_BASE_PATH%" %%f in (*.*) do (
   rem    "%VMRUN_PATH%" start "%%f" nogui
   if /i "%%~xf"==".vmx"  (
       echo %%f------------
    )else if /i "%%~xf"==".nvram" (
      echo %%f=========
    )else (
   rem   echo Value is unknown
)
)

pause
