Scriptname CLAWDistributionMenu extends Quest

Int Property MenuKey = 66 Auto ; F8. Human OBody binding is left unchanged.
Bool menuBusy = False

Event OnInit()
    Initialize()
EndEvent

Function Initialize()
    menuBusy = False
    RegisterForKey(MenuKey)
    RegisterForModEvent("CLAWDistribution_Loaded", "OnDistributionLoaded")
EndFunction

Function OnDistributionLoaded(String eventName, String strArg, Float numArg, Form sender)
    Initialize()
EndFunction

Event OnKeyDown(Int keyCode)
    If keyCode != MenuKey || Utility.IsInMenuMode() || menuBusy
        Return
    EndIf
    Actor target = Game.GetCurrentCrosshairRef() as Actor
    If target == None
        target = Game.GetPlayer()
    EndIf
    ShowPresetMenu(target)
EndEvent

Function ShowPresetMenu(Actor target)
    If menuBusy || target == None
        Return
    EndIf
    Race beastRace = Game.GetFormFromFile(0x0CDD84, "Skyrim.esm") as Race
    If target.GetRace() != beastRace
        Debug.Notification("CLAW: target a werewolf. Human body presets remain in OBody.")
        Return
    EndIf
    UIListMenu list = UIExtensions.GetMenu("UIListMenu") as UIListMenu
    If list == None
        Debug.Notification("CLAW: UIExtensions is required to select a body preset.")
        Return
    EndIf
    Bool female = target.GetActorBase().GetSex() == 1
    String[] names = CLAWDistributionNative.GetPresetNames(female)
    If names.Length == 0
        Debug.Notification("CLAW: no valid body presets available for this werewolf.")
        Return
    EndIf
    menuBusy = True
    Int page = 0
    Int pageSize = 60
    Bool browsing = True
    While browsing
        list.ResetMenu()
        String assigned = CLAWDistributionNative.GetAssigned(target)
        If CLAWDistributionNative.GetStatus(target) == 6
            assigned = "No preset (automatic selection disabled)"
        ElseIf assigned == ""
            assigned = "Automatic selection"
        EndIf
        list.AddEntryItem("Current: " + assigned)
        Int resetEntry = list.AddEntryItem("Clear CLAW body preset")
        Int previousEntry = -1
        Int nextEntry = -1
        If page > 0
            previousEntry = list.AddEntryItem("< Previous page")
        EndIf
        Int first = page * pageSize
        Int last = first + pageSize
        If last < names.Length
            nextEntry = list.AddEntryItem("Next page >")
        Else
            last = names.Length
        EndIf
        Int firstPresetEntry = list.GetPropertyInt("currentIndex")
        Int i = first
        While i < last
            list.AddEntryItem(names[i])
            i += 1
        EndWhile
        list.OpenMenu(target)
        Int result = list.GetResultInt()
        If result < 0
            browsing = False
        ElseIf result == resetEntry
            CLAWDistributionNative.ClearOwn(target)
            browsing = False
        ElseIf previousEntry >= 0 && result == previousEntry
            page -= 1
        ElseIf nextEntry >= 0 && result == nextEntry
            page += 1
        ElseIf result >= firstPresetEntry && result < firstPresetEntry + last - first
            String chosen = names[first + result - firstPresetEntry]
            If CLAWDistributionNative.AssignPreset(target, chosen)
                Debug.Notification("CLAW preset selected: " + chosen)
            Else
                Debug.Notification("CLAW: this preset could not be selected.")
            EndIf
            browsing = False
        EndIf
    EndWhile
    menuBusy = False
EndFunction

Function ChangeMenuKey(Int newKey)
    If newKey < 1 || newKey > 255
        Return
    EndIf
    UnregisterForKey(MenuKey)
    MenuKey = newKey
    RegisterForKey(MenuKey)
EndFunction
