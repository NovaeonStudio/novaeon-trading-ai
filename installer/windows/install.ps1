# NovaeonTradingAI installer for Windows 10/11 (BETA): installs the Linux version inside WSL2 (Ubuntu).
#
#   irm https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/installer/windows/install.ps1 | iex
#
# Options: as environment variables before the line above (e.g. $env:NOVAEON_SENTINEL_MODE = "remote"), or as
# parameters when the script is run as a file:
#   .\install.ps1 -Sentinel remote -SentinelUrl http://100.101.102.103:8010 -StartAtLogon
#     -Sentinel      remote | cuda | cpu | off   where the news check runs (default: the Linux installer decides/asks)
#     -SentinelUrl   the Sentinel on your Mac, e.g. http://100.101.102.103:8010/v1/systemone (mode remote)
#     -Distro        WSL distribution to use (default Ubuntu)
#     -StartAtLogon  keep WSL (and so the bot) running after you log in: a scheduled task, opt-in
#     -RemoveStartAtLogon   remove that scheduled task again
#     -Yes           accept every default (no questions)
#   Environment: NOVAEON_SENTINEL_MODE, NOVAEON_SENTINEL_URL, NOVAEON_WSL_DISTRO, NOVAEON_START_AT_LOGON=1,
#                NOVAEON_YES=1, NOVAEON_INSTALL_URL (another install.sh, for testing).
#
# What it does: checks Windows and WSL2, installs Ubuntu in WSL if there is none (needs admin rights once and maybe a
# restart; then run this again), turns on systemd in that distribution, and runs the regular Linux installer there.
# The app is then at http://localhost:8081 in your Windows browser. The bot runs only while WSL runs.
# Nothing here needs to stay open afterwards; the Linux installer's defaults apply (practice money, random password,
# reachable from this PC only, 1x leverage).

