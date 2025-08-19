use framework "Foundation"
use scripting additions


property ca : a reference to current application
property NSData : a reference to ca's NSData
property NSDictionary : a reference to ca's NSDictionary
property NSJSONSerialization : a reference to ca's NSJSONSerialization
property NSString : a reference to ca's NSString
property NSUTF8StringEncoding : a reference to 4
property NSJSONWritingPrettyPrinted : a reference to 1


property msgName : "信息"
property prefBtn : "偏好设置..."

property loginBtn : "登录"
property logoutBtn : "注销"
property winGeneral : "通用"
property winAccounts : "帐户"
property cancelBtn : "Cancel"
property enableBonjour : "启用 Bonjour 即时通信"
property failLogin : "不活跃"
property buttonCreateAccount : "创建新 Apple ID…"
property buttonSkip : "以后"
property buttonSkip2 : "跳过"
property buttonCancel : "取消"
property buttonOk : "好"

property usEng : "美国"
property errorMsg : "您的 Apple ID 或密码不正确。"
property errMsgList : {"Your Apple ID or password was incorrect.", "An error occurred during authentication."}
property errMsg03 : "An error occurred during activation. Try again."

property tailOpened : false
property login_status : ""
property failedLoginTimes : 0

property sendBatchSize : 15

property imLoaded : false


on doSaveJson(j, f)
	--set home to the path to home folder
	--set f to the POSIX path of home & "running122.status"
	--set {theData, theError} to current application's NSJSONSerialization's dataWithJSONObject:statusRecord options:NSJSONWritingPrettyPrinted |error|:(reference)
	
	set theJSONData to NSJSONSerialization's dataWithJSONObject:j options:NSJSONWritingPrettyPrinted |error|:(missing value)
	theJSONData's writeToFile:f atomically:false
end doSaveJson


on convertASToJSON:someASThing saveTo:posixPath
	--convert to JSON data
	set {theData, theError} to current application's NSJSONSerialization's dataWithJSONObject:someASThing options:NSJSONWritingPrettyPrinted |error|:(reference)
	if theData is missing value then error (theError's localizedDescription() as text) number -10000
	if posixPath is missing value then -- return string
		-- convert data to a UTF8 string
		set someString to current application's NSString's alloc()'s initWithData:theData encoding:(current application's NSUTF8StringEncoding)
		return someString as text
	else
		-- write data to file
		set theResult to theData's writeToFile:posixPath atomically:true
		return theResult as boolean -- returns false if save failed
	end if
end convertASToJSON:saveTo:

-- 实现imessage apple id的空白登录，初始iMessage没有登录账号
-- 定义常量，messages账户登入／登出
property IMLoginSuccess : false

