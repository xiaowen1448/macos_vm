#!/bin/bash

echo "🔍 Debugging ScptRunner paths..."

# 获取当前目录
echo "📂 Current directory: $(pwd)"

# 检查应用程序是否存在
if [ -d "./ScptRunner.app" ]; then
    echo "✅ ScptRunner.app exists"
    
    # 检查可执行文件
    if [ -f "./ScptRunner.app/Contents/MacOS/ScptRunner" ]; then
        echo "✅ Executable exists"
    else
        echo "❌ Executable not found"
    fi
    
    # 检查Info.plist
    if [ -f "./ScptRunner.app/Contents/Info.plist" ]; then
        echo "✅ Info.plist exists"
    else
        echo "❌ Info.plist not found"
    fi
else
    echo "❌ ScptRunner.app not found"
fi

# 检查测试脚本
echo ""
echo "📄 Checking test script..."
if [ -f "./test_script.scpt" ]; then
    echo "✅ test_script.scpt exists at: $(pwd)/test_script.scpt"
    echo "📋 Script permissions: $(ls -la test_script.scpt)"
else
    echo "❌ test_script.scpt not found"
fi

# 检查应用程序运行时的当前目录
echo ""
echo "🔍 Checking application working directory..."
if [ -f "./ScptRunner.app/Contents/MacOS/ScptRunner" ]; then
    echo "📂 Application executable: $(pwd)/ScptRunner.app/Contents/MacOS/ScptRunner"
    
    # 检查应用程序包路径
    echo "📦 Bundle path: $(pwd)/ScptRunner.app"
    
    # 检查应用程序目录
    echo "📁 App directory: $(pwd)"
fi

echo ""
echo "💡 Expected script path: $(pwd)/test_script.scpt"
echo "💡 API call: curl 'http://localhost:8787/script?name=test_script.scpt'" 