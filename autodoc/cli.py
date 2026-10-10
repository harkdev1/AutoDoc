from datetime import datetime
from io import BytesIO
import hashlib
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


def list_log_files(project_root=None):
    """Return the most recent daily logs first."""
    root = Path(project_root or Path.cwd())
    logs_dir = root / "logs"
    if not logs_dir.exists():
        return []

    files = [path for path in logs_dir.glob("*.md") if path.is_file()]
    return sorted(files, key=lambda path: path.name, reverse=True)


def get_screenshot_captions(project_root=None):
    """Collect screenshot captions from Markdown logs so a project summary can reuse earlier evidence."""
    root = Path(project_root or Path.cwd())
    captions = []
    for log_file in list_log_files(root):
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in re.finditer(r"!\[(.*?)\]\((?:\.\./)?screenshots/[^)]+\)", content, re.IGNORECASE):
            caption = match.group(1).strip()
            if caption:
                captions.append({"caption": caption, "log": log_file.name})
    return captions


def collect_project_timeline(project_root=None):
    """Read the time-boxed session entries and screenshot captions from the current project's logs."""
    root = Path(project_root or Path.cwd())
    entries = []
    for log_file in list_log_files(root):
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for match in re.finditer(r"## Session – ([^\n]+)\n(.*?)(?=\n---\n## Session|\n---\n\Z|\Z)", content, re.S):
            stamp = match.group(1).strip()
            body = match.group(2).strip()
            if not body:
                continue
            entries.append({
                "date": log_file.stem,
                "stamp": stamp,
                "body": body,
            })
    return entries


def select_significant_screenshots(project_root=None, max_screenshots=3):
    """Choose the evidence snapshots with the strongest narrative value rather than only the newest files."""
    root = Path(project_root or Path.cwd())
    screenshot_dir = root / "screenshots"
    if not screenshot_dir.exists():
        return []

    candidates = []
    for path in screenshot_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        scratch = path.stem.lower().replace("-", " ").replace("_", " ")
        score = 0
        for keyword in [
            "telemetry", "security", "policy", "gpo", "system", "powershell", "domain",
            "workstation", "server", "dashboard", "prototype", "visibility", "audit",
            "event", "lab", "debug", "script", "activity", "status", "capability",
        ]:
            if keyword in scratch:
                score += 2
        if any(token in scratch for token in ["gap", "issue", "error", "fix", "validation", "baseline", "completed", "configured", "troubleshooting"]):
            score += 1
        if path.stat().st_mtime:
            score += 0
        candidates.append({"path": path, "score": score, "mtime": path.stat().st_mtime})

    candidates.sort(key=lambda item: (item["score"], item["mtime"]), reverse=True)
    return [item["path"] for item in candidates[:max_screenshots]]


def describe_screenshot_context(screenshot_path, caption=""):
    """Generate a short explanation for what the screenshot is showing in project terms."""
    path = Path(screenshot_path)
    stem = path.stem
    cleaned = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{6}_", "", stem)
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    title = caption or (cleaned.title() if cleaned else path.name)
    lowered = title.lower()

    if "telemetry" in lowered or "event" in lowered or "security" in lowered:
        description = "This screenshot shows the telemetry or evidence being reviewed to understand the current system behavior and validate what the environment is actually recording."
    elif "policy" in lowered or "gpo" in lowered or "domain" in lowered or "workstation" in lowered or "server" in lowered:
        description = "This screenshot shows the current configuration or system state being reviewed as part of the active project setup, validation, or troubleshooting work."
    elif "powershell" in lowered or "script" in lowered or "system" in lowered or "diagnostic" in lowered:
        description = "This screenshot captures the live shell output or diagnostic evidence that is guiding the current troubleshooting, validation, or operational decision."
    elif "dashboard" in lowered or "prototype" in lowered or "status" in lowered:
        description = "This screenshot shows the working interface or project state that is currently being shaped to communicate the latest status, progress, and story."
    else:
        description = "This screenshot captures the most important project evidence for the current phase, showing the main state, artifact, or operational view being reviewed."

    return f"{description} It highlights the key detail the viewer should notice in this stage of the project."


def build_project_completion_markdown(project_root=None, project_name=None, status="Complete", narrative="", lessons=None, next_steps=None, output_path=None, long_form=False):
    """Construct a short HR summary or a longer engineering story with timeline evidence and project proof."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    lessons = lessons or []
    next_steps = next_steps or []
    output_path = Path(output_path) if output_path else root / "docs" / "project-complete.md"

    screenshot_dir = root / "screenshots"
    screenshot_paths = select_significant_screenshots(project_root=root, max_screenshots=3) if screenshot_dir.exists() else []

    captions = get_screenshot_captions(root)
    proof_points = []
    for screenshot in screenshot_paths:
        stem = screenshot.stem
        stem_normalized = stem.lower().replace("_", " ").replace("-", " ")
        caption = re.sub(r"^\d{4}-\d{2}-\d{2}_\d{6}_", "", stem).replace("-", " ")
        caption = caption.title() if caption else screenshot.name
        match_caption = next(
            (entry["caption"] for entry in captions if entry["caption"].lower().replace("_", " ") in stem_normalized or stem_normalized in entry["caption"].lower().replace("_", " ")),
            None,
        )
        if match_caption:
            caption = match_caption
        rel_path = Path(os.path.relpath(screenshot, output_path.parent)).as_posix()
        description = describe_screenshot_context(screenshot, caption)
        proof_points.append(
            f"### Highlight: {caption}\n![{caption}]({rel_path})\n{description}\n"
        )

    if not proof_points:
        proof_points.append("### Highlight moments\nNo screenshots were found in the current project. Capture a few key proof images to enrich this summary.\n")

    lessons_block = "\n".join(f"- {lesson}" for lesson in lessons) if lessons else "- No formal lessons captured yet."
    next_steps_block = "\n".join(f"- {step}" for step in next_steps) if next_steps else "- No further actions recorded."

    if long_form:
        timeline = collect_project_timeline(root)
        timeline_sections = []
        for item in timeline:
            body = item["body"]
            body = re.sub(r"^### ", "- ", body, flags=re.M)
            timeline_sections.append(f"### {item['date']} • {item['stamp']}\n{body}\n")

        timeline_body = "".join(timeline_sections) if timeline_sections else "No session logs were found. Start a session and finish it to populate the project story."

        trials = []
        for item in timeline:
            body = item["body"]
            if "Friction and AI Gaps" in body or "What the AI Missed" in body or "Dependencies/Blockers" in body:
                trials.append(f"### {item['date']} • {item['stamp']}\n{body}\n")
        trials_body = "".join(trials) if trials else "No detailed friction notes were captured, but the project still benefited from evidence-based learning and iteration."

        long_markdown = f"""# {project_name}

