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

-- 新增超时配置参数
property loginTimeout : 60 -- 单次登录操作超时时间（秒）
property verificationTimeout : 120 -- 验证码等待超时时间（秒）
property uiResponseTimeout : 10 -- UI响应超时时间（秒）
property retryDelay : 5 -- 重试间隔时间（秒）
property maxPasswordErrors : 3 -- 最大密码错误次数
property maxVerificationErrors : 2 -- 最大验证失败次数
property loginStatusCheckInterval : 2 -- 登录状态检查间隔（秒）
property loginStatusMaxChecks : 15 -- 登录状态最大检查次数
property customVerificationCode : "666666" -- 自定义验证码，如果为空则使用默认测试验证码
property verificationCodeMode : 1 -- 验证码获取方式：1=自定义输入，2=API获取
property appleIdFilePath : "~/Documents/appleid.txt" -- appleid.txt文件路径，空值时提示没有appleid文本



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



-- 主函数
on run
	try
		-- 步骤1：读取Apple ID信息
		set {my appleID, my userPassword} to readAppleIDInfo()
		
		-- 步骤2：切换到Messages应用并处理弹窗
		switchToMessagesAndHandleDialogs()
		
		-- 步骤3：打开账户标签页
		openAccountsTab()
		
		-- 步骤4：登录Apple ID（包含重试机制）
		if accountsTabOpened then
			loginAppleIDWithRetry(my appleID, my userPassword)
		end if
		
		-- 返回结果
		return "Login process completed"
		
	on error errMsg
		set end of errorMessages to "脚本执行失败: " & errMsg
		set overallSuccess to false
		return "Login process failed: " & errMsg
	end try
end run

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

