from datetime import datetime
import os
import click
import subprocess
import json
import time
from pathlib import Path
from google import genai
from google.genai import types

VERSION = "0.1.0"

def estimate_session_time(goal):
    """Use Gemini to estimate realistic time for a goal"""
    try:
        api_key = get_api_key()
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are a project estimation expert. Based on the following goal, provide a realistic time estimate.

Goal: {goal}

Respond with ONLY a number representing minutes (30-480 minutes / 0.5-8 hours). 
For example: "90" or "45" or "120"

Consider:
- Complexity of the task
- Testing and validation time
- Documentation time
- Buffer for unexpected issues (add 20%)

Be realistic, not optimistic."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        # Extract just the number from response
        minutes_str = response.text.strip()
        try:
            estimated_minutes = int(minutes_str)
            return estimated_minutes
        except:
            return None

    except Exception as e:
        return None

def get_api_key():
    """Get API key from environment or config file"""
    # Try environment variable first
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        return api_key
    
    # Try config file as fallback
    config_file = Path.home() / ".autodoc" / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                config = json.load(f)
                if "gemini_api_key" in config:
                    return config["gemini_api_key"]
        except:
            pass
    
    return None

def generate_ai_summary(notes):
    try:
        api_key = get_api_key()

        if not api_key:
            raise Exception("GEMINI_API_KEY not set. Set via: export GEMINI_API_KEY='your_key' or save to ~/.autodoc/config.json")

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an assistant that writes engineering documentation.

Convert the following rough notes into structured documentation.

Return format:

Summary:
Tasks Completed:
Issues Encountered:
Next Steps:
Notes:

Rough Notes:
{notes}
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        return response.text

    except Exception as e:
        click.echo("AI generation failed. Falling back to manual input.")
        click.echo(f"Error: {e}")

        summary = click.prompt("Work Summary")
        tasks = click.prompt("Tasks Completed")
        issues = click.prompt("Issues Encountered", default="None", show_default=False)
        next_steps = click.prompt("Next Steps", default="None", show_default=False)
        notes_extra = click.prompt("Notes", default="", show_default=False)

        return f"""
Summary:
{summary}

Tasks Completed:
{tasks}

Issues Encountered:
{issues}

Next Steps:
{next_steps}

Notes:
{notes_extra}
"""

@click.group()
def cli():
    """AutoDoc - Secure Project Scaffolding & Documentation CLI"""
    pass

@click.command()
def version():
    """Show AutoDoc version"""
    click.echo(f"AutoDoc Version: {VERSION}")

@click.command()
def status():
    """Show project status"""
    stats_file = ".autodoc/stats.json"

    click.echo("AutoDoc Status")
    click.echo(f"Version: {VERSION}")

    if not os.path.exists(stats_file):
        click.echo("No session data yet.")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    total_sessions = stats["total_sessions"]
    total_days = len(stats["days_logged"])
    total_minutes = stats["total_minutes"]
    total_hours = round(total_minutes / 60, 2)
    last_session = stats["last_session"]

    click.echo(f"Total Sessions: {total_sessions}")
    click.echo(f"Total Days Logged: {total_days}")
    click.echo(f"Total Hours: {total_hours}")
    click.echo(f"Last Session: {last_session}")

@click.command()
@click.argument("project_name")
def init(project_name):
    """Initialize a new AutoDoc project"""
    
    base_path = project_name

    folders = [
        "terraform",
        "src",
        "scripts",
        "logs",
        "diagrams",
        "docs",
        "screenshots",
        ".security"
    ]

    # Create project directory
    os.makedirs(base_path, exist_ok=True)

    # Create subfolders
    for folder in folders:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)

    # Create README.md
    readme_content = f"# {project_name}\n\nProject initialized with AutoDoc.\n"
    with open(os.path.join(base_path, "README.md"), "w") as f:
        f.write(readme_content)

    # Create CHANGELOG.md
    with open(os.path.join(base_path, "CHANGELOG.md"), "w") as f:
        f.write("# Changelog\n\n")

    # Create .gitignore
    gitignore_content = """
# Security
*.pem
*.key
*.p12
*.pfx
*.tfstate*
*.tfvars
*.env
.aws/
.azure/
.gcp/
secrets/
.security/

# Python
__pycache__/
*.pyc

# macOS
.DS_Store

# Logs
*.log
"""
    with open(os.path.join(base_path, ".gitignore"), "w") as f:
        f.write(gitignore_content)

    # Initialize git
    os.system(f"cd {project_name} && git init")

    click.echo(f"Project '{project_name}' initialized successfully.")

def update_readme_dashboard():
    stats_file = ".autodoc/stats.json"

    if not os.path.exists(stats_file):
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    total_sessions = stats["total_sessions"]
    total_days = len(stats["days_logged"])
    total_minutes = stats["total_minutes"]
    total_hours = round(total_minutes / 60, 2)
    last_session = stats["last_session"]

    readme_content = f"""# Project Dashboard

## AutoDoc Statistics
Total Sessions: {total_sessions}
Total Days Logged: {total_days}
Total Hours Logged: {total_hours}
Last Session: {last_session}

## Documentation
See logs/ for detailed session logs.
See CHANGELOG.md for project timeline.
"""

    with open("README.md", "w") as f:
        f.write(readme_content)