Status: {status}

## Project story
{narrative or 'This project is complete and the work is ready for handoff.'}

## Project timeline
{timeline_body}

## Screenshots and proof
{''.join(proof_points)}

## Trials and tribulations
{trials_body}

## Lessons learned
{lessons_block}

## Next steps
{next_steps_block}
"""
        return long_markdown

    markdown = f"""# {project_name}

Status: {status}

## Project story
{narrative or 'This project is complete and the work is ready for handoff.'}

## What we shipped
- The project was completed with a clear objective, technical execution, and proof captured in the logs.
- The implementation and project records are documented in the repository for future context.
- The work can be reviewed quickly by anyone familiar with the project.

## Key proof moments
{''.join(proof_points)}

## Lessons learned
{lessons_block}

## Next steps
{next_steps_block}
"""
    return markdown


def write_project_completion_documents(project_root=None, project_name=None, status="Complete", narrative="", lessons=None, next_steps=None, short_path=None, long_path=None):
    """Keep the short file as the current project snapshot and append the long file as the project history."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    short_file = Path(short_path) if short_path else root / "docs" / "project-complete-short.md"
    long_file = Path(long_path) if long_path else root / "docs" / "project-complete-long.md"
    short_file.parent.mkdir(parents=True, exist_ok=True)
    long_file.parent.mkdir(parents=True, exist_ok=True)

    short_markdown = build_project_completion_markdown(
        project_root=root,
        project_name=project_name,
        status=status,
        narrative=narrative,
        lessons=lessons,
        next_steps=next_steps,
        output_path=short_file,
        long_form=False,
    )
    short_file.write_text(short_markdown, encoding="utf-8")

    long_markdown = build_project_completion_markdown(
        project_root=root,
        project_name=project_name,
        status=status,
        narrative=narrative,
        lessons=lessons,
        next_steps=next_steps,
        output_path=long_file,
        long_form=True,
    )

    existing_long = long_file.read_text(encoding="utf-8", errors="ignore").strip() if long_file.exists() else ""
    if existing_long:
        combined = long_markdown + "\n\n---\n\n" + existing_long + "\n"
    else:
        combined = long_markdown + "\n"
    long_file.write_text(combined, encoding="utf-8")
    return short_markdown, combined


def update_project_readme(project_root=None, project_name=None, narrative="", status="Complete", latest_session=None):
    """Update the managed README snapshot while preserving the project overview and latest session."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    readme_path = root / "README.md"
    start_marker = "<!-- autodoc:project-snapshot:start -->"
    end_marker = "<!-- autodoc:project-snapshot:end -->"
    existing = readme_path.read_text(encoding="utf-8", errors="ignore") if readme_path.exists() else ""
    title_match = re.match(r"^# .+\n?", existing)
    title = title_match.group(0).strip() if title_match else f"# {project_name}"
    body = existing[title_match.end():].strip() if title_match else existing.strip()

    if latest_session is None:
        latest_match = re.search(
            r"(?ms)^## Latest session\s*\n(.*?)(?=^" + re.escape(end_marker) + r"\s*$|^---\s*$)",
            body,
        )
        latest_session = latest_match.group(1).strip() if latest_match else ""

    if start_marker in body and end_marker in body:
        body = re.sub(
            re.escape(start_marker) + r".*?" + re.escape(end_marker),
            "",
            body,
            count=1,
            flags=re.S,
        ).strip()
    else:
        body = re.sub(r"(?ms)^## Status:.*?^---\s*$\s*", "", body, count=1).strip()
        body = re.sub(r"(?m)^Status:.*\n?", "", body, count=1).strip()

    preamble = ""
    if body.startswith("> **Project status:**"):
        preamble, _, body = body.partition("\n\n")
        body = body.strip()
    if body.startswith(title + "\n"):
        body = body[len(title):].strip()

    latest_block = f"\n\n## Latest session\n{latest_session.strip()}" if latest_session and latest_session.strip() else ""
    snapshot = f"""{start_marker}

## Status: {status}

## Project summary
{narrative or 'This project is in progress and its current work is recorded in the project logs.'}{latest_block}

{end_marker}"""
    sections = [title]
    if preamble:
        sections.append(preamble)
    sections.append(snapshot)
    if body:
        sections.append(body)
    updated = "\n\n".join(sections).rstrip() + "\n"
    readme_path.write_text(updated, encoding="utf-8")
    return updated


def refresh_readme_after_session(project_root=None, project_name=None, session_summary="", status="In progress"):
    """Lightweight, automatic README refresh after each session without replacing the whole project story."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    readme_path = root / "README.md"
    summary_text = session_summary.strip() or "No session summary recorded yet."
    summary_block = f"""# {project_name}

## Status: {status}

## Latest session
{summary_text}

---

"""

    if not readme_path.exists():
        readme_path.write_text(summary_block, encoding="utf-8")
        return summary_block

    existing = readme_path.read_text(encoding="utf-8", errors="ignore").strip()
    if "## Latest session" in existing or "## Status: " in existing:
        pattern = re.compile(r"^# .+?\n\n## Status: .*?\n\n## (?:Latest session|Project summary)\n.*?(?:\n---\n)?", re.S)
        existing = pattern.sub("", existing).strip()

    updated = summary_block + (existing + "\n" if existing else "")
    readme_path.write_text(updated, encoding="utf-8")
    return updated


def refresh_project_status_file(project_root=None, project_name=None, session_summary="", status="In progress", date_str=None, notes="", where_left_off="", session_details=""):
    """Keep a project-status journal at the repo root so each session contributes to the project's living story."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    status_path = root / "project-status.md"
    summary_text = session_summary.strip() or "No session summary recorded yet."
    today = date_str or datetime.now().strftime("%Y-%m-%d")

    details_text = session_details.strip() or "No additional session details recorded."
    current_entry = f"""## Session – {today}

### Status: {status}

### Session summary
{summary_text}

### Session details
{details_text}

### Notes
{notes.strip() or 'No extra notes recorded.'}

