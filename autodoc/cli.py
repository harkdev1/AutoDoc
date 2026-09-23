from datetime import datetime
from io import BytesIO
import os
import click
import subprocess
import json
import re
import shutil
import sys
import time
import subprocess
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image, ImageGrab, ImageOps

VERSION = "0.1.0"
MONITOR_STATE_FILE = Path(".autodoc") / "screen_monitor.json"
MONITOR_STOP_FILE = Path(".autodoc") / "screen_monitor.stop"
MONITOR_MAX_FRAMES = 240
REPOSITORY_CONFIG_FILE = Path(".autodoc") / "repository.json"

def estimate_session_time(goal):
    """Use Gemini to estimate realistic time for a goal"""
    try:
        api_key = get_api_key()
        if not api_key:
            return None

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are the session planning assistant for AutoDoc, an engineering
focus-session and documentation tool.

Your job is to estimate how long ONE focused work session should take
for the following goal.

Goal:
{goal}

Rules:
- A single focus session must be between 30 and 240 minutes.
- NEVER estimate more than 240 minutes.
- Prefer focused sessions of 45-120 minutes when practical.
- If the goal is too large to reasonably complete in one focused session,
  estimate the time for the FIRST meaningful chunk of work rather than
  estimating the entire project.
- When a goal is too large, recommend splitting it across multiple
  sessions.
- Include reasonable time for testing and validation.
- Do not include long-term project planning, future sessions, or unrelated
  work in the estimate.
- Be realistic rather than optimistic.

Return ONLY the estimated number of minutes for the recommended session.
Do not include words, explanations, ranges, or units.

