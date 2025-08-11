#!/bin/bash

echo "🚀 Quick test for ScptRunner API..."

# 检查应用程序是否运行
echo "📡 Checking if ScptRunner is running..."
if ! curl -s http://localhost:8787/script?name=test_script.scpt > /dev/null 2>&1; then
    echo "❌ ScptRunner is not running"
    echo "Please start the application first:"
    echo "  open ./ScptRunner.app"
    exit 1
fi

echo "✅ ScptRunner is running"

# 测试API
echo ""
echo "🔍 Testing API with different scripts..."

# 测试简单脚本
echo "Testing simple_test.scpt..."
response=$(curl -s "http://localhost:8787/script?name=simple_test.scpt")
echo "Response: $response"

# 测试健壮脚本
echo ""
echo "Testing robust_test.scpt..."
response=$(curl -s "http://localhost:8787/script?name=robust_test.scpt")
echo "Response: $response"

# 测试原始脚本
echo ""
echo "Testing test_script.scpt..."
response=$(curl -s "http://localhost:8787/script?name=test_script.scpt")
echo "Response: $response"

# 检查响应
if echo "$response" | grep -q "error"; then
    echo "❌ API returned an error"
    echo "💡 Make sure test_script.scpt exists in the same directory as ScptRunner.app"
else
    echo "✅ API call successful"
fi 