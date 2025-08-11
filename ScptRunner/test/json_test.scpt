-- JSON测试脚本
-- 返回标准JSON格式的数据

on run
    -- 获取当前时间
    set currentTime to (current date) as string
    
    -- 构建JSON格式的返回数据
    set jsonResult to "{" & return
    set jsonResult to jsonResult & "  \"status\": \"success\"," & return
    set jsonResult to jsonResult & "  \"message\": \"测试脚本执行成功\"," & return
    set jsonResult to jsonResult & "  \"timestamp\": \"" & currentTime & "\"," & return
    set jsonResult to jsonResult & "  \"data\": {" & return
    set jsonResult to jsonResult & "    \"system\": \"macOS\"," & return
    set jsonResult to jsonResult & "    \"application\": \"ScptRunner\"," & return
    set jsonResult to jsonResult & "    \"api\": \"working\"" & return
    set jsonResult to jsonResult & "  }" & return
    set jsonResult to jsonResult & "}"
    
    -- 返回JSON结果
    return jsonResult
end run