on startIMLogin(account)
	--set account to {"brightchangu@naver.com", "Tkdql0147!", 60,30}
	--set account to {"lr2h@naver.com", "Criminal0!", 60, 20}
	set appleId to item 1 of account
	set password_api to item 2 of account
	
	if password_api contains "----" then
		set applePwd to do shell script "echo \"" & password_api & "\"|awk '{split($1, arr, \"----\"); print arr[1]}'"
		set appleApi to do shell script "echo \"" & password_api & "\"|awk '{split($1, arr, \"----\"); print arr[2]}'"
	else
		set applePwd to password_api
		set appleApi to ""
	end if
	
	my log_event("开始登录iMessage ，使用ID: " & appleId & ",Pwd: " & applePwd & ",Api: " & appleApi)
	--my log_event("登录使用Apple ID：" & appleId)
	
	set maxWaitTime to 60
	set maxWaitStatus to 20
	
	tell application "Messages"
		activate
		set visible of window 1 to true
		--忽略异常情况
		ignoring application responses
			tell application "System Events"
				key code 53 # ESC
			end tell
		end ignoring
	end tell
	
	delay 1
	
	
	tell application "System Events"
		# 初始页面输入账号和密码，然后点击登录 
		tell process msgName
			set target_button to a reference to (first button whose name is buttonCreateAccount) of (splitter group 1) of (first window whose name is msgName)
			if target_button exists then
				click (first button whose name is buttonSkip) of (splitter group 1) of (first window whose name is msgName)
				delay 2
				--确定跳过。
				click (first button whose name is buttonSkip2) of (sheet 1) of (first window whose name is msgName)
				delay 2
				click (first button whose name is buttonCancel) of (sheet 1) of (first window whose name is msgName)
			end if
			
			
			set frontmost to true
			-- 打开账号设置窗口
			log "打开账号设置窗口"
			keystroke "," using {command down}
			delay 0.5
			
			-- 确认打开的是Accounts窗口
			set allWindows to every window
			set tgtWindowName to winAccounts
			set accountsWindow to (my searchWindow(allWindows, tgtWindowName))
			if accountsWindow = 0 then
				delay 0.5
				click (button winAccounts of toolbar 1 of window winGeneral)
				delay 1
			end if
			
			--关闭存在的警告窗口
			set target_button to a reference to (first button whose name is buttonCancel) of (sheet 1) of (first window whose name is winAccounts)
			if target_button exists then
				click target_button
				delay 1
			end if
			
			set target_button to (a reference to (first button whose name is "以后") of (sheet 1) of (first window whose name is winAccounts))
			if target_button exists then
				click target_button
				delay 0.3
			end if
			
			set target_button to a reference to (first button whose name is buttonOk) of (sheet 1) of (first window whose name is winAccounts)
			if target_button exists then
				click target_button
				delay 1
			end if
			
			set target_button to a reference to (first button whose name is buttonCancel) of group 2 of group 1 of UI element 1 of scroll area 1 of (sheet 1) of (first window whose name is winAccounts)
			if target_button exists then
				click target_button
				delay 1
			end if
			
			# 检测是否处于成功登录状态
			set allData to every UI element of UI element of row 1 of table 1 of scroll area 1 of group 1 of window winAccounts
			set allDataString to my toString(allData)
			if failLogin is in allDataString then
				log "login failed!"
				set login_status to "fail"
			else
				log "login sucessful!"
				set login_status to "succeed"
			end if
			
			if login_status = "succeed" then
				-- 已经登录成功了。
				set IMLoginSuccess to true
				return true
			else
				--button "Sign In" of group 1 of group 1 of window "Accounts" 
				--text field 1 of group 1 of group 1 of window "Accounts"
				--text field 2 of group 1 of group 1 of window "Accounts"
				try
					select row 1 of table 1 of scroll area 1 of group 1 of window winAccounts
					
					delay 0.1
					click text field 1 of group 1 of group 1 of window winAccounts
					
					set value of text field 1 of group 1 of group 1 of window winAccounts to appleId
					delay 0.1
					set value of text field 2 of group 1 of group 1 of window winAccounts to applePwd
					delay 0.1
					
					click text field 1 of group 1 of group 1 of window winAccounts
					delay 0.1
					keystroke "a"
					delay 0.1
					set value of text field 1 of group 1 of group 1 of window winAccounts to appleId
					delay 0.1
					
					click (button loginBtn of group 1 of group 1 of window winAccounts)
					delay 3
				end try
				
				-- 检查是否成功登录
				set login_try_status to false
				set login_busy_hidden to false
				set login_has_sheet to false
				
				-- 需要输入api的设备码
				set input_phone_code_finished to false
				set wait_count to 0
				set wait_total to 12
				repeat while wait_count < wait_total and input_phone_code_finished is false
					try
						if static text "输入发送至 " of group 2 of group 1 of UI element 1 of scroll area 1 of sheet 1 of window "帐户" exists then
							-- set device_code to do shell script "curl '" & appleApi & "' | sed 's/[^0-9]//g'"
							-- set device_code to do shell script "curl '" & appleApi & "' | grep -o '[0-9]\\{6\\}' | head -n 1 | sed 's/[^0-9]//g'"
							set device_code to do shell script "curl '" & appleApi & "' | grep -o '[0-9]\\{6\\}' | sed 's/[^0-9]//g'"
							if the length of device_code is 6 then
								keystroke device_code
								set input_phone_code_finished to true
							else
								set wait_count to wait_count + 1
								delay 5
							end if
						else
							set wait_count to wait_count + 1
							delay 5
						end if
					on error
						set wait_count to wait_count + 1
						delay 5
					end try
				end repeat
				
				delay 15
				
				
				repeat with chkBusy from 0 to maxWaitTime
					# 检测是否处于成功登录状态
					set target_button to (a reference to (first button whose name is buttonOk) of (sheet 1) of (first window whose name is winAccounts))
					if target_button exists then
						click target_button
						set login_has_sheet to true
						delay 0.5
					end if
					
					set target_button to (a reference to (first button whose name is "以后") of (sheet 1) of (first window whose name is winAccounts))
					if target_button exists then
						click target_button
						delay 0.3
					end if
					
					set target_button to (a reference to (first button whose name is buttonCancel) of (sheet 1) of (first window whose name is winAccounts))
					if target_button exists then
						click target_button
						set login_has_sheet to true
						delay 1
					end if
					
					
					set target_button to (a reference to (first button whose name is buttonCancel) of group 2 of group 1 of UI element 1 of scroll area 1 of (sheet 1) of (first window whose name is winAccounts))
					if target_button exists then
						click target_button
						set login_has_sheet to true
						delay 1
					end if
					
					
					set busyIndicator to (a reference to (first busy indicator) of (group 1) of (group 1) of (first window whose name is winAccounts))
					if busyIndicator exists then
						set login_busy_hidden to false
					else
						set login_busy_hidden to true
					end if
					
					if login_busy_hidden then
						
						set checkStatusTimes to 5
						if login_has_sheet is false then
							set checkStatusTimes to maxWaitStatus
						end if
						
						repeat with chkStatus from 0 to checkStatusTimes
							set allData to every UI element of UI element of row 1 of table 1 of scroll area 1 of group 1 of window winAccounts
							set allDataString to my toString(allData)
							if failLogin is in allDataString then
								log "try login failed!"
								set login_try_status to false
							else
								log "try login sucessful!"
								set login_try_status to true
								exit repeat
							end if
							delay 1
							log chkStatus
						end repeat
						
						
						--登录状态已经完成了。直接退出。
						exit repeat
						
					end if
					
					delay 1
				end repeat
				
				
				if login_try_status is false then
					set IMLoginSuccess to false
					click (button 1 of window winAccounts)
					return false
				else
					# 确保页面处于账户登录页面
					repeat with cnt_chk from 0 to 6
						delay 3
						if exists tab group 1 of group 1 of window winAccounts then # 如果有tab group 1说明登录成功，并且当前在登录账户页面
							click (button 1 of window winAccounts)
							set IMLoginSuccess to true
							return true
						end if
					end repeat
					click (button 1 of window winAccounts)
					return false
				end if
			end if
			
		end tell
	end tell
	