-- 带重试机制的登录函数（增强版）
on loginAppleIDWithRetry(appleID, userPassword)
	set currentLoginAttempt to 0
	set loginSuccessful to false
	set passwordErrorCount to 0
	set verificationErrorCount to 0
	set consecutiveFailures to 0
	set lastErrorType to ""
	
	repeat while currentLoginAttempt < maxLoginAttempts and not loginSuccessful
		set currentLoginAttempt to currentLoginAttempt + 1

		
		try
			-- 使用超时控制的登录尝试
			set loginStartTime to (current date)
			set loginResult to loginAppleIDSingleAttemptWithTimeout(appleID, userPassword, currentLoginAttempt, loginTimeout)
			set loginEndTime to (current date)
			set loginDuration to (loginEndTime - loginStartTime)
			
	
			
			if loginResult is "SUCCESS" then
				set loginSuccessful to true
				set consecutiveFailures to 0
	
	
				
				-- 使用超时控制等待验证码窗口
				set verificationResult to waitForVerificationWindowWithTimeout(verificationTimeout)
	
				
				-- 处理验证码输入
				set testVerificationCode to getVerificationCode()
				set inputResult to inputVerificationCodeWithTimeout(testVerificationCode, uiResponseTimeout)
	
				
			else if loginResult is "VERIFICATION_NEEDED" then
				set loginSuccessful to true
				set consecutiveFailures to 0
	
	
				
				-- 使用超时控制等待验证码窗口
				set verificationResult to waitForVerificationWindowWithTimeout(verificationTimeout)
	
				
				-- 处理验证码输入
				set testVerificationCode to getVerificationCode()
				set inputResult to inputVerificationCodeWithTimeout(testVerificationCode, uiResponseTimeout)
	
				
			else if loginResult is "PASSWORD_ERROR" then
				-- 密码错误处理
				set passwordErrorCount to passwordErrorCount + 1
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "PASSWORD_ERROR"

	
				
				if passwordErrorCount >= maxPasswordErrors then

	
					set end of errorMessages to "Apple ID密码不正确，已尝试 " & passwordErrorCount & " 次"
					set overallSuccess to false
					exit repeat
				else
					-- 智能重试延迟：根据错误次数增加延迟时间
					set dynamicDelay to retryDelay + (passwordErrorCount * 2)

	
					delay dynamicDelay
				end if
				
			else if loginResult is "ACCOUNT_ERROR" then
				-- 账户错误，不需要重试
				set lastErrorType to "ACCOUNT_ERROR"

	
				set end of errorMessages to "Apple ID账户不存在或无效"
				set overallSuccess to false
				exit repeat
				
			else if loginResult is "VERIFICATION_FAILED" then
				-- 验证失败处理
				set verificationErrorCount to verificationErrorCount + 1
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "VERIFICATION_FAILED"

	
				
				if verificationErrorCount >= maxVerificationErrors then

	
					set end of errorMessages to "登录验证失败次数过多，已尝试 " & verificationErrorCount & " 次"
					set overallSuccess to false
					exit repeat
				else if currentLoginAttempt < maxLoginAttempts then
					-- 验证失败后使用更长的延迟时间
					set verificationDelay to retryDelay + (verificationErrorCount * 3)

	
					delay verificationDelay
				end if
				
			else if loginResult is "TIMEOUT" then
				-- 超时处理
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "TIMEOUT"

	
				
				if currentLoginAttempt < maxLoginAttempts then
					-- 超时后使用较长的延迟时间
					set timeoutDelay to retryDelay + 5
	
	
					delay timeoutDelay
				end if
				
			else
				-- 其他未知错误
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "UNKNOWN_ERROR"

	
				
				if currentLoginAttempt < maxLoginAttempts then
					-- 根据连续失败次数调整延迟时间
					set adaptiveDelay to retryDelay + (consecutiveFailures * 2)
	
	
					delay adaptiveDelay
				end if
			end if
			
		on error errMsg
			set consecutiveFailures to consecutiveFailures + 1


			
			
			if currentLoginAttempt < maxLoginAttempts then
				-- 异常后使用基础延迟时间
	

				delay retryDelay
			end if
		end try
	end repeat
	
	-- 最终结果处理
	if not loginSuccessful then

		if passwordErrorCount >= maxPasswordErrors then
			set end of errorMessages to "登录失败：Apple ID或密码不正确，已尝试 " & passwordErrorCount & " 次"
		else if verificationErrorCount >= maxVerificationErrors then
			set end of errorMessages to "登录失败：验证失败次数过多，已尝试 " & verificationErrorCount & " 次"
		else if lastErrorType is "TIMEOUT" then
			set end of errorMessages to "登录失败：操作超时，请检查网络连接"
		else if lastErrorType is "ACCOUNT_ERROR" then
			set end of errorMessages to "登录失败：Apple ID账户不存在或无效"
		else
			set end of errorMessages to "所有登录尝试均失败，已达到最大重试次数 (" & maxLoginAttempts & ")"
		end if
		set overallSuccess to false
	else

	end if
end loginAppleIDWithRetry

-- 单次登录尝试
on loginAppleIDSingleAttempt(appleID, userPassword, attemptNumber)
	try
		tell application "System Events"
			tell process "Messages"
				-- 等待账户页面加载
				delay 2
			end tell
		end tell
		

		
		-- 第一步：先尝试填写Apple ID和密码
		set inputCompleted to my fillLoginCredentials(appleID, userPassword)
		
		-- 第二步：如果成功填写信息，再寻找并点击登录按钮
		if inputCompleted then

			my findAndClickLoginButton()
		else
			-- 如果没有找到输入框，可能需要先点击登录按钮打开登录界面
			set loginDialogOpened to my findAndClickLoginButton()
			if loginDialogOpened then
				delay 3 -- 等待登录对话框出现
				my fillLoginCredentials(appleID, userPassword)
				-- 再次尝试确认登录
				my confirmLoginAfterInput()
			end if
		end if
		
		-- 等待登录结果
		delay 5
		
		-- 检查登录结果
		set loginResult to my checkLoginResult()
		
		-- 根据检查结果处理并记录详细日志
		if loginResult is "PASSWORD_ERROR" then

			return "PASSWORD_ERROR"
		else if loginResult is "ACCOUNT_ERROR" then

			return "ACCOUNT_ERROR"
		else if loginResult is "VERIFICATION_FAILED" then

			return "VERIFICATION_FAILED"
		else if loginResult is "VERIFICATION_NEEDED" then

			return "VERIFICATION_NEEDED"
		else if loginResult is "SUCCESS" then

			return "SUCCESS"
		else
			-- 对于不明确的状态，进行额外检查
			delay 3
			set secondCheck to my checkLoginResult()
			if secondCheck is "PASSWORD_ERROR" or secondCheck is "ACCOUNT_ERROR" or secondCheck is "VERIFICATION_FAILED" then
	
				return secondCheck
			else
				-- 如果仍然不明确，假设成功但需要进一步验证
	
				return loginResult
			end if
		end if
		
	on error errMsg

		return "ERROR: " & errMsg
	end try
