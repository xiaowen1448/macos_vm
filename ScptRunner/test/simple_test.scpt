-- 简单测试AppleScript脚本
-- 避免复杂的系统信息获取，确保兼容性

on run
    -- 获取当前时间
    set currentTime to (current date) as string
    
    -- 构建简单的返回信息
    set resultText to "✅ 测试脚本执行成功！" & return & return
    set resultText to resultText & "📅 当前时间: " & currentTime & return
    set resultText to resultText & "🖥️ 系统: macOS" & return
    set resultText to resultText & "📦 应用程序: ScptRunner" & return
    set resultText to resultText & "🔗 API: 正常工作" & return
    
    -- 返回结果
    return resultText
end run 