-- Rulează JavaScript în primul tab Chrome care conține textul "match".
-- argv: match, javascript. Întoarce rezultatul sau __NOCHROME__ / __NOTAB__.
on run argv
	set matchText to item 1 of argv
	set js to item 2 of argv
	if application "Google Chrome" is not running then return "__NOCHROME__"
	tell application "Google Chrome"
		repeat with w in windows
			repeat with t in tabs of w
				if (URL of t) contains matchText then
					set r to execute t javascript js
					if r is missing value then return ""
					return r as text
				end if
			end repeat
		end repeat
	end tell
	return "__NOTAB__"
end run
