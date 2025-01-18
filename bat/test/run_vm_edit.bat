@setlocal enabledelayedexpansion
@echo off
set plist_path=D:\macos_vm\plist\chengpin

for /f "tokens=* delims=" %%a in (ip_list.txt) do (
	set /a plist_num+=1
	ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/mount_efi.sh' >> run.log  2>&1
	scp plist_path\config_!plist_num!.plist wx@%%a :/Volumes/EFI/CLOVER/config.plist >> run.log  2>&1
	ssh  -o StrictHostKeyChecking=no  wx@%%a  '/Users/wx/reboot.sh'  >> run.log  2>&1
) 