end startIMLogin


on checkIMLoaded()
	--第一次打开iMessage
	if imLoaded is false then
		tell application "Messages"
			activate
			ignoring application responses
				tell application "System Events"
					key code 53 # ESC
				end tell
			end ignoring
		end tell
		delay 10
		
		set imLoaded to true
	end if
	
end checkIMLoaded


on checkIMLogin(curActivated)
	
	tell application "Messages"
		activate
		set visible of window 1 to true
		--忽略异常情况
		ignoring application responses
			tell application "System Events"
				key code 53 # ESC
			end tell
		end ignoring
	end tell
	
	delay 1
	
	tell application "System Events"
		# 初始页面输入账号和密码，然后点击登录 
		tell process msgName
			set target_button to a reference to (first button whose name is buttonCreateAccount) of (splitter group 1) of (first window whose name is msgName)
			if target_button exists then
				
				if curActivated then
					set IMLoginSuccess to false
					return false
				end if
				
				click (first button whose name is buttonSkip) of (splitter group 1) of (first window whose name is msgName)
				delay 2
				--确定跳过。
				click (first button whose name is buttonSkip2) of (sheet 1) of (first window whose name is msgName)
				delay 2
				click (first button whose name is buttonCancel) of (sheet 1) of (first window whose name is msgName)
			end if
			
			
			set frontmost to true
			-- 打开账号设置窗口
			log "打开账号设置窗口"
			keystroke "," using {command down}
			delay 0.5
			
			--关闭音效
			-- 确认打开的是通用窗口
			try
				set allWindows to every window
				set tgtWindowName to winGeneral
				set generalsWindow to (my searchWindow(allWindows, tgtWindowName))
				if generalsWindow = 0 then
					delay 0.5
					click (button winGeneral of toolbar 1 of window winAccounts)
					delay 1
				end if
				set theCheckbox to checkbox "播放声音效果" of group 1 of window winGeneral
				tell theCheckbox
					if (its value as boolean) then click theCheckbox
				end tell
			end try
			
			delay 0.5
			
			-- 确认打开的是Accounts窗口
			set allWindows to every window
			set tgtWindowName to winAccounts
			set accountsWindow to (my searchWindow(allWindows, tgtWindowName))
			if accountsWindow = 0 then
				delay 0.5
				click (button winAccounts of toolbar 1 of window winGeneral)
				delay 1
			end if
			
			--关闭存在的警告窗口
			set target_button to a reference to (first button whose name is buttonOk) of (sheet 1) of (first window whose name is winAccounts)
			if target_button exists then
				click target_button
				delay 1
			end if
			
			# 检测是否处于成功登录状态
			set allData to every UI element of UI element of row 1 of table 1 of scroll area 1 of group 1 of window winAccounts
			set allDataString to my toString(allData)
			if failLogin is in allDataString then
				log "login failed!"
				set login_status to "fail"
				set IMLoginSuccess to false
				return false
			else
				log "login sucessful!"
				click (button 1 of window winAccounts)
				set login_status to "succeed"
				set IMLoginSuccess to true
				return true
			end if
		end tell
	end tell
	
