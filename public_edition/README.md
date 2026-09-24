# AutoDoc Public Edition

This folder contains the distribution materials for the safe, local-first desktop edition of AutoDoc.

The public application uses the GUI entry point at `../autodoc/public_gui.py` and
the shared local storage helpers at `../autodoc/public_cli.py`.
It does not use the developer CLI, does not require a Gemini API key, and does not
touch `.autodoc/` state or perform automatic Git staging.

## Download

Windows users can download the latest app here:

[Download AutoDoc-Public.exe](https://github.com/harkdev1/AutoDoc-Public-Edition/releases/latest)

Download the `.exe`, place it somewhere you can find it, and double-click it.
No Python installation is required for the executable release.

## First Launch

AutoDoc opens with a short welcome screen. Nothing is required to start:

1. Choose whether to connect GitHub now or later.
2. Choose Gemini, no AI, or another provider later.
3. Select **Start locally**.
4. Choose a project folder when prompted.

Your local records are stored in that project folder under `.autodoc-public/`.
Your existing developer AutoDoc state is not used.

## What Each Area Does

- **Dashboard**: See sessions, minutes, days logged, and the current project.
- **Focus Session**: Start a timer-based work session, capture optional screenshots, and finish it into a Markdown log.
- **Work Shift**: Clock in for a workday, keep a running notepad, and clock out into an AI-reviewed journal entry.
- **Project Hub**: Create or open projects, see the daily focus, and sync the full project to GitHub after review.
- **Manual Log**: Record one piece of work without starting a session or timer.
- **Logs**: Read every local Markdown log inside the app.
- **Vibe Code**: Ask Gemini for a proposed feature, then use one approved **Apply and test** action. AutoDoc backs up the project and validates changed Python and JSON files immediately.
- **Settings**: Configure Gemini, GitHub, and manual update checks.

## Manual Log

Use **Manual Log** when the work already happened or was done outside AutoDoc.
Enter a date, optional times, a title, and your notes. Gemini can summarize the
notes, but you edit and approve the result before it is saved.

## Sessions

Use **Focus Session** when you want a live timer:

1. Enter a goal and definition of done.
2. Choose a planned duration.
3. Start the session.
4. Watch the live timer in the top bar.
5. Finish the session and review the generated entry.

Screenshots are manual and can capture all displays or one selected monitor.

Focus sessions also offer explicit evidence capture, which saves a screenshot every
30 seconds only after you start it. AutoDoc never records in the background.

Use **Work Shift** when you want a broader workday journal. Clock in, paste or
type notes throughout the day, then clock out to review an AI-generated journal
before saving it.

## Continue from notes

Use **Continue** for notes copied from a notepad, ticket, chat, or handoff. AutoDoc
looks at the latest local journal entries, identifies the last known stopping point,
and proposes a next step. AI output is labeled for review, and when AI is unavailable
the app uses a cautious local fallback that does not claim unverified work was done.

## AI and Privacy

AI is optional. Without a Gemini key, AutoDoc still supports local sessions,
manual logs, Markdown viewing, screenshots, and statistics. When AI is enabled,
the relevant notes or project files are sent to the provider to produce a result.
Review AI output before saving or applying it.

## GitHub

GitHub is optional. The app can use GitHub device sign-in when a public OAuth
client ID is configured. Local logs remain usable without GitHub.

The **Sync to GitHub** action uses two confirmations: first review changed files,
then confirm staging Markdown logs, committing, and pushing. It does not silently
sync the entire project. A timestamped backup of the journal, statistics, and
active shift state is created under `.autodoc-public/backups/` before staging.

The **Project menu** also offers full-project sync. This uses the same review and
confirmation steps, but stages all reviewed project changes instead of only logs.

## Vibe Code Safety

Vibe Code creates a backup before applying changes, blocks protected folders,
restricts edits to the selected project, validates changed Python files, and
rolls back when validation fails. It does not run shell commands automatically.

## Updates

Open **Settings** and choose **Check for updates**, or enable the optional launch
alert. For a packaged release, AutoDoc can download the `AutoDoc-Public.exe`
asset from GitHub, replace the running executable after approval, and restart.
Updates are never installed without approval.

## Publishing releases

Build the first bootstrap executable with:

```powershell
.\public_edition\build.ps1 -Version 0.1.0-public
```

Publish `dist\AutoDoc-Public.exe` as a GitHub release asset with the exact name
`AutoDoc-Public.exe`. For every later update, bump the version and publish the
new executable and its generated `AutoDoc-Public.exe.sha256` checksum under the
same asset name:

```powershell
.\public_edition\build.ps1 -Version 0.2.0-public
```

The installed app checks the latest release, asks the user, downloads the asset,
and replaces itself. Keep the release asset name stable and use increasing
semantic versions so the app can recognize newer releases.

## Troubleshooting

- If the app opens in the wrong folder, use **Choose project** in the sidebar.
- If Gemini is unavailable, continue locally or add your key in **Settings**.
- If GitHub sync fails, confirm the folder is a Git repository with a configured remote.
- If Windows warns about the executable, verify the SHA-256 value shown on the release page.

## Source Installation

Developers can run the source version with Python 3.10 or newer:

```powershell
python -m pip install -r .\public_edition\requirements.txt
python -m autodoc.public_gui
```

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
python -m autodoc.public_gui
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
