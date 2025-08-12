-- Apple ID 自动登录脚本
-- 格式要求：belle10665@gmail.com----GcxCmGhJY7h3----573018243428----http://appleid-phone-api.vip/api/get_sms.php?id=3837058330

property executionResults : {}
property errorMessages : {}
property overallSuccess : true
property accountsTabOpened : false

-- 主函数
on run
	try
		-- 步骤1：读取Apple ID信息
		set {appleID, password} to readAppleIDInfo()
		
		-- 步骤2：切换到Messages应用
		switchToMessages()
		
		-- 步骤3：打开账户标签页
		openAccountsTab()
		
		-- 步骤4：登录Apple ID
		if accountsTabOpened then
			loginAppleID(appleID, password)
		end if
		
		-- 显示执行结果
		displayResults()
		
	on error errMsg
		set end of errorMessages to "脚本执行失败: " & errMsg
		set overallSuccess to false
		displayResults()
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
		set fileContent to read file appleIDFile as «class utf8»
		
		-- 解析第一行数据（假设每行一个账户）
		set AppleScript's text item delimiters to "\n"
		set fileLines to text items of fileContent
		set AppleScript's text item delimiters to ""
		
		if length of fileLines > 0 then
			set firstLine to item 1 of fileLines
			
			-- 解析格式：email----password----phone----api_url
			set AppleScript's text item delimiters to "----"
			set accountParts to text items of firstLine
			set AppleScript's text item delimiters to ""
			
			if length of accountParts >= 2 then
				set appleID to item 1 of accountParts
				set password to item 2 of accountParts
				
				set end of executionResults to {stepName:"step1_read_file", success:true, message:"成功读取Apple ID: " & appleID, timestamp:(current date) as string}
				
				return {appleID, password}
			else
				error "文件格式不正确，需要包含----分隔符"
			end if
		else
			error "文件为空"
		end if
		
	on error errMsg
		set end of executionResults to {stepName:"step1_read_file", success:false, message:"读取文件失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "文件读取失败: " & errMsg
		set overallSuccess to false
		error errMsg
	end try
end readAppleIDInfo

-- 切换到Messages应用
on switchToMessages()
	try
		tell application "Messages" to activate
		delay 2
		set end of executionResults to {stepName:"step2_switch_app", success:true, message:"成功切换到Messages应用", timestamp:(current date) as string}
	on error errMsg
		set end of executionResults to {stepName:"step2_switch_app", success:false, message:"切换到Messages失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "应用切换失败: " & errMsg
		set overallSuccess to false
		error errMsg
	end try
end switchToMessages

-- 打开账户标签页
on openAccountsTab()
	try
		tell application "System Events"
			tell process "Messages"
				-- 等待窗口加载
				repeat 10 times
					if exists window 1 then exit repeat
					delay 1
				end repeat
				
				if not (exists window 1) then
					error "Messages窗口未找到"
				end if
				
				-- 尝试多种方式点击账户标签
				set tabClicked to false
				
				-- 方法1：尝试中文"帐户"
				try
					if exists (button "帐户" of toolbar 1 of window 1) then
						click button "帐户" of toolbar 1 of window 1
						set tabClicked to true
						set end of executionResults to {stepName:"step3_accounts_tab", success:true, message:"成功点击'帐户'标签", timestamp:(current date) as string}
					end if
				end try
				
				-- 方法2：尝试简体中文"账户"
				if not tabClicked then
					try
						if exists (button "账户" of toolbar 1 of window 1) then
							click button "账户" of toolbar 1 of window 1
							set tabClicked to true
							set end of executionResults to {stepName:"step3_accounts_tab", success:true, message:"成功点击'账户'标签", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 方法3：尝试英文"Accounts"
				if not tabClicked then
					try
						if exists (button "Accounts" of toolbar 1 of window 1) then
							click button "Accounts" of toolbar 1 of window 1
							set tabClicked to true
							set end of executionResults to {stepName:"step3_accounts_tab", success:true, message:"成功点击'Accounts'标签", timestamp:(current date) as string}
						end if
					end try
				end if
				
				-- 方法4：点击第二个工具栏按钮
				if not tabClicked then
					try
						click button 2 of toolbar 1 of window 1
						set tabClicked to true
						set end of executionResults to {stepName:"step3_accounts_tab", success:true, message:"成功点击第二个工具栏按钮", timestamp:(current date) as string}
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
		set end of executionResults to {stepName:"step3_accounts_tab", success:false, message:"打开账户标签失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "账户标签操作失败: " & errMsg
		set overallSuccess to false
	end try
end openAccountsTab

-- 登录Apple ID
on loginAppleID(appleID, password)
	try
		tell application "System Events"
			tell process "Messages"
				-- 等待账户页面加载
				delay 2
				
				-- 查找登录相关的按钮或链接
				set loginStarted to false
				
				-- 方法1：查找"登录"按钮
				try
					if exists (button "登录" of window 1) then
						click button "登录" of window 1
						set loginStarted to true
						delay 2
					end if
				end try
				
				-- 方法2：查找"Sign In"按钮
				if not loginStarted then
					try
						if exists (button "Sign In" of window 1) then
							click button "Sign In" of window 1
							set loginStarted to true
							delay 2
						end if
					end try
				end if
				
				-- 方法3：查找包含"登录"的任何按钮
				if not loginStarted then
					try
						set allButtons to every button of window 1
						repeat with btn in allButtons
							if (name of btn as string) contains "登录" or (name of btn as string) contains "Sign" then
								click btn
								set loginStarted to true
								delay 2
								exit repeat
							end if
						end repeat
					end try
				end if
				
				-- 如果找到登录按钮，尝试填写信息
				if loginStarted then
					delay 3 -- 等待登录窗口出现
					
					-- 填写Apple ID
					fillAppleIDField(appleID)
					
					-- 填写密码
					fillPasswordField(password)
					
					-- 点击确认登录
					confirmLogin()
					
					set end of executionResults to {stepName:"step4_login", success:true, message:"Apple ID登录流程完成", timestamp:(current date) as string}
				else
					-- 如果没有找到登录按钮，可能已经登录或需要其他操作
					set end of executionResults to {stepName:"step4_login", success:false, message:"未找到登录按钮，可能已经登录", timestamp:(current date) as string}
				end if
			end tell
		end tell
		
	on error errMsg
		set end of executionResults to {stepName:"step4_login", success:false, message:"登录过程失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "登录失败: " & errMsg
		set overallSuccess to false
	end try
end loginAppleID

-- 填写Apple ID字段
on fillAppleIDField(appleID)
	try
		tell application "System Events"
			tell process "Messages"
				-- 查找用户名/邮箱输入框
				set fieldFilled to false
				
				-- 方法1：查找text field
				try
					set textFields to every text field of window 1
					if length of textFields > 0 then
						set value of (item 1 of textFields) to appleID
						set fieldFilled to true
					end if
				end try
				
				-- 方法2：查找包含placeholder的输入框
				if not fieldFilled then
					try
						repeat with tf in (every text field of window 1)
							-- 点击输入框并输入
							click tf
							delay 0.5
							keystroke appleID
							set fieldFilled to true
							exit repeat
						end repeat
					end try
				end if
				
				-- 方法3：通过tab键导航
				if not fieldFilled then
					key code 48 -- Tab键
					delay 0.5
					keystroke appleID
					set fieldFilled to true
				end if
				
			end tell
		end tell
	on error errMsg
		error "填写Apple ID失败: " & errMsg
	end try
end fillAppleIDField

-- 填写密码字段
on fillPasswordField(password)
	try
		tell application "System Events"
			tell process "Messages"
				-- 切换到密码字段（通常是下一个字段）
				key code 48 -- Tab键
				delay 0.5
				
				-- 输入密码
				keystroke password
				delay 0.5
				
			end tell
		end tell
	on error errMsg
		error "填写密码失败: " & errMsg
	end try
end fillPasswordField

-- 确认登录
on confirmLogin()
	try
		tell application "System Events"
			tell process "Messages"
				-- 方法1：按回车键
				key code 36 -- Return key
				delay 1
				
				-- 方法2：查找确认按钮
				try
					if exists (button "确定" of window 1) then
						click button "确定" of window 1
					else if exists (button "OK" of window 1) then
						click button "OK" of window 1
					else if exists (button "登录" of window 1) then
						click button "登录" of window 1
					else if exists (button "Sign In" of window 1) then
						click button "Sign In" of window 1
					end if
				end try
			end tell
		end tell
	on error errMsg
		error "确认登录失败: " & errMsg
	end try
end confirmLogin

-- 显示执行结果
on displayResults()
	set resultMessage to "=== Apple ID 自动登录执行结果 ===" & "\n\n"
	
	-- 显示成功步骤
	set resultMessage to resultMessage & "执行步骤:\n"
	repeat with result in executionResults
		set resultMessage to resultMessage & "• " & (stepName of result) & ": "
		if (success of result) then
			set resultMessage to resultMessage & "✓ " & (message of result)
		else
			set resultMessage to resultMessage & "✗ " & (message of result)
		end if
		set resultMessage to resultMessage & "\n"
	end repeat
	
	-- 显示错误信息
	if length of errorMessages > 0 then
		set resultMessage to resultMessage & "\n错误信息:\n"
		repeat with errMsg in errorMessages
			set resultMessage to resultMessage & "• " & errMsg & "\n"
		end repeat
	end if
	
	-- 显示总体结果
	set resultMessage to resultMessage & "\n总体结果: "
	if overallSuccess then
		set resultMessage to resultMessage & "✓ 执行成功"
	else
		set resultMessage to resultMessage & "✗ 执行失败"
	end if
	
	-- 显示对话框
	display dialog resultMessage buttons {"确定"} default button "确定" with title "执行结果"
end displayResults