-- Messages数据库查询脚本
-- 用于查询macOS Messages应用的聊天记录数据库

on run
    try
        -- 数据库文件路径
        set dbPath to "/Users/wx/Library/Messages/chat.db"
        
        -- SQL查询语句
        set sqlQuery to "select m.ROWID as \"消息唯一ID\",m.account as \"发送账号\",h.id as \"联系人ID\",m.text as \"消息正文\", m.service as \"服务类型\",m.is_sent as \"是否发送\",m.is_delivered as \"是否送达\",m.is_read as \"是否已读\" from message m LEFT JOIN handle h ON m.handle_id = h.ROWID;"
        
        -- 构建sqlite3命令
        set sqliteCommand to "sqlite3 -header -csv \"" & dbPath & "\" \"" & sqlQuery & "\""
        
        -- 执行命令并获取结果
        set queryResult to do shell script sqliteCommand
        
        -- 返回查询结果
        return queryResult
        
    on error errMsg number errNum
        -- 错误处理
        if errNum = -128 then
            return "用户取消操作"
        else if errNum = 1 then
            return "错误: 数据库文件不存在或无法访问。请检查路径: /Users/wx/Library/Messages/chat.db"
        else
            return "执行错误: " & errMsg & " (错误代码: " & errNum & ")"
        end if
    end try
end run

-- 可选：为Python调用提供的函数接口
on queryMessagesDB()
    return run
end queryMessagesDB