### Where we left off
{where_left_off.strip() or 'No handoff note captured yet.'}

---

"""

    if not status_path.exists():
        existing = f"# {project_name} Project Status\n\nThis file records the live project journey and is updated after every AutoDoc finish."
    else:
        existing = status_path.read_text(encoding="utf-8", errors="ignore").strip()

    existing = re.sub(r"(?ms)^## Latest session.*?(?=^## (?!Latest session)\S.*$|^---\s*$|\Z)", "", existing, count=1).strip()
    existing = re.sub(r"(?m)^## Status:.*\n?", "", existing, count=1).strip()
    current_status = f"## Current status: {status}"
    if re.search(r"(?m)^## Current status:.*$", existing):
        existing = re.sub(r"(?m)^## Current status:.*$", current_status, existing, count=1)
    else:
        title_line = re.search(r"(?m)^# .+$", existing)
        if title_line:
            insert_at = title_line.end()
            existing = existing[:insert_at] + "\n\n" + current_status + existing[insert_at:]
        else:
            existing = current_status + "\n\n" + existing

    updated = existing.rstrip() + "\n\n" + current_entry

    status_path.write_text(updated, encoding="utf-8")
    return updated


def generate_project_completion_story(project_root=None, project_name=None, status="Complete"):
    """Use project logs and screenshot captions to draft a stage-aware summary."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    log_text = ""
    for log_file in list_log_files(root):
        try:
            log_text += f"\n---\n{log_file.name}\n" + log_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

    screenshot_captions = get_screenshot_captions(root)
    captions_text = "\n".join(f"- {entry['caption']}" for entry in screenshot_captions[:10]) if screenshot_captions else "- No screenshot captions captured yet."

    try:
        api_key = get_api_key()
        if not api_key:
            raise Exception("No API key configured.")

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are a senior product storyteller for technical projects.

Write a concise project summary for '{project_name}', whose current status is '{status}'.
Use the project's logs and screenshot captions as evidence.
The audience includes curious employers and technical peers who want a quick understanding of what was built, what changed, and what we learned.
Describe the work as ongoing when the status is not complete; do not imply unfinished work is complete.

Return a polished markdown summary with these headings:
1. Project story
2. Key achievements
3. Lessons learned
4. Next steps
5. Proof points

Project logs:
{log_text[:6000]}

Screenshot captions:
{captions_text}
"""
        chat = client.chats.create(model="gemini-2.5-flash")
        response = chat.send_message(prompt)
        return response.text.strip() or f"{project_name} is currently {status.lower()}."
    except Exception:
        fallback = (
            f"{project_name} is currently {status.lower()}, with progress and evidence captured in the project logs and screenshots. "
            "The work centers on delivering practical outcomes, documenting the engineering process, and making progress easy to review. "
            "Key lessons include keeping documentation close to delivery, recording proof as work progresses, and making handoff notes explicit."
        )
        return fallback


def refresh_project_completion_documents(project_root=None, project_name=None, status="In progress", narrative=None, latest_session=None):
    """Refresh the current project snapshot and append the latest story to its history."""
    root = Path(project_root or Path.cwd())
    project_name = project_name or root.name
    story = narrative or generate_project_completion_story(root, project_name, status=status)
    lessons = [
        "Keep documentation close to delivery.",
        "Use screenshots as proof points.",
        "Write the project story in plain language for future reviewers.",
    ]
    next_steps = [
        "Continue from the handoff notes and current project status.",
        "Capture final cleanup or deployment follow-up items as they are completed.",
    ]
    write_project_completion_documents(
        project_root=root,
        project_name=project_name,
        status=status,
        narrative=story,
        lessons=lessons,
        next_steps=next_steps,
    )
    update_project_readme(
        project_root=root,
        project_name=project_name,
        narrative=story,
        status=status,
        latest_session=latest_session,
    )
    return story


def open_log_for_editing(path):
    """Open the selected log in the system editor so a user can manually refine or extend it."""
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Log not found: {target}")

    if shutil.which("code"):
        subprocess.run(["code", str(target)], check=False)
        return target

    if os.name == "nt":
        subprocess.run(["notepad.exe", str(target)], check=False)
        return target

    click.echo(f"Open the log manually in your editor: {target}")
    return target


def refine_log_with_ai(project_root=None, target_file=None, prompt=None):
    """Ask Gemini to rewrite a project log in a more polished or readable style without replacing the original record automatically."""
    root = Path(project_root or Path.cwd())
    target = Path(target_file) if target_file else (list_log_files(root)[0] if list_log_files(root) else None)
    if target is None or not target.exists():
        raise FileNotFoundError("No log file is available to refine.")

    content = target.read_text(encoding="utf-8", errors="ignore")
    prompt_text = prompt or "Rewrite this engineering log to be clearer, more polished, and easier for a recruiter or hiring manager to scan. Preserve the technical truth and keep the project story honest."

    try:
        api_key = get_api_key()
        if not api_key:
            raise Exception("No API key configured.")

        client = genai.Client(api_key=api_key)
        response = client.chats.create(model="gemini-2.5-flash").send_message(
            f"You are editing an engineering log for clarity and story. Preserve facts and improve readability.\n\nOriginal log:\n{content}\n\nRequested edit:\n{prompt_text}\n\nReturn only the revised markdown."
        )
        revised = response.text.strip()
        if revised:
            return revised
    except Exception:
        pass

    return content


def gather_project_context(project_root=None, max_log_files=3):
    """Pull together a concise project briefing from README, recent logs, and screenshot names."""
    root = Path(project_root or Path.cwd())
    parts = []

    readme_path = root / "README.md"
    if readme_path.exists():
        try:
            parts.append(f"# README\n{readme_path.read_text(encoding='utf-8', errors='ignore')[:2500]}")
        except OSError:
            pass

    log_files = list_log_files(root)[:max_log_files]
    if log_files:
        log_text = []
        for log_file in log_files:
            try:
                log_text.append(f"# {log_file.name}\n{log_file.read_text(encoding='utf-8', errors='ignore')[:2500]}")
            except OSError:
                pass
        parts.append("\n\n".join(log_text))

    screenshot_dir = root / "screenshots"
    if screenshot_dir.exists():
        screenshots = sorted(screenshot_dir.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:10]
        if screenshots:
            names = "\n".join(f"- {s.name}" for s in screenshots)
            parts.append(f"# Recent screenshots\n{names}")

    return "\n\n".join(parts) if parts else "No project context was found."


def generate_assistant_plan(project_root=None, user_question=None, project_name=None):
    """Use Gemini to turn project context into concrete next steps and milestone guidance."""
    root = Path(project_root or Path.cwd())
    name = project_name or root.name
    question = user_question or "What should I do next to finish this project well?"
    context = gather_project_context(root)

    try:
        api_key = get_api_key()
        if not api_key:
            raise Exception("No API key configured.")

        client = genai.Client(api_key=api_key)
        prompt = f"""
