-- 验证码输入测试脚本
-- 专门用于测试和调试验证码输入功能

property testResults : {}
property debugMode : true

-- 主测试函数
on run
	try
		-- 清空测试结果
		set testResults to {}
		
		-- 切换到Messages应用
		tell application "Messages" to activate
		delay 2
		
		-- 开始验证码输入测试
		set testResult to testVerificationCodeInput()
		
		-- 返回测试结果
		return generateTestReport()
		
	on error errMsg
		set end of testResults to {testName:"main_test", success:false, message:"测试执行失败: " & errMsg, timestamp:(current date) as string}
		return generateTestReport()
	end try
end run

-- 测试验证码输入功能
on testVerificationCodeInput()
	try
		set end of testResults to {testName:"verification_test_start", success:true, message:"开始验证码输入测试", timestamp:(current date) as string}
		
		-- 等待验证码窗口出现
		set windowFound to waitForVerificationWindow()
		
		if windowFound then
			set end of testResults to {testName:"window_detection", success:true, message:"成功检测到验证码窗口", timestamp:(current date) as string}
			
			-- 分析UI结构
			debugVerificationUI()
			
			-- 测试所有输入方法
			testAllInputMethods()
		else
			set end of testResults to {testName:"window_detection", success:false, message:"未检测到验证码窗口", timestamp:(current date) as string}
		end if
		
		return true
		
	on error errMsg
		set end of testResults to {testName:"verification_test_error", success:false, message:"验证码测试出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testVerificationCodeInput

-- 等待验证码窗口出现
on waitForVerificationWindow()
	try
		tell application "System Events"
			tell process "Messages"
				repeat 30 times
					-- 检查窗口标题
					try
						if exists window 1 then
							set windowTitle to name of window 1
							if windowTitle contains "验证" or windowTitle contains "Verification" or windowTitle contains "Code" then
								set end of testResults to {testName:"window_title_check", success:true, message:"通过窗口标题检测到验证码窗口: " & windowTitle, timestamp:(current date) as string}
								return true
							end if
						end if
					end try
					
					-- 检查sheet对话框
					try
						if exists sheet 1 of window 1 then
							set sheetTexts to every static text of sheet 1 of window 1
							repeat with sheetText in sheetTexts
								try
									set textValue to value of sheetText
									if textValue contains "验证码" or textValue contains "verification code" or textValue contains "输入发送至" then
										set end of testResults to {testName:"sheet_text_check", success:true, message:"通过sheet文本检测到验证码窗口: " & textValue, timestamp:(current date) as string}
										return true
									end if
								end try
							end repeat
						end if
					end try
					
					-- 检查文本输入框的placeholder
					try
						set allTextFields to every text field of window 1
						repeat with textField in allTextFields
							try
								set placeholderText to placeholder of textField
								if placeholderText contains "验证码" or placeholderText contains "verification code" then
									set end of testResults to {testName:"placeholder_check", success:true, message:"通过placeholder检测到验证码窗口: " & placeholderText, timestamp:(current date) as string}
									return true
								end if
							end try
						end repeat
					end try
					
					delay 1
				end repeat
			end tell
		end tell
		
		set end of testResults to {testName:"window_wait_timeout", success:false, message:"等待验证码窗口超时", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"window_wait_error", success:false, message:"等待验证码窗口出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end waitForVerificationWindow

-- 调试验证码UI结构
on debugVerificationUI()
	try
		set end of testResults to {testName:"ui_debug_start", success:true, message:"开始分析验证码UI结构", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				if exists window 1 then
					-- 统计主窗口UI元素
					set allElements to entire contents of window 1
					set elementCount to count of allElements
					set end of testResults to {testName:"ui_element_count", success:true, message:"主窗口UI元素总数: " & elementCount, timestamp:(current date) as string}
					
					-- 列出所有静态文本
					set allStaticTexts to every static text of window 1
					set staticTextCount to count of allStaticTexts
					set end of testResults to {testName:"static_text_count", success:true, message:"静态文本数量: " & staticTextCount, timestamp:(current date) as string}
					
					repeat with i from 1 to staticTextCount
						try
							set staticText to item i of allStaticTexts
							set textValue to value of staticText
							set textPosition to position of staticText
							set end of testResults to {testName:"static_text_" & i, success:true, message:"静态文本 " & i & ": '" & textValue & "' 位置: " & textPosition, timestamp:(current date) as string}
						end try
					end repeat
					
					-- 分析所有文本输入框
					set allTextFields to every text field of window 1
					set textFieldCount to count of allTextFields
					set end of testResults to {testName:"text_field_count", success:true, message:"文本输入框数量: " & textFieldCount, timestamp:(current date) as string}
					
					repeat with i from 1 to textFieldCount
						try
							set textField to item i of allTextFields
							set fieldValue to value of textField
							set fieldPlaceholder to placeholder of textField
							set fieldPosition to position of textField
							set fieldSize to size of textField
							set end of testResults to {testName:"text_field_" & i, success:true, message:"输入框 " & i & ": 值='" & fieldValue & "' placeholder='" & fieldPlaceholder & "' 位置=" & fieldPosition & " 大小=" & fieldSize, timestamp:(current date) as string}
						end try
					end repeat
					
					-- 检查sheet对话框
					if exists sheet 1 of window 1 then
						set sheetTextFields to every text field of sheet 1 of window 1
						set sheetFieldCount to count of sheetTextFields
						set end of testResults to {testName:"sheet_field_count", success:true, message:"Sheet对话框输入框数量: " & sheetFieldCount, timestamp:(current date) as string}
						
						repeat with i from 1 to sheetFieldCount
							try
								set sheetField to item i of sheetTextFields
								set sheetValue to value of sheetField
								set sheetPlaceholder to placeholder of sheetField
								set sheetPosition to position of sheetField
								set sheetSize to size of sheetField
								set end of testResults to {testName:"sheet_field_" & i, success:true, message:"Sheet输入框 " & i & ": 值='" & sheetValue & "' placeholder='" & sheetPlaceholder & "' 位置=" & sheetPosition & " 大小=" & sheetSize, timestamp:(current date) as string}
							end try
						end repeat
					end if
				end if
			end tell
		end tell
		
		set end of testResults to {testName:"ui_debug_complete", success:true, message:"UI结构分析完成", timestamp:(current date) as string}
		
	on error errMsg
		set end of testResults to {testName:"ui_debug_error", success:false, message:"UI调试出错: " & errMsg, timestamp:(current date) as string}
	end try
end debugVerificationUI

-- 测试所有输入方法
on testAllInputMethods()
	try
		set testCode to "123456" -- 测试用验证码
		set end of testResults to {testName:"input_methods_start", success:true, message:"开始测试所有验证码输入方法", timestamp:(current date) as string}
		
		-- 方法1：基于"验证码"文本定位
		testInputMethod1(testCode)
		
		-- 方法2：通过placeholder属性查找
		testInputMethod2(testCode)
		
		-- 方法3：通过输入框宽度判断
		testInputMethod3(testCode)
		
		-- 方法4：在sheet对话框中查找
		testInputMethod4(testCode)
		
		-- 方法5：Tab键导航
		testInputMethod5(testCode)
		
		-- 方法6：直接输入
		testInputMethod6(testCode)
		
		set end of testResults to {testName:"input_methods_complete", success:true, message:"所有输入方法测试完成", timestamp:(current date) as string}
		
	on error errMsg
		set end of testResults to {testName:"input_methods_error", success:false, message:"输入方法测试出错: " & errMsg, timestamp:(current date) as string}
	end try
end testAllInputMethods

-- 测试方法1：基于"验证码"文本定位
on testInputMethod1(testCode)
	try
		set end of testResults to {testName:"method1_start", success:true, message:"测试方法1：基于'验证码'文本定位", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				set allStaticTexts to every static text of window 1
				repeat with staticText in allStaticTexts
					try
						set textValue to value of staticText
						if textValue contains "验证码" or textValue contains "verification code" then
							set textPosition to position of staticText
							set end of testResults to {testName:"method1_text_found", success:true, message:"找到验证码文本: '" & textValue & "' 位置: " & textPosition, timestamp:(current date) as string}
							
							-- 尝试在附近查找输入框
							set allTextFields to every text field of window 1
							repeat with textField in allTextFields
								try
									set fieldPosition to position of textField
									-- 简单的位置判断逻辑
									set end of testResults to {testName:"method1_field_attempt", success:true, message:"尝试输入框位置: " & fieldPosition, timestamp:(current date) as string}
									
									-- 尝试输入测试代码
									set focused of textField to true
									set value of textField to testCode
									set end of testResults to {testName:"method1_success", success:true, message:"方法1成功输入测试代码: " & testCode, timestamp:(current date) as string}
									return true
								end try
							end repeat
						end if
					end try
				end repeat
			end tell
		end tell
		
		set end of testResults to {testName:"method1_failed", success:false, message:"方法1未能找到合适的输入框", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"method1_error", success:false, message:"方法1出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod1

-- 测试方法2：通过placeholder属性查找
on testInputMethod2(testCode)
	try
		set end of testResults to {testName:"method2_start", success:true, message:"测试方法2：通过placeholder属性查找", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				set allTextFields to every text field of window 1
				repeat with textField in allTextFields
					try
						set placeholderText to placeholder of textField
						if placeholderText contains "验证码" or placeholderText contains "verification code" or placeholderText contains "code" then
							set end of testResults to {testName:"method2_placeholder_found", success:true, message:"找到验证码placeholder: '" & placeholderText & "'", timestamp:(current date) as string}
							
							-- 尝试输入测试代码
							set focused of textField to true
							set value of textField to testCode
							set end of testResults to {testName:"method2_success", success:true, message:"方法2成功输入测试代码: " & testCode, timestamp:(current date) as string}
							return true
						end if
					end try
				end repeat
			end tell
		end tell
		
		set end of testResults to {testName:"method2_failed", success:false, message:"方法2未能找到合适的输入框", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"method2_error", success:false, message:"方法2出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod2

-- 测试方法3：通过输入框宽度判断
on testInputMethod3(testCode)
	try
		set end of testResults to {testName:"method3_start", success:true, message:"测试方法3：通过输入框宽度判断", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				set allTextFields to every text field of window 1
				repeat with textField in allTextFields
					try
						set fieldSize to size of textField
						set fieldWidth to item 1 of fieldSize
						-- 验证码输入框通常比较窄
						if fieldWidth > 50 and fieldWidth < 200 then
							set end of testResults to {testName:"method3_size_match", success:true, message:"找到合适宽度的输入框: " & fieldWidth, timestamp:(current date) as string}
							
							-- 尝试输入测试代码
							set focused of textField to true
							set value of textField to testCode
							set end of testResults to {testName:"method3_success", success:true, message:"方法3成功输入测试代码: " & testCode, timestamp:(current date) as string}
							return true
						end if
					end try
				end repeat
			end tell
		end tell
		
		set end of testResults to {testName:"method3_failed", success:false, message:"方法3未能找到合适的输入框", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"method3_error", success:false, message:"方法3出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod3

-- 测试方法4：在sheet对话框中查找
on testInputMethod4(testCode)
	try
		set end of testResults to {testName:"method4_start", success:true, message:"测试方法4：在sheet对话框中查找", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				if exists sheet 1 of window 1 then
					set sheetTextFields to every text field of sheet 1 of window 1
					repeat with textField in sheetTextFields
						try
							set end of testResults to {testName:"method4_sheet_field_found", success:true, message:"在sheet中找到输入框", timestamp:(current date) as string}
							
							-- 尝试输入测试代码
							set focused of textField to true
							set value of textField to testCode
							set end of testResults to {testName:"method4_success", success:true, message:"方法4成功输入测试代码: " & testCode, timestamp:(current date) as string}
							return true
						end try
					end repeat
				else
					set end of testResults to {testName:"method4_no_sheet", success:false, message:"未找到sheet对话框", timestamp:(current date) as string}
				end if
			end tell
		end tell
		
		set end of testResults to {testName:"method4_failed", success:false, message:"方法4未能找到合适的输入框", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"method4_error", success:false, message:"方法4出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod4

-- 测试方法5：Tab键导航
on testInputMethod5(testCode)
	try
		set end of testResults to {testName:"method5_start", success:true, message:"测试方法5：Tab键导航", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				-- 尝试使用Tab键导航到验证码输入框
				repeat 5 times
					keystroke tab
					delay 0.5
					
					-- 尝试输入测试代码
					try
						keystroke testCode
						set end of testResults to {testName:"method5_success", success:true, message:"方法5成功输入测试代码: " & testCode, timestamp:(current date) as string}
						return true
					end try
				end repeat
			end tell
		end tell
		
		set end of testResults to {testName:"method5_failed", success:false, message:"方法5未能成功输入", timestamp:(current date) as string}
		return false
		
	on error errMsg
		set end of testResults to {testName:"method5_error", success:false, message:"方法5出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod5

-- 测试方法6：直接输入
on testInputMethod6(testCode)
	try
		set end of testResults to {testName:"method6_start", success:true, message:"测试方法6：直接输入", timestamp:(current date) as string}
		
		tell application "System Events"
			tell process "Messages"
				-- 直接尝试输入验证码
				keystroke testCode
				set end of testResults to {testName:"method6_success", success:true, message:"方法6成功输入测试代码: " & testCode, timestamp:(current date) as string}
				return true
			end tell
		end tell
		
	on error errMsg
		set end of testResults to {testName:"method6_error", success:false, message:"方法6出错: " & errMsg, timestamp:(current date) as string}
		return false
	end try
end testInputMethod6

-- 生成测试报告
on generateTestReport()
	try
		set reportLines to {}
		set end of reportLines to "=== 验证码输入测试报告 ==="
		set end of reportLines to "测试时间: " & (current date) as string
		set end of reportLines to "测试结果数量: " & (count of testResults)
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
		set end of reportLines to "=== 测试统计 ==="
		set end of reportLines to "成功: " & successCount
		set end of reportLines to "失败: " & failureCount
		set end of reportLines to "总计: " & (successCount + failureCount)
		
		-- 将报告行合并为字符串
		set AppleScript's text item delimiters to return
		set reportText to reportLines as string
		set AppleScript's text item delimiters to ""
		
		return reportText
		
	on error errMsg
		return "生成测试报告时出错: " & errMsg
	end try
end generateTestReport