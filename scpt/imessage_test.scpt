-- Apple ID 自动登录完整脚本（增强版）
-- 格式要求：belle10665@gmail.com----GcxCmGhJY7h3----573018243428----http://appleid-phone-api.vip/api/get_sms.php?id=3837058330

property executionResults : {}
property errorMessages : {}
property overallSuccess : true
property accountsTabOpened : false
property maxLoginAttempts : 3
property currentLoginAttempt : 0
property appleID : ""
property userPassword : ""

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
		
		-- 返回JSON结果
		return generateJSONResult()
		
	on error errMsg
		set end of errorMessages to "脚本执行失败: " & errMsg
		set overallSuccess to false
		return generateJSONResult()
	end try
end run

-- 读取Apple ID信息
on readAppleIDInfo()
	try
		-- 获取用户Documents目录下的appleid.txt文件
		set documentsPath to (path to documents folder) as string
		set appleIDFile to documentsPath & "appleid.txt"
		
		-- 检查文件是否存在
		tell application "System Events"
			if not (exists file appleIDFile) then
				error "~/Documents/appleid.txt 文件不存在，请在Documents目录下创建该文件"
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
				
				set end of executionResults to {stepName:"step1_read_file", success:true, message:"成功读取Apple ID: " & appleID, timestamp:(current date) as string}
				
				return {appleID, userPassword}
			else
				error "文件格式不正确，需要包含----分隔符"
			end if
		else
			error "文件为空或没有有效内容"
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step1_read_file", success:false, message:"读取文件失败: " & errMsg, timestamp:(current date) as string}
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
		set end of executionResults to {stepName:"step2_switch_app", success:true, message:"成功切换到Messages应用", timestamp:(current date) as string}
		
		-- 处理系统弹窗
		handleSystemDialogs()
		
	on error errMsg
		set end of executionResults to {stepName:"step2_switch_app", success:false, message:"切换到Messages失败: " & errMsg, timestamp:(current date) as string}
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
									set end of executionResults to {stepName:"step3_later_button", success:true, message:"成功点击'以后'按钮: " & elementName, timestamp:(current date) as string}
									exit repeat
								end if
							end try
						end if
					end try
				end repeat
				
				if not firstButtonClicked then
					set end of executionResults to {stepName:"step3_later_button", success:false, message:"未找到'以后'按钮", timestamp:(current date) as string}
				end if
			on error errMsg
				set end of executionResults to {stepName:"step3_later_button", success:false, message:"查找'以后'按钮错误: " & errMsg, timestamp:(current date) as string}
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
									set end of executionResults to {stepName:"step4_skip_button", success:true, message:"成功在对话框中点击'跳过'按钮: " & buttonName, timestamp:(current date) as string}
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
										set end of executionResults to {stepName:"step4_skip_button", success:true, message:"成功通过全局搜索点击'跳过'按钮: " & elementName, timestamp:(current date) as string}
										exit repeat
									end if
								end if
							end try
						end repeat
					end if
					
					if not secondButtonClicked then
						set end of executionResults to {stepName:"step4_skip_button", success:false, message:"未找到'跳过'按钮", timestamp:(current date) as string}
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
										set end of executionResults to {stepName:"step5_cancel_button", success:true, message:"成功在对话框中点击'取消'按钮: " & buttonName, timestamp:(current date) as string}
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
											set end of executionResults to {stepName:"step5_cancel_button", success:true, message:"成功通过全局搜索点击'取消'按钮: " & elementName, timestamp:(current date) as string}
											exit repeat
										end if
									end if
								end try
							end repeat
						end if
						
						if not thirdButtonClicked then
							set end of executionResults to {stepName:"step5_cancel_button", success:false, message:"未找到'取消'按钮", timestamp:(current date) as string}
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
		
		set end of executionResults to {stepName:"step6_open_preferences", success:true, message:"成功打开偏好设置", timestamp:(current date) as string}
		
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
				
				-- 尝试多种方式点击账户标签
				set tabClicked to false
				
				-- 方法1：尝试中文"帐户"
				try
					if exists (button "帐户" of toolbar 1 of window 1) then
						click button "帐户" of toolbar 1 of window 1
						set tabClicked to true
						set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'帐户'标签", timestamp:(current date) as string}
					end if
				end try
				
				-- 方法2：尝试简体中文"账户"
				if not tabClicked then
					try
						if exists (button "账户" of toolbar 1 of window 1) then
							click button "账户" of toolbar 1 of window 1
							set tabClicked to true
							set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'账户'标签", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 方法3：尝试英文"Accounts"
				if not tabClicked then
					try
						if exists (button "Accounts" of toolbar 1 of window 1) then
							click button "Accounts" of toolbar 1 of window 1
							set tabClicked to true
							set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'Accounts'标签", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 方法4：点击第二个工具栏按钮
				if not tabClicked then
					try
						click button 2 of toolbar 1 of window 1
						set tabClicked to true
						set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击第二个工具栏按钮", timestamp:(current date) as string}
					end try
				end if
				
				if tabClicked then
					set accountsTabOpened to true
					delay 2 -- 等待页面加载
				else
					error "无法找到账户标签按钮"
				end if
			end tell
		end tell
		
	on error errMsg
		set end of executionResults to {stepName:"step6_7_accounts", success:false, message:"打开账户标签失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "账户标签操作失败: " & errMsg
		set overallSuccess to false
	end try
end openAccountsTab

-- 带重试机制的登录函数
on loginAppleIDWithRetry(appleID, userPassword)
	set currentLoginAttempt to 0
	set loginSuccessful to false
	set passwordErrorCount to 0
	set maxPasswordErrors to 2 -- 最多允许2次密码错误
	
	repeat while currentLoginAttempt < maxLoginAttempts and not loginSuccessful
		set currentLoginAttempt to currentLoginAttempt + 1
		set end of executionResults to {stepName:"step8_login_attempt", success:true, message:"开始第 " & currentLoginAttempt & " 次登录尝试", timestamp:(current date) as string}
		
		try
			set loginResult to loginAppleIDSingleAttempt(appleID, userPassword, currentLoginAttempt)
			
			if loginResult is "SUCCESS" then
				set loginSuccessful to true
				set end of executionResults to {stepName:"step8_login_success", success:true, message:"第 " & currentLoginAttempt & " 次尝试登录成功", timestamp:(current date) as string}
				
				-- 登录成功后处理验证码
				handleVerificationCode()
				
			else if loginResult is "VERIFICATION_NEEDED" then
				set loginSuccessful to true
				set end of executionResults to {stepName:"step8_login_verification", success:true, message:"第 " & currentLoginAttempt & " 次尝试需要验证码", timestamp:(current date) as string}
				
				-- 处理验证码
				handleVerificationCode()
				
			else if loginResult is "PASSWORD_ERROR" then
				-- 密码错误处理
				set passwordErrorCount to passwordErrorCount + 1
				set end of executionResults to {stepName:"step8_password_error", success:false, message:"第 " & currentLoginAttempt & " 次登录密码错误（累计 " & passwordErrorCount & " 次）", timestamp:(current date) as string}
				
				if passwordErrorCount >= maxPasswordErrors then
					-- 密码错误次数过多，停止重试
					set end of executionResults to {stepName:"step8_password_error_limit", success:false, message:"密码错误次数过多，停止登录尝试", timestamp:(current date) as string}
					set end of errorMessages to "Apple ID密码不正确，已尝试 " & passwordErrorCount & " 次"
					set overallSuccess to false
					exit repeat
				else
					-- 继续重试，但给出明确提示
					set end of executionResults to {stepName:"step8_password_retry", success:true, message:"密码错误，将在3秒后重试", timestamp:(current date) as string}
					delay 3
				end if
				
			else if loginResult is "ACCOUNT_ERROR" then
				-- 账户错误，不需要重试
				set end of executionResults to {stepName:"step8_account_error", success:false, message:"Apple ID账户不存在或无效，停止重试", timestamp:(current date) as string}
				set end of errorMessages to "Apple ID账户不存在或无效"
				set overallSuccess to false
				exit repeat
				
			else
				-- 其他登录失败，准备重试
				set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & currentLoginAttempt & " 次登录失败: " & loginResult, timestamp:(current date) as string}
				
				if currentLoginAttempt < maxLoginAttempts then
					delay 3 -- 等待3秒后重试
				end if
			end if
			
		on error errMsg
			set end of executionResults to {stepName:"step8_login_error", success:false, message:"第 " & currentLoginAttempt & " 次登录出现错误: " & errMsg, timestamp:(current date) as string}
			
			if currentLoginAttempt < maxLoginAttempts then
				delay 3 -- 等待3秒后重试
			end if
		end try
	end repeat
	
	if not loginSuccessful then
		if passwordErrorCount >= maxPasswordErrors then
			set end of errorMessages to "登录失败：Apple ID或密码不正确"
		else
			set end of errorMessages to "所有登录尝试均失败，已达到最大重试次数"
		end if
		set overallSuccess to false
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
		
		set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"开始第 " & attemptNumber & " 次填写登录凭据", timestamp:(current date) as string}
		
		-- 第一步：先尝试填写Apple ID和密码
		set inputCompleted to my fillLoginCredentials(appleID, userPassword)
		
		-- 第二步：如果成功填写信息，再寻找并点击登录按钮
		if inputCompleted then
			set end of executionResults to {stepName:"step8b_click_login", success:true, message:"开始点击登录按钮", timestamp:(current date) as string}
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
			set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & attemptNumber & " 次登录失败：Apple ID或密码不正确", timestamp:(current date) as string}
			return "PASSWORD_ERROR"
		else if loginResult is "ACCOUNT_ERROR" then
			set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & attemptNumber & " 次登录失败：账户不存在或无效", timestamp:(current date) as string}
			return "ACCOUNT_ERROR"
		else if loginResult is "VERIFICATION_FAILED" then
			set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & attemptNumber & " 次登录失败：验证失败", timestamp:(current date) as string}
			return "VERIFICATION_FAILED"
		else if loginResult is "VERIFICATION_NEEDED" then
			set end of executionResults to {stepName:"step8_login_success", success:true, message:"第 " & attemptNumber & " 次登录成功，需要验证码", timestamp:(current date) as string}
			return "VERIFICATION_NEEDED"
		else if loginResult is "SUCCESS" then
			set end of executionResults to {stepName:"step8_login_success", success:true, message:"第 " & attemptNumber & " 次登录完全成功", timestamp:(current date) as string}
			return "SUCCESS"
		else
			-- 对于不明确的状态，进行额外检查
			delay 3
			set secondCheck to my checkLoginResult()
			if secondCheck is "PASSWORD_ERROR" or secondCheck is "ACCOUNT_ERROR" or secondCheck is "VERIFICATION_FAILED" then
				set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & attemptNumber & " 次登录失败（二次检查）：" & secondCheck, timestamp:(current date) as string}
				return secondCheck
			else
				-- 如果仍然不明确，假设成功但需要进一步验证
				set end of executionResults to {stepName:"step8_login_unclear", success:true, message:"第 " & attemptNumber & " 次登录状态不明确，假设成功：" & loginResult, timestamp:(current date) as string}
				return loginResult
			end if
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step8_login_error", success:false, message:"第 " & attemptNumber & " 次登录过程中出错: " & errMsg, timestamp:(current date) as string}
		return "ERROR: " & errMsg
	end try
