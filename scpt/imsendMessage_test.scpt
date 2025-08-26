-- iMessage自动发送脚本 - 修正版（支持图片附件和文本）
-- 用法：需要准备包含手机号、消息内容和图片的文件

-- 配置文件路径（请修改为你的实际路径）
set phoneFilePath to "/Users/wx/Documents/phone_numbers.txt"
set templateFilePath to "/Users/wx/Documents/message_template.txt"

-- 图片配置 - 使用固定路径
set fixedImagePath to "/Users/wx/Documents/images/attachment.png" -- 修改为你的实际图片路径
set includeImage to true -- 设置为false如果不需要发送图片

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
		log "手机号文件为空或格式错误" buttons {"确定"} default button 1
		return
	end if
on error
	log "无法读取手机号文件：" & phoneFilePath buttons {"确定"} default button 1
	return
end try

-- 读取消息模板文件
try
	set messageContent to read POSIX file templateFilePath as «class utf8»
	
	-- 去除文件末尾可能存在的多余换行符
	set messageContent to removeTrailingNewlines(messageContent)
	
	if length of messageContent = 0 then
		log "消息模板文件为空" buttons {"确定"} default button 1
		return
	end if
	
	-- 记录读取成功的日志
	log "成功读取模板文件，内容长度: " & (length of messageContent) & " 字符"
	log "包含段落数: " & (count of paragraphs of messageContent)
on error
	log "无法读取消息模板文件：" & templateFilePath buttons {"确定"} default button 1
	return
end try

-- 处理换行符的函数
on removeTrailingNewlines(messageContent)
	set cleanContent to messageContent
	
	-- 去除末尾的多余换行符（但保留内容中间的换行符）
	repeat while cleanContent ends with return
		if length of cleanContent > 1 then
			set cleanContent to text 1 thru -2 of cleanContent
		else
			exit repeat
		end if
	end repeat
	
	return cleanContent
end removeTrailingNewlines

-- 验证图片文件
set imageAttachment to null
if includeImage then
	try
		set imageAttachment to POSIX file fixedImagePath
		-- 检查文件是否存在
		tell application "Finder"
			if not (exists imageAttachment) then
				log "图片文件不存在：" & fixedImagePath buttons {"确定"} default button 1
				return
			end if
		end tell
		log "✓ 图片文件验证成功"
	on error errMsg
		log "✗ 图片文件验证失败：" & errMsg buttons {"确定"} default button 1
		return
	end try
end if

-- 显示将要发送的信息概览
set phoneList to ""
repeat with phoneNum in validPhones
	set phoneList to phoneList & phoneNum & return
end repeat

set imageInfo to ""
if includeImage and imageAttachment is not null then
	set imageInfo to return & "包含图片附件：是"
else
	set imageInfo to return & "包含图片附件：否"
end if

 log "准备发送消息到以下号码：" phoneList &  "消息内容："  & messageContent & imageInfo 
 

-- 验证手机号格式（简单验证）
repeat with phoneNumber in validPhones
	if length of phoneNumber < 10 then
		log "手机号格式可能不正确：" & phoneNumber buttons {"确定"} default button 1
		return
	end if
end repeat

-- 发送消息函数 - 修正版
on sendMessage(targetNumber, msgContent, imgAttachment, hasImage)
	try
		tell application "Messages"
			activate
			delay 2
			
			-- 获取或创建对话
			set targetService to 1st service whose service type = iMessage
			set targetBuddy to buddy targetNumber of targetService
				-- 发送图片附件
			if hasImage and imgAttachment is not null then
				try
					send imgAttachment to targetBuddy
					delay 2
					log "图片附件发送成功到: " & targetNumber
				on error imgErr
					log "图片发送失败到 " & targetNumber & ": " & imgErr
					-- 即使图片发送失败，文本消息可能已经成功
				end try
			end if
			-- 发送文本消息
			if length of msgContent > 0 then
				send msgContent to targetBuddy
				delay 1
				log "文本消息发送成功到: " & targetNumber
			end if
			
			return true
		end tell
		
	on error errMsg
		log "发送到 " & targetNumber & " 失败: " & errMsg
		return false
	end try
end sendMessage

-- 主发送逻辑
set totalPhones to count of validPhones
set successCount to 0
set failureList to {}

repeat with i from 1 to totalPhones
	set currentPhone to item i of validPhones
	log "正在发送到 " & currentPhone & " (" & i & "/" & totalPhones & ")" buttons {"确定"} default button 1 giving up after 2
	
	-- 发送消息
	set sendResult to sendMessage(currentPhone, messageContent, imageAttachment, includeImage)
	
	if sendResult then
		set successCount to successCount + 1
		log "成功发送到: " & currentPhone
	else
		set end of failureList to currentPhone
		log "发送失败: " & currentPhone
	end if
	
	-- 发送间隔，避免过于频繁
	if i < totalPhones then
		delay 3
	end if
end repeat

-- 显示发送结果
set resultMessage to "发送完成！" & return & "成功: " & successCount & " 个" & return & "失败: " & (totalPhones - successCount) & " 个"

if (count of failureList) > 0 then
	set failureNumbers to ""
	repeat with failedPhone in failureList
		set failureNumbers to failureNumbers & failedPhone & return
	end repeat
	set resultMessage to resultMessage & return & return & "失败的号码：" & return & failureNumbers
end if

logresultMessage buttons {"确定"} default button 1

log "批量发送任务完成。成功: " & successCount & ", 失败: " & (totalPhones - successCount)