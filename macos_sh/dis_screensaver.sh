defaults write com.apple.screensaver idleTime -int 0
defaults -currentHost write com.apple.screensaver idleTime -int 0
launchctl unload -w /System/Library/LaunchAgents/com.apple.ScreenSaver.Engine.plist
killall cfprefsd
killall SystemUIServer
defaults -currentHost read com.apple.screensaver idleTime
defaults read com.apple.screensaver idleTime