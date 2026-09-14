# AutoDoc MVP

**CLI-based documentation automation tool** for infrastructure projects.

AutoDoc automates:
- Session tracking
- Documentation generation (via Google Gemini AI)
- CHANGELOG management
- README dashboard with stats
- Git automation
- Screenshot capture

## Quick Start

```bash
# Initialize project
autodoc init my-project
cd my-project

# Start session
autodoc start

# Do your work...

# Finish session (auto-documents everything)
autodoc finish
```

## Commands

| Command | Purpose |
|---------|----------|
| `autodoc init <project>` | Initialize new project |
| `autodoc test` | Runs a test protocol for functionality |
| `autodoc start` | Start work session |
| `autodoc finish` | End session & auto-document |
| `autodoc status` | Show project stats |
| `autodoc stats` | Show detailed stats |
| `autodoc log` | Manual log entry |
| `autodoc version` | Show version |

## Features

✅ Session tracking (duration calculation)  
✅ AI-generated documentation (Google Gemini)  
✅ Daily logs with multi-session support  
✅ CHANGELOG auto-updates  
✅ README dashboard with total hours  
✅ Stats tracking (sessions, days, hours)  
✅ Screenshot capture (macOS)  
✅ Git automation (auto-commit)  

## Setup

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Get Google API Key

Get free key from: https://ai.google.dev/

```bash
export GOOGLE_API_KEY=your_key
```

Or it will prompt you on first use.

## AutoDoc MVP v0.1 Complete ✅

This is a working CLI MVP. Next phases:
- v0.2: Improve dashboard
- v0.3: Advanced analytics
- v0.4: VS Code extension