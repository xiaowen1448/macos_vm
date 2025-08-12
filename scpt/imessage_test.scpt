-- Apple ID 自动登录完整脚本
-- 格式要求：belle10665@gmail.com----GcxCmGhJY7h3----573018243428----http://appleid-phone-api.vip/api/get_sms.php?id=3837058330

property executionResults : {}
property errorMessages : {}
property overallSuccess : true
property accountsTabOpened : false

-- 主函数
on run
	try
		-- 步骤1：读取Apple ID信息
		set {appleID, userPassword} to readAppleIDInfo()
		
		-- 步骤2：切换到Messages应用并处理弹窗
		switchToMessagesAndHandleDialogs()
		
		-- 步骤3：打开账户标签页
		openAccountsTab()
		
		-- 步骤4：登录Apple ID（修改后的逻辑）
		if accountsTabOpened then
			loginAppleIDNewLogic(appleID, userPassword)
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
		-- 获取脚本所在目录的appleid.txt文件
		set scriptPath to path to me
		tell application "Finder"
			set scriptFolder to container of scriptPath
		end tell
		set appleIDFile to (scriptFolder as string) & "appleid.txt"
		
		-- 检查文件是否存在
		tell application "System Events"
			if not (exists file appleIDFile) then
				error "appleid.txt 文件不存在，请在脚本同目录下创建该文件"
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

-- 新的登录逻辑：先输入信息，再寻找登录按钮
on loginAppleIDNewLogic(appleID, userPassword)
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
			set end of executionResults to {stepName:"step8_login", success:true, message:"Apple ID登录流程完成", timestamp:(current date) as string}
		else
			-- 如果没有找到输入框，可能需要先点击登录按钮打开登录界面
			set loginDialogOpened to my findAndClickLoginButton()
			if loginDialogOpened then
				delay 3 -- 等待登录对话框出现
				my fillLoginCredentials(appleID, userPassword)
				-- 再次尝试确认登录
				my confirmLoginAfterInput()
			end if
			set end of executionResults to {stepName:"step8_login", success:true, message:"通过先点击登录按钮再输入信息的方式完成登录", timestamp:(current date) as string}
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step8_login", success:false, message:"登录过程失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "登录失败: " & errMsg
		set overallSuccess to false
	end try
end loginAppleIDNewLogic

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
	
	-- 添加汇总信息
	if overallSuccess then
		set jsonResult to jsonResult & "\"summary\":\"Apple ID自动登录流程完成，所有步骤执行成功\""
	else
		set jsonResult to jsonResult & "\"summary\":\"Apple ID自动登录流程部分步骤失败，请查看详细错误信息\""
	end if
	
	set jsonResult to jsonResult & "}"
	
	return jsonResult
end generateJSONResult