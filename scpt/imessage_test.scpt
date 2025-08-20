-- Apple ID 自动登录完整脚本（增强版）

property executionResults : {}
property errorMessages : {}
property debugMessages : {}
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

-- Debug日志输出函数
on logDebug(level, functionName, message)
	if not debugEnabled then return
	
	set levelPriority to getLevelPriority(level)
	set currentLevelPriority to getLevelPriority(debugLevel)
	
	if levelPriority >= currentLevelPriority then
		set timestamp to (current date) as string
		set debugEntry to {level:level, function:functionName, message:message, timestamp:timestamp}
		set end of debugMessages to debugEntry
		
		-- 同时输出到控制台（可选）
		log "[" & level & "] [" & functionName & "] " & message
	end if
end logDebug

-- 获取日志级别优先级
on getLevelPriority(level)
	if level is "DEBUG" then return 1
	if level is "INFO" then return 2
	if level is "WARN" then return 3
	if level is "ERROR" then return 4
	return 2 -- 默认INFO级别
end getLevelPriority

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
		logDebug("ERROR", "getAppleIdFilePath", "获取appleid.txt路径失败: " & errMsg)
		error "获取appleid.txt路径失败: " & errMsg
	end try
end getAppleIdFilePath

-- 错误分类和处理
property errorCategories : {}
property errorRecoveryAttempts : {}
property maxRecoveryAttempts : 3

-- 错误分类函数
on categorizeError(errorMessage)
	logDebug("DEBUG", "categorizeError", "分析错误: " & errorMessage)
	
	-- 网络相关错误
	if errorMessage contains "network" or errorMessage contains "connection" or errorMessage contains "timeout" or errorMessage contains "网络" or errorMessage contains "连接" or errorMessage contains "超时" then
		return "NETWORK_ERROR"
	end if
	
	-- UI相关错误
	if errorMessage contains "UI element" or errorMessage contains "window" or errorMessage contains "button" or errorMessage contains "text field" or errorMessage contains "界面" or errorMessage contains "按钮" or errorMessage contains "输入框" then
		return "UI_ERROR"
	end if
	
	-- 认证相关错误
	if errorMessage contains "password" or errorMessage contains "Apple ID" or errorMessage contains "authentication" or errorMessage contains "密码" or errorMessage contains "认证" or errorMessage contains "验证" then
		return "AUTH_ERROR"
	end if
	
	-- 系统相关错误
	if errorMessage contains "System Events" or errorMessage contains "process" or errorMessage contains "application" or errorMessage contains "系统" or errorMessage contains "进程" or errorMessage contains "应用" then
		return "SYSTEM_ERROR"
	end if
	
	-- 默认为未知错误
	return "UNKNOWN_ERROR"
end categorizeError