end loginAppleIDSingleAttempt

-- 检查登录结果
on checkLoginResult()
	try
		tell application "System Events"
			tell process "Messages"
				delay 3 -- 增加等待时间，确保错误信息完全显示
				
				-- 检查是否有错误信息
				set errorFound to false
				set verificationNeeded to false
				set loginSuccess to false
				set errorMessage to ""
				
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
								if elementValue contains "您的 Apple ID 或密码不正确" or elementValue contains "Apple ID 或密码不正确" or elementValue contains "密码不正确" or elementValue contains "incorrect password" or elementValue contains "密码错误" or elementValue contains "wrong password" or elementValue contains "Invalid Apple ID or password" or elementValue contains "Apple ID or password is incorrect" then
									set errorFound to true
									set errorMessage to elementValue
									set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到密码错误信息: " & elementValue, timestamp:(current date) as string}
									return "PASSWORD_ERROR"
								end if
								
								-- 检查账户相关错误
								if elementValue contains "账户不存在" or elementValue contains "account does not exist" or elementValue contains "无效的用户名" or elementValue contains "invalid username" or elementValue contains "Apple ID不存在" or elementValue contains "Apple ID does not exist" then
									set errorFound to true
									set errorMessage to elementValue
									set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到账户不存在错误: " & elementValue, timestamp:(current date) as string}
									return "ACCOUNT_ERROR"
								end if
								
								-- 检查验证失败
								if elementValue contains "验证失败" or elementValue contains "verification failed" or elementValue contains "鉴定失败" or elementValue contains "authentication failed" or elementValue contains "登录失败" or elementValue contains "login failed" then
									set errorFound to true
									set errorMessage to elementValue
									set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到验证失败错误: " & elementValue, timestamp:(current date) as string}
									return "VERIFICATION_FAILED"
								end if
								
								-- 检查是否需要验证码
								if elementValue contains "验证码" or elementValue contains "verification code" or elementValue contains "输入验证码" or elementValue contains "enter code" or elementValue contains "双重认证" or elementValue contains "two-factor" then
									set verificationNeeded to true
									set end of executionResults to {stepName:"step8_check_result", success:true, message:"检测到需要验证码: " & elementValue, timestamp:(current date) as string}
								end if
								
								-- 检查是否登录成功
								if elementValue contains "已登录" or elementValue contains "signed in" or elementValue contains "登录成功" or elementValue contains "connected" or elementValue contains "iMessage" then
									set loginSuccess to true
									set end of executionResults to {stepName:"step8_check_result", success:true, message:"检测到登录成功信息: " & elementValue, timestamp:(current date) as string}
								end if
							end if
							
						end try
					end repeat
				end try
				
				-- 方法2：检查sheet对话框中的文本（增强错误检测）
				try
					set allSheets to every sheet of window 1
					repeat with currentSheet in allSheets
						-- 检查sheet中的所有UI元素
						try
							set allSheetElements to entire contents of currentSheet
							repeat with sheetElement in allSheetElements
								try
									set elementValue to ""
									try
										set elementValue to value of sheetElement as string
									on error
										try
											set elementValue to name of sheetElement as string
										end try
									end try
									
									if elementValue is not "" then
										-- 检查Apple ID或密码错误的各种表述
										if elementValue contains "您的 Apple ID 或密码不正确" or elementValue contains "Apple ID 或密码不正确" or elementValue contains "密码不正确" or elementValue contains "incorrect password" or elementValue contains "密码错误" or elementValue contains "wrong password" or elementValue contains "Invalid Apple ID or password" or elementValue contains "Apple ID or password is incorrect" then
											set errorFound to true
											set errorMessage to elementValue
											set end of executionResults to {stepName:"step8_check_result", success:false, message:"在sheet中检测到密码错误信息: " & elementValue, timestamp:(current date) as string}
											return "PASSWORD_ERROR"
										end if
										
										-- 检查账户相关错误
										if elementValue contains "账户不存在" or elementValue contains "account does not exist" or elementValue contains "无效的用户名" or elementValue contains "invalid username" or elementValue contains "Apple ID不存在" or elementValue contains "Apple ID does not exist" then
											set errorFound to true
											set errorMessage to elementValue
											set end of executionResults to {stepName:"step8_check_result", success:false, message:"在sheet中检测到账户不存在错误: " & elementValue, timestamp:(current date) as string}
											return "ACCOUNT_ERROR"
										end if
										
										-- 检查验证失败
										if elementValue contains "验证失败" or elementValue contains "verification failed" or elementValue contains "鉴定失败" or elementValue contains "authentication failed" or elementValue contains "登录失败" or elementValue contains "login failed" then
											set errorFound to true
											set errorMessage to elementValue
											set end of executionResults to {stepName:"step8_check_result", success:false, message:"在sheet中检测到验证失败错误: " & elementValue, timestamp:(current date) as string}
											return "VERIFICATION_FAILED"
										end if
										
										-- 检查验证码需求
										if elementValue contains "验证码" or elementValue contains "verification code" or elementValue contains "输入验证码" or elementValue contains "enter code" or elementValue contains "双重认证" or elementValue contains "two-factor" then
											set verificationNeeded to true
											set end of executionResults to {stepName:"step8_check_result", success:true, message:"在sheet中检测到需要验证码: " & elementValue, timestamp:(current date) as string}
										end if
									end if
									
								end try
							end repeat
						end try
					end repeat
				end try
				
				-- 方法3：检查是否有输入验证码的文本框出现
				try
					set allTextFields to every text field of window 1
					repeat with textField in allTextFields
						try
							-- 检查文本框的placeholder或相关属性
							if exists (attribute "AXPlaceholderValue" of textField) then
								set placeholderText to value of attribute "AXPlaceholderValue" of textField
								if placeholderText contains "验证码" or placeholderText contains "code" then
									set verificationNeeded to true
								end if
							end if
						end try
					end repeat
				end try
				
				-- 根据检查结果返回相应状态
				if errorFound then
					return "LOGIN_ERROR"
				else if verificationNeeded then
					return "VERIFICATION_NEEDED"
				else if loginSuccess then
					return "SUCCESS"
				else
					-- 如果没有明确的错误或成功信息，假设需要更多时间
					delay 3
					-- 再次检查
					if my quickCheckForSuccess() then
						return "SUCCESS"
					else
						return "UNCLEAR_STATUS"
					end if
				end if
				
			end tell
		end tell
	on error errMsg
		set end of executionResults to {stepName:"step8_check_result", success:false, message:"检查登录结果时出错: " & errMsg, timestamp:(current date) as string}
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

