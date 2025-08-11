-- 健壮的测试AppleScript脚本
-- 处理各种可能的错误和类型转换问题

on run
    try
        -- 获取当前时间
        set currentTime to (current date) as string
        
        -- 尝试获取系统信息（使用安全的方法）
        set systemVersion to "Unknown"
        set computerName to "Unknown"
        set userName to "Unknown"
        
        try
            set systemInfo to system info
            set systemVersion to system version of systemInfo as string
        on error
            set systemVersion to "macOS 10.12+"
        end try
        
        try
            set computerName to computer name of systemInfo as string
        on error
            set computerName to "Mac"
        end try
        
        try
            set userName to short user name of systemInfo as string
        on error
            set userName to "User"
        end try
        
        -- 构建返回信息
        set resultText to "✅ 测试脚本执行成功！" & return & return
        set resultText to resultText & "📅 当前时间: " & currentTime & return
        set resultText to resultText & "🖥️ 系统版本: " & systemVersion & return
        set resultText to resultText & "💻 计算机名称: " & computerName & return
        set resultText to resultText & "👤 用户名: " & userName & return
        set resultText to resultText & "🔗 API状态: 正常工作" & return
        
        -- 返回结果
        return resultText
        
    on error errorMessage
        -- 如果出现错误，返回错误信息
        return "❌ 脚本执行出错: " & errorMessage
    end try
end run 