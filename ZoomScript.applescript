use framework "Foundation"

on isBreakoutRoomLabel(theLabel)
	return theLabel contains "Room "
end isBreakoutRoomLabel

on isUnassignedLabel(theLabel)
	return theLabel is "Unassigned"
end isUnassignedLabel

on sendInMainRoom(theMessage)
	activate application "zoom.us"
	tell application "System Events"
		tell process "zoom.us"
			set mainWindow to first window whose title starts with "Zoom Meeting"
			perform action "AXRaise" of mainWindow
			try
				set messageField to text area 1 of scroll area 2 of splitter group 1 of splitter group 1 of mainWindow
			on error
				set messageField to text area 1 of scroll area 2 of splitter group 2 of splitter group 1 of mainWindow
			end try
			set value of messageField to theMessage
			set focused of messageField to true
			keystroke return
		end tell
	end tell
end sendInMainRoom

on broadcastMessage(theMessage)
	tell application "System Events"
		tell process "zoom.us"
			set breakoutRoomWindow to first window whose title starts with "Breakout Rooms"
			perform action "AXRaise" of breakoutRoomWindow
			set broadcastButton to first button of breakoutRoomWindow whose description contains "Broadcast"
			perform action "AXPress" of broadcastButton
			set messageField to first text field of breakoutRoomWindow
			set value of messageField to theMessage
			set sendButton to first button of breakoutRoomWindow whose description contains "Broadcast"
			perform action "AXPress" of sendButton
		end tell
	end tell
end broadcastMessage

on assignToRoom(theRoom, theParticipant)
	tell application "System Events"
		tell process "zoom.us"
			set breakoutRoomWindow to first window whose title starts with "Breakout Rooms"
			perform action "AXRaise" of breakoutRoomWindow
			set roomView to table 1 of scroll area 1 of breakoutRoomWindow
			set theRows to UI elements of roomView
			--set inUnassignedSection to false
			repeat with i from 1 to count theRows
				set theLabel to my labelOfRoomRow(item i of theRows)
				if theLabel is not missing value then
					--if inUnassignedSection then
					if theLabel is theParticipant then
						set rowItem to UI element 1 of item i of theRows
						try
							set assignButton to (first button whose description starts with "Assign") of rowItem
						on error
							set assignButton to (first button whose description starts with "Move To") of rowItem
						end try
						perform action "AXPress" of assignButton
						
						set assignWindow to (first window whose subrole is "AXSystemDialog")
						set theRoomRows to UI elements of table 1 of scroll area 1 of assignWindow
						
						repeat with j from 1 to count theRoomRows
							
							set roomButton to button 1 of UI element 1 of item j of theRoomRows
							set roomTitle to description of roomButton
							if roomTitle is theRoom then
								perform action "AXPress" of roomButton
								return "done"
							end if
						end repeat
						
						return "Couldn't breakout room to assign in popup dialog"
						--else if my isBreakoutRoomLabel(theLabel) then
						--	return "Couldn't find person to assign in Unassigned section"
					end if
					--else
					--	if my isUnassignedLabel(theLabel) then
					--		set inUnassignedSection to true
					--	end if
					--end if
				end if
			end repeat
			
		end tell
	end tell
end assignToRoom


on getBreakoutRooms()
	set theRooms to {}
	set currentRoomName to ""
	set currentRoomMembers to {}
	tell application "System Events"
		tell process "zoom.us"
			set breakoutRoomWindow to first window whose title starts with "Breakout Rooms"
			perform action "AXRaise" of breakoutRoomWindow
			set roomView to table 1 of scroll area 1 of breakoutRoomWindow
			set theRows to UI elements of roomView
			repeat with i from 1 to count theRows
				set theLabel to my labelOfRoomRow(item i of theRows)
				if theLabel is not missing value then
					if my isBreakoutRoomLabel(theLabel) or my isUnassignedLabel(theLabel) then
						
						-- flush room data
						if currentRoomName is not "" then
							set theRooms's end to {room_name:currentRoomName, participants:currentRoomMembers}
						end if
						
						-- init next room
						set currentRoomName to theLabel
						set currentRoomMembers to {}
						
					else
						-- member row
						set currentRoomMembers's end to theLabel
					end if
					
				end if
			end repeat
			
			-- flush room data
			if currentRoomName is not "" then
				set theRooms's end to {room_name:currentRoomName, participants:currentRoomMembers}
			end if
			
		end tell
	end tell
	return theRooms
end getBreakoutRooms

on labelOfRoomRow(theRow)
	try
		tell application "System Events" to return description of UI element 1 of theRow
	on error
		return missing value
	end try
end labelOfRoomRow

(*
on getParticipants()
	set theNames to {}
	tell application "System Events"
		tell process "zoom.us"
			set participantsView to outline 1 of scroll area 1 of splitter group 1 of window "Zoom Meeting"
			set theRows to UI elements of participantsView
			repeat with i from 1 to count theRows
				set theLabel to my labelOfParticipantRow(item i of theRows)
				if theLabel is not missing value then
					set theNames's end to theLabel
				end if
			end repeat
		end tell
	end tell
	return theNames
end getParticipants
*)

on labelOfParticipantRow(theRow)
	try
		tell application "System Events" to return value of first static text of UI element 1 of theRow
	on error
		return missing value
	end try
end labelOfParticipantRow

on toJson(theValue)
	set type to class of theValue
	if type is class then
		return "null"
	else if type is string then
		return stringToJson(theValue)
	else if type is boolean then
		if theValue then
			return "true"
		else
			return "false"
		end if
	else if type is integer or type is real then
		return theValue as text
	else if type is list then
		return listToJson(theValue)
	else if type is record then
		return recordToJson(theValue)
	else
		return ("\"TODO - " & theValue as text) & "\""
	end if
end toJson

on stringToJson(str)
	return items 5 thru -3 of listToJson({str}) as text
end stringToJson

on recordToJson(rec)
	set objCDictionary to current application's NSDictionary's dictionaryWithDictionary:rec
	
	set {jsonDictionary, anError} to current application's NSJSONSerialization's dataWithJSONObject:objCDictionary options:(current application's NSJSONWritingPrettyPrinted) |error|:(reference)
	
	if jsonDictionary is missing value then
		return "null"
	else
		return (current application's NSString's alloc()'s initWithData:jsonDictionary encoding:(current application's NSUTF8StringEncoding)) as text
	end if
end recordToJson


on listToJson(theList)
	if theList's length is 0 then return "[]"
	
	set objCArray to current application's NSArray's arrayWithArray:theList
	
	set {jsonList, anError} to current application's NSJSONSerialization's dataWithJSONObject:objCArray options:(current application's NSJSONWritingPrettyPrinted) |error|:(reference)
	
	if jsonList is missing value then
		return "null"
	else
		return (current application's NSString's alloc()'s initWithData:jsonList encoding:(current application's NSUTF8StringEncoding)) as text
	end if
end listToJson
