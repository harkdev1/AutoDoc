# AutoDoc Public Edition

The Public Edition is a local-first distribution of AutoDoc for safe experimentation.
It is intentionally separate from the developer CLI. Gemini is optional, and
the public edition does not touch `.autodoc/` or perform automatic Git staging.

## Included

- Project-local initialization
- Focus sessions and Markdown session logs
- Basic statistics
- Screenshot capture with Markdown references
- Optional Git commits of already-staged changes

## Quick start

From the project root:

```powershell
python .\autodoc\public_cli.py init
python .\autodoc\public_cli.py start
python .\autodoc\public_cli.py finish
python .\autodoc\public_cli.py status
```

Public state is stored in `.autodoc-public/`. The developer state in `.autodoc/`
is not read or changed.

## Build a Windows executable

Install the build tool in the active virtual environment:

```powershell
python -m pip install pyinstaller
```

Build the executable from the repository root:

```powershell
pyinstaller --onefile --name AutoDoc-Public .\autodoc\public_cli.py
```

The executable is written to `dist\AutoDoc-Public.exe`. Do not package the
developer CLI as the public executable.

## Git safety

The public `git-commit` command never runs `git add`. Stage the intended files
yourself, then commit them explicitly:

```powershell
git add logs\2026-09-22.md
python .\autodoc\public_cli.py git-commit --message "Document public session"
```

Do not distribute `.autodoc-public/`, project logs, screenshots, API keys, or
other local project data as part of a release artifact.