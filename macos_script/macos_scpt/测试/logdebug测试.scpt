
property customVerificationCode : "66666" -- 自定义验证码，如果为空则使用默认测试验证码
inputVerificationCode()

-- 简单的iMessage验证码输入函数
on inputVerificationCode()
	try
		-- 激活Messages应用
		tell application "Messages" to activate
		delay 1
		
		tell application "System Events"
			tell process "Messages"
				set frontmost to true
				delay 0.5
				
				-- 检查验证码对话框是否存在
				if exists sheet 1 of window "帐户" then
					
					-- 将验证码复制到剪贴板
					set the clipboard to customVerificationCode as string
					delay 0.2
					
					-- 点击对话框获取焦点
					click sheet 1 of window "帐户"
					delay 0.3
					
					-- 粘贴验证码
					keystroke "v" using command down
					
					return true
				else
					return false
				end if
			end tell
		end tell
		
	on error
		return false
	end try
end inputVerificationCode