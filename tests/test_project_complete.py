import tempfile
import unittest
from pathlib import Path

from autodoc import public_cli
from autodoc.cli import build_project_completion_markdown, generate_assistant_plan, list_log_files, refresh_project_completion_documents, refresh_project_status_file, refresh_readme_after_session, update_project_readme, write_project_completion_documents


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

    def test_refresh_readme_after_session_updates_status_and_latest_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text("# Original Project\n\nOld content stays below.\n", encoding="utf-8")

            refreshed = refresh_readme_after_session(
                project_root=root,
                project_name="Original Project",
                session_summary="Finished the API integration and documented the deployment notes.",
                status="In progress",
            )

            self.assertIn("## Status: In progress", refreshed)
            self.assertIn("Latest session", refreshed)
            self.assertIn("Finished the API integration", refreshed)
            self.assertIn("Old content stays below", refreshed)

    def test_refresh_project_status_file_updates_session_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = root / "project-status.md"
            status_path.write_text("# Project Status\n\nExisting project history stays below.\n", encoding="utf-8")

            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Finished the API integration and documented the deployment notes.",
                status="In progress",
                date_str="2026-10-10",
                notes="Need the release checklist before shutdown.",
                session_details="**Goal:** Validate the API integration.\n\n**Duration:** 45 minutes.",
            )

            self.assertIn("## Status: In progress", refreshed)
            self.assertIn("## Session summary", refreshed)
            self.assertIn("Finished the API integration", refreshed)
            self.assertIn("Existing project history stays below", refreshed)
            self.assertIn("2026-10-10", refreshed)
            self.assertIn("**Goal:** Validate the API integration.", refreshed)
            self.assertIn("**Duration:** 45 minutes.", refreshed)

    def test_refresh_project_status_file_keeps_prior_sessions_and_updates_current_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            first = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Configured the initial workstation policy.",
                status="In progress",
                date_str="2026-10-09",
            )
            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Validated the PowerShell diagnostics script.",
                status="In progress",
                date_str="2026-10-10",
            )

            self.assertIn("Configured the initial workstation policy.", refreshed)
            self.assertIn("Validated the PowerShell diagnostics script.", refreshed)
            self.assertIn("2026-10-09", refreshed)
            self.assertIn("2026-10-10", refreshed)
            self.assertIn("Current status: In progress", refreshed)

    def test_refresh_project_status_file_migrates_legacy_status_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status_path = root / "project-status.md"
            status_path.write_text(
                "# Original Project Status\n\n"
                "## Status: In progress\n\n"
                "## Latest session\nOld generic placeholder.\n\n"
                "## Notes\nKeep the project journal.\n\n---\n",
                encoding="utf-8",
            )

            refreshed = refresh_project_status_file(
                project_root=root,
                project_name="Original Project",
                session_summary="Recorded the latest project work.",
                status="In progress",
                date_str="2026-10-10",
            )

            self.assertEqual(refreshed.count("## Current status: In progress"), 1)
            self.assertNotIn("\n## Status: In progress\n", refreshed)
            self.assertNotIn("Old generic placeholder", refreshed)
            self.assertIn("Keep the project journal.", refreshed)

    def test_project_readme_keeps_latest_session_details_with_project_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme_path = root / "README.md"
            readme_path.write_text(
                "# Demo Project\n\n"
                "> **Project status:** See [project-status.md](project-status.md).\n\n"
                "## About\nExisting project details stay below the generated summary.\n",
                encoding="utf-8",
            )
            session_details = "**Goal:** Validate the telemetry pipeline.\n\n**Duration:** 45 minutes."

            refresh_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="The project is validating its telemetry pipeline.",
                latest_session=session_details,
            )

            readme_text = readme_path.read_text(encoding="utf-8")
            self.assertIn("## Status: In progress", readme_text)
            self.assertIn("The project is validating its telemetry pipeline.", readme_text)
            self.assertIn("## Latest session", readme_text)
            self.assertIn("**Goal:** Validate the telemetry pipeline.", readme_text)
            self.assertIn("**Duration:** 45 minutes.", readme_text)
            self.assertIn("[project-status.md](project-status.md)", readme_text)
            self.assertIn("Existing project details stay below the generated summary.", readme_text)

            update_project_readme(
                project_root=root,
                project_name="Demo Project",
                narrative="The project is complete after telemetry validation.",
                status="Complete",
            )
            completed_readme = readme_path.read_text(encoding="utf-8")
            self.assertIn("## Status: Complete", completed_readme)
            self.assertIn("**Goal:** Validate the telemetry pipeline.", completed_readme)
            self.assertEqual(completed_readme.count("## Latest session"), 1)

    def test_public_finish_documentation_refresh_updates_readme_and_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Public Demo\n\nProject details.\n", encoding="utf-8")
            public_cli.update_project_documentation(
                project_root=root,
                project_name="Public Demo",
                date_str="2026-10-10",
                session_summary="### Work completed\nBuilt the account diagnostics script.",
                session_details="**Goal:** Validate account diagnostics.\n\n**Duration:** 30 minutes.",
                latest_session="**Goal:** Validate account diagnostics.\n\n**Duration:** 30 minutes.",
                notes="The script ran successfully.",
                where_left_off="Test the script on another workstation.",
            )

            readme_text = (root / "README.md").read_text(encoding="utf-8")
            status_text = (root / "project-status.md").read_text(encoding="utf-8")
            self.assertIn("## Latest session", readme_text)
            self.assertIn("**Goal:** Validate account diagnostics.", readme_text)
            self.assertIn("## Current status: In progress", status_text)
            self.assertIn("Built the account diagnostics script.", status_text)
            self.assertIn("Test the script on another workstation.", status_text)

    def test_build_project_completion_markdown_prefers_significant_screenshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "screenshots").mkdir()
            (root / "logs").mkdir()
            (root / "docs").mkdir()

            newest = root / "screenshots" / "2026-10-10_100000_temp-progress.png"
            newest.write_bytes(b"fakepng")
            important = root / "screenshots" / "2026-10-08_080000_telemetry-visibility-gap.png"
            important.write_bytes(b"fakepng")

            result = build_project_completion_markdown(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="We are validating telemetry visibility before the next phase.",
                lessons=["Use the strongest proof to explain progress."],
                next_steps=["Fix the telemetry issue."],
                output_path=root / "docs" / "project-complete-short.md",
            )

            self.assertIn("telemetry visibility gap", result.lower())
            self.assertIn("This screenshot shows the telemetry", result)
            self.assertLess(result.lower().find("telemetry visibility gap"), result.lower().find("temp progress"))

    def test_write_project_completion_documents_overwrites_short_and_appends_long(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            short_path = root / "docs" / "project-complete-short.md"
            long_path = root / "docs" / "project-complete-long.md"
            short_path.write_text("old short\n", encoding="utf-8")
            long_path.write_text("old long\n", encoding="utf-8")

            write_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="Current sprint focus is securing the telemetry pipeline.",
                lessons=["Capture evidence as work happens."],
                next_steps=["Finish the telemetry validation pass."],
                short_path=short_path,
                long_path=long_path,
            )

            self.assertIn("Current sprint focus is securing the telemetry pipeline", short_path.read_text(encoding="utf-8"))
            self.assertNotIn("old short", short_path.read_text(encoding="utf-8"))
            long_text = long_path.read_text(encoding="utf-8")
            self.assertIn("Current sprint focus is securing the telemetry pipeline", long_text)
            self.assertIn("old long", long_text)

    def test_refresh_project_completion_documents_updates_current_snapshot_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            short_path = docs / "project-complete-short.md"
            long_path = docs / "project-complete-long.md"
            short_path.write_text("# Old snapshot\n", encoding="utf-8")
            long_path.write_text("# Earlier milestone\n\nPrior work remains documented.\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo Project\n\nExisting details.\n", encoding="utf-8")

            refresh_project_completion_documents(
                project_root=root,
                project_name="Demo Project",
                status="In progress",
                narrative="The current milestone validates telemetry visibility.",
            )

            short_text = short_path.read_text(encoding="utf-8")
            long_text = long_path.read_text(encoding="utf-8")
            readme_text = (root / "README.md").read_text(encoding="utf-8")
            self.assertIn("Status: In progress", short_text)
            self.assertIn("The current milestone validates telemetry visibility.", short_text)
            self.assertNotIn("Old snapshot", short_text)
            self.assertIn("Earlier milestone", long_text)
            self.assertIn("The current milestone validates telemetry visibility.", long_text)
            self.assertIn("## Status: In progress", readme_text)

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