-- 处理验证码（带60秒超时重试机制）
on handleVerificationCode()
	try
		set end of executionResults to {stepName:"step9_verification_start", success:true, message:"开始处理验证码流程（60秒超时）", timestamp:(current date) as string}
		
		-- 设置60秒超时
		set verificationTimeout to 60
		set verificationStartTime to (current date)
		set verificationSuccess to false
		set verificationAttempts to 0
		set maxVerificationAttempts to 3
		
		repeat while not verificationSuccess and verificationAttempts < maxVerificationAttempts
			set verificationAttempts to verificationAttempts + 1
			set end of executionResults to {stepName:"step9_verification_attempt", success:true, message:"第 " & verificationAttempts & " 次验证码尝试", timestamp:(current date) as string}
			
			-- 检查是否超时
			set currentTime to (current date)
			set elapsedTime to (currentTime - verificationStartTime)
			if elapsedTime > verificationTimeout then
				set end of executionResults to {stepName:"step9_verification_timeout", success:false, message:"验证码处理超时（" & elapsedTime & "秒），准备重新登录", timestamp:(current date) as string}
				-- 超时后重新尝试登录
				my retryLoginAfterTimeout()
				return
			end if
			
			-- 等待验证码窗口出现
			set verificationWindowFound to my waitForVerificationWindow()
			
			if verificationWindowFound then
				-- 检测验证码输入框并输入测试文本
				set testInputResult to my inputTestCodeAndContinue()
				
				if testInputResult then
					-- 等待并检查验证码输入后的结果
					set verificationResult to my checkVerificationResultWithTimeout(currentTime, verificationTimeout)
					
					if verificationResult is "SUCCESS" then
						set verificationSuccess to true
						set end of executionResults to {stepName:"step9_verification_success", success:true, message:"验证码验证成功", timestamp:(current date) as string}
					else if verificationResult is "TIMEOUT" then
						set end of executionResults to {stepName:"step9_verification_timeout", success:false, message:"验证码验证超时，准备重新登录", timestamp:(current date) as string}
						my retryLoginAfterTimeout()
						return
					else if verificationResult is "FAILED" then
						set end of executionResults to {stepName:"step9_verification_failed", success:false, message:"第 " & verificationAttempts & " 次验证码验证失败，继续尝试", timestamp:(current date) as string}
						-- 继续下一次尝试
					end if
				else
					set end of executionResults to {stepName:"step9_verification_input_failed", success:false, message:"第 " & verificationAttempts & " 次验证码输入失败", timestamp:(current date) as string}
				end if
			else
				set end of executionResults to {stepName:"step9_verification_window_not_found", success:false, message:"第 " & verificationAttempts & " 次未找到验证码窗口", timestamp:(current date) as string}
			end if
			
			-- 如果不是最后一次尝试，等待一下再继续
			if not verificationSuccess and verificationAttempts < maxVerificationAttempts then
				delay 3
			end if
		end repeat
		
		-- 如果所有尝试都失败了
		if not verificationSuccess then
			set end of executionResults to {stepName:"step9_verification_all_failed", success:false, message:"所有验证码尝试均失败，准备重新登录", timestamp:(current date) as string}
			my retryLoginAfterTimeout()
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step9_verification_error", success:false, message:"处理验证码时出错: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "验证码处理失败: " & errMsg
		my retryLoginAfterTimeout()
	end try