Examples:
45
60
90
120
180
240
"""

        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message(prompt)

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


def load_repository_config():
    if not REPOSITORY_CONFIG_FILE.exists():
        return {}
    try:
        with REPOSITORY_CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {}


def save_repository_config(config):
    REPOSITORY_CONFIG_FILE.parent.mkdir(exist_ok=True)
    with REPOSITORY_CONFIG_FILE.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2)


def push_repository_if_enabled():
    config = load_repository_config()
    if not config.get("auto_sync"):
        return False
    try:
        subprocess.run(["git", "push"], check=True)
        click.echo("GitHub sync complete.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        click.echo(f"Automatic GitHub sync failed: {error}")
        return False


def save_activity_sheet(frames, started_at, stopped_at):
    """Save one contact sheet from in-memory snapshots; never writes a video."""
    if not frames:
        return None

    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    timestamp = stopped_at.strftime("%Y-%m-%d_%H%M%S")
    filename = screenshots_dir / f"activity_{timestamp}.jpg"
    thumbnails = []
    for frame in frames:
        with Image.open(BytesIO(frame)) as image:
            thumbnails.append(image.convert("RGB"))

    columns = 4
    tile_width, tile_height = 320, 200
    rows = (len(thumbnails) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_width, rows * tile_height), "white")
    for index, thumbnail in enumerate(thumbnails):
        tile = ImageOps.contain(thumbnail, (tile_width - 12, tile_height - 32))
        left = (index % columns) * tile_width + (tile_width - tile.width) // 2
        top = (index // columns) * tile_height + 8
        sheet.paste(tile, (left, top))

    sheet.save(filename, "JPEG", quality=78, optimize=True)
    date_str = stopped_at.strftime("%Y-%m-%d")
    log_filename = Path("logs") / f"{date_str}.md"
    Path("logs").mkdir(exist_ok=True)
    if not log_filename.exists():
        log_filename.write_text(f"# Engineering Log – {date_str}\n", encoding="utf-8")
    markdown_path = f"../screenshots/{filename.name}"
    entry = (
        f"\n## Passive activity capture – {started_at.strftime('%H:%M')} to {stopped_at.strftime('%H:%M')}\n"
        f"![Passive activity capture]({markdown_path})\n"
        f"Snapshots: {len(frames)} (stored as one contact sheet; no video saved)\n"
    )
    with log_filename.open("a", encoding="utf-8") as log_file:
        log_file.write(entry)
    return filename


def monitor_worker(interval):
    started_at = datetime.now()
    frames = []
    MONITOR_STOP_FILE.unlink(missing_ok=True)
    while not MONITOR_STOP_FILE.exists() and len(frames) < MONITOR_MAX_FRAMES:
        try:
            with ImageGrab.grab() as screenshot:
                screenshot.thumbnail((640, 400))
                buffer = BytesIO()
                screenshot.convert("RGB").save(buffer, "JPEG", quality=60, optimize=True)
                frames.append(buffer.getvalue())
        except Exception:
            pass
        if not MONITOR_STOP_FILE.exists():
            time.sleep(interval)

    stopped_at = datetime.now()
    save_activity_sheet(frames, started_at, stopped_at)
    MONITOR_STOP_FILE.unlink(missing_ok=True)
    MONITOR_STATE_FILE.unlink(missing_ok=True)


def launch_monitor_worker(interval):
    MONITOR_STATE_FILE.parent.mkdir(exist_ok=True)
    MONITOR_STOP_FILE.unlink(missing_ok=True)
    MONITOR_STATE_FILE.write_text(
        json.dumps({"started_at": datetime.now().isoformat(timespec="seconds"), "interval": interval}),
        encoding="utf-8",
    )
    log_path = MONITOR_STATE_FILE.with_suffix(".log")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "monitor", "worker", "--interval", str(interval)],
        stdin=subprocess.DEVNULL,
        stdout=log_path.open("a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        creationflags=creation_flags,
        close_fds=True,
    )


@click.group()
def monitor():
    """Capture optional, local-only activity snapshots during focused work."""


@monitor.command("start")
@click.option("--interval", type=click.IntRange(5, 3600), default=30, show_default=True)
def monitor_start(interval):
    """Start background snapshots; stop with `autodoc monitor stop`."""
    if MONITOR_STATE_FILE.exists():
        raise click.ClickException("Screen activity capture is already running.")

    click.confirm(
        "This captures your screen every interval seconds and may include private information. "
        "Only one contact sheet is saved when stopped; no video is saved. Continue?",
        abort=True,
    )
    launch_monitor_worker(interval)
    click.echo(f"Passive screen capture started (every {interval}s). Stop with: autodoc monitor stop")


@monitor.command("stop")
def monitor_stop():
    """Stop capture and save one contact sheet to the daily log."""
    if not MONITOR_STATE_FILE.exists():
        raise click.ClickException("Screen activity capture is not running.")
    MONITOR_STOP_FILE.write_text("stop", encoding="utf-8")
    click.echo("Stopping capture. Saving one activity contact sheet...")


@monitor.command("status")
def monitor_status():
    """Show whether background capture is active."""
    if MONITOR_STATE_FILE.exists():
        click.echo("Screen activity capture: ON")
    else:
        click.echo("Screen activity capture: OFF")


@monitor.command("worker", hidden=True)
@click.option("--interval", type=click.IntRange(5, 3600), required=True)
def monitor_worker_command(interval):
    """Run the background capture worker."""
    monitor_worker(interval)

@click.command()
def setup():
    """Configure AutoDoc for first use"""

    click.echo("\nAutoDoc Setup\n")
    click.echo("Configure your Gemini API connection.\n")

    api_key = click.prompt(
        "Gemini API Key",
        hide_input=True
    )

    if not api_key.strip():
        click.echo("Setup cancelled: API key cannot be empty.")
        return

    click.echo("\nValidating Gemini API...")

    try:
        client = genai.Client(api_key=api_key.strip())
        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message("Reply with exactly: PASS")

        if "PASS" not in response.text.upper():
            click.echo("API validation failed.")
            return

    except Exception as e:
        click.echo(f"API validation failed: {e}")
        return

    config_dir = Path.home() / ".autodoc"
    config_dir.mkdir(exist_ok=True)

    config_file = config_dir / "config.json"

    with open(config_file, "w") as f:
        json.dump(
            {"gemini_api_key": api_key.strip()},
            f,
            indent=2
        )

    click.echo("✓ Gemini API validated")
    click.echo("✓ Configuration saved")
    click.echo("\nAutoDoc is ready.\n")

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

        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message(prompt)

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

def generate_feature_proposal(feature_request):
    """Generate an AI implementation proposal for a requested feature."""
    try:
        api_key = get_api_key()

        if not api_key:
            raise Exception("Gemini API key not configured.")

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are a senior Python software engineer reviewing the AutoDoc project.

AutoDoc is a Python Click CLI tool located in autodoc/cli.py.
It already uses Pillow for screenshot capture and Gemini for AI features.

Feature Request:
{feature_request}

Existing Project Context:
- Main implementation file: autodoc/cli.py
- CLI framework: Click
- Screenshot library: Pillow
- AI library: google-genai
- Existing workflow: init, start, test, finish, doctor, self-test, status
- Documentation is stored in Markdown logs
- AI-generated output requires human peer review
- Do not introduce fictional classes, directories, or frameworks

Return the following sections:

1. Feature Summary
2. Existing AutoDoc Components Relevant to This Feature
3. Recommended Implementation
4. Specific Functions Likely to Change
5. Implementation Steps
6. Testing Plan
7. Risks and Edge Cases
8. Human Review Checklist

Rules:
- Ground recommendations in the provided project context.
- Do not assume SessionManager or nonexistent directories.
- Prefer modifying existing functionality over adding unnecessary architecture.
- Do not modify files.
- Clearly identify anything that requires inspecting the actual source code.
- Keep the proposal practical for AutoDoc v0.1.
        """

        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message(prompt)

        return response.text

    except Exception as e:
        click.echo("Feature proposal generation failed.")
        click.echo(f"Error: {e}")
        return None

