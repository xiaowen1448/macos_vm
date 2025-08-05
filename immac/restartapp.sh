#!/bin/sh
ps aux | grep immac | grep -v grep | awk '{print $2}' | xargs kill
sleep 1
ps aux | grep Messages.app | grep -v grep | awk '{print $2}' | xargs kill
sleep 1

open /Users/cc/Documents/immac.app/
sleep 2