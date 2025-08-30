-- iMessage自动发送脚本 - JSON结果版（支持图片附件和文本）
-- 用法：需要准备包含手机号、消息内容和图片的文件

-- 配置文件路径（请修改为你的实际路径）
set phoneFilePath to "/Users/wx/Documents/send_default/phone_numbers.txt"
set templateFilePath to "/Users/wx/Documents/send_default/message_template.txt"

-- 图片配置 - 使用固定路径
set fixedImagePath to "/Users/wx/Documents/send_default/images/attachment.png" -- 修改为你的实际图片路径
set includeImage to true -- 设置为false如果不需要发送图片

-- JSON结果存储
set jsonResult to {}

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
		set errorResult to createErrorJSON("手机号文件为空或格式错误")
		return errorResult
	end if
on error errMsg
	set errorResult to createErrorJSON("无法读取手机号文件: " & errMsg)
	return errorResult
end try

-- 读取消息模板文件
try
	set messageContent to read POSIX file templateFilePath as «class utf8»
	
	-- 去除文件末尾可能存在的多余换行符
	set messageContent to removeTrailingNewlines(messageContent)
	
	if length of messageContent = 0 then
		set errorResult to createErrorJSON("消息模板文件为空")
		return errorResult
	end if
	
on error errMsg
	set errorResult to createErrorJSON("无法读取消息模板文件: " & errMsg)
	return errorResult
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
set imageStatus to "none"
if includeImage then
	try
		set imageAttachment to POSIX file fixedImagePath
		-- 检查文件是否存在
		tell application "Finder"
			if not (exists imageAttachment) then
				set errorResult to createErrorJSON("图片文件不存在: " & fixedImagePath)
				return errorResult
			end if
		end tell
		set imageStatus to "ready"
	on error errMsg
		set errorResult to createErrorJSON("图片文件验证失败: " & errMsg)
		return errorResult
	end try
end if

-- 验证手机号格式（简单验证）
repeat with phoneNumber in validPhones
	if length of phoneNumber < 10 then
		set errorResult to createErrorJSON("手机号格式可能不正确: " & phoneNumber)
		return errorResult
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
			
			set imageSuccess to false
			set textSuccess to false
			set errorMessages to {}
			
			-- 发送图片附件
			if hasImage and imgAttachment is not null then
				try
					send imgAttachment to targetBuddy
					delay 2
					set imageSuccess to true
				on error imgErr
					set end of errorMessages to ("图片发送失败: " & imgErr)
				end try
			end if
			
			-- 发送文本消息
			if length of msgContent > 0 then
				try
					send msgContent to targetBuddy
					delay 1
					set textSuccess to true
				on error textErr
					set end of errorMessages to ("文本发送失败: " & textErr)
				end try
			end if
			
			-- 返回发送结果
			return {success:(textSuccess or imageSuccess), imageSuccess:imageSuccess, textSuccess:textSuccess, errors:errorMessages}
		end tell
		
	on error errMsg
		return {success:false, imageSuccess:false, textSuccess:false, errors:{errMsg}}
	end try
end sendMessage

-- 主发送逻辑
set totalPhones to count of validPhones
set successCount to 0
set failureCount to 0
set successNumbers to {}
set failureNumbers to {}
set detailedResults to {}

-- 获取当前时间戳
set currentDate to (current date)
set timestamp to (currentDate as string)

repeat with i from 1 to totalPhones
	set currentPhone to item i of validPhones
	
	-- 发送消息
	set sendResult to sendMessage(currentPhone, messageContent, imageAttachment, includeImage)
	
	-- 解析发送结果
	set phoneSuccess to success of sendResult
	set phoneImageSuccess to imageSuccess of sendResult
	set phoneTextSuccess to textSuccess of sendResult
	set phoneErrors to errors of sendResult
	
	if phoneSuccess then
		set successCount to successCount + 1
		set end of successNumbers to currentPhone
	else
		set failureCount to failureCount + 1
		set end of failureNumbers to currentPhone
	end if
	
	-- 创建详细结果记录
	set phoneResult to "{" & return & ¬
		"    \"phone\": \"" & currentPhone & "\"," & return & ¬
		"    \"success\": " & (phoneSuccess as string) & "," & return & ¬
		"    \"text_sent\": " & (phoneTextSuccess as string) & "," & return & ¬
		"    \"image_sent\": " & (phoneImageSuccess as string)
	
	if (count of phoneErrors) > 0 then
		set errorStr to ""
		repeat with errorMsg in phoneErrors
			if errorStr ≠ "" then set errorStr to errorStr & ", "
			set errorStr to errorStr & "\"" & escapeJsonString(errorMsg as string) & "\""
		end repeat
		set phoneResult to phoneResult & "," & return & "    \"errors\": [" & errorStr & "]"
	end if
	
	set phoneResult to phoneResult & return & "  }"
	set end of detailedResults to phoneResult
	
	-- 发送间隔，避免过于频繁
	if i < totalPhones then
		delay 3
	end if