def review_ai_output(ai_output):
    """Allow the user to review and record AI-generated content"""

    click.echo("\n" + "=" * 50)
    click.echo("AI-GENERATED CONTENT")
    click.echo("=" * 50)
    click.echo(ai_output)
    click.echo("=" * 50)

    approved = click.confirm(
        "\nApprove this AI-generated content?",
        default=True
    )

    reviewer_notes = click.prompt(
        "Reviewer notes",
        default="",
        show_default=False
    )

    review = {
        "status": "approved" if approved else "rejected",
        "reviewer": "human",
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "notes": reviewer_notes
    }

    return review

@click.group()
def cli():
    """
AutoDoc – Engineering Documentation & Session Tracking CLI

Commands:
  init     Initialize AutoDoc project
  start    Start focus session
  finish   Finish session and generate logs
  log      Quick engineering log
  stats    Show statistics
  status   Show project status
  test     Run test command and diagnose errors
  version  Show AutoDoc version
"""
    pass


@click.group()
def repo():
    """Create and sync the Git repository for the current project."""


@repo.command("create")
@click.option("--name", default=None, help="GitHub repository name; defaults to the folder name.")
@click.option("--private/--public", default=True, help="Set the GitHub repository visibility.")
@click.option("--auto-sync/--no-auto-sync", default=True, show_default=True)
def repo_create(name, private, auto_sync):
    """Create a local repository and publish it to GitHub with one setup flow."""
    init.callback()
    if not Path(".git").exists():
        subprocess.run(["git", "init"], check=True)
    subprocess.run(["git", "branch", "-M", "main"], check=False)

    repository_name = name or Path.cwd().name
    visibility = "private" if private else "public"
    click.confirm(
        f"Create GitHub repository '{repository_name}' as {visibility} and enable automatic sync?",
        abort=True,
    )
    subprocess.run(["git", "add", "."], check=True)
    commit = subprocess.run(
        ["git", "commit", "-m", "Initialize AutoDoc project"],
        check=False,
        capture_output=True,
        text=True,
    )
    if commit.returncode not in (0, 1):
        raise click.ClickException(commit.stderr.strip() or "Initial Git commit failed.")

    if not shutil.which("gh"):
        save_repository_config({"name": repository_name, "visibility": visibility, "auto_sync": False})
        raise click.ClickException("GitHub CLI (gh) is not installed. The local repository was created; install gh and rerun repo create.")

    command = ["gh", "repo", "create", repository_name, "--source", ".", "--remote", "origin", "--push"]
    command.append(f"--{visibility}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise click.ClickException(f"GitHub repository creation failed with exit code {error.returncode}.") from error

    save_repository_config({"name": repository_name, "visibility": visibility, "auto_sync": auto_sync})
    click.echo(f"Repository ready: {repository_name}")
    click.echo(f"Automatic sync: {'ON' if auto_sync else 'OFF'}")


@repo.command("status")
def repo_status():
    """Show repository and automatic-sync settings."""
    config = load_repository_config()
    if not Path(".git").exists():
        click.echo("Git repository: not initialized")
        return
    click.echo("Git repository: initialized")
    click.echo(f"Remote: {config.get('name', 'not configured')}")
    click.echo(f"Automatic sync: {'ON' if config.get('auto_sync') else 'OFF'}")


@repo.command("sync")
def repo_sync():
    """Push the current committed branch to its configured remote."""
    if not Path(".git").exists():
        raise click.ClickException("Git repository is not initialized. Run autodoc repo create first.")
    if not subprocess.run(["git", "remote", "get-url", "origin"], check=False, capture_output=True).stdout:
        raise click.ClickException("No origin remote is configured.")
    try:
        subprocess.run(["git", "push"], check=True)
        click.echo("GitHub sync complete.")
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise click.ClickException(f"GitHub sync failed: {error}") from error

@click.command()
def propose():
    """Generate an AI implementation proposal for a feature."""
    feature_request = click.prompt("What feature do you want to build?")

    click.echo("\nGenerating feature proposal...\n")

    proposal = generate_feature_proposal(feature_request)

    if proposal:
        click.echo("\n" + "=" * 60)
        click.echo("AI FEATURE PROPOSAL")
        click.echo("=" * 60)
        click.echo(proposal)
        click.echo("\nAI output requires human review before implementation.")

@click.command()
def version():
    """Show AutoDoc version"""
    click.echo(f"AutoDoc Version: {VERSION}")

@click.command()
def status():
    """Show AutoDoc status"""
    
    click.echo("AutoDoc Status")
    click.echo(f"Version: {VERSION}")

    stats_file = ".autodoc/stats.json"

    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            stats = json.load(f)
    else:
        stats = {}

    total_minutes = stats.get("total_minutes", 0)
    total_sessions = stats.get("total_sessions", 0)
    total_days = stats.get("total_days", 0)

    click.echo(f"Total Sessions: {total_sessions}")
    click.echo(f"Total Minutes: {total_minutes}")
    click.echo(f"Total Days Logged: {total_days}")

@click.command()
def init():
    """Initialize AutoDoc in the current directory"""

    click.echo("Initializing AutoDoc in current directory...")

    # Create folders
    os.makedirs("logs", exist_ok=True)
    os.makedirs("screenshots", exist_ok=True)
    os.makedirs(".autodoc", exist_ok=True)
    os.makedirs(".autodoc/tests", exist_ok=True)

    # Create stats.json
    stats_file = ".autodoc/stats.json"
    if not os.path.exists(stats_file):
        stats = {
            "total_sessions": 0,
            "days_logged": [],
            "total_minutes": 0,
            "last_session": "N/A"
        }
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=4)

    # Create README
    if not os.path.exists("README.md"):
        with open("README.md", "w", encoding="utf-8") as f:
            f.write("# Project\n\nInitialized with AutoDoc.\n")

    # Create dashboard directory
    os.makedirs("docs", exist_ok=True)

    # Create CHANGELOG
    if not os.path.exists("CHANGELOG.md"):
        with open("CHANGELOG.md", "w") as f:
            f.write("# Changelog\n\n")

    click.echo("AutoDoc initialized successfully.")

