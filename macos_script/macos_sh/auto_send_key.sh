osascript -e 'tell application "System Events" to keystroke (ASCII character 127)'
sleep 2
osascript -e 'tell application "System Events" to keystroke (ASCII character 127)'
sleep 2
osascript -e 'tell application "System Events" to keystroke "123456"'
osascript -e 'tell application "System Events" to keystroke return'
echo $?
