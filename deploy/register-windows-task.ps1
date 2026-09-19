[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$ConfigPath,
    [Parameter(Mandatory = $true)][string]$EnvFile,
    [switch]$AtStartup,
    [switch]$Backup,
    [switch]$Preview
)
$ErrorActionPreference = 'Stop'
$taskRepository = (Resolve-Path -LiteralPath $RepoPath).Path
$taskConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$taskEnvironment = (Resolve-Path -LiteralPath $EnvFile).Path
$taskPython = Join-Path $taskRepository '.venv\Scripts\python.exe'
$taskLauncher = Join-Path $taskRepository 'deploy\windows_runner.py'
if (-not (Test-Path -LiteralPath $taskPython -PathType Leaf)) { throw 'Create the repository virtual environment first.' }
$taskMode = if ($Backup) { 'backup' } else { 'daemon' }
$taskName = if ($Backup) { 'Internship Watch Backup' } else { 'Internship Watch' }
$taskState = Join-Path $taskRepository 'data\service'
$taskParts = @($taskLauncher, '--config', $taskConfig, '--env-file', $taskEnvironment,
               '--mode', $taskMode, '--state-dir', $taskState)
foreach ($part in $taskParts) { if ($part.Contains('"')) { throw 'A task argument contains an unsupported quote.' } }
$taskArguments = ($taskParts | ForEach-Object { '"' + $_ + '"' }) -join ' '
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($AtStartup) {
    $taskVenvConfig = Get-Content -LiteralPath (Join-Path $taskRepository '.venv\pyvenv.cfg')
    if ($taskVenvConfig | Where-Object { $_ -match '^home\s*=' -and $_ -like ('*' + $env:USERPROFILE + '*') }) {
        throw 'Startup mode requires a machine-wide Python installation and a venv rebuilt from it; the current Python is in a user profile.'
    }
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\LOCAL SERVICE' -LogonType ServiceAccount -RunLevel Limited
} else {
    $taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
}
if ($Backup) {
    $taskTrigger = New-ScheduledTaskTrigger -Daily -At '03:15'
} elseif ($AtStartup) {
    $taskTrigger = New-ScheduledTaskTrigger -AtStartup
} else {
    $taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
}
$taskAction = New-ScheduledTaskAction -Execute $taskPython -Argument $taskArguments -WorkingDirectory $taskRepository
$taskSettings = New-ScheduledTaskSettingsSet -Hidden -MultipleInstances IgnoreNew -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
if ($Preview) {
    [pscustomobject]@{ Name = $taskName; Mode = $taskMode; AtStartup = [bool]$AtStartup;
        Execute = $taskPython; Arguments = $taskArguments; StartsAutomaticallyNow = $false }
    return
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw 'A task with this name already exists. Inspect and update it deliberately; this script does not overwrite it.'
}
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger `
    -Principal $taskPrincipal -Settings $taskSettings -Description 'Persistent internship collection or verified encrypted backup.' | Out-Null
Write-Output ('Registered ' + $taskName + '. Start it explicitly after configuration and monitor setup are complete.')
