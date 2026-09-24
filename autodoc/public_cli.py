from datetime import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

import click
from PIL import ImageGrab


VERSION = os.getenv("AUTODOC_VERSION", "0.1.0-public")
STATE_DIR = Path(".autodoc-public")
SESSION_FILE = STATE_DIR / "session.json"
SHIFT_FILE = STATE_DIR / "shift.json"
STATS_FILE = STATE_DIR / "stats.json"
LOG_DIR = Path("logs")
SCREENSHOT_DIR = Path("screenshots")


def save_shift(shift):
    STATE_DIR.mkdir(exist_ok=True)
    SHIFT_FILE.write_text(json.dumps(shift, indent=2) + "\n", encoding="utf-8")


def load_shift():
    if not SHIFT_FILE.exists():
        return None
    try:
        return json.loads(SHIFT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise click.ClickException(f"Invalid shift file: {SHIFT_FILE}")


def backup_journal():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = STATE_DIR / "backups" / f"journal_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for source in (LOG_DIR, STATS_FILE, SHIFT_FILE):
        if source.is_dir():
            shutil.copytree(source, backup_dir / source.name, dirs_exist_ok=True)
        elif source.exists():
            shutil.copy2(source, backup_dir / source.name)
    return backup_dir


def capture_screenshot(path, bbox=None):
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    ImageGrab.grab(bbox=bbox, all_screens=True).save(path)


def load_stats():
    if not STATS_FILE.exists():
        return {"total_sessions": 0, "total_minutes": 0, "days_logged": [], "last_session": None}
    try:
        return json.loads(STATS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise click.ClickException(f"Invalid statistics file: {STATS_FILE}")


def save_stats(stats):
    STATE_DIR.mkdir(exist_ok=True)
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


def append_log(entry, date_str):
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{date_str}.md"
    if not log_file.exists():
        log_file.write_text(f"# AutoDoc Public Log - {date_str}\n", encoding="utf-8")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    return log_file


def recent_journal_context(max_files=3, max_chars=12000):
    if not LOG_DIR.exists():
        return "No previous journal entries found."
    files = sorted(LOG_DIR.glob("*.md"), reverse=True)[:max_files]
    if not files:
        return "No previous journal entries found."
    sections = []
    remaining = max_chars
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        excerpt = text[-remaining:]
        sections.append(f"FILE: {path.name}\n{excerpt}")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n\n".join(sections) or "No readable previous journal entries found."


def record_session(date_str, duration_minutes):
    stats = load_stats()
    stats["total_sessions"] += 1
    stats["total_minutes"] += max(0, duration_minutes)
    if date_str not in stats["days_logged"]:
        stats["days_logged"].append(date_str)
    stats["last_session"] = date_str
    save_stats(stats)


@click.group()
def cli():
    """AutoDoc Public Edition: local-first project documentation."""


@cli.command()
def version():
    """Show the public edition version."""
    click.echo(f"AutoDoc Public Edition {VERSION}")


@cli.command()
def init():
    """Initialize public edition folders in the current project."""
    STATE_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    if not STATS_FILE.exists():
        save_stats({"total_sessions": 0, "total_minutes": 0, "days_logged": [], "last_session": None})
    click.echo(f"Initialized AutoDoc Public Edition in {Path.cwd()}")
    click.echo(f"Private state: {STATE_DIR}")


@cli.command()
def start():
    """Start a local documentation session."""
    STATE_DIR.mkdir(exist_ok=True)
    if SESSION_FILE.exists():
        raise click.ClickException("A public session is already active.")

    goal = click.prompt("Session goal", default="", show_default=False)
    done = click.prompt("Definition of done", default="", show_default=False)
    blockers = click.prompt("Dependencies or blockers", default="", show_default=False)
    minutes = click.prompt("Planned minutes", type=click.IntRange(min=1), default=60)
    session = {
        "start_time": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "definition_of_done": done,
        "blockers": blockers,
        "planned_minutes": minutes,
    }
    SESSION_FILE.write_text(json.dumps(session, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Public session started for {minutes} minutes.")


@cli.command()
def finish():
    """Finish the active session and write a Markdown record."""
    if not SESSION_FILE.exists():
        raise click.ClickException("No active public session.")

    try:
        session = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        start_time = datetime.fromisoformat(session["start_time"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise click.ClickException(f"Invalid session file: {error}") from error

    end_time = datetime.now()
    duration = max(0, int((end_time - start_time).total_seconds() / 60))
    notes = click.prompt("What did you work on?", default="", show_default=False)
    next_steps = click.prompt("Next steps", default="", show_default=False)
    date_str = end_time.strftime("%Y-%m-%d")
    entry = f"""
\n---
\n## Public Session - {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}
### Goal
{session['goal'] or 'Not specified'}

### Definition of Done
{session['definition_of_done'] or 'Not specified'}

### Blockers
{session['blockers'] or 'None'}

### Notes
{notes or 'None'}

### Next Steps
{next_steps or 'None'}

### Duration
{duration} minutes (planned: {session['planned_minutes']} minutes)
"""
    log_file = append_log(entry, date_str)
    record_session(date_str, duration)
    SESSION_FILE.unlink()
    click.echo(f"Session recorded in {log_file}")


@cli.command()
def status():
    """Show current public edition status."""
    stats = load_stats()
    click.echo(f"AutoDoc Public Edition {VERSION}")
    click.echo(f"Project: {Path.cwd()}")
    click.echo(f"Active session: {'yes' if SESSION_FILE.exists() else 'no'}")
    click.echo(f"Sessions: {stats['total_sessions']}")
    click.echo(f"Minutes: {stats['total_minutes']}")
    click.echo(f"Days logged: {len(stats['days_logged'])}")


@cli.command()
def stats():
    """Show local session statistics."""
    stats_data = load_stats()
    click.echo(json.dumps(stats_data, indent=2))


@cli.command()
def screenshot():
    """Capture a screenshot and add a Markdown reference to today's log."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    filename = f"public_{timestamp}.png"
    path = SCREENSHOT_DIR / filename
    try:
        ImageGrab.grab().save(path)
    except Exception as error:
        raise click.ClickException(f"Screenshot capture failed: {error}") from error

    date_str = now.strftime("%Y-%m-%d")
    entry = f"\n### Screenshot captured at {timestamp}\n![Screenshot](../screenshots/{filename})\n"
    log_file = append_log(entry, date_str)
    click.echo(f"Screenshot saved to {path}")
    click.echo(f"Markdown reference added to {log_file}")


@cli.command("git-commit")
@click.option("--message", required=True, help="Commit message.")
def git_commit(message):
    """Commit already-staged changes; never stages files automatically."""
    try:
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], check=False)
        if result.returncode == 0:
            raise click.ClickException("No staged changes. Stage files explicitly before committing.")
        subprocess.run(["git", "commit", "-m", message], check=True)
    except FileNotFoundError as error:
        raise click.ClickException("Git is not installed or is unavailable.") from error
    except subprocess.CalledProcessError as error:
        raise click.ClickException(f"Git commit failed with exit code {error.returncode}.") from error
    click.echo("Committed staged changes.")


if __name__ == "__main__":
    cli()
