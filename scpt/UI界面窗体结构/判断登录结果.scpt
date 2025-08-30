
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
checkLoginStatus()
on checkLoginStatus()
	try
		tell application "System Events"
			tell process "Messages"
				-- 首先检查是否有验证码输入框
					
				--检测是否成功	return "IM_SUCESSFULL"
				try
					tell window "帐户"
						if exists button "注销" of tab group 1 of group 1  then
							--log "检测到登录 "
							return "IM_SUCESSFULL"
						end if
						
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