def update_readme_dashboard():
    stats_file = ".autodoc/stats.json"

    if not os.path.exists(stats_file):
        return

    with open(stats_file, "r") as f:
        stats = json.load(f)

    total_sessions = stats.get("total_sessions", 0)
    total_days = len(stats.get("days_logged", []))
    total_minutes = stats.get("total_minutes", 0)
    total_hours = round(total_minutes / 60, 2)
    last_session = stats.get("last_session", "N/A")

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

    os.makedirs("docs", exist_ok=True)

    with open("docs/dashboard.md", "w", encoding="utf-8") as f:
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
            "total_minutes": 0,
            "last_session": "N/A"
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
        with open(log_filename, "w", encoding="utf-8") as f:
            f.write(f"# Engineering Log – {date_str}\n")
            f.write(session_entry)
    else:
        with open(log_filename, "a", encoding="utf-8") as f:
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
def test():
    """Run a test command and analyze output"""
    
    click.echo("\n🧪 AutoDoc Test Runner\n")

    command = click.prompt("Enter command to run")

    click.echo(f"\nRunning: {command}\n")

    try:
        result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True
    )

        output = result.stdout
        error = result.stderr

        if output:
            click.echo("Output:")
            click.echo(output)

        if error:
            click.echo("\nError:")
            click.echo(error)

            # Send error to AI for diagnosis
            click.echo("\nAnalyzing error with AI...\n")
            diagnosis = diagnose_error(error)
            click.echo("AI Diagnosis:")
            click.echo(diagnosis)

        # Save test log
        if not os.path.exists(".autodoc/tests"):
            os.makedirs(".autodoc/tests")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        test_file = f".autodoc/tests/test_{timestamp}.md"

        with open(test_file, "w") as f:
            f.write(f"# AutoDoc Test Run – {timestamp}\n\n")
            f.write(f"## Command\n{command}\n\n")

            f.write("## Output\n")
            f.write(output if output else "None\n")

            f.write("\n## Error\n")
            f.write(error if error else "None\n")

            if error:
                f.write("\n## AI Diagnosis\n")
                f.write(diagnosis)

        click.echo(f"\nTest log saved: {test_file}")

    except Exception as e:
        click.echo(f"Test failed: {e}")
    
