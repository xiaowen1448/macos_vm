export uu_name=`uuidgen`
echo "123456" | sudo -S scutil --set ComputerName $uu_name
echo "123456" | sudo -S scutil --set LocalHostName $uu_name