You are AutoDoc Assist, an AI project guide inside a development workflow.

Project name: {name}
User request: {question}

Use this project context to create a practical next-step plan:
{context[:8000]}

Return a clear markdown plan with these sections:
1. Current status
2. Immediate next step
3. Recommended work sequence
4. Risks or blockers to watch
5. Evidence to capture
6. Next steps

Keep it helpful, concise, and grounded in the actual project context. Focus on what to do next rather than abstract strategy.
"""
        response = client.chats.create(model="gemini-2.5-flash").send_message(prompt)
        return response.text.strip() or "No plan generated."
    except Exception as exc:
        click.echo(
            f"\n[AutoDoc Assist diagnostic] Gemini request failed: "
            f"{type(exc).__name__}: {exc}",
            err=True,
        )
        fallback = f"""# {name} — AutoDoc Assist plan

## Current status
The project is active and can be advanced with a clear next milestone.

## Immediate next step
Pick the single most important task that moves the project closer to completion, then finish one small, testable piece of it.

## Recommended work sequence
1. Review the README, recent logs, and latest screenshot evidence.
2. Identify the next high-value task that builds momentum.
3. Start a focus session and make the smallest meaningful progress.
4. Capture at least one proof screenshot and one short log entry.
5. Review what changed and decide the next milestone.

## Risks or blockers to watch
- Scope creep
- Missing proof or weak documentation
- Too many tasks in one working block

## Evidence to capture
- one screenshot of the current milestone
- one note explaining what changed
- one note explaining why this matters

## Next steps
- Define the next finished milestone
- update the README status
- keep the log and visual proof current
"""
        return fallback


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


def write_assistant_plan_log(project_root, question, plan, decision="Pending review"):
    """Keep a single project-level plan journal so each prompt and plan remains reviewable without creating multiple files."""
    output_path = Path(project_root) / "assistant-plan.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""## {timestamp}

### Prompt
{question}

### Proposed plan
{plan}

### Decision
{decision}
"""

    existing = output_path.read_text(encoding="utf-8", errors="ignore") if output_path.exists() else "# AutoDoc Assist Log\n"
    if "# AutoDoc Assist Log" not in existing:
        existing = "# AutoDoc Assist Log\n" + existing

    output_path.write_text(existing.rstrip() + "\n\n" + entry.rstrip() + "\n", encoding="utf-8")
    return output_path


@click.command()
@click.option("--prompt", "prompt_text", default=None, help="Prompt AutoDoc Assist with what you want to do next.")
@click.option("--auto-approve", is_flag=True, default=False, help="Accept the generated plan immediately without prompting for review.")
def assist(prompt_text, auto_approve):
    """Ask AutoDoc Assist for a plan, review it, and keep the discussion in one project log."""
    project_root = Path.cwd()
    project_name = project_root.name
    question = prompt_text or click.prompt("What do you want help with right now?", default="What should I do next to move this project forward?", show_default=True)

    plan = generate_assistant_plan(project_root=project_root, user_question=question, project_name=project_name)

    if not auto_approve:
        review_choice = click.prompt(
            "Review this plan: [approve] keep it, [regenerate], [edit], or [quit]",
            default="approve",
            show_default=True,
        ).strip().lower()

        if review_choice in {"quit", "q"}:
            decision = "Deferred: user exited before approval"
            write_assistant_plan_log(project_root, question, plan, decision)
            click.echo("AutoDoc Assist plan saved for later review.")
            return

        if review_choice in {"regenerate", "r"}:
            follow_up = click.prompt("Give AutoDoc Assist a more specific angle or constraint", default="Make the plan more realistic and lower risk.", show_default=True)
            plan = generate_assistant_plan(project_root=project_root, user_question=f"{question} Additional guidance: {follow_up}", project_name=project_name)
            decision = "Regenerated after review"
        elif review_choice in {"edit", "e"}:
            edited_plan = click.prompt("Edit the plan text in-place", default=plan, show_default=False)
            plan = edited_plan.strip() or plan
            decision = "Edited by user"
        else:
            decision = "Approved by user"
    else:
        decision = "Approved automatically"

    output_path = write_assistant_plan_log(project_root, question, plan, decision)

    click.echo("\n" + "=" * 60)
    click.echo("AutoDoc Assist")
    click.echo("=" * 60)
    click.echo(plan)
    click.echo("=" * 60)
    click.echo(f"Recorded in: {output_path}")


@click.group()
def project():
    """Project finish, status, and summary commands."""


def slugify_project_name(project_name):
    """Turn a project display name into a stable gallery folder name."""
    slug = re.sub(r"[^a-z0-9]+", "-", project_name.casefold()).strip("-")
    if not slug:
        raise ValueError("Project name must contain at least one ASCII letter or number.")
    return slug


