if [ -e /Users/cc/config.plist ]
then
	echo "found config.plist, start to config"
	sleep 5
	sudo diskutil mount /dev/disk0s1
	sleep 3
	cp -f /Users/cc/config.plist /Volumes/EFI/EFI/CLOVER/config.plist
	mv -f /Users/cc/config.plist /Users/cc/config.plist.set
	sleep 1
	sudo /System/Library/Filesystems/hfs.fs/Contents/Resources/hfs.util -s disk0s2
	touch /Users/cc/has5ma
	touch /Users/cc/logs
	echo has5ma >> /Users/cc/has5ma
	echo started >> /Users/cc/logs
	sleep 5
	sudo shutdown -r now
else
	echo "no config plist, skip."
fi