def diagnose_error(error_text):
    """Use AI to diagnose terminal errors"""
    try:
        api_key = get_api_key()
        if not api_key:
            return "No API key configured for AI diagnosis."

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are a senior DevOps engineer.

Analyze the following terminal error and explain:

1. What caused the error
2. How to fix it
3. What to check next
4. Example command to fix it (if applicable)

Error:
{error_text}
"""

        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message(prompt)

        return response.text

    except Exception as e:
        return f"AI diagnosis failed: {e}"

@click.command()
def doctor():
    """Check AutoDoc project health"""

    click.echo("\n🩺 AutoDoc Doctor Report")
    click.echo("-" * 40)

    # Check AutoDoc folder
    if os.path.exists(".autodoc"):
        click.echo("AutoDoc initialized: OK")
    else:
        click.echo("AutoDoc initialized: Missing (.autodoc folder)")

        fix = click.confirm(
            "Doctor can create the missing .autodoc folder. Apply correction?",
            default=True
        )

        if fix:
            os.makedirs(".autodoc", exist_ok=True)
            click.echo("Correction applied: .autodoc folder created.")

            if os.path.exists(".autodoc"):
                click.echo("Verification: .autodoc folder is now OK.")
            else:
                click.echo("Verification failed: .autodoc folder is still missing.")

    # Check logs folder
    if os.path.exists("logs"):
        click.echo("Logs folder: OK")
    else:
        click.echo("Logs folder: Missing")

    # Check README
    if os.path.exists("README.md"):
        click.echo("README.md: OK")
    else:
        click.echo("README.md: Missing")

    # Check CHANGELOG
    if os.path.exists("CHANGELOG.md"):
        click.echo("CHANGELOG.md: OK")
    else:
        click.echo("CHANGELOG.md: Missing")

    # Check Git repo
    if os.path.exists(".git"):
        click.echo("Git repository: OK")
    else:
        click.echo("Git repository: Not initialized")

    # Check stats file
    if os.path.exists(".autodoc/stats.json"):
        click.echo("Stats file: OK")
    else:
        click.echo("Stats file: Missing")

    # Check Gemini API
    api_key = get_api_key()
    if api_key:
        click.echo("Gemini API: OK")
    else:
        click.echo("Gemini API: Not configured")

    # Check active session
    if os.path.exists(".autodoc/session.json"):
        click.echo("Active session: Yes")
    else:
        click.echo("Active session: No")

    click.echo("-" * 40)
    click.echo("Doctor check complete.\n")

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
    passive_capture = click.confirm(
        "Enable passive screen snapshots while you work? (no video saved)",
        default=False,
    )

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    session_data = {
        "start_time": start_time,
        "goal": goal,
        "definition_of_done": definition_of_done,
        "dependencies": dependencies,
        "tech_context": tech_context,
        "timeboxing_minutes": timeboxing,
        "passive_capture": passive_capture,
        "passive_interval": 30,
        "paused_seconds": 0,
    }

    with open(session_file, "w") as f:
        json.dump(session_data, f, indent=2)

    if passive_capture:
        launch_monitor_worker(30)

    click.echo("\n" + "═" * 50)
    click.echo(f"✅ FOCUS MODE ACTIVATED")
    click.echo(f"⏱️  Timeline: {timeboxing} minutes")
    if goal:
        click.echo(f"🎯 Goal: {goal[:50]}{'...' if len(goal) > 50 else ''}")
    click.echo("\n📵 Notifications off. Deep work begins now.")
    click.echo("═" * 50 + "\n")


@click.command()
def pause():
    """Pause or resume the active focus session and passive capture."""
    session_file = ".autodoc/session.json"
    if not os.path.exists(session_file):
        click.echo("No active session.")
        return

    with open(session_file, "r") as f:
        session = json.load(f)

    now = datetime.now()
    if session.get("paused_at"):
        paused_at = datetime.strptime(session["paused_at"], "%Y-%m-%d %H:%M:%S")
        session["paused_seconds"] = session.get("paused_seconds", 0) + int((now - paused_at).total_seconds())
        session.pop("paused_at", None)
        if session.get("passive_capture"):
            launch_monitor_worker(session.get("passive_interval", 30))
        message = "Session resumed."
    else:
        session["paused_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        if MONITOR_STATE_FILE.exists():
            MONITOR_STOP_FILE.write_text("pause", encoding="utf-8")
        message = "Session paused."

    with open(session_file, "w") as f:
        json.dump(session, f, indent=2)
    click.echo(message)

@click.command()
def screenshot_workflow():
    """Capture screenshots and add Markdown references to the daily log."""

    os.makedirs("screenshots", exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_filename = f"logs/{date_str}.md"

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
        filename = f"{timestamp}.png"
        screenshot_path = os.path.join("screenshots", filename)

        try:
            screenshot = ImageGrab.grab()
            screenshot.save(screenshot_path)

            click.echo(f"Screenshot saved: {screenshot_path}")

            # Correct relative path from logs/ to screenshots/
            markdown_path = f"../screenshots/{filename}"

            description = f"Screenshot captured at {timestamp}"

            markdown_entry = (
                f"\n## {description}\n"
                f"![{description}]({markdown_path})\n"
            )

            # Append Markdown reference directly to the daily log
            with open(log_filename, "a", encoding="utf-8") as log_file:
                log_file.write(markdown_entry)

            click.echo(f"Markdown reference added to: {log_filename}")

        except Exception as e:
            click.echo(f"Screenshot capture or logging failed: {e}")
            break

        another = click.prompt("Take another screenshot? (y/n)")

        if another.lower() != "y":
            break


def capture_manual_screenshot(description):
    now = datetime.now()
    safe_description = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:48]
    filename = f"{now.strftime('%Y-%m-%d_%H%M%S')}_{safe_description or 'screen'}.png"
    screenshot_path = Path("screenshots") / filename
    log_filename = Path("logs") / f"{now.strftime('%Y-%m-%d')}.md"
    Path("screenshots").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    screenshot = ImageGrab.grab()
    screenshot.save(screenshot_path)
    if not log_filename.exists():
        log_filename.write_text(f"# Engineering Log – {now.strftime('%Y-%m-%d')}\n", encoding="utf-8")
    markdown_path = f"../screenshots/{filename}"
    with log_filename.open("a", encoding="utf-8") as log_file:
        log_file.write(
            f"\n## Screenshot – {description}\n"
            f"![{description}]({markdown_path})\n"
        )
    return screenshot_path


@click.command(name="screenshot")
def screenshot_command():
    """Capture one named screenshot and add it to today's Markdown log."""
    description = click.prompt("What should this screenshot show?", default="work in progress", show_default=True)
    try:
        screenshot_path = capture_manual_screenshot(description)
        click.echo(f"Screenshot saved: {screenshot_path}")
        click.echo("Added to today's Markdown log.")
    except Exception as error:
        raise click.ClickException(f"Screenshot capture failed: {error}") from error

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

    if session.get("paused_at"):
        paused_at = datetime.strptime(session["paused_at"], "%Y-%m-%d %H:%M:%S")
        session["paused_seconds"] = session.get("paused_seconds", 0) + int((end_time - paused_at).total_seconds())
        session.pop("paused_at", None)

    if session.get("passive_capture") and MONITOR_STATE_FILE.exists():
        MONITOR_STOP_FILE.write_text("finish", encoding="utf-8")

    duration = end_time - start_time
    active_seconds = max(0, int(duration.total_seconds()) - session.get("paused_seconds", 0))
    duration_minutes = int(active_seconds / 60)

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
    struggles = click.prompt("What slowed you down or felt difficult?", default="None", show_default=False)
    ai_missed = click.prompt("What did the AI miss or get wrong?", default="None", show_default=False)
    story_context = click.prompt("What should the story of this work emphasize?", default="None", show_default=False)
    story_notes = (
        f"Work completed:\n{rough_notes}\n\n"
        f"Struggles:\n{struggles}\n\n"
        f"AI missed or got wrong:\n{ai_missed}\n\n"
        f"Story emphasis:\n{story_context}"
    )
    ai_output = generate_ai_summary(story_notes)

    review = review_ai_output(ai_output)

    if review["status"] == "rejected":
        click.echo("\nAI output rejected. Please revise the generated content before continuing.")
        return

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

