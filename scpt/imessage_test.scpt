-- Apple ID 自动登录完整脚本（增强版）

property executionResults : {}
property errorMessages : {}

property overallSuccess : true
property accountsTabOpened : false
property maxLoginAttempts : 5 -- 增加最大登录尝试次数
property currentLoginAttempt : 0
property appleID : ""
property userPassword : ""
property debugEnabled : true
property debugLevel : "INFO" -- DEBUG, INFO, WARN, ERROR

-- 监控配置参数（移除超时限制）
-- property loginTimeout : 60 -- 已移除：单次登录操作超时时间
-- property verificationTimeout : 120 -- 已移除：验证码等待超时时间
property uiResponseTimeout : 10 -- UI响应超时时间（秒）
property retryDelay : 5 -- 重试间隔时间（秒）
property maxPasswordErrors : 3 -- 最大密码错误次数
property maxVerificationErrors : 2 -- 最大验证失败次数
property loginStatusCheckInterval : 2 -- 登录状态检查间隔（秒）
property loginStatusMaxChecks : 15 -- 登录状态最大检查次数
property customVerificationCode : "666666" -- 自定义验证码，如果为空则使用默认测试验证码
property verificationCodeMode : 1 -- 验证码获取方式：1=自定义输入，2=API获取
property appleIdFilePath : "~/Documents/appleid.txt" -- appleid.txt文件路径，空值时提示没有appleid文本




-- 主函数
on run
	try
		-- 步骤1：读取Apple ID信息
		set {my appleID, my userPassword} to readAppleIDInfo()
		
		-- 步骤2：切换到Messages应用并处理弹窗
		switchToMessagesAndHandleDialogs()
		
		-- 步骤3：打开账户标签页
		openAccountsTab()	

		--步骤4：填写账户和密码

		fillLoginCredentials(my appleID, my userPassword)
			
		--步骤5：执行登录
		 findAndClickLoginButton()

		-- 步骤6：开始检测执行结果
		set loginResult to monitorLoginResult()
		
		-- 返回结果
		return loginResult
		
	on error errMsg
		set end of errorMessages to "脚本执行失败: " & errMsg
		set overallSuccess to false
		return "Login process failed: " & errMsg
	end try
end run

-- 获取appleid.txt文件路径
on getAppleIdFilePath()
	try
		-- 如果配置路径为空，提示没有appleid文本
		if appleIdFilePath is "" then
			error "appleid.txt文件路径未配置，请设置appleIdFilePath参数"
		else
			-- 处理~路径，转换为绝对路径
			set resolvedPath to appleIdFilePath
			if resolvedPath starts with "~/" then
				set homePath to (path to home folder) as string
				-- 移除末尾的冒号并替换为POSIX路径格式
				if homePath ends with ":" then set homePath to text 1 thru -2 of homePath
				set resolvedPath to homePath & ":" & (text 3 thru -1 of resolvedPath)
				-- 将/替换为:
				set AppleScript's text item delimiters to "/"
				set pathParts to text items of resolvedPath
				set AppleScript's text item delimiters to ":"
				set resolvedPath to pathParts as string
				set AppleScript's text item delimiters to ""
			end if
			return resolvedPath
		end if
	on error errMsg

		error "获取appleid.txt路径失败: " & errMsg
	end try
end getAppleIdFilePath


-- 读取Apple ID信息
on readAppleIDInfo()
	try
		-- 获取appleid.txt文件路径
		set appleIDFile to getAppleIdFilePath()
		
		-- 检查文件是否存在
		tell application "System Events"
			if not (exists file appleIDFile) then
				error "找不到文件\"file " & appleIDFile & "\"。请检查文件是否存在于指定路径。"
			end if
		end tell
		
		-- 读取文件内容
		set fileContent to read file appleIDFile as string
		
		-- 获取第一行（使用换行符分割）
		set AppleScript's text item delimiters to return
		set fileLines to text items of fileContent
		if length of fileLines = 1 then
			-- 尝试使用 linefeed 分割
			set AppleScript's text item delimiters to linefeed
			set fileLines to text items of fileContent
		end if
		set AppleScript's text item delimiters to ""
		
		-- 找到第一行有内容的行
		set firstLine to ""
		repeat with i from 1 to length of fileLines
			set lineText to item i of fileLines as string
			if length of lineText > 0 then
				set firstLine to lineText
				exit repeat
			end if
		end repeat
		
		if firstLine is not "" then
			-- 解析格式：email----password----phone----api_url
			set AppleScript's text item delimiters to "----"
			set accountParts to text items of firstLine
			set AppleScript's text item delimiters to ""
			
			if length of accountParts >= 2 then
				-- 直接获取字符串，不进行复杂处理
				set appleID to (item 1 of accountParts) as string
				set userPassword to (item 2 of accountParts) as string
				
				-- 简单去除前后空格
				if appleID starts with " " then set appleID to text 2 thru -1 of appleID
				if appleID ends with " " then set appleID to text 1 thru -2 of appleID
				if userPassword starts with " " then set userPassword to text 2 thru -1 of userPassword
				if userPassword ends with " " then set userPassword to text 1 thru -2 of userPassword
				
	
				
				return {appleID, userPassword}
			else
				error "文件格式不正确，需要包含----分隔符"
			end if
		else
			error "文件为空或没有有效内容"
		end if
		
	on error errMsg
		
		set end of errorMessages to "文件读取失败: " & errMsg
		set overallSuccess to false
		error errMsg
	end try