end checkIMLogin


on testWindow(showEveryThing)
	tell application "System Events"
		# 初始页面输入账号和密码，然后点击登录 
		tell process msgName
			set allWindows to every window
			repeat with curWindow in allWindows
				--log toString(curWindow)
				if showEveryThing then
					tell curWindow
						repeat with uiElem in entire contents as list
							--set classNames to classNames & (class of uiElem as string)
							uiElem
							--log toString(uiElem)
						end repeat
					end tell
				end if
			end repeat
		end tell
	end tell
end testWindow

on FileExists(theFile) -- (String) as Boolean
	tell application "System Events"
		if exists file theFile then
			return true
		else
			return false
		end if
	end tell
end FileExists


on JSONtoRecord from fp
	local fp
	
	set JSONdata to NSData's dataWithContentsOfFile:fp
	
	set [x, e] to (NSJSONSerialization's ¬
		JSONObjectWithData:JSONdata ¬
			options:0 ¬
			|error|:(reference))
	
	if e ≠ missing value then error e
	
	tell x to if its isKindOfClass:NSDictionary then ¬
		return it as record
	
	x as list
end JSONtoRecord

on JSONtoList from fp
	local fp
	
	set JSONdata to NSData's dataWithContentsOfFile:fp
	
	set [x, e] to (NSJSONSerialization's ¬
		JSONObjectWithData:JSONdata ¬
			options:0 ¬
			|error|:(reference))
	
	if e ≠ missing value then error e
	
	return x as list
end JSONtoList




