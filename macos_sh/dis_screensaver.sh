defaults -currentHost write com.apple.screensaver idleTime -int 0
killall cfprefsd
defaults -currentHost read com.apple.screensaver idleTime
