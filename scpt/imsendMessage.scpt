-- iMessage自动发送脚本
-- 用法：需要准备包含手机号和消息内容的文本文件

-- 配置文件路径（请修改为你的实际路径）
set phoneFilePath to "/Users/wx/Documents/phone_numbers.txt"
set templateFilePath to "/Users/wx/Documents/message_template.txt"

-- 读取手机号文件
try
	set phoneContent to read POSIX file phoneFilePath as «class utf8»
	set phoneNumbers to paragraphs of phoneContent
	-- 过滤空行
	set validPhones to {}
	repeat with phoneNum in phoneNumbers
		if length of (phoneNum as string) > 0 then
			set end of validPhones to phoneNum
		end if
	end repeat
	
	if (count of validPhones) = 0 then
		display dialog "手机号文件为空或格式错误" buttons {"确定"} default button 1
		return
	end if
on error
	display dialog "无法读取手机号文件：" & phoneFilePath buttons {"确定"} default button 1
	return
end try

-- 读取消息模板文件
try
	set messageContent to read POSIX file templateFilePath as «class utf8»
	if length of messageContent = 0 then
		display dialog "消息模板文件为空" buttons {"确定"} default button 1
		return
	end if
on error
	display dialog "无法读取消息模板文件：" & templateFilePath buttons {"确定"} default button 1
	return
end try

-- 显示将要发送的信息概览
set phoneList to ""
repeat with phoneNum in validPhones
	set phoneList to phoneList & phoneNum & return
end repeat

set confirmResult to display dialog "准备发送消息到以下号码：" & return & phoneList & return & "消息内容：" & return & messageContent buttons {"取消", "发送"} default button 2
if button returned of confirmResult is "取消" then
	return
end if

-- 验证手机号格式（简单验证）
repeat with phoneNumber in validPhones
	if length of phoneNumber < 10 then
		display dialog "手机号格式可能不正确：" & phoneNumber buttons {"确定"} default button 1
		return
	end if
end repeat

-- 发送消息函数
on sendMessage(targetNumber, msgContent)
	try
		-- 打开Messages应用
		tell application "Messages"
			activate
			delay 2
			
			-- 使用正确的Messages语法发送消息
			set targetChat to make new chat with properties {recipients:{targetNumber}}
			send msgContent to targetChat
			
			-- 等待发送完成
			delay 3
			
			return true
		end tell
		
	on error errMsg
		try
			-- 备用方法：查找现有聊天记录
			tell application "Messages"
				-- 查找与该号码的现有对话
				set existingChats to chats whose name contains targetNumber
				if (count of existingChats) > 0 then
					send msgContent to item 1 of existingChats
				else
					-- 如果没有现有对话，创建新的
					set newChat to make new chat with properties {recipients:{targetNumber}}
					send msgContent to newChat
				end if
				delay 3
				return true
			end tell
		on error errMsg2
			-- 最简单的方法
			try
				tell application "Messages"
					send msgContent to buddy targetNumber of (first service)
					delay 3
					return true
				end tell
			on error errMsg3
				log "发送到 " & targetNumber & " 失败: " & errMsg3
				return false
			end try
		end try
	end try
