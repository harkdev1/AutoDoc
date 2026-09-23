# AutoDoc Public Edition

This folder contains the distribution materials for the safe, local-first desktop edition of AutoDoc.

The public application uses the GUI entry point at `../autodoc/public_gui.py` and
the shared local storage helpers at `../autodoc/public_cli.py`.
It does not use the developer CLI, does not require a Gemini API key, and does not
touch `.autodoc/` state or perform automatic Git staging.

## Included Features

- Local project initialization
- Focus sessions
- Markdown session logs
- Basic statistics
- Screenshot capture
- Explicit Git commits for already-staged files
- Gemini-assisted Vibe Code proposals with review and backups
- Standalone manual logs without an active session
- In-app Markdown log viewer
- Two-step GitHub log sync

GitHub sign-in uses the OAuth device flow when a public GitHub OAuth App client
ID is configured. No client secret is placed in the application.

## Requirements

- Windows
- Python 3.10 or newer for source execution
- PowerShell for the build script
- Pillow for screenshot support
- PyInstaller only when building the executable

## Run From Source

From the repository root:

```powershell
python .\autodoc\public_cli.py --help
python .\autodoc\public_cli.py init
python .\autodoc\public_cli.py start
```

Launch the desktop GUI with:

```powershell
python .\autodoc\public_gui.py
```

Public project state is stored in `.autodoc-public/` in the project being documented.

To enable GitHub sign-in during development, set the public OAuth App client ID:

```powershell
$env:AUTODOC_GITHUB_CLIENT_ID = "your-public-client-id"
```

The released executable should be built with the intended public client ID
configured through the release environment.

## Manual Logs and Log Viewer

Use **Manual Log** when you want to record one completed piece of work without
starting a timer or ongoing session. Enter the date, optional start/end times,
title, and notes. Gemini can help summarize the notes, and you approve or edit
the summary before the log is saved.

Use **Logs** to read all Markdown logs inside the app. GitHub is optional and is
not required to view or create local records.

The **Sync to GitHub** action has two confirmations. First it shows the changed
files for review. Then it asks for confirmation before staging only `logs`,
creating a commit, and pushing to the configured remote.

## Vibe Code

Open the **Vibe Code** page, describe the feature, and choose **Ask Gemini**.
The app shows the proposed files before anything changes. Applying a proposal:

1. Creates a timestamped backup under `.autodoc-public/backups/`.
2. Restricts changes to the current project folder.
3. Rejects protected folders and oversized files.
4. Runs Python syntax validation on changed Python files.
5. Rolls back the proposal if validation fails.

Vibe Code does not run shell commands automatically. Review every proposal before
applying it.

## Build The Executable

From the repository root:

```powershell
.\public_edition\build.ps1
```

The script creates `dist\AutoDoc-Public.exe`. It launches the GUI and does not include project logs,
screenshots, `.autodoc/` state, credentials, or other personal data.

## Git Safety

The public edition never runs `git add`. To use its optional commit command:

```powershell
git add logs\2026-09-22.md
python .\autodoc\public_cli.py git-commit --message "Document session"
```

Review staged files before every commit.

## Release Checklist

- Run the public CLI help command.
- Run the build script from a clean checkout.
- Test the executable in a temporary project folder.
- Confirm no API keys or `.autodoc/` data are in the release directory.
- Confirm the executable starts without the developer CLI installed.
- Scan the release archive before sharing it.
