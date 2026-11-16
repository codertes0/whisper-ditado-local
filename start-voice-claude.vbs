' Inicia o voice-claude escondido (sem janela de terminal).
' Window style 0 = oculto. Roda em segundo plano igual ao Wispr Flow.
Dim sh
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.Run "cmd /c "".venv\Scripts\python.exe -u voice_claude.py > last-run.log 2> last-run.err""", 0, False
