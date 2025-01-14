@setlocal enabledelayedexpansion
@echo off	
REM  定义原始文件config.plist
set pdir=D:\macos_vm\plist\config\
set pdir_output=D:\macos_vm\plist\chengpin\
REM   读取原始文本五码文件
REM :846878D3B2B4:FV984520CNDHWVQDY:FVFXP1HVHV22:Mac-B4831CEBD52A0C4C:MacBookPro14,1:
REM  Model: $1 , Board-id:$2 , SerialNumber:$3   ,CustomUUID:$4 ,ROM:$5 , BoardSerialNumber:$6  ,SmUUID:$7
set count=0
   for /f "tokens=* delims=" %%a in (5.txt) do (
	REM  $2 :ROM ,$3:BoardSerialNumber,$4:SerialNumber,$5:Board-id,$6:Model
	rem sed "s/$1/MacBookPro14,1/" test.txt
	rem  echo The first column is: %RESULT%
	rem  echo %%a |awk  -F":" "{ print $3 }"
	rem  echo %%a |awk  -F":" "{ print $4 }"
	rem  echo %%a |awk  -F":" "{ print $5 }"
	rem  echo %%a |awk  -F":" "{ print $6 }"
	set /a count+=1
	REM echo !count!
	copy /y  !pdir!config.plist    !pdir_output!config_!count!.plist >> null 
	rem  echo  The file has been copied !pdir_output!config_!count!.plist
	REM  $2 :ROM 
	for /f %%i in ('echo %%a ^| awk  -F":" "{ print $2 }"') do set ROM=%%i
	REM echo ROM is: !ROM!
	REM  传入rom文件，加密为base64，传入clover文件
	REM  powershell -Command "[Convert]::ToBase64String([byte[]] ('!ROM!' -split '(.{2})' | Where-Object { $_ -ne '' } | ForEach-Object { [Convert]::ToByte($_, 16) }))"
	for /f %%i in ('powershell -Command "[Convert]::ToBase64String([byte[]] ('!ROM!' -split '(.{2})' | Where-Object { $_ -ne '' } | ForEach-Object { [Convert]::ToByte($_, 16) }))"') do set CLOVER_NAME=%%i
	SET CLOVER_NAME=!CLOVER_NAME!
	rem  uuidgen  powershell -Command  [guid]::NewGuid()
	rem  VisualStudio
	for /f %%i in ('powershell -Command "$string = '!CLOVER_NAME!'; $string -replace '/', '\/'"') do set CLOVER_NAME=%%i
	SET CLOVER_NAME=!CLOVER_NAME!
	echo  CLOVER  ROM :!CLOVER_NAME!
	REM $3:BoardSerialNumber
	for /f %%i in ('echo %%a ^| awk  -F":" "{ print $3 }"') do set BoardSerialNumber=%%i
	REM echo BoardSerialNumber is: !BoardSerialNumber!
	REM $4:SerialNumber
	for /f %%i in ('echo %%a ^| awk  -F":" "{ print $4 }"') do set SerialNumber=%%i
	REM echo SerialNumber is: !SerialNumber!
	REM $5:Board-id
	for /f %%i in ('echo %%a ^| awk  -F":" "{ print $5 }"') do set Board-id=%%i
	REM echo Board-id is: !Board-id!
	REM $6:Model
	for /f %%i in ('echo %%a ^| awk  -F":" "{ print $6 }"') do set Model=%%i
	REM  echo Model is: !Model!
	REM CustomUUID
	for /f %%i in ('uuidgen') do set CustomUUID=%%i
	SET  CustomUUID=!CustomUUID!
	REM echo CustomUUID is: !CustomUUID!
	REM SmUUID
	for /f %%i in ('uuidgen') do set UUID=%%i
	SET  SmUUID=!UUID!
	REM  echo SmUUID is: !SmUUID!
	sed -i  "s/$1/!Model!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$2/!Board-id!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$3/!SerialNumber!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$4/!CustomUUID!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$5/!CLOVER_NAME!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$6/!BoardSerialNumber!/g" !pdir_output!config_!count!.plist
	 del sed*
	sed -i  "s/$7/!SmUUID!/g"  !pdir_output!config_!count!.plist
	 del sed*
	echo  !pdir_output!config_!count!.plist  has been generated successfully!
	
	 REM delete  sed temp files 
 )
echo   All Config files Written done ..................
pause

