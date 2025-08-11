-- 简单的JSON测试脚本
-- 返回一个标准的JSON字符串

set jsonString to "{\"status\":\"success\",\"message\":\"Hello from AppleScript\",\"timestamp\":\"" & (current date as string) & "\",\"data\":{\"test\":true,\"number\":42}}"

return jsonString