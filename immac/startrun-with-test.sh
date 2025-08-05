#!/bin/sh
ps aux | grep immac | grep -v grep | awk '{print $2}' | xargs kill
sleep 1

rm -rf /Users/cc/run/*
rm -rf /Users/cc/done/$1
rm -rf /Users/cc/stoptask/$1
rm -rf /Users/cc/result/$1
rm -rf /Users/cc/lrun/*
rm -rf /Users/cc/ldone/$1
rm -rf /Users/cc/lstoptask/$1
rm -rf /Users/cc/lresult/$1
rm -rf /Users/cc/ltested
rm -rf /Users/cc/lresult/ltestnumbers
rm -rf /Users/cc/Library/Preferences/ByHost/com.apple.identityservices.idstatuscache*
rm -rf /Users/cc/Library/Preferences/com.apple.iChat.plist
ps aux | grep identityservicesd | grep -v grep | awk '{print $2}' | xargs kill
ps aux | grep Messages.app | grep -v grep | awk '{print $2}' | xargs kill

sleep 1
 
open /Users/cc/Documents/immac.app/

sleep 2