#!/bin/sh
export uu_name=`uuidgen`
echo "123456" | sudo -S scutil --set ComputerName $uu_name > /dev/null
echo "123456" | sudo -S scutil --set HostName $uu_name > /dev/null
echo "123456" | sudo -S scutil --set LocalHostName $uu_name > /dev/null
