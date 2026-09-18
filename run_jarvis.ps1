# JARVIS — PowerShell Launcher
param(
    [string]$Mode,
    [switch]$Tui,
    [switch]$Web,
    [switch]$Cli,
    [switch]$Voice,
    [switch]$Diagnostics,
    [int]$Port = 8888,
    [switch]$NoBrowser
)

Set-Location $PSScriptRoot

$pythonExe = "python"
if (Test-Path ".\venv\Scripts\python.exe") {
    $pythonExe = ".\venv\Scripts\python.exe"
} elseif (Test-Path ".\.venv\Scripts\python.exe") {
    $pythonExe = ".\.venv\Scripts\python.exe"
}

$argsList = @("main.py")

if ($Mode) { $argsList += @("--mode", $Mode) }
if ($Tui) { $argsList += "--tui" }
if ($Web) { $argsList += "--web"; $argsList += @("--port", $Port.ToString()) }
if ($NoBrowser) { $argsList += "--no-browser" }
if ($Cli) { $argsList += "--cli" }
if ($Voice) { $argsList += "--voice" }
if ($Diagnostics) { $argsList += "--diagnostics" }

& $pythonExe $argsList