def get_project_display_name(project_root):
    """Prefer the project's README title while retaining a safe directory-name fallback."""
    root = Path(project_root)
    readme = root / "README.md"
    if readme.is_file():
        try:
            match = re.search(r"(?m)^#\s+(.+?)\s*$", readme.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            match = None
        if match:
            return match.group(1).strip()
    return root.name.replace("-", " ").replace("_", " ").title()


ROADMAP_SHOWCASE_START = "<!-- autodoc:showcase:start -->"
ROADMAP_SHOWCASE_END = "<!-- autodoc:showcase:end -->"
PROJECT_SHOWCASE_START = "<!-- autodoc:project-showcase:start -->"
PROJECT_SHOWCASE_END = "<!-- autodoc:project-showcase:end -->"
EVIDENCE_GALLERY_START = "<!-- autodoc:evidence-gallery:start -->"
EVIDENCE_GALLERY_END = "<!-- autodoc:evidence-gallery:end -->"
PRIVATE_SCREENSHOT_NAME_PARTS = (
    "activity_",
    "pc-specs",
    "users-and-groups",
    "static-ip",
    "dns-forward-lookup-zone",
    "promoted-to-northstar-solutions-domain-c",
    "system-troubleshooting",
    "system-info-script-execution",
    "windows-server-manager",
    "week-1-windows-server-environment-completed",
    "131044",
)


def collect_log_linked_screenshots(project_root):
    """Return existing screenshot files referenced by AutoDoc logs, excluding known private captures."""
    root = Path(project_root).resolve()
    screenshot_root = (root / "screenshots").resolve()
    references = []
    seen = set()
    pattern = re.compile(r"!\[(?P<caption>.*?)\]\((?P<path>[^)]+)\)")
    for log_path in list_log_files(root):
        try:
            content = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in pattern.finditer(content):
            target = match.group("path").strip().split("#", 1)[0]
            if re.match(r"^[a-z]+://", target, flags=re.I):
                continue
            source_path = (log_path.parent / target).resolve()
            try:
                source_path.relative_to(screenshot_root)
            except ValueError:
                continue
            if not source_path.is_file() or source_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            if any(part in source_path.name.casefold() for part in PRIVATE_SCREENSHOT_NAME_PARTS):
                continue
            key = str(source_path).casefold()
            if key in seen:
                continue
            seen.add(key)
            references.append({
                "source": source_path,
                "caption": match.group("caption").strip() or source_path.stem.replace("_", " ").title(),
                "log": log_path,
            })
    return references


def copy_log_linked_screenshots(project_root, project_folder, screenshots):
    """Copy only existing log-linked images and verify each transferred file byte-for-byte."""
    source_root = Path(project_root).resolve()
    screenshots_root = (source_root / "screenshots").resolve()
    destination_root = Path(project_folder).resolve() / "screenshots"
    copied = []
    for item in screenshots:
        source = Path(item["source"]).resolve()
        try:
            source.relative_to(screenshots_root)
        except ValueError as error:
            raise ValueError(f"Screenshot is outside the source screenshots folder: {source}") from error
        if not source.is_file():
            raise FileNotFoundError(f"Screenshot referenced by an AutoDoc log is missing: {source}")

        target = destination_root / source.name
        if target.exists():
            source_digest = hashlib.sha256(source.read_bytes()).digest()
            target_digest = hashlib.sha256(target.read_bytes()).digest()
            if source_digest != target_digest:
                raise ValueError(f"Existing gallery image differs from the source; refusing to overwrite: {target}")
        else:
            destination_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if source_hash != target_hash:
            raise OSError(f"Screenshot copy verification failed: {source.name}")
        copied.append({**item, "gallery_path": target})
    return copied


def replace_managed_gallery_block(markdown, start_marker, end_marker, content, heading):
    """Replace one AutoDoc-managed gallery block without disturbing surrounding README prose."""
    start_count = markdown.count(start_marker)
    end_count = markdown.count(end_marker)
    if start_count != end_count or start_count > 1:
        raise ValueError("Gallery README contains unbalanced AutoDoc markers.")
    block = f"{start_marker}\n{content.strip()}\n{end_marker}"
    if start_count:
        pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.S)
        return pattern.sub(lambda _match: block, markdown, count=1).rstrip() + "\n"

    heading_match = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", markdown)
    if heading_match:
        insertion = heading_match.end()
        return markdown[:insertion] + "\n\n" + block + "\n\n" + markdown[insertion:].lstrip("\n")
    return markdown.rstrip() + f"\n\n{heading}\n\n{block}\n"


