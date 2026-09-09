@echo off
chcp 936 >nul
setlocal
rem 卸载：删除快捷方式与程序目录（延迟执行，避免删除自身目录冲突）
set "TARGET=%LOCALAPPDATA%\狸猫猫表单"
if not "%~1"=="" set "TARGET=%~1"
set "VBS=%TEMP%\lmk_uninstall_%RANDOM%.vbs"
> "%VBS%" echo Set ws = CreateObject("WScript.Shell")
>>"%VBS%" echo Set fso = CreateObject("Scripting.FileSystemObject")
>>"%VBS%" echo If MsgBox("确定卸载「狸猫猫表单」吗？", vbYesNo + vbQuestion, "卸载狸猫猫表单") ^<^> vbYes Then WScript.Quit
>>"%VBS%" echo On Error Resume Next
>>"%VBS%" echo fso.DeleteFile ws.SpecialFolders("Desktop") ^& "\狸猫猫表单.lnk", True
>>"%VBS%" echo WScript.Sleep 600
>>"%VBS%" echo fso.DeleteFolder "%TARGET%", True
>>"%VBS%" echo MsgBox "已卸载完成。", vbInformation, "狸猫猫表单"
start "" wscript.exe "%VBS%"
endlocal
