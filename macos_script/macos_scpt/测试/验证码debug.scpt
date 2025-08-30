    checkLoginMsgStatus()
--continuousMonitorLoginResult()
-- 持续监控函数（新版本）
on continuousMonitorLoginResult()
	try
		set maxRetryAttempts to 3 -- 最大重试次数
		set currentRetryCount to 0
		
		-- 主监控循环
		repeat
			-- 第一步：检查登录忙碌状态
			set busyStatus to checkLoginProcessingStatus()
			set msgStatus to checkLoginMsgStatus()
			set loginStatus to checkLoginStatus()
			if busyStatus is "LOGIN_BUSY" then
				-- 如果正在登录中，等待5秒后继续检测
				display dialog 1111
				delay 5
			else if busyStatus is "LOGIN_NO_BUSY" then
				-- 第二步：检查登录消息状态
				
				display dialog 2222
				if msgStatus is "VERIFICATION_NEEDED" then
					-- 需要双重验证码，自动输入测试验证码
					display dialog 3333
				else if msgStatus is "NO_VERIFICATION_NEEDED" then
					-- 第三步：检查登录状态
					display dialog 4444
					
					log "登录状态检测结果: " & loginStatus
					
					if loginStatus is "LOGIN_ERROR" or loginStatus is "LOGIN_BUTTON_IN" or loginStatus is "LOGIN_PASSWORD_ERROR" then
						-- 检测到登录失败，进行重试
						if currentRetryCount < maxRetryAttempts then
							set currentRetryCount to currentRetryCount + 1
							
							-- 等待3秒后重新登录
							delay 3
							
							-- 重新登录
							display dialog 55555
							--findAndClickLoginButton()
							
							-- 继续监控循环
						else
							-- 达到最大重试次数，最后检查一次是否需要验证码
							delay 2
							set finalMsgStatus to checkLoginMsgStatus()
							if finalMsgStatus is "VERIFICATION_NEEDED" then
								-- 出现验证码输入框，进行验证码输入
							else
								-- 确实没有验证码，登录失败
								return "登录失败，已达到最大重试次数"
							end if
						end if
					else if loginStatus is "LOGIN_SUCCESS" then
						-- 登录成功
						return "登录成功"
					else
						-- 其他状态，继续监控
						delay 5
					end if
				else
					-- 消息状态检测出错，继续监控
					delay 5
				end if
			else
				-- 忙碌状态检测出错，继续监控
				delay 5
			end if
		end repeat
		
	on error errMsg
		return "监控过程出错: " & errMsg
	end try
end continuousMonitorLoginResult





-- 检测登录忙碌状态函数
on checkLoginProcessingStatus()
	delay 3
	try
		tell application "System Events"
			tell process "Messages"
				tell window "帐户"
					if exists (busy indicator 1 of sheet 1) then
						--log "菊花转出现了"
						return "LOGIN_BUSY"
					else
						--log "没有菊花转"
						return "LOGIN_NO_BUSY"
					end if
					
				end tell
			end tell
		end tell
	on error errMsg
		return "LOGIN_NO_BUSY"
	end try
end checkLoginProcessingStatus



-- 检测登录消息状态函数
on checkLoginMsgStatus()
	try
		tell application "System Events"
			tell process "Messages"
				-- 检查是否需要双重验证码
				try
					-- 检查验证码输入框
					if static text "输入发送至 " of group 2 of group 1 of UI element 1 of scroll area 1 of sheet 1 of window "帐户" exists then
						return "VERIFICATION_NEEDED"
					end if
					
				end try
				
				-- 默认返回不需要验证
				return "NO_VERIFICATION_NEEDED"
			end tell
		end tell
	on error errMsg
		return "CHECK_ERROR"
	end try
end checkLoginMsgStatus


-- 检测登录状态函数（增强版）
on checkLoginStatus()
	try
		tell application "System Events"
			tell process "Messages"
				
				-- 检查是否有密码错误提示
				try
					tell window "帐户"
						set errorTexts to every static text of group 1 of group 1
						repeat with t in errorTexts
							set msg to (value of t as text)
							if msg contains "密码错误" or msg contains "密码不正确" or msg contains "Password incorrect" or msg contains "Wrong password" or msg contains "不正确。" or msg contains "incorrect" then
								return "LOGIN_PASSWORD_ERROR"
								exit repeat
							end if
						end repeat
					end tell
				end try
				
				-- 检查是否有一般登录错误提示
				try
					tell window "帐户"
						set errorTexts to every static text of group 1 of group 1
						repeat with t in errorTexts
							set msg to (value of t as text)
							if msg contains "登录失败" or msg contains "登录错误" or msg contains "Login failed" or msg contains "Login error" or msg contains "Authentication failed" or msg contains "出错" then
								return "LOGIN_ERROR"
								exit repeat
							end if
						end repeat
					end tell
				end try
				
				-- 检查是否还有登录按钮（表示需要登录或登录失败）
				try
					tell window "帐户"
						if exists button "登录" of group 1 of group 1 then
							--log "检测到登录 "
							return "LOGIN_BUTTON_IN"
						end if
						
					end tell
				end try
				
				-- 默认返回未知状态
				return "UNKNOWN"
			end tell
		end tell
	on error errMsg
		return "CHECK_ERROR"
	end try
end checkLoginStatus