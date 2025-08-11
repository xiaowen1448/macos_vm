-- 测试AppleScript脚本
-- 这个脚本用于测试ScptRunner的API功能

on run
    -- 获取当前时间
    set currentTime to (current date) as string
    
    -- 获取系统信息
    set systemInfo to system info
    
    -- 获取用户名（兼容macOS 10.12）
    set userName to short user name of systemInfo
    
    -- 构建返回信息
    set resultText to "测试脚本执行成功！" & return & return
    set resultText to resultText & "当前时间: " & currentTime & return
    set resultText to resultText & "系统版本: " & (system version of systemInfo) & return
    set resultText to resultText & "计算机名称: " & (computer name of systemInfo) & return
    set resultText to resultText & "用户名: " & userName & return
    
    -- 返回结果
    return resultText
end run 