end loginAppleIDSingleAttempt

-- 改进的登录结果检查（带状态监控）
on checkLoginResult()

	try
		tell application "System Events"
			tell process "Messages"
				-- 使用配置的状态检查间隔
				delay loginStatusCheckInterval
				
				-- 检查是否有错误信息
				set errorFound to false
				set verificationNeeded to false
				set loginSuccess to false
				set errorMessage to ""
				set checkCount to 0
				
				-- 多次状态检查循环，提高检测准确性
				repeat while checkCount < loginStatusMaxChecks and not errorFound and not verificationNeeded and not loginSuccess
					set checkCount to checkCount + 1
		
					
					-- 方法1：检查窗口中的所有文本元素（包括错误提示）
					try
						set allUIElements to entire contents of window 1
						repeat with uiElement in allUIElements
							try
								set elementValue to ""
								try
									set elementValue to value of uiElement as string
								on error
									try
										set elementValue to name of uiElement as string
									end try
								end try
								
								if elementValue is not "" then
				
									
									-- 检查Apple ID或密码错误的各种表述
									if elementValue contains "您的 Apple ID 或密码不正确" or elementValue contains "Apple ID 或密码不正确" or elementValue contains "密码不正确" or elementValue contains "incorrect password" or elementValue contains "密码错误" or elementValue contains "wrong password" or elementValue contains "Invalid Apple ID or password" or elementValue contains "Apple ID or password is incorrect" or elementValue contains "登录信息不正确" then
										set errorFound to true
										set errorMessage to elementValue
	
						
										return "PASSWORD_ERROR"
									end if
									
									-- 检查账户相关错误
									if elementValue contains "账户不存在" or elementValue contains "account does not exist" or elementValue contains "无效的用户名" or elementValue contains "invalid username" or elementValue contains "Apple ID不存在" or elementValue contains "Apple ID does not exist" or elementValue contains "此Apple ID不存在" or elementValue contains "账户无效" then
										set errorFound to true
										set errorMessage to elementValue
	
						
										return "ACCOUNT_ERROR"
									end if
									
									-- 检查验证失败
									if elementValue contains "验证失败" or elementValue contains "verification failed" or elementValue contains "鉴定失败" or elementValue contains "authentication failed" or elementValue contains "登录失败" or elementValue contains "login failed" or elementValue contains "身份验证失败" then
										set errorFound to true
										set errorMessage to elementValue
	
						
										return "VERIFICATION_FAILED"
									end if
								
								-- 检查是否需要验证码
										if elementValue contains "验证码" or elementValue contains "verification code" or elementValue contains "输入验证码" or elementValue contains "enter code" or elementValue contains "双重认证" or elementValue contains "two-factor" or elementValue contains "输入代码" or elementValue contains "安全代码" then
											set verificationNeeded to true
					
							
										end if
										
										-- 检查是否登录成功
										if elementValue contains "已登录" or elementValue contains "signed in" or elementValue contains "登录成功" or elementValue contains "connected" or elementValue contains "iMessage" or elementValue contains "Messages" or elementValue contains "账户已连接" or elementValue contains "Account connected" then
											set loginSuccess to true
					
							
										end if
									end if
									
								end try
							end repeat
					end try
					
					-- 如果没有明确结果，等待后再次检查
					if not errorFound and not verificationNeeded and not loginSuccess and checkCount < loginStatusMaxChecks then
		
						delay loginStatusCheckInterval
					end if
				end repeat
				
				
				-- 根据检查结果返回相应状态
		
				
				if errorFound then
		
					return "LOGIN_ERROR"
				else if verificationNeeded then
		
					return "VERIFICATION_NEEDED"
				else if loginSuccess then
		
					return "SUCCESS"
				else
					-- 如果经过多次检查仍无明确结果，进行最后的快速检查
		
					delay 3
					if my quickCheckForSuccess() then
		
						return "SUCCESS"
					else
		
						return "UNCLEAR_STATUS"
					end if
				end if
				
			end tell
		end tell
	on error errMsg

		return "CHECK_ERROR"
	end try