end sendMessage
-- 检查发送状态并处理未送达消息
on checkDeliveryStatus()
	try
		delay 5 -- 等待消息发送状态更新
		
		tell application "System Events"
			tell process "Messages"
				set hasUndelivered to false
				
				try
					-- 根据提供的窗体结构查找未送达信息
					-- 查找路径：UI element 1 of scroll area 2 of splitter group 1 of window "信息"
					set messageWindow to window "信息"
					if exists messageWindow then
						set splitterGroup to splitter group 1 of messageWindow
						if exists splitterGroup then
							set scrollArea to scroll area 2 of splitterGroup
							if exists scrollArea then
								set uiElement1 to UI element 1 of scrollArea
								if exists uiElement1 then
									-- 查找"未送达"UI元素
									try
										set undeliveredElement to UI element "未送达" of uiElement1
										if exists undeliveredElement then
											-- 进一步检查"未送达"文本
											set group1 to group 1 of undeliveredElement
											if exists group1 then
												set innerGroup to group 1 of group1
												if exists innerGroup then
													set undeliveredText to static text "未送达" of innerGroup
													if exists undeliveredText then
														set hasUndelivered to true
														log "发现未送达消息：" & (value of undeliveredText)
													end if
												end if
											end if
										end if
									end try
									
									-- 查找感叹号图标（image 2）
									try
										set exclamationImage to image 2 of uiElement1
										if exists exclamationImage then
											set hasUndelivered to true
											log "发现感叹号图标"
										end if
									end try
								end if
							end if
						end if
					end if
				end try
				
				-- 备用方法：通用检查
				if not hasUndelivered then
					try
						if exists (static texts whose value contains "未送达" or value contains "Not Delivered" or value contains "未发送") then
							set hasUndelivered to true
							log "通过备用方法发现未送达消息"
						end if
					end try
				end if
				
				-- 如果检测到未送达，尝试重新发送
				if hasUndelivered then
					log "消息未送达，尝试重新发送..."
					
					-- 根据窗体结构查找并点击重新发送相关元素
					try
						set messageWindow to window "信息"
						if exists messageWindow then
							set splitterGroup to splitter group 1 of messageWindow
							if exists splitterGroup then
								set scrollArea to scroll area 2 of splitterGroup
								if exists scrollArea then
									set uiElement1 to UI element 1 of scrollArea
									if exists uiElement1 then
										-- 尝试点击button 1（可能是重新发送按钮）
										try
											set retryButton to button 1 of uiElement1
											if exists retryButton then
												click retryButton
												delay 2
												log "已点击重新发送按钮"
												
												-- 处理弹出的确认对话框
												try
													set confirmSheet to sheet 1 of window "信息"
													if exists confirmSheet then
														-- 检查是否有"您的信息无法发送"提示
														if exists (static text "您的信息无法发送。" of confirmSheet) then
															log "发现信息无法发送提示"
															-- 点击"再试一次"按钮
															if exists (button "再试一次" of confirmSheet) then
																click (button "再试一次" of confirmSheet)
																delay 3
																log "已点击再试一次按钮"
																return "retrying"
															end if
														end if
													end if
												end try
												
												return "retrying"
											end if
										end try
									end if
								end if
							end if
						end if
					end try
					
					return "failed"
				else
					-- 没有检测到未送达标识，认为发送成功
					log "消息发送成功"
					return "success"
				end if
			end tell
		end tell
		
	on error errMsg
		log "检查送达状态时出错: " & errMsg
		-- 发生错误时，再等待一段时间检查
		delay 3
		try
			tell application "System Events"
				tell process "Messages"
					if exists (static texts whose value contains "未送达") then
						return "failed"
					else
						return "success"
					end if
				end tell
			end tell
		on error
			return "unknown"
		end try
	end try
end checkDeliveryStatus

-- 主发送逻辑，批量发送到多个号码
set totalPhones to count of validPhones
set successCount to 0
set failureList to {}

repeat with i from 1 to totalPhones
	set currentPhone to item i of validPhones
	display dialog "正在发送到 " & currentPhone & " (" & i & "/" & totalPhones & ")" buttons {"确定"} default button 1 giving up after 2
	
	-- 为每个号码尝试最多3次发送
	set maxAttempts to 3
	set currentAttempt to 1
	set sendSuccess to false
	
	repeat while currentAttempt ≤ maxAttempts and sendSuccess is false
		-- 尝试发送消息
		set sendResult to sendMessage(currentPhone, messageContent)
		
		if sendResult then
			-- 检查送达状态并处理重发
			set deliveryResult to checkDeliveryStatus()
			
			if deliveryResult is "success" then
				set sendSuccess to true
				set successCount to successCount + 1
			else if deliveryResult is "retrying" then
				-- 如果正在重试，等待重发完成后再次检查
				delay 5
				set retryCheck to checkDeliveryStatus()
				if retryCheck is "success" then
					set sendSuccess to true
					set successCount to successCount + 1
				end if
			else if deliveryResult is "failed" then
				-- 明确失败，记录日志
				log "消息到 " & currentPhone & " 发送失败，第 " & currentAttempt & " 次尝试"
			end if
		end if
		
		if sendSuccess is false and currentAttempt < maxAttempts then
			delay 3 -- 重试前等待3秒
		end if
		
		set currentAttempt to currentAttempt + 1
	end repeat
	
	-- 记录失败的号码
	if sendSuccess is false then
		set end of failureList to currentPhone
	end if
	
	-- 发送间隔，避免发送过快
	if i < totalPhones then
		delay 1
	end if
end repeat

-- 最终结果统计
set resultMessage to "发送完成！" & return & "成功：" & successCount & " 个" & return & "总数：" & totalPhones & " 个"

if (count of failureList) > 0 then
	set resultMessage to resultMessage & return & return & "发送失败的号码："
	repeat with failedPhone in failureList
		set resultMessage to resultMessage & return & failedPhone
	end repeat
end if

display dialog resultMessage buttons {"确定"} default button 1