### Working Story
{story_context}

### Friction and AI Gaps
{struggles}

### What the AI Missed
{ai_missed}

### AI Peer Review
Status: {review["status"].title()}
Reviewer: {review["reviewer"]}
Reviewed At: {review["reviewed_at"]}
Reviewer Notes: {review["notes"]}

### Duration
{duration_minutes} minutes (Planned: {timeboxed_minutes} minutes)

### Notes
{notes}
"""

    # Ensure logs folder exists
    os.makedirs("logs", exist_ok=True)

    # Create or append log file
    if not os.path.exists(log_filename):
        with open(log_filename, "w", encoding="utf-8") as f:
            f.write(f"# Engineering Log – {date_str}\n")
            f.write(session_entry)
    else:
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(session_entry)

    # Update CHANGELOG
    with open("CHANGELOG.md", "a") as f:
        f.write(f"- {date_str}: {rough_notes}\n")

    # Update stats + README
    update_stats(date_str, duration_minutes)
    update_readme_dashboard()

    # Git automation
    commit_created = False
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", f"AutoDoc session {date_str}"], check=True)
        commit_created = True
    except:
        click.echo("Git commit failed.")

    if commit_created:
        push_repository_if_enabled()

    # Save handover note for next session
    prev_file = ".autodoc/previous_session.json"
    with open(prev_file, "w") as f:
        json.dump({"where_left_off": where_left_off}, f, indent=2)

    # Remove session file
    os.remove(session_file)

    click.echo("\n✅ Session logged successfully. Handover note saved.")

@click.command()
def self_test():
    """Run a quick AutoDoc health and integration test"""

    click.echo("\n🧪 AutoDoc Self-Test\n")

    checks = []

    # 1. Project initialization
    initialized = os.path.exists(".autodoc")
    checks.append(("AutoDoc initialized", initialized))

    # 2. Gemini API
    api_key = get_api_key()
    gemini_ok = bool(api_key)

    if gemini_ok:
        try:
            client = genai.Client(api_key=api_key)
            click.echo("Testing Gemini...")
            chat = client.chats.create(model="gemini-2.5-flash")
            click.echo("Sending Gemini test...")
            response = chat.send_message("Reply with exactly: PASS")
            gemini_ok = "PASS" in response.text.upper()
        except Exception:
            gemini_ok = False

    checks.append(("Gemini API", gemini_ok))

    # 3. PowerShell execution
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", "Write-Output 'PASS'"],
            capture_output=True,
            text=True
        )
        powershell_ok = result.returncode == 0 and "PASS" in result.stdout
    except Exception:
        powershell_ok = False

    checks.append(("PowerShell execution", powershell_ok))

    # 4. Screenshot capture
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        test_screenshot = f"screenshots/self_test_{timestamp}.png"

        screenshot = ImageGrab.grab()
        screenshot.save(test_screenshot)

        screenshot_ok = os.path.exists(test_screenshot)
    except Exception:
        screenshot_ok = False

    checks.append(("Screenshot capture", screenshot_ok))

    click.echo("-" * 40)

    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        click.echo(f"{status}: {name}")

    click.echo("-" * 40)

    if all(passed for _, passed in checks):
        click.echo("Self-test completed successfully.")
    else:
        click.echo("Self-test detected one or more failures.")

@click.command()
def demo():
    """Run the AutoDoc guided showcase."""
    click.echo("\n" + "=" * 60)
    click.echo("AutoDoc v0.1 — GUIDED SHOWCASE")
    click.echo("=" * 60)

    steps = [
        ("1", "SETUP", "Configure AutoDoc and its AI connection.", "autodoc setup"),
        ("2", "DOCTOR", "Check project health and apply safe corrections.", "autodoc doctor"),
        ("3", "SELF-TEST", "Verify Gemini, PowerShell, and screenshot capture.", "autodoc self-test"),
        ("4", "START SESSION", "Create a focused engineering work session.", "autodoc start"),
        ("5", "WORK / TEST", "Perform the technical task and investigate results.", "autodoc test"),
        ("6", "EVIDENCE CAPTURE", "Capture visual evidence during the engineering session.", "Screenshot capture"),
        ("7", "FINISH", "Generate documentation from rough engineering notes.", "autodoc finish"),
        ("8", "AI PEER REVIEW", "Human reviews the generated documentation.", "Review AI output"),
        ("9", "VERSION CONTROL", "Record the completed work in Git.", "Git commit"),
        ("10", "FINAL STATUS", "Confirm the project is healthy and documented.", "autodoc status"),
    ]

    for number, title, description, command in steps:
        click.echo("\n" + "-" * 60)
        click.echo(f"STEP {number} — {title}")
        click.echo("-" * 60)
        click.echo(f"\n{description}")
        click.echo(f"\nCOMMAND")
        click.echo(f"> {command}")

        if number != "10":
            click.pause("\nPress Enter to continue...")

    click.echo("\n" + "=" * 60)
    click.echo("AI proposes. Human validates. AutoDoc records.")
    click.echo("=" * 60)

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
cli.add_command(test)
cli.add_command(self_test)
cli.add_command(doctor)
cli.add_command(start)
cli.add_command(pause)
cli.add_command(finish)
cli.add_command(stats)
cli.add_command(setup)
cli.add_command(demo)
cli.add_command(screenshot_workflow)
cli.add_command(screenshot_command)
cli.add_command(propose)
cli.add_command(monitor)
cli.add_command(repo)

if __name__ == "__main__":
    cli()