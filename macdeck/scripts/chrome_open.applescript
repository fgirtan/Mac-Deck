-- Deschide un URL în Google Chrome. Dacă un tab conține deja textul "match",
-- îl aduce în față în loc să deschidă unul nou.
-- argv: url, match, newTab ("1" = deschide mereu tab nou)
on run argv
	set targetURL to item 1 of argv
	set matchText to item 2 of argv
	set forceNew to (item 3 of argv) is "1"
	tell application "Google Chrome"
		if not forceNew then
			repeat with w in windows
				set i to 0
				repeat with t in tabs of w
					set i to i + 1
					if (URL of t) contains matchText then
						set active tab index of w to i
						set index of w to 1
						activate
						return "focused"
					end if
				end repeat
			end repeat
		end if
		if (count of windows) is 0 then
			make new window
			set URL of active tab of front window to targetURL
		else
			tell front window to make new tab with properties {URL:targetURL}
		end if
		activate
	end tell
	return "opened"
end run