end checkLoginResult

-- 快速检查是否登录成功
on quickCheckForSuccess()
	try
		tell application "System Events"
			tell process "Messages"
				-- 检查是否回到了主账户界面（没有登录对话框）
				set loginDialogExists to false
				try
					set allSheets to every sheet of window 1
					if length of allSheets > 0 then
						set loginDialogExists to true
					end if
				end try
				
				-- 如果没有登录对话框，可能表示登录成功
				return not loginDialogExists
			end tell
		end tell
	on error
		return false
	end try
end quickCheckForSuccess


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

-- 寻找并点击登录按钮
on findAndClickLoginButton()
	try
		tell application "System Events"
			tell process "Messages"
				set loginButtonClicked to false
				
				-- 先等待界面稳定
				delay 1
				
				-- 方法1：在主窗口查找"登录"按钮
				try
					set allButtons to every button of window 1
					repeat with btn in allButtons
						set buttonName to name of btn as string
						if buttonName contains "登录" or buttonName contains "Sign In" or buttonName contains "登入" or buttonName contains "iMessage" then
							click btn
							set loginButtonClicked to true
		
							delay 2 -- 等待登录界面出现
							exit repeat
						end if
					end repeat
				end try
				
				-- 方法2：在sheet对话框中查找登录按钮
				if not loginButtonClicked then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetButtons to every button of currentSheet
							repeat with sheetButton in sheetButtons
								try
									set buttonName to name of sheetButton
									if buttonName contains "登录" or buttonName contains "Sign In" or buttonName contains "登入" then
										click sheetButton
										set loginButtonClicked to true
				
										delay 2
										exit repeat
									end if
								end try
							end repeat
							if loginButtonClicked then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：查找"添加账户"、"Add Account"等按钮
				if not loginButtonClicked then
					try
						repeat with btn in (every button of window 1)
							set buttonName to name of btn as string
							if buttonName contains "添加" or buttonName contains "Add" or buttonName contains "新增" or buttonName contains "+" then
								click btn
								set loginButtonClicked to true
		
								delay 3 -- 等待添加账户界面出现
								exit repeat
							end if
						end repeat
					end try
				end if
				
				-- 方法5：使用回车键（作为最后的尝试）
				if not loginButtonClicked then
					try
						key code 36 -- Return key
						set loginButtonClicked to true
		
						delay 2
					end try
				end if
				
				if not loginButtonClicked then
	
				end if
				
				return loginButtonClicked
			end tell
		end tell
	on error errMsg
		
		return false
	end try
end findAndClickLoginButton

-- 输入信息后确认登录
on confirmLoginAfterInput()
	try
		tell application "System Events"
			tell process "Messages"
				delay 1
				
				-- 尝试多种确认方式
				-- 方法1：回车键
				key code 36 -- Return key
				delay 1
				
				-- 方法2：查找确认按钮
				try
					set allButtons to every button of window 1
					repeat with btn in allButtons
						set buttonName to name of btn as string
						if buttonName contains "登录" or buttonName contains "Sign In" or buttonName contains "确定" or buttonName contains "OK" or buttonName contains "Continue" then
							click btn
							exit repeat
						end if
					end repeat
				end try
				
	
			end tell
		end tell
	on error errMsg
		
	end try
