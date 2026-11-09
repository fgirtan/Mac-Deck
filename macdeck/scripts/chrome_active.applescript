-- URL-ul tab-ului activ din fereastra Chrome din față (sau nimic).
if application "Google Chrome" is not running then return ""
tell application "Google Chrome"
	if (count of windows) is 0 then return ""
	return URL of active tab of front window
end tell