# Logs a text representation of the specified object or objects, which may be of any type, typically for debugging.
# Works hard to find a meaningful text representation of each object.
# SYNOPSIS
#   dlog(anyObjOrListOfObjects)
# USE EXAMPLES
#   dlog("before")  # single object
#     dlog({ "front window: ", front window }) # list of objects
# SETUP
#   At the top of your script, define global variable DLOG_TARGETS and set it to a *list* of targets (even if you only have 1 target).
#     set DLOG_TARGETS to {} # must be a list with any combination of: "log", "syslog", "alert", <posixFilePath>
#   An *empty* list means that logging should be *disabled*.
#   If you specify a POSIX file path, the file will be *appended* to; variable references in the path
#   are allowed, and as a courtesy the path may start with "~" to refer to your home dir.
#   Caveat: while you can *remove* the variable definition to disable logging, you'll take an additional performance hit.
# SETUP EXAMPLES
#    For instance, to use both AppleScript's log command *and* display a GUI alert, use:
#       set DLOG_TARGETS to { "log", "alert" }
# Note: 
#   - Since the subroutine is still called even when DLOG_TARGETS is an empty list, 
#     you pay a performancy penalty for leaving dlog() calls in your code.
#   - Unlike with the built-in log() method, you MUST use parentheses around the parameter.
#   - To specify more than one object, pass a *list*. Note that while you could try to synthesize a single
#     output string by concatenation yourself, you'd lose the benefit of this subroutine's ability to derive
#     readable text representations even of objects that can't simply be converted with `as text`.
on dlog(anyObjOrListOfObjects)
	global DLOG_TARGETS
	try
		if length of DLOG_TARGETS is 0 then return
	on error
		return
	end try
	# The following tries hard to derive a readable representation from the input object(s).
	if class of anyObjOrListOfObjects is not list then set anyObjOrListOfObjects to {anyObjOrListOfObjects}
	local lst, i, txt, errMsg, orgTids, oName, oId, prefix, logTarget, txtCombined, prefixTime, prefixDateTime
	set lst to {}
	repeat with anyObj in anyObjOrListOfObjects
		set txt to ""
		repeat with i from 1 to 2
			try
				if i is 1 then
					if class of anyObj is list then
						set {orgTids, AppleScript's text item delimiters} to {AppleScript's text item delimiters, {", "}} # '
						set txt to ("{" & anyObj as string) & "}"
						set AppleScript's text item delimiters to orgTids # '
					else
						set txt to anyObj as string
					end if
				else
					set txt to properties of anyObj as string
				end if
			on error errMsg
				# Trick for records and record-*like* objects:
				# We exploit the fact that the error message contains the desired string representation of the record, so we extract it from there. This (still) works as of AS 2.3 (OS X 10.9).
				try
					set txt to do shell script "egrep -o '\\{.*\\}' <<< " & quoted form of errMsg
				end try
			end try
			if txt is not "" then exit repeat
		end repeat
		set prefix to ""
		if class of anyObj is not in {text, integer, real, boolean, date, list, record} and anyObj is not missing value then
			set prefix to "[" & class of anyObj
			set oName to ""
			set oId to ""
			try
				set oName to name of anyObj
				if oName is not missing value then set prefix to prefix & " name=\"" & oName & "\""
			end try
			try
				set oId to id of anyObj
				if oId is not missing value then set prefix to prefix & " id=" & oId
			end try
			set prefix to prefix & "] "
			set txt to prefix & txt
		end if
		set lst to lst & txt
	end repeat
	set {orgTids, AppleScript's text item delimiters} to {AppleScript's text item delimiters, {" "}} # '
	set txtCombined to lst as string
	set prefixTime to "[" & time string of (current date) & "] "
	set prefixDateTime to "[" & short date string of (current date) & " " & text 2 thru -1 of prefixTime
	set AppleScript's text item delimiters to orgTids # '
	# Log the result to every target specified.
	repeat with logTarget in DLOG_TARGETS
		if contents of logTarget is "log" then
			log prefixTime & txtCombined
		else if contents of logTarget is "alert" then
			display alert prefixTime & txtCombined
		else if contents of logTarget is "syslog" then
			do shell script "logger -t " & quoted form of ("AS: " & (name of me)) & " " & quoted form of txtCombined
		else # assumed to be a POSIX file path to *append* to.
			set fPath to contents of logTarget
			if fPath starts with "~/" then set fPath to "$HOME/" & text 3 thru -1 of fPath
			do shell script "printf '%s\\n' " & quoted form of (prefixDateTime & txtCombined) & " >> \"" & fPath & "\""
		end if
	end repeat
end dlog
# 用于applescript的脚本调试的两个函数，非常有用
# dlog可以自动记录脚本执行的记录到home指定的文件
# toString可以把任何的object转化为string，从而方便调试
# 参考：https://stackoverflow.com/questions/13653358/how-to-log-objects-to-a-console-with-applescript?utm_medium=organic&utm_source=google_rich_qa&utm_campaign=google_rich_qa


