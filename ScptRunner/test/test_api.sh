#!/bin/bash

echo "🧪 Testing ScptRunner API..."

# 检查应用程序是否运行
echo "📡 Checking if ScptRunner is running..."
if ! curl -s http://localhost:8787/script?name=test_script.scpt > /dev/null 2>&1; then
    echo "❌ ScptRunner is not running or not accessible"
    echo "Please start the application first:"
    echo "  open ./ScptRunner.app"
    exit 1
fi

echo "✅ ScptRunner is running"

# 测试简化 API
echo ""
echo "🔍 Testing simplified API..."
echo "Request: GET http://localhost:8787/script?name=test_script.scpt"
response=$(curl -s "http://localhost:8787/script?name=test_script.scpt")
echo "Response: $response"

# 测试完整路径 API
echo ""
echo "🔍 Testing full path API..."
echo "Request: GET http://localhost:8787/run?path=$(pwd)/test_script.scpt"
response=$(curl -s "http://localhost:8787/run?path=$(pwd)/test_script.scpt")
echo "Response: $response"

# 测试错误情况
echo ""
echo "🔍 Testing error case..."
echo "Request: GET http://localhost:8787/script?name=nonexistent.scpt"
response=$(curl -s "http://localhost:8787/script?name=nonexistent.scpt")
echo "Response: $response"

echo ""
echo "🎉 API testing completed!" 