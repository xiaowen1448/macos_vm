#!/bin/zsh
set -euo pipefail

APP_NAME=ScptRunner
PROJ_DIR=$(cd "$(dirname "$0")" && pwd)
SRC_DIR="$PROJ_DIR/Sources"
OUT_APP="$PROJ_DIR/$APP_NAME.app"
BIN_DIR="$OUT_APP/Contents/MacOS"
RES_DIR="$OUT_APP/Contents/Resources"
PLIST="$PROJ_DIR/Info.plist"

echo "🚀 Building $APP_NAME for macOS 10.12..."

# Clean previous build
rm -rf "$OUT_APP"

# Create directories
mkdir -p "$BIN_DIR" "$RES_DIR"

echo "🔨 Compiling Objective-C code..."
clang \
  -framework AppKit \
  -framework Foundation \
  -framework CoreFoundation \
  -fobjc-arc \
  -std=c99 \
  -o "$BIN_DIR/$APP_NAME" \
  "$SRC_DIR/main.m"

if [ $? -eq 0 ]; then
    echo "✅ Compilation successful"
else
    echo "❌ Compilation failed"
    exit 1
fi

# Copy Info.plist
echo "📋 Copying Info.plist..."
cp "$PLIST" "$OUT_APP/Contents/Info.plist"

# Skip codesigning to avoid issues
echo "⏭️ Skipping codesigning to avoid issues"

# Verify the app structure
echo "🧐 Verifying app structure..."
if [ -f "$BIN_DIR/$APP_NAME" ]; then
    echo "✅ Executable created successfully"
    
    # Check if executable is runnable
    if [ -x "$BIN_DIR/$APP_NAME" ]; then
        echo "✅ Executable has execute permissions"
    else
        echo "⚠️ Adding execute permissions..."
        chmod +x "$BIN_DIR/$APP_NAME"
    fi
    
    # Check library dependencies
    echo "📚 Checking library dependencies..."
    otool -L "$BIN_DIR/$APP_NAME"
else
    echo "❌ Executable not found"
    exit 1
fi

if [ -f "$OUT_APP/Contents/Info.plist" ]; then
    echo "✅ Info.plist copied successfully"
else
    echo "❌ Info.plist not found"
    exit 1
fi

echo ""
echo "🎉 Build completed successfully!"
echo "📂 App location: $OUT_APP"
echo ""
echo "To test the app:"
echo "1. Double-click $OUT_APP to run"
echo "2. Or use: open '$OUT_APP'"
echo "3. Or run directly: '$BIN_DIR/$APP_NAME'"
echo ""
echo "Note: This app is built for macOS 10.12 and later using Objective-C" 