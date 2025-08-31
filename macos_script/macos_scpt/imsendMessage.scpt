-- iMessage自动发送脚本 - JSON结果版（修复双引号问题）
-- 用法：需要准备包含手机号、消息内容和图片的文件

-- 配置文件路径（请修改为你的实际路径）
set phoneFilePath to "/Users/wx/Documents/send_default/phone_numbers.txt"
set templateFilePath to "/Users/wx/Documents/send_default/message_template.txt"

-- 图片配置 - 使用固定路径
set fixedImagePath to "/Users/wx/Documents/send_default/images/attachment.png"
set includeImage to true

-- 定义双引号字符（避免转义问题）
set q to ASCII character 34 -- 双引号字符

-- 调试：输出文件路径
log "=== 调试信息 ==="
log "手机号文件路径: " & phoneFilePath
log "消息模板文件路径: " & templateFilePath

-- 读取手机号文件
try
	set phoneFile to POSIX file phoneFilePath
	log "正在读取手机号文件: " & phoneFilePath
	
	set phoneContent to read phoneFile as «class utf8»
	set phoneNumbers to paragraphs of phoneContent
	
	log "读取到 " & (count of phoneNumbers) & " 行数据"
	
	-- 过滤空行
	set validPhones to {}
	repeat with phoneNum in phoneNumbers
		set phoneStr to phoneNum as string
		if length of phoneStr > 0 then
			set end of validPhones to phoneStr
			log "有效号码: " & phoneStr
		end if
	end repeat
	
	log "过滤后有效号码数量: " & (count of validPhones)
	
	if (count of validPhones) = 0 then
		set errorResult to createErrorJSON("手机号文件为空或格式错误")
		return errorResult
	end if
on error errMsg
	log "读取手机号文件出错: " & errMsg
	set errorResult to createErrorJSON("无法读取手机号文件: " & errMsg)
	return errorResult
end try

-- 读取消息模板文件
try
	set templateFile to POSIX file templateFilePath
	log "正在读取消息模板文件: " & templateFilePath
	
	set messageContent to read templateFile as «class utf8»
	set messageContent to removeTrailingNewlines(messageContent)
	
	log "消息内容长度: " & (length of messageContent) & " 字符"
	if length of messageContent > 50 then
		log "消息内容预览: " & (text 1 thru 50 of messageContent) & "..."
	else
		log "消息内容预览: " & messageContent
	end if
	
	if length of messageContent = 0 then
		set errorResult to createErrorJSON("消息模板文件为空")
		return errorResult
	end if
	
on error errMsg
	log "读取消息模板文件出错: " & errMsg
	set errorResult to createErrorJSON("无法读取消息模板文件: " & errMsg)
	return errorResult
end try

-- 验证图片文件
set imageAttachment to null
if includeImage then
	try
		set imageAttachment to POSIX file fixedImagePath
		tell application "Finder"
			if not (exists imageAttachment) then
				set errorResult to createErrorJSON("图片文件不存在: " & fixedImagePath)
				return errorResult
			end if
		end tell
	on error errMsg
		set errorResult to createErrorJSON("图片文件验证失败: " & errMsg)
		return errorResult
	end try
end if

-- 验证手机号格式
repeat with phoneNumber in validPhones
	if length of phoneNumber < 10 then
		set errorResult to createErrorJSON("手机号格式可能不正确: " & phoneNumber)
		return errorResult
	end if
end repeat

-- 主发送逻辑
set totalPhones to count of validPhones
set successCount to 0
set failureCount to 0
set successNumbers to {}
set failureNumbers to {}
set detailedResults to {}

-- 获取当前时间戳
set currentDate to (current date)
set timestamp to formatDateToISO(currentDate)

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
	set phoneResult to buildPhoneResultJSON(currentPhone, phoneSuccess, phoneTextSuccess, phoneImageSuccess, phoneErrors)
	set end of detailedResults to phoneResult
	
	-- 发送间隔
	if i < totalPhones then
		delay 3
	end if
end repeat

-- 构建最终JSON
set finalJSON to buildFinalJSON(timestamp, messageContent, includeImage, fixedImagePath, totalPhones, successCount, failureCount, successNumbers, failureNumbers, detailedResults)

