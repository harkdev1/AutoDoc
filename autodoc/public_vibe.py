from datetime import datetime
import json
import os
from pathlib import Path
import py_compile
import shutil
import tempfile

try:
    from google import genai
except ImportError:
    genai = None


MAX_FILE_BYTES = 200_000
IGNORED_NAMES = {".git", ".venv", "venv", "node_modules", ".autodoc", ".autodoc-public", "__pycache__"}


class VibeCoder:
    def __init__(self, project_root, api_key):
        self.project_root = Path(project_root).resolve()
        self.api_key = api_key

    def collect_context(self):
        files = []
        for path in self.project_root.rglob("*"):
            if not path.is_file() or any(part in IGNORED_NAMES for part in path.parts):
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            files.append(f"FILE: {path.relative_to(self.project_root).as_posix()}\n{text}")
        return "\n\n".join(files)

    def propose(self, request, mode="propose"):
        if genai is None:
            raise RuntimeError("The google-genai package is not installed.")
        if not self.api_key:
            raise RuntimeError("Add a Gemini API key in Settings before using Vibe Code.")

        prompt = f"""You are AutoDoc Public Edition's local coding assistant.
The user requested:
{request}

Mode: {mode}

Project files:
{self.collect_context()}

Return ONLY valid JSON with this shape:
{{
  "summary": "short explanation",
  "files": [
    {{"path": "relative/path.py", "action": "create|update", "content": "complete file contents"}}
  ],
  "notes": "validation notes"
}}

Rules:
- Only propose files inside the project root.
- Do not include secrets, API keys, or credentials.
- Preserve unrelated existing behavior.
- Return complete file contents for every changed file.
- Do not propose shell commands or arbitrary code execution.
"""
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return self.parse_proposal(response.text)

    @staticmethod
    def parse_proposal(text):
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        proposal = json.loads(cleaned)
        if not isinstance(proposal.get("files"), list):
            raise ValueError("Gemini returned no valid file list.")
        for item in proposal["files"]:
            if item.get("action") not in {"create", "update"}:
                raise ValueError("Proposal contains an unsupported file action.")
            if not item.get("path") or not isinstance(item.get("content"), str):
                raise ValueError("Proposal contains an invalid file entry.")
        return proposal

    def apply(self, proposal):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(".autodoc-public") / "backups" / timestamp
        changed_paths = []
        backups = []
        try:
            for item in proposal["files"]:
                target = (self.project_root / item["path"]).resolve()
                if self.project_root not in target.parents:
                    raise ValueError(f"File escapes project root: {item['path']}")
                if any(part in IGNORED_NAMES for part in target.relative_to(self.project_root).parts):
                    raise ValueError(f"File is protected: {item['path']}")
                if len(item["content"].encode("utf-8")) > MAX_FILE_BYTES:
                    raise ValueError(f"File is too large: {item['path']}")
                if target.exists():
                    backup = backup_dir / target.relative_to(self.project_root)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                    backups.append((target, backup))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item["content"], encoding="utf-8")
                changed_paths.append(target)

            self.validate_changed_files(changed_paths)
            return changed_paths, backup_dir
        except Exception:
            for target in changed_paths:
                target.unlink(missing_ok=True)
            for target, backup in backups:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
            raise

    @staticmethod
    def validate_changed_files(paths):
        temp_dir = tempfile.mkdtemp(prefix="autodoc-vibe-")
        try:
            for path in paths:
                if path.suffix == ".py":
                    py_compile.compile(str(path), doraise=True, cfile=os.path.join(temp_dir, path.name + "c"))
                elif path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def run_post_apply_checks(paths):
        """Run deterministic checks without executing arbitrary project commands."""
        VibeCoder.validate_changed_files(paths)
        return [path.name for path in paths]
