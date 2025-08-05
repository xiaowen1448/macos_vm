#!/bin/sh
rm -rf /Users/cc/Library/Preferences/ByHost/com.apple.identityservices.idstatuscache*
rm -rf /Users/cc/Library/Preferences/com.apple.iChat.plist
ps aux | grep identityservicesd | grep -v grep | awk '{print $2}' | xargs kill
ps aux | grep Messages.app | grep -v grep | awk '{print $2}' | xargs kill
sleep 3
open /Applications/Messages.app/ 