end handleVerificationCode

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
									set end of executionResults to {stepName:"step9a_verification_window", success:true, message:"找到验证码窗口，文本内容: " & textContent, timestamp:(current date) as string}
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
											set end of executionResults to {stepName:"step9a_verification_window", success:true, message:"在对话框中找到验证码提示: " & textContent, timestamp:(current date) as string}
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
											set end of executionResults to {stepName:"step9a_verification_window", success:true, message:"找到验证码输入框，placeholder: " & placeholderText, timestamp:(current date) as string}
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
			set end of executionResults to {stepName:"step9a_verification_window", success:false, message:"等待验证码窗口超时，未找到验证码输入界面", timestamp:(current date) as string}
		end if
		
		return verificationFound
		
	on error errMsg
		set end of executionResults to {stepName:"step9a_verification_window", success:false, message:"等待验证码窗口时出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end waitForVerificationWindow

-- 输入测试验证码并点击继续
on inputTestCodeAndContinue()
	try
		set testCode to "123456" -- 测试验证码
		set inputSuccess to false
		
		tell application "System Events"
			tell process "Messages"
				-- 方法1：在主窗口查找验证码输入框
				try
					set allTextFields to every text field of window 1
					repeat with textField in allTextFields
						try
							-- 检查是否是验证码输入框
							set shouldUseThisField to false
							
							-- 通过placeholder判断
							if exists (attribute "AXPlaceholderValue" of textField) then
								set placeholderText to value of attribute "AXPlaceholderValue" of textField
								if placeholderText contains "验证码" or placeholderText contains "code" or placeholderText contains "代码" then
									set shouldUseThisField to true
								end if
							end if
							
							-- 通过位置判断（通常验证码输入框比较短）
							if not shouldUseThisField then
								try
									set fieldSize to size of textField
									-- 如果输入框比较短，可能是验证码输入框
									if item 1 of fieldSize < 200 then
										set shouldUseThisField to true
									end if
								end try
							end if
							
							if shouldUseThisField then
								click textField
								delay 0.5
								keystroke "a" using {command down} -- 全选
								keystroke testCode
								set inputSuccess to true
								set end of executionResults to {stepName:"step9b_input_test_code", success:true, message:"在主窗口输入测试验证码: " & testCode, timestamp:(current date) as string}
								exit repeat
							end if
						end try
					end repeat
				end try
				
				-- 方法2：在sheet对话框中查找验证码输入框
				if not inputSuccess then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetTextFields to every text field of currentSheet
							repeat with sheetTextField in sheetTextFields
								try
									click sheetTextField
									delay 0.5
									keystroke "a" using {command down}
									keystroke testCode
									set inputSuccess to true
									set end of executionResults to {stepName:"step9b_input_test_code", success:true, message:"在对话框中输入测试验证码: " & testCode, timestamp:(current date) as string}
									exit repeat
								end try
							end repeat
							if inputSuccess then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：如果都没找到，尝试直接输入（假设焦点在验证码输入框）
				if not inputSuccess then
					try
						keystroke testCode
						set inputSuccess to true
						set end of executionResults to {stepName:"step9b_input_test_code", success:true, message:"通过直接输入方式输入测试验证码: " & testCode, timestamp:(current date) as string}
					end try
				end if
			end tell
		end tell
		
		if inputSuccess then
			-- 输入成功后，寻找并点击继续按钮
			return my findAndClickContinueButton()
		else
			set end of executionResults to {stepName:"step9b_input_test_code", success:false, message:"未能找到验证码输入框", timestamp:(current date) as string}
			return false
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step9b_input_test_code", success:false, message:"输入测试验证码时出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end inputTestCodeAndContinue

-- 寻找并点击继续按钮
on findAndClickContinueButton()
	try
		tell application "System Events"
			tell process "Messages"
				set continueButtonClicked to false
				delay 1 -- 等待界面响应
				
				-- 方法1：在主窗口查找继续按钮
				try
					set allButtons to every button of window 1
					repeat with btn in allButtons
						try
							set buttonName to name of btn as string
							if buttonName contains "继续" or buttonName contains "Continue" or buttonName contains "确定" or buttonName contains "OK" or buttonName contains "验证" or buttonName contains "Verify" then
								click btn
								set continueButtonClicked to true
								set end of executionResults to {stepName:"step9c_click_continue", success:true, message:"在主窗口点击继续按钮: " & buttonName, timestamp:(current date) as string}
								exit repeat
							end if
						end try
					end repeat
				end try
				
				-- 方法2：在sheet对话框中查找继续按钮
				if not continueButtonClicked then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetButtons to every button of currentSheet
							repeat with sheetButton in sheetButtons
								try
									set buttonName to name of sheetButton as string
									if buttonName contains "继续" or buttonName contains "Continue" or buttonName contains "确定" or buttonName contains "OK" or buttonName contains "验证" or buttonName contains "Verify" then
										click sheetButton
										set continueButtonClicked to true
										set end of executionResults to {stepName:"step9c_click_continue", success:true, message:"在对话框中点击继续按钮: " & buttonName, timestamp:(current date) as string}
										exit repeat
									end if
								end try
							end repeat
							if continueButtonClicked then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：使用回车键
				if not continueButtonClicked then
					try
						key code 36 -- Return key
						set continueButtonClicked to true
						set end of executionResults to {stepName:"step9c_click_continue", success:true, message:"通过回车键确认验证码", timestamp:(current date) as string}
					end try
				end if
				
				-- 方法4：查找默认按钮
				if not continueButtonClicked then
					try
						set allButtons to every button of window 1
						repeat with btn in allButtons
							try
								if exists (attribute "AXDefaultButton" of btn) then
									set isDefault to value of attribute "AXDefaultButton" of btn
									if isDefault then
										click btn
										set continueButtonClicked to true
										set end of executionResults to {stepName:"step9c_click_continue", success:true, message:"点击默认按钮确认验证码", timestamp:(current date) as string}
										exit repeat
									end if
								end if
							end try
						end repeat
					end try
				end if
				
				if not continueButtonClicked then
					set end of executionResults to {stepName:"step9c_click_continue", success:false, message:"未找到继续按钮", timestamp:(current date) as string}
				end if
				
				return continueButtonClicked
			end tell
		end tell
		
	on error errMsg
		set end of executionResults to {stepName:"step9c_click_continue", success:false, message:"点击继续按钮时出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end findAndClickContinueButton

-- 检查验证码输入后的结果（带超时检查）
on checkVerificationResultWithTimeout(startTime, timeoutSeconds)
	try
		delay 5 -- 等待验证结果
		
		-- 检查是否超时
		set currentTime to (current date)
		set elapsedTime to (currentTime - startTime)
		if elapsedTime > timeoutSeconds then
			set end of executionResults to {stepName:"step9d_verification_timeout", success:false, message:"验证码检查超时（" & elapsedTime & "秒）", timestamp:(current date) as string}
			return "TIMEOUT"
		end if
		
		tell application "System Events"
			tell process "Messages"
				set verificationSuccess to false
				set verificationError to false
				set errorMessage to ""
				
				-- 方法1：检查主窗口中的结果文本
				try
					set allStaticTexts to every static text of window 1
					repeat with textElement in allStaticTexts
						try
							set textContent to value of textElement as string
							
							-- 检查验证码错误信息
							if textContent contains "验证码错误" or textContent contains "incorrect code" or textContent contains "验证码不正确" or textContent contains "wrong code" or textContent contains "invalid code" then
								set verificationError to true
								set errorMessage to textContent
								set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码错误: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
							-- 检查验证码过期信息
							if textContent contains "验证码已过期" or textContent contains "code expired" or textContent contains "验证码超时" then
								set verificationError to true
								set errorMessage to textContent
								set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码过期: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
							-- 检查验证成功信息
							if textContent contains "验证成功" or textContent contains "verification successful" or textContent contains "登录成功" or textContent contains "signed in successfully" then
								set verificationSuccess to true
								set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"验证码验证成功: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
						end try
					end repeat
				end try
				
				-- 方法2：检查sheet对话框中的结果
				if not verificationSuccess and not verificationError then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetTexts to every static text of currentSheet
							repeat with sheetText in sheetTexts
								try
									set textContent to value of sheetText as string
									
									if textContent contains "验证码错误" or textContent contains "incorrect code" then
										set verificationError to true
										set errorMessage to textContent
										set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"在对话框中发现验证码错误: " & textContent, timestamp:(current date) as string}
										exit repeat
									end if
									
									if textContent contains "验证成功" or textContent contains "verification successful" then
										set verificationSuccess to true
										set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"在对话框中发现验证成功: " & textContent, timestamp:(current date) as string}
										exit repeat
									end if
									
								end try
							end repeat
							if verificationSuccess or verificationError then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：检查是否回到了正常界面（没有验证码对话框）
				if not verificationSuccess and not verificationError then
					delay 3 -- 再等待3秒
					
					-- 再次检查超时
					set currentTime to (current date)
					set elapsedTime to (currentTime - startTime)
					if elapsedTime > timeoutSeconds then
						set end of executionResults to {stepName:"step9d_verification_timeout", success:false, message:"验证码检查超时（" & elapsedTime & "秒）", timestamp:(current date) as string}
						return "TIMEOUT"
					end if
					
					try
						set hasVerificationDialog to false
						set allSheets to every sheet of window 1
						if length of allSheets > 0 then
							-- 检查是否还有验证码相关的对话框
							repeat with currentSheet in allSheets
								set sheetTexts to every static text of currentSheet
								repeat with sheetText in sheetTexts
									try
										set textContent to value of sheetText as string
										if textContent contains "验证码" or textContent contains "verification code" then
											set hasVerificationDialog to true
											exit repeat
										end if
									end try
								end repeat
								if hasVerificationDialog then exit repeat
							end repeat
						end if
						
						if not hasVerificationDialog then
							-- 如果没有验证码对话框了，可能表示验证成功
							set verificationSuccess to true
							set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"验证码对话框消失，推测验证成功", timestamp:(current date) as string}
						else
							-- 如果还有验证码对话框，可能需要重新输入
							set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码对话框仍然存在，可能需要重新输入", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 根据检查结果返回状态
				if verificationError then
					set end of errorMessages to "验证码验证失败: " & errorMessage
					return "FAILED"
				else if verificationSuccess then
					set end of executionResults to {stepName:"step9_verification_complete", success:true, message:"验证码流程完成，验证成功", timestamp:(current date) as string}
					return "SUCCESS"
				else
					set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"无法确定验证码验证结果", timestamp:(current date) as string}
					return "FAILED"
				end if
			end tell
		end tell
		
	on error errMsg
		set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"检查验证码结果时出错: " & errMsg, timestamp:(current date) as string}
		return "FAILED"
	end try
