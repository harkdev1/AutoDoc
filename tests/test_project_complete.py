import tempfile
import unittest
from pathlib import Path

from autodoc.cli import build_project_completion_markdown, generate_assistant_plan, list_log_files


class ProjectCompletionTests(unittest.TestCase):
    def test_build_project_completion_markdown_includes_story_status_and_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()

            log_file = root / "logs" / "2026-10-10.md"
            log_file.write_text(
                "# Engineering Log – 2026-10-10\n\n"
                "## Screenshot – Dashboard build\n"
                "![Dashboard build](../screenshots/2026-10-10_120000_dashboard-build.png)\n\n"
                "### Summary\nBuild automation for launch.\n\n"
                "### Lessons Learned\nKeep documentation close to delivery.\n",
                encoding="utf-8",
            )

            screenshot = root / "screenshots" / "2026-10-10_120000_dashboard-build.png"
            screenshot.write_bytes(b"fakepng")

            readme = root / "README.md"
            readme.write_text("# Demo Project\n\nStatus: In progress\n", encoding="utf-8")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Demo Project",
                status="Complete",
                narrative="We built the delivery flow and documented the launch path.",
                lessons=["Keep docs close to delivery.", "Use proof screenshots for stakeholder updates."],
                next_steps=["Ship the beta release.", "Set up long-term metrics tracking."],
            )

            self.assertIn("Demo Project", result)
            self.assertIn("Status: Complete", result)
            self.assertIn("Lessons learned", result)
            self.assertIn("Dashboard build", result)
            self.assertIn("Keep docs close to delivery", result)

    def test_list_log_files_returns_sorted_markdown_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            logs_dir.mkdir()
            (logs_dir / "2026-10-12.md").write_text("older", encoding="utf-8")
            (logs_dir / "2026-10-11.md").write_text("newer", encoding="utf-8")
            (logs_dir / "notes.txt").write_text("ignore", encoding="utf-8")

            files = list_log_files(root)
            self.assertEqual([path.name for path in files], ["2026-10-12.md", "2026-10-11.md"])

    def test_generate_assistant_plan_uses_project_context_and_includes_next_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()
            (root / "README.md").write_text("# Demo Project\n\nThis project is in progress.\n", encoding="utf-8")
            (root / "logs" / "2026-10-10.md").write_text("### Summary\nWe built a working prototype.\n", encoding="utf-8")
            plan = generate_assistant_plan(project_root=root, user_question="What should I do next?", project_name="Demo Project")
            self.assertIn("Demo Project", plan)
            self.assertIn("Next steps", plan)
            self.assertIn("prototype", plan.lower())

    def test_build_project_completion_markdown_long_form_includes_timeline_and_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "logs").mkdir()
            (root / "screenshots").mkdir()

            log_file = root / "logs" / "2026-10-10.md"
            log_file.write_text(
                "# Engineering Log – 2026-10-10\n\n"
                "## Session – 09:00 to 09:45\n"
                "### Goal\nBuild the dashboard prototype\n\n"
                "### Working Story\nWe got the first version working.\n\n"
                "### Friction and AI Gaps\nThe first pass missed the layout edge case.\n\n"
                "### What the AI Missed\nIt did not include mobile spacing.\n\n"
                "### Duration\n45 minutes (Planned: 60 minutes)\n\n"
                "## Screenshot – Dashboard prototype\n"
                "![Dashboard prototype](../screenshots/dashboard-prototype.png)\n",
                encoding="utf-8",
            )

            screenshot = root / "screenshots" / "dashboard-prototype.png"
            screenshot.write_bytes(b"fakepng")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Example Feature Project",
                status="Example complete",
                narrative="We built the example feature and documented the journey.",
                lessons=["Document decisions as they happen."],
                next_steps=["Keep iterating."],
                long_form=True,
            )

            self.assertIn("Project timeline", result)
            self.assertIn("Trials and tribulations", result)
            self.assertIn("09:00 to 09:45", result)
            self.assertIn("mobile spacing", result)


if __name__ == "__main__":
    unittest.main()