end readAppleIDInfo

-- 切换到Messages应用并处理系统弹窗
on switchToMessagesAndHandleDialogs()
	try
		tell application "Messages" to activate
		delay 3
		
		
		-- 处理系统弹窗
		
		handleSystemDialogs()
		
		
	on error errMsg

		
		set end of errorMessages to "应用切换失败: " & errMsg
		set overallSuccess to false
		error errMsg
	end try
end switchToMessagesAndHandleDialogs

-- 处理系统对话框
on handleSystemDialogs()
	tell application "System Events"
		tell process "Messages"
			set firstButtonClicked to false
			
			-- 第一步: 查找"以后"按钮
			try
				set allElements to entire contents
				repeat with element in allElements
					try
						if class of element is button then
							try
								set elementName to name of element
								if elementName contains "以后" or elementName contains "Later" or elementName contains "稍后" then
									click element
									set firstButtonClicked to true
				
									exit repeat
								end if
							end try
						end if
					end try
				end repeat
				
				if not firstButtonClicked then
	
				end if
			on error errMsg
	
			end try
			
			-- 如果第一个按钮成功点击，处理后续对话框
			if firstButtonClicked then
				delay 3
				
				-- 第二步: 查找"跳过"按钮
				set secondButtonClicked to false
				try
					-- 在sheet对话框中查找
					set allSheets to every sheet of window 1
					repeat with currentSheet in allSheets
						set sheetButtons to every button of currentSheet
						repeat with sheetButton in sheetButtons
							try
								set buttonName to name of sheetButton
								if buttonName contains "跳过" or buttonName contains "Skip" or buttonName contains "skip" then
									click sheetButton
									set secondButtonClicked to true
		
									exit repeat
								end if
							end try
						end repeat
						if secondButtonClicked then exit repeat
					end repeat
					
					-- 如果在sheet中没找到，尝试全局搜索
					if not secondButtonClicked then
						set allElements to entire contents
						repeat with element in allElements
							try
								if class of element is button then
									set elementName to name of element
									if elementName contains "跳过" or elementName contains "Skip" or elementName contains "skip" then
										click element
										set secondButtonClicked to true
		
										exit repeat
									end if
								end if
							end try
						end repeat
					end if
					
					if not secondButtonClicked then
		
					end if
				end try
				
				-- 第三步: 如果前两个按钮都成功，点击"取消"按钮
				if secondButtonClicked then
					delay 2
					set thirdButtonClicked to false
					
					try
						-- 在sheet对话框中查找取消按钮
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetButtons to every button of currentSheet
							repeat with sheetButton in sheetButtons
								try
									set buttonName to name of sheetButton
									if buttonName contains "取消" or buttonName contains "Cancel" or buttonName contains "cancel" or buttonName contains "关闭" or buttonName contains "Close" then
										click sheetButton
										set thirdButtonClicked to true
			
										exit repeat
									end if
								end try
							end repeat
							if thirdButtonClicked then exit repeat
						end repeat
						
						-- 如果在sheet中没找到，进行全局搜索
						if not thirdButtonClicked then
							set allElements to entire contents
							repeat with element in allElements
								try
									if class of element is button then
										set elementName to name of element
										if elementName contains "取消" or elementName contains "Cancel" or elementName contains "cancel" or elementName contains "关闭" or elementName contains "Close" then
											click element
											set thirdButtonClicked to true
			
											exit repeat
										end if
									end if
								end try
							end repeat
						end if
						
						if not thirdButtonClicked then
			
						end if
					end try
				end if
			end if
		end tell
	end tell