def update_stats(date_str, duration_minutes=0):
    if not os.path.exists(".autodoc"):
        os.makedirs(".autodoc")

    stats_file = ".autodoc/stats.json"

    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            stats = json.load(f)
    else:
        stats = {
            "total_sessions": 0,
            "days_logged": [],
            "total_minutes": 0
        }

    stats["total_sessions"] += 1
    stats["total_minutes"] += duration_minutes

    if date_str not in stats["days_logged"]:
        stats["days_logged"].append(date_str)

    stats["last_session"] = date_str

    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=4)

@click.command()
def log():
    """Create or append a daily engineering log"""

    if not os.path.exists("logs"):
        click.echo("Error: logs folder not found. Run inside an AutoDoc project.")
        return

    # Get user input
    summary = click.prompt("What did you work on today?")
    tasks = click.prompt("Tasks completed (comma separated)")
    notes = click.prompt("Notes", default="", show_default=False)

    # Time info
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    log_filename = f"logs/{date_str}.md"

    # Create session entry
    session_entry = f"""
---

## Session – {time_str}

### Summary
{summary}

### Tasks Completed
{tasks}

### Notes
{notes}
"""

    # If log file doesn't exist, create header
    if not os.path.exists(log_filename):
        with open(log_filename, "w") as f:
            f.write(f"# Engineering Log – {date_str}\n")
            f.write(session_entry)
    else:
        with open(log_filename, "a") as f:
            f.write(session_entry)

    # Update CHANGELOG
    changelog_entry = f"- {date_str}: {summary}\n"
    with open("CHANGELOG.md", "a") as f:
        f.write(changelog_entry)

    # Update stats
    update_stats(date_str)
    update_readme_dashboard()

    # Git automation
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"AutoDoc log {date_str}"], check=True)
        click.echo("Git commit created.")
    except:
        click.echo("Git commit failed.")

    click.echo(f"Log updated: {log_filename}")

@click.command()
def start():
    """Start an AutoDoc focus session"""
    if not os.path.exists(".autodoc"):
        os.makedirs(".autodoc")

    session_file = ".autodoc/session.json"

    if os.path.exists(session_file):
        click.echo("Session already running.")
        return

    # Show previous session's handover note if it exists
    prev_file = ".autodoc/previous_session.json"
    if os.path.exists(prev_file):
        with open(prev_file, "r") as f:
            prev = json.load(f)
            if prev.get("where_left_off"):
                click.echo("\n📋 From Previous Session:")
                click.echo(f"   {prev['where_left_off']}\n")

    # Focus session entry protocol
    click.echo("═" * 50)
    click.echo("🎯 ENTERING FOCUS MODE")
    click.echo("═" * 50)
    click.echo("\nDefine your intent (press Enter to skip):\n")
    
    goal = click.prompt("Session Goal", default="", show_default=False)
    
    # AI time estimation
    estimated_minutes = None
    if goal:
        click.echo("\n⏱️  Analyzing goal complexity...")
        estimated_minutes = estimate_session_time(goal)
        if estimated_minutes:
            click.echo(f"💡 Estimated time needed: {estimated_minutes} minutes (~{estimated_minutes//60}h {estimated_minutes%60}m)")
    
    definition_of_done = click.prompt("\nDefinition of Done (acceptance criteria)", default="", show_default=False)
    dependencies = click.prompt("Dependencies or blockers", default="", show_default=False)
    tech_context = click.prompt("Technical context (branch, server, tools)?", default="", show_default=False)
    
    # Use AI estimate as default, or 90 minutes if no goal
    default_time = estimated_minutes if estimated_minutes else 90
    timeboxing = click.prompt(f"\nTimeboxing duration (minutes) [suggested: {default_time}]", type=int, default=default_time, show_default=False)

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    session_data = {
        "start_time": start_time,
        "goal": goal,
        "definition_of_done": definition_of_done,
        "dependencies": dependencies,
        "tech_context": tech_context,
        "timeboxing_minutes": timeboxing
    }

    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)

    click.echo("\n" + "═" * 50)
    click.echo(f"✅ FOCUS MODE ACTIVATED")
    click.echo(f"⏱️  Timeline: {timeboxing} minutes")
    if goal:
        click.echo(f"🎯 Goal: {goal[:50]}{'...' if len(goal) > 50 else ''}")
    click.echo("\n📵 Notifications off. Deep work begins now.")
    click.echo("═" * 50 + "\n")

