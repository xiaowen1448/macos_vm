-- 系统对话框处理脚本
-- 处理Apple ID登录弹窗
tell application "Messages" to activate
delay 3

-- 初始化结果变量
set executionResults to {}
set overallSuccess to true
set errorMessages to {}

tell application "System Events"
	tell process "Messages"
		set firstButtonClicked to false
		
		-- 第一步: 在Messages进程中深度查找"以后"按钮
		try
			-- 获取所有UI元素
			set allElements to entire contents
			repeat with element in allElements
				try
					if class of element is button then
						try
							set elementName to name of element
							if elementName contains "以后" or elementName contains "Later" or elementName contains "稍后" then
								click element
								--log "第一步成功: 在UI树中找到并点击: " & elementName
								set firstButtonClicked to true
								set end of executionResults to {stepName:"step1_later_button", success:true, message:"成功点击'以后'按钮: " & elementName, timestamp:(current date) as string}
								exit repeat
							end if
						end try
					end if
				end try
			end repeat
			
			if not firstButtonClicked then
				set end of executionResults to {stepName:"step1_later_button", success:false, message:"未找到'以后'按钮", timestamp:(current date) as string}
				set end of errorMessages to "第一步失败：未找到'以后'按钮"
				set overallSuccess to false
			end if
		on error errMsg
			set end of executionResults to {stepName:"step1_later_button", success:false, message:"第一步执行错误: " & errMsg, timestamp:(current date) as string}
			set end of errorMessages to "第一步执行错误: " & errMsg
			set overallSuccess to false
		end try
		
		-- 如果第一个按钮成功点击，等待3秒后处理对话框
		if firstButtonClicked then
			--log "等待3秒后查找跳过按钮..."
			delay 3
			
			-- 第二步: 在对话框中查找"跳过"按钮
			set secondButtonClicked to false
			try
				set allSheets to every sheet of window 1
				repeat with currentSheet in allSheets
					set sheetButtons to every button of currentSheet
					repeat with sheetButton in sheetButtons
						try
							set buttonName to name of sheetButton
							if buttonName contains "跳过" or buttonName contains "Skip" or buttonName contains "skip" then
								click sheetButton
								--log "第二步成功: 在对话框中找到并点击了按钮: " & buttonName
								set secondButtonClicked to true
								set end of executionResults to {stepName:"step2_skip_button", success:true, message:"成功在对话框中点击'跳过'按钮: " & buttonName, timestamp:(current date) as string}
								exit repeat
							end if
						end try
					end repeat
					if secondButtonClicked then exit repeat
				end repeat
			end try
			
			-- 如果在sheet中没找到，尝试其他位置
			if not secondButtonClicked then
				try
					-- 尝试在主窗口中查找
					set allButtons to every button of window 1
					repeat with currentButton in allButtons
						try
							set buttonName to name of currentButton
							if buttonName contains "跳过" or buttonName contains "Skip" or buttonName contains "skip" then
								click currentButton
								--log "第二步成功: 在主窗口中找到并点击了按钮: " & buttonName
								set secondButtonClicked to true
								set end of executionResults to {stepName:"step2_skip_button", success:true, message:"成功在主窗口中点击'跳过'按钮: " & buttonName, timestamp:(current date) as string}
								exit repeat
							end if
						end try
					end repeat
				end try
			end if
			
			-- 如果还没找到，进行全局搜索
			if not secondButtonClicked then
				try
					set allElements to entire contents
					repeat with element in allElements
						try
							if class of element is button then
								set elementName to name of element
								if elementName contains "跳过" or elementName contains "Skip" or elementName contains "skip" then
									click element
									--log "第二步成功: 全局搜索找到并点击: " & elementName
									set secondButtonClicked to true
									set end of executionResults to {stepName:"step2_skip_button", success:true, message:"成功通过全局搜索点击'跳过'按钮: " & elementName, timestamp:(current date) as string}
									exit repeat
								end if
							end if
						end try
					end repeat
				end try
			end if
			
			if not secondButtonClicked then
				set end of executionResults to {stepName:"step2_skip_button", success:false, message:"未找到'跳过'按钮", timestamp:(current date) as string}
				set end of errorMessages to "第二步失败：未找到'跳过'按钮"
				set overallSuccess to false
			end if
			
			-- 第三步: 如果前两个按钮都成功，继续点击"取消"按钮
			if secondButtonClicked then
				--log "前两步完成，开始查找取消按钮..."
				delay 2
				
				set thirdButtonClicked to false
				
				-- 在sheet对话框中查找取消按钮
				try
					set allSheets to every sheet of window 1
					repeat with currentSheet in allSheets
						set sheetButtons to every button of currentSheet
						repeat with sheetButton in sheetButtons
							try
								set buttonName to name of sheetButton
								if buttonName contains "取消" or buttonName contains "Cancel" or buttonName contains "cancel" or buttonName contains "关闭" or buttonName contains "Close" then
									click sheetButton
									--	log "第三步成功: 在对话框中找到并点击了按钮: " & buttonName
									set thirdButtonClicked to true
									set end of executionResults to {stepName:"step3_cancel_button", success:true, message:"成功在对话框中点击'取消'按钮: " & buttonName, timestamp:(current date) as string}
									exit repeat
								end if
							end try
						end repeat
						if thirdButtonClicked then exit repeat
					end repeat
				end try
				
				-- 如果在sheet中没找到取消按钮，尝试其他位置
				if not thirdButtonClicked then
					try
						-- 尝试在主窗口中查找
						set allButtons to every button of window 1
						repeat with currentButton in allButtons
							try
								set buttonName to name of currentButton
								if buttonName contains "取消" or buttonName contains "Cancel" or buttonName contains "cancel" or buttonName contains "关闭" or buttonName contains "Close" then
									click currentButton
									--log "第三步成功: 在主窗口中找到并点击了按钮: " & buttonName
									set thirdButtonClicked to true
									set end of executionResults to {stepName:"step3_cancel_button", success:true, message:"成功在主窗口中点击'取消'按钮: " & buttonName, timestamp:(current date) as string}
									exit repeat
								end if
							end try
						end repeat
					end try
				end if
				
				-- 如果还没找到，进行全局搜索取消按钮
				if not thirdButtonClicked then
					try
						set allElements to entire contents
						repeat with element in allElements
							try
								if class of element is button then
									set elementName to name of element
									if elementName contains "取消" or elementName contains "Cancel" or elementName contains "cancel" or elementName contains "关闭" or elementName contains "Close" then
										click element
										--	log "第三步成功: 全局搜索找到并点击: " & elementName
										set thirdButtonClicked to true
										set end of executionResults to {stepName:"step3_cancel_button", success:true, message:"成功通过全局搜索点击'取消'按钮: " & elementName, timestamp:(current date) as string}
										exit repeat
									end if
								end if
							end try
						end repeat
					end try
				end if
				
				if not thirdButtonClicked then
					set end of executionResults to {stepName:"step3_cancel_button", success:false, message:"未找到'取消'按钮", timestamp:(current date) as string}
					set end of errorMessages to "第三步失败：未找到'取消'按钮"
					set overallSuccess to false
				end if
				
				-- 第四步：打开iMessage信息中的偏好设置
				if thirdButtonClicked then
					--log "三个按钮都已成功点击！开始打开iMessage偏好设置..."
					delay 1
					
					set preferencesOpened to false
					set accountsTabOpened to false
					
					try
						-- 确保Messages应用在前台
						tell application "System Events"
							tell process "Messages"
								-- 确保在前台
								set frontmost to true
								delay 0.3
								key code 49 using control down -- Control + Space
								delay 0.5
								-- 打开偏好设置（⌘,）
								keystroke "," using {command down}
								set preferencesOpened to true
								set end of executionResults to {stepName:"step4_open_preferences", success:true, message:"成功打开偏好设置", timestamp:(current date) as string}
							end tell
						end tell
						
						delay 1
						
						-- 切换到帐户标签
						tell application "System Events"
							tell process "Messages"
								try
									-- 优先点击中文"帐户"
									if exists (button "帐户" of toolbar 1 of window 1) then
										click button "帐户" of toolbar 1 of window 1
										set accountsTabOpened to true
										set end of executionResults to {stepName:"step5_accounts_tab", success:true, message:"成功切换到'帐户'标签", timestamp:(current date) as string}
									else if exists (button "账户" of toolbar 1 of window 1) then
										click button "账户" of toolbar 1 of window 1
										set accountsTabOpened to true
										set end of executionResults to {stepName:"step5_accounts_tab", success:true, message:"成功切换到'账户'标签", timestamp:(current date) as string}
									else if exists (button "Accounts" of toolbar 1 of window 1) then
										click button "Accounts" of toolbar 1 of window 1
										set accountsTabOpened to true
										set end of executionResults to {stepName:"step5_accounts_tab", success:true, message:"成功切换到'Accounts'标签", timestamp:(current date) as string}
									else
										-- 找不到就点第二个按钮（大多数版本帐户是第二个）
										click button 2 of toolbar 1 of window 1
										set accountsTabOpened to true
										set end of executionResults to {stepName:"step5_accounts_tab", success:true, message:"成功点击第二个工具栏按钮（账户标签）", timestamp:(current date) as string}
									end if
								on error errMsg
									set end of executionResults to {stepName:"step5_accounts_tab", success:false, message:"无法切换到帐户标签：" & errMsg, timestamp:(current date) as string}
									set end of errorMessages to "账户标签切换失败: " & errMsg
									set overallSuccess to false
								end try
							end tell
						end tell
						
					on error errMsg
						-- 如果菜单方式失败，尝试快捷键方式
						try
							log "菜单方式失败，尝试快捷键方式"
							tell application "Messages" to set frontmost to true
							delay 0.5
							tell application "System Events"
								keystroke "," using {command down}
							end tell
							delay 0.5
							set preferencesOpened to true
							set end of executionResults to {stepName:"step4_open_preferences", success:true, message:"通过快捷键成功打开偏好设置", timestamp:(current date) as string}
							log "已通过快捷键Cmd+,打开偏好设置"
							log "所有步骤完成！偏好设置已打开！"
						on error errMsg2
							set end of executionResults to {stepName:"step4_open_preferences", success:false, message:"打开偏好设置失败: " & errMsg2, timestamp:(current date) as string}
							set end of errorMessages to "偏好设置打开失败: " & errMsg2
							set overallSuccess to false
							log "打开偏好设置失败: " & errMsg2
						end try
					end try
					
				else
					set end of executionResults to {stepName:"step4_open_preferences", success:false, message:"前置步骤失败，无法打开偏好设置", timestamp:(current date) as string}
					set end of errorMessages to "前置步骤失败，无法打开偏好设置"
					set overallSuccess to false
					log "前两个按钮成功，但取消按钮未找到"
				end if
				
			else
				set end of executionResults to {stepName:"step3_cancel_button", success:false, message:"第二步失败，跳过第三步", timestamp:(current date) as string}
				set end of errorMessages to "第二步失败，跳过第三步"
				set overallSuccess to false
			end if
			
		else
			set end of executionResults to {stepName:"step2_skip_button", success:false, message:"第一步失败，跳过第二步", timestamp:(current date) as string}
			set end of errorMessages to "第一步失败，跳过第二步"
			set overallSuccess to false
			log "第一个按钮未找到"
		end if
		
	end tell
	
end tell

-- 构建JSON返回结果
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
	set jsonResult to jsonResult & "\"summary\":\"所有步骤执行成功，iMessage偏好设置已打开并切换到账户标签\""
else
	set jsonResult to jsonResult & "\"summary\":\"部分步骤执行失败，请查看详细错误信息\""
end if

set jsonResult to jsonResult & "}"

-- 返回JSON结果
return jsonResult