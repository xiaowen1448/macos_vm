on run argv
    set scriptArgs to argv
    
    -- 获取账号和密码参数
    set appleID to "test@example.com"
    set password to "testpassword"
    
    if (count of scriptArgs) >= 2 then
        set appleID to (item 1 of scriptArgs) as string
        set password to (item 2 of scriptArgs) as string
    end if
    
    -- 初始化结果字符串
    set outputText to "iMessage登录自动化脚本开始:" & return
    set outputText to outputText & "Apple ID: " & appleID & return
    set outputText to outputText & "参数数量: " & (count of scriptArgs) & return
    
    try
        -- 步骤1: 启动Messages应用
        set outputText to outputText & "步骤1: 启动Messages应用" & return
        tell application "Messages"
            activate
            delay 3
        end tell
        
        -- 步骤2: 等待应用启动
        set outputText to outputText & "步骤2: 等待应用启动" & return
        delay 5
        
        tell application "System Events"
            tell process "Messages"
                -- 检查是否需要登录
                try
                    -- 尝试多种登录界面检测
                    set loginDetected to false
                    
                    -- 检测方法1: 查找登录按钮
                    try
                        if exists (button "登录" of window 1) then
                            set outputText to outputText & "检测到登录按钮" & return
                            set loginDetected to true
                            
                            -- 点击登录按钮
                            click button "登录" of window 1
                            delay 2
                        end if
                    on error
                        -- 继续检测其他方法
                    end try
                    
                    -- 检测方法2: 查找"Sign In"按钮（英文界面）
                    if not loginDetected then
                        try
                            if exists (button "Sign In" of window 1) then
                                set outputText to outputText & "检测到Sign In按钮" & return
                                set loginDetected to true
                                
                                -- 点击Sign In按钮
                                click button "Sign In" of window 1
                                delay 2
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    -- 检测方法3: 查找Apple ID输入框
                    if not loginDetected then
                        try
                            if exists (text field 1 of window 1) then
                                set outputText to outputText & "检测到登录输入框" & return
                                set loginDetected to true
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    -- 检测方法4: 查找用户名输入框
                    if not loginDetected then
                        try
                            if exists (text field "用户名" of window 1) then
                                set outputText to outputText & "检测到用户名输入框" & return
                                set loginDetected to true
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    -- 检测方法5: 查找"Username"输入框（英文界面）
                    if not loginDetected then
                        try
                            if exists (text field "Username" of window 1) then
                                set outputText to outputText & "检测到Username输入框" & return
                                set loginDetected to true
                            end if
                        on error
                            -- 继续检测其他方法
                        end try
                    end if
                    
                    if loginDetected then
                        -- 开始登录流程
                        set outputText to outputText & "开始登录流程..." & return
                        
                        -- 输入Apple ID
                        set outputText to outputText & "步骤3: 输入Apple ID" & return
                        keystroke appleID
                        delay 1
                        
                        -- 按Tab键切换到密码框
                        set outputText to outputText & "步骤4: 切换到密码框" & return
                        key code 48 -- Tab键
                        delay 1
                        
                        -- 输入密码
                        set outputText to outputText & "步骤5: 输入密码" & return
                        keystroke password
                        delay 1
                        
                        -- 按回车键登录
                        set outputText to outputText & "步骤6: 点击登录" & return
                        key code 36 -- 回车键
                        delay 3
                        
                        set outputText to outputText & "登录流程完成" & return
                        
                    else
                        set outputText to outputText & "未检测到登录界面，可能已经登录" & return
                        set outputText to outputText & "或者需要手动处理登录界面" & return
                    end if
                    
                on error loginError
                    set outputText to outputText & "登录过程出错: " & loginError & return
                    set outputText to outputText & "可能需要手动处理登录界面" & return
                end try
            end tell
        end tell
        
        -- 步骤7: 测试完成
        set outputText to outputText & "步骤7: 测试完成" & return
        set outputText to outputText & "iMessage登录自动化完成" & return
        set outputText to outputText & "请检查Messages应用中的登录状态" & return
        
        return outputText
        
    on error errMsg
        return "执行错误: " & errMsg
    end try
end run 