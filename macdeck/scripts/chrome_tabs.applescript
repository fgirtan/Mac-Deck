-- Listează tab-urile Chrome: o linie per tab, "activ<TAB>url<TAB>titlu".
-- Primul tab marcat cu 1 e tab-ul activ al ferestrei din față.
on run argv
	if application "Google Chrome" is not running then return ""
	set out to ""
	tell application "Google Chrome"
		set wi to 0
		repeat with w in windows
			set wi to wi + 1
			set ai to active tab index of w
			set ti to 0
			repeat with t in tabs of w
				set ti to ti + 1
				set flag to "0"
				if wi is 1 and ti is ai then set flag to "1"
				set out to out & flag & tab & (URL of t) & tab & (title of t) & linefeed
			end repeat
		end repeat
	end tell
	return out
end run
