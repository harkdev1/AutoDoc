# AutoDoc MVP

AutoDoc is a Python CLI tool designed to automatically document development work.
It helps track sessions, generate logs, maintain changelogs, update README dashboards, and debug errors using AI.

# Purpose

The objective is to develop an automated engineering journal that captures real-time technical progress. By programmatically logging terminal activity, system states, and visual snapshots, the tool generates a continuous record of infrastructure automation and cloud development. This ensures comprehensive documentation and traceability while allowing the engineer to remain focused on core execution. 

# Why I Built This

This tool is primarily designed for personal productivity and engineering documentation workflows.

# AutoDoc automates:

- Project initialization
- Session tracking (start / finish)
- Engineering log generation
- README dashboard updates
- CHANGELOG updates
- Screenshot logging
- Git automation
- Project statistics tracking
- Test runner for commands
- AI error diagnosis
- Project health check (doctor)

# Installation

Requires:

- Python 3.10+
- pipx (recommended)

Install:

git clone https://github.com/YOUR_USERNAME/autodoc.git
cd autodoc
pipx install .

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

# Example Workflow

cd your-project
autodoc init
autodoc start
# work on project (ex: 2 hours)
autodoc finish
git add .
git commit -m "Project progress"
git push

AutoDoc will generate logs, upate README dashboards, maintain changelogs and track project statistics.

# Project Structure Example

project/
├── .autodoc/
├── logs/
├── screenshots/
├── README.md
├── CHANGELOG.md

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

# Disclaimer

This tool is a personal developer productivity and documentation tool. It is not production software and is not optimized for commercial use.

It is primarily intended for personal engineering workflows, documentation automation, and portfolio development.