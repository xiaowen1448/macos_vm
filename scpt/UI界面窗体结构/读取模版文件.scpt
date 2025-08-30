-- 读取消息模板文件 - 增强版（完全模拟复制粘贴效果）
try
	-- 方法1：标准读取（保留所有换行符和格式）
	set messageContent to read POSIX file templateFilePath as «class utf8»
	
	-- 去除文件末尾可能存在的多余换行符（模拟手动选择时的行为）
	set messageContent to removeTrailingNewlines(messageContent)
	
	if length of messageContent = 0 then
		display dialog "消息模板文件为空" buttons {"确定"} default button 1
		return
	end if
	
	-- 记录读取成功的日志
	log "成功读取模板文件，内容长度: " & (length of messageContent) & " 字符"
	log "包含段落数: " & (count of paragraphs of messageContent)
	
on error errMsg
	-- 如果标准方法失败，尝试备用方法
	try
		-- 备用方法：通过shell命令读取
		set messageContent to do shell script "cat " & quoted form of (POSIX path of (POSIX file templateFilePath))
		
		-- 处理可能的编码问题
		set messageContent to removeTrailingNewlines(messageContent)
		
		if length of messageContent = 0 then
			display dialog "消息模板文件为空" buttons {"确定"} default button 1
			return
		end if
		
		log "通过备用方法成功读取模板文件"
		
	on error shellErr
		display dialog "无法读取消息模板文件：" & templateFilePath & return & return & "错误信息：" & errMsg & return & "备用方法错误：" & shellErr buttons {"确定"} default button 1
		return
	end try
end try

-- 处理换行符的函数（确保与复制粘贴行为一致）
on removeTrailingNewlines(textContent)
	set cleanContent to textContent
	
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

-- 验证内容格式的函数
on validateMessageContent(content)
	-- 检查是否包含常见的URL模式
	set hasURL to false
	if content contains "http://" or content contains "https://" or content contains "www." then
		set hasURL to true
	end if
	
	-- 分析内容结构
	set lineCount to count of paragraphs of content
	set charCount to length of content
	
	-- 返回验证信息
	return {hasURL:hasURL, lines:lineCount, chars:charCount}
end validateMessageContent

-- 使用示例和测试
set templateFilePath to "/Users/wx/Documents/message_template.txt"

-- 执行读取
-- 这里插入上面的读取代码

-- 验证读取的内容
set contentInfo to validateMessageContent(messageContent)
log "内容验证 - URL: " & (hasURL of contentInfo) & ", 行数: " & (lines of contentInfo) & ", 字符数: " & (chars of contentInfo)