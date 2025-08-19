-- 验证码输入调试脚本
-- 增强版调试功能，用于解决输入失败问题

property testResults : {}
property debugMode : true

-- 主调试函数
on run
	try
		-- 清空测试结果
		set testResults to {}
		
		-- 切换到Messages应用
		tell application "Messages" to activate
		delay 3
		
		-- 开始全面调试
		set debugResult to performFullDebug()
		
		-- 返回调试结果
		return generateDebugReport()
		
	on error errMsg
		set end of testResults to {testName:"main_debug", success:false, message:"调试执行失败: " & errMsg, timestamp:(current date) as string}
		return generateDebugReport()
	end try
end run

-- 执行全面调试
on performFullDebug()
	try
		set end of testResults to {testName:"debug_start", success:true, message:"开始全面调试验证码输入问题", timestamp:(current date) as string}
		
		-- 1. 检查Messages应用状态
		checkMessagesAppStatus()
		
		-- 2. 分析当前窗口结构
		analyzeCurrentWindow()
		
		-- 3. 查找所有可能的输入框
		findAllInputFields()
		
		-- 4. 测试键盘输入功能
		testKeyboardInput()
		
		-- 5. 尝试强制输入方法
		tryForceInput()
		
		return true
		
	on error errMsg
		set end of testResults to {testName:"debug_error", success:false, message:"调试过程出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end performFullDebug

-- 检查Messages应用状态
on checkMessagesAppStatus()
	try
		set end of testResults to {testName:"app_status_check", success:true, message:"检查Messages应用状态", timestamp:(current date) as string}
		
		tell application "System Events"
			-- 检查Messages进程是否存在
			if exists process "Messages" then
				set end of testResults to {testName:"messages_process_exists", success:true, message:"Messages进程存在", timestamp:(current date) as string}
				
				tell process "Messages"
					-- 检查窗口数量
					set windowCount to count of windows
					set end of testResults to {testName:"window_count", success:true, message:"窗口数量: " & windowCount, timestamp:(current date) as string}
					
					-- 检查前台状态
					set isFrontmost to frontmost
					set end of testResults to {testName:"app_frontmost", success:true, message:"应用是否在前台: " & isFrontmost, timestamp:(current date) as string}
				end tell
			else
				set end of testResults to {testName:"messages_process_missing", success:false, message:"Messages进程不存在", timestamp:(current date) as string}
			end if
		end tell
		
	on error errMsg
		set end of testResults to {testName:"app_status_error", success:false, message:"检查应用状态出错: " & errMsg, timestamp:(current date) as string}
	end try
end checkMessagesAppStatus

-- 分析当前窗口结构
on analyzeCurrentWindow()
	try
		set end of testResults to {testName:"window_analysis_start", success:true, message:"开始分析当前窗口结构", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				if exists window 1 then
					-- 获取窗口基本信息
					set windowTitle to name of window 1
					set windowPosition to position of window 1
					set windowSize to size of window 1
					set end of testResults to {testName:"window_info", success:true, message:"窗口标题: '" & windowTitle & "' 位置: " & windowPosition & " 大小: " & windowSize, timestamp:(current date) as string}
					
					-- 检查是否有sheet对话框
					if exists sheet 1 of window 1 then
						set end of testResults to {testName:"sheet_exists", success:true, message:"检测到sheet对话框", timestamp:(current date) as string}
						
						-- 分析sheet内容
						set sheetTexts to every static text of sheet 1 of window 1
						repeat with i from 1 to count of sheetTexts
							try
								set sheetText to item i of sheetTexts
								set textValue to value of sheetText
								set end of testResults to {testName:"sheet_text_" & i, success:true, message:"Sheet文本 " & i & ": '" & textValue & "'", timestamp:(current date) as string}
							end try
						end repeat
					else
						set end of testResults to {testName:"no_sheet", success:true, message:"未检测到sheet对话框", timestamp:(current date) as string}
					end if
					
					-- 统计所有UI元素
					set allElements to entire contents of window 1
					set elementCount to count of allElements
					set end of testResults to {testName:"total_elements", success:true, message:"窗口总UI元素数: " & elementCount, timestamp:(current date) as string}
				else
					set end of testResults to {testName:"no_window", success:false, message:"未找到Messages窗口", timestamp:(current date) as string}
				end if
			end tell
		end tell
		
	on error errMsg
		set end of testResults to {testName:"window_analysis_error", success:false, message:"窗口分析出错: " & errMsg, timestamp:(current date) as string}
	end try
end analyzeCurrentWindow

-- 查找所有可能的输入框
on findAllInputFields()
	try
		set end of testResults to {testName:"input_field_search", success:true, message:"开始查找所有输入框", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				if exists window 1 then
					-- 查找主窗口的输入框
					set mainTextFields to every text field of window 1
					set mainFieldCount to count of mainTextFields
					set end of testResults to {testName:"main_text_fields", success:true, message:"主窗口输入框数量: " & mainFieldCount, timestamp:(current date) as string}
					
					repeat with i from 1 to mainFieldCount
						try
							set textField to item i of mainTextFields
							set fieldValue to value of textField
							set fieldPlaceholder to placeholder of textField
							set fieldPosition to position of textField
							set fieldSize to size of textField
							set fieldEnabled to enabled of textField
							set fieldFocused to focused of textField
							set end of testResults to {testName:"main_field_" & i, success:true, message:"主输入框 " & i & ": 值='" & fieldValue & "' placeholder='" & fieldPlaceholder & "' 位置=" & fieldPosition & " 大小=" & fieldSize & " 启用=" & fieldEnabled & " 焦点=" & fieldFocused, timestamp:(current date) as string}
						end try
					end repeat
					
					-- 查找sheet对话框的输入框
					if exists sheet 1 of window 1 then
						set sheetTextFields to every text field of sheet 1 of window 1
						set sheetFieldCount to count of sheetTextFields
						set end of testResults to {testName:"sheet_text_fields", success:true, message:"Sheet输入框数量: " & sheetFieldCount, timestamp:(current date) as string}
						
						repeat with i from 1 to sheetFieldCount
							try
								set sheetField to item i of sheetTextFields
								set sheetValue to value of sheetField
								set sheetPlaceholder to placeholder of sheetField
								set sheetPosition to position of sheetField
								set sheetSize to size of sheetField
								set sheetEnabled to enabled of sheetField
								set sheetFocused to focused of sheetField
								set end of testResults to {testName:"sheet_field_" & i, success:true, message:"Sheet输入框 " & i & ": 值='" & sheetValue & "' placeholder='" & sheetPlaceholder & "' 位置=" & sheetPosition & " 大小=" & sheetSize & " 启用=" & sheetEnabled & " 焦点=" & sheetFocused, timestamp:(current date) as string}
							end try
						end repeat
					end if
				end if
			end tell
		end tell
		
	on error errMsg
		set end of testResults to {testName:"input_field_error", success:false, message:"查找输入框出错: " & errMsg, timestamp:(current date) as string}
	end try
end findAllInputFields

-- 测试键盘输入功能
on testKeyboardInput()
	try
		set end of testResults to {testName:"keyboard_test_start", success:true, message:"开始测试键盘输入功能", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				-- 测试基本键盘输入
				keystroke "TEST"
				delay 1
				set end of testResults to {testName:"basic_keystroke", success:true, message:"执行基本键盘输入测试", timestamp:(current date) as string}
				
				-- 测试数字输入
				keystroke "1234"
				delay 2
				set end of testResults to {testName:"number_keystroke", success:true, message:"执行数字键盘输入测试", timestamp:(current date) as string}
				
				-- 清除输入
				keystroke "a" using command down
				keystroke delete
				set end of testResults to {testName:"clear_input", success:true, message:"清除输入测试", timestamp:(current date) as string}
			end tell
		end tell
		
	on error errMsg
		set end of testResults to {testName:"keyboard_test_error", success:false, message:"键盘输入测试出错: " & errMsg, timestamp:(current date) as string}
	end try
end testKeyboardInput

-- 尝试强制输入方法
on tryForceInput()
	try
		set testCode to "999888"
		set end of testResults to {testName:"force_input_start", success:true, message:"开始尝试强制输入方法", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				if exists window 1 then
					-- 方法1: 尝试点击并输入每个输入框
					set allTextFields to every text field of window 1
					repeat with i from 1 to count of allTextFields
						try
							set textField to item i of allTextFields
							set end of testResults to {testName:"force_click_" & i, success:true, message:"尝试点击输入框 " & i, timestamp:(current date) as string}
							
							-- 点击输入框
							click textField
							delay 0.5
							
							-- 设置焦点
							set focused of textField to true
							delay 0.5
							
							-- 清空现有内容
							set value of textField to ""
							delay 0.2
							
							-- 输入测试代码
							set value of textField to testCode
							delay 0.5
							
							-- 检查输入结果
							set currentValue to value of textField
							if currentValue = testCode then
								set end of testResults to {testName:"force_success_" & i, success:true, message:"强制输入成功，输入框 " & i & " 值: '" & currentValue & "'", timestamp:(current date) as string}
							else
								set end of testResults to {testName:"force_partial_" & i, success:false, message:"强制输入部分成功，输入框 " & i & " 期望: '" & testCode & "' 实际: '" & currentValue & "'", timestamp:(current date) as string}
							end if
							
							-- 尝试键盘输入
							keystroke testCode
							delay 0.5
							set keyboardValue to value of textField
							set end of testResults to {testName:"keyboard_input_" & i, success:true, message:"键盘输入后，输入框 " & i & " 值: '" & keyboardValue & "'", timestamp:(current date) as string}
							
						end try
					end repeat
					
					-- 方法2: 尝试sheet对话框输入
					if exists sheet 1 of window 1 then
						set sheetTextFields to every text field of sheet 1 of window 1
						repeat with i from 1 to count of sheetTextFields
							try
								set sheetField to item i of sheetTextFields
								set end of testResults to {testName:"sheet_force_" & i, success:true, message:"尝试强制输入Sheet输入框 " & i, timestamp:(current date) as string}
								
								click sheetField
								delay 0.5
								set focused of sheetField to true
								delay 0.5
								set value of sheetField to testCode
								delay 0.5
								
								set sheetCurrentValue to value of sheetField
								set end of testResults to {testName:"sheet_result_" & i, success:true, message:"Sheet强制输入结果，输入框 " & i & " 值: '" & sheetCurrentValue & "'", timestamp:(current date) as string}
							end try
						end repeat
					end if
				end if
			end tell
		end tell
		
	on error errMsg
		set end of testResults to {testName:"force_input_error", success:false, message:"强制输入出错: " & errMsg, timestamp:(current date) as string}
	end try
end tryForceInput

-- 生成调试报告
on generateDebugReport()
	try
		set reportLines to {}
		set end of reportLines to "=== 验证码输入调试报告 ==="
		set end of reportLines to "调试时间: " & (current date) as string
		set end of reportLines to "调试结果数量: " & (count of testResults)
		set end of reportLines to ""
		
		set successCount to 0
		set failureCount to 0
		
		repeat with testResult in testResults
			set testName to testName of testResult
			set success to success of testResult
			set message to message of testResult
			set timestamp to timestamp of testResult
			
			if success then
				set successCount to successCount + 1
				set statusText to "[成功]"
			else
				set failureCount to failureCount + 1
				set statusText to "[失败]"
			end if
			
			set end of reportLines to statusText & " " & testName & ": " & message
		end repeat
		
		set end of reportLines to ""
		set end of reportLines to "=== 调试统计 ==="
		set end of reportLines to "成功: " & successCount
		set end of reportLines to "失败: " & failureCount
		set end of reportLines to "总计: " & (successCount + failureCount)
		
		-- 将报告行合并为字符串
		set AppleScript's text item delimiters to return
		set reportText to reportLines as string
		set AppleScript's text item delimiters to ""
		
		return reportText
		
	on error errMsg
		return "生成调试报告时出错: " & errMsg
	end try
end generateDebugReport