@setlocal enabledelayedexpansion
@echo off
set plist_path=D:\macos_vm\plist\chengpin

 ssh  -o StrictHostKeyChecking=no  wx@192.168.119.156  '/Users/wx/mount_efi.sh'
 
 ssh  -o StrictHostKeyChecking=no  wx@192.168.119.157 '/Users/wx/mount_efi.sh'
 
 scp %plist_path%\config_1.plist  wx@192.168.119.156:/Volumes/EFI/CLOVER/config.plist
 
 scp %plist_path%\config_2.plist  wx@192.168.119.157:/Volumes/EFI/CLOVER/config.plist
 
 ssh  -o StrictHostKeyChecking=no  wx@192.168.119.156  '/Users/wx/reboot.sh' 
 
 ssh  -o StrictHostKeyChecking=no  wx@192.168.119.157 '/Users/wx/reboot.sh'
 
 
 pause