-- === 输出JSON结果 ===
log "=== iMessage发送结果 JSON 开始 ==="
log finalJSON
log "=== iMessage发送结果 JSON 结束 ==="

-- 打印到标准输出
do shell script "echo " & quoted form of finalJSON

-- 完成通知
display notification "发送完成! 成功: " & successCount & "/" & totalPhones & " (成功率: " & (round ((successCount / totalPhones) * 100)) & "%)" with title "iMessage批量发送"

-- 返回JSON
log "=== 准备返回最终JSON结果 ==="
log "JSON字符长度: " & (length of finalJSON)

return finalJSON

-- 发送消息函数
on sendMessage(targetNumber, msgContent, imgAttachment, hasImage)
	try
		tell application "Messages"
			activate
			delay 2
			
			set targetService to 1st service whose service type = iMessage
			set targetBuddy to buddy targetNumber of targetService
			
			set imageSuccess to false
			set textSuccess to false
			set errorMessages to {}
			
			if hasImage and imgAttachment is not null then
				try
					send imgAttachment to targetBuddy
					delay 2
					set imageSuccess to true
				on error imgErr
					set end of errorMessages to ("图片发送失败: " & imgErr)
				end try
			end if
			
			if length of msgContent > 0 then
				try
					send msgContent to targetBuddy
					delay 1
					set textSuccess to true
				on error textErr
					set end of errorMessages to ("文本发送失败: " & textErr)
				end try
			end if
			
			return {success:(textSuccess or imageSuccess), imageSuccess:imageSuccess, textSuccess:textSuccess, errors:errorMessages}
		end tell
		
	on error errMsg
		return {success:false, imageSuccess:false, textSuccess:false, errors:{errMsg}}
	end try
end sendMessage

-- 构建单个手机号结果的JSON
on buildPhoneResultJSON(phoneNum, isSuccess, textSent, imageSent, errorList)
	set q to ASCII character 34 -- 双引号
	
	set phoneResult to "{" & return & ¬
		"    " & q & "phone" & q & ": " & q & phoneNum & q & "," & return & ¬
		"    " & q & "success" & q & ": " & (isSuccess as string) & "," & return & ¬
		"    " & q & "text_sent" & q & ": " & (textSent as string) & "," & return & ¬
		"    " & q & "image_sent" & q & ": " & (imageSent as string)
	
	if (count of errorList) > 0 then
		set errorArray to ""
		repeat with errorMsg in errorList
			if errorArray is not "" then set errorArray to errorArray & ", "
			set errorArray to errorArray & q & escapeJsonString(errorMsg as string) & q
		end repeat
		set phoneResult to phoneResult & "," & return & "    " & q & "errors" & q & ": [" & errorArray & "]"
	end if
	
	set phoneResult to phoneResult & return & "  }"
	return phoneResult
end buildPhoneResultJSON


-- 创建错误JSON的函数
on createErrorJSON(errorMessage)
	set currentDate to (current date)
	set timestamp to formatDateToISO(currentDate)
	set q to ASCII character 34 -- 双引号
	
	set errorJSON to "{" & return & ¬
		"  " & q & "status" & q & ": " & q & "error" & q & "," & return & ¬
		"  " & q & "timestamp" & q & ": " & q & timestamp & q & "," & return & ¬
		"  " & q & "error_message" & q & ": " & q & escapeJsonString(errorMessage) & q & "," & return & ¬
		"  " & q & "summary" & q & ": {" & return & ¬
		"    " & q & "total_numbers" & q & ": 0," & return & ¬
		"    " & q & "successful_sends" & q & ": 0," & return & ¬
		"    " & q & "failed_sends" & q & ": 0," & return & ¬
		"    " & q & "success_rate" & q & ": " & q & "0%" & q & return & ¬
		"  }" & return & ¬
		"}"
	
	-- 输出错误JSON
	log "=== 错误JSON结果 ==="
	log errorJSON
	
	do shell script "echo " & quoted form of errorJSON
	
	display notification "脚本执行失败: " & errorMessage with title "错误"
	
	return errorJSON
