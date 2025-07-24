@echo off
setlocal enabledelayedexpansion


set root_dir="D:\macos_vm\NewVM"

 
set "max_num=0"
for /d %%D in ("%root_dir%\VM_*") do (
    set "folder=%%~nxD"
    for /f "tokens=2 delims=_" %%A in ("!folder!") do (
        set /a "num=%%A"
        if !num! GTR !max_num! set "max_num=!num!"
    )
)

echo VM max number is : %max_num%

set /a "new_count=2"

for /l %%I in (1,1,%new_count%) do (
    set /a "next_num=max_num+%%I"
    set "new_dir=%root_dir%\VM_!next_num!"
    if not exist "!new_dir!" (
        echo mkdir folder: !new_dir!
        md "!new_dir!"
    )
)

echo Finished!
