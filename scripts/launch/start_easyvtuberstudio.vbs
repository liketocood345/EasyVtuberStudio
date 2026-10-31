' Launch EasyVtuberStudio splash with pythonw before any cmd.exe window.
Option Explicit
Dim fso, sh, here, repo, pythonw, script, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
' This script lives in scripts/launch, two levels below the portable root.
repo = fso.GetParentFolderName(fso.GetParentFolderName(here))
pythonw = repo & "\addons\face_puppeteer\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonw) Then
  pythonw = repo & "\runtime\venv\Scripts\pythonw.exe"
End If
If Not fso.FileExists(pythonw) Then
  pythonw = repo & "\workspace\student_venv\Scripts\pythonw.exe"
End If
script = repo & "\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\start_with_splash.py"
If Not fso.FileExists(pythonw) Or Not fso.FileExists(script) Then
  sh.Run """" & repo & "\scripts\launch\run_load_preview_puppeteer.bat""", 1, False
  WScript.Quit 1
End If
cmd = """" & pythonw & """ """ & script & """"
sh.Run cmd, 0, False