def get_project_github_remote(project_root):
    """Return a sanitized GitHub URL and current branch for a source project, if configured."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return "", "main"
    remote = result.stdout.strip()
    https_match = re.fullmatch(r"https?://github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?/?", remote, flags=re.I)
    ssh_match = re.fullmatch(r"git@github\.com:([^/\s]+/[^/\s]+?)(?:\.git)?", remote, flags=re.I)
    repository = (https_match or ssh_match)
    if not repository:
        return "", "main"
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    branch = branch_result.stdout.strip() if not branch_result.returncode else "main"
    return f"https://github.com/{repository.group(1)}", branch or "main"


def extract_project_next_steps(project_root):
    """Read a few existing next-step bullets without inventing new project work."""
    for relative_path in ("docs/project-complete-short.md", "project-status.md"):
        path = Path(project_root) / relative_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"(?ms)^## Next steps\s*\n(.*?)(?=^## |\Z)", text)
        if match:
            lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
            return "\n".join(lines[:6])
    return "No explicit next steps recorded."


def extract_log_session_summary(session_body, max_chars=700):
    """Extract the recorded session summary and outcome without generating new claims."""
    summary_match = re.search(
        r"(?ms)^(?:Summary:|### Summary)\s*\n(.*?)(?=^(?:Tasks Completed:|Issues Encountered:|Next Steps:|Notes:|### Working Story|### Friction and AI Gaps|### What the AI Missed|### AI Peer Review|### Duration)\s*$|\Z)",
        session_body,
    )
    summary = summary_match.group(1).strip() if summary_match else ""
    if not summary:
        story_match = re.search(r"(?ms)^### Working Story\s*\n(.*?)(?=^### |\Z)", session_body)
        summary = story_match.group(1).strip() if story_match else ""
    summary = re.sub(r"\s+", " ", summary)

    outcome_match = re.search(r"(?m)^### Goal Achieved\s*\n([^\n]+)", session_body)
    if outcome_match:
        outcome = re.sub(r"[*_`]+", "", outcome_match.group(1)).strip()
        if outcome:
            summary = f"Recorded outcome: {outcome}. {summary}".strip()

    if not summary:
        summary = "No structured session summary was found in this log entry."
    if len(summary) > max_chars:
        summary = summary[:max_chars - 3].rsplit(" ", 1)[0] + "..."
    return summary


def build_project_showcase(project_root, project_name, status, narrative, screenshots, source_repo_url, source_branch):
    """Create a concise case-study page with copied evidence and source-log provenance."""
    root = Path(project_root)
    slug = slugify_project_name(project_name)
    story = narrative.strip() or f"{project_name} status: {status}. See the linked session logs for the recorded work."
    lines = [
        f"**{'Main Homelab · ' if slug == 'cyberops-sandbox' else ''}Status:** {status}",
        f"**Source repository:** [{source_repo_url}]({source_repo_url})" if source_repo_url else "**Source repository:** Not linked; no GitHub origin was configured.",
        "",
        "## What I built",
        story,
        "",
        "## Evidence gallery",
    ]
    if screenshots:
        for item in screenshots:
            gallery_name = Path(item["gallery_path"]).name
            log_relative = Path(item["log"]).relative_to(root).as_posix()
            log_link = f"{source_repo_url}/blob/{source_branch}/{log_relative}" if source_repo_url else f"../../../{root.name}/{log_relative}"
            lines.extend([
                f"### {item['caption']}",
                f"![{item['caption']}](screenshots/{gallery_name})",
                f"Evidence copied from [{log_relative}]({log_link}) and verified against the source image.",
                "",
            ])
    else:
        lines.append("No eligible screenshot references were approved for this gallery update.")
        lines.append("")

    timeline = collect_project_timeline(root)
    if timeline:
        lines.extend(["## Session highlights", ""])
        for entry in timeline[:12]:
            log_relative = f"logs/{entry['date']}.md"
            if source_repo_url:
                log_link = f"{source_repo_url}/blob/{source_branch}/{log_relative}"
            else:
                log_link = f"../../../{root.name}/{log_relative}"
            session_summary = extract_log_session_summary(entry["body"])
            lines.extend([
                f"### {entry['date']} · {entry['stamp']}",
                session_summary,
                f"[Open the original AutoDoc log]({log_link})",
                "",
            ])

    lines.extend([
        "## Current limitations and next steps",
        extract_project_next_steps(root),
        "",
        "## Project files",
    ])
    for filename, label in (
        ("project-status.md", "Current project status"),
        ("docs/project-complete-short.md", "Short project summary"),
        ("docs/project-complete-long.md", "Full project history"),
    ):
        if (root / filename).is_file():
            if source_repo_url:
                file_link = f"{source_repo_url}/blob/{source_branch}/{filename}"
            else:
                file_link = f"../../../{root.name}/{filename}"
            lines.append(f"- [{label}]({file_link})")
    lines.append("- [Evidence index](evidence-index.md)")
    lines.extend([
        "",
        "---",
        "Screenshots are copied only from image references present in AutoDoc logs. Review each image for private details before publishing.",
        f"Gallery folder: `projects/{slug}/screenshots/`.",
    ])
    return "\n".join(lines).strip() + "\n"


def update_project_evidence_index(project_folder, project_root, project_name, screenshots, source_repo_url, source_branch):
    """Create or refresh a visual index of copied log-linked images with their source-log provenance."""
    gallery_folder = Path(project_folder)
    project_root = Path(project_root)
    index_path = gallery_folder / "evidence-index.md"
    if index_path.is_file():
        existing = index_path.read_text(encoding="utf-8", errors="ignore")
    else:
        existing = (
            f"# {project_name} Evidence Index\n\n"
            "Screenshots below are copied only when referenced by an AutoDoc source log. "
            "Each transferred image is verified against its source bytes and linked back to that log.\n\n"
            "## Transferred screenshots\n"
        )

    entries = []
    for item in screenshots:
        image_name = Path(item["gallery_path"]).name
        log_relative = Path(item["log"]).relative_to(project_root).as_posix()
        log_link = (
            f"{source_repo_url}/blob/{source_branch}/{log_relative}"
            if source_repo_url
            else f"../../../{project_root.name}/{log_relative}"
        )
        description = describe_screenshot_context(item["source"], item["caption"])
        entries.extend([
            f"### {item['caption']}",
            f"![{item['caption']}](screenshots/{image_name})",
            description,
            f"Source: [{log_relative}]({log_link}). Image copied from the log reference and SHA-256 verified.",
            "",
        ])
    if not entries:
        entries = ["No screenshots were approved for transfer. Source images remain in the project repository.\n"]

    updated = replace_managed_gallery_block(
        existing,
        EVIDENCE_GALLERY_START,
        EVIDENCE_GALLERY_END,
        "\n".join(entries),
        "## Transferred screenshots",
    )
    index_path.write_text(updated, encoding="utf-8")
    return index_path


def build_gallery_index_entry(project_name, project_slug, status, narrative, screenshots, source_repo_url):
    story = re.sub(r"\s+", " ", narrative).strip()
    if len(story) > 420:
        story = story[:417].rsplit(" ", 1)[0] + "..."
    lines = [
        f"### [{project_name}](projects/{project_slug}/README.md)",
        "",
        f"**{'Main Homelab · ' if project_slug == 'cyberops-sandbox' else ''}{status}**" + (f" · [Source repository]({source_repo_url})" if source_repo_url else ""),
        "",
        story,
    ]
    if screenshots:
        first_image = Path(screenshots[0]["gallery_path"]).name
        caption = screenshots[0]["caption"]
        lines.extend(["", f"[![{caption}](projects/{project_slug}/screenshots/{first_image})](projects/{project_slug}/README.md)"])
    return "\n".join(lines)


def update_roadmap_gallery(roadmap_root, project_root, project_name, status, narrative, approved_screenshots):
    """Update a project's one-page Roadmap showcase, index card, and log-linked screenshot copies."""
    roadmap_root = Path(roadmap_root).resolve()
    project_root = Path(project_root).resolve()
    if project_root == roadmap_root or project_root in roadmap_root.parents or roadmap_root in project_root.parents:
        raise ValueError("Source project and Roadmap repository must remain separate, non-nested repositories.")
    if not (roadmap_root / ".git").exists() or not (roadmap_root / "projects").is_dir():
        raise ValueError(f"Roadmap path is not the expected standalone gallery repository: {roadmap_root}")

    project_slug = slugify_project_name(project_name)
    project_folder = (roadmap_root / "projects" / project_slug).resolve()
    if project_folder.parent != (roadmap_root / "projects").resolve():
        raise ValueError("Project gallery path escaped the Roadmap projects directory.")
    guarded = ["README.md", f"projects/{project_slug}"]
    dirty = subprocess.run(["git", "status", "--porcelain", "--", *guarded], cwd=roadmap_root, capture_output=True, text=True, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=roadmap_root, check=False)
    if dirty.stdout.strip() or staged.returncode == 1:
        raise ValueError("Roadmap gallery/index has local changes; review or commit them before AutoDoc overwrites or pushes it.")

    project_folder.mkdir(parents=True, exist_ok=True)
    copied_screenshots = copy_log_linked_screenshots(project_root, project_folder, approved_screenshots)
    source_repo_url, source_branch = get_project_github_remote(project_root)
    page_content = build_project_showcase(
        project_root,
        project_name,
        status,
        narrative,
        copied_screenshots,
        source_repo_url,
        source_branch,
    )
    project_readme = project_folder / "README.md"
    existing_project_page = project_readme.read_text(encoding="utf-8", errors="ignore") if project_readme.exists() else f"# {project_name}\n"
    updated_project_page = replace_managed_gallery_block(
        existing_project_page,
        PROJECT_SHOWCASE_START,
        PROJECT_SHOWCASE_END,
        page_content,
        "## Showcase",
    )
    project_readme.write_text(updated_project_page, encoding="utf-8")
    update_project_evidence_index(
        project_folder,
        project_root,
        project_name,
        copied_screenshots,
        source_repo_url,
        source_branch,
    )

    index_path = roadmap_root / "README.md"
    index_text = index_path.read_text(encoding="utf-8", errors="ignore")
    index_entry = build_gallery_index_entry(project_name, project_slug, status, narrative, copied_screenshots, source_repo_url)
    updated_index = replace_managed_gallery_block(
        index_text,
        f"<!-- autodoc:project:{project_slug}:start -->",
        f"<!-- autodoc:project:{project_slug}:end -->",
        index_entry,
        "## Gallery",
    )
    index_path.write_text(updated_index, encoding="utf-8")
    return project_folder, copied_screenshots


