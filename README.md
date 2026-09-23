# AutoDoc

AI-assisted engineering documentation and session tracking from the command line.

AutoDoc helps turn day-to-day technical work into structured, searchable project documentation without requiring engineers to stop and manually write everything from scratch.

## Why AutoDoc?

Technical work often gets completed faster than it gets documented.

AutoDoc provides a repeatable workflow for:

- Planning focused engineering sessions
- Tracking time and progress
- Turning rough notes into structured documentation with Gemini
- Capturing terminal test results and diagnosing errors with AI
- Maintaining project logs and statistics
- Automatically recording work in Git

## Features

### Focus Sessions

Start a structured work session with:

- Session goals
- Definition of Done
- Dependencies and blockers
- Technical context
- AI-assisted time estimation
- Timeboxing

### AI-Assisted Documentation

At the end of a session, provide rough notes and AutoDoc uses Gemini to generate structured engineering documentation:

- Summary
- Tasks Completed
- Issues Encountered
- Next Steps
- Notes

If AI generation fails, AutoDoc falls back to manual documentation.

### AI Error Diagnosis

Run a command through AutoDoc's test runner and capture its output.

When an error occurs, AutoDoc can send the error to Gemini for:

- Cause analysis
- Recommended fixes
- Next checks
- Example commands

### Automatic Project Documentation

AutoDoc maintains:

- Daily engineering logs
- CHANGELOG
- Project statistics
- Documentation dashboard
- Session handover notes

### Git Automation

AutoDoc automatically creates Git commits when logging work, helping maintain a historical record of project activity.

## Workflow

```text
Start Session
      ↓
Define Goal & Timebox
      ↓
Perform Technical Work
      ↓
Finish Session
      ↓
Enter Rough Notes
      ↓
Gemini Generates Documentation
      ↓
Update Logs / Stats / Changelog
      ↓
Git Commit
```

## AI Governance

AutoDoc treats AI-generated content as a draft, not authoritative documentation.

AI proposes → Human validates → AutoDoc records

## Commands

```text
autodoc init      Initialize a project
autodoc start     Start a focus session
autodoc finish    Finish a session and generate documentation
autodoc log       Create a quick engineering log
autodoc test      Run a command and analyze errors
autodoc doctor    Check project health
autodoc status    Show project status
autodoc stats     Show detailed statistics
autodoc version   Show AutoDoc version
```

## Requirements

- Python
- Git
- Gemini API key

AutoDoc currently uses Google's Gemini API for AI-assisted documentation and error diagnosis.

## Project Structure

```text
AutoDoc/
├── autodoc/              Application source
├── logs/                 Engineering logs
├── screenshots/          Session evidence
├── docs/                 Generated dashboard
├── .autodoc/             Local project state
├── CHANGELOG.md          Project history
├── README.md             Project documentation
├── requirements.txt      Python dependencies
└── setup.py              Package configuration
```

## Status

AutoDoc is an actively developed MVP.

The current focus is making the existing CLI workflow reliable, presentable, and useful for real engineering work.

## Future Direction

Potential future development includes a more convenient interface, multi-project management, and additional AI-assisted workflows.

The CLI remains the core application and workflow engine.

## Public Edition

AutoDoc Public Edition is a local-first distribution target for experimentation.
It uses a separate `.autodoc-public/` state directory and does not require a
Gemini API key. It never stages files automatically; Git commits require files
to be staged explicitly first.

Run it from a checkout with:

```powershell
python .\autodoc\public_cli.py --help
```

See [docs/public-edition.md](docs/public-edition.md) for packaging instructions.