end checkVerificationResultWithTimeout

-- 验证码超时后重新尝试登录
on retryLoginAfterTimeout()
	try
		set end of executionResults to {stepName:"step10_retry_login_start", success:true, message:"验证码超时，开始重新登录流程", timestamp:(current date) as string}
		
		-- 关闭当前的验证码对话框
		tell application "System Events"
			tell process "Messages"
				try
					-- 尝试关闭sheet对话框
					set allSheets to every sheet of window 1
					repeat with currentSheet in allSheets
						try
							-- 查找取消或关闭按钮
							set allButtons to every button of currentSheet
							repeat with btn in allButtons
								set buttonName to name of btn as string
								if buttonName contains "取消" or buttonName contains "Cancel" or buttonName contains "关闭" or buttonName contains "Close" then
									click btn
									set end of executionResults to {stepName:"step10_close_dialog", success:true, message:"关闭验证码对话框: " & buttonName, timestamp:(current date) as string}
									exit repeat
								end if
							end repeat
						end try
					end repeat
				end try
				
				-- 等待对话框关闭
				delay 2
				
				-- 尝试按ESC键关闭对话框
				try
					key code 53 -- ESC key
					delay 1
				end try
			end tell
		end tell
		
		-- 等待界面稳定
		delay 3
		
		-- 重新开始登录流程
		set end of executionResults to {stepName:"step10_restart_login", success:true, message:"准备重新开始登录流程", timestamp:(current date) as string}
		
		-- 增加登录重试计数
		set currentLoginAttempt to currentLoginAttempt + 1
		
		-- 检查是否超过最大重试次数
		if currentLoginAttempt <= maxLoginAttempts then
			set end of executionResults to {stepName:"step10_retry_login", success:true, message:"开始第 " & currentLoginAttempt & " 次重新登录", timestamp:(current date) as string}
			
			-- 调用登录函数（使用全局变量中的用户名和密码）
			my loginAppleIDSingleAttempt(my appleID, my userPassword, currentLoginAttempt)
		else
			set end of executionResults to {stepName:"step10_max_retries_reached", success:false, message:"已达到最大登录重试次数（" & maxLoginAttempts & "次）", timestamp:(current date) as string}
			set end of errorMessages to "登录重试次数已达上限，登录失败"
			set overallSuccess to false
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step10_retry_login_error", success:false, message:"重新登录过程中出错: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "重新登录失败: " & errMsg
		set overallSuccess to false
	end try