def commit_and_push_roadmap_update(roadmap_root, project_name):
    """Commit only the updated gallery index/project folder and push the Roadmap branch."""
    root = Path(roadmap_root)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True, check=False)
    if not branch or remote.returncode:
        raise ValueError("Roadmap was updated locally but has no current branch or origin remote to push.")

    slug = slugify_project_name(project_name)
    subprocess.run(["git", "add", "--", "README.md", f"projects/{slug}"], cwd=root, check=True)
    staged_paths = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    allowed_prefix = f"projects/{slug}/"
    if any(path != "README.md" and not path.startswith(allowed_prefix) for path in staged_paths):
        raise ValueError("Unexpected staged Roadmap paths detected; refusing to commit or push.")
    if not staged_paths:
        return "No Roadmap changes to commit."

    subprocess.run(["git", "commit", "-m", f"Update project gallery: {project_name}"], cwd=root, check=True)
    subprocess.run(["git", "push", "origin", branch], cwd=root, check=True)
    return f"Pushed Roadmap gallery update to origin/{branch}."


def sync_project_to_roadmap(project_root, project_name, status, narrative, roadmap_dir=None):
    """Sync one project showcase to the sibling Roadmap gallery and publish only its gallery files."""
    root = Path(project_root).resolve()
    target_roadmap = Path(roadmap_dir).resolve() if roadmap_dir else root.parent / "roadmap"
    if root == target_roadmap:
        click.echo("Current project is the Roadmap gallery itself; self-sync skipped.")
        return None
    if not (target_roadmap / ".git").exists():
        click.echo(f"Roadmap gallery not found at {target_roadmap}; source project finished locally.")
        return None

    screenshots = collect_log_linked_screenshots(root)
    project_gallery = target_roadmap / "projects" / slugify_project_name(project_name) / "screenshots"
    previously_approved = []
    new_screenshots = []
    for item in screenshots:
        if (project_gallery / Path(item["source"]).name).is_file():
            previously_approved.append(item)
        else:
            new_screenshots.append(item)

    approved_screenshots = list(previously_approved)
    if new_screenshots:
        click.echo(f"\nNew log-linked screenshots for {project_name}'s gallery:")
        for item in new_screenshots:
            click.echo(f"- {item['caption']} ({item['source'].name}; from {item['log'].name})")
        if click.confirm("Publish these new images to the Roadmap gallery?", default=False):
            approved_screenshots.extend(new_screenshots)
        else:
            click.echo("New images skipped; previously approved images and the showcase will still update.")
    elif not screenshots:
        click.echo(f"No eligible AutoDoc log-linked screenshots found for {project_name}.")
    else:
        click.echo("No new screenshots to review; previously approved gallery images will be reverified.")

    try:
        project_folder, copied_screenshots = update_roadmap_gallery(
            roadmap_root=target_roadmap,
            project_root=root,
            project_name=project_name,
            status=status,
            narrative=narrative,
            approved_screenshots=approved_screenshots,
        )
        for item in copied_screenshots:
            click.echo(f"Screenshot copied and hash-verified: {item['gallery_path']}")
        click.echo(f"Showcase updated: {project_folder}")
        result = commit_and_push_roadmap_update(target_roadmap, project_name)
        click.echo(result)
        return project_folder
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        click.echo(f"Roadmap update failed; source project work remains saved: {error}", err=True)
        return None


@project.command("complete")
@click.option("--name", default=None, help="Project name to use in the README and summary.")
@click.option("--status", default="Complete", show_default=True, help="Project completion status to display.")
@click.option("--summary", default=None, help="Optional custom project summary to override the AI-generated writeup.")
@click.option("--format", "output_format", type=click.Choice(["short", "long", "both"], case_sensitive=False), default="both", show_default=True, help="Which project summary format to generate.")
@click.option("--skip-roadmap", is_flag=True, help="Do not update the sibling Roadmap showcase for this completion.")
@click.option("--roadmap-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Roadmap repository path (defaults to a sibling ./roadmap directory).")
def project_complete(name, status, summary, output_format, skip_roadmap, roadmap_dir):
    """Generate a short hiring summary and a longer story-based engineering summary."""
    project_root = Path.cwd()
    project_name = name or get_project_display_name(project_root)
    story = summary or generate_project_completion_story(project_root, project_name, status=status)
    lessons = []
    if "lessons learned" in story.lower():
        lessons = [
            "Document decisions as they happen so a later handoff reads naturally.",
            "Capture proof in the moment with screenshots and structured notes.",
            "Use the README as the public landing page for project status and impact.",
        ]
    else:
        lessons = [
            "Keep documentation close to delivery.",
            "Use screenshots as proof points.",
            "Write the story in plain language for future employers and collaborators.",
        ]

    next_steps = [
        "Share the completed project summary in the README and release notes.",
        "Capture any final cleanup or deployment follow-up items.",
        "Keep logs fresh for future review and hiring conversations.",
    ]

    output_dir = project_root / "docs"
    output_dir.mkdir(exist_ok=True)
    short_path = output_dir / "project-complete-short.md"
    long_path = output_dir / "project-complete-long.md"

    if output_format in {"short", "long", "both"}:
        short_markdown, _ = write_project_completion_documents(
            project_root=project_root,
            project_name=project_name,
            status=status,
            narrative=story,
            lessons=lessons,
            next_steps=next_steps,
            short_path=short_path,
            long_path=long_path,
        )
        update_project_readme(project_root=project_root, project_name=project_name, narrative=story, status=status)
        click.echo(f"Short project pager saved to: {short_path}")
        click.echo(f"Long project story saved to: {long_path}")

    if output_format == "both":
        click.echo(f"README updated with the short summary and status: {status}")
    elif output_format == "short":
        click.echo(f"README updated with status: {status}")

    target_roadmap = Path(roadmap_dir).resolve() if roadmap_dir else project_root.parent / "roadmap"
    if skip_roadmap:
        click.echo("Roadmap showcase update skipped by --skip-roadmap.")
    else:
        sync_project_to_roadmap(project_root, project_name, status, story, target_roadmap)


