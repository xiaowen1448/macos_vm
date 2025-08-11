#!/bin/bash

echo "🧪 Testing iMessage Login Scripts..."

# 检查应用程序是否运行
echo "📡 Checking if ScptRunner is running..."
if ! curl -s http://localhost:8787/script?name=simple_test.scpt > /dev/null 2>&1; then
    echo "❌ ScptRunner is not running"
    echo "Please start the application first:"
    echo "  open ./ScptRunner.app"
    exit 1
fi

echo "✅ ScptRunner is running"

# 测试简化的iMessage登录脚本
echo ""
echo "🔍 Testing simplified iMessage login script..."
echo "Request: GET http://localhost:8787/script?name=imessage_simple_login.scpt"
response=$(curl -s "http://localhost:8787/script?name=imessage_simple_login.scpt")
echo "Response: $response"

# 测试修复后的原始脚本
echo ""
echo "🔍 Testing fixed original iMessage script..."
echo "Request: GET http://localhost:8787/script?name=imessage_simple_text.scpt"
response=$(curl -s "http://localhost:8787/script?name=imessage_simple_text.scpt")
echo "Response: $response"

# 测试增强版脚本
echo ""
echo "🔍 Testing enhanced iMessage login script..."
echo "Request: GET http://localhost:8787/script?name=imessage_login.scpt"
response=$(curl -s "http://localhost:8787/script?name=imessage_login.scpt")
echo "Response: $response"

echo ""
echo "🎉 iMessage login testing completed!"
echo ""
echo "💡 Note: Make sure to replace the test credentials with real ones in the script" 