-- 错误恢复策略
on attemptErrorRecovery(errorCategory, errorMessage, context)
	logDebug("INFO", "attemptErrorRecovery", "尝试恢复错误类型: " & errorCategory & "，上下文: " & context)
	
	-- 检查是否已达到最大恢复尝试次数
	set recoveryKey to errorCategory & "_" & context
	set currentAttempts to 0
	
	-- 查找现有的恢复尝试次数
	repeat with recoveryRecord in errorRecoveryAttempts
		if (recoveryRecord's keyName as string) is recoveryKey then
			set currentAttempts to recoveryRecord's attemptCount
			exit repeat
		end if
	end repeat
	
	if currentAttempts >= maxRecoveryAttempts then
		logDebug("ERROR", "attemptErrorRecovery", "已达到最大恢复尝试次数: " & maxRecoveryAttempts)
		return false
	end if
	
	-- 更新尝试次数
	set newAttempts to currentAttempts + 1
	set foundExisting to false
	repeat with i from 1 to length of errorRecoveryAttempts
		if (item i of errorRecoveryAttempts)'s keyName is recoveryKey then
			set item i of errorRecoveryAttempts to {keyName:recoveryKey, attemptCount:newAttempts}
			set foundExisting to true
			exit repeat
		end if
	end repeat
	
	if not foundExisting then
		set end of errorRecoveryAttempts to {keyName:recoveryKey, attemptCount:newAttempts}
	end if
	
	-- 根据错误类型执行恢复策略
	if errorCategory is "NETWORK_ERROR" then
		return recoverFromNetworkError(errorMessage, context)
	else if errorCategory is "UI_ERROR" then
		return recoverFromUIError(errorMessage, context)
	else if errorCategory is "AUTH_ERROR" then
		return recoverFromAuthError(errorMessage, context)
	else if errorCategory is "SYSTEM_ERROR" then
		return recoverFromSystemError(errorMessage, context)
	else
		return recoverFromUnknownError(errorMessage, context)
	end if
end attemptErrorRecovery

-- 网络错误恢复
on recoverFromNetworkError(errorMessage, context)
	logDebug("INFO", "recoverFromNetworkError", "尝试恢复网络错误")
	
	-- 等待网络恢复
	delay 10
	
	-- 检查网络连接
	try
		do shell script "ping -c 1 apple.com"
		logDebug("INFO", "recoverFromNetworkError", "网络连接正常")
		return true
	on error
		logDebug("ERROR", "recoverFromNetworkError", "网络连接仍然异常")
		return false
	end try
end recoverFromNetworkError

-- UI错误恢复
on recoverFromUIError(errorMessage, context)
	logDebug("INFO", "recoverFromUIError", "尝试恢复UI错误")
	
	try
		-- 重新激活Messages应用
		tell application "Messages" to activate
		delay 3
		
		-- 检查应用是否响应
		tell application "System Events"
			tell process "Messages"
				set windowCount to count of windows
				if windowCount > 0 then
					logDebug("INFO", "recoverFromUIError", "Messages应用已恢复响应")
					return true
				else
					logDebug("ERROR", "recoverFromUIError", "Messages应用仍无响应")
					return false
				end if
			end tell
		end tell
	on error errMsg
		logDebug("ERROR", "recoverFromUIError", "UI恢复失败: " & errMsg)
		return false
	end try
end recoverFromUIError

-- 认证错误恢复
on recoverFromAuthError(errorMessage, context)
	logDebug("INFO", "recoverFromAuthError", "认证错误通常需要用户干预，无法自动恢复")
	return false
end recoverFromAuthError

-- 系统错误恢复
on recoverFromSystemError(errorMessage, context)
	logDebug("INFO", "recoverFromSystemError", "尝试恢复系统错误")
	
	try
		-- 重启System Events（如果可能）
		delay 5
		tell application "System Events" to activate
		delay 2
		logDebug("INFO", "recoverFromSystemError", "System Events已重新激活")
		return true
	on error errMsg
		logDebug("ERROR", "recoverFromSystemError", "系统错误恢复失败: " & errMsg)
		return false
	end try
end recoverFromSystemError

-- 未知错误恢复
on recoverFromUnknownError(errorMessage, context)
	logDebug("INFO", "recoverFromUnknownError", "尝试通用错误恢复策略")
	
	-- 通用恢复策略：等待并重试
	delay 5
	return true
end recoverFromUnknownError

-- 主函数
on run
	try
		logDebug("INFO", "run", "开始执行Apple ID自动登录脚本")
		
		-- 步骤1：读取Apple ID信息
		logDebug("INFO", "run", "步骤1：开始读取Apple ID信息")
		set {my appleID, my userPassword} to readAppleIDInfo()
		logDebug("INFO", "run", "步骤1完成：成功读取Apple ID: " & my appleID)
		
		-- 步骤2：切换到Messages应用并处理弹窗
		logDebug("INFO", "run", "步骤2：开始切换到Messages应用并处理弹窗")
		switchToMessagesAndHandleDialogs()
		logDebug("INFO", "run", "步骤2完成：Messages应用切换完成")
		
		-- 步骤3：打开账户标签页
		logDebug("INFO", "run", "步骤3：开始打开账户标签页")
		openAccountsTab()
		logDebug("INFO", "run", "步骤3完成：账户标签页状态 - " & accountsTabOpened)
		
		-- 步骤4：登录Apple ID（包含重试机制）
		if accountsTabOpened then
			logDebug("INFO", "run", "步骤4：开始登录Apple ID，最大尝试次数: " & maxLoginAttempts)
			loginAppleIDWithRetry(my appleID, my userPassword)
			logDebug("INFO", "run", "步骤4完成：登录尝试结束，当前尝试次数: " & currentLoginAttempt)
		else
			logDebug("ERROR", "run", "步骤4跳过：账户标签页未成功打开")
		end if
		
		-- 返回JSON结果
		logDebug("INFO", "run", "脚本执行完成，生成最终结果")
		return generateJSONResult()
		
	on error errMsg
		logDebug("ERROR", "run", "脚本执行失败: " & errMsg)
		
		-- 分析错误类型并尝试恢复
		set errorCategory to categorizeError(errMsg)
		logDebug("INFO", "run", "错误分类: " & errorCategory)
		
		-- 尝试错误恢复
		set recoverySuccessful to attemptErrorRecovery(errorCategory, errMsg, "main_execution")
		if recoverySuccessful then
			logDebug("INFO", "run", "错误恢复成功，尝试重新执行")
			try
				-- 重新执行关键步骤
				if not accountsTabOpened then
					openAccountsTab()
				end if
				if accountsTabOpened and currentLoginAttempt < maxLoginAttempts then
					loginAppleIDWithRetry(my appleID, my userPassword)
				end if
			on error secondErrMsg
				logDebug("ERROR", "run", "恢复后重新执行仍失败: " & secondErrMsg)
				set end of errorMessages to "脚本执行失败（恢复后）: " & secondErrMsg
			end try
		else
			logDebug("ERROR", "run", "错误恢复失败")
		end if
		
		set end of errorMessages to "脚本执行失败: " & errMsg & " (错误类型: " & errorCategory & ")"
		set overallSuccess to false
		return generateJSONResult()
	end try
end run

-- 读取Apple ID信息
on readAppleIDInfo()
	try
		logDebug("DEBUG", "readAppleIDInfo", "开始读取Apple ID信息")
		
		-- 获取appleid.txt文件路径
		set appleIDFile to getAppleIdFilePath()
		logDebug("DEBUG", "readAppleIDInfo", "目标文件路径: " & appleIDFile)
		
		-- 检查文件是否存在
		tell application "System Events"
			if not (exists file appleIDFile) then
				logDebug("ERROR", "readAppleIDInfo", "appleid.txt文件不存在，路径: " & appleIDFile)
				logDebug("INFO", "readAppleIDInfo", "请确保文件存在于指定路径，或检查appleIdFilePath配置")
				error "找不到文件\"file " & appleIDFile & "\"。请检查文件是否存在于指定路径。"
			end if
		end tell
		logDebug("DEBUG", "readAppleIDInfo", "文件存在性检查通过")
		
		-- 读取文件内容
		set fileContent to read file appleIDFile as string
		logDebug("DEBUG", "readAppleIDInfo", "文件内容长度: " & (length of fileContent) & " 字符")
		
		-- 获取第一行（使用换行符分割）
		logDebug("DEBUG", "readAppleIDInfo", "开始解析文件内容")
		set AppleScript's text item delimiters to return
		set fileLines to text items of fileContent
		if length of fileLines = 1 then
			-- 尝试使用 linefeed 分割
			logDebug("DEBUG", "readAppleIDInfo", "使用linefeed重新分割文件行")
			set AppleScript's text item delimiters to linefeed
			set fileLines to text items of fileContent
		end if
		set AppleScript's text item delimiters to ""
		logDebug("DEBUG", "readAppleIDInfo", "文件总行数: " & (length of fileLines))
		
		-- 找到第一行有内容的行
		set firstLine to ""
		repeat with i from 1 to length of fileLines
			set lineText to item i of fileLines as string
			if length of lineText > 0 then
				set firstLine to lineText
				logDebug("DEBUG", "readAppleIDInfo", "找到第一行有效内容，行号: " & i)
				exit repeat
			end if
		end repeat
		
		if firstLine is not "" then
			logDebug("DEBUG", "readAppleIDInfo", "开始解析账户信息，原始内容长度: " & (length of firstLine))
			-- 解析格式：email----password----phone----api_url
			set AppleScript's text item delimiters to "----"
			set accountParts to text items of firstLine
			set AppleScript's text item delimiters to ""
			logDebug("DEBUG", "readAppleIDInfo", "分割后的部分数量: " & (length of accountParts))
			
			if length of accountParts >= 2 then
				-- 直接获取字符串，不进行复杂处理
				set appleID to (item 1 of accountParts) as string
				set userPassword to (item 2 of accountParts) as string
				logDebug("DEBUG", "readAppleIDInfo", "原始Apple ID: '" & appleID & "', 密码长度: " & (length of userPassword))
				
				-- 简单去除前后空格
				if appleID starts with " " then set appleID to text 2 thru -1 of appleID
				if appleID ends with " " then set appleID to text 1 thru -2 of appleID
				if userPassword starts with " " then set userPassword to text 2 thru -1 of userPassword
				if userPassword ends with " " then set userPassword to text 1 thru -2 of userPassword
				logDebug("INFO", "readAppleIDInfo", "处理后的Apple ID: '" & appleID & "', 密码长度: " & (length of userPassword))
				
				set end of executionResults to {stepName:"step1_read_file", success:true, message:"成功读取Apple ID: " & appleID, timestamp:(current date) as string}
				logDebug("INFO", "readAppleIDInfo", "Apple ID信息读取成功")
				
				return {appleID, userPassword}
			else
				logDebug("ERROR", "readAppleIDInfo", "文件格式错误，分割部分不足2个")
				error "文件格式不正确，需要包含----分隔符"
			end if
		else
			logDebug("ERROR", "readAppleIDInfo", "未找到有效的文件内容")
			error "文件为空或没有有效内容"
		end if
		
	on error errMsg
		logDebug("ERROR", "readAppleIDInfo", "读取Apple ID信息时发生错误: " & errMsg)
		set end of executionResults to {stepName:"step1_read_file", success:false, message:"读取文件失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "文件读取失败: " & errMsg
		set overallSuccess to false
		error errMsg
	end try
end readAppleIDInfo

-- 切换到Messages应用并处理系统弹窗
on switchToMessagesAndHandleDialogs()
	try
		logDebug("INFO", "switchToMessagesAndHandleDialogs", "开始切换到Messages应用")
		tell application "Messages" to activate
		logDebug("DEBUG", "switchToMessagesAndHandleDialogs", "Messages应用激活命令已发送，等待3秒")
		delay 3
		set end of executionResults to {stepName:"step2_switch_app", success:true, message:"成功切换到Messages应用", timestamp:(current date) as string}
		logDebug("INFO", "switchToMessagesAndHandleDialogs", "Messages应用切换成功")
		
		-- 处理系统弹窗
		logDebug("DEBUG", "switchToMessagesAndHandleDialogs", "开始处理系统弹窗")
		handleSystemDialogs()
		logDebug("DEBUG", "switchToMessagesAndHandleDialogs", "系统弹窗处理完成")
		
	on error errMsg
		logDebug("ERROR", "switchToMessagesAndHandleDialogs", "切换到Messages应用失败: " & errMsg)
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
						set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'帐户'标签", timestamp:(current date) as string}
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
							set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'账户'标签", timestamp:(current date) as string}
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
							set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击'Accounts'标签", timestamp:(current date) as string}
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
							set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"成功点击第二个工具栏按钮", timestamp:(current date) as string}
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
									set end of executionResults to {stepName:"step7_accounts_tab", success:true, message:"通过索引成功点击账户按钮: " & buttonName, timestamp:(current date) as string}
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
		
		-- 在System Events块外部进行日志记录
		logDebug("DEBUG", "openAccountsTab", "工具栏是否存在: " & toolbarExists)
		logDebug("DEBUG", "openAccountsTab", "工具栏按钮数量: " & toolbarButtonCount)
		
		-- 输出按钮信息
		repeat with buttonInfo in buttonNames
			logDebug("DEBUG", "openAccountsTab", buttonInfo)
		end repeat
		
		if tabClicked then
			set accountsTabOpened to true
			logDebug("INFO", "openAccountsTab", "账户标签页成功打开，使用" & clickMethod & "，按钮名称: " & clickedButtonName)
			delay 2 -- 等待页面加载
		else
			set accountsTabOpened to false
			logDebug("ERROR", "openAccountsTab", "所有方法都无法找到账户标签按钮")
			set end of executionResults to {stepName:"step7_accounts_tab", success:false, message:"所有方法都无法找到账户标签按钮", timestamp:(current date) as string}
			-- 不抛出错误，让脚本继续执行并记录详细信息
		end if
		
	on error errMsg
		set accountsTabOpened to false
		logDebug("ERROR", "openAccountsTab", "打开账户标签页时发生异常: " & errMsg)
		set end of executionResults to {stepName:"step6_7_accounts", success:false, message:"打开账户标签失败: " & errMsg, timestamp:(current date) as string}
		set end of errorMessages to "账户标签操作失败: " & errMsg
		set overallSuccess to false
	end try
end openAccountsTab

-- 带重试机制的登录函数（增强版）
on loginAppleIDWithRetry(appleID, userPassword)
	logDebug("INFO", "loginAppleIDWithRetry", "开始带重试机制的登录流程，最大尝试次数: " & maxLoginAttempts)
	
	set currentLoginAttempt to 0
	set loginSuccessful to false
	set passwordErrorCount to 0
	set verificationErrorCount to 0
	set consecutiveFailures to 0
	set lastErrorType to ""
	
	repeat while currentLoginAttempt < maxLoginAttempts and not loginSuccessful
		set currentLoginAttempt to currentLoginAttempt + 1
		logDebug("INFO", "loginAppleIDWithRetry", "开始第 " & currentLoginAttempt & " 次登录尝试")
		set end of executionResults to {stepName:"step8_login_attempt", success:true, message:"开始第 " & currentLoginAttempt & " 次登录尝试", timestamp:(current date) as string}
		
		try
			-- 使用超时控制的登录尝试
			set loginStartTime to (current date)
			set loginResult to loginAppleIDSingleAttemptWithTimeout(appleID, userPassword, currentLoginAttempt, loginTimeout)
			set loginEndTime to (current date)
			set loginDuration to (loginEndTime - loginStartTime)
			
			logDebug("DEBUG", "loginAppleIDWithRetry", "第 " & currentLoginAttempt & " 次登录尝试完成，耗时: " & loginDuration & " 秒，结果: " & loginResult)
			
			if loginResult is "SUCCESS" then
				set loginSuccessful to true
				set consecutiveFailures to 0
				logDebug("INFO", "loginAppleIDWithRetry", "登录成功，开始处理验证码流程")
				set end of executionResults to {stepName:"step8_login_success", success:true, message:"第 " & currentLoginAttempt & " 次尝试登录成功，开始等待验证码窗口", timestamp:(current date) as string}
				
				-- 使用超时控制等待验证码窗口
				set verificationResult to waitForVerificationWindowWithTimeout(verificationTimeout)
				set end of executionResults to {stepName:"step8_verification_completed", success:verificationResult, message:"验证码窗口等待完成，结果: " & verificationResult, timestamp:(current date) as string}
				
				-- 处理验证码输入
				set testVerificationCode to getVerificationCode()
				set inputResult to inputVerificationCodeWithTimeout(testVerificationCode, uiResponseTimeout)
				set end of executionResults to {stepName:"step8_verification_input", success:inputResult, message:"验证码输入完成，结果: " & inputResult, timestamp:(current date) as string}
				
			else if loginResult is "VERIFICATION_NEEDED" then
				set loginSuccessful to true
				set consecutiveFailures to 0
				logDebug("INFO", "loginAppleIDWithRetry", "登录需要验证码，开始验证码处理流程")
				set end of executionResults to {stepName:"step8_login_verification", success:true, message:"第 " & currentLoginAttempt & " 次尝试需要验证码", timestamp:(current date) as string}
				
				-- 使用超时控制等待验证码窗口
				set verificationResult to waitForVerificationWindowWithTimeout(verificationTimeout)
				set end of executionResults to {stepName:"step8_verification_completed", success:verificationResult, message:"验证码窗口等待完成，结果: " & verificationResult, timestamp:(current date) as string}
				
				-- 处理验证码输入
				set testVerificationCode to getVerificationCode()
				set inputResult to inputVerificationCodeWithTimeout(testVerificationCode, uiResponseTimeout)
				set end of executionResults to {stepName:"step8_verification_input", success:inputResult, message:"验证码输入完成，结果: " & inputResult, timestamp:(current date) as string}
				
			else if loginResult is "PASSWORD_ERROR" then
				-- 密码错误处理
				set passwordErrorCount to passwordErrorCount + 1
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "PASSWORD_ERROR"
				logDebug("WARN", "loginAppleIDWithRetry", "密码错误，累计次数: " & passwordErrorCount)
				set end of executionResults to {stepName:"step8_password_error", success:false, message:"第 " & currentLoginAttempt & " 次登录密码错误（累计 " & passwordErrorCount & " 次）", timestamp:(current date) as string}
				
				if passwordErrorCount >= maxPasswordErrors then
					logDebug("ERROR", "loginAppleIDWithRetry", "密码错误次数超过限制，停止重试")
					set end of executionResults to {stepName:"step8_password_error_limit", success:false, message:"密码错误次数过多，停止登录尝试", timestamp:(current date) as string}
					set end of errorMessages to "Apple ID密码不正确，已尝试 " & passwordErrorCount & " 次"
					set overallSuccess to false
					exit repeat
				else
					-- 智能重试延迟：根据错误次数增加延迟时间
					set dynamicDelay to retryDelay + (passwordErrorCount * 2)
					logDebug("INFO", "loginAppleIDWithRetry", "密码错误，将在 " & dynamicDelay & " 秒后重试")
					set end of executionResults to {stepName:"step8_password_retry", success:true, message:"密码错误，将在 " & dynamicDelay & " 秒后重试", timestamp:(current date) as string}
					delay dynamicDelay
				end if
				
			else if loginResult is "ACCOUNT_ERROR" then
				-- 账户错误，不需要重试
				set lastErrorType to "ACCOUNT_ERROR"
				logDebug("ERROR", "loginAppleIDWithRetry", "账户不存在或无效，停止重试")
				set end of executionResults to {stepName:"step8_account_error", success:false, message:"Apple ID账户不存在或无效，停止重试", timestamp:(current date) as string}
				set end of errorMessages to "Apple ID账户不存在或无效"
				set overallSuccess to false
				exit repeat
				
			else if loginResult is "VERIFICATION_FAILED" then
				-- 验证失败处理
				set verificationErrorCount to verificationErrorCount + 1
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "VERIFICATION_FAILED"
				logDebug("WARN", "loginAppleIDWithRetry", "验证失败，累计次数: " & verificationErrorCount)
				set end of executionResults to {stepName:"step8_verification_failed", success:false, message:"第 " & currentLoginAttempt & " 次登录验证失败（累计 " & verificationErrorCount & " 次）", timestamp:(current date) as string}
				
				if verificationErrorCount >= maxVerificationErrors then
					logDebug("ERROR", "loginAppleIDWithRetry", "验证失败次数超过限制，停止重试")
					set end of executionResults to {stepName:"step8_verification_error_limit", success:false, message:"验证失败次数过多，停止登录尝试", timestamp:(current date) as string}
					set end of errorMessages to "登录验证失败次数过多，已尝试 " & verificationErrorCount & " 次"
					set overallSuccess to false
					exit repeat
				else if currentLoginAttempt < maxLoginAttempts then
					-- 验证失败后使用更长的延迟时间
					set verificationDelay to retryDelay + (verificationErrorCount * 3)
					logDebug("INFO", "loginAppleIDWithRetry", "验证失败，将在 " & verificationDelay & " 秒后重试")
					set end of executionResults to {stepName:"step8_verification_retry", success:true, message:"验证失败，将在 " & verificationDelay & " 秒后重试", timestamp:(current date) as string}
					delay verificationDelay
				end if
				
			else if loginResult is "TIMEOUT" then
				-- 超时处理
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "TIMEOUT"
				logDebug("WARN", "loginAppleIDWithRetry", "登录操作超时")
				set end of executionResults to {stepName:"step8_login_timeout", success:false, message:"第 " & currentLoginAttempt & " 次登录操作超时", timestamp:(current date) as string}
				
				if currentLoginAttempt < maxLoginAttempts then
					-- 超时后使用较长的延迟时间
					set timeoutDelay to retryDelay + 5
					logDebug("INFO", "loginAppleIDWithRetry", "超时后将在 " & timeoutDelay & " 秒后重试")
					set end of executionResults to {stepName:"step8_timeout_retry", success:true, message:"超时后将在 " & timeoutDelay & " 秒后重试", timestamp:(current date) as string}
					delay timeoutDelay
				end if
				
			else
				-- 其他未知错误
				set consecutiveFailures to consecutiveFailures + 1
				set lastErrorType to "UNKNOWN_ERROR"
				logDebug("WARN", "loginAppleIDWithRetry", "未知登录错误: " & loginResult)
				set end of executionResults to {stepName:"step8_login_failed", success:false, message:"第 " & currentLoginAttempt & " 次登录失败: " & loginResult, timestamp:(current date) as string}
				
				if currentLoginAttempt < maxLoginAttempts then
					-- 根据连续失败次数调整延迟时间
					set adaptiveDelay to retryDelay + (consecutiveFailures * 2)
					logDebug("INFO", "loginAppleIDWithRetry", "将在 " & adaptiveDelay & " 秒后重试")
					set end of executionResults to {stepName:"step8_adaptive_retry", success:true, message:"将在 " & adaptiveDelay & " 秒后重试", timestamp:(current date) as string}
					delay adaptiveDelay
				end if
			end if
			
		on error errMsg
			set consecutiveFailures to consecutiveFailures + 1
			logDebug("ERROR", "loginAppleIDWithRetry", "第 " & currentLoginAttempt & " 次登录出现异常: " & errMsg)
			set end of executionResults to {stepName:"step8_login_error", success:false, message:"第 " & currentLoginAttempt & " 次登录出现错误: " & errMsg, timestamp:(current date) as string}
			
			
			if currentLoginAttempt < maxLoginAttempts then
				-- 异常后使用基础延迟时间
				logDebug("INFO", "loginAppleIDWithRetry", "异常后将在 " & retryDelay & " 秒后重试")
				set end of executionResults to {stepName:"step8_exception_retry", success:true, message:"异常后将在 " & retryDelay & " 秒后重试", timestamp:(current date) as string}
				delay retryDelay
			end if
		end try
	end repeat
	
	-- 最终结果处理
	if not loginSuccessful then
		logDebug("ERROR", "loginAppleIDWithRetry", "所有登录尝试均失败，最后错误类型: " & lastErrorType)
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
		logDebug("INFO", "loginAppleIDWithRetry", "登录流程成功完成")
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

-- 改进的登录结果检查（带状态监控）
on checkLoginResult()
	logDebug("INFO", "checkLoginResult", "开始检查登录结果")
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
					logDebug("INFO", "checkLoginResult", "第 " & checkCount & " 次状态检查")
					
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
									logDebug("DEBUG", "checkLoginResult", "检查UI元素: " & elementValue)
									
									-- 检查Apple ID或密码错误的各种表述
									if elementValue contains "您的 Apple ID 或密码不正确" or elementValue contains "Apple ID 或密码不正确" or elementValue contains "密码不正确" or elementValue contains "incorrect password" or elementValue contains "密码错误" or elementValue contains "wrong password" or elementValue contains "Invalid Apple ID or password" or elementValue contains "Apple ID or password is incorrect" or elementValue contains "登录信息不正确" then
										set errorFound to true
										set errorMessage to elementValue
										logDebug("ERROR", "checkLoginResult", "检测到密码错误: " & elementValue)
										set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到密码错误信息: " & elementValue, timestamp:(current date) as string}
										return "PASSWORD_ERROR"
									end if
									
									-- 检查账户相关错误
									if elementValue contains "账户不存在" or elementValue contains "account does not exist" or elementValue contains "无效的用户名" or elementValue contains "invalid username" or elementValue contains "Apple ID不存在" or elementValue contains "Apple ID does not exist" or elementValue contains "此Apple ID不存在" or elementValue contains "账户无效" then
										set errorFound to true
										set errorMessage to elementValue
										logDebug("ERROR", "checkLoginResult", "检测到账户错误: " & elementValue)
										set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到账户不存在错误: " & elementValue, timestamp:(current date) as string}
										return "ACCOUNT_ERROR"
									end if
									
									-- 检查验证失败
									if elementValue contains "验证失败" or elementValue contains "verification failed" or elementValue contains "鉴定失败" or elementValue contains "authentication failed" or elementValue contains "登录失败" or elementValue contains "login failed" or elementValue contains "身份验证失败" then
										set errorFound to true
										set errorMessage to elementValue
										logDebug("ERROR", "checkLoginResult", "检测到验证失败: " & elementValue)
										set end of executionResults to {stepName:"step8_check_result", success:false, message:"检测到验证失败错误: " & elementValue, timestamp:(current date) as string}
										return "VERIFICATION_FAILED"
									end if
								
								-- 检查是否需要验证码
										if elementValue contains "验证码" or elementValue contains "verification code" or elementValue contains "输入验证码" or elementValue contains "enter code" or elementValue contains "双重认证" or elementValue contains "two-factor" or elementValue contains "输入代码" or elementValue contains "安全代码" then
											set verificationNeeded to true
											logDebug("INFO", "checkLoginResult", "检测到需要验证码: " & elementValue)
											set end of executionResults to {stepName:"step8_check_result", success:true, message:"检测到需要验证码: " & elementValue, timestamp:(current date) as string}
										end if
										
										-- 检查是否登录成功
										if elementValue contains "已登录" or elementValue contains "signed in" or elementValue contains "登录成功" or elementValue contains "connected" or elementValue contains "iMessage" or elementValue contains "Messages" or elementValue contains "账户已连接" or elementValue contains "Account connected" then
											set loginSuccess to true
											logDebug("INFO", "checkLoginResult", "检测到登录成功: " & elementValue)
											set end of executionResults to {stepName:"step8_check_result", success:true, message:"检测到登录成功信息: " & elementValue, timestamp:(current date) as string}
										end if
									end if
									
								end try
							end repeat
					end try
					
					-- 如果没有明确结果，等待后再次检查
					if not errorFound and not verificationNeeded and not loginSuccess and checkCount < loginStatusMaxChecks then
						logDebug("INFO", "checkLoginResult", "状态不明确，等待 " & loginStatusCheckInterval & " 秒后再次检查")
						delay loginStatusCheckInterval
					end if
				end repeat
				
				
				-- 根据检查结果返回相应状态
				logDebug("INFO", "checkLoginResult", "状态检查完成，错误: " & errorFound & "，验证: " & verificationNeeded & "，成功: " & loginSuccess)
				
				if errorFound then
					logDebug("ERROR", "checkLoginResult", "检测到登录错误")
					return "LOGIN_ERROR"
				else if verificationNeeded then
					logDebug("INFO", "checkLoginResult", "需要验证码")
					return "VERIFICATION_NEEDED"
				else if loginSuccess then
					logDebug("INFO", "checkLoginResult", "登录成功")
					return "SUCCESS"
				else
					-- 如果经过多次检查仍无明确结果，进行最后的快速检查
					logDebug("WARNING", "checkLoginResult", "经过 " & checkCount & " 次检查仍无明确结果，进行最后检查")
					delay 3
					if my quickCheckForSuccess() then
						logDebug("INFO", "checkLoginResult", "最后检查确认登录成功")
						return "SUCCESS"
					else
						logDebug("WARNING", "checkLoginResult", "状态仍然不明确")
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

-- 验证码输入函数
on inputVerificationCode(testCode)
	try
		set codeInputSuccess to false
		set end of executionResults to {stepName:"step9b_input_verification", success:true, message:"开始输入验证码: " & testCode, timestamp:(current date) as string}
		
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
									set end of executionResults to {stepName:"step9b_input_verification", success:true, message:"在主窗口成功输入验证码到输入框: " & placeholderText, timestamp:(current date) as string}
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
											set end of executionResults to {stepName:"step9b_input_verification", success:true, message:"在对话框中成功输入验证码到输入框: " & placeholderText, timestamp:(current date) as string}
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
						set end of executionResults to {stepName:"step9b_input_verification", success:true, message:"通过通用键盘输入方式输入验证码", timestamp:(current date) as string}
					end try
				end if
				
				-- 输入完成后，尝试提交验证码
				if codeInputSuccess then
					delay 1
					-- 尝试按回车键提交
					try
						key code 36 -- 回车键
						set end of executionResults to {stepName:"step9c_submit_verification", success:true, message:"按回车键提交验证码", timestamp:(current date) as string}
					end try
					
					-- 或者尝试点击提交按钮
					try
						set submitButtons to every button of window 1
						repeat with submitButton in submitButtons
							try
								set buttonTitle to title of submitButton
								if buttonTitle contains "提交" or buttonTitle contains "确定" or buttonTitle contains "Submit" or buttonTitle contains "OK" or buttonTitle contains "Continue" then
									click submitButton
									set end of executionResults to {stepName:"step9c_submit_verification", success:true, message:"点击提交按钮: " & buttonTitle, timestamp:(current date) as string}
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
										set end of executionResults to {stepName:"step9c_submit_verification", success:true, message:"在对话框中点击提交按钮: " & buttonTitle, timestamp:(current date) as string}
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
			set end of executionResults to {stepName:"step9b_input_verification", success:false, message:"未能找到验证码输入框或输入失败", timestamp:(current date) as string}
		end if
		
		return codeInputSuccess
		
	on error errMsg
		set end of executionResults to {stepName:"step9b_input_verification", success:false, message:"输入验证码时出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end inputVerificationCode


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
	
	-- 添加debug日志信息
	set jsonResult to jsonResult & "\"debugLogs\":["
	repeat with i from 1 to length of debugMessages
		set currentDebug to item i of debugMessages
		set jsonResult to jsonResult & "{"
		set jsonResult to jsonResult & "\"level\":\"" & (level of currentDebug) & "\","
		set jsonResult to jsonResult & "\"function\":\"" & (function of currentDebug) & "\","
		set jsonResult to jsonResult & "\"message\":\"" & (message of currentDebug) & "\","
		set jsonResult to jsonResult & "\"timestamp\":\"" & (timestamp of currentDebug) & "\""
		set jsonResult to jsonResult & "}"
		if i < length of debugMessages then
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

-- 带超时控制的单次登录尝试
on loginAppleIDSingleAttemptWithTimeout(appleID, userPassword, attemptNumber)
	logDebug("INFO", "loginAppleIDSingleAttemptWithTimeout", "开始带超时控制的登录尝试，超时时间: " & loginTimeout & " 秒")
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
				logDebug("WARNING", "loginAppleIDSingleAttemptWithTimeout", "登录过程中出现错误: " & errMsg)
				delay 2
			end try
		end repeat
		
		logDebug("WARNING", "loginAppleIDSingleAttemptWithTimeout", "登录操作超时 (" & loginTimeout & " 秒)")
		return "TIMEOUT"
	on error errMsg
		logDebug("ERROR", "loginAppleIDSingleAttemptWithTimeout", "登录过程中发生错误: " & errMsg)
		return "ERROR"
	end try
end loginAppleIDSingleAttemptWithTimeout

-- 带超时控制的验证窗口等待
on waitForVerificationWindowWithTimeout()
	logDebug("INFO", "waitForVerificationWindowWithTimeout", "开始等待验证窗口，超时时间: " & verificationTimeout & " 秒")
	set startTime to (current date)
	
	repeat while ((current date) - startTime) < verificationTimeout
		try
			if waitForVerificationWindow() then
				logDebug("INFO", "waitForVerificationWindowWithTimeout", "验证窗口已出现")
				return true
			end if
			delay 2
		on error errMsg
			logDebug("WARNING", "waitForVerificationWindowWithTimeout", "等待验证窗口时出现错误: " & errMsg)
			delay 2
		end try
	end repeat
	
	logDebug("WARNING", "waitForVerificationWindowWithTimeout", "等待验证窗口超时 (" & verificationTimeout & " 秒)")
	return false
end waitForVerificationWindowWithTimeout

-- 带超时控制的验证码输入
on inputVerificationCodeWithTimeout(verificationCode, timeoutSeconds)
	logDebug("INFO", "inputVerificationCodeWithTimeout", "开始输入验证码: " & verificationCode & "，超时时间: " & timeoutSeconds & " 秒")
	set startTime to (current date)
	
	repeat while ((current date) - startTime) < timeoutSeconds
		try
			logDebug("DEBUG", "inputVerificationCodeWithTimeout", "尝试输入验证码: " & verificationCode)
			set inputResult to inputVerificationCode(verificationCode)
			if inputResult then
				logDebug("INFO", "inputVerificationCodeWithTimeout", "验证码输入成功")
				return true
			end if
			delay 1
		on error errMsg
			logDebug("WARNING", "inputVerificationCodeWithTimeout", "输入验证码时出现错误: " & errMsg)
			delay 1
		end try
	end repeat
	
	logDebug("WARNING", "inputVerificationCodeWithTimeout", "输入验证码超时 (" & timeoutSeconds & " 秒)")
	return false
end inputVerificationCodeWithTimeout

-- 获取验证码函数
on getVerificationCode()
	try
		logDebug("INFO", "getVerificationCode", "验证码获取模式: " & verificationCodeMode)
		
		if verificationCodeMode is 1 then
			-- 模式1：自定义输入，直接使用customVerificationCode，绝不调用API
			logDebug("INFO", "getVerificationCode", "强制使用自定义验证码（模式1）: " & customVerificationCode)
			-- 额外检查：确保不会意外使用appleid.txt中的数字
			if customVerificationCode contains "61659" or customVerificationCode contains "250813" then
				logDebug("ERROR", "getVerificationCode", "检测到自定义验证码包含appleid.txt中的数字，强制使用666666")
				return "666666"
			else
				return customVerificationCode
			end if
			
		else if verificationCodeMode is 2 then
			-- 模式2：API获取（已禁用，直接使用自定义验证码）
			logDebug("WARNING", "getVerificationCode", "API模式已禁用，使用自定义验证码: " & customVerificationCode)
			return customVerificationCode
			
		else
			-- 未知模式，使用自定义验证码
			logDebug("WARNING", "getVerificationCode", "未知的验证码模式: " & verificationCodeMode & "，使用自定义验证码: " & customVerificationCode)
			return customVerificationCode
		end if
		
	on error errMsg
		logDebug("ERROR", "getVerificationCode", "获取验证码时出错: " & errMsg)
		return customVerificationCode -- 出错时返回自定义验证码
	end try
end getVerificationCode

-- 设置自定义验证码函数
on setCustomVerificationCode(newCode)
	try
		set customVerificationCode to newCode
		logDebug("INFO", "setCustomVerificationCode", "已设置自定义验证码: " & newCode)
		return true
	on error errMsg
		logDebug("ERROR", "setCustomVerificationCode", "设置自定义验证码时出错: " & errMsg)
		return false
	end try
end setCustomVerificationCode

-- API获取验证码函数已删除，只使用自定义验证码模式