end confirmLoginAfterInput


-- 等待验证码窗口出现
on waitForVerificationWindow()
	try
		set maxWaitTime to 60 -- 最多等待60秒
		set waitTime to 0
		set verificationFound to false
		
		repeat while waitTime < maxWaitTime and not verificationFound
			tell application "System Events"
				tell process "Messages"
					-- 方法1：检查是否有验证码相关的文本
					try
						set allStaticTexts to every static text of window 1
						repeat with textElement in allStaticTexts
							try
								set textContent to value of textElement as string
								if textContent contains "验证码" or textContent contains "verification code" or textContent contains "输入代码" or textContent contains "enter code" then
									set verificationFound to true
				
									exit repeat
								end if
							end try
						end repeat
					end try
					
					-- 方法2：检查sheet对话框中的验证码文本
					if not verificationFound then
						try
							set allSheets to every sheet of window 1
							repeat with currentSheet in allSheets
								set sheetTexts to every static text of currentSheet
								repeat with sheetText in sheetTexts
									try
										set textContent to value of sheetText as string
										if textContent contains "验证码" or textContent contains "verification code" then
											set verificationFound to true
					
											exit repeat
										end if
									end try
								end repeat
								if verificationFound then exit repeat
							end repeat
						end try
					end if
					
					-- 方法3：检查是否有专门的验证码输入框
					if not verificationFound then
						try
							set allTextFields to every text field of window 1
							repeat with textField in allTextFields
								try
									if exists (attribute "AXPlaceholderValue" of textField) then
										set placeholderText to value of attribute "AXPlaceholderValue" of textField
										if placeholderText contains "验证码" or placeholderText contains "code" or placeholderText contains "代码" then
											set verificationFound to true
					
											exit repeat
										end if
									end if
								end try
							end repeat
						end try
					end if
				end tell
			end tell
			
			if not verificationFound then
				delay 2
				set waitTime to waitTime + 2
			end if
		end repeat
		
		if not verificationFound then

		end if
		
		return verificationFound
		
	on error errMsg
		
		return false
	end try
end waitForVerificationWindow

-- 验证码输入函数
on inputVerificationCode(testCode)
	try
		set codeInputSuccess to false

		
		tell application "System Events"
			tell process "Messages"
				-- 方法1：在主窗口中查找验证码输入框
				try
					set allTextFields to every text field of window 1
					repeat with textField in allTextFields
						try
							-- 检查是否是验证码输入框
							if exists (attribute "AXPlaceholderValue" of textField) then
								set placeholderText to value of attribute "AXPlaceholderValue" of textField
								if placeholderText contains "验证码" or placeholderText contains "code" or placeholderText contains "代码" then
									-- 找到验证码输入框，进行输入
									click textField
									delay 0.5
									set value of textField to ""
									set value of textField to testCode
									set codeInputSuccess to true
			
									exit repeat
								end if
							end if
						end try
					end repeat
				end try
				
				-- 方法2：在sheet对话框中查找验证码输入框
				if not codeInputSuccess then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetTextFields to every text field of currentSheet
							repeat with sheetTextField in sheetTextFields
								try
									-- 检查是否是验证码输入框
									if exists (attribute "AXPlaceholderValue" of sheetTextField) then
										set placeholderText to value of attribute "AXPlaceholderValue" of sheetTextField
										if placeholderText contains "验证码" or placeholderText contains "code" or placeholderText contains "代码" then
											-- 找到验证码输入框，进行输入
											click sheetTextField
											delay 0.5
											set value of sheetTextField to ""
											set value of sheetTextField to testCode
											set codeInputSuccess to true
				
											exit repeat
										end if
									end if
								end try
							end repeat
							if codeInputSuccess then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：通用键盘输入方法（如果找不到特定的输入框）
				if not codeInputSuccess then
					try
						-- 尝试直接键盘输入（假设焦点在验证码输入框）
						keystroke "a" using {command down} -- 全选
						keystroke testCode
						set codeInputSuccess to true
	
					end try
				end if
				
				-- 输入完成后，尝试提交验证码
				if codeInputSuccess then
					delay 1
					-- 尝试按回车键提交
					try
						key code 36 -- 回车键
	
					end try
					
					-- 或者尝试点击提交按钮
					try
						set submitButtons to every button of window 1
						repeat with submitButton in submitButtons
							try
								set buttonTitle to title of submitButton
								if buttonTitle contains "提交" or buttonTitle contains "确定" or buttonTitle contains "Submit" or buttonTitle contains "OK" or buttonTitle contains "Continue" then
									click submitButton
			
									exit repeat
								end if
							end try
						end repeat
					end try
					
					-- 也检查sheet中的提交按钮
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetButtons to every button of currentSheet
							repeat with sheetButton in sheetButtons
								try
									set buttonTitle to title of sheetButton
									if buttonTitle contains "提交" or buttonTitle contains "确定" or buttonTitle contains "Submit" or buttonTitle contains "OK" or buttonTitle contains "Continue" then
										click sheetButton
			
										exit repeat
									end if
								end try
							end repeat
							if codeInputSuccess then exit repeat
						end repeat
					end try
				end if
				
			end tell
		end tell
		
		if not codeInputSuccess then

		end if
		
		return codeInputSuccess
		
	on error errMsg

		return false
	end try