end retryLoginAfterTimeout

-- 检查验证码输入后的结果（保留原函数以兼容）
on checkVerificationResult()
	try
		delay 5 -- 等待验证结果
		
		tell application "System Events"
			tell process "Messages"
				set verificationSuccess to false
				set verificationError to false
				set errorMessage to ""
				
				-- 方法1：检查主窗口中的结果文本
				try
					set allStaticTexts to every static text of window 1
					repeat with textElement in allStaticTexts
						try
							set textContent to value of textElement as string
							
							-- 检查验证码错误信息
							if textContent contains "验证码错误" or textContent contains "incorrect code" or textContent contains "验证码不正确" or textContent contains "wrong code" or textContent contains "invalid code" then
								set verificationError to true
								set errorMessage to textContent
								set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码错误: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
							-- 检查验证码过期信息
							if textContent contains "验证码已过期" or textContent contains "code expired" or textContent contains "验证码超时" then
								set verificationError to true
								set errorMessage to textContent
								set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码过期: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
							-- 检查验证成功信息
							if textContent contains "验证成功" or textContent contains "verification successful" or textContent contains "登录成功" or textContent contains "signed in successfully" then
								set verificationSuccess to true
								set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"验证码验证成功: " & textContent, timestamp:(current date) as string}
								exit repeat
							end if
							
						end try
					end repeat
				end try
				
				-- 方法2：检查sheet对话框中的结果
				if not verificationSuccess and not verificationError then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetTexts to every static text of currentSheet
							repeat with sheetText in sheetTexts
								try
									set textContent to value of sheetText as string
									
									if textContent contains "验证码错误" or textContent contains "incorrect code" then
										set verificationError to true
										set errorMessage to textContent
										set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"在对话框中发现验证码错误: " & textContent, timestamp:(current date) as string}
										exit repeat
									end if
									
									if textContent contains "验证成功" or textContent contains "verification successful" then
										set verificationSuccess to true
										set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"在对话框中发现验证成功: " & textContent, timestamp:(current date) as string}
										exit repeat
									end if
									
								end try
							end repeat
							if verificationSuccess or verificationError then exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：检查是否回到了正常界面（没有验证码对话框）
				if not verificationSuccess and not verificationError then
					delay 3 -- 再等待3秒
					try
						set hasVerificationDialog to false
						set allSheets to every sheet of window 1
						if length of allSheets > 0 then
							-- 检查是否还有验证码相关的对话框
							repeat with currentSheet in allSheets
								set sheetTexts to every static text of currentSheet
								repeat with sheetText in sheetTexts
									try
										set textContent to value of sheetText as string
										if textContent contains "验证码" or textContent contains "verification code" then
											set hasVerificationDialog to true
											exit repeat
										end if
									end try
								end repeat
								if hasVerificationDialog then exit repeat
							end repeat
						end if
						
						if not hasVerificationDialog then
							-- 如果没有验证码对话框了，可能表示验证成功
							set verificationSuccess to true
							set end of executionResults to {stepName:"step9d_verification_result", success:true, message:"验证码对话框消失，推测验证成功", timestamp:(current date) as string}
						else
							-- 如果还有验证码对话框，可能需要重新输入
							set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"验证码对话框仍然存在，可能需要重新输入", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 根据检查结果设置最终状态
				if verificationError then
					set end of errorMessages to "验证码验证失败: " & errorMessage
				else if verificationSuccess then
					set end of executionResults to {stepName:"step9_verification_complete", success:true, message:"验证码流程完成，验证成功", timestamp:(current date) as string}
				else
					set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"无法确定验证码验证结果", timestamp:(current date) as string}
					set end of errorMessages to "验证码结果检查不明确"
				end if
			end tell
		end tell
		
	on error errMsg
		set end of executionResults to {stepName:"step9d_verification_result", success:false, message:"检查验证码结果时出错: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "验证码结果检查失败: " & errMsg
	end try
end checkVerificationResult

-- 填写登录凭据（Apple ID和密码）
on fillLoginCredentials(appleID, userPassword)
	try
		tell application "System Events"
			tell process "Messages"
				set credentialsFilled to false
				
				-- 等待登录界面加载
				delay 2
				
				-- 方法1：在主窗口中查找文本输入框
				set textFields to every text field of window 1
				
				if length of textFields >= 2 then
					try
						-- 填写Apple ID
						set value of (item 1 of textFields) to ""
						set value of (item 1 of textFields) to appleID
						delay 0.5
						
						-- 填写密码
						set value of (item 2 of textFields) to ""
						set value of (item 2 of textFields) to userPassword
						delay 0.5
						
						set credentialsFilled to true
						set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"在主窗口成功填写Apple ID和密码", timestamp:(current date) as string}
					on error
						-- 如果直接设置值失败，尝试点击和键入的方式
						click (item 1 of textFields)
						delay 0.5
						keystroke "a" using {command down} -- 全选
						keystroke appleID
						
						delay 0.5
						key code 48 -- Tab键切换到密码框
						delay 0.5
						keystroke "a" using {command down} -- 全选
						keystroke userPassword
						
						set credentialsFilled to true
						set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"在主窗口通过键盘输入方式成功填写凭据", timestamp:(current date) as string}
					end try
				end if
				
				-- 方法2：在sheet对话框中查找输入框
				if not credentialsFilled then
					try
						set allSheets to every sheet of window 1
						repeat with currentSheet in allSheets
							set sheetTextFields to every text field of currentSheet
							if length of sheetTextFields >= 2 then
								-- 填写Apple ID
								set value of (item 1 of sheetTextFields) to ""
								set value of (item 1 of sheetTextFields) to appleID
								delay 0.5
								
								-- 填写密码
								set value of (item 2 of sheetTextFields) to ""
								set value of (item 2 of sheetTextFields) to userPassword
								delay 0.5
								
								set credentialsFilled to true
								set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"在对话框中成功填写凭据", timestamp:(current date) as string}
								exit repeat
							else if length of sheetTextFields = 1 then
								-- 只有一个输入框的情况
								set value of (item 1 of sheetTextFields) to appleID
								delay 0.5
								key code 48 -- Tab键
								delay 0.5
								keystroke userPassword
								set credentialsFilled to true
								set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"在对话框中通过单个输入框填写凭据", timestamp:(current date) as string}
								exit repeat
							end if
						end repeat
					end try
				end if
				
				-- 方法3：尝试通用的键盘输入方法
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
						set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"通过通用键盘输入方式填写凭据", timestamp:(current date) as string}
					end try
				end if
				
				-- 方法4：查找所有可能的输入元素
				if not credentialsFilled then
					try
						-- 查找所有UI元素，包括可能的输入框
						set allElements to entire contents of window 1
						set foundTextFields to {}
						
						repeat with element in allElements
							try
								if (class of element is text field) or (class of element is combo box) then
									set end of foundTextFields to element
								end if
							end try
						end repeat
						
						if length of foundTextFields >= 1 then
							click (item 1 of foundTextFields)
							delay 0.5
							keystroke "a" using {command down}
							keystroke appleID
							
							if length of foundTextFields >= 2 then
								click (item 2 of foundTextFields)
								delay 0.5
								keystroke "a" using {command down}
								keystroke userPassword
							else
								key code 48 -- Tab键
								delay 0.5
								keystroke userPassword
							end if
							
							set credentialsFilled to true
							set end of executionResults to {stepName:"step8a_fill_credentials", success:true, message:"通过搜索所有元素找到输入框并填写", timestamp:(current date) as string}
						end if
					end try
				end if
				
				if not credentialsFilled then
					set end of executionResults to {stepName:"step8a_fill_credentials", success:false, message:"未找到合适的输入框", timestamp:(current date) as string}
				end if
				
				return credentialsFilled
			end tell
		end tell
	on error errMsg
		set end of executionResults to {stepName:"step8a_fill_credentials", success:false, message:"填写凭据失败: " & errMsg, timestamp:(current date) as string}
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
							set end of executionResults to {stepName:"step8b_click_login", success:true, message:"在主窗口成功点击登录按钮: " & buttonName, timestamp:(current date) as string}
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
										set end of executionResults to {stepName:"step8b_click_login", success:true, message:"在对话框中成功点击登录按钮: " & buttonName, timestamp:(current date) as string}
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
								set end of executionResults to {stepName:"step8b_click_login", success:true, message:"点击添加账户按钮: " & buttonName, timestamp:(current date) as string}
								delay 3 -- 等待添加账户界面出现
								exit repeat
							end if
						end repeat
					end try
				end if
				
				-- 方法4：如果没找到明确的登录按钮，查找"确定"、"OK"等按钮
				if not loginButtonClicked then
					try
						repeat with btn in (every button of window 1)
							set buttonName to name of btn as string
							if buttonName contains "确定" or buttonName contains "OK" or buttonName contains "好" or buttonName contains "Continue" then
								click btn
								set loginButtonClicked to true
								set end of executionResults to {stepName:"step8b_click_login", success:true, message:"通过确定按钮操作: " & buttonName, timestamp:(current date) as string}
								delay 2
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
						set end of executionResults to {stepName:"step8b_click_login", success:true, message:"通过回车键确认登录", timestamp:(current date) as string}
						delay 2
					end try
				end if
				
				if not loginButtonClicked then
					set end of executionResults to {stepName:"step8b_click_login", success:false, message:"未找到登录确认按钮", timestamp:(current date) as string}
				end if
				
				return loginButtonClicked
			end tell
		end tell
	on error errMsg
		set end of executionResults to {stepName:"step8b_click_login", success:false, message:"点击登录按钮失败: " & errMsg, timestamp:(current date) as string}
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
				
				set end of executionResults to {stepName:"step8c_confirm_login", success:true, message:"执行登录确认操作", timestamp:(current date) as string}
			end tell
		end tell
	on error errMsg
		set end of executionResults to {stepName:"step8c_confirm_login", success:false, message:"确认登录失败: " & errMsg, timestamp:(current date) as string}
	end try
