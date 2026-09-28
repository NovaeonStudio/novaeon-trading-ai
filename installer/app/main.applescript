-- NovaeonTradingAI.app: first launch runs the installer in Terminal, later launches open the app in the browser.
-- All logic lives in launch.sh (Contents/Resources) so it can be tested without clicking.
on run
	set launcher to POSIX path of (path to resource "launch.sh")
	try
		do shell script "/bin/bash " & quoted form of launcher
	on error errMsg
		display dialog "NovaeonTradingAI could not start:" & return & return & errMsg buttons {"OK"} default button "OK" with icon caution
	end try
end run
