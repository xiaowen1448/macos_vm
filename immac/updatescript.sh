#!/bin/sh
ps aux | grep immac | grep -v grep | awk '{print $2}' | xargs kill
sleep 1

unzip -o /Users/cc/Documents/pgq.zip -d /Users/cc/Documents
open /Users/cc/Documents/immac.app/
sleep 2