@click.group()
def logs():
    """List, open, and refine project logs."""


@logs.command("list")
def logs_list():
    """List the project logs in reverse chronological order."""
    entries = list_log_files(Path.cwd())
    if not entries:
        click.echo("No project logs found in ./logs")
        return
    for path in entries:
        click.echo(path.name)


@logs.command("open")
@click.argument("path", required=False)
def logs_open(path):
    """Open the most recent log or a specific one in your editor."""
    root = Path.cwd()
    if path:
        target = root / path
    else:
        targets = list_log_files(root)
        target = targets[0] if targets else None
    if target is None or not target.exists():
        raise click.ClickException("No log file is available to open.")
    open_log_for_editing(target)
    click.echo(f"Opened: {target}")


@logs.command("edit")
@click.argument("path", required=False)
@click.option("--prompt", default=None, help="Optional prompt for AI-assisted log refinement.")
def logs_edit(path, prompt):
    """Open the log for manual editing, optionally refining it with Gemini."""
    root = Path.cwd()
    if path:
        target = root / path
    else:
        targets = list_log_files(root)
        target = targets[0] if targets else None
    if target is None or not target.exists():
        raise click.ClickException("No log file is available to edit.")

    if prompt:
        refined = refine_log_with_ai(project_root=root, target_file=target, prompt=prompt)
        target.write_text(refined, encoding="utf-8")
        click.echo(f"AI-assisted revision saved to {target}")

    open_log_for_editing(target)
    click.echo(f"Ready for manual review: {target}")


@logs.command("refine")
@click.argument("edit_prompt", required=False)
@click.option("--file", default=None, help="Specific log file to refine.")
def logs_refine(edit_prompt, file):
    """Ask Gemini to rewrite a log entry for clarity and stronger narrative."""
    target = Path(file) if file else None
    prompt = edit_prompt or "Rewrite this log entry in a clearer, polished format for a technical narrative and hiring review."
    root = Path.cwd()
    refined = refine_log_with_ai(project_root=root, target_file=target, prompt=prompt)
    if target is None:
        target = list_log_files(root)[0]
    target.write_text(refined, encoding="utf-8")
    click.echo(f"AI refinement complete: {target}")


@click.group()
def cli():
    """
AutoDoc – Engineering Documentation & Session Tracking CLI

Commands:
  init     Initialize AutoDoc project
  start    Start focus session
  finish   Finish session and generate logs
  pause    Pause or resume an active focus session
  log      Quick engineering log
  logs     List, open, and refine project logs
  project  Generate short and long project completion summaries
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
@click.option("--skip-roadmap", is_flag=True, help="Do not update the sibling Roadmap gallery for this session.")
@click.option("--roadmap-dir", type=click.Path(path_type=Path, file_okay=False), default=None, help="Roadmap repository path (defaults to a sibling ./roadmap directory).")
def finish(skip_roadmap, roadmap_dir):
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

    session_summary = f"""### Work completed
{rough_notes.strip() or 'No rough notes recorded.'}

### AI-reviewed session summary
{ai_output.strip() or 'No AI summary recorded.'}"""
    session_details = "\n\n".join(
        [
            f"**Session time:** {date_str}, {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}",
            f"**Goal:** {goal or 'No goal set.'}",
            f"**Goal achieved:** {'Yes' if goal_achieved and goal_achieved.lower() == 'y' else 'No' if goal_achieved else 'Not applicable; no goal was set.'}",
            f"**Duration:** {duration_minutes} minutes (planned: {timeboxed_minutes} minutes)",
            f"**Working story:** {story_context or 'No story emphasis provided.'}",
            f"**Friction or blockers:** {struggles or 'None reported.'}",
            f"**AI gaps:** {ai_missed or 'None reported.'}",
            f"**AI peer review:** {review['status'].title()} by {review['reviewer']} at {review['reviewed_at']}",
            f"**Reviewer notes:** {review['notes'] or 'None.'}",
        ]
    )
    latest_session = f"{session_summary}\n\n{session_details}\n\n**Notes:** {notes or 'None.'}\n\n**Handoff:** {where_left_off or 'No handoff captured.'}"

    # Update stats and project documentation
    update_stats(date_str, duration_minutes)
    update_readme_dashboard()
    refresh_project_status_file(
        project_root=Path.cwd(),
        project_name=Path.cwd().name,
        session_summary=session_summary,
        status="In progress",
        date_str=date_str,
        notes=notes,
        where_left_off=where_left_off,
        session_details=session_details,
    )
    refresh_project_completion_documents(
        project_root=Path.cwd(),
        project_name=Path.cwd().name,
        status="In progress",
        latest_session=latest_session,
    )

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
    if skip_roadmap:
        click.echo("Roadmap showcase update skipped by --skip-roadmap.")
    else:
        roadmap_narrative = f"{rough_notes.strip()}\n\n{ai_output.strip()}".strip()
        sync_project_to_roadmap(
            project_root=Path.cwd(),
            project_name=get_project_display_name(Path.cwd()),
            status="In progress",
            narrative=roadmap_narrative,
            roadmap_dir=roadmap_dir,
        )

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
cli.add_command(assist)
cli.add_command(project)
cli.add_command(logs)
cli.add_command(repo)

if __name__ == "__main__":
    cli()