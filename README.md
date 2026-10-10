# AutoDoc

> **Project status:** See [project-status.md](project-status.md) for the live status and journey, or the [short](docs/project-complete-short.md) and [long](docs/project-complete-long.md) project summaries.

## Status: In progress

## Latest session – 2026-10-10
Today's work improved AutoDoc's project-documentation workflow. `finish` now records the latest session details in the README and project-status journal, refreshes the short project snapshot, and appends the long-form history. The README keeps its project summary and status links when those sections update. Project-status updates retain prior sessions. Screenshot summaries prefer significant evidence and explain what each selected image shows.

The project-completion regression tests cover history retention and README session-detail persistence. The three project READMEs and status journals are being standardized around the same current-status and latest-session model.

AutoDoc is an AI-assisted engineering workflow for turning daily technical work into structured, reviewable project documentation.

It helps you:

- start a focused work session
- record project context and screenshots
- capture notes and milestones in daily logs
- ask Gemini for next steps and project guidance
- generate short or long project completion summaries
- keep the project README as a useful landing page

## Why this exists

Most technical work is done quickly, but documentation often lags behind. AutoDoc gives you a lightweight workflow to capture that progress while it is happening instead of trying to reconstruct it later.

## Quick start

```powershell
py -3.14 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
autodoc --help
```

If you already have the virtual environment activated, the normal entry point is:

```powershell
autodoc --help
```

## Core workflow

```powershell
autodoc init
autodoc start
autodoc pause
autodoc screenshot
autodoc finish
autodoc logs
autodoc assist
```

A simple rhythm is:

1. initialize the project
2. start a focus session
3. work in short, meaningful blocks
4. capture screenshots or notes as you go
5. finish the session and log what happened
6. ask AutoDoc Assist what to do next

## Current CLI commands

These are the commands currently exposed by the app:

```text
autodoc assist               Ask AutoDoc Assist for a practical next-step plan.
autodoc demo                 Run the AutoDoc guided showcase.
autodoc doctor               Check AutoDoc project health.
autodoc finish               Finish AutoDoc session and log work.
autodoc init                 Initialize AutoDoc in the current directory.
autodoc log                  Create or append a daily engineering log.
autodoc logs                 List, open, and refine project logs.
autodoc monitor              Capture optional, local-only activity snapshots.
autodoc pause                Pause or resume the active focus session.
autodoc project              Project finish, status, and summary commands.
autodoc propose              Generate an AI implementation proposal for a feature.
autodoc repo                 Create and sync the Git repository for the current project.
autodoc screenshot           Capture one named screenshot and add it to today's log.
autodoc screenshot-workflow Capture screenshots and add Markdown references to logs.
autodoc self-test            Run a quick AutoDoc health and integration test.
autodoc setup                Configure AutoDoc for first use.
autodoc start                Start an AutoDoc focus session.
autodoc stats                Show detailed AutoDoc stats.
autodoc status               Show AutoDoc status.
autodoc test                 Run a test command and analyze output.
autodoc version              Show AutoDoc version.
```

## Project commands

The `project` command is for completion and status summaries:

```powershell
autodoc project complete --format both
```

This creates a short and long project summary and refreshes the README summary toward the top so the repository landing page reads like a project overview instead of a raw backlog dump.

## AutoDoc Assist

The `assist` command is the AI planning layer. It reads project context from the README, recent logs, and screenshot names, then helps answer questions such as:

```powershell
autodoc assist --prompt "What should I do next to finish this project well?"
```

It writes the latest plan to a single file at the project root:

```text
assistant-plan.md
```

Each new prompt overwrites the file so it stays lightweight and easy to iterate with Gemini.

## Features

### Focus sessions

- define a goal and timebox
- capture blockers and dependencies
- review progress at the end of the session
- keep decisions tied to actual effort and dates

### AI-generated documentation

AutoDoc can turn rough notes into structured output such as:

- summary
- tasks completed
- issues encountered
- next steps
- notes

### Logs and evidence

AutoDoc keeps project records in Markdown, including:

- daily engineering logs
- session history
- screenshot references
- proof points for later review

### Project summaries

- short pager for quick status review
- long-form story based on timeline and logs
- README refresh for project landing pages

### Git and repo tools

Support for repo initialization and sync is built in where the workflow needs it.

## Requirements

- Python
- Git
- Gemini API key for the main developer CLI

The public edition provides a safer local-only workflow and does not require the Gemini API in the same way.

## Project structure

```text
AutoDoc/
├── autodoc/              CLI and workflow source
├── logs/                 Daily engineering logs
├── screenshots/          Evidence and proof captures
├── docs/                 Generated summaries and notes
├── .autodoc/             Local project state
├── README.md             GitHub landing page
├── CHANGELOG.md          Project history
├── requirements.txt      Python dependencies
├── setup.py              Packaging metadata
├── pyproject.toml        Modern project config
├── public_edition/       Local-first public edition
└── autodoc-test/         Example project used for validation
```

## Public edition

A local-first public variant is included under the `public_edition` folder for safe experimentation without touching the main project state.

## Status

AutoDoc is currently an active CLI workflow tool with AI-assisted project management, documentation, and evidence capture built around a practical engineering rhythm.

This repository is meant to be easy to use, quick to iterate on, and polished enough for GitHub-first visibility.

See [docs/public-edition.md](docs/public-edition.md) for packaging instructions.