end createErrorJSON

-- 日期格式化函数：返回 YYYY-MM-DD HH:MM:SS
on formatDateToISO(theDate)
	if class of theDate is not date then error "参数必须是 date 类型。"

	set y to (year of theDate) as integer
	set m to (month of theDate) as integer
	set d to (day of theDate) as integer

	set totalSeconds to (time of theDate) as integer
	set h to totalSeconds div 3600
	set mi to (totalSeconds mod 3600) div 60
	set s to totalSeconds mod 60

	set yStr to y as text
	set mStr to padZero(m)
	set dStr to padZero(d)
	set hStr to padZero(h)
	set miStr to padZero(mi)
	set sStr to padZero(s)

	return yStr & "-" & mStr & "-" & dStr & " " & hStr & ":" & miStr & ":" & sStr
end formatDateToISO

-- 补零函数，只有这一份
on padZero(n)
	if n < 10 then
		return "0" & (n as text)
	else
		return n as text
	end if
end padZero


-- 处理换行符的函数
on removeTrailingNewlines(messageContent)
	set cleanContent to messageContent
	
	repeat while cleanContent ends with return
		if length of cleanContent > 1 then
			set cleanContent to text 1 thru -2 of cleanContent
		else
			exit repeat
		end if
	end repeat
	
	return cleanContent
end removeTrailingNewlines



-- 构建最终JSON
on buildFinalJSON(ts, msgContent, hasImage, imagePath, total, successNum, failNum, successList, failList, detailList)
	set q to ASCII character 34
	set successRate to round ((successNum / total) * 100)
	
	-- 构建成功号码数组
	set successArray to ""
	repeat with successPhone in successList
		if successArray is not "" then set successArray to successArray & ", "
		set successArray to successArray & q & successPhone & q
	end repeat
	
	-- 构建失败号码数组
	set failureArray to ""
	repeat with failurePhone in failList
		if failureArray is not "" then set failureArray to failureArray & ", "
		set failureArray to failureArray & q & failurePhone & q
	end repeat
	
	-- 构建详细结果数组
	set detailedArray to ""
	repeat with detailResult in detailList
		if detailedArray is not "" then set detailedArray to detailedArray & "," & return
		set detailedArray to detailedArray & "  " & detailResult
	end repeat
	
	-- 构建完整JSON
	set jsonStr to "{" & return & ¬
		"  " & q & "status" & q & ": " & q & "completed" & q & "," & return & ¬
		"  " & q & "timestamp" & q & ": " & q & ts & q & "," & return & ¬
		"  " & q & "message_content" & q & ": " & q & escapeJsonString(msgContent) & q & "," & return & ¬
		"  " & q & "image_included" & q & ": " & (hasImage as string) & "," & return & ¬
		"  " & q & "image_path" & q & ": " & q & imagePath & q & "," & return & ¬
		"  " & q & "summary" & q & ": {" & return & ¬
		"    " & q & "total_numbers" & q & ": " & total & "," & return & ¬
		"    " & q & "successful_sends" & q & ": " & successNum & "," & return & ¬
		"    " & q & "failed_sends" & q & ": " & failNum & "," & return & ¬
		"    " & q & "success_rate" & q & ": " & q & successRate & "%" & q & return & ¬
		"  }," & return & ¬
		"  " & q & "successful_numbers" & q & ": [" & successArray & "]," & return & ¬
		"  " & q & "failed_numbers" & q & ": [" & failureArray & "]," & return & ¬
		"  " & q & "detailed_results" & q & ": [" & return & detailedArray & return & "  ]" & return & ¬
		"}"
	
	return jsonStr
end buildFinalJSON

-- JSON字符串转义函数
on escapeJsonString(inputString)
	set escapedString to inputString
	
	-- 转义反斜杠
	set escapedString to replaceText(escapedString, "\\", "\\\\")
	
	-- 转义双引号 - 使用ASCII字符避免语法问题
	set doubleQuote to ASCII character 34
	set escapedString to replaceText(escapedString, doubleQuote, "\\" & doubleQuote)
	
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