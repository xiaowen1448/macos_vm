on run argv
    set scriptArgs to argv
    
    -- 使用固定参数进行测试
    set testText to "Hello from ScptRunner! This is a test message."
    set testPassword to "testpassword123"
    
    -- 初始化结果字符串
    set outputText to "iMessage文本输入测试开始:" & return
    set outputText to outputText & "测试文本: " & testText & return
    set outputText to outputText & "测试密码: " & testPassword & return
    set outputText to outputText & "参数数量: " & (count of scriptArgs) & return
    
    try
        -- 步骤1: 启动Messages应用
        set outputText to outputText & "步骤1: 启动Messages应用" & return
        tell application "Messages"
            activate
            delay 2
        end tell
        
        -- 步骤2: 等待应用启动
        set outputText to outputText & "步骤2: 等待应用启动 (3秒)" & return
        delay 3
        
        -- 步骤3: 尝试输入文本
        set outputText to outputText & "步骤3: 尝试输入文本" & return
        
        tell application "System Events"
            tell process "Messages"
                -- 检测并处理密码输入框
                try
                    set passwordHandled to false
                    
                    -- 调试信息：列出所有窗口
                    set windowCount to count of windows
                    set outputText to outputText & "检测到 " & windowCount & " 个窗口" & return
                    
                    -- 遍历所有窗口
                    repeat with i from 1 to windowCount
                        try
                            set windowName to name of window i
                            set outputText to outputText & "窗口 " & i & ": " & windowName & return
                            
                            -- 列出窗口中的所有文本字段
                            set textFieldCount to count of text fields of window i
                            set outputText to outputText & "  窗口 " & i & " 有 " & textFieldCount & " 个文本字段" & return
                            
                            repeat with j from 1 to textFieldCount
                                try
                                    set fieldName to name of text field j of window i
                                    set outputText to outputText & "    文本字段 " & j & ": " & fieldName & return
                                on error
                                    set outputText to outputText & "    文本字段 " & j & ": (无法获取名称)" & return
                                end try
                            end repeat
                        on error
                            set outputText to outputText & "无法访问窗口 " & i & return
                        end try
                    end repeat
                    
                    -- 检测方法1: 查找密码输入框（中文界面）
                    try
                        if exists (text field "密码" of window 1) then
                            set outputText to outputText & "检测到密码输入框" & return
                            click text field "密码" of window 1
                            delay 1
                            keystroke testPassword
                            set passwordHandled to true
                            delay 2
                        end if
                    on error
                        -- 继续检测其他方法
                    end try
                    
                    -- 检测方法2: 查找Password输入框（英文界面）
                    if not passwordHandled then
                        try
                            if exists (text field "Password" of window 1) then
                                set outputText to outputText & "检测到Password输入框" & return
                                click text field "Password" of window 1
                                delay 1
                                keystroke testPassword
                                set passwordHandled to true
                                delay 2
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    -- 检测方法3: 查找第二个文本字段（通常是密码框）
                    if not passwordHandled then
                        try
                            if exists (text field 2 of window 1) then
                                set outputText to outputText & "检测到第二个文本字段（可能是密码框）" & return
                                click text field 2 of window 1
                                delay 1
                                keystroke testPassword
                                set passwordHandled to true
                                delay 2
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    -- 检测方法4: 查找所有文本字段并尝试输入
                    if not passwordHandled then
                        try
                            set textFieldCount to count of text fields of window 1
                            if textFieldCount >= 2 then
                                set outputText to outputText & "尝试在第二个文本字段输入密码" & return
                                click text field 2 of window 1
                                delay 1
                                keystroke testPassword
                                set passwordHandled to true
                                delay 2
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    if passwordHandled then
                        set outputText to outputText & "成功在密码输入框中输入文本" & return
                    else
                        set outputText to outputText & "未检测到密码输入框" & return
                    end if
                    
                on error passwordError
                    set outputText to outputText & "密码输入过程出错: " & passwordError & return
                end try
            end tell
            
            -- 尝试使用keystroke输入文本
            try
                keystroke testText
                set outputText to outputText & "使用keystroke输入文本成功: " & testText & return
            on error keystrokeError
                set outputText to outputText & "keystroke输入失败: " & keystrokeError & return
            end try
            
            -- 尝试按回车键
            try
                delay 1
                key code 36 -- 回车键
                set outputText to outputText & "已按回车键尝试发送" & return
            on error sendError
                set outputText to outputText & "发送失败: " & sendError & return
            end try
        end tell
        
        -- 步骤4: 测试完成
        set outputText to outputText & "步骤4: 测试完成" & return
        set outputText to outputText & "iMessage文本输入测试完成" & return
        set outputText to outputText & "注意: 请检查Messages应用中的文本输入结果"
        
        return outputText
        
    on error errMsg
        return "执行错误: " & errMsg
    end try
end run
