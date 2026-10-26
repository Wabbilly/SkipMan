-- SkipMan.app — the Dock/Finder launcher.
-- Click it: opens SkipMan. Drop links or .webloc files on it: adds them.
-- skipman://add?url=... links (e.g. from a bookmark) also land here.

property appDir : "__APP_DIR__"

on run
	launchSkipMan({})
end run

on open theItems
	set args to {}
	repeat with f in theItems
		set end of args to POSIX path of f
	end repeat
	launchSkipMan(args)
end open

on open location theURL
	launchSkipMan({theURL})
end open location

on launchSkipMan(args)
	set cmd to quoted form of (appDir & "/mac/run.sh")
	repeat with a in args
		set cmd to cmd & " " & quoted form of (a as text)
	end repeat
	do shell script cmd & " > /dev/null 2>&1 &"
end launchSkipMan