function Install-NovaeonTradingAI {
    [CmdletBinding()]
    param(
        [string] $Sentinel = $env:NOVAEON_SENTINEL_MODE,
        [string] $SentinelUrl = $env:NOVAEON_SENTINEL_URL,
        [string] $Distro = $env:NOVAEON_WSL_DISTRO,
        [switch] $StartAtLogon,
        [switch] $RemoveStartAtLogon,
        [switch] $Yes
    )
    $ErrorActionPreference = 'Stop'
    $distroGiven = [bool]$Distro
    if (-not $Distro) { $Distro = 'Ubuntu' }
    if ($env:NOVAEON_START_AT_LOGON -eq '1') { $StartAtLogon = $true }
    if ($env:NOVAEON_YES -eq '1') { $Yes = $true }
    if ($null -eq $Sentinel) { $Sentinel = '' }
    if (@('', 'remote', 'cuda', 'cpu', 'off') -notcontains $Sentinel) {
        Write-Host "Unknown Sentinel mode '$Sentinel' (remote, cuda, cpu or off; mlx needs a Mac)." -ForegroundColor Red; return
    }
    $installUrl = 'https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/install.sh'
    if ($env:NOVAEON_INSTALL_URL) { $installUrl = $env:NOVAEON_INSTALL_URL }
    $taskName = 'NovaeonTradingAI - keep WSL running'
    $env:WSL_UTF8 = '1'   # wsl.exe prints UTF-16 otherwise

    function Step([string] $t) { Write-Host ''; Write-Host "==> $t" -ForegroundColor White }
    function Info([string] $t) { Write-Host "    $t" }
    function Ok([string] $t) { Write-Host "    $t" -ForegroundColor Green }
    function Warn([string] $t) { Write-Host "    ! $t" -ForegroundColor Yellow }
    function Stop-Install([string] $t) { Write-Host ''; Write-Host "Install stopped: $t" -ForegroundColor Red; throw 'NovaeonTradingAI install stopped' }
    function Ask([string] $q, [bool] $def) {
        if ($Yes) { return $def }
        $hint = if ($def) { '[Y/n]' } else { '[y/N]' }
        $a = Read-Host "    $q $hint"
        if (-not $a) { return $def }
        return $a -match '^[yY]'
    }
    function Test-Admin {
        $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    function Invoke-Wsl([string[]] $a) {   # run wsl.exe, return its output lines (without the NULs older versions add)
        $ErrorActionPreference = 'Continue'   # Windows PowerShell 5.1 turns redirected stderr lines into errors otherwise
        $out = & wsl.exe @a 2>&1
        $script:wslExit = $LASTEXITCODE
        return @($out | ForEach-Object { "$_" -replace "`0", '' } | Where-Object { $_ -ne '' })
    }
    function Get-WslDistro { $l = Invoke-Wsl @('--list', '--quiet'); if ($script:wslExit -ne 0) { return @() }; return @($l | ForEach-Object { $_.Trim() }) }
    function ConvertTo-BashWord([string] $s) { return "'" + ($s -replace "'", "'\''") + "'" }

    function Remove-Task {
        if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
            Ok "removed the scheduled task '$taskName'"
        } else { Info "no scheduled task '$taskName' found" }
    }

    Write-Host 'NovaeonTradingAI installer for Windows (BETA: runs the Linux version inside WSL2)' -ForegroundColor White
    if ($RemoveStartAtLogon) { Remove-Task; return }

    # ------------------------------------------------------------------ Windows
    Step 'Checking Windows'
    $build = [Environment]::OSVersion.Version.Build
    if (-not [Environment]::Is64BitOperatingSystem) { Stop-Install 'A 64-bit Windows is required.' }
    if ($build -lt 19041) {
        Stop-Install "WSL2 needs Windows 10 version 2004 (build 19041) or newer, or Windows 11. This PC has build $($build): run Windows Update first."
    }
    $winName = if ($build -ge 22000) { 'Windows 11' } else { 'Windows 10' }
    $arch = $env:PROCESSOR_ARCHITECTURE
    Ok "$winName (build $build, $arch)"

    # ------------------------------------------------------------------ WSL
    Step 'Checking WSL2'
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Stop-Install 'wsl.exe was not found. WSL needs Windows 10 2004+ or Windows 11.' }
    $null = Invoke-Wsl @('--version')
    if ($script:wslExit -ne 0) {
        # the old built-in WSL has no --version and no systemd support: update to the current WSL first
        Info 'updating WSL to the current version (wsl --update)...'
        & wsl.exe --update
        $null = Invoke-Wsl @('--version')
        if ($script:wslExit -ne 0) { Stop-Install "Could not update WSL. Run 'wsl --update' in an administrator PowerShell, then run this installer again." }
    }
    $distros = Get-WslDistro
    if (-not $distroGiven -and $distros -notcontains $Distro) {   # e.g. "Ubuntu-24.04" from an earlier WSL setup
        $other = $distros | Where-Object { $_ -like 'Ubuntu*' } | Select-Object -First 1
        if ($other) { $Distro = $other; Info "using the existing WSL distribution $Distro" }
    }
    if ($distros -notcontains $Distro) {
        Warn "No WSL distribution named '$Distro' yet."
        Info 'Installing it needs administrator rights once (Windows asks), and Windows may need a restart.'
        Info "After that, open '$Distro' from the Start menu once, create your Linux user name and password,"
        Info 'and run this installer again.'
        if (-not (Ask "Install $Distro in WSL now?" $true)) { Stop-Install "WSL distribution $Distro missing (install it with: wsl --install -d $Distro)." }
        if (Test-Admin) { & wsl.exe --install -d $Distro }
        else { Start-Process -FilePath wsl.exe -ArgumentList @('--install', '-d', $Distro) -Verb RunAs -Wait }
        Write-Host ''
        Write-Host "Next: restart Windows if it asks you to, open '$Distro' once from the Start menu (create your user), then run" -ForegroundColor White
        Write-Host '  irm https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/installer/windows/install.ps1 | iex' -ForegroundColor White
        return
    }
    $verLine = Invoke-Wsl @('--list', '--verbose') | Where-Object { $_ -match "^\*?\s*$([regex]::Escape($Distro))\s" } | Select-Object -First 1
    if ($verLine -and $verLine -match '\s1\s*$') {
        Info "$Distro runs as WSL 1: converting it to WSL 2 (this can take a few minutes)..."
        & wsl.exe --set-version $Distro 2
        if ($LASTEXITCODE -ne 0) { Stop-Install "Could not convert $Distro to WSL 2 (wsl --set-version $Distro 2)." }
    }
    $user = (Invoke-Wsl @('-d', $Distro, '--exec', 'id', '-un') | Select-Object -Last 1)
    $uid = (Invoke-Wsl @('-d', $Distro, '--exec', 'id', '-u') | Select-Object -Last 1)
    if ($script:wslExit -ne 0 -or -not $user) { Stop-Install "Could not start $Distro. Open it once from the Start menu and finish its setup, then run this again." }
    if ($uid -eq '0') {
        Stop-Install "$Distro logs in as root. Open $Distro, create a normal user (sudo adduser <name>), make it the default (see 'Change the default user' in Microsoft's WSL docs), then run this again."
    }
    Ok "WSL2 distribution $Distro, Linux user $user"

    # ------------------------------------------------------------------ systemd
    # --exec: no Linux shell in between (it would expand $ and quotes a second time). No double quotes in the arguments:
    # Windows PowerShell 5.1 does not escape them for native programs.
    $pid1 = (Invoke-Wsl @('-d', $Distro, '--exec', 'ps', '-p', '1', '-o', 'comm=') | Select-Object -Last 1)
    if ($pid1 -ne 'systemd') {
        Step "Turning on systemd in $Distro (the bot runs as systemd user services)"
        Info 'This writes [boot] systemd=true to /etc/wsl.conf and restarts WSL (wsl --shutdown):'
        Info 'every open WSL window and running Linux program stops once.'
        if (-not (Ask 'Continue?' $true)) { Stop-Install 'systemd is required in WSL.' }
        $fix = 'f=/etc/wsl.conf; touch $f; if grep -qE ''^[[:space:]]*systemd[[:space:]]*='' $f; then sed -i -E ''s/^[[:space:]]*systemd[[:space:]]*=.*/systemd=true/'' $f; elif grep -q ''^\[boot\]'' $f; then sed -i ''/^\[boot\]/a systemd=true'' $f; else printf ''\n[boot]\nsystemd=true\n'' >> $f; fi'
        $null = Invoke-Wsl @('-d', $Distro, '-u', 'root', '--exec', 'sh', '-c', $fix)
        if ($script:wslExit -ne 0) { Stop-Install 'Could not write /etc/wsl.conf.' }
        & wsl.exe --shutdown
        Start-Sleep -Seconds 8
        $pid1 = (Invoke-Wsl @('-d', $Distro, '--exec', 'ps', '-p', '1', '-o', 'comm=') | Select-Object -Last 1)
        if ($pid1 -ne 'systemd') { Stop-Install "systemd did not start in $Distro (PID 1 is '$pid1'). Update WSL (wsl --update) and try again." }
        Ok 'systemd is on'
    }
    # linger: the user's services run without an open WSL window (as long as WSL itself runs)
    $null = Invoke-Wsl @('-d', $Distro, '-u', 'root', '--exec', 'loginctl', 'enable-linger', $user)

    # ------------------------------------------------------------------ Linux installer
    Step "Running the Linux installer in $Distro"
    $opts = @()
    if ($Sentinel) { $opts += @('--sentinel', $Sentinel) }
    if ($SentinelUrl) { $opts += @('--sentinel-url', $SentinelUrl) }
    if ($Yes) { $opts += '--yes' }
    $optStr = ($opts | ForEach-Object { ConvertTo-BashWord $_ }) -join ' '
    $cmd = "set -o pipefail; command -v curl >/dev/null || { echo 'curl is missing: sudo apt install curl' >&2; exit 1; }; " +
           "curl -fsSL $(ConvertTo-BashWord $installUrl) | NOVAEON_NO_OPEN=1 bash -s -- $optStr"
    & wsl.exe -d $Distro --exec bash -lc $cmd
    if ($LASTEXITCODE -ne 0) { Stop-Install "The Linux installer stopped (see above). Run this again to resume." }

    $port = (Invoke-Wsl @('-d', $Distro, '--exec', 'sh', '-c', '. $HOME/NovaeonTradingAI/install.env 2>/dev/null && echo $NOVAEON_ENGINE_PORT') | Select-Object -Last 1)
    if (-not ($port -match '^\d+$')) { $port = '8081' }
    $url = "http://localhost:$port"

    # ------------------------------------------------------------------ keep running (opt-in)
    Step 'Keeping the bot running'
    Info 'WSL stops a while after its last window closes, and with it the bot. A scheduled task can start WSL when you'
    Info 'log in to Windows and keep it running in the background (no window).'
    $hasTask = [bool](Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)
    if (-not $StartAtLogon -and -not $hasTask -and -not $Yes) { $StartAtLogon = (Ask 'Start and keep WSL running when you log in?' $false) }
    if ($StartAtLogon) {
        $arg = "-NoProfile -WindowStyle Hidden -Command `"wsl.exe -d $Distro --exec /bin/sleep infinity`""
        $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
        $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
            -Description 'Keeps WSL running so NovaeonTradingAI trades while you are logged in (installer/windows/install.ps1).' -Force | Out-Null
        Start-ScheduledTask -TaskName $taskName
        Ok "scheduled task '$taskName' created and started"
        Info "remove it with: .\install.ps1 -RemoveStartAtLogon   (or in Task Scheduler)"
    } elseif ($hasTask) { Ok "scheduled task '$taskName' is already set up" }
    else { Info 'not set up: the bot runs while a WSL window is open or WSL is otherwise running.' }

    # ------------------------------------------------------------------ done
    Write-Host ''
    Write-Host 'NovaeonTradingAI is installed in WSL (BETA on Windows).' -ForegroundColor Green
    Write-Host ''
    Write-Host "  Open:      $url   (in your Windows browser; the login is shown above)"
    Write-Host "  Helper:    wsl -d $Distro -- ~/NovaeonTradingAI/bin/novaeon status | start | stop | logs | password | update | uninstall"
    Write-Host '  The bot trades only while WSL runs and Windows is awake (sleep and hibernate pause it).'
    Write-Host '  If the page does not open: WSL must forward localhost (the default; see localhostForwarding in .wslconfig).'
    Write-Host ''
    if (-not $Yes) { Start-Process $url }
}

try { Install-NovaeonTradingAI @args } catch { if ($_.Exception.Message -ne 'NovaeonTradingAI install stopped') { throw } }