# Converts the specified object - which may be of any type - into a string representation for logging/debugging.
# Tries hard to find a readable representation - sadly, simple conversion with `as text` mostly doesn't work with non-primitive types.
# An attempt is made to list the properties of non-primitive types (does not always work), and the result is prefixed with the type (class) name
# and, if present, the object's name and ID.
# EXAMPLE
#       toString(path to desktop)  # -> "[alias] Macintosh HD:Users:mklement:Desktop:"
# To test this subroutine and see the various representations, use the following:
#   repeat with elem in {42, 3.14, "two", true, (current date), {"one", "two", "three"}, {one:1, two:"deux", three:false}, missing value, me,  path to desktop, front window of application (path to frontmost application as text)}
#       log toString(contents of elem)
#   end repeat
on toString(anyObj)
	local i, txt, errMsg, orgTids, oName, oId, prefix
	set txt to ""
	repeat with i from 1 to 2
		try
			if i is 1 then
				if class of anyObj is list then
					set {orgTids, AppleScript's text item delimiters} to {AppleScript's text item delimiters, {", "}}
					set txt to ("{" & anyObj as string) & "}"
					set AppleScript's text item delimiters to orgTids # '
				else
					set txt to anyObj as string
				end if
			else
				set txt to properties of anyObj as string
			end if
		on error errMsg
			# Trick for records and record-*like* objects:
			# We exploit the fact that the error message contains the desired string representation of the record, so we extract it from there. This (still) works as of AS 2.3 (OS X 10.9).
			try
				set txt to do shell script "egrep -o '\\{.*\\}' <<< " & quoted form of errMsg
			end try
		end try
		if txt is not "" then exit repeat
	end repeat
	set prefix to ""
	if class of anyObj is not in {text, integer, real, boolean, date, list, record} and anyObj is not missing value then
		set prefix to "[" & class of anyObj
		set oName to ""
		set oId to ""
		try
			set oName to name of anyObj
			if oName is not missing value then set prefix to prefix & " name=\"" & oName & "\""
		end try
		try
			set oId to id of anyObj
			if oId is not missing value then set prefix to prefix & " id=" & oId
		end try
		set prefix to prefix & "] "
	end if
	return prefix & txt
end toString

--set this_text to "---1---"
--trim_line(this_text, "-", 0)
on trim_line(this_text, trim_chars, trim_indicator)
	# 0 = beginning, 1 = end, 2 = both
	set x to the length of the trim_chars
	# trim beginning
	if the trim_indicator is in {0, 2} then
		repeat while this_text begins with the trim_chars
			try
				set this_text to characters (x + 1) thru -1 of this_text as string
			on error
				return ""
			end try
		end repeat
	end if
	# trim ending
	
	if the trim_indicator is in {1, 2} then
		repeat while this_text ends with the trim_chars
			try
				set this_text to characters 1 thru -(x + 1) of this_text as string
			on error
				return ""
			end try
		end repeat
	end if
	return this_text
end trim_line



# write data to file
on write_to_file(this_data, target_file, append_data)
	try
		set toWrtData to ""
		set toWrtData to toWrtData & item 1 of this_data
		set toWrtData to toWrtData & "," & item 2 of this_data
		set the open_target_file to open for access POSIX file target_file with write permission
		if append_data is false then
			set eof of the open_target_file to 0
		end if
		write toWrtData to the open_target_file starting at eof
		close access the open_target_file
		return true
	on error e
		log e
		try
			close access file target_file
		end try
		return false
	end try
end write_to_file


-- 查找目标窗口是否存在
on searchWindow(allWindows, tgtWindowName)
	repeat with curWindow in allWindows
		if name of curWindow = tgtWindowName then
			return 1
		end if
	end repeat
	return 0
end searchWindow




-- Function to get all accounts labels
on getLabels(filePath)
	-- Define an empty list that will contains all labels 
	set labels to {}
	tell application "System Events"
		-- Get the plist file content and save it in fileContent variable
		set fileContent to property list items of contents of property list file filePath
		-- Scan each file row and add each label to labels list
		repeat with account in fileContent
			set label to name of account
			set end of labels to label
		end repeat
	end tell
	-- Return the list with all labels
	return labels