end handleSystemDialogs

-- 打开账户标签页
on openAccountsTab()
	try
		-- 打开偏好设置
		tell application "System Events"
			tell process "Messages"
				set frontmost to true
				delay 0.5
				keystroke "," using {command down}
				delay 2
			end tell
		end tell
		
		-- 切换到账户标签
		tell application "System Events"
			tell process "Messages"
				-- 等待窗口加载
				repeat 10 times
					if exists window 1 then exit repeat
					delay 1
				end repeat
				
				if not (exists window 1) then
					error "Messages偏好设置窗口未找到"
				end if
				
				-- 首先调试工具栏信息
				try
					set toolbarExists to exists toolbar 1 of window 1
					set toolbarButtonCount to 0
					set buttonNames to {}
					
					if toolbarExists then
						set toolbarButtons to every button of toolbar 1 of window 1
						set toolbarButtonCount to count of toolbarButtons
						
						-- 收集所有按钮名称
						repeat with i from 1 to toolbarButtonCount
							try
								set buttonName to name of button i of toolbar 1 of window 1
								set end of buttonNames to ("按钮 " & i & ": " & buttonName)
							on error
								set end of buttonNames to ("按钮 " & i & ": 无法获取名称")
							end try
						end repeat
					end if
				on error debugErr
					set toolbarExists to false
					set toolbarButtonCount to 0
				end try
				
				-- 尝试多种方式点击账户标签
				set tabClicked to false
				set clickMethod to ""
				set clickedButtonName to ""
				
				-- 方法1：尝试中文"帐户"
				try
					if exists (button "帐户" of toolbar 1 of window 1) then
						click button "帐户" of toolbar 1 of window 1
						set tabClicked to true
						set clickMethod to "方法1"
						set clickedButtonName to "帐户"
	
					end if
				on error method1Err
					-- 记录错误但不输出日志
				end try
				
				-- 方法2：尝试简体中文"账户"
				if not tabClicked then
					try
						if exists (button "账户" of toolbar 1 of window 1) then
							click button "账户" of toolbar 1 of window 1
							set tabClicked to true
							set clickMethod to "方法2"
							set clickedButtonName to "账户"
	
						end if
					on error method2Err
						-- 记录错误但不输出日志
					end try
				end if
				
				-- 方法3：尝试英文"Accounts"
				if not tabClicked then
					try
						if exists (button "Accounts" of toolbar 1 of window 1) then
							click button "Accounts" of toolbar 1 of window 1
							set tabClicked to true
							set clickMethod to "方法3"
							set clickedButtonName to "Accounts"
	
						end if
					on error method3Err
						-- 记录错误但不输出日志
					end try
				end if
				
				-- 方法4：点击第二个工具栏按钮
				if not tabClicked then
					try
						if exists button 2 of toolbar 1 of window 1 then
							click button 2 of toolbar 1 of window 1
							set tabClicked to true
							set clickMethod to "方法4"
							set clickedButtonName to "第二个按钮"
	
						end if
					on error method4Err
						-- 记录错误但不输出日志
					end try
				end if
				
				-- 方法5：尝试通过索引遍历所有按钮
				if not tabClicked then
					try
						set buttonCount to count of (every button of toolbar 1 of window 1)
						repeat with i from 1 to buttonCount
							try
								set buttonName to name of button i of toolbar 1 of window 1
								if buttonName contains "账户" or buttonName contains "帐户" or buttonName contains "Accounts" or buttonName contains "Account" then
									click button i of toolbar 1 of window 1
									set tabClicked to true
									set clickMethod to "方法5"
									set clickedButtonName to buttonName
		
									exit repeat
								end if
							end try
						end repeat
					on error method5Err
						-- 记录错误但不输出日志
					end try
				end if
			end tell
		end tell
		
		if tabClicked then
			set accountsTabOpened to true
			delay 2 -- 等待页面加载
		else
			set accountsTabOpened to false

			-- 不抛出错误，让脚本继续执行并记录详细信息
		end if
		
	on error errMsg
		set accountsTabOpened to false

		set end of errorMessages to "账户标签操作失败: " & errMsg
		set overallSuccess to false
	end try
end openAccountsTab


