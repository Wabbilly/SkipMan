' SkipMan launcher — silent (no console flash)
' Uses python.exe (more reliable than pythonw.exe on this system)
' with WScript.Run window style 0 to hide the console.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
localAppData = sh.ExpandEnvironmentStrings("%LocalAppData%")

' Try common python.exe install locations, fall back to PATH
candidates = Array( _
    localAppData & "\Programs\Python\Python313\python.exe", _
    localAppData & "\Programs\Python\Python312\python.exe", _
    localAppData & "\Programs\Python\Python311\python.exe", _
    "C:\Python313\python.exe", _
    "C:\Python312\python.exe", _
    "C:\Python311\python.exe" _
)

py = ""
For Each c In candidates
    If fso.FileExists(c) Then
        py = c
        Exit For
    End If
Next

If py = "" Then py = "python.exe"  ' last resort: PATH lookup

sh.CurrentDirectory = scriptDir
' Style 0 = hidden window (no console flash). False = don't wait for exit.
sh.Run """" & py & """ """ & scriptDir & "\skipman.pyw""", 0, False