end getLabels


-- Function to get email and password of a selected account
on getAccountInfo(filePath, selectedAccount)
	tell application "System Events"
		-- Open the plist file and get its content
		set fileContent to property list file (filePath)
		-- Get information based on selectedAccount
		set info to value of property list item selectedAccount of fileContent
	end tell
	-- Return the info array
	return info
end getAccountInfo

# Function to get the absolute path of a file
on getPath(fileName)
	tell application "Finder"
		# Get the absolute path of parent folder of your AppleScript file.
		set _path to parent of (path to me) as string
		# Transform the path in a POSIX path
		set _path to POSIX path of _path
		# Concatenate the folder path with the file name
		set _path to _path & fileName
		# Return the POSIX path of plist file with name 'filename' that is inside the folder of AppleScript file
		return _path
	end tell
end getPath

on zero_pad(value, string_length)
	set string_zeroes to ""
	set digits_to_pad to string_length - (length of (value as string))
	if digits_to_pad > 0 then
		repeat digits_to_pad times
			set string_zeroes to string_zeroes & "0" as string
		end repeat
	end if
	set padded_value to string_zeroes & value as string
	return padded_value
end zero_pad

on GetCurrentTime()
	set now to (current date)
	
	set result to (year of now as integer) as string
	set result to result & "-"
	set result to result & zero_pad(month of now as integer, 2)
	set result to result & "-"
	set result to result & zero_pad(day of now as integer, 2)
	set result to result & " "
	set result to result & zero_pad(hours of now as integer, 2)
	set result to result & ":"
	set result to result & zero_pad(minutes of now as integer, 2)
	set result to result & ":"
	set result to result & zero_pad(seconds of now as integer, 2)
	
	return result
end GetCurrentTime

on convertNumberToString(theNumber)
	set theNumberString to theNumber as string
	set theOffset to offset of "E" in theNumberString
	if theOffset = 0 then return theNumberString
	set thePrefix to text 1 thru (theOffset - 1) of theNumberString
	set theConvertedNumberPrefix to ""
	if thePrefix begins with "-" then
		set theConvertedNumberPrefix to "-"
		if thePrefix = "-" then
			set thePrefix to ""
		else
			set thePrefix to text 2 thru -1 of thePrefix
		end if
	end if
	set theDecimalAdjustment to (text (theOffset + 1) thru -1 of theNumberString) as number
	set isNegativeDecimalAdjustment to theDecimalAdjustment is less than 0
	if isNegativeDecimalAdjustment then
		set thePrefix to (reverse of (characters of thePrefix)) as string
		set theDecimalAdjustment to -theDecimalAdjustment
	end if
	set theDecimalOffset to offset of "." in thePrefix
	if theDecimalOffset = 0 then
		set theFirstPart to ""
	else
		set theFirstPart to text 1 thru (theDecimalOffset - 1) of thePrefix
	end if
	set theSecondPart to text (theDecimalOffset + 1) thru -1 of thePrefix
	set theConvertedNumber to theFirstPart
	set theRepeatCount to theDecimalAdjustment
	if (length of theSecondPart) is greater than theRepeatCount then set theRepeatCount to length of theSecondPart
	repeat with a from 1 to theRepeatCount
		try
			set theConvertedNumber to theConvertedNumber & character a of theSecondPart
		on error
			set theConvertedNumber to theConvertedNumber & "0"
		end try
		if a = theDecimalAdjustment and a is not equal to (length of theSecondPart) then set theConvertedNumber to theConvertedNumber & "."
	end repeat
	if theConvertedNumber ends with "." then set theConvertedNumber to theConvertedNumber & "0"
	if isNegativeDecimalAdjustment then set theConvertedNumber to (reverse of (characters of theConvertedNumber)) as string
	return theConvertedNumberPrefix & theConvertedNumber
end convertNumberToString

on log_event(theMessage)
	log theMessage
	set theLine to (do shell script ¬
		"date  +'%Y-%m-%d %H:%M:%S'" as string) ¬
		& " " & theMessage
	do shell script "echo " & theLine & ¬
		" >> /Users/cc/logs"
end log_event