end repeat

-- 构建成功和失败号码的JSON数组
set successArray to ""
repeat with successPhone in successNumbers
	if successArray ≠ "" then set successArray to successArray & ", "
	set successArray to successArray & "\"" & successPhone & "\""
end repeat

set failureArray to ""
repeat with failurePhone in failureNumbers
	if failureArray ≠ "" then set failureArray to failureArray & ", "
	set failureArray to failureArray & "\"" & failurePhone & "\""
end repeat

-- 构建详细结果的JSON数组
set detailedArray to ""
repeat with detailResult in detailedResults
	if detailedArray ≠ "" then set detailedArray to detailedArray & "," & return
	set detailedArray to detailedArray & "  " & detailResult
end repeat

-- 构建完整的JSON结果
set finalJSON to "{" & return & ¬
	"  \"status\": \"completed\"," & return & ¬
	"  \"timestamp\": \"" & timestamp & "\"," & return & ¬
	"  \"message_content\": \"" & escapeJsonString(messageContent) & "\"," & return & ¬
	"  \"image_included\": " & (includeImage as string) & "," & return & ¬
	"  \"image_path\": \"" & fixedImagePath & "\"," & return & ¬
	"  \"summary\": {" & return & ¬
	"    \"total_numbers\": " & totalPhones & "," & return & ¬
	"    \"successful_sends\": " & successCount & "," & return & ¬
	"    \"failed_sends\": " & failureCount & "," & return & ¬
	"    \"success_rate\": " & (round ((successCount / totalPhones) * 100)) & "%" & return & ¬
	"  }," & return & ¬
	"  \"successful_numbers\": [" & successArray & "]," & return & ¬
	"  \"failed_numbers\": [" & failureArray & "]," & return & ¬
	"  \"detailed_results\": [" & return & detailedArray & return & "  ]" & return & ¬
	"}"

-- 保存JSON结果到文件
set jsonFilePath to "/Users/wx/Documents/send_default/send_results.json"
try
	set jsonFile to open for access POSIX file jsonFilePath with write permission
	set eof of jsonFile to 0
	write finalJSON to jsonFile as «class utf8»
	close access jsonFile
	display notification "JSON结果已保存到文件" with title "发送完成"
on error
	try
		close access POSIX file jsonFilePath
	end try
	display notification "保存JSON结果失败" with title "警告"
end try

-- 显示JSON结果
display dialog "=== 发送结果 (JSON格式) ===" & return & return & finalJSON buttons {"确定"} default button 1 with title "批量发送完成"

-- 同时在控制台输出（用于调试）
log "=== JSON结果 ===" & return & finalJSON

-- 返回JSON字符串作为脚本结果
return finalJSON

-- 创建错误JSON的函数
on createErrorJSON(errorMessage)
	set currentDate to (current date)
	set timestamp to (currentDate as string)
	
	set errorJSON to "{" & return & ¬
		"  \"status\": \"error\"," & return & ¬
		"  \"timestamp\": \"" & timestamp & "\"," & return & ¬
		"  \"error_message\": \"" & escapeJsonString(errorMessage) & "\"," & return & ¬
		"  \"summary\": {" & return & ¬
		"    \"total_numbers\": 0," & return & ¬
		"    \"successful_sends\": 0," & return & ¬
		"    \"failed_sends\": 0," & return & ¬
		"    \"success_rate\": \"0%\"" & return & ¬
		"  }" & return & ¬
		"}"
	
	-- 显示错误信息
	display dialog "错误: " & errorMessage & return & return & "JSON结果:" & return & errorJSON buttons {"确定"} default button 1 with title "脚本执行失败"
	
	-- 保存错误JSON到文件
	set jsonFilePath to "/Users/wx/Documents/send_default/send_results.json"
	try
		set jsonFile to open for access POSIX file jsonFilePath with write permission
		set eof of jsonFile to 0
		write errorJSON to jsonFile as «class utf8»
		close access jsonFile
	on error
		try
			close access POSIX file jsonFilePath
		end try
	end try
	
	return errorJSON
end createErrorJSON

-- JSON字符串转义函数
on escapeJsonString(inputString)
	set escapedString to inputString
	
	-- 转义反斜杠
	set escapedString to replaceText(escapedString, "\\", "\\\\")
	
	-- 转义双引号
	set escapedString to replaceText(escapedString, "\"", "\\\"")
	
	-- 转义换行符
	set escapedString to replaceText(escapedString, return, "\\n")
	set escapedString to replaceText(escapedString, linefeed, "\\n")
	
	-- 转义制表符
	set escapedString to replaceText(escapedString, tab, "\\t")
	
	return escapedString
end escapeJsonString

-- 文本替换函数
on replaceText(inputString, searchString, replaceString)
	set AppleScript's text item delimiters to searchString
	set textItems to text items of inputString
	set AppleScript's text item delimiters to replaceString
	set outputString to textItems as string
	set AppleScript's text item delimiters to ""
	return outputString
end replaceText