def screenshot_workflow():
    if not os.path.exists("screenshots"):
        os.makedirs("screenshots")

    while True:
        choice = click.prompt("Take screenshot? (y/n)")

        if choice.lower() != "y":
            break

        ready = click.prompt("Prepare screen. Type 1 when ready")

        if ready != "1":
            click.echo("Screenshot cancelled.")
            break

        # Countdown
        for i in range(5, 0, -1):
            click.echo(f"{i}...")
            time.sleep(1)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"screenshots/{timestamp}.png"

        subprocess.run(["screencapture", filename])

        click.echo(f"Screenshot saved: {filename}")

        another = click.prompt("Take another screenshot? (y/n)")
        if another.lower() != "y":
            break

@click.command()
def finish():
    """Finish AutoDoc session and log work"""
    session_file = ".autodoc/session.json"

    if not os.path.exists(session_file):
        click.echo("No active session.")
        return

    with open(session_file, "r") as f:
        session = json.load(f)

    start_time_str = session["start_time"]
    start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
    end_time = datetime.now()

    duration = end_time - start_time
    duration_minutes = int(duration.total_seconds() / 60)

    # Display goal and achievement (only if goal was set)
    click.echo("\n📊 Session Review\n")
    
    goal = session.get('goal', '')
    if goal:
        click.echo(f"Goal: {goal}")
        click.echo(f"Definition of Done: {session.get('definition_of_done', 'N/A')}")
        goal_achieved = click.prompt("\nDid you achieve your goal? (y/n)", default="y", show_default=False)
        if goal_achieved.lower() == "y":
            click.echo("🎉 Great work!")
        else:
            click.echo("🤔 That's okay. Next session can pick this up.")
    else:
        goal_achieved = ""
        click.echo("(No goal was set for this session)")
    
    timeboxed_minutes = session.get('timeboxing_minutes', duration_minutes)
    click.echo(f"Time: {duration_minutes} minutes (planned: {timeboxed_minutes} minutes)")

    # Ask for rough notes instead of full summary
    rough_notes = click.prompt("What did you work on? (rough notes)")
    ai_output = generate_ai_summary(rough_notes)

    notes = click.prompt("Extra notes", default="", show_default=False)
    where_left_off = click.prompt("Where did you leave off? (one sentence for next session)", default="", show_default=False)

    date_str = end_time.strftime("%Y-%m-%d")
    log_filename = f"logs/{date_str}.md"

    # Build session entry with goal and context (show N/A for empty fields)
    goal_display = session.get('goal') or 'N/A'
    def_of_done_display = session.get('definition_of_done') or 'N/A'
    deps_display = session.get('dependencies') or 'N/A'
    
    goal_section = f"\n### Goal\n{goal_display}\n" if goal else ""
    def_of_done_section = f"\n### Definition of Done\n{def_of_done_display}\n" if goal else ""
    deps_section = f"\n### Dependencies/Blockers\n{deps_display}\n" if goal else ""
    achieved_section = f"\n### Goal Achieved\n{'✅ Yes' if goal_achieved and goal_achieved.lower() == 'y' else '❌ No'}\n" if goal_achieved else ""

    session_entry = f"""
---

## Session – {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}{goal_section}{def_of_done_section}{achieved_section}
{ai_output}

### Duration
{duration_minutes} minutes (Planned: {timeboxed_minutes} minutes)

### Notes
{notes}
"""

    # Create or append log file
    if not os.path.exists(log_filename):
        with open(log_filename, "w") as f:
            f.write(f"# Engineering Log – {date_str}\n")
            f.write(session_entry)
    else:
        with open(log_filename, "a") as f:
            f.write(session_entry)

    # Update CHANGELOG
    with open("CHANGELOG.md", "a") as f:
        f.write(f"- {date_str}: {rough_notes}\n")

    # Update stats + README
    update_stats(date_str, duration_minutes)
    update_readme_dashboard()

    # Screenshot workflow
    screenshot_workflow()

    # Git automation
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"AutoDoc session {date_str}"], check=True)
    except:
        click.echo("Git commit failed.")

    # Save handover note for next session
    prev_file = ".autodoc/previous_session.json"
    with open(prev_file, "w") as f:
        json.dump({"where_left_off": where_left_off}, f, indent=2)

    # Remove session file
    os.remove(session_file)

    click.echo("\n✅ Session logged successfully. Handover note saved.")

@click.command()
def stats():
    """Show detailed AutoDoc stats"""
    stats_file = ".autodoc/stats.json"

    if not os.path.exists(stats_file):
        click.echo("No stats available.")
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    total_sessions = stats["total_sessions"]
    total_days = len(stats["days_logged"])
    total_minutes = stats["total_minutes"]
    total_hours = round(total_minutes / 60, 2)

    click.echo("AutoDoc Statistics")
    click.echo(f"Total Sessions: {total_sessions}")
    click.echo(f"Total Days Logged: {total_days}")
    click.echo(f"Total Minutes: {total_minutes}")
    click.echo(f"Total Hours: {total_hours}")

cli.add_command(version)
cli.add_command(status)
cli.add_command(init)
cli.add_command(log)
cli.add_command(start)
cli.add_command(finish)
cli.add_command(stats)

if __name__ == "__main__":
    cli()