end confirmLoginAfterInput

-- 生成JSON结果
on generateJSONResult()
	set jsonResult to "{"
	set jsonResult to jsonResult & "\"success\":" & (overallSuccess as string) & ","
	set jsonResult to jsonResult & "\"timestamp\":\"" & ((current date) as string) & "\","
	set jsonResult to jsonResult & "\"totalSteps\":" & (length of executionResults) & ","
	set jsonResult to jsonResult & "\"loginAttempts\":" & currentLoginAttempt & ","
	set jsonResult to jsonResult & "\"maxAttempts\":" & maxLoginAttempts & ","
	
	-- 添加密码错误统计信息
	set passwordErrorCount to 0
	set accountErrorCount to 0
	set verificationErrorCount to 0
	repeat with currentStep in executionResults
		set stepMessage to (message of currentStep) as string
		if stepMessage contains "密码错误" or stepMessage contains "密码不正确" then
			set passwordErrorCount to passwordErrorCount + 1
		else if stepMessage contains "账户不存在" or stepMessage contains "账户错误" then
			set accountErrorCount to accountErrorCount + 1
		else if stepMessage contains "验证失败" then
			set verificationErrorCount to verificationErrorCount + 1
		end if
	end repeat
	
	set jsonResult to jsonResult & "\"errorStatistics\":{"
	set jsonResult to jsonResult & "\"passwordErrors\":" & passwordErrorCount & ","
	set jsonResult to jsonResult & "\"accountErrors\":" & accountErrorCount & ","
	set jsonResult to jsonResult & "\"verificationErrors\":" & verificationErrorCount
	set jsonResult to jsonResult & "},"
	
	-- 添加执行步骤详情
	set jsonResult to jsonResult & "\"steps\":["
	repeat with i from 1 to length of executionResults
		set currentStep to item i of executionResults
		set jsonResult to jsonResult & "{"
		set jsonResult to jsonResult & "\"stepName\":\"" & (stepName of currentStep) & "\","
		set jsonResult to jsonResult & "\"success\":" & (success of currentStep) & ","
		set jsonResult to jsonResult & "\"message\":\"" & (message of currentStep) & "\","
		set jsonResult to jsonResult & "\"timestamp\":\"" & (timestamp of currentStep) & "\""
		set jsonResult to jsonResult & "}"
		if i < length of executionResults then
			set jsonResult to jsonResult & ","
		end if
	end repeat
	set jsonResult to jsonResult & "],"
	
	-- 添加错误信息
	set jsonResult to jsonResult & "\"errors\":["
	repeat with i from 1 to length of errorMessages
		set jsonResult to jsonResult & "\"" & (item i of errorMessages) & "\""
		if i < length of errorMessages then
			set jsonResult to jsonResult & ","
		end if
	end repeat
	set jsonResult to jsonResult & "],"
	
	-- 添加详细的汇总信息
	if overallSuccess then
		set jsonResult to jsonResult & "\"summary\":\"Apple ID自动登录流程完成，包含验证码处理，所有步骤执行成功\""
	else
		set summaryMessage to "Apple ID自动登录流程失败，已执行 " & currentLoginAttempt & " 次登录尝试"
		if passwordErrorCount > 0 then
			set summaryMessage to summaryMessage & "，检测到 " & passwordErrorCount & " 次密码错误"
		end if
		if accountErrorCount > 0 then
			set summaryMessage to summaryMessage & "，检测到 " & accountErrorCount & " 次账户错误"
		end if
		if verificationErrorCount > 0 then
			set summaryMessage to summaryMessage & "，检测到 " & verificationErrorCount & " 次验证错误"
		end if
		set summaryMessage to summaryMessage & "，请检查Apple ID和密码是否正确"
		set jsonResult to jsonResult & "\"summary\":\"" & summaryMessage & "\""
	end if
	
	set jsonResult to jsonResult & "}"
	
	return jsonResult
end generateJSONResult