-- 填写登录凭据（Apple ID和密码）
on fillLoginCredentials(appleID, userPassword)
	try
		tell application "System Events"
			tell process "Messages"
				set credentialsFilled to false
				
				-- 等待登录界面加载
				delay 2
			
				-- 方法1：尝试通用的键盘输入方法
				if not credentialsFilled then
					try
						-- 尝试直接输入（假设焦点在第一个输入框）
						keystroke "a" using {command down} -- 全选
						keystroke appleID
						delay 0.5
						key code 48 -- Tab键
						delay 0.5
						keystroke "a" using {command down} -- 全选
						keystroke userPassword
						delay 0.5
						
						set credentialsFilled to true
			
					end try
				end if
				return credentialsFilled
			end tell
		end tell
	on error errMsg
		
		return false
	end try
end fillLoginCredentials


-- 单次登录尝试
on findAndClickLoginButton()
	try
		tell application "System Events"
			tell process "Messages"
				set loginButtonClicked to false
				
				-- 先等待界面稳定,查找按钮，点击登录
				delay 1
				tell window "帐户"
						if exists button "登录" of group 1 of group 1 then
							--display dialog "检测到登录 "
							click button "登录" of group 1 of group 1
							set loginButtonClicked to true
						end if
					end tell
				if not loginButtonClicked then	
				end if
				return loginButtonClicked
			end tell
		end tell
	on error errMsg
		return false
	end try
end findAndClickLoginButton
checkLoginStatus()
-- 检测登录状态函数
on checkLoginStatus()
	try
		tell application "System Events"
			tell process "Messages"
			
				-- 匹配出错
				try
					tell window "帐户"
						set errorTexts to every static text of group 1 of group 1
						repeat with t in errorTexts
							set msg to (value of t as text)
							if msg contains "出错" or msg contains "incorrect" then
								display dialog "检测到错误提示: " & msg
								return "LOGIN_ERROR"
								exit repeat
							end if
						end repeat
					end tell
					
				end try
				
				-- 匹配登录按钮
				try
					tell window "帐户"
						if exists button "登录" of group 1 of group 1 then
							--display dialog "检测到登录 "
							return "LOGIN_BUTTON_IN"
							
						end if
						
					end tell
					
				end try
				
				-- 匹配您的 Apple ID 或密码不正确。
				try
					tell window "帐户"
						set errorTexts to every static text of group 1 of group 1
						repeat with t in errorTexts
							set msg to (value of t as text)
							if msg contains "不正确。" or msg contains "incorrect" then
								display dialog "检测到错误提示: " & msg
								return "LOGIN_PASSWORD_ERROR"
								exit repeat
							end if
						end repeat
					end tell
					
				end try
				
				-- 默认返回未知状态
				return "UNKNOWN"
			end tell
		end tell
	on error errMsg
		log "检测登录状态时出错: " & errMsg
		return "CHECK_ERROR"
	end try
end checkLoginStatus


--匹配登录后进度窗体，busy indicator，返回结果后，则该窗体消失，未返回则此窗体存在
on checkLoginBusyStatus()
	
	--sheet 1 of window "帐户" of application process "Messages" of application "System Events", busy indicator 1 of sheet 1 of window "帐户" of application process "Messages" of application "System Events", button "取消" of sheet 1 of window "帐户" of application process "Messages" of application "System Events"
	try
		tell application "System Events"
			tell process "Messages"
				tell window "帐户"
					if exists sheet 1 then
						
						if exists button "取消" of sheet 1 then
							
							return "LOGIN_BUSY"
						else
							return "UNKNOWN"
						end if
					end if
					
				end tell
			end tell
		end tell
		
	end try
	
end checkLoginBusyStatus


--匹配登录后验证码输入框
on checkLoginMsgStatus()
	
	--sheet 1 of window "帐户" of application process "Messages" of application "System Events", busy indicator 1 of sheet 1 of window "帐户" of application process "Messages" of application "System Events", button "取消" of sheet 1 of window "帐户" of application process "Messages" of application "System Events"
	try
		tell application "System Events"
			tell process "Messages"
				tell window "帐户"
					-- 首先检查是否有验证码输入框
					try
						if static text "输入发送至 " of group 2 of group 1 of UI element 1 of scroll area 1 of sheet 1 of window "帐户" exists then
							return "VERIFICATION_NEEDED"
						end if
					end try
					
				end tell
			end tell
		end tell
		
	end try
	
end checkLoginMsgStatus
