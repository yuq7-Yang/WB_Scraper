# Weibo Bot Quick Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a double-click Windows startup path for the existing Weibo dashboard.

**Architecture:** Add a root-level batch launcher that changes into the repository directory, checks Python, and runs `python -m weibo_bot.dashboard`. Create a current-user desktop shortcut that targets the launcher and uses the repository root as its working directory.

**Tech Stack:** Windows batch, PowerShell COM shortcut creation, existing Python Flask app.

---

### Task 1: Project Launcher

**Files:**
- Create: `启动面板.bat`

- [ ] **Step 1: Create the launcher file**

Create `启动面板.bat` in the repository root with this exact content:

```bat
@echo off
setlocal

pushd "%~dp0" || (
    echo Failed to enter the project directory.
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python or make sure the python command is available.
    echo.
    pause
    exit /b 1
)

echo Starting Weibo dashboard...
echo Project directory: %CD%
echo.

python -m weibo_bot.dashboard
set "EXIT_CODE=%ERRORLEVEL%"

popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Dashboard startup failed. Exit code: %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
```

- [ ] **Step 2: Verify the launcher syntax can be read**

Run: `Get-Content -LiteralPath '.\启动面板.bat'`

Expected: The command prints the exact batch content from Step 1.

### Task 2: Desktop Shortcut

**Files:**
- Create outside repo: current user's desktop `微博抓取面板.lnk`

- [ ] **Step 1: Create the desktop shortcut**

Run this PowerShell command from the repository root:

```powershell
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktop '微博抓取面板.lnk'
$target = Join-Path (Get-Location) '启动面板.bat'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = (Get-Location).Path
$shortcut.Description = '启动微博抓取面板'
$shortcut.Save()
```

- [ ] **Step 2: Verify the shortcut points at the launcher**

Run:

```powershell
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktop '微博抓取面板.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
[pscustomobject]@{
  Exists = Test-Path -LiteralPath $shortcutPath
  TargetPath = $shortcut.TargetPath
  WorkingDirectory = $shortcut.WorkingDirectory
}
```

Expected:

```text
Exists           : True
TargetPath       : D:\美甲美睫\wb_scraper\启动面板.bat
WorkingDirectory : D:\美甲美睫\wb_scraper
```

### Task 3: Startup Verification

**Files:**
- No file changes.

- [ ] **Step 1: Check whether port 5000 is already in use**

Run:

```powershell
Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 5000 -ErrorAction SilentlyContinue
```

Expected: No output before launching, unless another copy of the dashboard is already running.

- [ ] **Step 2: Start the launcher in a background process**

Run:

```powershell
$process = Start-Process -FilePath '.\启动面板.bat' -WorkingDirectory (Get-Location) -PassThru
Start-Sleep -Seconds 5
$process.Id
```

Expected: A process id is printed.

- [ ] **Step 3: Verify Flask is reachable**

Run:

```powershell
try {
  $response = Invoke-WebRequest -Uri 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 5
  $response.StatusCode
} catch {
  $_.Exception.Message
}
```

Expected: `200`, or a clear error message that can be reported if startup fails.

- [ ] **Step 4: Stop the verification process if it is still running**

Run:

```powershell
Get-Process -Id $process.Id -ErrorAction SilentlyContinue | Stop-Process
```

Expected: The test-launched command window closes, or there is no output if it already exited.