end inputVerificationCode


-- 带超时控制的单次登录尝试
on loginAppleIDSingleAttemptWithTimeout(appleID, userPassword, attemptNumber)

	set startTime to (current date)
	set timeoutReached to false
	
	try
		-- 在超时时间内尝试登录
		repeat while ((current date) - startTime) < loginTimeout and not timeoutReached
			try
				set loginResult to loginAppleIDSingleAttempt(appleID, userPassword, attemptNumber)
				if loginResult is not "TIMEOUT" and loginResult is not "UNCLEAR_STATUS" then
					return loginResult
				end if
				delay 2 -- 短暂等待后重试
			on error errMsg
	
				delay 2
			end try
		end repeat
		
		
		return "TIMEOUT"
	on error errMsg
		
		return "ERROR"
	end try
end loginAppleIDSingleAttemptWithTimeout

-- 带超时控制的验证窗口等待
on waitForVerificationWindowWithTimeout()

	set startTime to (current date)
	
	repeat while ((current date) - startTime) < verificationTimeout
		try
			if waitForVerificationWindow() then

				return true
			end if
			delay 2
		on error errMsg

			delay 2
		end try
	end repeat
	
	
	return false
end waitForVerificationWindowWithTimeout

-- 带超时控制的验证码输入
on inputVerificationCodeWithTimeout(verificationCode, timeoutSeconds)

	set startTime to (current date)
	
	repeat while ((current date) - startTime) < timeoutSeconds
		try

			set inputResult to inputVerificationCode(verificationCode)
			if inputResult then
	
				return true
			end if
			delay 1
		on error errMsg

			delay 1
		end try
	end repeat
	
	
	return false
end inputVerificationCodeWithTimeout

-- 获取验证码函数
on getVerificationCode()
	try
	
		
		if verificationCodeMode is 1 then
			-- 模式1：自定义输入，直接使用customVerificationCode，绝不调用API

			-- 额外检查：确保不会意外使用appleid.txt中的数字
			if customVerificationCode contains "61659" or customVerificationCode contains "250813" then
	
				return "666666"
			else
				return customVerificationCode
			end if
			
		else if verificationCodeMode is 2 then
			-- 模式2：API获取（已禁用，直接使用自定义验证码）

			return customVerificationCode
			
		else
			-- 未知模式，使用自定义验证码

			return customVerificationCode
		end if
		
	on error errMsg

		return customVerificationCode -- 出错时返回自定义验证码
	end try
end getVerificationCode

-- 设置自定义验证码函数
on setCustomVerificationCode(newCode)
	try
		set customVerificationCode to newCode

		return true
	on error errMsg

		return false
	end try
end setCustomVerificationCode

-- API获取验证码函数已删除，只使用自定义验证码模式