# MacOS UI Automation Application Installer

## Installation Instructions

### Method 1: Using Installer Script (Recommended)
1. Extract the installer package
2. Run the installer script in terminal:
   ```bash
   sudo ./install.sh
   ```

### Method 2: Manual Installation
1. Extract the installer package
2. Drag `MacOSUIAutomation.app` to Applications folder
3. Grant permissions in System Preferences

## Permission Settings

First run requires the following permissions:

1. **Accessibility Permission**:
   - System Preferences > Security & Privacy > Accessibility
   - Click lock icon to unlock settings
   - Add `MacOSUIAutomation.app` and check it

2. **Automation Permission**:
   - System Preferences > Security & Privacy > Automation
   - Allow application to control other applications

## Application Features

- **iMessage Auto Click Later**: Automatically open iMessage and click "Later" button
- **Disable Apple ID Alert**: Disable Apple ID related warning prompts
- **Disable Screensaver**: Disable screensaver program
- **Reboot System**: Reboot macOS system
- **Custom Scripts**: Support custom AppleScript, Shell, Python scripts

## Usage

1. Start application: `open /Applications/MacOSUIAutomation.app`
2. Select script from the list
3. Click "Execute Selected Script" button
4. View results in log area

## System Requirements

- macOS 10.12 or higher
- Python 3.6 or higher (built into application)

## Technical Support

If you encounter issues, please check:
1. System version meets requirements
2. Permission settings are correct
3. Script syntax is correct

## Version Information

- Version: 1.0
- Release Date: 2024
- Supported Systems: macOS 10.12+
