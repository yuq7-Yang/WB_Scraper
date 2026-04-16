# Weibo Bot Quick Launch Design

## Goal

Add a convenient Windows launch path for the local Weibo dashboard so the user can start it by double-clicking, without typing PowerShell commands.

## Scope

- Add a project-local `启动面板.bat` launcher in the repository root.
- Create a desktop shortcut named `微博抓取面板` that points to the launcher.
- Keep the existing application startup command: `python -m weibo_bot.dashboard`.
- Do not change scraper, reply, database, or dashboard behavior.

## Launcher Behavior

The batch file will:

1. Switch to the project root using the batch file's own location.
2. Check that Python is available.
3. Start the existing dashboard module with `python -m weibo_bot.dashboard`.
4. Keep the console window open if startup fails so the user can see the error.

The dashboard already opens `http://127.0.0.1:5000` through `webbrowser.open`, so the launcher does not need to open the browser separately.

## Desktop Shortcut

The shortcut will:

- Live on the current user's desktop.
- Use `启动面板.bat` as the target.
- Use the repository root as the working directory.

## Verification

Verify by:

- Running the batch file once from PowerShell.
- Confirming the dashboard process starts far enough to bind Flask on `127.0.0.1:5000`, or reporting any existing port conflict.
- Confirming the desktop shortcut file exists and points at the launcher.
