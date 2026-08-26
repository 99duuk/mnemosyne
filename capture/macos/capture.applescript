property bridgeHeader : "MNEMOSYNE_BRIDGE_V1"

on bridgeError(code)
	return bridgeHeader & linefeed & "ERROR" & linefeed & code
end bridgeError

on safariTab(expectedURL)
	if application "Safari" is not running then return my bridgeError("NO_SAFARI_TAB")
	try
		tell application "Safari"
			if frontmost is false then return my bridgeError("SAFARI_NOT_FRONTMOST")
			if (count of windows) is 0 then return my bridgeError("NO_SAFARI_TAB")
			set selectedTab to «class cTab» of front window
			if selectedTab is missing value then return my bridgeError("NO_SAFARI_TAB")
			set currentURL to «class pURL» of selectedTab
		end tell
	on error errorText number errorNumber
		if errorNumber is -1743 then return my bridgeError("APPLE_EVENTS_DENIED")
		if errorNumber is -1728 then return my bridgeError("NO_SAFARI_TAB")
		error errorText number errorNumber
	end try
	if currentURL is missing value or currentURL is "" then return my bridgeError("NO_SAFARI_TAB")
	if expectedURL is not missing value and currentURL is not expectedURL then return my bridgeError("TAB_CHANGED")
	return {selectedTab, currentURL}
end safariTab

on run arguments
	if (count of arguments) is 0 then error "invalid bridge mode"
	set bridgeMode to item 1 of arguments
	if bridgeMode is "notify" then
		if (count of arguments) is not 3 then error "invalid notify arity"
		«event sysonotf» (item 3 of arguments) given «class appr»:(item 2 of arguments)
		return bridgeHeader & linefeed & "OK"
	end if
	if bridgeMode is "snapshot" then
		if (count of arguments) is not 1 then error "invalid snapshot arity"
		set tabResult to my safariTab(missing value)
		if class of tabResult is text then return tabResult
		return bridgeHeader & linefeed & "OK" & linefeed & item 2 of tabResult
	end if
	if bridgeMode is not "smoke" and bridgeMode is not "extract" then error "invalid bridge mode"
	if bridgeMode is "smoke" and (count of arguments) is not 2 then error "invalid smoke arity"
	if bridgeMode is "extract" and (count of arguments) is not 3 then error "invalid extract arity"
	set expectedURL to item 2 of arguments
	set tabResult to my safariTab(expectedURL)
	if class of tabResult is text then return tabResult
	set selectedTab to item 1 of tabResult
	set beforeURL to item 2 of tabResult
	try
		if bridgeMode is "smoke" then
			tell application "Safari"
				set pageResult to «event sfridojs» "'MNEMOSYNE_JS_OK'" given «class dcnm»:selectedTab
			end tell
		else
			set extractorSource to «event rdwrread» («class psxf» (item 3 of arguments)) given «class as  »:«class utf8»
			tell application "Safari"
				set pageResult to «event sfridojs» extractorSource given «class dcnm»:selectedTab
			end tell
		end if
	on error errorText number errorNumber
		if errorNumber is -1743 then return my bridgeError("APPLE_EVENTS_DENIED")
		if errorNumber is -2700 and errorText contains "JavaScript from Apple Events" then return my bridgeError("JAVASCRIPT_UNAVAILABLE")
		error errorText number errorNumber
	end try
	set rebound to my safariTab(expectedURL)
	if class of rebound is text then return rebound
	if item 1 of rebound is not selectedTab then return my bridgeError("TAB_CHANGED")
	set afterURL to item 2 of rebound
	if bridgeMode is "smoke" then
		if pageResult is not "MNEMOSYNE_JS_OK" then error "unexpected smoke result"
		return bridgeHeader & linefeed & "OK" & linefeed & pageResult
	end if
	if pageResult is "MNEMOSYNE_UNSUPPORTED_PAGE" then return my bridgeError("UNSUPPORTED_PAGE")
	return bridgeHeader & linefeed & "OK" & linefeed & beforeURL & linefeed & afterURL & linefeed & pageResult
end run
